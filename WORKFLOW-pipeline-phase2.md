# WORKFLOW: ManggoMusicCH Phase 2 Pipeline
**Version**: 1.0
**Date**: 2026-05-14
**Author**: Workflow Architect
**Status**: Review
**Supersedes**: Phase 1 pipeline (DESIGN.md §Pipeline Architecture)

## Overview

The nightly AI music pipeline is upgraded from a flat 2-song generate-and-upload to a quality-gated, mood-aware, thematically-themed content factory. Two songs per night are generated at 2am SGT, scored for quality, and elevated to **Hero** (top scorer) and **Standard** (second) with staggered YouTube publish times. Mood is extracted from lyrics to drive visualizer colors. Full SRT lyrics are burned into long-form videos. On Sundays, the week's videos are concatenated into a compilation album. Day-of-week themes modulate song prompt generation for variety and audience retention.

---

## Workflow Registry

### View 1: By Workflow

| Workflow | Spec file | Status | Trigger | Primary actor | Last reviewed |
|---|---|---|---|---|---|
| Phase 2 nightly pipeline | This document | Review | Cron 2am SGT | Pipeline orchestrator | 2026-05-14 |
| Weekly compilation | This document (§7) | Review | Cron 2am Sunday | Pipeline orchestrator | 2026-05-14 |
| Song quality gating | This document (§2) | Review | After generation | Quality scorer | 2026-05-14 |
| Mood detection + color mapping | This document (§4) | Review | After lyrics generation | Mood analyzer | 2026-05-14 |
| SRT lyrics generation (long-form) | This document (§3) | Review | After mood detection | SRT generator | 2026-05-14 |
| Staggered upload scheduling | This document (§5) | Review | Visualizer complete | Upload scheduler | 2026-05-14 |

**Deprecated**: Phase 1 pipeline (DESIGN.md) — replaced by Phase 2

### View 2: By Component

| Component | File(s) | Workflows it participates in |
|---|---|---|
| Pipeline orchestrator | `nightly_music.py` | All workflows (entry point) |
| MiniMax API wrapper | `minimax_music_api.py` | Song generation, lyrics generation |
| Visualizer | `nightly_visualizer.py` | Long-form visualizer, Shorts, SRT generation, mood colors |
| Uploader | `nightly_uploader.py` | YouTube upload, scheduling, thumbnail |
| Trending fetcher | `fetch_trending.py` | Song prompt generation, weekly themes |
| Dedup checker | `check-duplicate.py` | All generation workflows |
| Prompt gen | `prompt_gen.py` | Mood detection, image prompt generation |
| Image gen | `image_gen.py` | Per-song backgrounds, thumbnails |
| Config | `nightly-music.yaml` | All workflows (parameter source) |
| Weekly compilation (new) | `nightly_compilation.py` | Weekly compilation |

### View 3: By User Journey

| What the customer experiences | Underlying workflow(s) | Entry point |
|---|---|---|
| Hero song at 18:00 | Quality gating → Mood detection → Visualizer → Upload (18:00) | YouTube browse |
| Standard song at 20:00 | Same pipeline, second rank → Upload (20:00) | YouTube browse |
| Shorts preview at 12:00 | Song gen → Shorts (30s) → Upload (12:00) | YouTube Shorts |
| SRT lyrics on long video | SRT generation → FFmpeg subtitles filter | Long-form video play |
| Weekly compilation (Sunday) | Compilation trigger → Concat metadata → Upload | YouTube browse |
| Dynamic visualizer colors | Mood detection → Color mapping → FFmpeg waveform colors | Video appearance |
| Day-themed mood/genre | Weekly theme mapper → Prompt modifier → MiniMax gen | Song style |

### View 4: By State

| State | Entered by | Exited by | Workflows that can trigger exit |
|---|---|---|---|
| `generated` | MiniMax API success | → `scored`, `failed_gen` | Quality gating |
| `scored` | Quality scoring | → `accepted_hero`, `accepted_standard`, `rejected` | Quality gating |
| `accepted_hero` | Score >= hero_threshold | → `mood_detected`, `failed_mood` | Mood detection |
| `accepted_standard` | Score >= standard_threshold | → `mood_detected`, `failed_mood` | Mood detection |
| `rejected` | Score < standard_threshold | (terminal, skip) | — |
| `mood_detected` | Mood analysis complete | → `visualized`, `failed_viz` | Visualizer |
| `visualized` | FFmpeg MP4 generated | → `uploaded`, `failed_upload` | Upload |
| `uploaded` | YouTube API success | → `delivered` | Telegram delivery |
| `delivered` | Telegram sent | (terminal) | — |
| `failed_gen` | Generation exception | (terminal, log + notify) | — |
| `failed_mood` | Mood analysis failure | (terminal, use default colors) | — |
| `failed_viz` | FFmpeg failure | (terminal, retry or skip) | — |
| `failed_upload` | YouTube API failure | (terminal, retry next day) | — |

---

## Pipeline Flow Diagram

