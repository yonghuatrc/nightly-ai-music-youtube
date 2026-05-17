# Nightly AI Music YouTube Channel

> AI-generated music that's actually good — uploaded daily to YouTube with visualizers. Full pipeline: trending fetch → dedup → MiniMax music gen → FFmpeg visualizer → YouTube upload → Telegram delivery.

**Status:** Phase 2 complete — quality-gated pipeline running nightly  
**Schedule:** 2am SGT daily via crontab  
**First videos:** [晴天风格](https://www.youtube.com/watch?v=2plnyTSExQE) · [我只能离开风格](https://www.youtube.com/shorts/niijYd3WZk8)

---

## Why This Exists

AI song generation has reached quality levels worth sharing, but most AI music sits in a folder somewhere. This project automates the entire pipeline — from picking trending songs to publishing polished YouTube videos — so there's fresh AI-generated music every day with zero manual effort. The pitch: "AI songs can be good. Here's proof, every day."

---

## How It Works

```
CRON (2am SGT)
  │
  ▼
nightly_music.py --date YYYY-MM-DD
  │
  ├── 1. Fetch trending Chinese songs (QQ Music, KKBOX, MY FM)
  ├── 2. Dedup against last 7 days (check-duplicate.py)
  ├── 3. Apply weekly theme modifier (weekly_themes.py)             ← Phase 2
  ├── 4. Generate 2 songs via MiniMax Music API
  ├── 5. Score song quality (song_quality.py)                        ← Phase 2
  │      ├── Hero ≥ 6   → full treatment
  │      ├── Standard ≥ 4 → basic treatment
  │      └── Reject < 4 → dropped
  ├── 6. Generate image prompt from lyrics (prompt_gen.py)           ← Phase 2
  ├── 7. Download background image (image_gen.py)                    ← Phase 2
  ├── 8. Detect mood → color palette (7 themes)                     ← Phase 2
  ├── 9. Generate MP4 visualizer (FFmpeg waveform + mood colors)
  │      └── SRT subtitle overlay on long-form                      ← Phase 2
  ├── 10. Generate YouTube Shorts (30s, 9:16)                       ← Phase 2
  ├── 11. Upload to YouTube (staggered schedule)
  │       ├── Hero → 18:00 SGT
  │       ├── Standard → 20:00 SGT
  │       └── Shorts → 12:00 SGT
  ├── 12. Sync to output/ directory
  └── 13. Send Telegram batch (summary + links + files)
       │
       ▼
  SUNDAY ONLY: nightly_compilation.py                               ← Phase 2
       │
       └── FFmpeg concat Mon-Sat Hero videos → album upload
```

---

## Project Structure

```
nightly-ai-music-youtube/
├── scripts/
│   ├── nightly_music.py          # Pipeline orchestrator
│   ├── nightly_visualizer.py     # FFmpeg waveform MP4 generator + SRT
│   ├── nightly_uploader.py       # YouTube Data API v3 uploader
│   ├── nightly_compilation.py    # Weekly album concat (Sunday)     ← P2
│   ├── minimax_music_api.py      # MiniMax Music API wrapper
│   ├── fetch_trending.py         # Multi-source trending song fetcher
│   ├── check-duplicate.py        # 7-day dedup checker
│   ├── song_quality.py           # 5-dimension quality scoring       ← P2
│   ├── weekly_themes.py          # Day-of-week mood modifiers        ← P2
│   ├── prompt_gen.py             # LLM-based image prompt gen        ← P2
│   └── image_gen.py              # Pollinations.ai image download    ← P2
├── config/
│   └── nightly-music.yaml        # Quality gate, shorts, themes, compilation
├── assets/
│   ├── backgrounds/              # Visualizer background images
│   └── branding/                 # Channel logo + banner             ← P2
├── output/
│   └── YYYY-MM-DD/               # Per-night output (MP3, TXT, MP4, SRT, Shorts)
├── docs/                         # Design docs, growth strategy, issues
│   ├── GROWTH_STRATEGY.md        # 500-sub growth plan               ← P2
│   └── CHANNEL_ABOUT.md          # YouTube About section             ← P2
├── logs/                         # Pipeline run logs
├── .env.example                  # Environment variable template
└── .gitignore
```

---

## Configuration

Edit `config/nightly-music.yaml` to change behavior — no code changes needed:

| Key | Default | Description |
|-----|---------|-------------|
| `song_count` | `2` | Songs per night |
| `language` | `"chinese-only"` | `"chinese-only"`, `"mixed"`, or list like `["Chinese", "English"]` |
| `trending_source` | `["qq-douyin", "kkbox", "my-fm"]` | Sources tried in order, deduplicated |
| `youtube.enabled` | `true` | Enable YouTube upload |
| `youtube.privacy` | `"private"` | `"private"`, `"unlisted"`, or `"public"` |
| `quality_gate.enabled` | `true` | Score songs and filter weak ones (Phase 2) |
| `quality_gate.hero_threshold` | `6.0` | Score for premium treatment (Phase 2) |
| `quality_gate.standard_threshold` | `4.0` | Score for basic treatment (Phase 2) |
| `visualizer.enabled` | `true` | Enable FFmpeg visualizer |
| `visualizer.resolution` | `"1920x1080"` | Output resolution |
| `visualizer.lyrics_overlay` | `true` | Burn SRT subtitles into long-form (Phase 2) |
| `visualizer.mood_colors` | `true` | Dynamic mood-based palette (Phase 2) |
| `shorts.enabled` | `true` | Generate YouTube Shorts (Phase 2) |
| `shorts.duration_sec` | `30` | Shorts length in seconds (Phase 2) |
| `shorts.upload_time` | `"12:00"` | Shorts scheduled publish time (Phase 2) |
| `weekly_themes.enabled` | `true` | Day-of-week mood modifiers (Phase 2) |
| `compilation.enabled` | `true` | Sunday album concat (Phase 2) |
| `telegram.songs_per_message` | `5` | Songs per Telegram batch |

---

## Setup

### Prerequisites
- Python 3.12+ with venv at `~/.hermes/venv/`
- FFmpeg 6.1.1+ (for visualizer)
- CJK font: `sudo apt install fonts-noto-cjk` (for Chinese song metadata)
- MiniMax API key in `~/.hermes/.env`
- Telegram bot token in `~/.hermes/.env`

### YouTube OAuth (one-time setup)
```bash
python3 scripts/nightly_uploader.py --setup-auth
```
This opens a browser for Google OAuth consent. Tokens are saved to `/mnt/d/Hermes/secrets/youtube-oauth*.json` and auto-refreshed.

### Dry Run
```bash
python3 scripts/nightly_music.py --date $(date +%Y-%m-%d)
```

### Cron Job
```
# Runs at 2am SGT daily
0 2 * * * cd /mnt/d/Hermes/pending-projects/nightly-ai-music-youtube && /home/dennis/.hermes/venv/bin/python3 scripts/nightly_music.py --date $(date +\%Y-\%m-\%d) >> logs/nightly_music.log 2>&1
```

---

## Secrets & Credentials

All secrets live outside the repo:

| File | Purpose |
|------|---------|
| `~/.hermes/.env` | MiniMax API key, Telegram bot token |
| `/mnt/d/Hermes/secrets/youtube-oauth*.json` | YouTube OAuth tokens |

---

## YouTube Channel

- **Channel:** [ManggoMusicCH](https://www.youtube.com/@ManggoMusicCH)
- **Long-form videos:** Quality-gated Hero (18:00 SGT) + Standard (20:00 SGT)
- **Shorts (30s):** Clipped from chorus section, uploaded at 12:00 SGT
- **Weekly compilation (Sunday):** Album-style concat of Mon-Sat Hero videos
- Privacy: currently set to private during testing
- See [docs/CHANNEL_ABOUT.md](docs/CHANNEL_ABOUT.md) for channel branding setup

---

## Phase 2 — Complete (2026-05-14)

All Phase 2 features are shipped. The old "10 songs/day, multi-agent" plan was replaced with a quality-gated strategy.

| Feature | Description | Status |
|---------|-------------|--------|
| Quality gating | Score 0-10 on 5 dimensions. Hero ≥6, Standard ≥4, reject <4 | ✅ |
| Mood-based colors | 7 mood palettes from lyrics keywords (LLM + rule-based) | ✅ |
| SRT on long-form | Full-song timed subtitles via FFmpeg `subtitles=` filter | ✅ |
| Staggered schedule | Hero 18:00, Standard 20:00, Shorts 12:00 | ✅ |
| Shorts 30s | Clipped from chorus, 9:16 vertical | ✅ |
| Weekly themes | Day-of-week mood modifiers in prompts | ✅ |
| Weekly compilation | Sunday FFmpeg concat → album upload | ✅ |
| E2E testing + tuning | Calibrated thresholds, fixed B1-B4 bugs (ordering + Shorts frame/seconds) | ✅ |

### What's Next

- Monitor quality gate calibration after 7+ days of scoring data
- Review subscriber growth against 500-target trajectory
- Tune mood detection accuracy from real song feedback

---

## Documentation Index

| File | Purpose |
|------|---------|
| [DESIGN.md](DESIGN.md) | Why we built it this way — office-hours design record |
| [EXECUTION_PLAN.md](EXECUTION_PLAN.md) | What's done, what's next — living tracker + Phase 1 & 2 specs |
| [Phase2_Issues.md](Phase2_Issues.md) | Phase 2 issue backlog and Sprint tracker |
| [docs/CHANNEL_ABOUT.md](docs/CHANNEL_ABOUT.md) | YouTube channel setup guide |

---

## License

Private project — Dennis Ng, 2026.
