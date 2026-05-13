#!/usr/bin/env python3
"""
nightly_visualizer.py — FFmpeg-based static music visualizer

Takes an MP3 + optional background image → produces 1920x1080 H.264 MP4 video
with waveform overlay and title text.

Usage:
    python3 nightly_visualizer.py --mp3 song.mp3 --title "Song Title" --output output.mp4
    python3 nightly_visualizer.py --mp3 song.mp3 --title "Test" --output out.mp4 --bg bg.png

Module usage:
    from nightly_visualizer import generate_visualizer
    result = generate_visualizer("song.mp3", "output.mp4", "My Song")
"""

import os
import re
import subprocess
import sys
import time
import argparse
from pathlib import Path

# ---------------------------------------------------------------------------
# Optional: Pollinations.ai fallback for background generation
# ---------------------------------------------------------------------------
_api_generate_background = None

try:
    import image_gen
    _api_generate_background = image_gen.generate_default_background
except ImportError:
    # Fallback: scripts/ dir might not be on sys.path
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    if _script_dir not in sys.path:
        sys.path.insert(0, _script_dir)
    try:
        import image_gen  # type: ignore
        _api_generate_background = image_gen.generate_default_background
    except ImportError:
        _api_generate_background = None

# prompt_gen — per-song image prompt generation from lyrics
_prompt_gen_module = None
try:
    import prompt_gen
    _prompt_gen_module = prompt_gen
except ImportError:
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    if _script_dir not in sys.path:
        sys.path.insert(0, _script_dir)
    try:
        import prompt_gen  # type: ignore
        _prompt_gen_module = prompt_gen
    except ImportError:
        _prompt_gen_module = None


# ---------------------------------------------------------------------------
# FFmpeg detection
# ---------------------------------------------------------------------------
def _find_ffmpeg():
    """Locate FFmpeg binary. Returns path or None."""
    for path in ["ffmpeg", "/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg"]:
        try:
            subprocess.run([path, "-version"], capture_output=True, timeout=5)
            return path
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


_FFMPEG = _find_ffmpeg()


# ---------------------------------------------------------------------------
# Font detection for CJK text rendering
# ---------------------------------------------------------------------------
def _find_cjk_font():
    """Find a CJK-capable font on the system. Falls back to DejaVu Sans."""
    candidates = [
        # NotoSansCJK variants
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
        "/usr/share/fonts/truetype/noto/NotoSansCJKsc-Regular.otf",
        # WenQuanYi (good CJK coverage)
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        # Fallback: DejaVu Sans (no CJK, but at least ASCII renders)
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


# ---------------------------------------------------------------------------
# Background image detection + Pollinations.ai fallback
# ---------------------------------------------------------------------------
def _find_background():
    """
    Find a background image from local assets.
    Falls back to Pollinations.ai generation if none exist.
    Returns path or None.
    """
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "backgrounds"),
        os.path.expanduser("/mnt/d/Hermes/songs/assets/backgrounds/"),
    ]
    image_exts = {".png", ".jpg", ".jpeg", ".webp"}
    for bg_dir in candidates:
        if os.path.isdir(bg_dir):
            for fname in sorted(os.listdir(bg_dir)):
                if os.path.splitext(fname)[1].lower() in image_exts:
                    path = os.path.join(bg_dir, fname)
                    if os.path.isfile(path):
                        return path
    # Fallback: generate via Pollinations.ai
    return _generate_background_via_api()


def _generate_background_via_api():
    """Generate a background image via Pollinations.ai when no local one exists."""
    if _api_generate_background is None:
        print("[nightly:visualizer] image_gen module not available — cannot generate background",
              file=sys.stderr)
        return None

    bg_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets", "backgrounds",
    )
    os.makedirs(bg_dir, exist_ok=True)
    out_path = os.path.join(bg_dir, "api-generated-bg.jpg")

    try:
        print("[nightly:visualizer] No local background — generating via Pollinations.ai...")
        result = _api_generate_background(out_path=out_path)
        if result and os.path.isfile(result):
            size_kb = os.path.getsize(result) / 1024
            print(f"[nightly:visualizer] Generated background via API: {result} ({size_kb:.1f} KB)")
            return result
    except Exception as e:
        print(f"[nightly:visualizer] Pollinations.ai background generation failed: {e}",
              file=sys.stderr)

    return None