```
CRON 2am SGT
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│  STEP 0: LOAD CONFIG + WEEKLY THEME                          │
│    ├─ Load nightly-music.yaml                                 │
│    ├─ Determine day-of-week theme                             │
│    │   Mon=upbeat, Tue=melancholy, Wed=romantic,             │
│    │   Thu=sad, Fri=dance, Sat=chill, Sun=soft               │
│    └─ Inject theme into prompt template                       │
└──────────────────┬───────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────┐
│  STEP 1: FETCH TRENDING + DEDUP                              │
│    ├─ Fetch from sources (qq-douyin → kkbox → my-fm → pool) │
│    ├─ Dedup against last 7 days (check-duplicate.py)         │
│    └─ Select top 2 trending + apply theme modifier            │
└──────────────────┬───────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────┐
│  STEP 2: GENERATE 2 SONGS (MiniMax)                         │
│    ├─ Song 1: prompt + day-of-week theme                     │
│    ├─ Song 2: prompt + day-of-week theme                     │
│    └─ Each: lyrics → music → save MP3+TXT                    │
└──────────────────┬───────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────┐
│  STEP 3: QUALITY GATING                                      │
│    ├─ Score both songs (0-10)                                 │
│    ├─ Highest scorer → HERO   (needs ≥6/10)                  │
│    ├─ Second scorer  → STANDARD (needs ≥4/10)                │
│    ├─ If BOTH < 4 → SKIP DAY, alert via Telegram             │
│    └─ If Hero passes, Standard fails → Hero-only day          │
└─────┬────────────────────────────┬───────────────────────────┘
      │                            │
      ▼                            ▼
┌──────────────────┐   ┌──────────────────────┐
│  HERO ACCEPTED   │   │ STANDARD ACCEPTED    │
│  (quality ≥6)    │   │ (≥4 but <6 OR < hero)│
└──────┬───────────┘   └──────┬───────────────┘
       │                      │
       ▼                      ▼
┌──────────────────────────────────────────────────────────────┐
│  STEP 4: MOOD DETECTION (from lyrics)                       │
│    ├─ Analyze lyrics via MiniMax LLM (prompt_gen.py)        │
│    │   OR rule-based keyword fallback                        │
│    ├─ Map mood → color palette:                              │
│    │   Upbeat → warm coral+gold (#FF6B6B, #FFD93D)          │
│    │   Melancholy → cool blue+gray (#4ECDC4, #95D5B2)       │
│    │   Romantic → soft pink+amber (#FF9F9F, #FFC8A2)        │
│    │   Sad → deep blue+indigo (#6C63FF, #3F3D56)            │
│    │   Dance → neon+purple (#FF00FF, #00FFFF)               │
│    │   Chill → mint+teal (#7BC8A4, #98D4BB)                 │
│    │   Soft → pastel (#D4A5A5, #A8D5BA)                    │
│    └─ Output per-song: mood_label, color_primary, color_sec │
└─────┬────────────────────────────┬───────────────────────────┘
      │                            │
      ▼                            ▼
┌──────────────────┐   ┌───────────────────────────────────────┐
│  SRT GENERATION  │   │  PER-SONG BACKGROUND (Pollinations.ai)│
│  (full-length)   │   │  ├─ Landscape bg (1920x1080)          │
│  ├─ Parse lyrics  │   │  └─ Vertical bg (1080x1920)          │
│  │  into timed    │   └───────────┬───────────────────────────┘
│  │  segments      │               │
│  ├─ Distribute    │               ▼
│  │  evenly over   │   ┌───────────────────────────────────────┐
│  │  song duration │   │  SHORTS GENERATION (30s)              │
│  └─ Save .srt      │   ├─ Find loudest 30s segment            │
│         │          │   ├─ Generate SRT for 30s                │
│         │          │   ├─ Generate 9:16 MP4                   │
│         │          │   └─ Output: {song}-short.mp4            │
│         ▼          └───────────┬───────────────────────────────┘
│                              │
│   ┌──────────────────────────┘
│   │
▼   ▼
┌──────────────────────────────────────────────────────────────┐
│  STEP 5: LONG-FORM VISUALIZER (FFmpeg)                      │
│    ├─ Background: song-specific (Pollinations) or global     │
│    ├─ Waveform: mood-based colors (not static)               │
│   ╔═╪═══════════════════════════════════════════════════════╗ │
│   ║ │  SRT subtitle overlay via FFmpeg subtitles filter     ║ │
│   ║ │  (reuse same .srt from Step 4)                       ║ │
│   ╚═╪═══════════════════════════════════════════════════════╝ │
│    └─ Output: {song}-viz.mp4                                  │
└─────┬────────────────────────────┬───────────────────────────┘
      │                            │
      ▼                            ▼
┌──────────────────────────────────────────────────────────────┐
│  STEP 6: UPLOAD TO YOUTUBE (staggered)                      │
│    ├─ HERO: publish_at = 18:00 SGT                          │
│    │   metadata: "ManggoMusicCH 🥭 | {title}"               │
│    │   SEO: full description, mood tags                     │
│    ├─ STANDARD: publish_at = 20:00 SGT                      │
│    │   metadata: "{title}"                                   │
│    │   SEO: same template, shorter tags                     │
│    ├─ SHORTS (×2): publish_at = 12:00 SGT, 30s              │
│    └─ Upload thumbnails for each                             │
└──────────────────┬───────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────┐
│  STEP 7: SYNC → LOG → TELEGRAM                              │
│    ├─ Sync to D-drive                                        │
│    ├─ Log to song-log-YYYY-MM.json (with quality scores,     │
│    │   mood, hero/standard flags, color palette)             │
│    └─ Telegram delivery: MP3+lyrics + YouTube links          │
└──────────────────────────────────────────────────────────────┘

==================== SUNDAY-ONLY BRANCH ====================

CRON 2am SGT (only if day_of_week == Sunday)
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│  WEEKLY COMPILATION                                          │
│    ├─ Check: at least 2 videos exist from Mon-Sat            │
│    ├─ Create concat file list (FFmpeg concat demuxer)        │
│    ├─ Generate compilation thumbnail                         │
│    ├─ Generate compilation metadata (title, desc, chapters)  │
│    ├─ Run FFmpeg concat: 30-60 min MP4                      │
│    ├─ Upload to YouTube (publish_at = 18:00 Sunday)          │
│    ├─ Add to "Weekly Albums" playlist                        │
│    └─ Log + Telegram notification                            │
└──────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Workflow Tree

### STEP 0: Load Config + Weekly Theme

**Actor**: Pipeline orchestrator (`nightly_music.py`)
**Action**:
1. Load `nightly-music.yaml`
2. Determine `day_of_week` from `--date` parameter
3. Select weekly theme modifier based on day:
   - Monday: `upbeat` — 轻快活泼, 节奏明快
   - Tuesday: `melancholy` — 忧郁伤感, 深情
   - Wednesday: `romantic` — 浪漫温馨, 甜蜜
   - Thursday: `sad` — 悲伤凄美, 动情
   - Friday: `dance` — 舞曲节奏, 动感
   - Saturday: `chill` — 放松舒缓, 治愈
   - Sunday: `soft` — 柔和温暖, 宁静
4. Inject theme modifier into prompt generation templates
5. Set compilation flag: `is_sunday = (day_of_week == Sunday)`

**Timeout**: 5s
**Input**: `date_label: "YYYY-MM-DD"`
**Output on SUCCESS**: `{ theme: str, theme_modifier: str, is_sunday: bool }` → GO TO STEP 1
**Output on FAILURE**:
  - `FAILURE(config_missing)`: Config file not found → use defaults, proceed with theme=none
  - `FAILURE(invalid_date)`: --date not parseable → abort pipeline

**Observable states**:
  - Customer sees: N/A
  - Operator sees: Log `[nightly] Theme: upbeat (Monday)`
  - Database: N/A
  - Logs: `[nightly] Theme: {theme} ({day_name})`

---

### STEP 1: Fetch Trending + Dedup

**Actor**: Pipeline orchestrator + `fetch_trending.py` + `check-duplicate.py`
**Action**:
1. Call `fetch_trending.py` with configured sources (qq-douyin → kkbox → my-fm)
2. Dedup against last 7 days via `check-duplicate.py`
3. Pad from pool if needed
4. Apply **weekly theme modifier** to each selected style_prompt:
   - Append theme_modifier to the generated `style_prompt` string
   - e.g., `"类似周杰伦的《晴天》风格，华语流行抒情，钢琴为主，温暖男声，旋律朗朗上口，轻快活泼"` (Monday upbeat)
5. Select top 2 trending songs

**Timeout**: 60s total (30s fetch + 10s dedup + 20s pool)
**Input**: `sources: list[str], count: 2, theme_modifier: str`
**Output on SUCCESS**: `trending: list[2 dict]` → GO TO STEP 2
**Output on FAILURE**:
  - `FAILURE(no_songs)`: All sources + pool returned empty → ABORT — no songs to generate
  - `FAILURE(fetch_timeout)`: Subprocess timeout → retry once with pool only
  - `FAILURE(dedup_error)`: Dedup script failed (non-fatal) → proceed without dedup (log warning)

**Failure modes from existing implementation**:
  - Source fallback chain: qq-douyin → kkbox → my-fm → pool → abort
  - At pool level, always succeeds (25 hardcoded entries)

**Observable states**:
  - Customer sees: N/A
  - Operator sees: `[nightly] Using 2 trending songs` (or fallback warnings)
  - Database: N/A (logs only)
  - Logs: `[nightly] Themed prompts: {prompt1[:60]}...`

---

### STEP 2: Generate 2 Songs (MiniMax)

**Actor**: Pipeline orchestrator + `minimax_music_api.py`
**Action**:
For each of 2 trending songs:
1. Build prompt from trend data + weekly theme modifier
2. Call MiniMax lyrics API (step 1 of 2-step workflow)
3. Retry on placeholder lyrics (configurable: default 3 retries)
4. Call MiniMax music API (step 2) with retry on 429/5xx
5. Download MP3, save TXT lyrics
6. Small delay (2s) between songs

**Timeout**: 180s per song (60s lyrics + 120s music)
**Output on SUCCESS per song**: `song_result: { status: "success", title, mp3_path, txt_path, duration_sec, lyrics, ... }`
**Output on FAILURE per song**:
  - `FAILURE(placeholder_lyrics)`: All retries returned placeholder → accept anyway with placeholder warning
  - `FAILURE(music_api_error)`: HTTP 4xx/5xx after retries → mark song as `failed_gen`, continue to next song
  - `FAILURE(download_error)`: Audio download failed → same as music_api_error

**If BOTH songs fail**: → ABORT_UPLOAD (skip all downstream upload steps, Telegram alert only)

**Observable states**:
  - Customer sees: N/A
  - Operator sees: `[nightly] Generating song 1...` → `Song 1 OK — 180s, 5.2MB`
  - Database: N/A
  - Logs: `[nightly] Song 1 OK — {duration}s, {size}MB`

---

### STEP 3: Quality Gating ← NEW

**Actor**: Pipeline orchestrator (new `scorer` module or inline function)
**Action**:
For each successfully generated song:
1. Extract available quality signals:
   - `lyrics_length`: Total character count of lyrics (need ≥200 chars for good score)
   - `lyrics_placeholder_flag`: True if placeholder text detected
   - `duration_sec`: Song length in seconds (prefer 120-300s)
   - `section_count`: Number of [Verse]/[Chorus] sections in lyrics
   - `has_chorus`: True if lyrics contain [Chorus] marker
   - `lyrics_vocabulary`: Unique word count / total word ratio
2. Compute quality score 0-10:
   ```
   score = 10
   if lyrics_placeholder: score -= 4
   if lyrics_length < 200: score -= 3
   if lyrics_length < 100: score -= 5
   if duration_sec < 90: score -= 2
   if duration_sec > 360: score -= 1
   if section_count < 2: score -= 2
   if not has_chorus: score -= 1
   vocabulary_ratio = unique_words / total_words
   if vocabulary_ratio < 0.3: score -= 1  # too repetitive
   score = max(0, min(10, score))
   ```
3. Classify:
   - `score >= 6` → eligible for **HERO**
   - `score >= 4` → eligible for **STANDARD**
   - `score < 4` → **REJECTED** (skip song)
4. Assign roles:
   - Higher scorer → **Hero**
   - Lower scorer (if ≥4) → **Standard**
   - If tie or scores equal: randomly assign Hero/Standard
5. If BOTH < 4: → `ABORT_UPLOAD` — send failure Telegram, skip all upload steps
6. If Hero < 6 but Standard ≥ 4: → Standard becomes Hero (promote). Still upload.

**Timeout**: 5s per song
**Input**: `song_results: list[dict]`
**Output on SUCCESS**: `{ songs: [{ ...all_fields, quality_score: float, role: "hero"|"standard"|"rejected" }] }` → GO TO STEP 4

**Observable states**:
  - Customer sees: N/A
  - Operator sees: `[nightly] Quality: Song 1 → HERO (7.5/10), Song 2 → STANDARD (5.0/10)`
  - Database: N/A (logged)
  - Logs: `[nightly] Score: {title} = {score}/10 → {role}`

---

### STEP 4: Mood Detection + SRT + Backgrounds + Shorts

This step splits into 4 parallelizable sub-steps after quality classification.

---

#### STEP 4a: Mood Detection ← NEW

**Actor**: `prompt_gen.py` or inline rule-based analyzer
**Action**:
For each accepted song (Hero + Standard):
1. Extract first 400 chars of lyrics
2. Call MiniMax LLM via `prompt_gen._call_minimax_llm` with system prompt:
   ```
   "Classify the mood of this Chinese song into exactly one category:
   upbeat, melancholy, romantic, sad, dance, chill, soft.
   Return only the single word category, nothing else."
   ```
3. If LLM fails or times out → fallback to rule-based keyword matching (already exists in `_rule_based_fallback`)
4. Map mood → color palette:

| Mood | Primary Color | Secondary Color | Hex Pair |
|------|--------------|-----------------|----------|
| upbeat | Coral | Gold | `#FF6B6B\|#FFD93D` |
| melancholy | Teal | Sage | `#4ECDC4\|#95D5B2` |
| romantic | Soft Pink | Peach | `#FF9F9F\|#FFC8A2` |
| sad | Deep Blue | Indigo | `#6C63FF\|#3F3D56` |
| dance | Neon Magenta | Cyan | `#FF00FF\|#00FFFF` |
| chill | Mint | Teal | `#7BC8A4\|#98D4BB` |
| soft | Pastel Pink | Pastel Blue | `#D4A5A5\|#A8D5BA` |

