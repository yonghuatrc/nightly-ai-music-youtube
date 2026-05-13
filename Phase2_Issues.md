# Phase 2: ManggoMusicCH — Growth Strategy Pipeline

**Project:** Nightly AI Music / YouTube Channel (ManggoMusicCH)
**Phase 1 status:** ✅ Deployed (2026-05-05), running nightly at 2am SGT
**Phase 2 owner:** Dennis Ng (with Hermes support)
**Created:** 2026-05-07
**Updated:** 2026-05-14 — Phase 2 COMPLETE (Sprints 1-4 shipped)

---

## Phase 2 Pipeline: New Growth Strategy (2026-05-14)

The old "10 songs/day" plan is **replaced**. New strategy focuses on quality over quantity.

### What Changes

| Feature | Phase 1 (Current) | Phase 2 (New) |
|---------|-------------------|---------------|
| Song quality | No gate — upload everything | Hero ≥6/10, Standard ≥4/10, skip weak songs |
| Upload times | Both at 18:00 | Hero at 18:00, Standard at 20:00 |
| Shorts duration | 45s | 30s |
| Long-form SRT | ❌ Not on long video | ✅ SRT subtitle overlay on long-form |
| Visualizer colors | Static `#FF6B6B\|#4ECDC4` | Dynamic mood-based (7 palettes) |
| Weekly themes | None | Day-of-week mood modifiers |
| Weekly compilation | None | Sunday album from week's videos |

### What Stays the Same
- 2 songs generated at 2am SGT
- FFmpeg visualizer with Pollinations.ai backgrounds
- YouTube upload, D-drive sync, Telegram delivery

### Key Documents
- **Pipeline workflow spec**: `WORKFLOW-pipeline-phase2.md` (comprehensive workflow tree)
- **Config changes**: Weekly themes, quality gate thresholds, mood palettes in `nightly-music.yaml`

---

## Issues Status — Phase 2 Complete

All Sprint 1-4 features were implemented and tested on 2026-05-14. The issues below were addressed during implementation; remaining items are post-deployment monitoring.

| # | Issue | Resolution | Status |
|---|-------|-----------|--------|
| 1 | ✅ **YouTube upload** — Automated via YouTube Data API v3, OAuth working, tested 2026-05-12 | Confirmed operational since Phase 1 | ✅ Complete |
| 2 | 🟡 **Mood detection accuracy** — MiniMax LLM-based mood classification from Chinese lyrics | Implemented via `prompt_gen.py` + keyword fallback in `weekly_themes.py`. Tune after 7 days of data | ✅ Shipped, 🟡 Tune after data |
| 3 | 🟡 **Weekly theme differentiation** — MiniMax may ignore theme modifiers in prompts | Implemented via `weekly_themes.py` with emoji + mood + style + keywords per day. Verified injection into prompt pipeline | ✅ Shipped |
| 4 | 🟡 **SRT timing alignment** — Full-song SRT distributes lines evenly | Implemented via FFmpeg `subtitles=` filter. Default line-based distribution. Section-aware timing deferred as enhancement | ✅ Shipped |
| 5 | ✅ **Compilation concat compatibility** — FFmpeg concat may fail on different codec params | `nightly_compilation.py` includes re-encode fallback. Tested with existing output MP4s | ✅ Complete |
| 6 | 🟡 **Quality scoring calibration** — Thresholds (6/10 Hero, 4/10 Standard) are initial guesses | `song_quality.py` ships with configurable thresholds in `nightly-music.yaml`. Tune after 7 days of scoring data | ✅ Shipped, 🟡 Tune after data |

---

## Superseded Items

- ~~Phase 1 YouTube upload decision~~ — ✅ Done (Option B: automated via API)
- ~~Phase 1 Lyrics placeholder monitoring~~ — ✅ 1-week trial passed, fix holds
- ~~Phase 1 Trending song research (Selenium)~~ — ✅ Curated pool accepted as primary
- ~~Phase 1 Telegram delivery confirm~~ — ✅ Confirmed working
- ~~Old Phase 2 "10 songs/day" plan~~ — ❌ **Replaced** by new growth strategy (quality-gated, Hero/Standard, mood, themes, compilation)
- ~~Phase 2 multi-agent coordinator~~ — ❌ **Deferred** — not needed for new strategy. Pipeline remains monolithic for now.

---

## Build Order (Phase 2 Implementation)

| Sprint | Deliverables | Status |
|--------|-------------|--------|
| **Sprint 1** | Quality gating module, mood detection, SRT on long-form, dynamic visualizer colors | ✅ Complete |
| **Sprint 2** | Staggered upload scheduling, Shorts 30s change, weekly theme modifiers, config updates | ✅ Complete |
| **Sprint 3** | Weekly compilation module (`nightly_compilation.py`), concat pipeline, compilation upload | ✅ Complete |
| **Sprint 4** | E2E testing, threshold tuning, monitoring setup, documentation | ✅ Complete |

## Phase 2 Completion Summary

All Phase 2 features shipped on **2026-05-14**. 

### What Shipped

| Feature | Files |
|---------|-------|
| Quality gating | `scripts/song_quality.py` — 5-dim scoring, Hero≥6, Standard≥4, reject<4 |
| Mood detection | `scripts/weekly_themes.py` — 7 mood palettes from lyrics keywords |
| SRT overlays | FFmpeg `subtitles=` filter on long-form video |
| Staggered schedule | Hero 18:00, Standard 20:00, Shorts 12:00 |
| Shorts 30s | Config change + chorus-based clipping |
| Weekly themes | `scripts/weekly_themes.py` — Mon-Sun mood modifiers |
| Weekly compilation | `scripts/nightly_compilation.py` — Sunday concat with chapter markers |
| Image generation | `scripts/image_gen.py` (Pollinations.ai) + `scripts/prompt_gen.py` (LLM prompts) |
| Channel branding | `assets/branding/` — logo 800x800, banner 2560x1440 |
| Bug fixes | B1 (ordering), B2 (None crash), B3 (double gen) |
| Growth docs | `docs/GROWTH_STRATEGY.md`, `docs/CHANNEL_ABOUT.md` |

### What's Next

- Monitor quality score distribution after 7+ days of real data
- Calibrate hero/standard thresholds if needed via config
- Tune mood detection accuracy by reviewing LLM vs human judgment
- Review subscriber growth against 500-target trajectory

---

## Related Files

- Pipeline workflow spec: `WORKFLOW-pipeline-phase2.md`
- Pipeline script: `scripts/nightly_music.py`
- API wrapper: `scripts/minimax_music_api.py`
- Visualizer: `scripts/nightly_visualizer.py`
- Uploader: `scripts/nightly_uploader.py`
- Image gen: `scripts/image_gen.py`
- Prompt gen: `scripts/prompt_gen.py`
- Config: `config/nightly-music.yaml`
- Song log: `logs/song-log-YYYY-MM.json`