# ---------------------------------------------------------------------------
# Mood detection — Phase 2: mood-based color palettes for waveform
# ---------------------------------------------------------------------------
MOOD_PALETTES = {
    "romantic": "#FF6B6B|#FF9F9F|#FFD4D4",     # Pinks
    "melancholy": "#4A90D9|#6A5ACD|#2F4F7F",    # Blues
    "upbeat": "#FFD700|#FF8C00|#FF6347",         # Warm bright
    "calm": "#98D8C8|#7EC8E3|#B8E6D0",          # Pastels
    "energetic": "#FF3366|#FF6633|#FFCC00",      # Vibrant
    "sad": "#708090|#4A5568|#2D3748",            # Greys
    "chill": "#A29BFE|#6C5CE7|#DDA0DD",          # Purple/lavender
}

# Keywords for rule-based mood detection fallback
# Title matches weighted higher (checked twice), lyrics checked once
_MOOD_KEYWORDS = {
    "romantic": [
        "爱", "love", "forever", "永远", "heart", "you", "你",
        "kiss", "吻", "together", "一起", "baby", "亲爱的",
    ],
    "melancholy": [
        "泪", "cry", "sad", "离开", "leave", "gone", "失去",
        "lost", "寂寞", "lonely", "孤独", "回忆", "memory",
    ],
    "upbeat": [
        "阳光", "sun", "smile", "happy", "joy", "快乐",
        "笑", "跳", "奔跑", "run", "dance", "舞", "shine",
    ],
    "calm": [
        "星", "star", "moon", "night", "梦", "dream",
        "温柔", "gentle", "静", "quiet", "peace", "月",
    ],
    "energetic": [
        "fire", "burn", "power", "strong", "强", "燃",
        "fight", "never", "give", "up", "energy", "爆发",
    ],
    "sad": [
        "泪", "cry", "sad", "离开", "gone", "goodbye",
        "再见", "痛", "rain", "雨", "hurt", "broken", "break",
    ],
    "chill": [
        "梦", "dream", "温柔", "wind", "风", "cloud", "云",
        "float", "fly", "飞翔", "free", "breeze", "sky", "天空",
    ],
}

_DEFAULT_MOOD = "chill"


def detect_mood_from_lyrics(lyrics, title="", theme_mood=None):
    """Detect song mood from lyrics keywords, with optional weekly theme boost.

    Rule-based fallback: scores each mood by keyword matches.
    Title is weighted 2x (checked case-insensitive).
    Lyrics are weighted 1x.
    Theme mood (from weekly themes) gets +2 boost to ensure channel consistency.

    Args:
        lyrics: Full lyrics text
        title: Song title (optional, weighted higher)
        theme_mood: Optional mood key from weekly themes (e.g. "romantic").
                    Gets a +2 score boost for channel identity consistency.

    Returns:
        Tuple of (mood_key, palette_string) — e.g. ("romantic", "#FF6B6B|#FF9F9F|#FFD4D4")
    """
    title_lower = title.lower() if title else ""
    lyrics_lower = lyrics.lower() if lyrics else ""

    scores = {}
    for mood, keywords in _MOOD_KEYWORDS.items():
        score = 0
        for kw in keywords:
            kw_lower = kw.lower()
            # Title matches count 2x
            if title_lower:
                score += title_lower.count(kw_lower) * 2
            # Lyrics matches count 1x
            score += lyrics_lower.count(kw_lower)
        if score > 0 or mood == theme_mood:
            scores[mood] = score

    # Boost weekly theme mood for channel identity consistency
    if theme_mood and theme_mood in scores:
        scores[theme_mood] += 2
        print(f"[nightly:visualizer] Theme mood boost: '{theme_mood}' +2")

    if scores:
        best = max(scores, key=scores.get)
        palette = MOOD_PALETTES[best]
        print(f"[nightly:visualizer] Detected mood: '{best}' (score {scores[best]}) → {palette}")
        return best, palette

    # Theme mood acts as final fallback even if no keywords matched
    if theme_mood and theme_mood in MOOD_PALETTES:
        print(f"[nightly:visualizer] No mood keywords found, using theme fallback '{theme_mood}'")
        return theme_mood, MOOD_PALETTES[theme_mood]

    print(f"[nightly:visualizer] No mood keywords found, default to '{_DEFAULT_MOOD}'")
    return _DEFAULT_MOOD, MOOD_PALETTES[_DEFAULT_MOOD]