5. Store per-song: `mood_label`, `color_primary`, `color_secondary`

**Timeout**: 15s per song (LLM call)
**Input**: `lyrics: str`
**Output on SUCCESS**: `{ mood: str, color_primary: str, color_secondary: str }` → flows to visualizer (STEP 5)
**Output on FAILURE**:
  - `FAILURE(llm_timeout)`: MiniMax LLM timeout → use rule-based fallback
  - `FAILURE(no_mood_detected)`: All methods failed → default to "chill" with teal palette

**Observable states**:
  - Customer sees: Reflected in final video colors
  - Operator sees: `[nightly] Mood: "melancholy" → #4ECDC4|#95D5B2`
  - Database: N/A
  - Logs: `[nightly] Mood: {title} → {mood} ({color_primary}|{color_secondary})`

---

#### STEP 4b: Full-Length SRT Generation ← NEW (adapted from Shorts SRT)

**Actor**: `nightly_visualizer.py` — new `generate_full_srt()` function
**Action**:
For each accepted song:
1. Parse lyrics into lines (skip empty lines and section markers `[Verse]`, `[Chorus]`)
2. Calculate `duration_per_line = song_duration / num_lines`
3. Generate SRT entries distributed evenly across full song duration
4. Save to `{song_dir}/{safe_title}.srt`
5. **Reuse code from `_generate_chorus_srt()`** — lift the SRT formatting logic into a shared helper that accepts `(lyrics, duration_sec, segment_count=None)` and returns full SRT string

