#!/usr/bin/env python3
"""
nightly_music.py — Nightly AI Music Generation Pipeline

Generates N AI songs per night in a single run.
Features:
  - Reads config from D:/Hermes/config/nightly-music.yaml
  - Fetches trending Chinese songs from configurable source
  - Generates songs sequentially via MiniMax API
  - Creates per-day subfolders (YYYY-MM-DD/)
  - Batches Telegram delivery (5 songs per message)
  - Syncs to D-drive mirror

Usage:
    python3 nightly_music.py --date 2026-05-09
    python3 nightly_music.py --date 2026-05-09 --dry-run   (no generation, just test flow)
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPTS_DIR = os.path.expanduser("~/.hermes/scripts")
CONFIG_PATH = "/mnt/d/Hermes/config/nightly-music.yaml"
FETCH_SCRIPT = os.path.join(SCRIPTS_DIR, "fetch_trending.py")
DEDUP_SCRIPT = os.path.join(SCRIPTS_DIR, "check-duplicate.py")
SONGS_BASE   = os.path.expanduser("~/.hermes/songs/nightly-songs")
D_DRIVE_BASE = os.path.expanduser("/mnt/d/Hermes/songs/nightly-songs")


sys.path.insert(0, SCRIPTS_DIR)
sys.path.insert(0, "/home/dennis/.hermes/venv/lib/python3.12/site-packages")
from minimax_music_api import generate_and_save

# Optional imports — visualizer and YouTube uploader (graceful fallback)
try:
    from nightly_visualizer import generate_visualizer as _generate_visualizer
except ImportError:
    _generate_visualizer = None

try:
    from nightly_uploader import upload_video as _upload_video
except ImportError:
    _upload_video = None

# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------
def load_config():
    """Load YAML config. Returns dict with defaults if file missing."""
    defaults = {
        "song_count": 10,
        "language": "chinese-only",
        "trending_source": "qq-douyin",
        "max_lyrics_retries": 2,
        "telegram": {"songs_per_message": 5},
        "output_dir": SONGS_BASE,
        "d_drive_mirror": D_DRIVE_BASE,
        "youtube": {
            "enabled": False,
            "privacy": "private",
            "category": "10",
            "tags": ["AI Music", "MiniMax", "华语流行"],
        },
        "visualizer": {
            "enabled": True,
            "resolution": "1920x1080",
        },
    }
    try:
        import yaml
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            if cfg:
                # Merge with defaults
                for k, v in defaults.items():
                    if k not in cfg:
                        cfg[k] = v
                return cfg
    except Exception as e:
        print(f"[nightly] WARNING: Config load failed ({e}), using defaults",
              file=sys.stderr)
    return defaults


# ---------------------------------------------------------------------------
# Fetch trending songs
# ---------------------------------------------------------------------------
def fetch_trending(sources, count):
    """
    Fetch trending songs from one or more sources.
    sources can be a string (single source) or a list of strings.
    Aggregates results deduplicated by (song, artist) pair.
    Falls back to pool if all sources fail.
    """
    if isinstance(sources, str):
        sources = [sources]

    all_songs = []
    seen = set()

    for source in sources:
        cmd = [
            sys.executable, FETCH_SCRIPT,
            "--source", source,
            "--count", str(count * 2),  # Fetch extra for dedup
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                songs = json.loads(result.stdout)
                if songs:
                    # Dedup against already-collected songs
                    new_count = 0
                    for s in songs:
                        key = (s.get("song", ""), s.get("artist", ""))
                        if key not in seen:
                            seen.add(key)
                            all_songs.append(s)
                            new_count += 1
                    print(f"[nightly] Fetched {len(songs)} from '{source}' "
                          f"({new_count} new, {len(all_songs)} total)")
                else:
                    print(f"[nightly] '{source}' returned 0 songs", file=sys.stderr)
            else:
                print(f"[nightly] '{source}' failed (rc={result.returncode})",
                      file=sys.stderr)
        except Exception as e:
            print(f"[nightly] '{source}' exception: {e}", file=sys.stderr)

        # If we have enough, stop fetching more sources
        if len(all_songs) >= count:
            break

    if all_songs:
        print(f"[nightly] Total trending songs from all sources: {len(all_songs)}")
        return all_songs[:count]

    # Fallback to pool
    print("[nightly] All sources failed, falling back to pool...", file=sys.stderr)
    cmd_pool = [sys.executable, FETCH_SCRIPT, "--source", "pool", "--count", str(count)]
    try:
        result = subprocess.run(cmd_pool, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            songs = json.loads(result.stdout)
            for s in songs:
                s["source"] = "multi-source-fallback"
            return songs
    except Exception:
        pass
    return []


# ---------------------------------------------------------------------------
# Title extraction
# ---------------------------------------------------------------------------


def extract_title(music_name, lyrics, fallback_style, song_num):
    if music_name and music_name.strip():
        return music_name.strip()
    if lyrics:
        for line in lyrics.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("["):
                continue
            if re.fullmatch(r"[\W_]+", line):
                continue
            return line
    return f"AI Song #{song_num} — {fallback_style}"


# ---------------------------------------------------------------------------
# Filename sanitizer
# ---------------------------------------------------------------------------
def sanitize_filename(name):
    name = re.sub(r"[:/\\|]", "-", name)
    name = re.sub(r"['\"<>]", "", name)
    name = re.sub(r"\s+", " ", name)
    name = re.sub(r"-+", "-", name)
    return name.strip(".- ").lower()


# ---------------------------------------------------------------------------
# Song generation
# ---------------------------------------------------------------------------
def generate_song(prompt, song_num, songs_dir, date_label, max_lyrics_retries=2):
    """Generate a single song via MiniMax, save to daily folder."""
    tmp_mp3 = os.path.join(songs_dir, f"tmp-song-{song_num}.mp3")
    print(f"[nightly] Generating song {song_num}: {prompt[:60]}...")

    try:
        result = generate_and_save(
            prompt=prompt,
            lyrics="",
            output_path=tmp_mp3,
            is_instrumental=False,
            max_lyrics_retries=max_lyrics_retries,
        )
        print(f"[nightly] Song {song_num} OK — {result['duration_sec']}s, {result['size_mb']}MB")

        title = extract_title(
            result.get("song_title") or "",
            result.get("lyrics") or "",
            prompt[:30],
            song_num,
        )
        lyrics_text = result.get("lyrics", "")
        safe_title = sanitize_filename(title)

        mp3_path = os.path.join(songs_dir, f"{song_num:02d}-{safe_title}.mp3")
        txt_path = os.path.join(songs_dir, f"{song_num:02d}-{safe_title}.txt")

        if os.path.exists(tmp_mp3):
            os.rename(tmp_mp3, mp3_path)

        # Write lyrics file
        lyrics_content = (
            f"Title: {title}\n"
            f"Prompt: {prompt}\n"
            f"Generated by MiniMax music-2.6\n"
            f"\n--- LYRICS ---\n\n{lyrics_text}\n"
        )
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(lyrics_content)

        return {
            "status": "success",
            "title": title,
            "mp3_path": mp3_path,
            "txt_path": txt_path,
            "duration_sec": result["duration_sec"],
            "size_mb": result["size_mb"],
            "lyrics": lyrics_text,
            "error": None,
        }

    except Exception as e:
        print(f"[nightly] Song {song_num} FAILED: {e}", file=sys.stderr)
        # Clean up temp file
        if os.path.exists(tmp_mp3):
            os.remove(tmp_mp3)
        return {
            "status": "failed",
            "title": f"FAILED — {prompt[:40]}",
            "mp3_path": "",
            "txt_path": "",
            "duration_sec": 0,
            "size_mb": 0,
            "lyrics": "",
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def append_log(entries, date_label):
    """Append song entries to monthly song-log file. Idempotent per date."""
    month_key = date_label[:7]  # e.g. "2026-05"
    log_dir = os.path.expanduser("~/.hermes/work_logs/nightly-songs")
    log_path = os.path.join(log_dir, f"song-log-{month_key}.json")
    os.makedirs(log_dir, exist_ok=True)

    existing = []
    if os.path.exists(log_path):
        with open(log_path, encoding="utf-8") as f:
            try:
                existing = json.load(f)
            except json.JSONDecodeError:
                existing = []

    # Remove any existing entries for the same date (idempotent per date)
    before_count = len(existing)
    existing = [e for e in existing if e.get("date") != date_label]
    removed = before_count - len(existing)

    existing.extend(entries)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    if removed:
        print(f"[nightly] Log: replaced {removed} stale entries for {date_label}, logged {len(entries)} new")
    else:
        print(f"[nightly] Logged {len(entries)} entries")


# ---------------------------------------------------------------------------
# D-drive sync
# ---------------------------------------------------------------------------
def sync_to_d_drive(src_dir, d_drive_dir):
    """Copy entire daily folder to D-drive mirror."""
    try:
        os.makedirs(d_drive_dir, exist_ok=True)
        for fname in os.listdir(src_dir):
            src = os.path.join(src_dir, fname)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(d_drive_dir, fname))
        print(f"[nightly] D-drive sync: {src_dir} → {d_drive_dir}")
        return True
    except Exception as e:
        print(f"[nightly] D-drive sync failed: {e}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Telegram bot
# ---------------------------------------------------------------------------
def _load_telegram_config():
    env_path = os.path.expanduser("~/.hermes/.env")
    bot_token = None
    chat_id = "1188842054"
    with open(env_path) as f:
        for line in f:
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                bot_token = line.strip().split("=", 1)[1].strip('"').strip("'")
            if line.startswith("TELEGRAM_ALLOWED_USERS="):
                val = line.strip().split("=", 1)[1].strip()
                first = val.split(",")[0].strip()
                if first:
                    chat_id = first
    if not bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not found in ~/.hermes/.env")
    return bot_token, chat_id


_CACHED_TELEGRAM = None

def _ensure_telegram():
    """Lazy-load Telegram config on first use. Returns (bot_token, chat_id, api_url)."""
    global _CACHED_TELEGRAM
    if _CACHED_TELEGRAM is None:
        bot_token, chat_id = _load_telegram_config()
        _CACHED_TELEGRAM = (bot_token, chat_id, f"https://api.telegram.org/bot{bot_token}")
    return _CACHED_TELEGRAM


def send_telegram_batch(songs_batch, batch_num, total_batches, date_label):
    """
    Send a batch of songs in one Telegram message.
    Uses sendMediaGroup for multi-file, sendDocument for single file.
    First media item carries the caption.
    """
    import requests

    _, CHAT_ID, TELEGRAM_API = _ensure_telegram()

    if not songs_batch:
        return

    start_num = songs_batch[0]["song_number"]
    end_num = songs_batch[-1]["song_number"]

    # Build song summary table for caption
    lines = [f"🌙 AI Music — {date_label}"]
    if total_batches > 1:
        lines.append(f"📦 Batch {batch_num}/{total_batches} (Songs {start_num}-{end_num})")
    lines.append("")

    for s in songs_batch:
        status_icon = "✅" if s["status"] == "success" else "❌"
        title_display = s.get("title", "Unknown")
        duration = s.get("duration_sec", 0)
        duration_str = f"{int(duration//60)}:{int(duration%60):02d}" if duration else "--:--"
        prompt_short = s.get("prompt", "")[:40]
        lines.append(f"{status_icon} Song #{s['song_number']}: {title_display}")
        lines.append(f"   {duration_str} · {prompt_short}")
        if s["status"] == "failed":
            lines.append(f"   ⚠️ Failed: {s.get('error', 'unknown')}")
        if s.get("youtube_url"):
            lines.append(f"   🔗 {s['youtube_url']}")

    caption = "\n".join(lines)

    # Collect file paths (open lazily)
    file_items = []
    for s in songs_batch:
        if s["status"] == "success" and os.path.exists(s["mp3_path"]):
            file_items.append((s["mp3_path"], os.path.basename(s["mp3_path"]), "audio/mpeg"))
        if s["status"] == "success" and os.path.exists(s["txt_path"]):
            file_items.append((s["txt_path"], os.path.basename(s["txt_path"]), "text/plain"))

    if not file_items:
        try:
            resp = requests.post(
                f"{TELEGRAM_API}/sendMessage",
                data={"chat_id": CHAT_ID, "text": caption},
                timeout=30,
            )
            resp.raise_for_status()
            print(f"[nightly] Batch {batch_num}: caption-only message sent")
        except Exception as e:
            print(f"[nightly] Batch {batch_num} caption send FAILED: {e}", file=sys.stderr)
        return

    # Single file: use sendDocument (simpler)
    if len(file_items) == 1:
        fpath, fname, fmime = file_items[0]
        try:
            with open(fpath, "rb") as fh:
                resp = requests.post(
                    f"{TELEGRAM_API}/sendDocument",
                    data={"chat_id": CHAT_ID, "caption": caption},
                    files={"document": (fname, fh, fmime)},
                    timeout=120,
                )
            resp.raise_for_status()
            print(f"[nightly] Batch {batch_num} sent to Telegram (1 file: {fname})")
        except Exception as e:
            print(f"[nightly] Batch {batch_num} sendDocument FAILED: {e}", file=sys.stderr)
        return

    # Multi-file: use sendMediaGroup
    media_array = []
    for idx, (fpath, fname, _fmime) in enumerate(file_items):
        entry = {"type": "document", "media": f"attach://file{idx}"}
        if idx == 0:
            entry["caption"] = caption
        media_array.append(entry)

    # Build multipart form data
    form_data = {
        "chat_id": CHAT_ID,
        "media": json.dumps(media_array),
    }
    files_payload = {}
    opened_files = []
    try:
        for idx, (fpath, fname, fmime) in enumerate(file_items):
            fh = open(fpath, "rb")
            opened_files.append(fh)
            files_payload[f"file{idx}"] = (fname, fh, fmime)

        resp = requests.post(
            f"{TELEGRAM_API}/sendMediaGroup",
            data=form_data,
            files=files_payload,
            timeout=120,
        )
        resp.raise_for_status()
        print(f"[nightly] Batch {batch_num} sent to Telegram ({len(file_items)} files via media group)")
    except Exception as e:
        print(f"[nightly] Batch {batch_num} sendMediaGroup FAILED: {e}", file=sys.stderr)
    finally:
        for fh in opened_files:
            fh.close()


# ---------------------------------------------------------------------------
# Visualizer wrapper (graceful fallback if module missing)
# ---------------------------------------------------------------------------
def generate_visualizer_mp4(mp3_path, output_path, title, duration_sec=None):
    """
    Generate visualizer MP4 from MP3. Gracefully handles missing module.
    Returns dict with keys: path, duration, status, error.
    """
    if _generate_visualizer is None:
        print("[nightly] Visualizer module not available — skipping", file=sys.stderr)
        return {"path": "", "duration": 0, "status": "skipped", "error": "Module not loaded"}
    try:
        return _generate_visualizer(
            mp3_path=mp3_path,
            output_path=output_path,
            title=title,
            background_image=None,
            duration_sec=duration_sec,
        )
    except Exception as e:
        print(f"[nightly] Visualizer exception: {e}", file=sys.stderr)
        return {"path": "", "duration": 0, "status": "failed", "error": str(e)}


# ---------------------------------------------------------------------------
# YouTube uploader wrapper (graceful fallback if module missing)
# ---------------------------------------------------------------------------
def upload_to_youtube(video_path, title, prompt, date_label):
    """
    Upload video to YouTube with defaults. Gracefully handles missing deps.
    Returns dict with keys: video_id, youtube_url, status, error.
    """
    if _upload_video is None:
        print("[nightly] YouTube uploader module not available — skipping", file=sys.stderr)
        return {"video_id": "", "youtube_url": "", "status": "skipped", "error": "Module not loaded"}

    config = load_config()
    yt_cfg = config.get("youtube", {})

    if not yt_cfg.get("enabled", False):
        print("[nightly] YouTube upload disabled in config — skipping")
        return {"video_id": "", "youtube_url": "", "status": "disabled", "error": None}

    description = (
        f"AI-generated music inspired by: {prompt}\n\n"
        f"Generated on {date_label} using MiniMax music-2.6\n"
        f"#AIMusic #MiniMax #华语流行"
    )
    tags = yt_cfg.get("tags", ["AI Music", "MiniMax", "华语流行"])
    privacy = yt_cfg.get("privacy", "private")
    category = yt_cfg.get("category", "10")

    # Compute publish_at: 6pm SGT on the target date
    publish_at = None
    try:
        from datetime import datetime, timezone, timedelta
        sgt = timezone(timedelta(hours=8))
        publish_dt = datetime.strptime(date_label, "%Y-%m-%d").replace(
            hour=18, minute=0, second=0, tzinfo=sgt
        )
        publish_at = publish_dt.isoformat()
    except Exception:
        pass

    try:
        return _upload_video(
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
            category_id=category,
            privacy=privacy,
            thumbnail_path=None,
            publish_at=publish_at,
        )
    except Exception as e:
        print(f"[nightly] YouTube upload exception: {e}", file=sys.stderr)
        return {"video_id": "", "youtube_url": "", "status": "failed", "error": str(e)}


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def run_pipeline(date_str, dry_run=False):
    """Full pipeline: fetch → generate (×N) → sync → log → Telegram."""
    date_label = date_str
    print(f"\n{'='*60}")
    print(f"[nightly] Starting — {date_label}")
    print(f"[nightly] {'DRY RUN' if dry_run else 'PRODUCTION RUN'}")
    print(f"{'='*60}\n")

    # Step 0: Load config
    config = load_config()
    song_count = config.get("song_count", 10)
    raw_source = config.get("trending_source", "qq-douyin")
    # Normalize to list — single string or list both work
    if isinstance(raw_source, str):
        sources = [raw_source]
    elif isinstance(raw_source, list):
        sources = raw_source
    else:
        sources = ["qq-douyin"]
    songs_per_msg = config.get("telegram", {}).get("songs_per_message", 5)
    output_dir = os.path.expanduser(config.get("output_dir", SONGS_BASE))
    d_drive_dir = os.path.expanduser(config.get("d_drive_mirror", D_DRIVE_BASE))
    config_lang = config.get("language", "Chinese")

    # Validate sources against known list
    KNOWN_SOURCES = {"qq-douyin", "kkbox", "my-fm", "pool"}
    for src in sources:
        if src not in KNOWN_SOURCES:
            print(f"[nightly] WARNING: Unknown trending source '{src}' — will use generic search", file=sys.stderr)

    print(f"[nightly] Config: {song_count} songs, source={sources}, batch={songs_per_msg}/msg")

    # Step 1: Create daily folder
    songs_dir = os.path.join(output_dir, date_label)
    os.makedirs(songs_dir, exist_ok=True)
    d_drive_target = os.path.join(d_drive_dir, date_label)
    print(f"[nightly] Daily folder: {songs_dir}")

    # Step 2: Fetch trending songs
    trending = fetch_trending(sources, song_count)
    if not trending:
        print("[nightly] ERROR: No trending songs available, using pool", file=sys.stderr)
        trending = fetch_trending(["pool"], song_count)

    if not trending:
        print("[nightly] FATAL: No songs to generate. Aborting.", file=sys.stderr)
        return False

    print(f"[nightly] Using {len(trending)} trending songs as inspiration\n")

    # Step 2.5: Dedup against last 7 days
    try:
        dedup_result = subprocess.run(
            [sys.executable, DEDUP_SCRIPT, "--days", "7"],
            capture_output=True, text=True, timeout=10,
        )
        if dedup_result.returncode == 0:
            blocked = json.loads(dedup_result.stdout)
            blocked_keys = {(b["style_reference"], b["language"]) for b in blocked}
            if blocked_keys:
                filtered = []
                removed = []
                for t in trending:
                    style_key = f"{t.get('artist', '')} - {t.get('song', '')}"
                    lang = config_lang
                    if (style_key, lang) in blocked_keys:
                        removed.append(style_key)
                    else:
                        filtered.append(t)
                if removed:
                    print(f"[nightly] Dedup: removed {len(removed)} recently used: {', '.join(removed[:5])}")
                    trending = filtered
    except Exception as e:
        print(f"[nightly] Dedup check failed (non-fatal): {e}", file=sys.stderr)

    # If dedup filtered out too many songs, supplement from pool
    if len(trending) < song_count:
        needed = song_count - len(trending)
        print(f"[nightly] Dedup left {len(trending)} songs, supplementing {needed} from pool")
        pool_result = subprocess.run(
            [sys.executable, FETCH_SCRIPT, "--source", "pool", "--count", str(needed * 2)],
            capture_output=True, text=True, timeout=15,
        )
        if pool_result.returncode == 0:
            pool_songs = json.loads(pool_result.stdout)
            for ps in pool_songs:
                style_key = f"{ps.get('artist', '')} - {ps.get('song', '')}"
                if (style_key, config_lang) not in blocked_keys:
                    trending.append(ps)
                    if len(trending) >= song_count:
                        break
        print(f"[nightly] After pool fill: {len(trending)} trending songs")

    # Step 3: Generate songs
    song_results = []
    for i, trend in enumerate(trending[:song_count]):
        song_num = i + 1
        prompt = trend.get("style_prompt", "")
        artist = trend.get("artist", "")
        song_ref = trend.get("song", "")

        if not prompt:
            prompt = f"类似{artist}的《{song_ref}》风格，华语流行抒情，钢琴为主，温暖声线"

        print(f"[nightly] --- Song {song_num}/{song_count}: Inspired by {artist} - {song_ref} ---")

        if dry_run:
            # Simulate generation in dry-run mode
            dry_title = f"[DRY RUN] {artist} - {song_ref}"
            dry_safe = sanitize_filename(dry_title)
            result = {
                "status": "success",
                "title": dry_title,
                "mp3_path": os.path.join(songs_dir, f"{song_num:02d}-{dry_safe}.mp3"),
                "txt_path": os.path.join(songs_dir, f"{song_num:02d}-{dry_safe}.txt"),
                "duration_sec": random.randint(120, 200),
                "size_mb": round(random.uniform(3.5, 6.5), 2),
                "lyrics": f"[DRY RUN] Lyrics for {artist} - {song_ref}\n\n[Verse]\nDry run mode\n\n[Chorus]\nNo actual generation",
                "error": None,
                "prompt": prompt,
                "song_number": song_num,
                "trending_song": song_ref,
                "trending_artist": artist,
            }
            # Create placeholder files
            with open(result["mp3_path"], "w") as f:
                f.write(f"DRY RUN MP3 PLACEHOLDER - {artist} - {song_ref}")
            with open(result["txt_path"], "w", encoding="utf-8") as f:
                f.write(result["lyrics"])
        else:
            # Real generation
            gen_result = generate_song(prompt, song_num, songs_dir, date_label,
                                       max_lyrics_retries=config.get("max_lyrics_retries", 2))
            gen_result["prompt"] = prompt
            gen_result["song_number"] = song_num
            gen_result["trending_song"] = song_ref
            gen_result["trending_artist"] = artist

            # Small delay between songs to avoid rate limiting
            if i < song_count - 1:
                time.sleep(2)

            result = gen_result

        song_results.append(result)

        # Update progress
        successes = sum(1 for r in song_results if r["status"] == "success")
        print(f"[nightly] Progress: {successes}/{len(song_results)} successful\n")

    # Step 4: Generate visualizers
    visualizer_enabled = config.get("visualizer", {}).get("enabled", True)
    visualizer_results = []
    if visualizer_enabled:
        for song in song_results:
            if song["status"] == "success":
                title = song["title"]
                safe_viz = sanitize_filename(title)
                mp4_path = os.path.join(songs_dir, f"{song['song_number']:02d}-{safe_viz}-viz.mp4")

                if dry_run:
                    viz_result = {
                        "path": mp4_path,
                        "duration": song.get("duration_sec", 0),
                        "status": "ok",
                        "error": None,
                    }
                    print(f"[nightly] [DRY RUN] Would generate visualizer: {os.path.basename(mp4_path)}")
                else:
                    viz_result = generate_visualizer_mp4(
                        mp3_path=song["mp3_path"],
                        output_path=mp4_path,
                        title=title,
                        duration_sec=song.get("duration_sec"),
                    )

                song["mp4_path"] = viz_result.get("path", "")
                song["visualizer_status"] = viz_result.get("status", "failed")
                visualizer_results.append(viz_result)
            else:
                song["mp4_path"] = ""
                song["visualizer_status"] = "skipped"
    else:
        print("[nightly] Visualizer disabled in config — skipping")
        for song in song_results:
            song["mp4_path"] = ""
            song["visualizer_status"] = "disabled"

    # Step 5: Upload to YouTube
    youtube_cfg = config.get("youtube", {})
    youtube_enabled = youtube_cfg.get("enabled", False)
    youtube_results = []
    if youtube_enabled:
        for song in song_results:
            if song["status"] == "success" and song.get("visualizer_status") == "ok":
                if dry_run:
                    upload_result = {
                        "video_id": f"DRY-RUN-{song['song_number']:02d}",
                        "youtube_url": f"https://youtube.com/watch?v=DRY-RUN-{song['song_number']:02d}",
                        "status": "ok",
                        "error": None,
                    }
                    print(f"[nightly] [DRY RUN] Would upload: {song['title'][:50]}")
                else:
                    upload_result = upload_to_youtube(
                        video_path=song["mp4_path"],
                        title=song["title"],
                        prompt=song.get("prompt", ""),
                        date_label=date_label,
                    )
                song["youtube_video_id"] = upload_result.get("video_id", "")
                song["youtube_url"] = upload_result.get("url", upload_result.get("youtube_url", ""))
                song["youtube_status"] = upload_result.get("status", "failed")
                youtube_results.append(upload_result)
            else:
                song["youtube_video_id"] = ""
                song["youtube_url"] = ""
                song["youtube_status"] = song.get("visualizer_status", "skipped")
    else:
        print("[nightly] YouTube upload disabled in config — skipping")
        for song in song_results:
            song["youtube_video_id"] = ""
            song["youtube_url"] = ""
            song["youtube_status"] = "disabled"

    # Step 6: Sync to D-drive
    if not dry_run:
        sync_to_d_drive(songs_dir, d_drive_target)
    else:
        print(f"[nightly] [DRY RUN] Would sync: {songs_dir} → {d_drive_target}")

    # Step 7: Log
    log_entries = []
    for r in song_results:
        log_entries.append({
            "date": date_label,
            "song_number": r["song_number"],
            "language": config_lang,
            "style_source": "|".join(sources) if isinstance(sources, list) else sources,
            "style_reference": f"{r.get('trending_artist', '')} - {r.get('trending_song', '')}",
            "prompt_used": r.get("prompt", ""),
            "title": r.get("title", ""),
            "lyrics": r.get("lyrics", ""),
            "output_file": r.get("mp3_path", ""),
            "lyrics_file": r.get("txt_path", ""),
            "daily_folder": date_label,
            "duration_sec": r.get("duration_sec", 0),
            "size_mb": r.get("size_mb", 0),
            "mp4_path": r.get("mp4_path", ""),
            "visualizer_status": r.get("visualizer_status", ""),
            "youtube_video_id": r.get("youtube_video_id", ""),
            "youtube_url": r.get("youtube_url", ""),
            "youtube_status": r.get("youtube_status", ""),
            "d_drive_synced": not dry_run,
            "telegram_sent": False,
            "status": r["status"],
            "error": r.get("error"),
        })

    if not dry_run:
        append_log(log_entries, date_label)
    else:
        print(f"[nightly] [DRY RUN] Would log {len(log_entries)} entries")

    # Step 8: Telegram delivery
    successful_songs = [r for r in song_results if r["status"] == "success"]
    failed_songs = [r for r in song_results if r["status"] == "failed"]

    if not dry_run:
        # Always deliver successful songs (if any exist)
        if successful_songs:
            batches = []
            current_batch = []
            for r in successful_songs:
                current_batch.append(r)
                if len(current_batch) >= songs_per_msg:
                    batches.append(current_batch)
                    current_batch = []
            if current_batch:
                batches.append(current_batch)

            total_batches = len(batches)
            for idx, batch in enumerate(batches):
                send_telegram_batch(batch, idx + 1, total_batches, date_label)
                if idx < total_batches - 1:
                    time.sleep(3)  # Rate limit between batches

        # Additionally, send alert if high failure rate (supplemental, not replacement)
        if len(failed_songs) >= len(song_results) // 2:
            failure_msg = (
                f"⚠️ Nightly AI Music — {date_label}\n"
                f"High failure rate: {len(successful_songs)}/{len(song_results)} successful\n"
                f"Check logs for details."
            )
            import requests
            _, CHAT_ID, TELEGRAM_API = _ensure_telegram()
            try:
                resp = requests.post(
                    f"{TELEGRAM_API}/sendMessage",
                    data={"chat_id": CHAT_ID, "text": failure_msg},
                    timeout=30,
                )
                resp.raise_for_status()
                print(f"[nightly] Alert sent: high failure rate")
            except Exception as e:
                print(f"[nightly] High-failure alert FAILED: {e}", file=sys.stderr)

        # Always report individual failures
        if failed_songs:
            fail_summary = "\n".join(
                f"❌ Song #{r['song_number']}: {r.get('error', 'unknown')}"
                for r in failed_songs
            )
            fail_msg = (
                f"⚠️ Nightly AI Music — {date_label}\n"
                f"{len(failed_songs)} song(s) failed to generate:\n{fail_summary}"
            )
            import requests
            _, CHAT_ID, TELEGRAM_API = _ensure_telegram()
            try:
                resp = requests.post(
                    f"{TELEGRAM_API}/sendMessage",
                    data={"chat_id": CHAT_ID, "text": fail_msg},
                    timeout=30,
                )
                resp.raise_for_status()
            except Exception as e:
                print(f"[nightly] Failed summary send FAILED: {e}", file=sys.stderr)
    else:
        print(f"[nightly] [DRY RUN] Would send {len(successful_songs)} songs in batches of {songs_per_msg}")

    # Summary
    success_count = sum(1 for r in song_results if r["status"] == "success")
    fail_count = sum(1 for r in song_results if r["status"] == "failed")
    print(f"\n{'='*60}")
    print(f"[nightly] Complete — {date_label}")
    print(f"[nightly] {success_count} successful, {fail_count} failed of {len(song_results)}")
    print(f"[nightly] Output: {songs_dir}")
    print(f"{'='*60}\n")

    return fail_count == 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nightly AI Music — multi-song pipeline")
    parser.add_argument("--date", type=str, required=True, help="YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="Test mode — no API calls")
    # Keep backward compat for --song-number
    parser.add_argument("--song-number", type=int, help="Deprecated: use --date only")
    args = parser.parse_args()

    if args.song_number:
        print("[nightly] --song-number is deprecated. Use --date only (generates all songs).")
        print("[nightly] Falling back to old single-song mode...")
        # Import and run old single-song function
        from nightly_music_old import run_song
        ok = run_song(args.song_number, args.date)
        sys.exit(0 if ok else 1)

    ok = run_pipeline(args.date, dry_run=args.dry_run)
    sys.exit(0 if ok else 1)
