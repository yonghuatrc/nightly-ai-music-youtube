# Hermes Agent Execution Plan: Nightly AI Music — 10-Song Upgrade

> **STALE — Superseded pre-implementation plan.** This document was the original Phase 2 plan for a 10-song upgrade (2026-05-08). The project took a different direction: Phase 1 shipped with 2 songs/night, YouTube visualizer + uploader, and consolidated project layout. See [README.md](README.md) for current state.

> **Project:** nightly-ai-music-youtube
> **Boss:** Dennis Ng
> **Date:** 2026-05-08
> **Status:** Superseded — see README.md for current

---

## Mission

Upgrade the existing nightly AI music pipeline from 2 mixed-language songs to 10 Chinese-only songs based on real trending Chinese chart data. Add configuration for trending source and language selection, create per-day output folders, and batch Telegram delivery for cleaner mornings. The pipeline must run reliably at 2am with no manual intervention.

## Non-Negotiable Requirements

1. **Configurable trending source** — Must support at least 3 modes: QQ Music 抖音热歌榜 (default), NetEase Cloud 热歌榜, and a fallback hardcoded pool. Switching source must be a single config change.
2. **Configurable language** — Must support at least: "chinese-only" (default), "mixed" (EN/ZH/KR/JP), or a custom languages list. Switching must be a single config change.
3. **10 songs minimum** — Pipeline must generate exactly N songs (configurable, default 10) each night.
4. **Per-day folders** — All output files for a night go into `~/.hermes/songs/nightly-songs/YYYY-MM-DD/` with D-drive mirror at `/mnt/d/Hermes/songs/nightly-songs/YYYY-MM-DD/`.
5. **Batch Telegram delivery** — Send 1 consolidated message with ALL songs, not 20 individual messages. Group into batches of max 5 songs per message if needed.
6. **Stage-gated execution** — Each stage must show results and wait for Boss approval before proceeding.
7. **No band-aid fixes** — Root cause fixes only. The current PhantomJS/Selenium gap for trending research must be solved properly (use Tavily/web scraping with requests, not a half-baked solution).

## Recommended Architecture

| Layer | Choice | Reason |
|---|---|---|
| Config format | `D:\Hermes\config\nightly-music.yaml` (`/mnt/d/Hermes/config/nightly-music.yaml`) | Staging folder — Boss can open in Notepad from Windows. Script reads from this path. |
| Trending fetch | `requests` + JSON rankList from QQ Music 抖音热歌榜 (primary), KKBOX人氣排行榜, and/or MY FM RIM 劲爆排行榜. **Multi-source:** YAML accepts list `[- qq-douyin, - kkbox]` — tried in order, deduplicated. Falls back to pool. | No Selenium needed. Multiple sources aggregate more variety. |
| Trending fallback | Hardcoded Chinese styles pool | If all web sources fail, still produces Chinese songs (not dead air) |
| Per-song prompt | `"类似[歌手]的《[歌曲名]》风格，华语[流派]，[乐器]，[人声描述]"` | Maps a real trending song to MiniMax's style description format |
| Generation | MiniMax music-2.6 (single call per song) | Already proven in production (~44s/song, 10 songs ≈ 7.5 min) |
| Daily folders | `YYYY-MM-DD/` subdirectories under songs dir | Clean separation, easy for Boss to browse per-night output |
| Telegram batching | Single `send_message` with multiple `MEDIA:` tags per batch | Each batch = 1 caption + up to 5 MP3 + 5 lyrics files (max 20 file attachments per message is Telegram limit) |
| Configurable language | YAML key `language: "chinese-only" \| "mixed" \| ["Chinese", "English"]` | Simple string or list — script parses and filters accordingly |

## Directory Layout