Key differences from Shorts SRT (`_generate_chorus_srt`):
  - Uses ALL lyric lines (not just chorus/middle segment)
  - Uses FULL song duration (not 30s chorus clip)
  - Shorter per-line display time (song may have many lines)

**Timeout**: 5s per song (CPU-bound, no network)
**Input**: `lyrics: str, duration_sec: float`
**Output on SUCCESS**: `srt_path: str` → flows to visualizer (STEP 5)
**Output on FAILURE**:
  - `FAILURE(parse_error)`: Lyrics unparseable → skip SRT, visualizer runs without subtitles

**Observable states**:
  - Customer sees: SRT subtitles appearing during video playback
  - Operator sees: `[nightly:visualizer] SRT generated: 24 entries over 210s`
  - Database: `{song}/subtitle.srt` file
  - Logs: `[nightly] SRT: {title} → {n_entries} entries`

---

#### STEP 4c: Per-Song Backgrounds (no change, existing code)

**Actor**: `nightly_visualizer.generate_per_song_assets()`
**Action**:
1. Generate landscape background via Pollinations.ai with mood-aware prompt
2. Generate vertical background for Shorts
3. Generate thumbnail from landscape background

**Mood injection into prompt**: If mood_label is available, pass it to `prompt_gen.generate_prompt_from_lyrics()` as additional context so generated backgrounds match mood.

**No structural changes** — existing code already works. Mood enhancement is additive.

---

#### STEP 4d: Shorts Generation (30s instead of 45s)

**Actor**: `nightly_visualizer.generate_short()`
**Action**:
1. Find loudest **30s** segment (was 45s in Phase 1)
2. Extract chorus audio segment
3. Generate SRT for 30s segment (existing `_generate_chorus_srt`)
4. Generate 9:16 vertical MP4 with waveform + mood colors + SRT
5. Output: `{song}-short.mp4`

**Config change**: `shorts.duration_sec` in `nightly-music.yaml` changed from `45` to `30`

**Timeout**: 300s per short (FFmpeg-heavy)
**Output on SUCCESS**: `{ path: str, status: "ok", duration: 30.0 }`
**Output on FAILURE**:
  - `FAILURE(ffmpeg_error)`: FFmpeg fails → skip Shorts for this song, log error
  - `FAILURE(no_chorus)`: Audio too short to find 30s window → use first 30s

---

### STEP 5: Long-Form Visualizer with SRT + Mood Colors

**Actor**: `nightly_visualizer.generate_visualizer()` — modified
**Action**:
For each accepted song (Hero + Standard):
1. Load mood colors from STEP 4a
2. Build FFmpeg command with:
   - Background image (song-specific or global fallback)
   - **Mood waveform colors** instead of hardcoded `#FF6B6B|#4ECDC4`
     ```
     colors={color_primary}|{color_secondary}
     ```
   - **SRT subtitle overlay** via `subtitles=` filter
     ```
     subtitles={srt_path}:fontsdir={font_dir}
     ```
   - Title text (existing)
3. Run FFmpeg (existing `subprocess.run` pattern)

**Modified FFmpeg filter chain** (changes in bold):

Phase 1 (current):
```
[0:v]scale=1920:1080[bg]
[1:a]showwaves=s=1920x400:mode=cline:rate=25:colors=#FF6B6B|#4ECDC4[waves]
[bg][waves]overlay=0:(H-400)/2,drawtext=... [out]
```

