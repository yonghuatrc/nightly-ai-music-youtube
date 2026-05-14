# Design: ManggoMusicCH — Nightly AI Music YouTube Channel

> **Status**: Current. Phase 2 shipped 2026-05-14. Pipeline generates 0-2 quality-gated songs nightly, uploads to YouTube with mood-colored visualizers, SRT subtitles, Shorts clips, and Sunday compilation albums.
>
> Old pre-implementation design doc backed up as `DESIGN.md.old` (2026-05-12 office-hours draft).

---

## Overview

ManggoMusicCH is an autonomous YouTube music channel that publishes AI-generated Chinese pop songs daily. No human touch between 2am cron trigger and YouTube publish — the entire pipeline is self-contained, quality-gated, and instrumented.

**The problem**: AI music channels on YouTube post raw MP3s with no visualizer, inconsistent quality, and no branding. They don't build an audience because there's no channel experience.

**The solution**: A nightly pipeline that generates 2 songs, scores them on 5 quality dimensions, rejects weak ones, produces mood-colored waveform visualizers with synced lyrics, generates Shorts clips, uploads on a staggered schedule, and compiles weekly albums — all while being transparent about AI origin.

**The bet**: Consistent daily uploads with professional visualizers and a cohesive channel identity will outpace the status quo of sporadic, low-effort AI music uploads.

---

## Architecture Decisions

All 20 decisions, annotated by phase.

| # | Decision | Choice | Phase |
|---|----------|--------|-------|
| 1 | YouTube OAuth | One-time manual consent → auto-refresh token. Token at `/mnt/d/Hermes/secrets/`. | 1 |
| 2 | Bug fix sequencing | Fixed all 10 known bugs (retry, idempotency, lazy-load, dedup) before building YouTube. | 1 |
| 3 | Module structure | Monolithic `nightly_music.py` orchestrator with inline hooks. NOT multi-agent. | 1 |
| 4 | Upload timing | Cron generates at 2am SGT; YouTube API schedules publish for 6pm SGT (peak hours). | 1 |
| 5 | Dedup | Integrated into `fetch_trending.py` — checks last 7 days via `check-duplicate.py` before generation. | 1 |
| 6 | Telegram delivery | `sendMediaGroup` for batch MP3 + lyrics delivery to monitoring channel. | 1 |
| 7 | Log rotation | Monthly files: `logs/song-log-YYYY-MM.json`. Isolates corruption per month. | 1 |
| 8 | Test strategy | Regression test suite (CI on push). Unit tests deferred — pipeline is IO-heavy, not logic-heavy. | 1 |
| 9 | Parallel generation | Sequential 2 songs. MiniMax API handles 2 async internally; Python parallelism adds no benefit here. | 1 |
| 10 | GitHub repo | `github.com/yonghuatrc/nightly-ai-music-youtube` | 1 |
| 11 | File consolidation | All project files in one folder — no scattered scripts across the filesystem | 1 |
| 12 | Secrets location | `/mnt/d/Hermes/secrets/youtube-oauth*.json` + `~/.hermes/.env` for MiniMax/Telegram keys | 1 |
| 13 | Python environment | Venv at `~/.hermes/venv/` (Python 3.12.3). Not global pip. | 1 |
| 14 | Phase 2 strategy | **NOT multi-agent.** Quality-gated monolithic pipeline. Multi-agent was over-engineering for 2 songs. | 2 |
| 15 | Song count stays at 2 | Quality gate determines effective output (0-2/day). More songs ≠ more growth. Quota-safe at 2. | 2 |
| 16 | Weekly compilation | FFmpeg concat of Mon-Sat Hero videos on Sunday. Chapter markers from ffprobe duration probe. | 2 |
| 17 | Mood detection | Rule-based keyword scoring from lyrics (title 2x weight) + optional weekly theme boost. 7 palettes. | 2 |
| 18 | SRT subtitles | Full-song timed subtitles via FFmpeg `subtitles=` filter. All lyric lines distributed evenly across duration. | 2 |
| 19 | Shorts duration | 30s (reduced from 45s). Higher retention rate for Shorts algorithm. | 2 |
| 20 | Staggered upload | Hero video at 18:00 SGT, Standard at 20:00 SGT. Shorts at 12:00 SGT (separate upload window). | 2 |

