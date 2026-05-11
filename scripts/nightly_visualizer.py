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
import argparse
from pathlib import Path


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
# Background image detection
# ---------------------------------------------------------------------------
def _find_background():
    """Find a background image from assets. Returns path or None."""
    candidates = [
        os.path.expanduser("~/.hermes/songs/assets/backgrounds/"),
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
    return None


# ---------------------------------------------------------------------------
# Text escaping for FFmpeg drawtext
# ---------------------------------------------------------------------------
def _escape_ffmpeg_text(text):
    """Escape text for FFmpeg drawtext filter (single-quote delimited)."""
    return text.replace("\\", "\\\\").replace("'", "\\'")


# ---------------------------------------------------------------------------
# Core visualizer
# ---------------------------------------------------------------------------
def generate_visualizer(mp3_path, output_path, title, background_image=None, duration_sec=None):
    """
    Generate an MP4 visualizer video from an MP3 file.

    Args:
        mp3_path: Path to input MP3 file
        output_path: Path for output MP4 file
        title: Song title for text overlay
        background_image: Optional path to background image
        duration_sec: Optional max duration in seconds (truncates if set)

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
        "colors=#FF6B6B|#4ECDC4[waves]"
    )

    if has_font:
        overlay_chain = (
            f"[bg][waves]overlay=0:(H-400)/2,"
            f"drawtext=text='{escaped_title}':fontfile={font_path}:"
            f"fontcolor=white:fontsize=48:x=(w-text_w)/2:y=H-100:"
            f"expansion=none[out]"
        )
    else:
        overlay_chain = "[bg][waves]overlay=0:(H-400)/2[out]"

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