# ---------------------------------------------------------------------------
# Full-song SRT generation — Phase 2: lyrics overlay on long-form videos
# ---------------------------------------------------------------------------
def _generate_full_song_srt(lyrics_text, duration_sec):
    """Generate SRT subtitles for the full song length.

    Distributes ALL non-tag lyric lines evenly across the full duration.

    Args:
        lyrics_text: Full lyrics with section markers like [Verse]
        duration_sec: Total song duration in seconds

    Returns:
        SRT-formatted string, or empty string if no suitable lyrics
    """
    lines = []
    for line in lyrics_text.split("\n"):
        stripped = line.strip()
        if stripped and not stripped.startswith("["):
            lines.append(stripped)
    if not lines:
        return ""

    chunk_duration = duration_sec / len(lines)
    srt_parts = []
    idx = 1
    for i in range(0, len(lines), 2):
        chunk = lines[i:i + 2]
        chunk_text = "\n".join(chunk)
        start = i * chunk_duration
        end = (i + len(chunk)) * chunk_duration
        # Ensure each subtitle is visible for at least 1.5s
        if end - start < 1.5:
            end = start + 1.5
        srt_parts.append(str(idx))
        srt_parts.append(f"{_format_srt_time(start)} --> {_format_srt_time(min(end, duration_sec))}")
        srt_parts.append(chunk_text)
        srt_parts.append("")
        idx += 1

    return "\n".join(srt_parts)


# ---------------------------------------------------------------------------
# Text escaping for FFmpeg drawtext
# ---------------------------------------------------------------------------
def _escape_ffmpeg_text(text):
    """Escape text for FFmpeg drawtext filter (single-quote delimited)."""
    return text.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")