**What was considered but rejected**:
- **Multi-agent coordinator** (Approach B from old design): Would need agent orchestration, inter-agent state management, and per-agent retry logic. The entire pipeline is ~600 lines of orchestration in `nightly_music.py` — a coordinator agent would add 2x complexity for zero throughput benefit at 2 songs/night.
- **10 songs/day**: YouTube API quota caps at 10,000 units/day. Each upload is ~1,600 units + thumbnail. 10 songs would consume 80%+ of quota with zero room for error. Also, flooding a new channel with 10 uploads/day hurts algorithmic growth (YouTube treats new channels cautiously).
- **Animated visualizers** (moviepy): Deferred. SRT subtitles + mood colors had higher ROI per engineering hour. Moviepy adds rendering time, FFmpeg reliability, and CJK font complexity that wasn't justified.

---

## Pipeline Flow (Current)

```
CRON 2am SGT
   │
   ▼
nightly_music.py --date YYYY-MM-DD
   │
   ├── 1. Load config (config/nightly-music.yaml)
   │      └── song_count, quality_gate thresholds, youtube settings, themes
   │
   ├── 2. Create daily output directory (output/YYYY-MM-DD/)
   │
   ├── 3. Fetch trending songs (fetch_trending.py)
   │      ├── QQ Music hot chart
   │      ├── KKBOX Chinese chart
   │      └── MyFM chart
   │      └── Dedup against last 7 days (check-duplicate.py)
   │
   ├── 4. Apply weekly theme (weekly_themes.py)
   │      └── Inject day-of-week mood into song prompts
   │         (Mon=upbeat, Tue=melancholy, ..., Sun=calm)
   │
   ├── 5. Generate songs via MiniMax API (minimax_music_api.py)
   │      ├── Song 1 → MP3 + TXT (lyrics) → output/YYYY-MM-DD/01-*.mp3
   │      └── Song 2 → MP3 + TXT (lyrics) → output/YYYY-MM-DD/02-*.mp3
   │
   ├── 6. Score song quality (song_quality.py)
   │      ├── 5 dimensions (lyrics_length 30%, chorus 25%, duration 20%,
   │      │                  placeholder_check 15%, vocabulary 10%)
   │      ├── Hero ≥ 6.0 → full treatment, 18:00 slot
   │      ├── Standard ≥ 4.0 → basic treatment, 20:00 slot
   │      └── Reject < 4.0 → dropped, no upload (logged + telegram alert)
   │
   ├── 7. Generate image prompt from lyrics (prompt_gen.py)
   │      ├── Priority 1: MiniMax M2.7 LLM chat (via mmx CLI)
   │      ├── Priority 2: Pollinations.ai text endpoint
   │      └── Priority 3: Rule-based keyword fallback
   │      └── Enforces: no people, no faces, no text
   │
   ├── 8. Download background image (image_gen.py)
   │      ├── Pollinations.ai (free, no API key)
   │      ├── FLUX model, 1920x1080 for visualizer background
   │      ├── 15s rate limit between requests
   │      └── Also generates: 1280x720 thumbnail (Pillow resize)
   │
   ├── 9. Detect mood from lyrics (nightly_visualizer.py)
   │      ├── Score 7 moods by keyword frequency
   │      ├── Title keywords weighted 2x
   │      └── Weekly theme mood gets +2 boost
   │
   ├── 10. Generate long-form visualizer (nightly_visualizer.py)
   │       ├── FFmpeg drawtext overlay (CJK via wqy-zenhei font)
   │       ├── Mood-colored waveform (from MOOD_PALETTES)
   │       ├── SRT subtitle burn-in via `subtitles=` filter
   │       └── Output: 01-*-viz.mp4 (1920x1080, ~90-120 MB)
   │
   ├── 11. Generate Shorts clip (nightly_visualizer.py)
   │       ├── FFmpeg crop from center of visualizer (1080x1920, 9:16)
   │       ├── Duration: 30s (was 45s, reduced for retention)
   │       └── Output: 01-*-short.mp4
   │
   ├── 12. Upload to YouTube (nightly_uploader.py)
   │       ├── Hero → scheduled 18:00 SGT
   │       ├── Standard → scheduled 20:00 SGT
   │       └── Shorts → scheduled 12:00 SGT
   │       └── SEO description + 16 tags + thumbnail
   │       └── OAuth auto-refresh (no manual re-auth)
   │
   ├── 13. Log to song-log-YYYY-MM.json (monthly rotation)
   │       └── Includes: scores, verdict, video_id, youtube_url, duration
   │
   └── 14. Telegram delivery
           ├── sendMediaGroup: MP3 + lyrics preview
           └── Summary: scores, youtube links, quality verdicts
                │
                ▼
        SUNDAY ONLY: nightly_compilation.py
                │
                ├── Verify today is Sunday (weekday() == 6)
                ├── Get Mon-Sat dates for current week
                ├── Collect Hero videos (01-*-viz.mp4) from each day
                ├── Generate compilation thumbnail (FFmpeg color + drawtext)
                ├── FFmpeg concat with re-encode (libx264 + aac)
                ├── Generate chapter timestamps (ffprobe per-video duration)
                ├── Upload to YouTube (album-style title, chapter descriptions)
                └── Cleanup: delete individual compilation source MP4s
```

