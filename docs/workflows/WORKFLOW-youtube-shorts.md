# WORKFLOW: YouTube Shorts Generation — Sub-pipeline for ManggoMusicCH
**Version**: 0.1
**Date**: 2026-05-12
**Author**: Workflow Architect
**Status**: Draft
**Implements**: Phase 2 — YouTube Shorts (from DESIGN.md and EXECUTION_PLAN.md)

---

## Overview

For each nightly pipeline run (2 songs/night), select the **best candidate song** and produce a vertical 1080×1920 YouTube Short (≤60s). The Short captures the chorus segment (loudest 45s), generates a Pollinations.ai vertical background, renders waveform + title + lyrics karaoke, and uploads to YouTube scheduled for **12pm SGT** — a separate slot from the full videos (6pm SGT). Non-fatal failures skip the Short but never abort the main pipeline.

---

## Actors

| Actor | Role in this workflow |
|---|---|
| Main Pipeline (`nightly_music.py`) | Triggers Short sub-pipeline after song generation; supplies `song_results` |
| Shorts Orchestrator (`nightly_shorts.py`) | NEW module — selects song, orchestrates chorus detection → render → upload |
| FFprobe | Analyzes audio to detect loudest segment for chorus slicing |
| FFmpeg | Extracts audio clip; renders vertical video with overlay filters |
| Pollinations.ai (`image_gen.py`) | Generates vertical background image (1080×1920) |
| YouTube Data API v3 (`nightly_uploader.py`) | Uploads vertical video as Short with scheduling |
| Telegram | Includes Short link in nightly notification |
| Filesystem (output dir) | Stores intermediate artifacts (clip, background, render) |

---

## Prerequisites

- [ ] All song files exist in `output/{date_label}/` (`*.mp3`, `*.txt` with lyrics)
- [ ] FFprobe + FFmpeg 6.1.1+ installed and on PATH
- [ ] CJK font installed (same `_find_cjk_font()` used by visualizer)
- [ ] Pollinations.ai reachable (network access)
- [ ] YouTube OAuth token valid and auto-refresh working
- [ ] Main pipeline config `youtube.enabled: true`
- [ ] Shorts config section added to `nightly-music.yaml` (new key: `shorts`)
- [ ] Main pipeline has NOT yet aborted (Short failures are non-fatal)

---

## Trigger

**Hook point**: Inside `run_pipeline()`, **after** song generation loop completes (`song_results` populated), **before** or **after** visualizer generation.

Placed **after** song generation but can run **in parallel** with the visualizer loop — the Short only needs `mp3_path`, `title`, `lyrics`, `duration_sec` from each `song_result`. It does NOT depend on the 1920×1080 visualizer MP4.

```python
# In nightly_music.py, run_pipeline(), after line ~708 (song_results complete):

# === SHORTS SUB-PIPELINE ===
short_result = None
if config.get("shorts", {}).get("enabled", False) and song_results:
    try:
        from nightly_shorts import generate_short
        short_result = generate_short(
            song_results=song_results,
            date_label=date_label,
            songs_dir=songs_dir,
        )
    except Exception as e:
        print(f"[nightly] Shorts sub-pipeline failed (non-fatal): {e}", file=sys.stderr)
        short_result = {"status": "pipeline_error", "error": str(e)}
```

---

## Workflow Tree

