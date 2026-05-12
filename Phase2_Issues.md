# Phase 2: Nightly AI Music — YouTube Channel

> **STALE — Phase 1 issues tracker snapshot.** This document tracked Phase 2 issues as of 2026-05-07. All open issues (YouTube upload, trending research, Telegram delivery) are now resolved. See [README.md](README.md) for current state and [EXECUTION_PLAN.md](EXECUTION_PLAN.md) for completion tracking.

**Project:** Nightly AI Music / YouTube Channel
**Phase 1 status:** ✅ Deployed and complete (2026-05-12)
**Phase 2 owner:** Dennis Ng (with Hermes support)
**Created:** 2026-05-07

---

## Open Issues

| # | Issue | Owner | Next Step | Status |
|---|-------|-------|----------|--------|
| 1 | **YouTube upload** — Fully automated. `nightly_uploader.py` uses YouTube Data API v3 with OAuth. Videos upload daily at 6pm SGT. | Dennis | Done. First videos live: [晴天](https://youtube.com/watch?v=2plnyTSExQE), [我只能离开](https://youtube.com/shorts/niijYd3WZk8). | ✅ Resolved |
| 2 | **Lyrics placeholder retry** — Fixed with 2x retry in `minimax_music_api.py`. Issue resolved. | Hermes | Done. | ✅ Resolved |
| 3 | **Trending song research** — Replaced with `fetch_trending.py` that fetches QQ Music, KKBOX, and MY FM via requests (no Selenium needed). Falls back to curated pool. | Hermes | Done. Running nightly. | ✅ Resolved |
| 4 | **Telegram delivery confirm** — Switched to `sendMediaGroup` batching. Telegram delivery confirmed working. | Hermes | Done. | ✅ Resolved |

---

## YouTube Upload — Decision Needed

Before Phase 2 can proceed, Boss needs to decide:

1. **Channel setup:** What is the YouTube channel name? Who owns it?
2. **Upload approach:** 
   - **Option A (Manual):** Boss downloads from Telegram → uploads to YouTube manually. Simple, no API needed.
   - **Option B (Automated):** Use YouTube Data API v3 with OAuth. Requires Google Cloud project + channel verification. Hermes can automate end-to-end.

---

## Phase 1 Success Check (Trial ends 2026-05-13)

| Metric | Target | Current |
|--------|--------|---------|
| Successful generations | ≥12/14 songs | 6/6 (as of 2026-05-06) ✅ |
| Placeholder lyrics events | 0 | 2 retries caught in Phase 1 — fix deployed ✅ |
| Morning Telegram delivery | 7/7 days | Night 1 ✅, Night 2 ✅, pending 5 more |
| D-drive sync | 7/7 days | ✅ confirmed |

---

## Superseded from Phase 1

- ~~Web search trending (TikTok SG)~~ — Not working (needs Selenium). Replaced with curated pool.
- ~~SoulX API~~ — Dead end (2026-04 shut down). MiniMax confirmed as working provider.
- ~~2-step MiniMax workflow (manual lyrics + music)~~ — Merged into `generate_and_save` single call.

---

## Related Files

- Pipeline script: `~/.hermes/scripts/nightly_music.py`
- API wrapper: `~/.hermes/scripts/minimax_music_api.py`
- Song log: `~/.hermes/work_logs/nightly-songs/song-log.json`
- Phase 1 plan: `~/.hermes/pending-projects/nightly-ai-music-youtube/Project_Instruction.md`
