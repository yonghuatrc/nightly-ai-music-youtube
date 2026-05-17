# Stage-by-Stage Pipeline Testing

> **Goal:** Break the monolithic pipeline into independently testable stages. Each stage has clear inputs, outputs, validation criteria, and a PASS/FAIL gate before moving to the next stage.
>
> **Started:** 2026-05-14
> **Status:** ⬜ Planning

---

## Pipeline Stages

```
A ──→ B ──→ C ──┬──→ D ──→ F ──→ G ──→ H
                 │   ↗
                 └──→ E ──┘

                 I (Sunday only, after E of Mon-Sat)
```

---

## Stage A: Configuration + Trending Fetch + Dedup

| Property | Detail |
|----------|--------|
| **Input** | `--date YYYY-MM-DD` |
| **Output** | `trending_songs: list[dict]` |
| **CLI** | `python3 nightly_music.py --date X --stage fetch` |
| **Runtime** | ~30s |
| **Depends on** | Nothing |
| **Parallelizable** | No |

### Validation

```
[STAGE A] fetch_trending: loaded X songs from pool+qq+kkbox+myfm
[STAGE A] check_dedup: filtered Y duplicates, keeping Z songs
[STAGE A] PASS: {song_count} trending songs ready for stage B
```

### Test
```bash
python3 scripts/fetch_trending.py --source pool --count 5
# Expected: 5 songs with song/artist/source/style_prompt fields
```
```bash
python3 scripts/check-duplicate.py --output /tmp/dedup-test.txt
# Expected: 0 duplicates for fresh songs, N removed for known songs
```

### Status
- [ ] Stage CLI stub (`--stage fetch`) in `nightly_music.py`
- [ ] Config loaded from `nightly-music.yaml`
- [ ] Trending fetch from pool/qq/kkbox/myfm sources
- [ ] Dedup against last 7 days (song-log + output dirs)
- [ ] Daily output directory created (`output/YYYY-MM-DD/`)
- [ ] Tested with `--date` flag
- [ ] Signed off

### Known Issues
- None

---

## Stage B: Song Generation (MiniMax)

| Property | Detail |
|----------|--------|
| **Input** | `trending_songs` + `weekly_theme` |
| **Output** | `song_results: list[dict]` (MP3 + TXT files in `output/YYYY-MM-DD/`) |
| **CLI** | `python3 scripts/minimax_music_api.py --input X` |
| **Runtime** | ~360s (2 songs sequenced via MiniMax async) |
| **Depends on** | Stage A |
| **Parallelizable** | No |

### Validation

```
[STAGE B] minimax_music_api: generating song 1/2 "{title}"...
[STAGE B] minimax_music_api: song 1/2 complete (duration={N}s, lyrics={M} chars)
[STAGE B] minimax_music_api: generating song 2/2 "{title}"...
[STAGE B] minimax_music_api: song 2/2 complete (duration={N}s, lyrics={M} chars)
[STAGE B] PASS: 2 songs saved to output/YYYY-MM-DD/
```

### Test
```bash
python3 scripts/minimax_music_api.py \
  --prompt "一首关于夜晚的中文流行歌曲" \
  --output /tmp/stage-b-test
# Expected: MP3 + TXT files created, duration > 60s, lyrics > 100 chars
# Verify: ls -la /tmp/stage-b-test/
```

### Status
- [ ] Stage CLI stub in main pipeline
- [ ] MiniMax API key loaded from `~/.hermes/.env`
- [ ] Song generation (2 songs sequenced)
- [ ] MP3 saved with correct naming: `01-{title-slug}.mp3`
- [ ] TXT lyrics saved alongside MP3
- [ ] Weekly theme injected into generation prompt
- [ ] Tested with known-good prompt
- [ ] Signed off

### Known Issues
- **B2.1** — MiniMax API timeout: no retry wrapper. If API takes >120s, pipeline fails with no fallback.
- Song metadata (title, artist) may contain placeholders if MiniMax doesn't follow prompt structure.

---

## Stage C: Quality Gate

| Property | Detail |
|----------|--------|
| **Input** | `song_results` (lyrics text, duration_seconds, title) |
| **Output** | `song_results` enriched with `quality_score`, `hero_verdict`, `standard_verdict` |
| **CLI** | `python3 scripts/song_quality.py --input output/YYYY-MM-DD/` |
| **Runtime** | <1s |
| **Depends on** | Stage B |
| **Parallelizable** | Can run alongside D, E, F (independent of assets/viz) |

### Validation