```text
D:\Hermes\                           — Staging folder (mounted at /mnt/d/Hermes/)
  config\
    nightly-music.yaml              — CONFIGURATION: trending source, language, count, etc.
                                   Edit from Windows Notepad — script reads from /mnt/d/Hermes/config/

~/.hermes/
  scripts/
    nightly_music.py                — MODIFY: upgrade from 2 songs to multi-song pipeline
    fetch_trending.py               — CREATE: fetch trending Chinese songs from configurable source
    check-duplicate.py              — UPDATE: updated dedup logic for new config format
    minimax_music_api.py            — UNCHANGED (works fine)
  songs/
    nightly-songs/
      YYYY-MM-DD/                   — Per-day folder (created automatically)
        song-01.mp3, song-01.txt
        song-02.mp3, song-02.txt
        ...
  work_logs/
    nightly-songs/
      song-log.json                 — UNCHANGED format (appended per song)
  pending-projects/
    nightly-ai-music-youtube/
      AGENT_EXECUTION_PLAN.md       — THIS FILE
      Project_Instruction.md        — UPDATE with new phase info
      Phase2_Issues.md              — UPDATE with resolved items

/mnt/d/Hermes/songs/nightly-songs/
  YYYY-MM-DD/                       — D-drive mirror (shutil.copy2 after each song)
```

## Config File Format (`D:\Hermes\config\nightly-music.yaml`)

```yaml
# Nightly AI Music Configuration
# Edit this file from Windows to change behavior — no code changes needed.
# Script reads from: /mnt/d/Hermes/config/nightly-music.yaml

# Number of songs to generate each night
song_count: 10

# Language configuration:
#   "chinese-only"  — All songs in Chinese (default)
#   "mixed"         — Random EN/ZH/KR/JP (old behavior)
#   ["Chinese", "English"]  — Explicit list, random pick from these
language: "chinese-only"

# Trending source:
#   Single source: "qq-douyin"
#   Multiple sources (tried in order, deduplicated):
#     - "qq-douyin"
#     - "kkbox"
#   Sources: "qq-douyin" | "kkbox" | "my-fm" | "pool"
trending_source:
  - "qq-douyin"
  - "kkbox"
  - "my-fm"

# Telegram batching:
#   songs_per_message: Max songs per Telegram message (default: 5)
#   Telegram limits: max 20 file attachments per message
telegram:
  songs_per_message: 5

# Output directory (YEAR-MONTH-DAY subfolder created automatically)
output_dir: "~/.hermes/songs/nightly-songs"
d_drive_mirror: "/mnt/d/Hermes/songs/nightly-songs"
```

## Telegram Approval Workflow

Hermes will send Telegram update at each phase boundary and wait for Boss approval before proceeding to next phase. Boss is working via CLI so updates will be in-chat.

## Execution Phases

### Phase 1: Create `fetch_trending.py` — Trending Song Fetcher

**Goal:** A standalone Python script that fetches top Chinese trending songs from a configurable source and outputs clean JSON.

**Boss actions required:** None.

**Hermes must:**
- [ ] Create `~/.hermes/scripts/fetch_trending.py` with these capabilities:
  - `--source qq-douyin`: Fetches QQ Music 抖音热歌榜 (toplist/60), parses song names + artists
  - `--source qq-hot`: Fetches QQ Music 热歌榜 (toplist/26)
  - `--source netease-hot`: Fetches NetEase Cloud 热歌榜 (playlist/3778678) via public API
  - `--source pool`: Outputs from a hardcoded Chinese-only fallback pool
  - `--count N`: Returns top N trending songs
  - `--language Chinese`: Filters/validates that songs match language criteria
  - Output: JSON array of `[{"song":"晴天","artist":"周杰伦","source":"qq-douyin","style_prompt":"华语流行抒情，钢琴为主，温暖声线"}, ...]`
  - The `style_prompt` field is MiniMax-compatible description derived from song+artist
- [ ] Hardcoded Chinese fallback pool of 20+ Chinese song styles (周杰伦, 林俊杰, 邓紫棋, 薛之谦, 李荣浩, etc.) for when web fetch fails
- [ ] Test with `python3 ~/.hermes/scripts/fetch_trending.py --source qq-douyin --count 15`