```
                        ┌──────────────────────────────────────────┐
                        │     MAIN PIPELINE (nightly_music.py)     │
                        │  2am SGT CRON → Load → Fetch → Dedup    │
                        │        → MiniMax Gen (×2 songs)          │
                        └────────────────┬─────────────────────────┘
                                         │ song_results[0..1]
                                         ▼
                    ┌────────────────────────────────────────────┐
                    │       SHORTS SUB-PIPELINE HOOK POINT       │
                    │  (new module: nightly_shorts.py)           │
                    │  Non-fatal: any failure → log + skip       │
                    └────────────────┬───────────────────────────┘
                                     │
                                     ▼
               ┌─────────────────────────────────────────┐
               │  STEP 0: SELECT SONG FOR SHORTS         │
               │  Pick 1 song from song_results           │
               └────────────────┬────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
                    ▼                       ▼
            ┌─────────────────┐    ┌──────────────────┐
            │ SONG FOUND      │    │ NO SUITABLE SONG │
            │ (go to Step 1)  │    │ (all failed/      │
            └────────┬────────┘    │  too short)       │
                     │             └────────┬─────────┘
                     ▼                      │
           ┌──────────────────────┐         │
           │ STEP 1: CHORUS       │         │
           │ DETECTION            │         │
           │ ffprobe → loudest    │         │
           │ 45s segment          │         │
           └────────┬─────────────┘         │
                    │                       │
          ┌─────────┴──────────┐            │
          ▼                    ▼            │
   ┌──────────────┐    ┌──────────────┐     │
   │ SEGMENT      │    │ NO SEGMENT   │     │
   │ FOUND        │    │ (song too    │     │
   └──────┬───────┘    │  short /     │     │
          │            │  silent)     │     │
          ▼            └──────┬───────┘     │
   ┌────────────────┐        │              │
   │ STEP 2: AUDIO  │        │              │
   │ EXTRACTION     │        │              │
   │ ffmpeg -ss     │        │              │
   │ -t 45 chorus   │        │              │
   └───────┬────────┘        │              │
           │                 │              │
    ┌──────┴──────┐          │              │
    ▼             ▼          │              │
 ┌────────┐ ┌──────────┐     │              │
 │ CLIP   │ │ EXTRACT  │     │              │
 │ READY  │ │ FAILED   │     │              │
 └───┬────┘ └────┬─────┘     │              │
     │           │           │              │
     ▼           ▼           ▼              ▼
 ┌─────────────────────────────────────────────────────┐
 │  STEP 3: BACKGROUND GENERATION (Pollinations.ai)    │
 │  1080×1920 vertical, based on song title/theme      │
 └──────────────────────┬──────────────────────────────┘
                        │
              ┌─────────┴──────────┐
              ▼                    ▼
     ┌────────────────┐   ┌──────────────────┐
     │ IMAGE READY    │   │ POLLINATIONS     │
     │ (or fallback)  │   │ TIMEOUT / FAILED │
     └───────┬────────┘   └───────┬──────────┘
             │                    │
             ▼                    ▼
     ┌──────────────────────────────────────┐
     │  USE FALLBACK BACKGROUND             │
     │  (solid gradient #0a0f1e → #1a0a2e)  │
     │  OR cached asset from assets/         │
     └────────────────┬─────────────────────┘
                      │
                      ▼
     ┌──────────────────────────────────────┐
     │  STEP 4: VERTICAL RENDER             │
     │  FFmpeg: 1080×1920, waveform +       │
     │  title overlay + lyrics karaoke      │
     └────────────────┬─────────────────────┘
                      │
              ┌───────┴────────┐
              ▼                ▼
     ┌────────────────┐ ┌──────────────────┐
     │ RENDER OK      │ │ RENDER FAILED    │
     │ MP4 ready for  │ │ (retry once,     │
     │ upload         │ │  then SKIP)      │
     └───────┬────────┘ └──────┬───────────┘
             │                 │
             ▼                 ▼
     ┌──────────────────────────────────────┐
     │  STEP 5: UPLOAD TO YOUTUBE           │
     │  Scheduled: 12pm SGT                │
     │  Tags include #Shorts                │
     └────────────────┬─────────────────────┘
                      │
              ┌───────┴────────┐
              ▼                ▼
     ┌────────────────┐ ┌──────────────────┐
     │ UPLOAD OK      │ │ UPLOAD FAILED    │
     │ Return: URL,   │ │ (retry x2 with   │
     │ video_id       │ │  backoff, then   │
     └───────┬────────┘ │  SKIP_SHORT)     │
             │          └──────┬───────────┘
             ▼                 │
     ┌────────────────┐        │
     │ STEP 6:        │        │
     │ INJECT INTO    │        │
     │ TELEGRAM MSG   │        │
     └───────┬────────┘        │
             │                 │
             ▼                 ▼
     ┌──────────────────────────────────────────┐
     │  SUB-PIPELINE COMPLETE                    │
     │  short_result dict merged into main       │
     │  song_results + telegram caption          │
     └──────────────────────────────────────────┘
```

---

## STEP 0: Select Song for Shorts

**Actor**: Shorts Orchestrator (new module)
**Action**: From `song_results` (list of 2 song dicts), select the best 1 candidate for Shorts treatment.

**Selection priority** (first match wins):
1. First song with `status == "success"` and `duration_sec >= 45` → pick this one
2. If both qualify → pick first (song_results[0])
3. If none qualify → SKIP_SHORT

**Timeout**: 0.1s (pure logic)
**Input**: `song_results: list[dict]` (from main pipeline)
**Output on SUCCESS**: `{"selected_song": dict, "status": "selected"}` → GO TO STEP 1
**Output on FAILURE**:
  - `FAILURE(no_suitable_song)`: No song has `duration_sec >= 45` → `SKIP_SHORT`
  - `FAILURE(all_failed)`: All songs have `status == "failed"` → `SKIP_SHORT`

**Observable states**:
  - Customer sees: nothing (Shorts generation is invisible to customer until upload)
  - Operator sees: log line `[nightly:shorts] Selected song N: "{title}" ({duration_sec}s)`
  - Database: N/A (shorts state tracked in log only)
  - Logs: `[nightly:shorts] Selected song 1 for Short: 雨后初霁 (154.8s)`

---

## STEP 1: Chorus Detection (Loudest 45s Segment)

**Actor**: FFprobe (called via subprocess)
**Action**: Analyze the full song audio to find the loudest 45-second contiguous segment. Uses FFmpeg's `silencedetect` or `volumedetect` filters, or Python `audiowaveform` approach.

**Approach A (recommended — pure FFmpeg)**:
```bash
ffprobe -v error -show_entries stream=codec_type,duration -of json input.mp3
# Then use astats filter to measure RMS per window
ffmpeg -i input.mp3 -af "astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-" -f null - 2>&1
```
Parse RMS levels in 1-second windows → slide a 45s window → pick the window with max mean RMS.

**Approach B (if lyrics exist)**: Detect chorus by finding the most-repeated lyric section in the lyrics file. Use the `[Chorus]` tag markers. Fall back to RMS if no tags found.

**Fallback**: If all analysis fails, use middle 45s of the song: `start = max(0, (duration - 45) / 2)`

