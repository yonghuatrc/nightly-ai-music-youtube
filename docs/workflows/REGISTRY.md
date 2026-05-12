# Workflow Registry — ManggoMusicCH Nightly Pipeline

**Last updated**: 2026-05-12
**Maintainer**: Workflow Architect

---

## View 1: By Workflow (Master List)

| Workflow | Spec file | Status | Trigger | Primary actor | Last reviewed |
|---|---|---|---|---|---|
| Main nightly pipeline | — (in code) | Approved | CRON 2am SGT | `nightly_music.py` | 2026-05-12 |
| Trending song fetch | — (in code) | Approved | Main pipeline Step 2 | `fetch_trending.py` | 2026-05-12 |
| Dedup check | — (in code) | Approved | Main pipeline Step 2.5 | `check-duplicate.py` | 2026-05-12 |
| Song generation (MiniMax) | — (in code) | Approved | Main pipeline Step 3 | `minimax_music_api.py` | 2026-05-12 |
| Visualizer generation (1920×1080) | — (in code) | Approved | Main pipeline Step 4 | `nightly_visualizer.py` | 2026-05-12 |
| YouTube full video upload | — (in code) | Approved | Main pipeline Step 5 | `nightly_uploader.py` | 2026-05-12 |
| D-drive sync | — (in code) | Approved | Main pipeline Step 6 | `sync_to_d_drive()` | 2026-05-12 |
| Song logging | — (in code) | Approved | Main pipeline Step 7 | `append_log()` | 2026-05-12 |
| Telegram delivery | — (in code) | Approved | Main pipeline Step 8 | `send_telegram_batch()` | 2026-05-12 |
| **YouTube Shorts generation** | WORKFLOW-youtube-shorts.md | **Draft** | Main pipeline hook after song gen | `nightly_shorts.py` (NEW) | 2026-05-12 |

---

## View 2: By Component (Code → Workflows)

| Component | File(s) | Workflows it participates in |
|---|---|---|
| Pipeline orchestrator | `nightly_music.py` | ALL workflows — entry point for every step |
| Trending fetcher | `fetch_trending.py` | Trending song fetch |
| Dedup checker | `check-duplicate.py` | Dedup check |
| MiniMax API wrapper | `minimax_music_api.py` | Song generation |
| Visualizer | `nightly_visualizer.py` | Visualizer generation, Thumbnail generation |
| YouTube uploader | `nightly_uploader.py` | YouTube full video upload, YouTube Shorts upload |
| Image generator | `image_gen.py` | Visualizer generation (background), YouTube Shorts (background) |
| **Shorts orchestrator** | **`nightly_shorts.py` (NEW)** | **YouTube Shorts generation** |
| Config | `nightly-music.yaml` | ALL workflows (config affects behavior of all) |

---

## View 3: By Journey (User-Facing → Workflows)

### Customer Journeys
| What the customer experiences | Underlying workflow(s) | Entry point |
|---|---|---|
| Full music video appears on channel at 6pm SGT | Song generation → Visualizer → YouTube upload | CRON 2am SGT |
| **Short video appears on channel at 12pm SGT** | **Song generation → Shorts generation → YouTube upload** | **CRON 2am SGT** |
| Telegram notification with songs + links | Telegram delivery | CRON 2am SGT |
| **Telegram notification includes Short link** | **Telegram delivery (+ Short injection)** | **CRON 2am SGT** |

### Operator Journeys
| What the operator does | Underlying workflow(s) | Entry point |
|---|---|---|
| Checks nightly output | Song logging, D-drive sync | Output directory |
| Investigates generation failure | Song generation, Telegram delivery | Logs |
| Adjusts song count/sources | Config reload (all workflows) | night-music.yaml edit |
| Tests pipeline manually | All (dry run mode) | `--dry-run` CLI flag |

---

## View 4: By State (Entity States → Workflows)

| State | Entered by | Exited by | Workflows that can trigger exit |
|---|---|---|---|
| `pending` (song) | Song generation start | → `generating` | Song generation (MiniMax) |
| `generating` (song) | Song generation call | → `success`, `failed` | Song generation |
| `success` (song) | Song generation complete | — (terminal for gen) | Visualizer, Shorts, Upload |
| `failed` (song) | Song generation failure | — (terminal) | — |
| `selected` (short candidate) | Shorts Step 0 | → `chorus_detecting`, `skipped` | Shorts generation |
| `chorus_detecting` | Shorts Step 1 | → `audio_extracting`, `skipped` | Shorts generation |
| `audio_extracting` | Shorts Step 2 | → `background_generating`, `skipped` | Shorts generation |
| `background_generating` | Shorts Step 3 | → `rendering`, `rendering (fallback)` | Shorts generation |
| `rendering` | Shorts Step 4 | → `uploading`, `skipped` | Shorts generation |
| `uploading` | Shorts Step 5 | → `completed`, `skipped` | Shorts generation |
| `completed` (Short) | Shorts Step 5 (upload OK) | — (terminal) | — |
| `skipped` (Short) | Any Shorts step failure | — (terminal, non-fatal) | — |
