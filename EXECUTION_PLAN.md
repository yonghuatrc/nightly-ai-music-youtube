# Execution Plan: Nightly AI Music YouTube Channel

Date: 2026-05-14 (updated 2026-05-14)
Status: ✅ Phase 1 + Phase 2 complete — quality-gated pipeline runs nightly at 2am SGT

---

## Phase 1a: Bug Fixes — ✅ COMPLETE (2026-05-12)

All 10 bugs fixed across 3 files. Verified: compile clean, dry-run works, dedup active, source validation working.

| # | Bug | File | Fix Applied |
|---|-----|------|-------------|
| 1 | Song log not idempotent | `nightly_music.py:append_log()` | Delete existing entries for date before append; monthly log file |
| 2 | Recursive retry in generate_and_save() | `minimax_music_api.py:generate_and_save()` | Already for-loop; added missing `import sys` |
| 3 | Module-level .env crash | `nightly_music.py` | Lazy-load via `_ensure_telegram()` — loads on first use only |
| 4 | Dead dedup code | `nightly_music.py:run_pipeline()` | Already wired — calls check-duplicate.py, filters blocked pairs |
| 5 | Log file grows unbounded | `nightly_music.py:append_log()` | Monthly rotation: `song-log-{YYYY-MM}.json` |
| 6 | Telegram response never checked | `nightly_music.py:send_telegram_batch()` | Added `resp.raise_for_status()` + error logging |
| 7 | Telegram sends one-by-one | `nightly_music.py:send_telegram_batch()` | Rewrote to use `sendMediaGroup` API with multipart form |
| 8 | Config source validation | `nightly_music.py:run_pipeline()` | Warn on unknown sources (known: qq-douyin, kkbox, my-fm, pool) |
| 9 | Path normalization inconsistent | `nightly_music.py:D_DRIVE_BASE, run_pipeline()` | Applied `os.path.expanduser()` to D_DRIVE_BASE and d_drive_dir |
| 10 | Lyrics retry hardcoded | `nightly_music.py, minimax_music_api.py` | Added `max_lyrics_retries` to config defaults, passed through pipeline |

---

## Phase 1b: YouTube Integration

### Prerequisites (Boss must do)

| Step | What | How |
|------|------|-----|
| P1 | Create Google Cloud Project | Go to https://console.cloud.google.com |
| P2 | Enable YouTube Data API v3 | APIs & Services → Enable API |
| P3 | Configure OAuth consent screen | External, test user, add your email |
| P4 | Create OAuth 2.0 Desktop credentials | Download JSON → save to `/mnt/d/Hermes/secrets/youtube-oauth.json` |
| P5 | Install Python deps | `pip install google-auth google-auth-oauthlib google-api-python-client` |
| P6 | Install CJK font (if missing) | `sudo apt install fonts-noto-cjk` |
| P7 | Prepare 5-10 background images | Download from Unsplash/Pexels → `assets/backgrounds/` |
| P8 | Run one-time OAuth consent | `python nightly_uploader.py --auth` opens browser, click Allow |

### Implementation

| Step | Task | File | Depends on |
|------|------|------|------------|
| I1 | Create `nightly_visualizer.py` — FFmpeg waveform + album art overlay | NEW | P6, P7 |
| I2 | Create `nightly_uploader.py` — YouTube Data API v3 upload + scheduling | NEW | P1-P5, P8 |
| I3 | Integrate visualizer + uploader hooks into `nightly_music.py` | Modify | I1, I2 |
| I4 | Add YouTube config to `nightly-music.yaml` | Modify | I3 |
| I5 | Extend song-log schema with YouTube fields | Modify | I3 |
| I6 | Write unit tests for all new + modified modules | tests/ | I1-I5 |
| I7 | DRY RUN — full end-to-end test | All | I1-I6 |
| I8 | Update Telegram message format to include YouTube links | nightly_music.py | I7 |

---

## Phase 2: Quality-Gated Pipeline — ✅ COMPLETE (2026-05-14)

Phase 2 replaces the old "10 songs/day, multi-agent" plan with a quality-gated strategy: 0-2 songs/day, Hero/Standard tiers, mood-based visualizer colors, SRT subtitles, staggered upload, weekly themes, and Sunday compilation.