```
[STAGE C] song_quality: scoring song 1 "{title}"...
[STAGE C]   lyrics_length=X/3.0  has_chorus=Y/2.5  duration=Z/2.0
[STAGE C]   placeholder_check=W/1.5  vocabulary_richness=V/1.0
[STAGE C]   TOTAL={score}/10.0 → {"hero"|"standard"|"rejected"}
[STAGE C] PASS: song 1={score}/10 (hero≥6, standard≥4)
```

### Test
```bash
python3 scripts/song_quality.py --date 2026-05-14
# Expected: two scores printed, classification per config thresholds
# Verify: check config/nightly-music.yaml quality_gate section
```

### Status
- [ ] Stage CLI stub in main pipeline
- [ ] 5-dimension scoring (lyrics_length, has_chorus, duration, placeholder_check, vocabulary_richness)
- [ ] Hero threshold config (≥6.0)
- [ ] Standard threshold config (≥4.0)
- [ ] Reject handling (skip upload, log, Telegram alert)
- [ ] Tested with borderline cases (3.9, 4.0, 5.9, 6.0)
- [ ] Signed off

### Known Issues
- Quality score thresholds are initial guesses. Needs tuning after 7+ days of real scoring data.
- `has_chorus` detection is heuristic (keyword-based: 副歌/chorus/重复). May miss implicit choruses.

---

## Stage D: Asset Generation (Backgrounds + Thumbnails)

| Property | Detail |
|----------|--------|
| **Input** | `song_results` (title, lyrics, song_number) |
| **Output** | `bg.jpg` (1920×1080), `bg-vertical.jpg` (1080×1920), `thumb.jpg` (1280×720) per accepted song |
| **CLI** | `python3 scripts/image_gen.py --input output/YYYY-MM-DD/` |
| **Runtime** | ~60s per song (2 requests + 15s rate limit + resize) |
| **Depends on** | Stage B (needs lyrics for prompt) |
| **Parallelizable** | Yes — can run alongside E (viz). Songs within stage are sequential. |

### Validation

```
[STAGE D] prompt_gen: generating image prompt for song "{title}"...
[STAGE D]   Priority 1: MiniMax LLM → OK
[STAGE D]   prompt: "{description}, no people, no faces, no text"
[STAGE D] image_gen: downloading background for song 1...
[STAGE D]   bg.jpg: 1920x1080 ✓  bg-vertical.jpg: 1080x1920 ✓  thumb.jpg: 1280x720 ✓
[STAGE D] PASS: 3 assets generated for song 1
```

### Test
```bash
python3 scripts/image_gen.py --title "星空" --output /tmp/stage-d-test
# Expected: 3 JPG files with correct dimensions
# Verify: identify /tmp/stage-d-test/*.jpg  (or use ffprobe)
```
```bash
python3 scripts/prompt_gen.py --lyrics "夜空中最亮的星 能否听清" --song-number 1
# Expected: image prompt string with "no people, no faces, no text" suffix
```

### Status
- [ ] Stage CLI stub in main pipeline
- [ ] Image prompt generation (MiniMax LLM → Pollinations.ai → keyword fallback)
- [ ] Background download (Pollinations.ai, FLUX model, 1920×1080)
- [ ] Vertical background generation (1080×1920 for Shorts)
- [ ] Thumbnail creation (1280×720, Pillow resize)
- [ ] 15s rate limit between requests
- [ ] "No people, no faces, no text" enforcement in prompts
- [ ] Fallback when all image sources fail (solid color background)
- [ ] Tested with real lyrics input
- [ ] Signed off

### Known Issues
- **B4.1** — Pollinations.ai transient failures: no retry wrapper. ~5-10% of requests return 5xx or empty response.
- Pollinations.ai may not always respect "no people/faces" in prompt — occasional NSFW/non-compliant images need filtering.

---

## Stage E: Visualizer + SRT

| Property | Detail |
|----------|--------|
| **Input** | MP3 + `bg.jpg` + lyrics + `mood_palette` (color_primary, color_secondary) |
| **Output** | `viz.mp4` (1920×1080, song-length) + `viz.srt` (full-song timed subtitles) |
| **CLI** | `python3 scripts/nightly_visualizer.py --date YYYY-MM-DD --song 1` |
| **Runtime** | ~300s per song (FFmpeg waveform + subtitle burn-in) |
| **Depends on** | Stage C (mood) + Stage D (background) — falls back to defaults if D not run |
| **Parallelizable** | Yes — can run alongside D (assets). Songs within stage are sequential. |