# ---------------------------------------------------------------------------
# Core visualizer
# ---------------------------------------------------------------------------
def generate_visualizer(mp3_path, output_path, title, background_image=None,
                        duration_sec=None, lyrics="", mood_palette=None,
                        lyrics_overlay=True):
    """
    Generate an MP4 visualizer video from an MP3 file.

    Phase 2 enhancements:
    - Mood-based waveform colors (if mood_palette provided)
    - Full-song SRT subtitle overlay (if lyrics and lyrics_overlay)

    Args:
        mp3_path: Path to input MP3 file
        output_path: Path for output MP4 file
        title: Song title for text overlay
        background_image: Optional path to background image
        duration_sec: Optional max duration in seconds (truncates if set)
        lyrics: Full lyrics text for SRT subtitle generation (Phase 2)
        mood_palette: Color palette string like "#FF6B6B|#4ECDC4" (Phase 2)
        lyrics_overlay: Whether to burn SRT subtitles into video (Phase 2)

    Returns:
        dict with keys: path, duration, status (ok/failed), error (if failed)
    """
    result = {
        "path": output_path,
        "duration": 0,
        "status": "failed",
        "error": None,
    }

    if not _FFMPEG:
        result["error"] = "FFmpeg not found on system"
        print(f"[nightly:visualizer] {result['error']}", file=sys.stderr)
        return result

    if not os.path.exists(mp3_path):
        result["error"] = f"MP3 not found: {mp3_path}"
        print(f"[nightly:visualizer] {result['error']}", file=sys.stderr)
        return result

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Resolve background image
    bg_path = background_image
    if not bg_path:
        bg_path = _find_background()
    use_bg_image = bg_path and os.path.isfile(bg_path)

    # Find font
    font_path = _find_cjk_font()
    has_font = bool(font_path)

    # Escaped title for drawtext
    escaped_title = _escape_ffmpeg_text(title)

    # ── Phase 2: Mood-based waveform colors ──────────────────────────────
    colors_used = "#FF6B6B|#4ECDC4"  # default
    if mood_palette:
        colors_used = mood_palette
        print(f"[nightly:visualizer] Using mood palette: {mood_palette}")

    # ── Phase 2: Full-song SRT subtitle generation ───────────────────────
    temp_srt_path = None
    srt_content = ""
    if lyrics and lyrics_overlay:
        actual_duration = duration_sec or _probe_duration(mp3_path)
        if actual_duration > 0:
            srt_content = _generate_full_song_srt(lyrics, actual_duration)
            if srt_content:
                # Write SRT to temp file for FFmpeg subtitles filter
                temp_srt_path = os.path.join(
                    output_dir or ".",
                    f".srt-temp-{int(time.time())}.srt"
                )
                with open(temp_srt_path, "w", encoding="utf-8") as f:
                    f.write(srt_content)
                # Also save a permanent copy alongside the MP4
                srt_permanent = output_path.replace(".mp4", ".srt")
                with open(srt_permanent, "w", encoding="utf-8") as f:
                    f.write(srt_content)
                print(f"[nightly:visualizer] Full-song SRT: {len(srt_content)} chars, "
                      f"{srt_content.count('\\n\\n') + 1} subtitles")
        else:
            print(f"[nightly:visualizer] Cannot generate SRT — duration unknown",
                  file=sys.stderr)

    # Build FFmpeg command
    cmd = [_FFMPEG, "-y"]

    # Input: background or black color source
    if use_bg_image:
        cmd.extend(["-loop", "1", "-i", bg_path])
    else:
        cmd.extend(["-f", "lavfi", "-i", "color=c=#0a0f1e:s=1920x1080:r=1"])

    # Input: audio
    cmd.extend(["-i", mp3_path])

    # Build filter_complex
    if use_bg_image:
        bg_chain = "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2[bg]"
    else:
        bg_chain = "[0:v]setsar=1[bg]"

    waves_chain = (
        "[1:a]showwaves=s=1920x400:mode=cline:rate=25:"
        f"colors={colors_used}[waves]"
    )

    # Overlay chain: background + waveform + title + optional subtitles
    overlay_parts = [f"[bg][waves]overlay=0:(H-400)/2"]

    if has_font:
        overlay_parts.append(
            f"drawtext=text='{escaped_title}':fontfile={font_path}:"
            f"fontcolor=white:fontsize=48:x=(w-text_w)/2:y=H-100:"
            f"expansion=none"
        )

    if temp_srt_path and srt_content:
        overlay_parts.append(
            f"subtitles={temp_srt_path}:"
            f"fontsdir={os.path.dirname(font_path) if font_path else '/'}"
        )

    overlay_chain = ",".join(overlay_parts) + "[out]"
    filter_complex = ";".join([bg_chain, waves_chain, overlay_chain])

    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-map", "1:a",
    ])

    # Duration limit
    if duration_sec is not None and duration_sec > 0:
        cmd.extend(["-t", str(duration_sec)])

    # Output encoding
    cmd.extend([
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        output_path,
    ])

    cmd_str = " ".join(cmd)
    print(f"[nightly:visualizer] Generating: {os.path.basename(output_path)}")
    if not use_bg_image:
        print(f"[nightly:visualizer] No background image found, using dark gradient")
    if not has_font:
        print(f"[nightly:visualizer] No CJK font found, skipping text overlay")

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if proc.returncode != 0:
            stderr_tail = proc.stderr.strip().split("\n")[-5:]
            result["error"] = f"FFmpeg exited {proc.returncode}: {'; '.join(stderr_tail)}"
            print(f"[nightly:visualizer] FAILED: {result['error']}", file=sys.stderr)
            return result

        if not os.path.exists(output_path) or os.path.getsize(output_path) < 1000:
            result["error"] = "Output file missing or too small"
            print(f"[nightly:visualizer] {result['error']}", file=sys.stderr)
            return result

        # Get duration via ffprobe
        dur = _probe_duration(output_path)
        result["duration"] = dur
        result["status"] = "ok"
        result["error"] = None

        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"[nightly:visualizer] OK — {size_mb:.1f}MB, {dur:.1f}s → {output_path}")

    except subprocess.TimeoutExpired:
        result["error"] = "FFmpeg timed out (10 min limit)"
        print(f"[nightly:visualizer] {result['error']}", file=sys.stderr)
    except Exception as e:
        result["error"] = str(e)
        print(f"[nightly:visualizer] Exception: {e}", file=sys.stderr)
    finally:
        # Clean up temp SRT file
        if temp_srt_path and os.path.exists(temp_srt_path):
            try:
                os.remove(temp_srt_path)
            except Exception:
                pass

    return result