---

## Phase 1 — Foundation (Deployed 2026-05-12)

Phase 1 took the existing MiniMax API + Telegram pipeline and added YouTube infrastructure. Delivered in a single day after fixing 10 pre-existing bugs.

### What was built

| Module | Lines | Purpose |
|--------|-------|---------|
| `nightly_visualizer.py` | ~1050 | FFmpeg waveform visualizer with CJK album art overlay. Generates 1920x1080 MP4 from MP3 + background image. Initial static color scheme `#FF6B6B|#4ECDC4`. |
| `nightly_uploader.py` | ~350 | YouTube Data API v3 wrapper. OAuth auto-refresh via google-auth. Schedule upload with `publishAt`. SEO descriptions with 16 tags. Thumbnail upload. |
| `fetch_trending.py` | ~500 | Multi-source trending song fetcher (QQ Music, KKBOX, MyFM). Random selection + style extraction. |
| `check-duplicate.py` | ~100 | 7-day dedup checker — compares song titles against recent song log. Prevents same-song re-generation. |
| `minimax_music_api.py` | ~200 | MiniMax music-2.6 API wrapper. Async generation with lyrics. Retry logic for API failures. |

### Key decisions in Phase 1

- **YouTube OAuth was one-time setup** — not a recurring problem. Manual browser consent → auto-refresh token file. Tested and working.
- **YouTube quota budget**: Each upload costs ~1,600 units (video insert + thumbnail set). 2 songs = 3,200/10,000 units (32%). Leaves room for Shorts and compilation uploads.
- **Static visualizer colors** (`#FF6B6B|#4ECDC4`): Coral and teal as placeholder. Phase 2 would replace this with mood-based palettes.
- **No animated visualizers**: moviepy adds rendering time, CJK font complexity, and dependency weight. FFmpeg drawtext was faster, more reliable, and already available in WSL.
- **SEO descriptions**: Generated from song metadata. Include lyrics snippet, trending attribution, AI origin disclosure, 16 tags, call-to-action, and playlist links.
- **Thumbnails** initially: Pollinations.ai per-song thumbnails (1280x720). Phase 2 improved this with LLM-generated prompts.

### What Phase 1 did NOT have

- No quality gating (any generated song was uploaded)
- No mood-based colors (static coral/teal always)
- No SRT subtitles (no lyrics on video)
- No Shorts
- No staggered scheduling (all at 18:00 SGT)
- No weekly themes
- No compilation albums
- No per-song background images (single default background)

---

## Phase 2 — Quality Pipeline (Shipped 2026-05-14)

Phase 2 was planned as "multi-agent coordinator" (Approach B in the old design doc) but was executed as a **quality-gated monolithic pipeline** — same orchestrator, new utility modules. Four sprints, all shipped same day.

### Why Not Multi-Agent

The old design proposed a coordinator agent + sub-agents (Music Gen, Visualizer, YouTube Uploader, Growth Agent). This was rejected during implementation because:

1. **Over-engineering for 2 songs**: Agent orchestration frameworks add message passing, state management, retry queues, and health checks. The pipeline is `nightly_music.py` → sequential function calls. Adding agents would 2x the code for zero reliability gain.
2. **Single point of failure either way**: Whether you have one orchestrator or five agents, if MiniMax API is down at 2am, you get no songs. No architecture pattern fixes that without a fallback generation provider.
3. **Debugging complexity**: A failing agent in the middle of the night leaves orphan state. A failing function call leaves a stack trace. Monolithic is easier to debug at 3am.
4. **Future-proofing**: If we scale to 10+ songs with parallel visualizers, we'll modularize then. YAGNI.

