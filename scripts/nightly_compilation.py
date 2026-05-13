#!/usr/bin/env python3
"""
nightly_compilation.py — Weekly compilation album for ManggoMusicCH.

Runs on Sundays only. Concatenates Mon-Sat's Hero videos into a single
30-60 minute album with chapter markers, then uploads to YouTube.

Usage:
    python3 nightly_compilation.py --date 2026-05-17
    python3 nightly_compilation.py --date 2026-05-17 --dry-run
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths — project-relative via PROJECT_DIR
# ---------------------------------------------------------------------------
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(PROJECT_DIR, "scripts")
SONGS_BASE = os.path.join(PROJECT_DIR, "output")
CONFIG_PATH = os.path.join(PROJECT_DIR, "config", "nightly-music.yaml")

# Ensure scripts dir on path for imports
sys.path.insert(0, SCRIPTS_DIR)


# ---------------------------------------------------------------------------
# Week date helpers
# ---------------------------------------------------------------------------

def get_week_dates(date_str):
    """Get Mon-Sat dates for the week containing date_str.

    Sunday (date_str) is the compilation day; we collect Mon-Sat videos.

    Args:
        date_str: YYYY-MM-DD format, should be a Sunday

    Returns:
        List of YYYY-MM-DD strings for Mon-Sat of that week
    """
    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    # Monday = 0, Sunday = 6
    monday = dt - datetime.timedelta(days=dt.weekday())
    return [(monday + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(6)]  # Mon (0) to Sat (5)


def get_chinese_week_label(date_str):
    """Generate a Chinese week label like 'Week of May 11'.

    Args:
        date_str: YYYY-MM-DD format (Sunday)

    Returns:
        Chinese-formatted week label string
    """
    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    monday = dt - datetime.timedelta(days=dt.weekday())
    # Format: "May 11" in Chinese-style date
    month_names = {
        1: "January", 2: "February", 3: "March", 4: "April",
        5: "May", 6: "June", 7: "July", 8: "August",
        9: "September", 10: "October", 11: "November", 12: "December",
    }
    month_en = month_names[monday.month]
    return f"Week of {month_en} {monday.day}"


# ---------------------------------------------------------------------------
# Video duration probe
# ---------------------------------------------------------------------------

def get_video_duration(file_path):
    """Get duration of a media file in seconds via ffprobe.

    Args:
        file_path: Path to media file

    Returns:
        Duration in seconds (float), or 0.0 on failure
    """
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of",
             "default=noprint_wrappers=1:nokey=1", file_path],
            capture_output=True, text=True, timeout=15,
        )
        return float(proc.stdout.strip())
    except (ValueError, subprocess.TimeoutExpired, FileNotFoundError):
        return 0.0


# ---------------------------------------------------------------------------
# Video collection — find Hero videos from Mon-Sat
# ---------------------------------------------------------------------------

def collect_hero_videos(week_dates):
    """Collect Hero videos (01-*.mp4) from each day's output directory.

    Scans each Mon-Sat output/<date>/ directory for files matching
    the pattern "01-*-viz.mp4" (song #1 = Hero).

    Args:
        week_dates: List of YYYY-MM-DD date strings

    Returns:
        List of (date, video_path) tuples, in chronological order,
        only including dates where a valid Hero video exists
    """
    collected = []
    for date in week_dates:
        day_dir = os.path.join(SONGS_BASE, date)
        if not os.path.isdir(day_dir):
            print(f"[compilation] No output dir for {date} — skipping")
            continue

        # Find Hero video: song #1 = "01-*-viz.mp4"
        candidates = []
        for fname in sorted(os.listdir(day_dir)):
            if fname.startswith("01-") and fname.endswith("-viz.mp4"):
                fpath = os.path.join(day_dir, fname)
                if os.path.isfile(fpath) and os.path.getsize(fpath) > 1000:
                    candidates.append(fpath)

        if candidates:
            # Take the first matching file (should be only one)
            collected.append((date, candidates[0]))
            size_mb = os.path.getsize(candidates[0]) / (1024 * 1024)
            print(f"[compilation] Found Hero for {date}: "
                  f"{os.path.basename(candidates[0])} ({size_mb:.1f}MB)")
        else:
            print(f"[compilation] No Hero video for {date} — skipping")

    return collected


# ---------------------------------------------------------------------------
# FFmpeg concat
# ---------------------------------------------------------------------------

def build_concat_file(video_paths, output_path):
    """Create FFmpeg concat file and run the concat command.

    Uses the concat demuxer which requires all videos to have the same
    codec parameters. We re-encode to ensure compatibility.

    Args:
        video_paths: List of (date, path) tuples
        output_path: Path for the output MP4 file

    Returns:
        True on success, False on failure
    """
    concat_path = output_path + ".txt"
    try:
        with open(concat_path, "w", encoding="utf-8") as f:
            for _date, vp in video_paths:
                abs_path = os.path.abspath(vp)
                # Escape single quotes for FFmpeg concat file
                escaped = abs_path.replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")

        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_path,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            output_path,
        ]

        print(f"[compilation] Concatenating {len(video_paths)} videos...")
        print(f"[compilation] Output: {os.path.basename(output_path)}")

        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=3600,
        )

        if proc.returncode != 0:
            stderr_tail = proc.stderr.strip().split("\n")[-5:]
            print(f"[compilation] FFmpeg concat FAILED (rc={proc.returncode}): "
                  f"{'; '.join(stderr_tail)}", file=sys.stderr)
            return False

        if not os.path.exists(output_path) or os.path.getsize(output_path) < 1000:
            print(f"[compilation] Output file missing or too small after concat",
                  file=sys.stderr)
            return False

        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        dur = get_video_duration(output_path)
        print(f"[compilation] Concat OK — {size_mb:.1f}MB, {dur:.0f}s")
        return True

    except subprocess.TimeoutExpired:
        print(f"[compilation] FFmpeg concat timed out after 1 hour",
              file=sys.stderr)
        return False
    except Exception as e:
        print(f"[compilation] Concat exception: {e}", file=sys.stderr)
        return False
    finally:
        if os.path.exists(concat_path):
            try:
                os.remove(concat_path)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Chapter marker generation
# ---------------------------------------------------------------------------

def get_chapter_timestamps(video_paths):
    """Generate chapter markers from video durations.

    Args:
        video_paths: List of (date, path) tuples

    Returns:
        List of dicts with keys: time, name, duration, date
    """
    chapters = []
    current_time = 0.0
    for date, vp in video_paths:
        if os.path.exists(vp):
            duration = get_video_duration(vp)
            # Extract song name from filename: "01-Song-Name-viz.mp4"
            basename = os.path.basename(vp)
            # Strip "01-" prefix and "-viz.mp4" suffix
            name_part = basename
            if name_part.startswith("01-"):
                name_part = name_part[3:]
            if name_part.endswith("-viz.mp4"):
                name_part = name_part[:-8]
            # Clean up dashes and underscores for display
            display_name = name_part.replace("-", " ").replace("_", " ").strip().title()

            chapters.append({
                "time": current_time,
                "name": display_name or "Song",
                "duration": duration,
                "date": date,
            })
            current_time += duration if duration > 0 else 180  # fallback: 3 min
        else:
            # File exists per collection, but double-check
            chapters.append({
                "time": current_time,
                "name": "Missing Video",
                "duration": 180,
                "date": date,
            })
            current_time += 180

    return chapters


def format_chapters_for_description(chapters):
    """Format chapters as YouTube timestamps for video description.

    YouTube timestamps format:
        0:00 — Title
        3:45 — Title 2

    Args:
        chapters: List of chapter dicts from get_chapter_timestamps()

    Returns:
        Formatted string with newlines
    """
    lines = ["⏱ Timestamps\n"]
    for i, ch in enumerate(chapters):
        minutes = int(ch["time"] // 60)
        seconds = int(ch["time"] % 60)
        lines.append(
            f"{minutes}:{seconds:02d} — Day {i+1} ({ch['date']}): {ch['name']}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Compilation thumbnail generation via Pollinations.ai
# ---------------------------------------------------------------------------

def generate_compilation_thumbnail(output_dir, week_label):
    """Generate a compilation album thumbnail.

    Uses existing image_gen.generate_default_background as a simple
    fallback, or creates a text-based thumbnail via FFmpeg.

    Args:
        output_dir: Directory to save the thumbnail
        week_label: Week label string for text overlay

    Returns:
        Path to thumbnail image, or empty string on failure
    """
    thumb_path = os.path.join(output_dir, "compilation-thumb.jpg")

    # Try using FFmpeg to create a branded thumbnail with text overlay
    try:
        font_path = _find_cjk_font()
        if font_path:
            escaped_label = _escape_ffmpeg_text(
                f"ManggoMusicCH Weekly\n{week_label}"
            )
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i",
                "color=c=#1a1a2e:s=1280x720:d=1",
                "-vf",
                f"drawtext=text='{escaped_label}':"
                f"fontfile={font_path}:"
                f"fontcolor=white:fontsize=48:"
                f"x=(w-text_w)/2:y=(h-text_h)/2 - 30:"
                f"shadowcolor=black:shadowx=3:shadowy=3:"
                f"expansion=none,"
                f"drawtext=text='Weekly Compilation':"
                f"fontfile={font_path}:"
                f"fontcolor=#FFD700:fontsize=36:"
                f"x=(w-text_w)/2:y=(h+text_h)/2 + 30:"
                f"shadowcolor=black:shadowx=2:shadowy=2:"
                f"expansion=none",
                "-frames:v", "1",
                "-q:v", "2",
                thumb_path,
            ]
            subprocess.run(cmd, check=True, timeout=30, capture_output=True)
            if os.path.exists(thumb_path):
                size_kb = os.path.getsize(thumb_path) / 1024
                print(f"[compilation] Thumbnail generated: {thumb_path} "
                      f"({size_kb:.1f} KB)")
                return thumb_path
    except Exception as e:
        print(f"[compilation] Thumbnail generation failed: {e}",
              file=sys.stderr)

    return ""


from nightly_visualizer import _find_cjk_font, _escape_ffmpeg_text


# ---------------------------------------------------------------------------
# YouTube upload for compilation
# ---------------------------------------------------------------------------

def upload_compilation_to_youtube(video_path, title, description,
                                  thumbnail_path, date_label, dry_run=False):
    """Upload the compilation video to YouTube.

    Imports nightly_uploader.upload_video dynamically to avoid circular deps.

    Args:
        video_path: Path to compilation MP4
        title: Video title
        description: Video description with chapter markers
        thumbnail_path: Optional thumbnail path
        date_label: YYYY-MM-DD date for scheduling
        dry_run: If True, log intent without uploading

    Returns:
        dict with status info
    """
    if dry_run:
        print(f"[compilation] [DRY RUN] Would upload compilation to YouTube")
        print(f"[compilation] [DRY RUN]   Title: {title[:80]}")
        print(f"[compilation] [DRY RUN]   File: {os.path.basename(video_path)}")
        print(f"[compilation] [DRY RUN]   Thumb: {os.path.basename(thumbnail_path) if thumbnail_path else 'none'}")
        return {"status": "ok", "video_id": "DRY-RUN-COMP", "youtube_url": ""}

    try:
        sys.path.insert(0, SCRIPTS_DIR)
        from nightly_uploader import upload_video as _upload_video
    except ImportError:
        print("[compilation] nightly_uploader not available — skipping upload",
              file=sys.stderr)
        return {"status": "failed", "error": "uploader module not available"}

    # Load config for YouTube settings
    config = _load_config_simple()
    yt_cfg = config.get("youtube", {})
    if not yt_cfg.get("enabled", False):
        print("[compilation] YouTube upload disabled in config — skipping")
        return {"status": "disabled", "error": None}

    tags = yt_cfg.get("tags", ["AI Music", "华语流行", "AISong"])
    privacy = yt_cfg.get("privacy", "private")
    category = yt_cfg.get("category", "10")

    # Schedule for 10:00 SGT on Sunday
    publish_at = None
    try:
        from datetime import datetime, timezone, timedelta
        sgt = timezone(timedelta(hours=8))
        publish_dt = datetime.strptime(date_label, "%Y-%m-%d").replace(
            hour=10, minute=0, second=0, tzinfo=sgt
        )
        publish_at = publish_dt.isoformat()
    except Exception as e:
        print(f"[compilation] WARNING: publish_at calc failed: {e}",
              file=sys.stderr)

    # Append compilation to tags
    full_tags = list(tags)
    if "#WeeklyCompilation" not in full_tags:
        full_tags.append("WeeklyCompilation")

    try:
        result = _upload_video(
            video_path=video_path,
            title=title,
            description=description,
            tags=full_tags,
            category_id=category,
            privacy=privacy,
            thumbnail_path=thumbnail_path,
            publish_at=publish_at,
        )
        return result
    except Exception as e:
        print(f"[compilation] Upload exception: {e}", file=sys.stderr)
        return {"status": "failed", "error": str(e)}


def _load_config_simple():
    """Minimal YAML config loader for this module."""
    defaults = {
        "youtube": {"enabled": False, "tags": [], "privacy": "private", "category": "10"},
        "compilation": {"enabled": True, "max_duration_min": 45},
    }
    try:
        import yaml
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            if cfg:
                for k, v in defaults.items():
                    if k not in cfg:
                        cfg[k] = v
                return cfg
    except Exception:
        pass
    return defaults


# ---------------------------------------------------------------------------
# Cleanup: delete individual compilation source files after successful upload
# ---------------------------------------------------------------------------

def cleanup_source_files(video_paths, compilation_video_path):
    """Delete individual video files that were used in the compilation.

    Only deletes if the compilation video exists and is valid.
    This frees disk space after a successful compilation upload.

    Args:
        video_paths: List of (date, path) tuples of source videos
        compilation_video_path: Path to compiled output video

    Returns:
        Number of files deleted
    """
    if not os.path.exists(compilation_video_path):
        print("[compilation] Compilation output missing — skipping cleanup")
        return 0

    deleted = 0
    for _date, vp in video_paths:
        if os.path.exists(vp):
            try:
                size_mb = os.path.getsize(vp) / (1024 * 1024)
                os.remove(vp)
                print(f"[compilation] Cleaned: {os.path.basename(vp)} "
                      f"({size_mb:.1f}MB)")
                deleted += 1
            except Exception as e:
                print(f"[compilation] Cleanup failed for {vp}: {e}",
                      file=sys.stderr)

    if deleted > 0:
        print(f"[compilation] Cleanup complete: {deleted} source files deleted")
    else:
        print(f"[compilation] No source files to clean up")

    return deleted


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_weekly_compilation(date_label, config=None, dry_run=False):
    """Build and upload the weekly compilation album.

    This is the main entry point called from nightly_music.py.

    Workflow:
        1. Check if today is Sunday (run_pipeline already verified)
        2. Get Mon-Sat dates for the current week
        3. Collect Hero videos from each day
        4. Generate thumbnail for compilation
        5. Concatenate videos via FFmpeg
        6. Upload to YouTube with chapter markers
        7. Clean up individual compilation source files

    Args:
        date_label: YYYY-MM-DD (should be a Sunday)
        config: Full pipeline config dict (optional)
        dry_run: If True, log intent without executing

    Returns:
        dict with keys: status, video_path, error
    """
    result = {
        "status": "skipped",
        "video_path": "",
        "error": None,
    }

    print(f"\n{'='*60}")
    print(f"[compilation] Weekly Compilation Album — {date_label}")
    print(f"[compilation] {'DRY RUN' if dry_run else 'PRODUCTION RUN'}")
    print(f"{'='*60}\n")

    # Verify it's a Sunday
    dt = datetime.datetime.strptime(date_label, "%Y-%m-%d")
    if dt.weekday() != 6:
        print(f"[compilation] {date_label} is not Sunday (weekday={dt.weekday()}) "
              f"— skipping compilation")
        result["error"] = "Not a Sunday"
        return result

    # Load config if not provided
    if config is None:
        config = _load_config_simple()

    # Check compilation is enabled
    comp_cfg = config.get("compilation", {})
    if not comp_cfg.get("enabled", True):
        print(f"[compilation] Compilation disabled in config — skipping")
        result["error"] = "Compilation disabled in config"
        return result

    max_duration_min = comp_cfg.get("max_duration_min", 45)

    # Step 1: Get week dates (Mon-Sat)
    week_dates = get_week_dates(date_label)
    week_label = get_chinese_week_label(date_label)
    print(f"[compilation] Week: {week_dates[0]} to {week_dates[-1]} "
          f"({week_label})")

    # Step 2: Collect Hero videos
    video_paths = collect_hero_videos(week_dates)

    if len(video_paths) < 2:
        print(f"[compilation] Only {len(video_paths)} video(s) found — "
              f"need at least 2 for a compilation. Skipping.",
              file=sys.stderr)
        result["error"] = "Need at least 2 videos for compilation"
        return result

    print(f"[compilation] Collected {len(video_paths)} videos for compilation\n")

    # Step 3: Estimate duration
    total_duration = 0
    for _date, vp in video_paths:
        total_duration += get_video_duration(vp)
    print(f"[compilation] Estimated total duration: "
          f"{total_duration:.0f}s ({total_duration/60:.1f} min)")

    max_duration_sec = max_duration_min * 60
    if total_duration > max_duration_sec:
        print(f"[compilation] WARNING: Estimated duration ({total_duration:.0f}s) "
              f"exceeds max_duration_min ({max_duration_min} min)",
              file=sys.stderr)

    # Step 4: Generate compilation thumbnail
    songs_dir = os.path.join(SONGS_BASE, date_label)
    os.makedirs(songs_dir, exist_ok=True)

    if dry_run:
        print(f"[compilation] [DRY RUN] Would generate compilation thumbnail")
        thumb_path = ""
    else:
        thumb_path = generate_compilation_thumbnail(songs_dir, week_label)

    # Step 5: Concatenate videos
    comp_filename = f"compilation-{week_dates[0]}-to-{week_dates[-1]}.mp4"
    comp_output_path = os.path.join(songs_dir, comp_filename)

    if dry_run:
        print(f"[compilation] [DRY RUN] Would concatenate {len(video_paths)} videos")
        print(f"[compilation] [DRY RUN]   Output: {comp_output_path}")
        # Create placeholder for subsequent steps
        with open(comp_output_path, "w") as f:
            f.write("DRY RUN COMPILATION PLACEHOLDER")
    else:
        print(f"[compilation] Concatenating videos (may take a while)...")
        success = build_concat_file(video_paths, comp_output_path)
        if not success:
            result["error"] = "FFmpeg concat failed"
            result["status"] = "failed"
            print(f"[compilation] FAILED — concat error", file=sys.stderr)
            return result

    # Step 6: Generate chapter markers
    chapters = get_chapter_timestamps(video_paths)
    chapter_desc = format_chapters_for_description(chapters)

    # Build description
    description = (
        f"🎵 ManggoMusicCH Weekly Compilation\n"
        f"{week_label}\n\n"
        f"This week's AI-generated Chinese pop songs.\n"
        f"Daily new songs — subscribe for your daily dose of AI music!\n\n"
        f"{chapter_desc}\n\n"
        f"---\n"
        f"All songs generated by AI (MiniMax music-2.6)\n"
        f"#WeeklyCompilation #AIMusic #华语流行 #AISong #人工智能音乐"
    )

    # Step 7: Upload to YouTube
    title = f"🎵 ManggoMusicCH Weekly \u2014 {week_label}"
    if dry_run:
        print(f"[compilation] [DRY RUN] Would upload compilation to YouTube")
        upload_result = {
            "video_id": "DRY-RUN-COMP",
            "youtube_url": "",
            "status": "ok",
        }
    else:
        upload_result = upload_compilation_to_youtube(
            video_path=comp_output_path,
            title=title,
            description=description,
            thumbnail_path=thumb_path,
            date_label=date_label,
            dry_run=False,
        )

    if upload_result.get("status") == "ok" or upload_result.get("video_id"):
        result["status"] = "ok"
        result["video_path"] = comp_output_path
        result["youtube_url"] = upload_result.get(
            "url", upload_result.get("youtube_url", "")
        )
        print(f"[compilation] Upload OK — video_id: "
              f"{upload_result.get('video_id', 'unknown')}")

        # Step 8: Clean up source files after successful upload
        if not dry_run:
            cleanup_source_files(video_paths, comp_output_path)
        else:
            print(f"[compilation] [DRY RUN] Would clean up {len(video_paths)} "
                  f"source files")
    else:
        result["status"] = "failed"
        result["error"] = upload_result.get("error", "Upload failed")
        print(f"[compilation] Upload FAILED: {result['error']}",
              file=sys.stderr)

    print(f"\n{'='*60}")
    print(f"[compilation] Complete — {result['status']}")
    print(f"{'='*60}\n")

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="ManggoMusicCH Weekly Compilation Album"
    )
    parser.add_argument("--date", type=str, required=True,
                        help="YYYY-MM-DD (should be a Sunday)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Test mode — no generation or upload")
    args = parser.parse_args()

    result = build_weekly_compilation(
        args.date, dry_run=args.dry_run
    )
    sys.exit(0 if result["status"] == "ok" else 1)


if __name__ == "__main__":
    main()