### Validation

```
[STAGE E] nightly_visualizer: generating visualizer for song "{title}"...
[STAGE E]   mood: {label} → colors {primary}/{secondary}
[STAGE E]   audio: {duration}s waveform overlay
[STAGE E]   background: bg.jpg (1920×1080)
[STAGE E]   subtitles: viz.srt ({N} lines, evenly distributed)
[STAGE E]   output: viz.mp4 ({N}s, 1920×1080, {X} kbps)
[STAGE E] PASS: viz.mp4 and viz.srt created for song 1
```

### Test
```bash
python3 scripts/nightly_visualizer.py --date 2026-05-14 --song 1
# Expected: viz.mp4 + viz.srt in output/YYYY-MM-DD/01-*/
# Verify: ffprobe viz.mp4 (duration matches song, resolution 1920x1080)
# Verify: head -20 viz.srt (timestamps increasing, no overlap)
```
```bash
# Test standalone: use any MP3 + JPG
python3 scripts/nightly_visualizer.py \
  --mp3 /path/to/test.mp3 \
  --bg /path/to/bg.jpg \
  --output /tmp/stage-e-test.mp4 \
  --lyrics "line1\nline2\nline3" \
  --duration 180 \
  --color1 "#FF6B6B" --color2 "#4ECDC4"
# Expected: 180s MP4 with waveform + lyrics overlay
```

### Status
- [ ] Stage CLI stub in main pipeline
- [ ] FFmpeg waveform overlay with mood colors
- [ ] Background image compositing (bg.jpg as base layer)
- [ ] SRT generation from lyrics (evenly distributed over duration)
- [ ] SRT subtitle burn-in via FFmpeg `subtitles=` filter
- [ ] CJK font support for subtitle rendering (check font path)
- [ ] Section-aware timing (not just even distribution)
- [ ] Mood palette applied (color_primary, color_secondary from stage C)
- [ ] Tested with real MP3 + lyrics
- [ ] Signed off

### Known Issues
- **B1.1** — SRT timing drift: current section-weighted SRT has timing drift. Even distribution means early lines may overrun and late lines may be truncated. Whisper forced alignment can produce frame-accurate subtitles but is deferred.
- CJK font path must be verified on the WSL system. FFmpeg subtitles filter may fail silently if font is missing.
- FFmpeg waveform rendering is slow on long songs (300s+). Could benefit from lower resolution intermediate.

---

## Stage F: Shorts Generation

| Property | Detail |
|----------|--------|
| **Input** | MP3 + `bg-vertical.jpg` + lyrics + title |
| **Output** | `short.mp4` (1080×1920 vertical, 30s) |
| **CLI** | `python3 scripts/nightly_visualizer.py --date X --song 1 --shorts` |
| **Runtime** | ~120s per short (FFmpeg waveform + subtitle burn-in at vertical resolution) |
| **Depends on** | Stage D (`bg-vertical.jpg`) — falls back to scaled `bg.jpg` if D not run |
| **Parallelizable** | Yes — can run alongside E (viz) |

### Validation

```
[STAGE F] nightly_visualizer: generating Shorts for song "{title}"...
[STAGE F]   loudest segment: {start}s–{end}s (30s window)
[STAGE F]   output: short.mp4 (1080×1920, 30s)
[STAGE F] PASS: short.mp4 created for song 1
```

### Test
```bash
python3 scripts/nightly_visualizer.py --date 2026-05-14 --song 1 --shorts
# Expected: short.mp4 in output/YYYY-MM-DD/01-*/
# Verify: ffprobe short.mp4 (30s duration, 1080x1920 resolution)
```

### Status
- [ ] Stage CLI stub in main pipeline
- [ ] Loudest 30s segment detection via FFprobe `astats`
- [ ] Vertical waveform (1080×1920) with mood colors
- [ ] Vertical background (bg-vertical.jpg or scaled bg.jpg)
- [ ] SRT for 30s segment
- [ ] Tested audio frame/sec ratio (Bug B8 fix: window_sec → frame count conversion)
- [ ] Safety guard for <10s fallback when loudest window detection fails
- [ ] Signed off

### Known Issues
- None open. Bug B8 (Shorts duration < 3s) was fixed via frame-count conversion.

---

## Stage G: YouTube Upload

