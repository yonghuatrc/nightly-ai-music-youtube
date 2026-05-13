# Phase 2: ManggoMusicCH — Growth Strategy Pipeline

**Project:** Nightly AI Music / YouTube Channel (ManggoMusicCH)
**Phase 1 status:** ✅ Deployed (2026-05-05), running nightly at 2am SGT
**Phase 2 owner:** Dennis Ng (with Hermes support)
**Created:** 2026-05-07
**Updated:** 2026-05-14 — New strategy consensus (3-expert growth plan)

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

## Open Issues

| # | Issue | Owner | Next Step | Status |
|---|-------|-------|----------|--------|
| 1 | ✅ **YouTube upload** — Automated via YouTube Data API v3, OAuth working, tested 2026-05-12 | Dennis | Confirmed operational | ✅ Complete |
| 2 | 🟡 **Mood detection accuracy** — MiniMax LLM-based mood classification from Chinese lyrics. Needs real-song testing to validate. | Hermes | Run 5 test songs through mood detector, compare LLM vs human judgment | 🟡 Next sprint |
| 3 | 🟡 **Weekly theme differentiation** — MiniMax may ignore theme modifiers in prompts. Need to verify by generating same prompt with/without theme modifier. | Hermes | A/B test: generate 2 songs with same trend but different themes, compare output | 🟡 Next sprint |
| 4 | 🟡 **SRT timing alignment** — Full-song SRT distributes lines evenly. May look unnatural. Consider section-aligned timing using `[Verse]`/`[Chorus]` markers. | Hermes | Prototype section-aware SRT, compare visual quality | 🟡 Next sprint |
| 5 | 🟡 **Compilation concat compatibility** — FFmpeg concat may fail on videos with different codec params. Need re-encode fallback tested. | Hermes | Test concat on 3 existing MP4s from output dir | 🟡 Next sprint |
| 6 | 🟡 **Quality scoring calibration** — Scoring thresholds (6/10 Hero, 4/10 Standard) are guessed. Need real output to tune. | Hermes | After 7 days of scoring data, review distribution and adjust thresholds | 🟡 After 7 runs |

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

| Sprint | Deliverables |
|--------|-------------|
| **Sprint 1** | Quality gating module, mood detection, SRT on long-form, dynamic visualizer colors |
| **Sprint 2** | Staggered upload scheduling, Shorts 30s change, weekly theme modifiers, config updates |
| **Sprint 3** | Weekly compilation module (`nightly_compilation.py`), concat pipeline, compilation upload |
| **Sprint 4** | E2E testing, threshold tuning, monitoring setup, documentation |

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
