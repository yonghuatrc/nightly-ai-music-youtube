# Execution Plan: Nightly AI Music YouTube Channel

Date: 2026-05-12 (updated 2026-05-12)
Status: ✅ Phase 1 complete — pipeline runs nightly at 2am SGT

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
| P4 | Create OAuth 2.0 Desktop credentials | Download JSON → save to `~/.hermes/secrets/youtube-oauth.json` |
| P5 | Install Python deps | `pip install google-auth google-auth-oauthlib google-api-python-client` |
| P6 | Install CJK font (if missing) | `sudo apt install fonts-noto-cjk` |
| P7 | Prepare 5-10 background images | Download from Unsplash/Pexels → `~/.hermes/songs/assets/backgrounds/` |
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

## Phase 2: Multi-Agent Architecture (deferred)

| Feature | Description |
|---------|-------------|
| Multi-agent coordinator | Cron trigger → orchestrates gen → viz → distro → growth flow |
| Animated visualizers | moviepy/manim with particle effects, karaoke lyrics |
| 10 songs configurable | Trending chart integration (QQ Music, NetEase, Kugou) |
| YouTube Shorts | Auto-clip top 3 songs → 60s vertical format |
| Growth agent | Cross-posting (Twitter, Bilibili), analytics + strategy |
| Async generation | Parallel MiniMax API calls for 10 songs |

---

## Status Tracking

| Phase | Status | Date Completed |
|-------|--------|----------------|
| Phase 1a — Bug fixes | ✅ Complete | 2026-05-12 |
| Phase 1b — Prerequisites | ✅ Complete | 2026-05-12 |
| Phase 1b — Implementation | ✅ Complete | 2026-05-12 |
| Phase 1b — DRY RUN | ✅ Complete | 2026-05-12 |
| Phase 1b — YouTube Upload | ✅ Complete | 2026-05-12 |
| Phase 2 — Multi-agent | ⬜ Deferred | — |

---

## Reference: Original Phase 1 Specs (from 2026-05-05)

Preserved from the original `Project_Instruction.md` specification. These defined the initial pipeline before YouTube integration.

### Log Format

**File:** `~/.hermes/work_logs/nightly-songs/song-log.json` (monthly rotation: `song-log-YYYY-MM.json`)

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
  "output_file": "/home/dennis/.hermes/nightly-songs/2026-05-05-song-1.mp3",
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
| Pipeline script | `scripts/nightly_music.py` |
| API wrapper | `scripts/minimax_music_api.py` |
| Trending fetcher | `scripts/fetch_trending.py` |
| Dedup checker | `scripts/check-duplicate.py` |
| Visualizer | `scripts/nightly_visualizer.py` |
| YouTube uploader | `scripts/nightly_uploader.py` |
| Config | `config/nightly-music.yaml` |
| Output | `output/YYYY-MM-DD/` |
| Song log | `output/YYYY-MM-DD/..` (JSON logs in output dir) |
| Cron log | `logs/nightly_music.log` |