def _probe_duration(file_path):
    """Get duration of media file via ffprobe."""
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", file_path],
            capture_output=True, text=True, timeout=15,
        )
        return float(proc.stdout.strip())
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Thumbnail generation
# ---------------------------------------------------------------------------
def generate_thumbnail(title, output_path, bg_image=None):
    """
    Generate a thumbnail image with title text overlay.

    Args:
        title: Song title to render
        output_path: Path for output thumbnail image
        bg_image: Optional background image path

    Returns:
        dict with keys: path, status (ok/failed), error (if failed)
    """
    if not _FFMPEG:
        return {"path": "", "status": "failed", "error": "FFmpeg not found"}

    if not bg_image:
        bg_image = _find_background()

    font_path = _find_cjk_font()
    escaped = _escape_ffmpeg_text(title)

    # Build background input
    if bg_image and os.path.isfile(bg_image):
        input_spec = ["-loop", "1", "-i", bg_image]
        scale_filter = "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2"
    else:
        input_spec = ["-f", "lavfi", "-i", "color=c=#0a0f1e:s=1280x720:d=1"]
        scale_filter = "format=yuv420p"

    cmd = [_FFMPEG, "-y"] + input_spec + [
        "-vf",
        f"{scale_filter},"
        f"drawtext=text='{escaped}':"
        f"fontfile={font_path}:"
        f"fontcolor=white:fontsize=64:"
        f"x=(w-text_w)/2:y=(h-text_h)/2:"
        f"shadowcolor=black:shadowx=3:shadowy=3:"
        f"expansion=none",
        "-frames:v", "1",
        "-q:v", "2",
        output_path,
    ]
    try:
        subprocess.run(cmd, check=True, timeout=30, capture_output=True)
        return {"path": output_path, "status": "ok"}
    except Exception as e:
        print(f"[visualizer] Thumbnail generation failed: {e}", file=sys.stderr)
        return {"path": "", "status": "failed", "error": str(e)}


# ---------------------------------------------------------------------------
# Per-song asset generation (backgrounds + thumbnails via Pollinations.ai)
# ---------------------------------------------------------------------------
def generate_per_song_assets(song_result, songs_dir, config=None):
    """Generate per-song background images and thumbnail for a single song.

    Uses prompt_gen (LLM) to create image prompts from song title/lyrics,
    then downloads via Pollinations.ai. All steps are try/except so failures
    don't block the pipeline.

    Args:
        song_result: Song result dict (must have title, lyrics, song_number keys)
        songs_dir: Output directory
        config: Optional config dict (uses visual section)

    Returns:
        Updated song_result dict with bg_path, bg_vertical_path, thumbnail_path keys
    """
    _ensure_script_dir_on_path()

    if config is None:
        config = {}

    visual_cfg = config.get("visual", {})
    if not visual_cfg.get("generate_backgrounds", True):
        print("[nightly:visualizer] Background generation disabled in config")
        song_result["bg_path"] = ""
        song_result["bg_vertical_path"] = ""
        song_result["thumbnail_path"] = song_result.get("thumbnail_path", "")
        return song_result

    title = song_result.get("title", "Unknown")
    lyrics = song_result.get("lyrics", "")
    style_tags = ""
    song_num = song_result.get("song_number", 0)
    from nightly_music import sanitize_filename
    safe = sanitize_filename(title)[:60]

    bg_path = os.path.join(songs_dir, f"{song_num:02d}-{safe}-bg.jpg")
    bg_vertical_path = os.path.join(songs_dir, f"{song_num:02d}-{safe}-bg-vertical.jpg")
    thumb_path = os.path.join(songs_dir, f"{song_num:02d}-{safe}-thumb.jpg")

    # Step A: Generate landscape prompt → download background
    try:
        landscape_result = _safe_generate_prompt(title, lyrics, style_tags, "landscape")
        if landscape_result:
            print(f"[nightly:visualizer] Landscape prompt ({landscape_result['source']}): "
                  f"{landscape_result['prompt'][:60]}...")
            image_gen.generate_background(
                landscape_result["prompt"], bg_path, 1920, 1080
            )
            song_result["bg_path"] = bg_path
            print(f"[nightly:visualizer] Background saved: {os.path.basename(bg_path)}")
        else:
            print("[nightly:visualizer] No landscape prompt generated — skipping bg")
            song_result["bg_path"] = ""
    except Exception as e:
        print(f"[nightly:visualizer] Landscape background failed: {e}", file=sys.stderr)
        song_result["bg_path"] = ""

    # Step B: Generate vertical prompt → download vertical background for Shorts
    try:
        vertical_result = _safe_generate_prompt(title, lyrics, style_tags, "vertical")
        if vertical_result:
            print(f"[nightly:visualizer] Vertical prompt ({vertical_result['source']}): "
                  f"{vertical_result['prompt'][:60]}...")
            image_gen.generate_background(
                vertical_result["prompt"], bg_vertical_path, 1080, 1920
            )
            song_result["bg_vertical_path"] = bg_vertical_path
            print(f"[nightly:visualizer] Vertical bg saved: {os.path.basename(bg_vertical_path)}")
        else:
            print("[nightly:visualizer] No vertical prompt generated — skipping vertical bg")
            song_result["bg_vertical_path"] = ""
    except Exception as e:
        print(f"[nightly:visualizer] Vertical background failed: {e}", file=sys.stderr)
        song_result["bg_vertical_path"] = ""

    # Step C: Generate thumbnail from landscape background
    if song_result.get("bg_path") and os.path.isfile(song_result["bg_path"]):
        try:
            image_gen.generate_thumbnail_from_bg(song_result["bg_path"], thumb_path)
            song_result["thumbnail_path"] = thumb_path
            print(f"[nightly:visualizer] Thumbnail generated from bg: {os.path.basename(thumb_path)}")
        except Exception as e:
            print(f"[nightly:visualizer] Thumbnail from bg failed: {e}", file=sys.stderr)
    else:
        print("[nightly:visualizer] No landscape bg available — thumbnail from bg skipped")

    return song_result