**Timeout**: 15s for ffprobe analysis
**Input**: `selected_song["mp3_path"]`, `selected_song["duration_sec"]`, `selected_song["lyrics"]`
**Output on SUCCESS**: `{"chorus_start": float, "chorus_end": float, "duration": 45.0, "method": "rms_peak"|"lyrics_chorus_tag"|"middle_fallback"}` → GO TO STEP 2
**Output on FAILURE**:
  - `FAILURE(too_short)`: `duration_sec < 45` → `SKIP_SHORT`
  - `FAILURE(ffprobe_error)`: ffprobe not found or returns error → fallback to middle 45s with warning
  - `FAILURE(silent_audio)`: RMS near-zero throughout (silent file) → `SKIP_SHORT`
  - `FAILURE(timeout)`: ffprobe hangs > 15s → fallback to middle 45s

**Observable states**:
  - Customer sees: nothing
  - Operator sees: log line `[nightly:shorts] Chorus detected: 54.2s–99.2s (RMS method)` or `[nightly:shorts] Chorus detection failed — using middle segment fallback`
  - Database: N/A
  - Logs: `[nightly:shorts] Chorus start=54.2, end=99.2, method=rms_peak`

---

## STEP 2: Audio Clip Extraction

**Actor**: FFmpeg
**Action**: Extract the identified chorus segment as a standalone 45-second MP3 clip.

```bash
ffmpeg -y -i "{song.mp3}" -ss {chorus_start} -t 45 -c:a libmp3lame -b:a 192k "{output_dir}/chorus-{song_num}.mp3"
```

**Timeout**: 10s
**Input**: `selected_song["mp3_path"]`, `chorus_start`, `chorus_end`, `songs_dir`, `song_number`
**Output on SUCCESS**: `{"clip_path": "output/2026-05-12/chorus-01.mp3", "clip_duration": 45.0}` → GO TO STEP 3
**Output on FAILURE**:
  - `FAILURE(ffmpeg_error)`: FFmpeg exits non-zero → `SKIP_SHORT`
  - `FAILURE(timeout)`: FFmpeg hangs > 10s → `SKIP_SHORT`
  - `FAILURE(output_missing)`: Output file not created → retry once with `-ss` after `-i` (seek mode) → if still fails → `SKIP_SHORT`

**NOTE**: If the actual chorus duration is less than 45s (e.g., song chorus is 32s long), the clip will contain extra audio beyond the chorus (up to 45s total). This is acceptable — YouTube Shorts support up to 60s and the extra context improves the viewing experience.

**Observable states**:
  - Customer sees: nothing
  - Operator sees: log line `[nightly:shorts] Chorus clip extracted: chorus-01.mp3 (45.0s)`
  - Database: N/A
  - Logs: `[nightly:shorts] Clip extracted: /path/to/chorus-01.mp3, 1.2MB`

---

## STEP 3: Background Generation (Pollinations.ai — 1080×1920)

**Actor**: `image_gen.py` (existing module — extend with vertical preset)
**Action**: Generate a vertical background image suitable for Shorts. Use the song title to create a themed prompt.

**Prompt construction**:
```python
prompt = (
    f"vertical portrait background for '{title}' Chinese pop song, "
    f"1080x1920 portrait format, "
    f"dark atmospheric gradient, deep indigo #0a0f1e to dark purple, "
    f"subtle music notes, cinematic lighting, "
    f"smooth gradient suitable for text overlay, "
    f"no text"
)
```

Call `image_gen.generate(prompt, width=1080, height=1920, model="flux", seed=optional, out_path=...)`

**Fallback chain**:
1. Try Pollinations.ai with 120s timeout → if success, use generated image
2. If Pollinations timeout/error → try local `assets/backgrounds/*` (any cached image, scaled to vertical)
3. If no local assets → generate solid gradient via FFmpeg: `ffmpeg -f lavfi -i "color=c=#0a0f1e:s=1080x1920" -frames:v 1 bg-fallback.png`

**Timeout**: 120s (Pollinations can take 30-90s; this is the bottleneck step)
**Input**: `title` (song title for prompt), `songs_dir`
**Output on SUCCESS**: `{"bg_path": "output/2026-05-12/shorts-bg-01.jpg", "bg_source": "pollinations"|"local_asset"|"gradient_fallback"}` → GO TO STEP 4
**Output on FAILURE**:
  - `FAILURE(pollinations_timeout)`: 120s elapsed → fallback to local/gradient → continue (degraded)
  - `FAILURE(pollinations_error)`: API returns non-image → fallback → continue
  - `FAILURE(all_fallbacks_failed)`: No background available at all → continue with `bg_path=None` (FFmpeg will use solid color)

**Observable states**:
  - Customer sees: nothing (but the resulting Short will have this background or a fallback)
  - Operator sees: log line `[nightly:shorts] Background: generated via Pollinations (128.4 KB)` or `[nightly:shorts] Background: Pollinations timeout, using local fallback`
  - Database: N/A
  - Logs: `[nightly:shorts] bg_source=pollinations, bg_size_kb=128.4`

---

## STEP 4: Vertical Video Render (1080×1920 with Waveform + Overlays)

**Actor**: FFmpeg
**Action**: Render a vertical Short video with:
- Background image (1080×1920, scaled to fill)
- Waveform visualization (centered, responsive)
- Song title overlay (top area, CJK font, large)
- Artist/trending reference (subtitle line)
- Lyrics karaoke — show the chorus lyrics as scrolling overlay

**FFmpeg filter chain** (simplified):

