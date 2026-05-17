# Genre-Based Daily Song Selection — Implementation Plan

> **For:** Minimal Change Engineer  
> **Follow strictly.** Every step has exact file paths, code snippets, and verification commands. No ambiguity.

## Overview

Replace random trending song selection with genre-based daily rotation:
- Mon=抒情, Tue=古风, Wed=仙侠, Thu=抒情, Fri=摇滚, Sat=R&B, Sun=古风

**5 files changed, 4 phases, ~8-10h total**

---

## Phase 1: Genre Rotation + Prompt Keywords (~2h)

### Step 1.1: Create `scripts/genre_rotation.py`

New file with daily genre schedule and metadata.

```python
#!/usr/bin/env python3
"""Daily genre rotation for ManggoMusicCH."""

import datetime

GENRE_SCHEDULE = {
    0: "抒情",  # Monday
    1: "古风",  # Tuesday
    2: "仙侠",  # Wednesday
    3: "抒情",  # Thursday
    4: "摇滚",  # Friday
    5: "R&B",   # Saturday
    6: "古风",  # Sunday
}

GENRE_METADATA = {
    "抒情": {"emoji": "🌅", "style": "华语抒情流行"},
    "古风": {"emoji": "💔", "style": "华语古风"},
    "仙侠": {"emoji": "💌", "style": "华语仙侠"},
    "摇滚": {"emoji": "🎉", "style": "华语摇滚"},
    "R&B":  {"emoji": "🌟", "style": "华语R&B"},
}

def get_daily_genre(date_str=None):
    if date_str:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    else:
        dt = datetime.datetime.now()
    return GENRE_SCHEDULE.get(dt.weekday(), "抒情")

def get_genre_metadata(genre):
    return GENRE_METADATA.get(genre, {"emoji": "🎵", "style": "华语流行"})
```

Verify: `python3 scripts/genre_rotation.py --all` should output Mon-Sun schedule.

### Step 1.2: Create `scripts/genre_keywords.py`

New file with genre-specific keywords for MiniMax prompts.

```python
#!/usr/bin/env python3
"""Genre-specific prompt keywords for MiniMax."""

import random

GENRE_KEYWORDS = {
    "抒情": {
        "genres": ["华语流行抒情", "华语情歌", "抒情慢歌"],
        "instruments": ["钢琴为主", "弦乐铺底", "吉他与钢琴"],
        "vocals": ["温暖男声", "温柔女声", "深情男声", "治愈女声"],
        "moods": ["情感充沛", "深情款款", "旋律朗朗上口", "治愈温暖"],
    },
    "古风": {
        "genres": ["华语古风", "华语中国风", "国风抒情"],
        "instruments": ["古筝与笛", "琵琶与弦乐", "传统乐器与钢琴"],
        "vocals": ["古风女声", "清澈男声", "空灵女声", "诗意男声"],
        "moods": ["古韵悠长", "诗意盎然", "中国风意境", "典雅优美"],
    },
    "仙侠": {
        "genres": ["华语仙侠风", "古风燃曲", "华语武侠"],
        "instruments": ["古筝与鼓", "弦乐与编钟", "琵琶与笛", "钢琴与古筝"],
        "vocals": ["空灵女声", "清澈男声", "深情男声", "仙气女声"],
        "moods": ["仙气缭绕", "意境悠远", "大气磅礴", "荡气回肠"],
    },
    "摇滚": {
        "genres": ["华语摇滚", "流行摇滚", "轻摇滚"],
        "instruments": ["吉他与鼓", "电吉他与贝斯", "摇滚乐队"],
        "vocals": ["磁性男声", "有力嗓音", "激昂男声", "爆发力女声"],
        "moods": ["节奏明快", "副歌爆发", "激昂有力", "热血沸腾"],
    },
    "R&B": {
        "genres": ["华语R&B", "R&B抒情", "节奏蓝调"],
        "instruments": ["钢琴与鼓", "电子节拍", "贝斯与吉他"],
        "vocals": ["灵魂唱腔", "温柔声线", "磁性男声", "丝滑女声"],
        "moods": ["节奏感强", "旋律丝滑", "律动十足", "慵懒浪漫"],
    },
}

def get_genre_dimensions(genre):
    return GENRE_KEYWORDS.get(genre, GENRE_KEYWORDS["抒情"])

def build_genre_style_prompt(song, artist, genre):
    dims = get_genre_dimensions(genre)
    g = random.choice(dims["genres"])
    i = random.choice(dims["instruments"])
    v = random.choice(dims["vocals"])
    m = random.choice(dims["moods"])
    return f"类似{artist}的《{song}》风格，{g}，{i}，{v}，{m}"
```

Verify: `python3 scripts/genre_keywords.py --genre 古风`

### Step 1.3: Modify `scripts/fetch_trending.py`

Changes:
1. Add `"华语仙侠风"` to GENRES list (line 29)
2. Modify `build_style_prompt(song, artist, genre=None)` — accept optional genre param
3. Add `genre=None` param to ALL 5 fetcher functions: `fetch_qq_douyin()`, `fetch_kkbox()`, `fetch_myfm()`, `fetch_generic()`, `fetch_pool()`
4. Add `--genre` CLI argument to `main()`

### Step 1.4: Modify `scripts/nightly_music.py`

Changes:
1. Import `get_daily_genre` from `genre_rotation`
2. Add `"netease"` to `KNOWN_SOURCES` set
3. Modify `fetch_trending(sources, count, genre=None)` signature
4. In `run_pipeline()`, determine genre after config load, pass to fetch

### Step 1.5: Update `config/nightly-music.yaml`

Add genre config sections at end of file.

---

## Phase 2: NetEase Source + Genre-Aware Pipeline (~3h)

### Step 2.1: Add NetEase fetcher to `fetch_trending.py`

New function `fetch_netease(count=15, genre=None)` before `fetch_pool()`. Uses NetEase Cloud Music playlist detail API.

### Step 2.2: Update config sources

Add `"netease"` as first trending source in config.

---

## Phase 3: Per-Genre YouTube Metadata (~1h)

### Step 3.1: Add genre tags to config

### Step 3.2: Modify `upload_to_youtube()` and `upload_shorts_to_youtube()`

Add `genre=None` param. Append genre-specific tags. Update descriptions with genre label.

### Step 3.3: Add genre to log entries

---

## Phase 4: Testing (~3h)

- Compile check all files
- Test genre rotation for all 7 days
- Test genre keyword prompts for all 5 genres
- Test fetch_trending with/without genre
- Test pipeline dry-run for each genre day
- Test backward compatibility (genre disabled)
- Test NetEase fetcher (best-effort)
- Full assertions test

## Commit

```bash
git add -A && git commit -m "feat: genre-based daily song selection (抒情/古风/仙侠/摇滚/R&B)" && git push
```