# ---------------------------------------------------------------------------
# YouTube Shorts generation (9:16 vertical, chorus-based)
# ---------------------------------------------------------------------------
def generate_short(mp3_path, title, lyrics, output_path, bg_path=None, max_duration=45):
    """Generate a YouTube Short (9:16 vertical video) from an MP3.

    Detects the loudest N-second segment (chorus), extracts it, and renders
    a 1080x1920 vertical video with waveform, title, and lyrics subtitles.

    Args:
        mp3_path: Path to input MP3 file
        title: Song title for overlay text
        lyrics: Song lyrics for subtitles
        output_path: Path for output MP4
        bg_path: Optional vertical background image (1080x1920)
        max_duration: Shorts duration in seconds (default 45)

    Returns:
        dict with keys: path, status (ok/failed/skipped), error
    """
    result = {"path": "", "status": "failed", "error": None}

    if not _FFMPEG:
        result["error"] = "FFmpeg not found — Shorts skipped"
        print(f"[nightly:visualizer] {result['error']}", file=sys.stderr)
        return result

    if not os.path.exists(mp3_path):
        result["error"] = f"MP3 not found: {mp3_path}"
        print(f"[nightly:visualizer] {result['error']}", file=sys.stderr)
        return result

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    audio_duration = _probe_duration(mp3_path)
    if audio_duration <= 0:
        result["error"] = "Could not determine audio duration"
        return result

    # Find the loudest segment (chorus)
    chorus_start = _find_loudest_window(mp3_path, max_duration)
    actual_duration = min(max_duration, audio_duration - chorus_start)

    # Temp files
    temp_dir = os.path.join(output_dir, f".shorts-tmp-{int(time.time())}")
    os.makedirs(temp_dir, exist_ok=True)
    temp_audio = os.path.join(temp_dir, "chorus.mp3")
    temp_srt = os.path.join(temp_dir, "subtitles.srt")

    try:
        # Extract chorus audio segment
        _extract_audio_segment(mp3_path, temp_audio, chorus_start, actual_duration)
        print(f"[nightly:visualizer] Chorus: {chorus_start:.1f}s – "
              f"{chorus_start + actual_duration:.1f}s ({actual_duration:.1f}s)")

        # Generate SRT subtitles from lyrics
        srt_content = _generate_chorus_srt(lyrics, actual_duration)
        if srt_content:
            with open(temp_srt, "w", encoding="utf-8") as f:
                f.write(srt_content)

        # Resolve background
        use_bg = bg_path and os.path.isfile(bg_path)

        # Find font
        font_path = _find_cjk_font()
        has_font = bool(font_path)

        # Escaped title
        escaped_title = _escape_ffmpeg_text(title)

        # Build FFmpeg command
        cmd = [_FFMPEG, "-y"]

        if use_bg:
            cmd.extend(["-loop", "1", "-i", bg_path])
        else:
            cmd.extend(["-f", "lavfi", "-i", "color=c=#0a0f1e:s=1080x1920:r=1"])

        cmd.extend(["-i", temp_audio])

        # Build filter_complex
        if use_bg:
            bg_chain = (
                "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
                "pad=1080:1920:(ow-iw)/2:(oh-ih)/2[bg]"
            )
        else:
            bg_chain = "[0:v]setsar=1[bg]"

        waves_chain = (
            "[1:a]showwaves=s=1080x300:mode=cline:rate=25:"
            "colors=#FF6B6B|#4ECDC4[waves]"
        )

        # Overlay: background + waveform + title + subtitles
        overlay_parts = ["[bg][waves]overlay=0:H-380"]

        if has_font:
            overlay_parts.append(
                f"drawtext=text='{escaped_title}':fontfile={font_path}:"
                f"fontcolor=white:fontsize=56:"
                f"x=(w-text_w)/2:y=80:expansion=none:"
                f"shadowcolor=black:shadowx=3:shadowy=3"
            )

        if srt_content:
            overlay_parts.append(
                f"subtitles={temp_srt}:fontsdir={os.path.dirname(font_path) if font_path else '/'}"
            )

        overlay_chain = ",".join(overlay_parts) + "[out]"
        filter_complex = ";".join([bg_chain, waves_chain, overlay_chain])

        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-map", "1:a",
            "-t", str(actual_duration),
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            output_path,
        ])

        print(f"[nightly:visualizer] Generating Short: {os.path.basename(output_path)}")
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        if proc.returncode != 0:
            stderr_tail = proc.stderr.strip().split("\n")[-5:]
            result["error"] = f"FFmpeg exited {proc.returncode}: {'; '.join(stderr_tail)}"
            print(f"[nightly:visualizer] Short FAILED: {result['error']}", file=sys.stderr)
            return result

        if not os.path.exists(output_path) or os.path.getsize(output_path) < 1000:
            result["error"] = "Short output file missing or too small"
            print(f"[nightly:visualizer] {result['error']}", file=sys.stderr)
            return result

        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        dur = _probe_duration(output_path)
        result["path"] = output_path
        result["status"] = "ok"
        result["duration"] = dur
        print(f"[nightly:visualizer] Short OK — {size_mb:.1f}MB, {dur:.1f}s → {output_path}")

    except subprocess.TimeoutExpired:
        result["error"] = "FFmpeg timed out (10 min limit)"
        print(f"[nightly:visualizer] {result['error']}", file=sys.stderr)
    except Exception as e:
        result["error"] = str(e)
        print(f"[nightly:visualizer] Short exception: {e}", file=sys.stderr)
    finally:
        # Clean up temp dir
        try:
            for f in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, f))
            os.rmdir(temp_dir)
        except Exception:
            pass

    return result