```
Inputs:
  [0] background image (looped)
  [1] chorus audio clip.mp3

Filter complex:
  [0] scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2[bg]
  [1] showwaves=s=1080x400:mode=cline:rate=25:colors=#FF6B6B|#4ECDC4[waves]
  [bg][waves] overlay=0:(H-400)/2,
       drawtext=text='{title}':fontfile={font}:fontcolor=white:fontsize=56:x=(w-text_w)/2:y=80,
       drawtext=text='{artist_ref}':fontfile={font}:fontcolor=#FF6B6B:fontsize=28:x=(w-text_w)/2:y=150,
       drawtext=text='{lyrics_line}':fontfile={font}:fontcolor=white:fontsize=36:x=(w-text_w)/2:y=H-200
       [out]
```

**Lyrics karaoke approach**:
- Parse lyrics from `song["lyrics"]` — find the lines between `[Chorus]` and the next section marker
- OR use a simplified approach: show the first 2-3 lines of the chorus lyrics as static text
- For v1: static lyrics overlay (not per-beat synced)
- If no lyrics available → skip lyrics overlay, just show title + waveform

**Duration**: clip duration (45s or less)
**Resolution**: 1080×1920 (vertical, 9:16 aspect ratio)

**Output codec**: H.264 with AAC audio