### What Phase 2 Actually Built

Instead of agents, Phase 2 added standalone utility modules that `nightly_music.py` imports directly — same orchestration, richer capabilities.

---

### Sprint 1: Quality Gate + Mood + SRT

**Quality gate** (`song_quality.py`, 218 lines)

5-dimension scoring with configurable thresholds:

| Dimension | Weight | Score 10 | Score 6-7 | Score 3-4 | Score 0 |
|-----------|--------|----------|-----------|-----------|---------|
| Lyrics length | 30% | ≥200 chars | ≥100 chars | ≥50 chars | <50 chars |
| Has chorus | 25% | `[Chorus]` marker OR repeated 3-line/2-line chunks | — | — | No chorus |
| Duration | 20% | 120-210s | 90-120s | 60-90s | <60s |
| Placeholder check | 15% | No placeholder text | — | — | Starts with "[Auto-generated..." |
| Vocabulary richness | 10% | ≥50% unique words | — | — | 0% (empty) |

Verdict thresholds (from config):
- **Hero** ≥ 6.0: Full treatment, premium 18:00 slot, compilation inclusion
- **Standard** ≥ 4.0: Basic treatment, 20:00 slot, no compilation
- **Reject** < 4.0: Not uploaded, logged, Telegram alert

Lyrics floor: If `lyrics_length` score is 0 AND total text < 50 chars, score is capped at 4.0 (standard max). This prevents near-empty lyrics from reaching hero tier.

**Mood colors** (in `nightly_visualizer.py`)

7 hardcoded color palettes replacing the static `#FF6B6B|#4ECDC4`:

| Mood | Palette | Colors |
|------|---------|--------|
| Romantic | `#FF6B6B\|#FF9F9F\|#FFD4D4` | Pinks |
| Melancholy | `#4A90D9\|#6A5ACD\|#2F4F7F` | Blues |
| Upbeat | `#FFD700\|#FF8C00\|#FF6347` | Warm bright |
| Calm | `#98D8C8\|#7EC8E3\|#B8E6D0` | Pastels |
| Energetic | `#FF3366\|#FF6633\|#FFCC00` | Vibrant |
| Sad | `#708090\|#4A5568\|#2D3748` | Greys |
| Chill | `#A29BFE\|#6C5CE7\|#DDA0DD` | Purple/lavender |

Detection: Rule-based keyword scoring. Title matches weighted 2x, lyrics matches 1x, weekly theme mood gets +2 boost. Fallback chain: detected mood → theme mood → `"chill"`.

**SRT subtitles** (in `nightly_visualizer.py`)

Full-song timed subtitles via FFmpeg `subtitles=` filter:
- All non-structure lyric lines (no `[Verse]`, `[Chorus]` markers) distributed evenly across song duration
- Each subtitle displays for `duration / num_lines` seconds
- Rendered via FFmpeg's built-in subtitle renderer (no external player needed)
- CJK font path auto-detected via `_find_cjk_font()` (searches wqy-zenhei, Noto Sans CJK, etc.)
- Font embedded in subtitle render path for consistent rendering across systems
- Output: `01-*-viz.mp4` with subtitles burned in (not soft subtitles)

---

### Sprint 2: Staggered Schedule + 30s Shorts + Weekly Themes

**Staggered upload schedule** (in `nightly_music.py` + `nightly_uploader.py`):

| Tier | Publish Time (SGT) | Includes |
|------|-------------------|----------|
| Hero | 18:00 | Long-form visualizer + Shorts + thumbnail + SEO |
| Standard | 20:00 | Long-form visualizer + thumbnail (no Shorts) |
| Rejected | — | Not uploaded, logged only |

Hero videos get the 18:00 slot for peak evening viewing. Standard goes at 20:00 as a secondary slot. Shorts are uploaded separately at 12:00 SGT for the lunchtime scroll window.