### New Modules Created

| Module | File | Purpose |
|--------|------|---------|
| Song quality scoring | `scripts/song_quality.py` | Score on 5 dimensions (0-10); Hero ≥6, Standard ≥4, reject |
| Weekly themes | `scripts/weekly_themes.py` | Day-of-week mood modifiers (Mon-Sun) |
| Weekly compilation | `scripts/nightly_compilation.py` | Sunday FFmpeg concat album from Mon-Sat Heroes |
| Prompt generation | `scripts/prompt_gen.py` | LLM-based image prompt from song lyrics via MiniMax |
| Image generation | `scripts/image_gen.py` | Pollinations.ai rate-limited image download |

### Behavior Changes

| Feature | Phase 1 | Phase 2 |
|---------|---------|---------|
| Song quality | No gate — upload everything | Hero ≥6/10, Standard ≥4/10, skip <4 |
| Upload times | Both at 18:00 | Hero at 18:00, Standard at 20:00, Shorts at 12:00 |
| Shorts duration | 45s | 30s (higher retention) |
| Long-form SRT | ❌ Not on long video | ✅ SRT subtitle overlay on long-form |
| Visualizer colors | Static `#FF6B6B\|#4ECDC4` | Dynamic mood-based (7 palettes) |
| Weekly themes | None | Day-of-week mood modifiers |
| Weekly compilation | None | Sunday album from week's videos |
| Background images | Static default-dark.jpg | Per-song Pollinations.ai generated |

### Sprint Breakdown

| Sprint | Deliverables | Status |
|--------|-------------|--------|
| **Sprint 1** | `song_quality.py` — 5-dim scoring (lyrics_length, has_chorus, duration, placeholder_check, vocabulary_richness). Verdict: Hero ≥6 (premium), Standard ≥4, reject <4. Mood detection → 7 color palettes from lyrics. SRT overlay on long-form via FFmpeg `subtitles=` filter. Staggered upload schedule (Hero 18:00, Standard 20:00). Shorts duration 45s→30s. | ✅ Complete |
| **Sprint 2** | `image_gen.py` — Pollinations.ai wrapper with rate limiting (15s delay). `prompt_gen.py` — MiniMax M2.7 LLM prompt generation + Pollinations fallback + rule-based last resort. Channel branding assets (logo 800x800, banner 2560x1440). Per-song backgrounds + thumbnails via Pollinations. | ✅ Complete |
| **Sprint 3** | `weekly_themes.py` — 7 day-of-week themes (Mon=upbeat, Tue=melancholy, Wed=romantic, Thu=sad, Fri=energetic, Sat=chill, Sun=calm). Theme injected into MiniMax song prompt. Config toggle in `nightly-music.yaml`. | ✅ Complete |
| **Sprint 4** | `nightly_compilation.py` — Sunday-only FFmpeg concat of Mon-Sat Hero videos. Chapter markers, ~30-45 min album. Bug fixes: B1 (visualizer runs after asset gen), B2 (background=None crash), B3 (thumbnail double-gen). E2E regression pass. | ✅ Complete |

### Fixed Bugs (Phase 2 QA)

| # | Bug | File | Fix |
|---|-----|------|-----|
| B1 | Visualizer runs before assets exist | `nightly_music.py` | Reordered: assets→thumbnail→visualizer |
| B2 | `generate_background()` returns None | `image_gen.py` | Added fallback to default background |
| B3 | Thumbnail generated twice | `nightly_music.py` | Removed duplicate call in visualizer step |

---

## Status Tracking

| Phase | Status | Date Completed |
|-------|--------|----------------|
| Phase 1a — Bug fixes | ✅ Complete | 2026-05-12 |
| Phase 1b — Prerequisites | ✅ Complete | 2026-05-12 |
| Phase 1b — Implementation | ✅ Complete | 2026-05-12 |
| Phase 1b — DRY RUN | ✅ Complete | 2026-05-12 |
| Phase 1b — YouTube Upload | ✅ Complete | 2026-05-12 |
| Phase 2 — Sprint 1 (Quality, Mood, SRT) | ✅ Complete | 2026-05-14 |
| Phase 2 — Sprint 2 (Image Gen, Branding) | ✅ Complete | 2026-05-14 |
| Phase 2 — Sprint 3 (Weekly Themes) | ✅ Complete | 2026-05-14 |
| Phase 2 — Sprint 4 (Compilation, Bugfixes) | ✅ Complete | 2026-05-14 |