**Timeout**: 300s (5 min — rendering a 45s video at 1080×1920 with complex filters)
**Input**:
  - `clip_path` (from Step 2)
  - `bg_path` (from Step 3, or None)
  - `title` (from selected song)
  - `artist_ref` (from selected song's trending_artist/trending_song)
  - `lyrics` (for karaoke overlay)
  - `songs_dir`, `song_number`
  - `font_path` (from `_find_cjk_font()`)

**Output on SUCCESS**: `{"short_path": "output/2026-05-12/01-雨后初霁-short.mp4", "short_duration": 45.0}` → GO TO STEP 5
**Output on FAILURE**:
  - `FAILURE(ffmpeg_error)`: FFmpeg exits non-zero → retry once with simplified filters (no lyrics overlay, simpler waveform) → if still fails → `SKIP_SHORT`
  - `FAILURE(timeout)`: FFmpeg hangs > 300s → kill process → `SKIP_SHORT`
  - `FAILURE(output_missing)`: Output file not created → `SKIP_SHORT`
  - `FAILURE(output_too_small)`: File < 50KB → likely corrupt → `SKIP_SHORT`

**Observable states**:
  - Customer sees: nothing
  - Operator sees: log line `[nightly:shorts] Rendering Short: 01-雨后初霁-short.mp4 (45s, 1080x1920)`
  - Database: N/A
  - Logs: `[nightly:shorts] Render OK: 12.3MB, 45.0s, 1080x1920`

---

## STEP 5: Upload to YouTube as Short (Scheduled 12pm SGT)

**Actor**: `nightly_uploader.py` (existing module — reused)
**Action**: Upload the rendered Short MP4 to YouTube. Must use the **Shorts-specific schedule** (12pm SGT) and metadata including `#Shorts` tag.

**Key differences from full video upload**:
| Property | Full Video | Short |
|---|---|---|
| Schedule | 6pm SGT | 12pm SGT |
| Tags | `#AIMusic`, `#华语流行` etc. | Same + `#Shorts` |
| Title | Song title only | Song title + `#Shorts` suffix |
| Description | Same template | Same template + "Subscribe for daily AI music!" |
| Playlist | Full videos | Separate Shorts playlist |
| Privacy | `private` (testing) | `private` (testing, same as full) |

**Schedule calculation**:
```python
from datetime import datetime, timezone, timedelta
sgt = timezone(timedelta(hours=8))
publish_dt = datetime.strptime(date_label, "%Y-%m-%d").replace(
    hour=12, minute=0, second=0, tzinfo=sgt
)
publish_at = publish_dt.isoformat()
```

**Warning**: If the pipeline runs at 2am and the Short generation completes at ~2:05am, scheduling for 12pm SGT the same day gives ~10 hours. If the Short generation is significantly delayed (unlikely but possible), `publish_at` may be in the past → YouTube API will reject it. Mitigation: if `datetime.now(SGT) > publish_dt`, set privacy to `public` and upload immediately (no scheduling).

**Desired vs actual publish_at**: YouTube's `publishAt` must be at least 10-15 minutes in the future. Our 12pm SGT target is always well beyond this window when the pipeline finishes at ~2:05am.

**Timeout**: 300s (5 min — resumable upload handles network issues)
**Input**:
  - `short_path` (from Step 4)
  - `title` (from selected song, truncated to 97 chars + " #Shorts")
  - `description` (SEO description generated from template)
  - `tags` (from config + "#Shorts")
  - `category_id` = "10" (Music)
  - `privacy` = "private"
  - `publish_at` = 12pm SGT ISO datetime
  - `thumbnail_path` = None (Shorts auto-select thumbnail)

**Output on SUCCESS**: `{"video_id": "abc123", "youtube_url": "https://youtube.com/shorts/abc123", "status": "ok"}` → GO TO STEP 6
**Output on FAILURE**:
  - `FAILURE(quota_exceeded)`: YouTube API returns quota error → `SKIP_SHORT` (notify operator)
  - `FAILURE(auth_failed)`: OAuth token expired and refresh failed → `SKIP_SHORT`
  - `FAILURE(api_error)`: Other YouTube API error → retry with 2^retry backoff (x2 max) → if still fails → `SKIP_SHORT`
  - `FAILURE(schedule_in_past)`: `publish_at` is in the past → upload immediately with `privacy="public"` (no scheduling)
  - `FAILURE(timeout)`: Upload hangs > 300s → `SKIP_SHORT`

**Observable states**:
  - Customer sees: Short will appear at 12pm SGT (or immediately if schedule failed)
  - Operator sees: log line `[nightly:shorts] Short uploaded: https://youtube.com/shorts/abc123 (scheduled 12pm SGT)`
  - Database: song-log.json updated with short fields
  - Logs: `[nightly:shorts] Upload OK: video_id=abc123, scheduled=2026-05-12T12:00:00+08:00`

---

## STEP 6: Inject Short Result into Main Pipeline (Telegram Notification)

**Actor**: Shorts Orchestrator → Main Pipeline
**Action**: Merge the Short upload result into the main pipeline's data structures so it appears in the Telegram notification.

**Merge logic**: Add `short_result` into the day's data. The Telegram notification gains an additional line for the Short.

**Current Telegram format** (from `send_telegram_batch()`):
```
🌙 AI Music — 2026-05-12
📦 Batch 1/1 (Songs 1-2)

✅ Song #1: 雨后初霁
   2:34 · 类似周杰伦的《晴天》风格
   🔗 https://youtube.com/watch?v=abc123

✅ Song #2: 雨季的告白
   3:07 · 类似颜人中的《我只能离开》风格
   🔗 https://youtube.com/watch?v=def456
```

**New Telegram format with Shorts**:
```
🌙 AI Music — 2026-05-12
📦 Batch 1/1 (Songs 1-2)

✅ Song #1: 雨后初霁
   2:34 · 类似周杰伦的《晴天》风格
   🔗 https://youtube.com/watch?v=abc123

✅ Song #2: 雨季的告白
   3:07 · 类似颜人中的《我只能离开》风格
   🔗 https://youtube.com/watch?v=def456

📱 Short: 雨后初霁 (#Shorts)
   🕛 12pm SGT
   🔗 https://youtube.com/shorts/abc123
```

**Implementation**: After the main songs section in `send_telegram_batch()`, append the Short section if `short_result` exists and `short_result["status"] == "ok"`.

**Timeout**: 0.1s (in-memory merge, no I/O)
**Input**: `short_result` dict, `song_results` list, `telegram_caption_builder`
**Output on SUCCESS**: Telegram message sent with Short link
**Output on FAILURE**:
  - `FAILURE(telegram_api_error)`: Telegram API fails — log warning, not critical (Short still uploaded)

**Observable states**:
  - Customer sees: Telegram message with Short link (if Telegram succeeds)
  - Operator sees: log line `[nightly:shorts] Short link added to Telegram message`
  - Database: song-log.json updated
  - Logs: `[nightly:shorts] Telegram injection complete`

---

## SKIP_SHORT: Graceful Skip Path

**Triggered by**: Any non-recoverable failure in Steps 0-5
**Actions**:
  1. Log warning with step number and error detail
  2. Set `short_result = {"status": "skipped", "step": "<step_name>", "error": "<error_detail>"}`
  3. Clean up any intermediate files created up to the failure point (clip, background, partial render)
  4. Return control to main pipeline immediately
  5. Do NOT abort main pipeline — other songs continue processing normally

**What operator sees**: Log line `[nightly:shorts] SKIPPED at Step 2 (audio extraction): FFmpeg exited code 1 — continuing main pipeline`

**Intermediate cleanup inventory for SKIP_SHORT**:

| Resource | Created at | Cleanup action |
|---|---|---|
| Chorus audio clip | Step 2 | `os.remove(clip_path)` |
| Background image | Step 3 | `os.remove(bg_path)` |
| Partial render | Step 4 | `os.remove(partial_output)` if exists |

---

## State Transitions

```
[inactive] → (pipeline start, shorts enabled) → [selecting_song]
[selecting_song] → (song selected) → [chorus_detecting]
[selecting_song] → (no suitable song) → [skipped]

[chorus_detecting] → (found) → [audio_extracting]
[chorus_detecting] → (too short / silent) → [skipped]
[chorus_detecting] → (ffprobe failed) → use fallback → [audio_extracting]

[audio_extracting] → (clip ready) → [background_generating]
[audio_extracting] → (failed, retried) → (still failed) → [skipped]

[background_generating] → (image ready) → [rendering]
[background_generating] → (timeout) → use fallback → [rendering]
[background_generating] → (all fallbacks failed) → [rendering] (with solid color)

[rendering] → (render ok) → [uploading]
[rendering] → (failed, retried with simplified filters) → (ok) → [uploading]
[rendering] → (failed all retries) → [skipped]

[uploading] → (uploaded) → [telegram_injected] → [completed]
[uploading] → (quota exceeded / auth failed / timeout) → [skipped]
[uploading] → (schedule in past) → upload immediately → [telegram_injected] → [completed]

[skipped] → [completed]
```

```
ASCII state machine:

                    ┌─────────┐
                    │inactive │
                    └────┬────┘
                         │ pipeline starts
                         ▼
                   ┌───────────┐
                   │ selecting │
                   │   song    │
                   └─────┬─────┘
                    ┌────┴────┐
                    │         │
               ┌────▼──┐  ┌──▼──────┐
               │chorus │  │ skipped │◄── no suitable song
               │ detect│  └─────────┘
               └───┬───┘
              ┌────┴─────┐
         ┌────▼──┐  ┌────▼──────┐
         │ audio │  │ skipped  │◄── too short/silent
         │ extract│ └──────────┘
         └───┬────┘
        ┌────┴─────┐
   ┌────▼────┐ ┌───▼────────┐
   │  bg gen │ │  skipped  │◄── ffmpeg failure
   └────┬────┘ └────────────┘
   ┌────┴─────┐
   │  render  │──→ skip on all failures
   └────┬────┘
   ┌────┴─────┐
   │  upload  │──→ skip on api failure
   └────┬────┘
   ┌────┴─────────┐
   │ telegram     │
   │ inject       │
   └────┬─────────┘
   ┌────┴────┐
   │completed│
   └─────────┘
```

---

## Handoff Contracts

### Contract 1: Main Pipeline → Shorts Orchestrator

```
HANDOFF: nightly_music.py.run_pipeline() -> nightly_shorts.generate_short()
  PAYLOAD: {
    song_results: [
      {
        "status": "success" | "failed",
        "title": str,
        "mp3_path": str,           # "/path/to/01-title.mp3"
        "txt_path": str,           # "/path/to/01-title.txt"
        "duration_sec": float,     # 154.8
        "lyrics": str,             # Full lyrics text with [Verse], [Chorus], etc.
        "song_number": int,        # 1
        "trending_song": str,      # "晴天"
        "trending_artist": str,    # "周杰伦"
        "prompt": str,
        "error": str | None,
      },
      # ... song_results[1] ...
    ],
    date_label: str,               # "2026-05-12"
    songs_dir: str,                # "/path/to/output/2026-05-12"
    config: {
      "shorts": {
        "enabled": bool,
        "publish_hour_sgt": int,   # 12
        "chunk_duration": int,     # 45
        "fallback_on_failure": bool,
      }
    }
  }
  TIMEOUT: 600s (10 min — total budget for Short generation)
  ON FAILURE: Log warning, continue main pipeline
```

### Contract 2: Shorts Orchestrator → FFprobe (Chorus Detection)

```
HANDOFF: subprocess.run(ffprobe) -> chorus window
  COMMAND: ffprobe -v error -show_entries stream=codec_type,duration -of json "{mp3_path}"
  SUCCESS RESPONSE: JSON with stream info + duration
  FAILURE RESPONSE: Non-zero exit code, stderr text
  TIMEOUT: 15s
  ON FAILURE: Fallback to middle 45s segment
  OUTPUT: {"chorus_start": float, "chorus_end": float}
```

### Contract 3: Shorts Orchestrator → FFmpeg (Audio Extraction)

```
HANDOFF: subprocess.run(ffmpeg) -> chorus clip MP3
  COMMAND: ffmpeg -y -i "{mp3_path}" -ss {start} -t {duration} -c:a libmp3lame -b:a 192k "{clip_path}"
  SUCCESS RESPONSE: Exit code 0, file exists at clip_path
  FAILURE RESPONSE: Non-zero exit code
  TIMEOUT: 10s
  ON FAILURE: Retry with -ss after -i (slow seek) -> SKIP_SHORT if still fails
  OUTPUT: {"clip_path": str}
```

### Contract 4: Shorts Orchestrator → Pollinations.ai (Background)

```
HANDOFF: image_gen.generate() -> background image
  PAYLOAD: {
    prompt: "vertical portrait background for '{title}' ...",
    width: 1080,
    height: 1920,
    model: "flux",
    seed: None | int,
  }
  SUCCESS RESPONSE: str (file path to saved image)
  FAILURE RESPONSE: RuntimeError (timeout, connection, bad content type)
  TIMEOUT: 120s
  ON FAILURE: Fallback chain: local assets -> gradient
  OUTPUT: {"bg_path": str, "bg_source": "pollinations" | "local" | "gradient"}
```

### Contract 5: Shorts Orchestrator → FFmpeg (Vertical Render)

```
HANDOFF: subprocess.run(ffmpeg) -> Short MP4
  COMMAND: ffmpeg -y -loop 1 -i {bg_path} -i {clip_path} -filter_complex "..." -t {duration} -c:v libx264 ... "{short_path}"
  SUCCESS RESPONSE: Exit code 0, file exists at short_path, size > 50KB
  FAILURE RESPONSE: Non-zero exit code, or output missing/toosmall
  TIMEOUT: 300s
  ON FAILURE: Retry once with simplified filters -> SKIP_SHORT
  OUTPUT: {"short_path": str, "short_duration": float}
```

### Contract 6: Shorts Orchestrator → YouTube Uploader

```
HANDOFF: nightly_uploader.upload_video() -> upload result
  PAYLOAD: {
    video_path: str,             # short_path from Step 4
    title: str,                  # Song title (truncated to 97 chars)
    description: str,            # SEO description with Shorts template
    tags: [str],                 # Config tags + "#Shorts"
    category_id: "10",
    privacy: "private",
    thumbnail_path: None,
    publish_at: str,             # ISO 8601: "2026-05-12T12:00:00+08:00"
  }
  SUCCESS RESPONSE: {
    "video_id": "abc123",
    "youtube_url": "https://www.youtube.com/watch?v=abc123",
    "status": "ok",
  }
  FAILURE RESPONSE: {
    "video_id": "",
    "youtube_url": "",
    "status": "failed",
    "error": str,
  }
  TIMEOUT: 300s
  ON FAILURE: Retry x2 with exponential backoff -> SKIP_SHORT
  OUTPUT: {"video_id": str, "youtube_url": str, "status": "ok"|"failed"}
```

### Contract 7: Shorts Orchestrator → Main Pipeline (Result Merge)

```
HANDOFF: short_result -> main pipeline song_results + telegram
  PAYLOAD: {
    "status": "ok" | "skipped" | "pipeline_error",
    "song_number": int,           # Which song was selected
    "selected_title": str,         # "雨后初霁"
    "short_path": str,             # "/path/to/short.mp4"
    "clip_path": str,              # "/path/to/chorus.mp3"
    "bg_source": str,              # "pollinations" | "local" | "gradient"
    "video_id": str,               # "abc123" (if uploaded)
    "youtube_url": str,            # "https://youtube.com/shorts/abc123" (if uploaded)
    "scheduled_at": str,           # "2026-05-12T12:00:00+08:00" (if uploaded)
    "error": str | None,           # Error detail if skipped/failed
    "steps_completed": [str],      # ["step1_chorus", "step2_audio", "step3_bg", "step4_render", "step5_upload"]
    "duration_sec": float,         # Actual rendered duration
  }
  TIMEOUT: 0.1s
  ON FAILURE: Telegram notification still succeeds — Short info is additive
```

---

## Cleanup Inventory

| Resource | Created at | Destroyed by | Destroy method |
|---|---|---|---|
| Chorus clip MP3 | Step 2 | SKIP_SHORT | `os.remove(clip_path)` |
| Pollinations background | Step 3 | SKIP_SHORT | `os.remove(bg_path)` |
| Fallback gradient PNG | Step 3 (fallback) | SKIP_SHORT | `os.remove(fallback_path)` |
| Rendered Short MP4 | Step 4 | SKIP_SHORT (if render failed) | `os.remove(partial_output)` |
| Rendered Short MP4 | Step 4 | Never (keep for posterity) if upload succeeds | — |
| Chorus clip MP3 | Step 2 | End of pipeline | `os.remove(clip_path)` — safe to delete after upload |

**Retention policy**: Keep the Short MP4 in `output/{date_label}/` alongside the full visualizer. Delete the intermediate chorus clip MP3 after upload to save space. The background image can be kept (reused across nights if good) or deleted.

---

## Pacing Budget

| Step | Operation | Typical time | Worst case | Timeout |
|---|---|---|---|---|
| 0 | Song selection | 0.1s | 0.1s | 0.5s |
| 1 | Chorus detection (ffprobe) | 2-3s | 10s | 15s |
| 2 | Audio clip extraction | 1-2s | 5s | 10s |
| 3 | Background generation (Pollinations) | 30-90s | 110s | 120s |
| 4 | Vertical FFmpeg render | 30-60s | 120s | 300s |
| 5 | YouTube upload | 20-30s | 120s | 300s |
| 6 | Telegram injection | 0.1s | 1s | 5s |
| **Total** | **Best case** | **~65s** | **~368s (~6min)** | **750s total budget** |

**Impact on main pipeline**: The Short sub-pipeline adds at most ~6 minutes to the total runtime (worst case) and ~1-2 minutes typically. The main pipeline already has a 10-minute visualizer timeout per song (×2 songs = 20 min budget). The Short easily fits within the existing slack.

```
Pipeline timeline (typical):
2:00:00 — CRON fires
2:00:02 — Load config
2:00:05 — Fetch trending + dedup
2:00:35 — MiniMax gen song 1 (~30s)
2:01:05 — MiniMax gen song 2 (~30s)
2:01:35 — Visualizer song 1 (~60s)
2:02:35 — Visualizer song 2 (~60s)
          ┌─── SHORTS SUB-PIPELINE (parallel) ───┐
2:01:35   │  Chorus detection (2s)               │
2:01:37   │  Audio extraction (1s)                │
2:01:38   │  Background gen (45s)                 │
2:02:23   │  Vertical render (45s)                │
2:03:08   │  YouTube upload (25s)                 │
2:03:33   │  Telegram inject (0.1s)               │
          └───────────────────────────────────────┘
2:03:35 — D-drive sync
2:03:40 — Log
2:03:45 — Telegram delivery
2:03:50 — Complete (~3.8 min total)
```

---

## Config Changes Required

Add to `config/nightly-music.yaml`:

```yaml
# YouTube Shorts settings
shorts:
  enabled: true
  publish_hour_sgt: 12        # 12pm SGT — separate from full videos (6pm)
  chunk_duration: 45           # Seconds for chorus clip (max 60 for Shorts)
  selection_strategy: "first"  # "first" | "random" | "longest"
  background_generation: true  # Use Pollinations.ai for vertical backgrounds
  lyrics_karaoke: true         # Show lyrics overlay on Short
  prune_intermediates: true    # Delete chorus clip after upload (save space)
```

---

## Test Cases

| Test | Trigger | Expected behavior |
|---|---|---|
| TC-01: Happy path — Short generated and uploaded | 2 songs generated, first song > 45s, all APIs healthy | Short uploaded at 12pm SGT, Telegram includes Short link |
| TC-02: Song too short (< 45s) | selected song duration = 32s | SKIP_SHORT at Step 1, log warning, pipeline continues |
| TC-03: Chorus detection timeout | ffprobe hangs > 15s | Fallback to middle 45s, continue with warning |
| TC-04: All songs failed generation | song_results both have status="failed" | SKIP_SHORT at Step 0, no short attempted |
| TC-05: Pollinations.ai timeout (> 120s) | Pollinations request hangs | Fallback to local asset → gradient → render continues |
| TC-06: FFmpeg render fails (exit code 1) | Corrupt input clip or missing codec | Retry once with simplified filters → SKIP_SHORT if still fails |
| TC-07: YouTube quota exceeded | API returns quota error | SKIP_SHORT, log quota warning |
| TC-08: YouTube upload schedule in past | Pipeline delayed beyond 12pm SGT | Upload immediately with current timestamp, privacy unchanged |
| TC-09: OAuth token refresh fails | Token expired, refresh fails | SKIP_SHORT, log auth error |
| TC-10: Partial failure — background fails but render succeeds | Pollinations fails, fallback gradient used | Short generated with solid gradient, upload continues |
| TC-11: Partial failure — render succeeds but upload fails | API intermittent error (500) | Retry x2 → SKIP_SHORT, Short MP4 file preserved on disk |
| TC-12: Dry run compatibility | `--dry-run` flag set | Simulate all steps, log what would happen, no actual API calls |
| TC-13: No chorus detected in lyrics | Song has no `[Chorus]` tag | Use RMS peak detection on audio, don't rely on lyrics |
| TC-14: Both songs qualify — selection | 2 successful songs, both > 45s | Pick first (song_results[0]) |
| TC-15: Shorts disabled in config | `shorts.enabled: false` | Skip entire sub-pipeline, no log output about Shorts |

---

## Assumptions

| # | Assumption | Where verified | Risk if wrong |
|---|---|---|---|
| A1 | FFmpeg + FFprobe 6.1.1+ are installed and on PATH | Verified: `nightly_visualizer.py` uses them | Chorus detection and render both fail → SKIP_SHORT |
| A2 | Pollinations.ai is reachable from WSL at 2am SGT | Not verified — depends on network | Background fallback chain handles this (local/gradient) |
| A3 | The 45s chorus clip will produce a visually interesting Short | Not verified — depends on song structure | If chorus is quiet/build-up, Short may be boring — monitor and adjust |
| A4 | YouTube API supports `publishAt` for vertical Shorts the same as horizontal | Assumed based on YouTube API docs | Upload succeeds but scheduling may need workaround |
| A5 | CJK font for lyrics overlay is the same font used by visualizer | Verified: `_find_cjk_font()` shared | Lyrics render as boxes — need font fallback in filter chain |
| A6 | Song duration ≥ 45s is sufficient for a meaningful Short clip | Verified: all songs in log are 120-200s | Very short songs (< 45s) handled by SKIP_SHORT |
| A7 | Pollinations can generate 1080×1920 images | Assumed — API supports up to 4096px | Might stretch/distort — validate with test run |
| A8 | Intermediate chorus clips can be deleted after upload | Assumed — MP3 is derived from original | If original gets deleted, clip could be useful — adjust retention if needed |
| A9 | Short upload at 12pm SGT does not conflict with full video at 6pm SGT | Assumed — YouTube allows multiple uploads/day | No risk — different schedule, no conflict |
| A10 | The Short sub-pipeline should run sequentially (not parallel with visualizer) to avoid FFmpeg contention | Not verified — both use FFmpeg | If both run in parallel, FFmpeg may compete for CPU → run Shorts after visualizers |

---

## Open Questions

| # | Question | Raised by | Needs decision from |
|---|---|---|---|
| Q1 | **Song selection strategy**: Which song becomes the Short? Options: (a) always first, (b) random, (c) based on energy/analysis, (d) both songs get Shorts | Workflow Architect | Boss |
| Q2 | **Independent Shorts playlist**: Should Shorts go into a separate YouTube playlist from full videos? (Recommended: yes) | Workflow Architect | Boss |
| Q3 | **Thumbnail for Shorts**: YouTube Shorts auto-select from the video frame. Do we need a custom thumbnail (like full videos have)? | Workflow Architect | Boss |
| Q4 | **Re-use generated background**: If Pollinations generates a nice background, should we save it for reuse across nights (named by song/topic) or always regenerate? | Workflow Architect | Boss |
| Q5 | **Both songs or one**: Phase 2 mentions "auto-clip top 3 songs → 60s vertical format". Should we aim for 1 Short per night (v1) or both songs as Shorts (v2)? | Workflow Architect | Boss |
| Q6 | **Short privacy**: Currently full videos are `private`. Should Shorts match the same privacy setting, or be `unlisted`/`public` for discovery? | Workflow Architect | Boss |
| Q7 | **Monetization note**: Shorts have different monetization rules (must be > 60s for Shorts Fund). Our 45s clips won't qualify — just awareness, not a decision. | Workflow Architect | — |

---

## Files Required for Implementation

| File | Action | Purpose |
|---|---|---|
| `scripts/nightly_shorts.py` | **CREATE** | New module — Shorts orchestration: song selection, chorus detection, audio extraction, vertical render, result merge |
| `scripts/nightly_music.py` | **MODIFY** | Add Shorts hook point after song generation; import `nightly_shorts`; merge short_result into telegram caption |
| `scripts/image_gen.py` | **MODIFY** | Optionally add a preset `generate_short_background(title, out_path)` with 1080×1920 prompt |
| `scripts/nightly_uploader.py` | **NO CHANGE** | Reusable as-is — `upload_video()` handles any resolution, scheduling already built |
| `config/nightly-music.yaml` | **MODIFY** | Add `shorts:` config section |
| `scripts/nightly_visualizer.py` | **NO CHANGE** | Not involved in Shorts pipeline |
| `docs/workflows/WORKFLOW-youtube-shorts.md` | **CREATE** | This document |

---

## Spec vs Reality Audit Log

| Date | Finding | Action taken |
|---|---|---|
| 2026-05-12 | Initial spec created | — |
| TBD | [To be filled after Reality Checker verification against actual code] | — |
| TBD | [To be filled after first deployment] | — |