**30s Shorts** (config change in `nightly-music.yaml`):
- Original Shorts duration: 45s
- Changed to: 30s (higher completion rate → algorithmic boost)
- Generated via FFmpeg: crop 1080x1920 from center of long-form visualizer, trim to 30s from start
- Uploaded separately from long-form with `#Shorts` tag in privacy settings

**Weekly themes** (`weekly_themes.py`, 74 lines):

| Day | Emoji | Mood | Style | Keywords |
|-----|-------|------|-------|----------|
| Mon | 🌅 | upbeat | 正能量华语流行 | 开工,向上,阳光,希望,奋斗 |
| Tue | 💔 | melancholy | R&B抒情慢歌 | 思念,深夜,回忆,遗憾,错过 |
| Wed | 💌 | romantic | 华语浪漫情歌 | 爱,心动,告白,温柔,甜蜜 |
| Thu | 🌧️ | sad | 华语伤感抒情 | 雨,泪,离别,心痛,孤独 |
| Fri | 🎉 | energetic | 华语流行舞曲 | 周末,狂欢,自由,快乐,释放 |
| Sat | 🌟 | chill | 华语治愈民谣 | 星空,宁静,温暖,放松,治愈 |
| Sun | 🌙 | calm | 华语轻柔安眠 | 晚安,梦境,温柔,月光,安宁 |

Theme injection:
- Song 1 (Hero): Full style + keywords injection into prompt (strongly themed)
- Song 2 (Standard): Just mood keyword (more subtle)
- Config toggle: `themes.enabled: true` in `nightly-music.yaml`

---

### Sprint 3: Per-Song Backgrounds + Compilation

**Prompt generation** (`prompt_gen.py`, 209 lines):

3-tier fallback chain:
1. **MiniMax M2.7 LLM** (via `mmx` CLI): Sends system prompt + lyrics excerpt → receives Chinese scene description with English technical params
2. **Pollinations.ai text endpoint**: Free fallback if MiniMax CLI is unavailable
3. **Rule-based fallback**: Extracts mood keywords from lyrics → constructs prompt with detected colors + aspect ratio + Chinese aesthetic elements

All tiers enforce:
- No people, no faces, no text in generated images
- Chinese aesthetic elements (misty mountains, pavilions, bamboo, plum blossoms)
- Cinematic quality specification
- Aspect ratio appropriate for use case (landscape 16:9 for visualizer, 9:16 for Shorts)

**Image generation** (`image_gen.py`, 339 lines):

Pollinations.ai wrapper with:
- Rate-limited download: minimum 15-second gap between requests (Pollinations is a free service, no SLA)
- FLUX model (default), 1920x1080 for backgrounds, 1280x720 for thumbnails
- Content type validation (reject non-image responses)
- File size validation (reject <5KB — likely generation failure)
- Preset generators: `generate_channel_logo()`, `generate_channel_banner()`, `generate_thumbnail()`, `generate_default_background()`
- Thumbnail generation via Pillow resize (not a second API call)

**Weekly compilation** (`nightly_compilation.py`, 710 lines):

Sunday-only workflow:
1. Verify today is Sunday (weekday() == 6) — skip if not
2. Get Mon-Sat dates for current week
3. Scan each day's `output/YYYY-MM-DD/` for `01-*-viz.mp4` (Hero videos only)
4. Minimum 2 videos required — skip if fewer
5. Generate compilation thumbnail via FFmpeg `color=c=#1a1a2e` + `drawtext` overlay
6. FFmpeg concat via concat demuxer with re-encode (`libx264` + `aac`, CRF 23)
7. Chapter markers via ffprobe duration probes — formatted as YouTube timestamps in description
8. Upload with album-style title: `"🎵 ManggoMusicCH Weekly — Week of [Month] [Day]"`
9. Cleanup: Delete individual source MP4s after successful upload
10. Configurable via `compilation.enabled`, `compilation.max_duration_min: 45`

---

### Sprint 4: Bug Fixes + E2E Regression

Three ordering bugs found during integration testing:

| Bug | Symptom | Root Cause | Fix |
|-----|---------|------------|-----|
| B1 | Background generated AFTER visualizer | `generate_background_image()` was called after `generate_visualizer()` in the pipeline sequence | Moved background generation before visualizer: assets must exist before FFmpeg can use them |
| B2 | `background_image=None` passed to visualizer | Visualizer function signature accepted optional `background_image` arg, but pipeline called it without passing the downloaded path | Pipeline now passes `background_image` from `generate_background_image()` return value directly |
| B3 | Thumbnail double-generated | Pipeline was calling both `generate_thumbnail_from_bg()` (Pillow) AND an old standalone thumbnail API call | Removed standalone thumbnail call. Thumbnail now uses Pillow-only resize from the background image |