| Property | Detail |
|----------|--------|
| **Input** | `viz.mp4` + `short.mp4` + `thumb.jpg` + metadata (title, description, tags) |
| **Output** | YouTube video IDs + URLs |
| **CLI** | `python3 scripts/nightly_uploader.py --date X --song 1 --tier hero` |
| **Runtime** | ~120s per upload (upload + thumbnail set + scheduling) |
| **Depends on** | Stage E + F (needs final MP4 and thumb) |
| **Parallelizable** | No |

### Validation

```
[STAGE G] nightly_uploader: uploading Hero song "{title}"...
[STAGE G]   YouTube API: video created (ID: abc123)
[STAGE G]   Thumbnail: set successfully
[STAGE G]   Scheduled: 2026-05-15T18:00:00+08:00
[STAGE G]   URL: https://youtu.be/abc123
[STAGE G] PASS: Hero song uploaded + scheduled
```

### Test
```bash
# Dry-run mode (no actual upload):
python3 scripts/nightly_uploader.py \
  --date 2026-05-14 \
  --song 1 \
  --tier hero \
  --dry-run
# Expected: prints what WOULD be uploaded, no API call

# Full upload test (use test YouTube channel):
python3 scripts/nightly_uploader.py \
  --date 2026-05-14 \
  --song 1 \
  --tier hero \
  --privacy unlisted
# Expected: video appears in YouTube Studio with correct schedule
```

### Status
- [ ] Stage CLI stub in main pipeline
- [ ] YouTube OAuth (auto-refresh token from `/mnt/d/Hermes/secrets/`)
- [ ] Video upload (YouTube Data API v3)
- [ ] Thumbnail set via API
- [ ] Scheduled publish (Hero 18:00 SGT, Standard 20:00 SGT, Shorts 12:00 SGT)
- [ ] Privacy setting from config (default: `private`)
- [ ] Dry-run mode for testing
- [ ] Tags + description generated from song metadata
- [ ] Error handling for quota exceeded (10,000 units/day)
- [ ] Retry for transient API errors
- [ ] Signed off

### Known Issues
- **B6.1** — Thumbnail set has no retry for 5xx errors. YouTube API occasionally returns 503 on thumbnail set.
- YouTube API quota: each upload ~1,600 units + thumbnail. At 2 songs + 1 short = ~4,800 units. ~48% of daily quota used per night.
- OAuth token refresh happens automatically but requires `youtube-oauth-token.json` to exist on disk.

---

## Stage H: Notification + Sync + Log

| Property | Detail |
|----------|--------|
| **Input** | YouTube URLs + `song_results` + `songs_dir` |
| **Output** | Telegram message (batch MP3 + lyrics), D-drive file sync, log entry |
| **CLI** | `python3 scripts/nightly_music.py --date X --stage notify` |
| **Runtime** | ~30s |
| **Depends on** | Stage G (needs YouTube URLs) |
| **Parallelizable** | No |

### Validation

```
[STAGE H] telegram: sending batch notification...
[STAGE H]   Hero: {title} → https://youtu.be/{id} (18:00 SGT)
[STAGE H]   Standard: {title} → https://youtu.be/{id} (20:00 SGT)
[STAGE H] telegram: sendMediaGroup (2 MP3 + 2 TXT) → OK
[STAGE H] sync: output/YYYY-MM-DD/ → /mnt/d/Hermes/... (rsync)
[STAGE H] log: appended to logs/song-log-2026-05.json
[STAGE H] PASS: all notifications sent + synced + logged
```

### Test
```bash
# Test Telegram notification standalone:
python3 -c "
from minimax_music_api import send_telegram
send_telegram(
    songs_dir='/tmp/test-output',
    youtube_urls={'hero': 'https://youtu.be/test123'},
    bot_token='...',
    chat_id='...'
)"
# Expected: Telegram message with video link + media group

# Test log entry:
python3 -c "
from nightly_music import append_log
append_log({
    'date': '2026-05-14',
    'songs': [{'title': 'Test', 'score': 7.5, 'youtube_url': '...'}]
})"
# Expected: entry appended to logs/song-log-2026-05.json
```

### Status
- [ ] Stage CLI stub in main pipeline
- [ ] Telegram notification (video links per tier)
- [ ] Telegram `sendMediaGroup` (batch MP3 + lyrics TXT files)
- [ ] D-drive file sync (rsync or cp to `/mnt/d/Hermes/...`)
- [ ] Log entry to monthly song-log JSON
- [ ] Log rotation (monthly files)
- [ ] Error handling (Telegram API failure is non-fatal)
- [ ] Signed off

### Known Issues
- Telegram file size limit (50MB). MP3 files are typically <15MB so this is fine.
- D-drive sync path must be configured in `nightly-music.yaml`.