---

## Reference: Original Phase 1 Specs (from 2026-05-05)

Preserved from the original `Project_Instruction.md` specification. These defined the initial pipeline before YouTube integration.

### Log Format

**File:** `logs/song-log-YYYY-MM.json` (project-relative, monthly rotation)

```json
{
  "date": "2026-05-05",
  "song_number": 1,
  "language": "Chinese",
  "language_for_prompt": "Chinese",
  "style_source": "TikTok SG trending",
  "style_reference": "仿林俊杰 抒情R&B 风格",
  "prompt_used": "...",
  "model": "MiniMax-Music",
  "output_file": "output/2026-05-05/01-song.mp3",
  "lyrics": "..."
}
```

**Dedup rule:** Before generating, read last 7 days of log. Reject any style that matches both `style_reference` AND `language`. Pick alternative trending song if collision.

### Original Success Criteria (1-week trial)

| Metric | Target |
|--------|--------|
| Successful generations | ≥ 12/14 songs (allow 2 failures) |
| Morning notification rate | 7/7 days delivered by 9am |
| Dedup compliance | 0 duplicate style+language pairs |
| Audio playable | All files openable as MP3 |
| YouTube publishable | Boss can take audio file → upload to YouTube |

### Morning Notification Format

```
🌙 AI Music Daily — 2026-05-06

🎵 Song #1: [Song Title]
   Language: Chinese
   Style: 仿林俊杰抒情R&B · TikTok SG trending
   🎧 Audio: [file attached]
   📝 Lyrics:
   [full lyrics here]

🎵 Song #2: [Song Title]
   Language: English
   Style: upbeat TikTok pop · female vocal
   🎧 Audio: [file attached]
   📝 Lyrics:
   [full lyrics here]
```

### Risks & Mitigations (from Phase 1 spec)

| Risk | Impact | Mitigation |
|------|--------|------------|
| MiniMax API downtime at 2am | Songs missed | Retry once; if still fail, skip and notify |
| Song quality poor | Wasted nights | Boss can react to morning notification — adjust style prompt if needed |
| Duplicate style selected | Less variety | 7-day dedup check is aggressive enough |
| YouTube copyright claim | Channel risk | Boss is aware AI songs may trigger claims; project is explicit about AI origin |

---

## Related Files

| File | Location |
|------|----------|
| Design document | `DESIGN.md` |
| Execution plan | `EXECUTION_PLAN.md` (this file) |
| Phase 2 issues | `Phase2_Issues.md` |
| Phase 2 architecture | `Phase2_ARCHITECTURE.md` |
| Pipeline workflow spec | `WORKFLOW-pipeline-phase2.md` |
| Pipeline script | `scripts/nightly_music.py` |
| API wrapper | `scripts/minimax_music_api.py` |
| Trending fetcher | `scripts/fetch_trending.py` |
| Dedup checker | `scripts/check-duplicate.py` |
| Visualizer | `scripts/nightly_visualizer.py` |
| YouTube uploader | `scripts/nightly_uploader.py` |
| **Song quality** | **`scripts/song_quality.py`** (Phase 2) |
| **Weekly themes** | **`scripts/weekly_themes.py`** (Phase 2) |
| **Weekly compilation** | **`scripts/nightly_compilation.py`** (Phase 2) |
| **Prompt generation** | **`scripts/prompt_gen.py`** (Phase 2) |
| **Image generation** | **`scripts/image_gen.py`** (Phase 2) |
| Config | `config/nightly-music.yaml` |
| Growth strategy | `docs/GROWTH_STRATEGY.md` |
| Channel about | `docs/CHANNEL_ABOUT.md` |
| Output | `output/YYYY-MM-DD/` |
| Song log | `output/YYYY-MM-DD/..` (JSON logs in output dir) |
| Cron log | `logs/nightly_music.log` |