Phase 2 (new):
```
[0:v]scale=1920:1080[bg]
[1:a]showwaves=s=1920x400:mode=cline:rate=25:colors={color_primary}|{color_secondary}[waves]
[bg][waves]overlay=0:(H-400)/2,drawtext=...,subtitles={srt_path}:fontsdir={font_dir}[out]
```

**Timeout**: 600s per video (FFmpeg encoding)
**Input**: `mp3_path, output_path, title, mood_colors, srt_path, background_image, duration_sec`
**Output on SUCCESS**: `{ path: str, duration: float, status: "ok" }` → GO TO STEP 6
**Output on FAILURE**:
  - `FAILURE(ffmpeg_error)`: FFmpeg returns non-zero → retry once → if still fails, mark song as `failed_viz`
  - `FAILURE(ffprobe_validation)`: Output file missing or < 1KB → same retry logic
  - `FAILURE(srt_not_found)`: SRT file path doesn't exist → run visualizer WITHOUT subtitles (non-fatal)

**Observable states**:
  - Customer sees: N/A (video not yet published)
  - Operator sees: `[nightly:visualizer] OK — 45.2MB, 210.5s → {path}`
  - Database: `{song}/{safe_title}-viz.mp4` file
  - Logs: `[nightly:visualizer] Mood colors: #FF6B6B|#FFD93D (upbeat), SRT subtitles: 48 lines`

---

### STEP 6: Staggered Upload Scheduling ← NEW

**Actor**: Pipeline orchestrator + `nightly_uploader.py`
**Action**:
For each accepted song:
1. Determine role from STEP 3:
   - **Hero**: `publish_at = 18:00 SGT` on target date
   - **Standard**: `publish_at = 20:00 SGT` on target date
2. Build YouTube metadata:
   - **Hero title**: `🥭 {title} — ManggoMusicCH 每日AI单曲`
   - **Standard title**: `{title} — ManggoMusicCH AI歌曲`
   - **Hero SEO tags**: Full tag list + mood tag + `#ManggoMusicCH`
   - **Standard SEO tags**: Shorter tag list (no `#ManggoMusicCH`)
   - Both: Full lyrics in description (existing)
3. Upload via `nightly_uploader.upload_video()` with `publish_at` set
4. Set thumbnail

For Shorts (×2):
1. Upload time: **12:00 SGT** (unchanged from Phase 1)
2. Duration: **30s** (changed from 45s)
3. Upload Hero Short + Standard Short at same time (12:00)

**Staggered schedule**:
```
12:00 SGT — Shorts (Hero + Standard, 2× Shorts uploaded)
18:00 SGT — Hero long-form video
20:00 SGT — Standard long-form video
```

**Timeout**: 600s per upload (YouTube resumable upload)
**Input**: `video_path, title, description, tags, publish_at, thumbnail_path`
**Output on SUCCESS**: `{ video_id: str, youtube_url: str, status: "ok" }`
**Output on FAILURE**:
  - `FAILURE(auth_error)`: OAuth token expired and can't refresh → alert operator via Telegram, retry next day
  - `FAILURE(api_quota)`: YouTube API quota exceeded → skip upload, log quota usage, Telegram alert
  - `FAILURE(upload_error)`: Resumable upload failed after retries → log, Telegram alert
  - `FAILURE(thumbnail_error)`: Thumbnail set failed (non-fatal) → video uploaded but no custom thumbnail

**Observable states**:
  - Customer sees: At 12:00, Shorts appear in feed. At 18:00, Hero appears. At 20:00, Standard appears.
  - Operator sees: `[nightly:uploader] Uploaded: https://youtube.com/watch?v=abc123 (Hero, publish 18:00)`
  - Database: YouTube video IDs stored in log
  - Logs: `[nightly] YouTube: {title} → {youtube_url} (scheduled {publish_at})`

---

### STEP 7: Sync → Log → Telegram

**Actor**: Pipeline orchestrator
**Action**:
1. Sync daily output folder to D-drive (existing)
2. Log to `song-log-YYYY-MM.json` with extended fields:
   ```json
   {
     "quality_score": 7.5,
     "role": "hero",
     "mood_label": "upbeat",
     "color_primary": "#FF6B6B",
     "color_secondary": "#FFD93D",
     "weekly_theme": "upbeat",
     "srt_generated": true,
     "compilation_done": false
   }
   ```
3. Telegram delivery:
   - Send Hero MP3 + lyrics + YouTube link
   - Send Standard MP3 + lyrics + YouTube link
   - Include quality scores and mood label in caption
   - If any songs rejected in quality gate: report with reason

**Failure modes**: Same as Phase 1 (non-critical per-step failures)

---

## Sunday-Only Branch: Weekly Compilation

### STEP C1: Check Compilation Eligibility

**Actor**: New `nightly_compilation.py` (triggered after STEP 0 if `is_sunday`)
**Action**:
1. Scan last 7 days' output directories (Mon-Sat: `YYYY-MM-DD` format)
2. Count available video files (`*-viz.mp4`)
3. Verify at least 2 videos exist
4. Verify total duration ≥ 30 minutes