E2E regression: Full dry-run pipeline test after fixes confirmed all 7 steps complete without errors.

---

## Project Structure (Current)

```
nightly-ai-music-youtube/
│
├── scripts/
│   ├── nightly_music.py              # Pipeline orchestrator (1324 lines)
│   ├── nightly_visualizer.py         # FFmpeg visualizer + SRT + mood colors + Shorts (1050 lines)
│   ├── nightly_uploader.py           # YouTube Data API v3 + OAuth (350 lines)
│   ├── nightly_compilation.py        # Sunday weekly album concat (710 lines)
│   ├── song_quality.py               # 5-dimension quality scoring (218 lines)
│   ├── weekly_themes.py              # Day-of-week mood modifiers (74 lines)
│   ├── prompt_gen.py                 # LLM image prompt from lyrics (209 lines)
│   ├── image_gen.py                  # Pollinations.ai image download (339 lines)
│   ├── minimax_music_api.py          # MiniMax API wrapper (music 2.6) (200 lines)
│   ├── fetch_trending.py             # QQ Music / KKBOX / MyFM fetcher (500 lines)
│   └── check-duplicate.py            # 7-day dedup helper (100 lines)
│
├── config/
│   └── nightly-music.yaml            # All settings: song count, quality gate, themes, compilation
│
├── assets/
│   ├── branding/
│   │   ├── logo.png                  # Channel profile pic (1024x1024, Pollinations FLUX)
│   │   └── banner.png                # Channel banner (2560x1440)
│   └── backgrounds/
│       └── default-dark.jpg          # Fallback background (Phase 1)
│
├── output/
│   └── YYYY-MM-DD/                   # Per-night generation output
│       ├── 01-title.mp3              # Audio (Song 1)
│       ├── 01-title.txt              # Lyrics (Song 1)
│       ├── 01-title-viz.mp4          # Visualizer video (Song 1, long-form)
│       ├── 01-title-short.mp4        # YouTube Shorts (Song 1, 30s)
│       ├── 01-title-thumb.jpg        # Thumbnail (Song 1)
│       └── 01-title.srt              # Subtitle file (Song 1)
│       ├── 02-title.mp3              # Audio (Song 2, if generated)
│       ├── ...
│       └── compilation-YYYY-MM-DD-to-YYYY-MM-DD.mp4  # Sunday only
│
├── logs/
│   ├── nightly_music.log             # Cron output log (rotates with system logrotate)
│   └── song-log-YYYY-MM.json         # Monthly song log (rotation)
│
├── docs/
│   ├── GROWTH_STRATEGY.md            # 500-sub growth plan
│   ├── CHANNEL_ABOUT.md              # YouTube About section content
│   └── WORKFLOW-pipeline-phase2.md   # Phase 2 workflow specification
│
├── DESIGN.md                         # This file. Design and decisions.
├── EXECUTION_PLAN.md                 # Phase 1 execution tracker
├── README.md                         # Project overview and usage
├── Phase2_Issues.md                  # Phase 2 issue backlog (historical)
├── Phase2_ARCHITECTURE.md            # Phase 2 architecture reference (historical)
├── AGENT_EXECUTION_PLAN.md           # Agent-facing execution plan
├── Project_Instruction.md            # Original project specification
├── .env.example                      # Template (actual secrets in ~/.hermes/.env)
└── .gitignore
```

---

## Dependencies

