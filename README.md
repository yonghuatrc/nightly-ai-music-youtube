# Nightly AI Music YouTube Channel

> AI-generated music that's actually good — uploaded daily to YouTube with visualizers. Full pipeline: trending fetch → dedup → MiniMax music gen → FFmpeg visualizer → YouTube upload → Telegram delivery.

**Status:** Phase 1 complete, running nightly  
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
  ├── 3. Generate 2 songs via MiniMax Music API
  ├── 4. Generate MP4 visualizer (FFmpeg waveform + album art)
  ├── 5. Upload to YouTube (scheduled for 6pm SGT)
  ├── 6. Sync to D-drive mirror
  └── 7. Send Telegram batch (summary + links + files)
```

---

## Project Structure

```
nightly-ai-music-youtube/
├── scripts/
│   ├── nightly_music.py          # Pipeline orchestrator
│   ├── nightly_visualizer.py     # FFmpeg waveform MP4 generator
│   ├── nightly_uploader.py       # YouTube Data API v3 uploader
│   ├── minimax_music_api.py      # MiniMax Music API wrapper
│   ├── fetch_trending.py         # Multi-source trending song fetcher
│   └── check-duplicate.py        # 7-day dedup checker
├── config/
│   └── nightly-music.yaml        # Song count, language, YouTube, visualizer settings
├── assets/
│   └── backgrounds/              # Visualizer background images
├── output/
│   └── YYYY-MM-DD/               # Per-night output (MP3, TXT, MP4)
├── docs/                         # Design docs, execution plans, issues
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
| `visualizer.enabled` | `true` | Enable FFmpeg visualizer |
| `visualizer.resolution` | `"1920x1080"` | Output resolution |
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

- **Videos:** [AI Music — 周杰伦 晴天风格](https://www.youtube.com/watch?v=2plnyTSExQE)
- **Shorts:** [我只能离开风格 (Short)](https://www.youtube.com/shorts/niijYd3WZk8)
- Uploads scheduled for 6pm SGT (peak viewing hours)
- Privacy: currently set to private during testing

---

## Phase 2 Roadmap

| Feature | Description |
|---------|-------------|
| Multi-agent coordinator | Cron trigger → orchestrates gen → viz → distro → growth |
| Animated visualizers | moviepy/manim with particle effects, karaoke lyrics |
| 10 songs configurable | Scale up via trending chart integration |
| YouTube Shorts | Auto-clip top songs → 60s vertical format |
| Growth agent | Cross-posting (Twitter, Bilibili), analytics + strategy |
| Async generation | Parallel MiniMax API calls for N songs |

---

## Documentation Index

| File | Purpose |
|------|---------|
| [DESIGN.md](DESIGN.md) | Why we built it this way — office-hours design record |
| [EXECUTION_PLAN.md](EXECUTION_PLAN.md) | What's done, what's next — living tracker + original Phase 1 specs |

---

## License

Private project — Dennis Ng, 2026.