---

## Stage I: Weekly Compilation (Sunday only)

| Property | Detail |
|----------|--------|
| **Input** | 7 days of `viz.mp4` files (Mon-Sat Hero videos) |
| **Output** | `compilation.mp4` → YouTube upload |
| **CLI** | `python3 scripts/nightly_compilation.py --week-start 2026-05-11` |
| **Runtime** | ~600s (FFmpeg concat with re-encode fallback) |
| **Depends on** | Stage E (7 days' worth of Hero viz.mp4 files) |
| **Parallelizable** | No |

### Validation

```
[STAGE I] nightly_compilation: building weekly compilation...
[STAGE I]   week: Mon 2026-05-11 – Sat 2026-05-16
[STAGE I]   found: 6/6 Hero videos (Mon ✓ Tue ✓ Wed ✓ Thu ✓ Fri ✓ Sat ✓)
[STAGE I]   concat: ffmpeg -f concat ... (re-encode fallback: no)
[STAGE I]   output: compilation.mp4 ({N}s, 1920×1080)
[STAGE I]   chapters: Mon:0:00, Tue:3:30, Wed:7:15, ...
[STAGE I] PASS: compilation uploaded + scheduled for Sunday
```

### Test
```bash
# Dry-run: list videos that would be included
python3 scripts/nightly_compilation.py \
  --week-start 2026-05-11 \
  --dry-run
# Expected: list of 6 Hero video paths + total duration

# Full test (with output):
python3 scripts/nightly_compilation.py \
  --week-start 2026-05-11 \
  --output /tmp/stage-i-test.mp4
# Expected: compilation.mp4 with chapter markers
# Verify: ffprobe /tmp/stage-i-test.mp4 (duration = sum of 6 songs)
```

### Status
- [ ] Stage CLI stub in main pipeline
- [ ] Sunday-only guard (skip if not Sunday)
- [ ] Hero video discovery (Mon-Sat from `output/` directories)
- [ ] FFmpeg concat (lossless stream copy)
- [ ] Re-encode fallback for codec mismatch
- [ ] Chapter markers (ffprobe duration probe per video)
- [ ] Compilation metadata (title: "Weekly Compilation W${week}")
- [ ] Compilation upload to YouTube (with different description template)
- [ ] Missing day handling (skip missing days gracefully)
- [ ] Tested with partially-empty week (1-6 videos)
- [ ] Signed off

### Known Issues
- FFmpeg concat fails silently when only 1-2 videos found. Minimum threshold (≥3) should be enforced.
- Chapter marker accuracy depends on ffprobe duration probe — floating-point drift over 6 videos may compound.

---

## Overall Progress

| Stage | Name | CLI | Status | Bugs | Validated |
|-------|------|-----|--------|------|-----------|
| A | Fetch + Dedup | `--stage fetch` | ⬜ | — | ⬜ |
| B | Song Gen | `--stage gen` | ⬜ | B2.1 | ⬜ |
| C | Quality Gate | `--stage quality` | ⬜ | — | ⬜ |
| D | Assets | `--stage assets` | ⬜ | B4.1 | ⬜ |
| E | Visualizer + SRT | `--stage viz` | ⬜ | B1.1 | ⬜ |
| F | Shorts | `--stage shorts` | ⬜ | — | ⬜ |
| G | YouTube Upload | `--stage upload` | ⬜ | B6.1 | ⬜ |
| H | Notify + Sync | `--stage notify` | ⬜ | — | ⬜ |
| I | Compilation | `--stage compile` | ⬜ | — | ⬜ |

## Bug Tracker

| ID | Stage | Bug | Severity | Status |
|----|-------|-----|----------|--------|
| B1.1 | E | **SRT timing drift** — evenly-distributed lines mean early lines overrun duration, late lines truncated. Whisper forced alignment deferred. | Medium | ⬜ |
| B2.1 | B | **MiniMax API timeout** — no retry wrapper. Single API call failure kills entire song gen. | High | ⬜ |
| B4.1 | D | **Pollinations.ai transient failures** — ~5-10% of requests return 5xx or empty response. No retry mechanism. | Medium | ⬜ |
| B6.1 | G | **Thumbnail set has no retry** — YouTube API 503 on thumbnail set causes partial upload (video OK, no thumbnail). | Low | ⬜ |

## Changelog

- **2026-05-14**: Document created, initial stage definitions aligned with WORKFLOW-pipeline-phase2.md