def _find_loudest_window(mp3_path, window_sec=45):
    """Find the start time (seconds) of the loudest window_sec segment.

    Uses ffprobe with astats to get per-second RMS loudness, then slides
    a window across to find the segment with highest average loudness.
    """
    duration = _probe_duration(mp3_path)
    if duration <= window_sec:
        return 0.0

    # Get per-second RMS values via ffprobe
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-f", "lavfi",
            "-i", f"amovie={mp3_path},aresample=44100,astats=metadata=1:reset=44100",
            "-show_entries", "frame_tags=lavfi.astats.Overall.RMS_level",
            "-of", "csv=p=0",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            return max(0.0, (duration - window_sec) / 2)

        rms_values = []
        for line in proc.stdout.strip().split("\n"):
            line = line.strip()
            if line and line != "-inf":
                try:
                    rms_values.append(float(line))
                except ValueError:
                    pass

        if len(rms_values) < 2:
            return max(0.0, (duration - window_sec) / 2)

        # Slide window to find loudest segment
        window_samples = min(window_sec, len(rms_values))
        if window_samples >= len(rms_values):
            return 0.0

        best_start = 0
        best_avg = float("-inf")

        # Convert RMS dB to linear (higher = louder)
        # RMS is negative dB, more negative = quieter
        for i in range(len(rms_values) - window_samples + 1):
            window = rms_values[i:i + window_samples]
            # Filter out -inf values
            valid = [v for v in window if v != float("-inf")]
            if not valid:
                continue
            avg = sum(valid) / len(valid)
            if avg > best_avg:
                best_avg = avg
                best_start = i

        return float(best_start)

    except Exception:
        return max(0.0, (duration - window_sec) / 2)