**Timeout**: 30s
**Input**: `date_label: str` (Sunday date)
**Output on SUCCESS**: `{ eligible: bool, video_paths: list[str], total_duration: float }` → GO TO STEP C2 if eligible
**Output on FAILURE**:
  - `FAILURE(no_videos)`: < 2 videos from past week → SKIP compilation, log reason
  - `FAILURE(too_short)`: Total duration < 30 min → SKIP (still log, but don't upload)

---

### STEP C2: Generate Compilation Video

**Actor**: New `nightly_compilation.py` (new module)
**Action**:
1. Create `concat_file.txt` with FFmpeg concat demuxer format:
   ```
   file '/path/to/monday-viz.mp4'
   file '/path/to/tuesday-viz.mp4'
   ...
   ```
2. Generate compilation metadata:
   - **Title**: `"ManggoMusicCH 每周精选 | Week of May 11-17"`
   - **Description**: Week summary, list of songs with timestamps
   - **Chapters**: Each song as a YouTube chapter marker
     ```
     00:00 - Monday: {song_title}
     04:15 - Tuesday: {song_title}
     ...
     ```
3. Generate compilation thumbnail (Pollinations.ai with week theme)
4. Run FFmpeg concat:
   ```bash
   ffmpeg -f concat -safe 0 -i concat_file.txt -c copy output.mp4
   ```
   - If codec mismatch (likely since videos may have different encoding params), fall back to re-encode:
   ```bash
   ffmpeg -f concat -safe 0 -i concat_file.txt -c:v libx264 -crf 23 -c:a aac output.mp4
   ```

**Timeout**: 3600s (1 hour — large video)
**Input**: `video_paths: list[str], week_label: str`
**Output on SUCCESS**: `{ path: str, duration: float, chapters: list[dict] }` → GO TO STEP C3
**Output on FAILURE**:
  - `FAILURE(codec_mismatch)`: Stream copy fails → fallback to re-encode
  - `FAILURE(reencode_failure)`: Re-encode also fails → log error, skip upload
  - `FAILURE(duration_exceeds_limit)`: Video > 12 hours → truncate to 12h (YouTube limit)

---

### STEP C3: Upload Compilation

**Actor**: `nightly_uploader.py`
**Action**:
1. Upload compilation video with `publish_at = 18:00` Sunday SGT
2. **Metadata**:
   - Title: `"ManggoMusicCH 每周精选 | Week of {date_range}"`
   - Description: Song list with YouTube timestamp chapters
   - Tags: All standard tags + `#每周精选` + `#WeeklyAlbum`
   - Playlist: Add to "ManggoMusicCH 每周精选" playlist (create if not exists)
3. Set compilation thumbnail

**Timeout**: 600s
**Output on SUCCESS**: `{ video_id, youtube_url }` → GO TO SYNC+LOG
**Output on FAILURE**: Same failure modes as STEP 6 upload

---

## Handoff Contracts

### Pipeline Orchestrator → MiniMax API

```
HANDOFF: nightly_music.py -> minimax_music_api.generate_and_save()
  PAYLOAD:
    prompt: str        — "类似{artist}的《{song}》风格，{genre}，{instruments}，{vocals}，{mood}，{theme_modifier}"
    lyrics: str        — "" (empty, MiniMax generates)
    output_path: str   — tmp MP3 path
    is_instrumental: bool — False
    max_lyrics_retries: int — 3
  SUCCESS RESPONSE:
    {
      "song_title": str,
      "lyrics": str,
      "duration_sec": float,
      "size_mb": float,
      "audio_url": str
    }
  FAILURE RESPONSE:
    {
      "error": str,
      "retryable": true   — true for 429/5xx, false for 4xx
    }
  TIMEOUT: 180s — treated as FAILURE (retryable)
  ON FAILURE: Mark song as failed_gen, continue to next song
```

### Pipeline Orchestrator → Daily Theme Resolver

```
HANDOFF: nightly_music.py -> resolve_weekly_theme(date_label)
  PAYLOAD:
    date_label: str  — "YYYY-MM-DD"
  SUCCESS RESPONSE:
    {
      "theme": "upbeat",           # one of 7 themes
      "theme_modifier": "轻快活泼，节奏明快",  # Chinese modifier for prompt
      "day_name": "Monday",
      "is_sunday": false,
      "weekly_theme_prompt": "当前是Monday，歌曲风格应体现【轻快活泼，节奏明快】的氛围"
    }
  FAILURE RESPONSE:
    {
      "theme": "chill",
      "theme_modifier": "放松舒缓",
      "day_name": "unknown",
      "is_sunday": false
    }
  TIMEOUT: 5s
  ON FAILURE: Default to "chill" theme
```

### Mood Detector → Visualizer

```
HANDOFF: mood_detection() -> nightly_visualizer.generate_visualizer()
  PAYLOAD:
    lyrics: str,
    title: str,
  SUCCESS RESPONSE:
    {
      "mood_label": "upbeat",
      "color_primary": "#FF6B6B",
      "color_secondary": "#FFD93D",
      "confidence": 0.85
    }
  FAILURE RESPONSE:
    {
      "mood_label": "chill",
      "color_primary": "#7BC8A4",
      "color_secondary": "#98D4BB",
      "confidence": 0.0
    }
  TIMEOUT: 15s
  ON FAILURE: Default to "chill" palette
```

### SRT Generator → Visualizer

```
HANDOFF: generate_full_srt(lyrics, duration_sec) -> nightly_visualizer.generate_visualizer()
  PAYLOAD:
    lyrics: str,
    duration_sec: float
  SUCCESS RESPONSE:
    {
      "srt_path": "/path/to/song.srt",
      "line_count": 48,
      "total_duration_sec": 210.0
    }
  FAILURE RESPONSE:
    {
      "srt_path": "",
      "line_count": 0
    }
  TIMEOUT: 5s
  ON FAILURE: Visualizer runs without SRT
```

### Pipeline Orchestrator → YouTube Uploader (Staggered)

```
HANDOFF: nightly_music.py -> nightly_uploader.upload_video()
  PAYLOAD:
    video_path: str,
    title: str,                             # differs by Hero/Standard
    description: str,                       # full lyrics + SEO
    tags: list[str],                        # differs by Hero/Standard
    category_id: "10",
    privacy: "private",                     # auto-set when publish_at present
    thumbnail_path: str,
    publish_at: str                         # RFC 3339 — 18:00 or 20:00 SGT
    is_short: bool
  SUCCESS RESPONSE:
    {
      "video_id": "abc123",
      "youtube_url": "https://www.youtube.com/watch?v=abc123",
      "status": "ok"
    }
  FAILURE RESPONSE:
    {
      "video_id": "",
      "youtube_url": "",
      "status": "failed",
      "error": "YouTube API error: ...",
      "retryable": true
    }
  TIMEOUT: 600s
  ON FAILURE:
    - Auth failure → alert operator (requires manual OAuth re-auth)
    - Quota exceeded → skip remaining uploads for the day
    - Transient error → retry once → skip on second failure
```

### Weekly Compilation → YouTube Uploader

```
HANDOFF: nightly_compilation.py -> nightly_uploader.upload_video()
  PAYLOAD:
    video_path: str,                        # compilation MP4
    title: "ManggoMusicCH 每周精选 | Week of May 11-17",
    description: str,                       # song list + chapters + timestamps
    tags: ["AI Music", "华语流行", "每周精选", "WeeklyAlbum", "ManggoMusicCH", ...],
    category_id: "10",
    privacy: "private",
    thumbnail_path: str,                    # compilation thumbnail
    publish_at: str,                        # 18:00 Sunday SGT
    is_short: false
  SUCCESS RESPONSE:
    {
      "video_id": "abc123",
      "youtube_url": "https://www.youtube.com/watch?v=abc123",
      "status": "ok"
    }
  FAILURE RESPONSE:
    {
      "status": "failed",
      "error": str
    }
  TIMEOUT: 600s
  ON FAILURE: Alert operator, don't re-attempt (can be done manually next day)
```

---

## Configuration Changes (nightly-music.yaml)

```yaml
# Phase 2 additions to existing config

# Song quality gating
quality_gate:
  enabled: true
  hero_threshold: 6.0      # Minimum score 0-10 to be Hero
  standard_threshold: 4.0   # Minimum score to be Standard
  reject_below: 4.0         # Below this, song is skipped entirely

# Mood detection
mood_detection:
  enabled: true
  source: "minimax-llm"     # "minimax-llm" | "rule-based"
  fallback_mood: "chill"
  color_palettes:
    upbeat:    { primary: "#FF6B6B", secondary: "#FFD93D" }
    melancholy:{ primary: "#4ECDC4", secondary: "#95D5B2" }
    romantic:  { primary: "#FF9F9F", secondary: "#FFC8A2" }
    sad:       { primary: "#6C63FF", secondary: "#3F3D56" }
    dance:     { primary: "#FF00FF", secondary: "#00FFFF" }
    chill:     { primary: "#7BC8A4", secondary: "#98D4BB" }
    soft:      { primary: "#D4A5A5", secondary: "#A8D5BA" }

# Weekly themes (day-of-week modifiers)
weekly_themes:
  enabled: true
  monday:    { theme: "upbeat",     modifier: "轻快活泼，节奏明快" }
  tuesday:   { theme: "melancholy", modifier: "忧郁伤感，深情" }
  wednesday: { theme: "romantic",   modifier: "浪漫温馨，甜蜜" }
  thursday:  { theme: "sad",        modifier: "悲伤凄美，动情" }
  friday:    { theme: "dance",      modifier: "舞曲节奏，动感" }
  saturday:  { theme: "chill",      modifier: "放松舒缓，治愈" }
  sunday:    { theme: "soft",       modifier: "柔和温暖，宁静" }

# Staggered upload schedule
scheduling:
  hero_publish_time: "18:00"
  standard_publish_time: "20:00"
  shorts_publish_time: "12:00"

# Shorts duration (changed from 45 to 30)
shorts:
  enabled: true
  duration_sec: 30              # ← changed from 45
  upload_time: "12:00"

# SRT lyrics on long-form video
srt:
  enabled: true
  on_long_form: true            # ← new: SRT on long-form videos
  on_shorts: true               # existing: SRT on Shorts

# Weekly compilation (Sunday only)
compilation:
  enabled: true
  min_videos: 2
  min_duration_minutes: 30
  max_duration_hours: 12
  publish_time: "18:00"
  thumbnail_prompt: "weekly compilation album cover, song montage, ManggoMusicCH brand, dark aesthetic, music notes, cinematic"
  playlist_name: "ManggoMusicCH 每周精选"
```

---

## Cleanup Inventory

| Resource | Created at step | Destroyed by | Destroy method |
|---|---|---|---|
| Temp MP3 (`tmp-song-N.mp3`) | STEP 2 (MiniMax download) | `generate_song` cleanup | `os.remove` on exception |
| Temp Shorts dir (`.shorts-tmp-*`) | STEP 4d (Shorts FFmpeg) | `generate_short` finally block | `os.remove` + `os.rmdir` |
| SRT file (`.srt`) | STEP 4b | Pipeline end | No cleanup (kept as artifact) |
| Visualizer MP4 | STEP 5 | Pipeline end | No cleanup (uploaded to YouTube) |
| Short MP4 | STEP 4d | Pipeline end | No cleanup (uploaded to YouTube) |
| Thumbnail JPG | STEP 4c | Pipeline end | No cleanup (uploaded to YouTube) |
| Background images | STEP 4c | Pipeline end | No cleanup (kept as artifact) |
| Compilation MP4 (Sunday) | STEP C2 | Pipeline end | No cleanup (uploaded to YouTube) |
| Concat file list (Sunday) | STEP C2 | After FFmpeg run | `os.remove` |
| OAuth token (stale) | STEP 6 | On auth failure | Manual re-auth |
| Empty log entries | STEP 7 | Next write | Overwritten by idempotent log |

**Orphan risk**: If pipeline crashes mid-step, temp files in `.shorts-tmp-*` may remain. Mitigation: timestamped temp dir names + periodic cleanup of dirs > 24h old.

---

## Test Cases

| Test | Trigger | Expected behavior |
|---|---|---|
| TC-01: Happy path Hero+Standard | 2 songs generated, both score ≥6/≥4 | Hero published 18:00, Standard 20:00, Shorts at 12:00, mood colors applied, SRT on long-form |
| TC-02: Both songs rejected | 2 songs both score <4 | NO uploads, Telegram alert "No songs passed quality gate" |
| TC-03: Hero passes, Standard fails | Song A ≥6, Song B <4 | Hero-only day: 1 video at 18:00, 1 Short at 12:00, Standard skipped |
| TC-04: Standard promoted to Hero | Song A <6, Song B ≥4 | Song B promoted to Hero, published at 18:00 |
| TC-05: Mood detection fallback | MiniMax LLM timeout | Rule-based keyword fallback used, visualizer runs with default chill palette |
| TC-06: SRT generation on long-form | Song generated with 48-line lyrics | `.srt` file created with 48 entries distributed across song duration |
| TC-07: Mood color in visualizer | Mood = "melancholy" | FFmpeg command uses `#4ECDC4|#95D5B2` instead of `#FF6B6B|#4ECDC4` |
| TC-08: Staggered upload times | Hero + Standard both accepted | Hero `publish_at=18:00`, Standard `publish_at=20:00`, times verified in YouTube API body |
| TC-09: Shorts 30s duration | Short generation | FFmpeg `-t 30`, `_find_loudest_window` uses 30s window, Short duration = 30s ±2s |
| TC-10: Weekly theme on Monday | date_label = Monday | Prompt includes "轻快活泼，节奏明快" modifier |
| TC-11: Weekly theme on Thursday | date_label = Thursday | Prompt includes "悲伤凄美，动情" modifier |
| TC-12: Sunday compilation - eligible | 5 videos from Mon-Sat, total 45 min | Concatenated MP4 uploaded at 18:00 Sunday, chapters in description |
| TC-13: Sunday compilation - insufficient | 1 video from past week | Compilation skipped, log "insufficient videos (need ≥2)" |
| TC-14: Upload auth failure | OAuth token expired & can't refresh | Telegram alert sent, uploads skipped, retry next day |
| TC-15: Partial Shorts failure | Hero Short succeeds, Standard Short FFmpeg fails | Hero Short uploaded at 12:00, Standard Short skipped (non-fatal) |
| TC-16: One song generation fails | Song 1 succeeds, Song 2 fails | Only Song 1 progresses through pipeline, becomes Hero |
| TC-17: Both generation fail | Both songs return error | Pipeline aborts upload, Telegram alert sent |
| TC-18: IDEMPOTENCY: same date retry | `--date 2026-05-14` run twice | Second run replaces log entries, does NOT duplicate YouTube uploads (YouTube API skips duplicate `publish_at` slots if video IDs stored) |

---

## Assumptions

| # | Assumption | Where verified | Risk if wrong |
|---|---|---|---|
| A1 | FFmpeg `showwaves` accepts two `colors=` separated by pipe | Current code uses this, works | Low — well-documented FFmpeg feature |
| A2 | FFmpeg `subtitles` filter works with UTF-8 CJK fonts | Font (wqy-zenhei) installed and tested in Phase 1 | Low — tested in Shorts already |
| A3 | YouTube API publish_at UTC conversion is correct | SGT = UTC+8, current code handles this | Medium — if DST or timezone library changes, times shift by 1h |
| A4 | LLM-based mood detection is reliable for Chinese lyrics | Not verified — depends on MiniMax M2.7 accuracy | **HIGH** — if LLM returns wrong moods, visualizer colors won't match song feel |
| A5 | Compilation concat works across videos with different encoding params | Not verified — videos may have different keyframes, codec params | **HIGH** — may need re-encode fallback, which is slower and quality-lossy |
| A6 | YouTube chapter markers in description (00:00 format) work automatically | Standard YouTube feature for timestamps in description | Low — well-documented |
| A7 | Weekly theme modifiers produce noticeably different songs | Not verified — MiniMax may ignore modifier if prompt is already specific | **MEDIUM** — themes may not be distinguishable in output |
| A8 | Pollinations.ai background generation is fast enough for 2 songs in sequence | Current rate limiting (15s between requests) works | Low — time budget is generous (2am cron) |
| A9 | YouTube API `videos.insert` with `publishAt` forces privacy to private | Current code does this, tested | Low |
| A10 | SRT timing distribution (evenly across duration) looks natural | Not verified — may place subtitle display at awkward points in the music | **MEDIUM** — may need smarter segmentation that aligns with [Verse]/[Chorus] markers |

---

## Open Questions

1. **SRT on long-form vs Shorts**: Should the full SRT on long-form use the same timing formula as Shorts SRT (evenly distributed), or should it try to align with musical sections using `[Verse]`/`[Chorus]` markers? Section-aligned would look better but is harder to implement.
2. **Hero/Standard metadata differentiation**: How different should Hero and Standard titles/descriptions/tags be? Should only Hero get the `🥭` emoji and `ManggoMusicCH` branding?
3. **Compilation chapters**: YouTube supports chapters via timestamps in description (e.g., `00:00 Intro`). Does the channel want this, or just a simple concatenated video?
4. **Quality scoring weights**: Are the scoring weights in §3 reasonable, or should they be tuned after observing real output quality?
5. **Mood detection confidence threshold**: Should low-confidence moods (e.g., <0.5) fall back to default palette, or always use detected mood?
6. **Weekly theme override**: Should individual songs override the day's theme if their lyrics naturally suggest a different mood? (Currently theme is a prompt modifier, mood is post-generation detection — they may not match.)
7. **Compilation on weeks with insufficient videos**: What's the minimum useful compilation? 2 videos (15 min)? 3 videos (22 min)? Threshold needs tuning.
8. **YouTube API quota**: Weekly compilation adds ~1600 units on Sunday. Current 10,000/day quota is sufficient, but verify: 2 long-form (3200) + 2 Shorts (3200) + 1 compilation (1600) + thumbnails (150) = 8150/day. On Sunday this is 8150. On other days it's 6550. Both within 10,000 limit.

---

## Spec vs Reality Audit Log

| Date | Finding | Action taken |
|---|---|---|
| 2026-05-14 | Initial Phase 2 workflow spec created | — |
| 2026-05-14 | Reuses existing `_generate_chorus_srt()` for long-form SRT | Refactored into `generate_full_srt()` with parameterized duration |
| 2026-05-14 | Mood detection reuses `prompt_gen._call_minimax_llm()` | No new API calls needed |
| 2026-05-14 | Weekly theme injected into `fetch_trending.build_style_prompt()` | Adds `theme_modifier` parameter to prompt builder |
| 2026-05-14 | Background generation already uses mood-based prompts via `prompt_gen` | Mood label passed as additional context |
| 2026-05-14 | Shorts duration change from 45→30 is just config change | Updated `nightly-music.yaml` default |
| 2026-05-14 | Staggered upload requires `publish_at` parameter already supported | `upload_video()` already accepts `publish_at` |