**Acceptance:**
- [ ] Script runs without errors and returns 15+ Chinese song entries
- [ ] Each entry has song name, artist, and style_prompt fields
- [ ] Pool fallback works (test by running with `--source pool --count 10`)
- [ ] JSON output is valid (pipe through `python3 -m json.tool`)

### Phase 2: Update `nightly_music.py` — Multi-Song Pipeline

**Goal:** Rewrite the generation script to support configurable N songs, daily folders, and the new config file.

**Boss actions required:** None.

**Hermes must:**
- [ ] Create `/mnt/d/Hermes/config/nightly-music.yaml` with default settings (Boss can edit from `D:\Hermes\config\` in Windows)
- [ ] Rewrite `nightly_music.py` to:
  - Read config from `nightly-music.yaml`
  - Import and call `fetch_trending.py` as a subprocess, passing config values
  - For each trending song, construct a MiniMax prompt: `"类似[artist]的《[song]》风格，华语[genre]，[instruments]，[vocal_desc]"` with variations to avoid identical prompts
  - Generate songs sequentially (1 through N), each with retry logic
  - Create `YYYY-MM-DD/` subfolder under songs dir
  - Save MP3 as `song-01.mp3`, `song-02.txt` etc. inside the daily folder
  - Sync daily folder to D-drive mirror after all songs complete
  - Log each song to `song-log.json` with new `daily_folder` field
  - Return summary JSON: `{"date":"...", "song_count":N, "successful":N, "failed":0, "songs":[...]}`
- [ ] CLI interface: `python3 nightly_music.py --date 2026-05-09` (no more --song-number)
- [ ] Keep backward compatible: old `--song-number` arg triggers single-song mode

**Acceptance:**
- [ ] `python3 nightly_music.py --date 2026-05-09` generates songs in `.../nightly-songs/2026-05-09/`
- [ ] Daily folder has N × (MP3 + txt) files correctly named
- [ ] D-drive has matching mirror
- [ ] song-log.json has N new entries with correct `daily_folder` field
- [ ] Running with `language: "mixed"` produces varied languages

### Phase 3: Batch Telegram Delivery

**Goal:** Deliver songs in grouped Telegram messages instead of individual per-song messages.

**Boss actions required:** None.

**Hermes must:**
- [ ] Modify Telegram delivery in `nightly_music.py` to batch songs:
  - Group songs by `config.telegram.songs_per_message` (default 5)
  - Each batch: 1 consolidated message with:
    - Cover caption: "🌙 AI Music — 2026-05-09\nSongs 1-5 of 10\n[summary table per song: title, style, duration]"
    - File attachments: MP3 files + lyrics.txt for each song in batch
  - If songs_per_message = 0, send all in 1 message (respect Telegram's 20-file limit)
- [ ] Lyrics content: attach as `.txt` files (same as current), not inline in caption (avoids 4096-char limit)
- [ ] Handle edge case where a song failed — skip it in the batch, note in caption
- [ ] Verify Telegram batch send works (test with 3 song mockup)

**Acceptance:**
- [ ] 10 songs → 2 Telegram messages (5 songs each) with all files attached
- [ ] Each message has clear caption showing which songs are included
- [ ] Files playable when downloaded from Telegram

### Phase 4: Config Validation & Edge Cases

**Goal:** Handle all error modes gracefully without failed nights.

**Boss actions required:** None.

**Hermes must:**
- [ ] Validate YAML config on startup — if invalid, log error and use defaults
- [ ] Trending fetch failure → fall back to hardcoded pool (not abort)
- [ ] Language filter returns fewer songs than needed → supplement from pool
- [ ] MiniMax API failure on a song → retry once, skip if still fails, continue to next song
- [ ] If ≥50% songs fail → send Telegram alert instead of batch (Boss should know)
- [ ] Daily folder already exists → date made unique with suffix

**Acceptance:**
- [ ] Purposely delete config file → pipeline uses all defaults (no crash)
- [ ] Kill network during trending fetch → falls back to pool, generates songs
- [ ] Individual song failure → logged, skipped, pipeline continues for remaining songs

### Phase 5: Dry Run & Verification

**Goal:** Full end-to-end test before going live.

**Boss actions required:** Review dry run output.

**Hermes must:**
- [ ] Run: `python3 ~/.hermes/scripts/nightly_music.py --date 2026-05-09`
- [ ] Verify:
  - [ ] 10 MP3 files in `~/.hermes/songs/nightly-songs/2026-05-09/`
  - [ ] 10 lyrics.txt files (same folder)
  - [ ] All MP3s playable (check file size > 1MB)
  - [ ] D-drive mirror has matching folder
  - [ ] song-log.json has 10 new entries
  - [ ] Telegram received 2 messages (5 songs each)
  - [ ] Each message has MP3 + lyrics files attached
- [ ] Show summary to Boss
- [ ] **STOP. Wait for Boss approval before Phase 6.**

**Acceptance:**
- [ ] All 10 songs generated successfully
- [ ] Telegram delivery is clean and organized
- [ ] Boss approves the output

### Phase 6: Update Cron Job

**Goal:** Update the existing cron job to use the new pipeline.

**Boss actions required:** Approve dry run first.

**Hermes must:**
- [ ] Pause existing cron job `53617334c6b4` (Nightly AI Music Generation)
- [ ] Update its prompt to call the new script: `cd ~/.hermes && python3 scripts/nightly_music.py --date $(date +%Y-%m-%d)`
- [ ] Resume cron
- [ ] Verify: `cronjob(action='list')` shows updated prompt
- [ ] Also update system crontab entry (`crontab -l | grep nightly`)
- [ ] Send Telegram notification: "🔄 Nightly AI Music upgraded: 10 songs, Chinese trending, batched delivery"

**Acceptance:**
- [ ] Cron job updated and active
- [ ] Both Hermes cron and system crontab are in sync
- [ ] Next run is tomorrow 2am

### Phase 7: Update Project Docs

**Goal:** Keep project documentation current.

**Boss actions required:** None.

**Hermes must:**
- [ ] Update `Project_Instruction.md` with new specs (10 songs, Chinese trending, configurable)
- [ ] Update `Phase2_Issues.md` — mark relevant items resolved
- [ ] Update memory with new config locations and architecture
- [ ] Sync to D-drive: `rsync -av ~/.hermes/ /mnt/d/Hermes/.hermes/` (dry-run first, show output)

**Acceptance:**
- [ ] All docs updated
- [ ] D-drive mirrored

---

## Decisions Made

| # | Question | Answer |
|---|---|---|
| 1 | **Primary trending source** | QQ 抖音热歌榜 (default), plus KKBOX人氣排行榜 and MY FM RIM 劲爆排行榜 as alternatives |
| 2 | **Batch size** | 5 songs per message → 2 Telegram msgs for 10 songs |
| 3 | **2am schedule** | ✅ Keep 2am |
| 4 | **Daily folders** | ✅ New `YYYY-MM-DD/` subfolders for each night's songs (going forward) |

---

## Open Questions (Boss Input Needed)

None remaining — all decisions made. Ready for Boss to review plan and approve Phase 1 execution.

## Risks And Mitigations

| Risk | Mitigation |
|---|---|
| **QQ Music page structure changes** — regex parsing breaks | `fetch_trending.py` detects parse failure and falls back to pool mode. Log error so we know to update regex. |
| **MiniMax rate limiting** — 10 sequential calls may trigger throttling | Add 2s delay between songs. If 429 received, exponential backoff (2s, 4s, 8s) |
| **Telegram batching fails** — sending 10 files in 1 message times out | Fall back to individual sends per song (current behavior) |
| **Cron takes longer than expected** — 10 songs + lyrics + files could take 10-15 min | 2am start → ~2:15am finish, well within the window. Monitor first run. |
| **D-drive not available** — WSL mount issue | Log warning but continue. Retry on next sync. |
| **Config YAML typo** — invalid syntax causes pipeline to fail | Load with strict validation + fallback to hardcoded defaults. Log parse error. |