def _extract_audio_segment(mp3_path, output_path, start_sec, duration_sec):
    """Extract a segment of an MP3 file using FFmpeg."""
    cmd = [
        _FFMPEG, "-y",
        "-ss", str(start_sec),
        "-i", mp3_path,
        "-t", str(duration_sec),
        "-c", "copy",
        output_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    proc.check_returncode()
    return output_path


def _generate_chorus_srt(lyrics, duration_sec=45):
    """Generate SRT subtitle content from lyrics for a short video.

    Priority:
    1. Extract lines within [Chorus] tags (preferred)
    2. Fallback to middle third if no chorus tags found

    Args:
        lyrics: Full lyrics text
        duration_sec: Duration in seconds to fill

    Returns:
        SRT-formatted string, or empty string if no suitable lyrics found
    """
    # Try to find [Chorus] section first
    in_chorus = False
    chorus_lines = []
    for line in lyrics.split("\n"):
        stripped = line.strip()
        if stripped == "[Chorus]":
            in_chorus = True
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            in_chorus = False
            continue
        if in_chorus and stripped:
            chorus_lines.append(stripped)

    # Fallback to middle third if no chorus tags found
    if len(chorus_lines) < 2:
        lines = [
            l.strip() for l in lyrics.split("\n")
            if l.strip() and not l.strip().startswith("[")
        ]
        if not lines:
            return ""
        if len(lines) > 8:
            start = len(lines) // 3
            chorus_lines = lines[start:start + 6]
        else:
            chorus_lines = lines[:4]

    # Filter out any lines that are too short or look like metadata
    chorus_lines = [l for l in chorus_lines if len(l) > 2]

    if not chorus_lines:
        return ""

    # Distribute evenly across the duration
    num_lines = len(chorus_lines)
    duration_per_line = max(3.0, duration_sec / num_lines)

    srt_parts = []
    for i, line in enumerate(chorus_lines):
        start = i * duration_per_line
        end = min((i + 1) * duration_per_line, duration_sec)
        # Only include if there's enough time to display
        if end - start >= 1.5:
            srt_parts.append(str(i + 1))
            srt_parts.append(
                f"{_format_srt_time(start)} --> {_format_srt_time(end)}"
            )
            srt_parts.append(line)
            srt_parts.append("")

    return "\n".join(srt_parts)


def _format_srt_time(seconds):
    """Format seconds to SRT timestamp: HH:MM:SS,mmm."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _ensure_script_dir_on_path():
    """Ensure the scripts directory is on sys.path for imports."""
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    if _script_dir not in sys.path:
        sys.path.insert(0, _script_dir)


# _sanitize_for_filename removed — use nightly_music.sanitize_filename instead


def _safe_generate_prompt(title, lyrics, style_tags, orientation):
    """Safely call prompt_gen.generate_prompt_from_lyrics, returning None on failure."""
    if _prompt_gen_module is None:
        print("[nightly:visualizer] prompt_gen module not available", file=sys.stderr)
        return None
    try:
        return _prompt_gen_module.generate_prompt_from_lyrics(
            title, lyrics, style_tags, orientation
        )
    except Exception as e:
        print(f"[nightly:visualizer] prompt_gen failed: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Generate MP4 visualizer from MP3 + background"
    )
    parser.add_argument("--mp3", type=str, required=True, help="Input MP3 file path")
    parser.add_argument("--title", type=str, required=True, help="Song title for overlay")
    parser.add_argument("--output", type=str, required=True, help="Output MP4 file path")
    parser.add_argument("--bg", type=str, default=None, help="Background image path (optional)")
    parser.add_argument("--duration", type=float, default=None, help="Max duration in seconds")
    args = parser.parse_args()

    result = generate_visualizer(
        mp3_path=args.mp3,
        output_path=args.output,
        title=args.title,
        background_image=args.bg,
        duration_sec=args.duration,
    )

    if result["status"] == "ok":
        print(f"Visualizer: {result['path']} ({result['duration']:.1f}s)")
        sys.exit(0)
    else:
        print(f"ERROR: {result['error']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