| Dependency | Type | Purpose | Status |
|------------|------|---------|--------|
| MiniMax API key | Required | Music generation (music-2.6) and LLM prompt gen | ✅ In `~/.hermes/.env` |
| Telegram bot token | Required | Monitoring channel delivery | ✅ In `~/.hermes/.env` |
| FFmpeg ≥6.1.1 | Required | Visualizer, SRT burn-in, Shorts crop, compilation concat | ✅ WSL apt |
| Google Cloud Project | Required | YouTube Data API v3 | ✅ Created, API enabled |
| YouTube Data API v3 | Required | Upload + schedule + thumbnail | ✅ 10,000 units/day quota |
| YouTube OAuth token | Required | Auto-refresh via google-auth library | ✅ `/mnt/d/Hermes/secrets/youtube-oauth-token.json` |
| wqy-zenhei font | Required | CJK text in FFmpeg drawtext + subtitles | ✅ apt `fonts-wqy-zenhei` |
| Pollinations.ai | Required (free) | Background images + thumbnails | ✅ No key, 15s rate limit |
| mmx CLI | Required (Phase 2) | MiniMax LLM for prompt generation | ✅ `/home/dennis/.hermes/node/bin/mmx` |
| Pillow (PIL) | Required (Phase 2) | Thumbnail resize from background | ✅ `python3 -m pip install Pillow` |
| google-auth + google-api-python-client | Required | YouTube OAuth + upload | ✅ In venv |
| PyYAML | Required | Config file parsing | ✅ In venv |
| requests | Required | HTTP for Pollinations.ai + MiniMax API | ✅ In venv |

---

## What We Didn't Build (and Why)

| Feature | Status | Reason |
|---------|--------|--------|
| **Multi-agent coordinator** | Rejected | Over-engineering for 2 songs. Monolithic orchestrator is 600 lines of sequential calls. Adding agents would 2x complexity for zero reliability gain. |
| **10 songs/day** | Rejected | YouTube quota (10K units/day) limits to ~5-6 songs max. Also, flooding a new channel hurts algorithmic growth. 2 songs is optimal for Phase 1-2. |
| **Animated moviepy visualizers** | Deferred | SRT + mood colors had higher ROI. Moviepy would add rendering time, font complexity, and a new dependency. FFmpeg drawtext is faster and more reliable. |
| **Growth agent** | Deferred | Manual analytics review for now. No automated cross-posting to Twitter/Bilibili. Will revisit at 500 subs. |
| **Unit test suite** | Deferred | Pipeline is IO-heavy (API calls, FFmpeg subprocesses, file I/O). Unit tests would mock everything and test little. Regression test suite covers end-to-end integration. |
| **Multiple language support** | Deferred | Chinese-only for now. English/multilingual prompts would split the audience on a new channel. |
| **Music video generation** | Deferred | Animated AI video (like Runway or Pika) per song would cost ~$0.10-0.50/song and add 10+ minutes per generation. Not viable at 2 songs/day for a non-monetized channel. |
| **Playlist management** | Deferred | YouTube Data API playlist management is available but adds complexity. Manual playlists for now. |

---

## Success Criteria

| Metric | Target | Status |
|--------|--------|--------|
| Subscribers (30 days from first video) | 500 | 🏃 Monitoring — first video live 2026-05-12 |
| Daily uploads | 1-2 per day | ✅ Quality-gated: 0-2 depending on scores |
| Successful generation rate | 28/30 days | ✅ Scoring + retry logic active |
| YouTube automation | Fully hands-off | ✅ Upload + schedule + thumbnail + tags all automated |
| Visualizer quality | Mood-colored + SRT | ✅ 7 palettes, full-song subtitles |
| Quality gate effectiveness | ≥80% of songs reach standard+ | 🔄 Needs data — first runs target May 15+ |
| Shorts completion rate | ≥60% at 30s | 🔄 Monitoring — reduced from 45s for retention |
| Weekly compilation (Sundays) | ≥4 videos per compilation | ✅ FFmpeg concat with chapter markers |
| Mood detection accuracy | ≥70% matches listener expectation | 🔄 Needs user feedback data |
| Pipeline reliability | ≤1 failure/week from code bugs | ✅ All known ordering bugs fixed (B1-B3) |

---

## What's Next

### Short-term (1-2 weeks)
- **Quality calibration**: Review real scoring data from first week of runs. Adjust thresholds if Hero rate is too low (<20%) or too high (>80%).
- **Mood detection tuning**: Compare detected mood against listener feedback for the first batch of songs. Adjust keyword weights if needed.
- **Subscriber growth monitoring**: Track daily subscriber counts. If growth is <5/day, adjust distribution strategy (Reddit posts, Twitter shares, playlist submission).

### Medium-term (2-4 weeks)
- **Growth agent**: Automate cross-posting to relevant subreddits and Twitter communities.
- **Playlist structure**: Create mood-based playlists (Romantic Collection, Upbeat Mix, Chill Vibes) from uploaded songs.
- **Community posts**: LLM-generated weekly recaps as YouTube Community posts.

### Long-term (1-3 months)
- **Animated visualizers**: Explore moviepy or Manim for lyric-kinetic typography videos.
- **Multiple languages**: Add English song descriptions and tags to capture international audience.
- **Monetization check**: At 1,000 subs / 4,000 hours (if ever), review AdSense eligibility.
- **Backup generation**: If MiniMax API has prolonged downtime, evaluate fallback providers (Suno, Udio).

---

## SRT Alignment — Next Improvement

### Current Limitation
SRT subtitles are generated by distributing lyrics lines evenly across sections (section-weighted timing). This works well for songs with uniform singing speed, but lines with natural variation (held notes, rushed phrases, instrumental pauses) will show timing drift.

### Solution: Whisper Forced Alignment
Use OpenAI Whisper (whisper.cpp or openai-whisper) to transcribe the generated MP3 audio, extract word-level timestamps, then align the lyrics to those timestamps to produce frame-accurate SRT.

### Implementation Plan

1. Install whisper.cpp or openai-whisper
2. Transcribe MP3 → get word-level timestamps (JSON with start/end per word)
3. Match transcribed words to our lyrics text (fuzzy match)
4. Generate SRT from matched timestamps
5. Replace the current `_generate_section_weighted_srt()` with the Whisper-based SRT

### Whisper Options

| Option | Install | Speed | Accuracy |
|--------|---------|-------|----------|
| **openai-whisper** (Python) | `pip install openai-whisper` | Slower (needs GPU) | ★★★★★ |
| **whisper.cpp** (C++) | `git clone` + `make` | Fast (CPU or GPU) | ★★★★★ |
| **faster-whisper** (CTranslate2) | `pip install faster-whisper` | Fastest (GPU) | ★★★★★ |

### RTX 3060 Ti Recommendation
Use **openai-whisper** with `model="medium"` for Chinese songs. On the RTX 3060 Ti (8GB VRAM), a 3-minute song takes ~10-15 seconds to transcribe.

### New Function Signature (to add in nightly_visualizer.py)
```python
def align_lyrics_with_whisper(mp3_path: str, lyrics: str) -> list[dict]:
    """
    Align lyrics text to audio using OpenAI Whisper transcription.
    
    Steps:
    1. Transcribe MP3 with Whisper (model="medium", language="zh")
    2. Get word-level segments with timestamps
    3. Match transcribed segments to our lyrics lines (fuzzy string match)
    4. Return list of {line, start_sec, end_sec} dicts
    
    Returns empty list if Whisper not installed or fails.
    Falls back to section-weighted SRT if alignment fails.
    """
```

### Integration
- Add optional dependency: `openai-whisper` (lazy import, graceful fallback)
- In `_generate_section_weighted_srt()`, try Whisper alignment first
- If Whisper unavailable or fails, fall back to current section-weighted logic
- Cache Whisper results so re-runs don't re-transcribe

### Config
```yaml
# In nightly-music.yaml
srt:
  alignment: "whisper"    # "whisper" | "section-weighted" | "uniform"
  whisper_model: "medium"  # tiny, base, small, medium, large
```

### Effort
~2-3 hours total: Install Whisper + build integration + test with 3 songs.

---

## Pipeline Evolution History

```
Phase 1 (2026-05-12):
  2 songs → static visualizer → YouTube (18:00 all) → Telegram
  Total modules: 6

Phase 2 (2026-05-14):
  2 songs → quality score → mood colors → SRT overlay → Shorts (30s)
  → staggered upload (Hero 18:00 / Standard 20:00 / Shorts 12:00)
  → weekly compilation (Sunday)
  Total modules: 11
```

**Key architectural insight**: The old design doc proposed Approach B (multi-agent) as Phase 2. What actually shipped was closer to Approach A (monolithic) with Approach B's feature set bolted on as utility modules. This was the right call — the pipeline is simple enough that a coordinator agent would be overhead without benefit. The quality gate, mood detection, SRT, and compilation features are all function calls in a 1,300-line orchestrator, not message-passing actors in a distributed system. Simpler is better when the entire pipeline runs in under 30 minutes on a single machine.
