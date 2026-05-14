# Phase 2 Architecture — ManggoMusicCH Growth Strategy

> **Status:** Proposed (2026-05-14)
> **Supersedes:** Old Phase 2 plan (10 songs/day, multi-agent, async gen, growth agent)
> **Based on:** Expert consensus (Growth Hacker, SEO Specialist, Video Optimization Specialist)

---

## Table of Contents

1. [Architecture Decisions](#1-architecture-decisions)
2. [Module Structure](#2-module-structure)
3. [Config Schema](#3-config-schema)
4. [Quality Gate Design](#4-quality-gate-design)
5. [Lyrics SRT Overlay](#5-lyrics-srt-overlay)
6. [Mood Color System](#6-mood-color-system)
7. [Weekly Theme System](#7-weekly-theme-system)
8. [Compilation Generator](#8-compilation-generator)
9. [Pipeline State](#9-pipeline-state)
10. [Implementation Order](#10-implementation-order)
11. [What's Removed vs Kept](#11-whats-removed-vs-kept)

---

## 1. Architecture Decisions

### ADR-001: Staggered Schedule with Hero/Standard Tiers

| | Decision |
|---|----------|
| **Context** | Both songs currently scheduled at 18:00 SGT. YouTube algorithm treats them as a batch, not individual content. Also, not all songs are created equal — one is always better. |
| **Decision** | Score both songs via quality gate. Winner = **Hero** (scheduled at 18:00), loser = **Standard** (scheduled at 20:00). Shorts at 12:00 serve as teasers. |
| **Consequences** | + Two discovery windows instead of one. + Hero gets best metadata, thumbnail, visualizer. + Staggering avoids algorithm cannibalization. – More complex scheduling logic in uploader. |

### ADR-002: Song Quality Gate (Reject Low Quality)

| | Decision |
|---|----------|
| **Context** | MiniMax sometimes generates short songs (<90s), songs without chorus structure, or songs with placeholder lyrics. Uploading these hurts channel quality. |
| **Decision** | Score each song before upload: duration ≥120s, lyrics contain structure markers ([Chorus], [Verse]), lyrics length ≥100 chars. If BOTH songs fail gate, skip the day entirely. If one fails, only upload the other. |
| **Consequences** | + Consistent quality floor. + Prevents junk uploads. – Occasional skipped days. – Need to handle single-song days gracefully. |

### ADR-003: SRT Lyrics on Long-Form Videos (Reuse Existing Code)

| | Decision |
|---|----------|
| **Context** | Shorts already have SRT subtitles via `_generate_chorus_srt()`. Long-form videos have no lyrics overlay. This is the #1 ROI visualizer improvement. |
| **Decision** | Create `_generate_full_song_srt()` that distributes ALL lyrics lines across the full song duration (not just chorus). Reuse the same FFmpeg `subtitles=` filter from Shorts. Keep existing Shorts SRT code unchanged. |
| **Consequences** | + Highest subscriber value per dev hour. + Proven pattern (already works for Shorts). + ~20 lines of new code. – Longer videos (~3min) with subtitles require more rendering time. |

### ADR-004: Mood-Based Color Palettes from Lyrics

| | Decision |
|---|----------|
| **Context** | Visualizer currently uses hardcoded `#FF6B6B|#4ECDC4` waveform colors. Static colors regardless of song mood. |
| **Decision** | Extract mood keywords from lyrics → map to color palette → pass to FFmpeg `showwaves` colors parameter. Keyword→palette mapping table (Chinese + English keywords). |
| **Consequences** | + Higher visual engagement. + Mood-appropriate aesthetics. – Keyword matching is heuristic (won't be perfect). – Requires passing mood_colors through the pipeline. |

### ADR-005: Weekly Themes Influence Prompts

| | Decision |
|---|----------|
| **Context** | Songs feel same-y day after day. No sense of channel rhythm or anticipation. |
| **Decision** | Map day-of-week to mood descriptor. Inject into MiniMax prompt as modifier. Sunday gets "soft, gentle". Friday gets "dance, energetic". |
| **Consequences** | + Channel has rhythm. + Viewers develop expectations. – Some themes may underperform (iterate based on analytics). – Need to ensure prompt modifiers don't clash with trending song style. |

### ADR-006: Weekly Compilation (Sunday Album)

| | Decision |
|---|----------|
| **Context** | Subscribers who miss daily uploads have no easy way to catch up. Long-form albums drive watch time and session duration. |
| **Decision** | Every Sunday, concat all week's Hero and Standard videos into a single ~30-60min video using FFmpeg concat demuxer. Upload as "Week X — Best AI Songs [Compilation]". |
| **Consequences** | + Increased watch time. + Catch-up mechanism. + Album format performs well in search. – ~5-10 min additional rendering on Sunday. – Concat only (no transitions) in v1. |

### ADR-007: Remove 10 Songs/Day Scaling

| | Decision |
|---|----------|
| **Context** | Old plan scaled from 2→10 songs/day. Expert consensus: quality over quantity. 2 songs (Hero+Standard) + 2 Shorts is optimal. |
| **Decision** | Hard cap at 2 songs/day. No parallel MiniMax calls. No async gen agent. No growth agent. No quota management. |
| **Consequences** | + Lower API costs (~6,800 units/day, well within quota). + Simpler code. + More time per song for quality. – Lower raw output volume (but higher quality). |

---

## 2. Module Structure

### Changed Modules

| Module | Changes |
|--------|---------|
| `nightly_music.py` | Add `score_song()` quality gate. Add hero/standard tier assignment. Add staggered schedule handling. Add weekly theme prompt injection. |
| `nightly_visualizer.py` | Add `_generate_full_song_srt()` for long-form lyrics overlay. Add `_detect_mood_palette()` for mood colors. Import mood map from new module. |
| `nightly_uploader.py` | Accept `publish_at` per-song (hero at 18:00, standard at 20:00). Accept optional mood-based description modifiers. |
| `config/nightly-music.yaml` | New sections: `schedule`, `visualizer.lyrics_overlay`, `visualizer.mood_colors`, `quality_gate`, `weekly_themes`, `compilation`. |

### New Modules

| Module | File | Purpose |
|--------|------|---------|
| `quality_gate.py` | `scripts/quality_gate.py` | Song scoring, threshold check, hero/standard selection. |
| `mood_colors.py` | `scripts/mood_colors.py` | Keyword→palette mapping, mood detection from lyrics text. |
| `weekly_themes.py` | `scripts/weekly_themes.py` | Day-of-week mood mapping, prompt modifier generation. |
| `compilation.py` | `scripts/compilation.py` | Sunday concat of week's videos, upload as compilation. |
| `pipeline_state.py` | `scripts/pipeline_state.py` | Dataclass for passing state between pipeline stages (from old plan — keep). |

### Removed Modules (from old Phase 2 plan)

| Module | Reason |
|--------|--------|
| Async gen agent | Not needed (2 songs, sequential is fine) |
| Growth agent | Deferred — no YouTube Analytics API yet |
| Quota manager | Not needed (6,800 units/day is safe) |
| Multi-agent coordinator | Over-engineering for 2 songs |

### Files That Stay Unchanged

| File | Reason |
|------|--------|
| `fetch_trending.py` | No changes needed |
| `check-duplicate.py` | Already works |
| `minimax_music_api.py` | Already works |
| `image_gen.py` | Already works |
| `prompt_gen.py` | Already works |
| `nightly_uploader.py` | Minor: accept per-song `publish_at` |

---

## 3. Config Schema

```yaml
# Phase 2 — Revised Config
song_count: 2  # Hard cap. No longer configurable >2.

language: "chinese-only"

trending_source:
  - "qq-douyin"
  - "kkbox"
  - "my-fm"

telegram:
  songs_per_message: 5

d_drive_mirror: "/mnt/d/Hermes/songs/nightly-songs"

youtube:
  enabled: true
  privacy: "private"
  category: "10"
  tags:
    - "AI Music"
    - "华语流行"
    - "AISong"
    - "人工智能音乐"
    # ... (existing tags unchanged)

# ─── NEW: Schedule ─────────────────────────────────────────────────────
schedule:
  hero_time: "18:00"       # Best song of the day
  standard_time: "20:00"   # Second song (2h gap)

# ─── NEW: Visualizer Enhancements ──────────────────────────────────────
visualizer:
  enabled: true
  resolution: "1920x1080"
  hero_duration_max: 210    # 3:30 max for Hero
  standard_duration_max: 180 # 3:00 max for Standard
  lyrics_overlay: true       # #1 priority — SRT on long-form videos
  mood_colors: true          # Dynamic waveform colors from lyrics mood

# ─── Shorts ────────────────────────────────────────────────────────────
shorts:
  enabled: true
  duration_sec: 30           # REDUCED from 45s to 30s for higher sub conversion
  upload_time: "12:00"       # Noon teaser
  tags:
    - "#Shorts"
    - "AIMusic"
    - "华语流行"
    - "AI中文歌"
    - "AI歌曲"

# ─── NEW: Quality Gate ─────────────────────────────────────────────────
quality_gate:
  enabled: true
  min_song_duration: 120     # Seconds. Songs shorter than this are rejected.
  require_chorus_marker: true # Must have [Chorus] in lyrics structure
  min_lyrics_length: 100     # Characters. Placeholder lyrics fail this.
  # If BOTH songs fail gate → skip day entirely
  # If one fails → only upload the other as Hero
  # If both pass → score higher = Hero, lower = Standard

# ─── NEW: Weekly Themes ────────────────────────────────────────────────
weekly_themes:
  enabled: true
  # Day-of-week → mood modifier injected into MiniMax prompt
  # mapped in weekly_themes.py, but config overrides if set:
  # monday: "upbeat, energetic, fast tempo"
  # tuesday: "melancholy, slow tempo, minor key"
  # ... (full mapping in code, partial override here)

# ─── NEW: Weekly Compilation (Sunday Album) ────────────────────────────
compilation:
  enabled: true
  day: "sunday"
  duration_min: 1800         # 30 min minimum
  # Concat all Hero + Standard videos from Mon-Sat week.
  # Only generates on the configured day.

# Visual assets
visual:
  enabled: true
  generate_backgrounds: true
  generate_thumbnails: true
  llm_prompt_source: "minimax"
  pollinations_delay: 15

# API retry
max_lyrics_retries: 3
```

---

## 4. Quality Gate Design

### Scoring Algorithm

Each song gets a composite score from 3 weighted factors:

```python
def score_song(song: dict) -> dict:
    """
    Score a generated song for quality.

    Returns dict with:
      - score: float 0.0-1.0
      - passed: bool
      - breakdown: dict of individual scores
      - tier: "hero" | "standard" | "rejected"
    """
    score = 0.0
    breakdown = {}

    # Factor 1: Duration (weight 0.4)
    duration = song.get("duration_sec", 0)
    min_dur = config["quality_gate"]["min_song_duration"]  # 120s
    if duration >= min_dur:
        # Linear scale: 120s→0.5, 180s→0.75, 240s+→1.0
        dur_score = min(1.0, 0.5 + (duration - min_dur) / 240)
    else:
        dur_score = duration / min_dur * 0.4  # Below min: penalized
    breakdown["duration"] = dur_score
    score += dur_score * 0.4

    # Factor 2: Lyrics Structure (weight 0.35)
    lyrics = song.get("lyrics", "")
    structure_markers = ["[Chorus]", "[Verse]", "[Bridge]", "[Intro]", "[Outro]",
                         "[Chorus]", "[Verse]", "[Bridge]", "[Intro]", "[Outro]"]  # Chinese variants
    found_markers = sum(1 for m in structure_markers if m.lower() in lyrics.lower())
    min_markers = 2  # Expect at least [Verse] + [Chorus]
    struct_score = min(1.0, found_markers / min_markers * 0.7)
    if struct_score > 0:
        struct_score = max(0.3, struct_score)  # At least 0.3 if any markers found
    breakdown["structure"] = struct_score
    score += struct_score * 0.35

    # Factor 3: Lyrics Length & Variety (weight 0.25)
    lyrics_lines = [l for l in lyrics.split("\n")
                    if l.strip() and not l.strip().startswith("[")]
    char_count = sum(len(l) for l in lyrics_lines)
    min_chars = config["quality_gate"]["min_lyrics_length"]  # 100
    if char_count >= min_chars:
        length_score = min(1.0, char_count / 500)  # 500 chars = 1.0
    else:
        length_score = char_count / min_chars * 0.5
    breakdown["lyrics_length"] = length_score
    score += length_score * 0.25

    # Overall
    passed = (
        duration >= min_dur
        and char_count >= min_chars
    )
    if config["quality_gate"]["require_chorus_marker"]:
        has_chorus = any(c.lower() in lyrics.lower()
                         for c in ["[chorus]", "[Chorus]", "chorus"])
        passed = passed and has_chorus

    return {
        "score": round(score, 3),
        "passed": passed,
        "breakdown": breakdown,
    }
```

### Hero/Standard Selection

```python
def assign_tiers(songs: list) -> list:
    """
    Score all songs, assign tiers.
    Returns songs with tier field added.
    """
    scored = []
    for s in songs:
        result = score_song(s)
        s["quality_score"] = result
        scored.append(s)

    # Filter to passed only
    passed = [s for s in scored if s["quality_score"]["passed"]]

    if len(passed) == 0:
        # Skip day entirely
        return []

    # Sort by score descending
    passed.sort(key=lambda s: s["quality_score"]["score"], reverse=True)

    # Assign tiers
    passed[0]["tier"] = "hero"
    if len(passed) > 1:
        passed[1]["tier"] = "standard"

    # Remaining (if >2) get "excess" — not uploaded
    for s in passed[2:]:
        s["tier"] = "excess"

    return passed
```

### Edge Cases

| Scenario | Behaviour |
|----------|-----------|
| Both songs pass gate | Hero = higher score (18:00), Standard = lower score (20:00) |
| One song passes | Only upload that song as Hero at 18:00. Skip 20:00 slot. |
| Neither passes | Skip day entirely. Log warning. Send Telegram alert. |
| Song passes but visualizer fails | Upload MP3-only (no visualizer). Better than skipping. |
| Song passes but short fails | Still upload long-form. Short is bonus, not required. |

---

## 5. Lyrics SRT Overlay (Long-Form)

### Design Principle

**Reuse, don't rewrite.** Shorts already have `_generate_chorus_srt()`. Long-form videos need a different distribution strategy: show ALL lyrics lines (not just chorus) spread across the full song duration.

### New Function in `nightly_visualizer.py`

```python
def _generate_full_song_srt(lyrics: str, duration_sec: float) -> str:
    """
    Generate SRT subtitles for a full-length song.

    Distributes ALL lyrics lines evenly across the total duration,
    grouping lines into chunks of 1-2 lines per subtitle block.

    Different from _generate_chorus_srt() which:
      - Only uses the chorus/middle section
      - Always 45s duration
      - Fewer lines

    Args:
        lyrics: Full lyrics text with section markers like [Verse], [Chorus]
        duration_sec: Full song duration in seconds

    Returns:
        SRT-formatted string, or empty string if no lyrics available
    """
    # Parse lyrics: split into display lines (skip empty, keep section markers)
    raw_lines = lyrics.split("\n")

    # Build display blocks: group section header + following lines
    blocks = []
    current_section = ""
    current_lines = []

    for line in raw_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            # Section marker — flush previous block
            if current_lines:
                blocks.append((current_section, current_lines))
            current_section = stripped
            current_lines = []
        else:
            current_lines.append(stripped)

    # Flush last block
    if current_lines:
        blocks.append((current_section, current_lines))

    if not blocks:
        return ""

    # Flatten to display chunks: each chunk = 1-2 consecutive lines
    chunks = []
    for section, lines in blocks:
        for i in range(0, len(lines), 2):
            chunk_lines = lines[i:i+2]
            display = "\n".join(chunk_lines)
            chunks.append(display)

    if not chunks:
        return ""

    # Distribute evenly across duration
    # Each chunk gets equal time, minimum 3s per chunk
    num_chunks = len(chunks)
    sec_per_chunk = max(3.0, duration_sec / num_chunks)

    srt_parts = []
    for i, chunk in enumerate(chunks):
        start = i * sec_per_chunk
        end = min((i + 1) * sec_per_chunk, duration_sec)
        if end - start >= 1.5:  # Only if display time is meaningful
            srt_parts.append(str(i + 1))
            srt_parts.append(
                f"{_format_srt_time(start)} --> {_format_srt_time(end)}"
            )
            srt_parts.append(chunk)
            srt_parts.append("")

    return "\n".join(srt_parts)
```

### Integration Point in Visualizer

```python
def generate_visualizer(mp3_path, output_path, title,
                        background_image=None, duration_sec=None,
                        lyrics=None, mood_palette=None):
    """
    Existing function, extended with optional lyrics overlay and mood colors.

    Args:
        lyrics: Full lyrics text for SRT subtitle generation (new)
        mood_palette: Tuple of (color1, color2) for showwaves colors (new)
    """
    # ... existing logic ...

    # Generate SRT if lyrics provided
    srt_path = None
    if lyrics and config.get("visualizer", {}).get("lyrics_overlay", True):
        srt_content = _generate_full_song_srt(lyrics, actual_duration)
        if srt_content:
            srt_path = os.path.join(temp_dir, "subtitles.srt")
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(srt_content)

    # Use mood palette if provided
    wave_colors = "#FF6B6B|#4ECDC4"  # default
    if mood_palette and config.get("visualizer", {}).get("mood_colors", True):
        wave_colors = f"{mood_palette[0]}|{mood_palette[1]}"

    # Build filter_complex with SRT overlay
    # ... existing bg_chain + waves_chain + overlay_chain ...
    # Add subtitles filter if srt_path exists
    if srt_path:
        overlay_chain += f",subtitles={srt_path}:fontsdir={fontsdir}"
```

### Why This Is #1 Priority

| Reason | Detail |
|--------|--------|
| **Subscriber conversion** | Lyrics subtitles keep viewers watching longer → higher AVD → algorithm favors channel |
| **Code reuse** | `_generate_chorus_srt()`, `_format_srt_time()`, `subtitles=` filter — all already work |
| **Minimal code** | ~20 new lines in visualizer, ~30 lines for `_generate_full_song_srt()` |
| **No new deps** | FFmpeg already handles subtitles filter |
| **Works offline** | No API calls, no third-party services |

---

## 6. Mood Color System

### Architecture

```
lyrics text
    │
    ▼
mood_colors.py
    ├── Chinese keyword → mood detection
    ├── English keyword → mood detection
    └── mood → color palette mapping
            │
            ▼
    (color1, color2) tuple  →  FFmpeg showwaves colors parameter
```

### Keyword-to-Mood Mapping

```python
# mood_colors.py

MOOD_KEYWORDS = {
    # Chinese keywords → mood
    "happy": {
        "zh": ["快乐", "开心", "欢", "笑", "喜", "乐", "幸福", "美好",
               "阳光", "灿烂", "温暖", "甜蜜"],
        "en": ["happy", "joy", "laugh", "smile", "bright", "sunshine",
               "wonderful", "love", "dance"],
    },
    "sad": {
        "zh": ["伤心", "难过", "哭", "泪", "悲伤", "忧愁", "寂寞",
               "孤独", "失落", "心痛", "思念", "离别"],
        "en": ["sad", "cry", "tears", "lonely", "broken", "heartache",
               "miss", "farewell", "lost"],
    },
    "romantic": {
        "zh": ["爱", "恋", "情", "吻", "拥抱", "温柔", "浪漫", "想你",
               "陪伴", "永远", "承诺"],
        "en": ["love", "kiss", "embrace", "romance", "forever",
               "promise", "together", "sweetheart"],
    },
    "energetic": {
        "zh": ["奔跑", "飞翔", "力量", "勇敢", "燃烧", "热血", "战斗",
               "追", "梦", "青春", "疯狂"],
        "en": ["run", "fly", "power", "brave", "burn", "fight",
               "dream", "youth", "crazy", "energy"],
    },
    "melancholy": {
        "zh": ["秋", "落叶", "黄昏", "夕阳", "回忆", "曾经", "过去",
               "旧", "时光", "岁月", "尽头"],
        "en": ["autumn", "leaves", "dusk", "sunset", "memory",
               "past", "old days", "time", "end"],
    },
    "peaceful": {
        "zh": ["安静", "宁静", "星空", "月光", "风", "云", "海",
               "山", "自然", "心灵", "平静"],
        "en": ["quiet", "peace", "starry", "moonlight", "wind",
               "cloud", "ocean", "mountain", "calm"],
    },
}
```

### Mood-to-Palette Mapping

```python
MOOD_PALETTES = {
    "happy":      ("#FF6B6B", "#FFD93D"),  # Coral → Yellow
    "sad":        ("#6C5B7B", "#355C7D"),  # Purple → Deep Blue
    "romantic":   ("#FF6B9D", "#C44AFF"),  # Pink → Purple
    "energetic":  ("#FF4500", "#FFD700"),  # Orange Red → Gold
    "melancholy": ("#4A4E69", "#22223B"),  # Muted Violet → Dark Navy
    "peaceful":   ("#6BCB77", "#4D96FF"),  # Green → Sky Blue
    "default":    ("#FF6B6B", "#4ECDC4"),  # Coral → Teal (existing default)
}
```

### Detection Algorithm

```python
def detect_mood(lyrics: str, language: str = "chinese-only") -> str:
    """
    Detect primary mood from lyrics text.

    Returns mood key: "happy" | "sad" | "romantic" | "energetic"
                     | "melancholy" | "peaceful" | "default"
    """
    if not lyrics:
        return "default"

    lyrics_lower = lyrics.lower()
    scores = {}

    for mood, keywords in MOOD_KEYWORDS.items():
        score = 0
        lang_key = "zh" if language == "chinese-only" else "en"
        for keyword in keywords.get(lang_key, []):
            count = lyrics_lower.count(keyword.lower())
            score += count
        # Also check the other language at lower weight
        other_key = "en" if lang_key == "zh" else "zh"
        for keyword in keywords.get(other_key, []):
            count = lyrics_lower.count(keyword.lower())
            score += count * 0.3  # 30% weight for cross-language matches
        if score > 0:
            scores[mood] = score

    if not scores:
        return "default"

    # Return mood with highest keyword match count
    best_mood = max(scores, key=scores.get)
    # But only if it has at least 2 keyword matches (avoid single-word false positive)
    if scores[best_mood] >= 2:
        return best_mood
    return "default"


def get_mood_palette(lyrics: str, language: str = "chinese-only") -> tuple:
    """Return (color1, color2) hex strings for visualizer waveform."""
    mood = detect_mood(lyrics, language)
    palette = MOOD_PALETTES.get(mood, MOOD_PALETTES["default"])
    print(f"[mood] Detected '{mood}' → palette {palette}")
    return palette
```

### Integration Point

In `nightly_music.py` (or `nightly_visualizer.py`), after song generation:

```python
# Detect mood from lyrics
mood_palette = None
if config.get("visualizer", {}).get("mood_colors", True):
    from mood_colors import get_mood_palette
    mood_palette = get_mood_palette(
        song.get("lyrics", ""),
        config.get("language", "chinese-only")
    )

# Pass to visualizer
viz_result = generate_visualizer(
    mp3_path=song["mp3_path"],
    output_path=mp4_path,
    title=title,
    lyrics=song.get("lyrics", ""),  # For SRT overlay
    mood_palette=mood_palette,       # For dynamic colors
    duration_sec=hero_max_dur if tier == "hero" else standard_max_dur,
)
```

---

## 7. Weekly Theme System

### Day-of-Week Mapping

```python
# weekly_themes.py

import datetime

WEEKLY_THEMES = {
    0: {  # Monday
        "mood": "upbeat",
        "prompt_modifier": "upbeat, energetic, fast tempo, bright major key, driving beat",
        "prompt_modifier_zh": "轻快活力，节奏明快，积极向上，振奋人心",
        "color": "#FF6B35",
    },
    1: {  # Tuesday
        "mood": "melancholy",
        "prompt_modifier": "melancholy, slow tempo, minor key, reflective, wistful",
        "prompt_modifier_zh": "忧郁感伤，慢板，小调，沉思抒情",
        "color": "#6C5B7B",
    },
    2: {  # Wednesday
        "mood": "romantic",
        "prompt_modifier": "romantic, warm, gentle, love song, sweet melody",
        "prompt_modifier_zh": "浪漫温馨，柔情蜜意，甜蜜温暖，情歌",
        "color": "#FF6B9D",
    },
    3: {  # Thursday
        "mood": "sad",
        "prompt_modifier": "sad, emotional, slow, heartfelt, touching ballad",
        "prompt_modifier_zh": "伤感催泪，深情动人，慢板抒情，触人心弦",
        "color": "#355C7D",
    },
    4: {  # Friday
        "mood": "dance",
        "prompt_modifier": "dance, energetic, upbeat, rhythmic, club beat",
        "prompt_modifier_zh": "动感舞曲，节奏强劲，活力四射，派对气氛",
        "color": "#FF4500",
    },
    5: {  # Saturday
        "mood": "chill",
        "prompt_modifier": "chill, relaxed, lo-fi, laid back, smooth",
        "prompt_modifier_zh": "轻松悠闲，放松舒缓，慵懒惬意，慢生活",
        "color": "#6BCB77",
    },
    6: {  # Sunday
        "mood": "soft",
        "prompt_modifier": "soft, gentle, acoustic, tender, soothing",
        "prompt_modifier_zh": "温柔柔美，轻柔舒缓，纯净动人，暖心治愈",
        "color": "#87CEEB",
    },
}
```

### Prompt Modifier Injection

In `nightly_music.py`, when building the MiniMax prompt:

```python
def build_weekly_prompt(base_prompt: str, date_label: str, config: dict) -> str:
    """Inject weekly theme modifier into the generation prompt."""
    if not config.get("weekly_themes", {}).get("enabled", True):
        return base_prompt

    from weekly_themes import get_theme_modifier
    theme = get_theme_modifier(date_label)  # Returns prompt_modifier_zh for Chinese

    # Append theme modifier to base prompt
    modified = f"{base_prompt}。{theme}"
    print(f"[weekly_theme] {date_label}: '{theme}' appended to prompt")
    return modified


def get_theme_modifier(date_str: str) -> str:
    """Get the theme prompt modifier for a given date."""
    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    day_of_week = dt.weekday()  # 0=Monday
    theme = WEEKLY_THEMES.get(day_of_week, WEEKLY_THEMES[0])
    return theme["prompt_modifier_zh"]  # Use Chinese modifier for Chinese songs
```

### Integration Flow

```
nightly_music.py
  │
  ├── Load config (includes weekly_themes)
  ├── Get date_label (--date argument)
  ├── Fetch trending songs
  ├── For each trending song:
  │     ├── Build base prompt from trending + style
  │     ├── Inject weekly theme modifier → modified_prompt
  │     ├── Generate song via MiniMax with modified_prompt
  │     └── ...
  │
  └── Quality gate → assign tiers → upload with staggered schedule
```

---

## 8. Compilation Generator (Sunday Album)

### Design

```python
# compilation.py

"""
Weekly compilation generator.

Every Sunday, concat all Hero + Standard videos from Mon-Sat into
a single long video. Upload as "Week X — Best AI Songs [Compilation]".

Uses FFmpeg concat demuxer (no re-encoding, fast).

Videos must all have the same codec/resolution (they do — all
generated by same visualizer).
"""

import os
import json
import subprocess
from pathlib import Path


def get_week_videos(output_dir: str, week_end_date: str) -> list:
    """
    Find all uploaded videos from the week ending on week_end_date.

    week_end_date: Sunday's date (YYYY-MM-DD)
    Returns list of (video_path, title, tier) for Mon-Sat.
    """
    from datetime import datetime, timedelta

    sunday = datetime.strptime(week_end_date, "%Y-%m-%d")
    videos = []

    for i in range(6, 0, -1):  # Mon=6 days before, Sat=1 day before
        day = sunday - timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        day_dir = os.path.join(output_dir, day_str)

        if not os.path.isdir(day_dir):
            continue

        # Find video files with tier markers in filename
        for fname in sorted(os.listdir(day_dir)):
            if fname.endswith("-viz.mp4"):
                videos.append(os.path.join(day_dir, fname))

    return videos


def generate_compilation(output_dir: str, week_end_date: str,
                         compilation_dir: str) -> dict:
    """
    Generate a compilation video from all week's songs.

    Uses FFmpeg concat demuxer for zero-re-encode concatenation.

    Returns dict with path, status, error.
    """
    videos = get_week_videos(output_dir, week_end_date)
    if len(videos) < 2:
        return {"path": "", "status": "skipped",
                "error": f"Only {len(videos)} videos found, need ≥2"}

    # Create temp concat file
    concat_file = os.path.join(compilation_dir, "concat_list.txt")
    with open(concat_file, "w") as f:
        for v in videos:
            f.write(f"file '{v}'\n")

    # Determine week number
    from datetime import datetime
    sunday = datetime.strptime(week_end_date, "%Y-%m-%d")
    week_num = sunday.isocalendar()[1]

    output_path = os.path.join(
        compilation_dir,
        f"week-{week_num}-compilation-{week_end_date}.mp4"
    )

    # FFmpeg concat
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_file,
        "-c", "copy",  # No re-encode
        output_path,
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        if proc.returncode != 0:
            return {"path": "", "status": "failed",
                    "error": proc.stderr[-500:]}

        return {
            "path": output_path,
            "status": "ok",
            "duration_sec": sum(_probe_duration(v) for v in videos),
            "song_count": len(videos),
        }
    except Exception as e:
        return {"path": "", "status": "failed", "error": str(e)}
```

### Upload Metadata

```python
COMPILATION_TITLE_TEMPLATE = "Week {week_num} — Best AI Songs ({start_date} to {end_date})"
# Description:
# "🎵 本周AI歌曲精选合集 | Best AI Songs of the Week
#  收录本周{count}首AI生成的华语流行歌曲
#  
#  📅 日期: {start_date} → {end_date}
#  
#  歌曲列表:
#  {song_list}
#  
#  💬 哪首是你最喜欢的？评论区告诉我们！
#  🔔 订阅频道，每天收听新歌！
#  #AIMusic #华语流行 #AI歌曲合集 #人工智能音乐"
```

---

## 9. Pipeline State

Keep the `pipeline_state.py` dataclass from the old plan (it's useful regardless of scale):

```python
# pipeline_state.py

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SongState:
    """State for a single generated song through the pipeline."""
    song_number: int
    title: str = ""
    tier: str = ""                # "hero" | "standard" | "excess" | "rejected"
    status: str = "pending"       # pending | generating | generated | failed
    quality_score: float = 0.0
    quality_passed: bool = False

    # Files
    mp3_path: str = ""
    txt_path: str = ""
    mp4_path: str = ""
    short_path: str = ""
    thumbnail_path: str = ""
    bg_path: str = ""
    bg_vertical_path: str = ""

    # Upload state
    youtube_video_id: str = ""
    youtube_url: str = ""
    youtube_status: str = "pending"
    short_youtube_id: str = ""
    short_youtube_url: str = ""
    short_upload_status: str = "pending"

    # Content
    lyrics: str = ""
    prompt: str = ""
    trending_song: str = ""
    trending_artist: str = ""
    duration_sec: int = 0
    mood: str = ""
    mood_palette: tuple = ("#FF6B6B", "#4ECDC4")

    errors: list = field(default_factory=list)


@dataclass
class PipelineState:
    """Full pipeline execution state."""
    date_label: str
    config: dict = field(default_factory=dict)
    songs: list = field(default_factory=list)  # list of SongState
    compilation_video_path: str = ""

    # Schedule (from config + tier)
    hero_publish_at: str = ""
    standard_publish_at: str = ""
    shorts_publish_at: str = ""

    def get_hero(self) -> Optional[SongState]:
        return next((s for s in self.songs if s.tier == "hero"), None)

    def get_standard(self) -> Optional[SongState]:
        return next((s for s in self.songs if s.tier == "standard"), None)

    def get_uploadable(self) -> list:
        return [s for s in self.songs if s.tier in ("hero", "standard")]
```

---

## 10. Implementation Order

### Sprint 1: Lyrics Overlay + Mood Colors (Highest Sub Impact — 2 days)

| # | Task | Files | Est. | Verification |
|---|------|-------|------|-------------|
| 1 | Add `_generate_full_song_srt()` to visualizer | `nightly_visualizer.py` | 30min | Unit test: lyrics → correct SRT timestamps |
| 2 | Add `lyrics` param to `generate_visualizer()` signature | `nightly_visualizer.py` | 15min | Generated video has visible subtitles |
| 3 | Write `mood_colors.py` — keyword maps + detection | `mood_colors.py` (NEW) | 45min | Unit test: known lyrics → expected mood |
| 4 | Add `mood_palette` param to `generate_visualizer()` | `nightly_visualizer.py` | 15min | Generated video has different waveform colors |
| 5 | Wire lyrics + mood through `nightly_music.py` | `nightly_music.py` | 30min | Dry run propagates params correctly |
| 6 | Update config schema for `lyrics_overlay` + `mood_colors` | `nightly-music.yaml` | 10min | Config loads without error |
| 7 | Test full run with lyrics overlay + mood colors | Manual | 30min | Video has subtitles + dynamic colors |

### Sprint 2: Quality Gate + Staggered Schedule (2 days)

| # | Task | Files | Est. | Verification |
|---|------|-------|------|-------------|
| 1 | Write `quality_gate.py` — `score_song()` + `assign_tiers()` | `quality_gate.py` (NEW) | 1hr | Unit test: mock songs get correct scores/tiers |
| 2 | Integrate quality gate into `nightly_music.py` pipeline | `nightly_music.py` | 30min | Dry run shows tier assignment |
| 3 | Update `nightly_uploader.py` — accept per-song `publish_at` | `nightly_uploader.py` | 20min | Upload scheduled at different times |
| 4 | Stagger upload calls in `nightly_music.py` (hero 18:00, std 20:00) | `nightly_music.py` | 20min | Log shows different publish_at timestamps |
| 5 | Handle edge cases: zero-pass, one-pass days | `nightly_music.py` | 30min | Test with mock scores |
| 6 | Update config schema for `quality_gate` section | `nightly-music.yaml` | 10min | Config loads, defaults apply |
| 7 | Test: both pass, one passes, neither passes | Manual | 30min | Correct upload behaviour per scenario |

### Sprint 3: Weekly Themes + Prompt Injection (1 day)

| # | Task | Files | Est. | Verification |
|---|------|-------|------|-------------|
| 1 | Write `weekly_themes.py` — day-of-week mapping | `weekly_themes.py` (NEW) | 20min | Unit test: each day → expected modifier |
| 2 | Add theme injection to prompt building in `nightly_music.py` | `nightly_music.py` | 20min | Dry run shows modified prompts |
| 3 | Update config schema for `weekly_themes` | `nightly-music.yaml` | 10min | Config loads |
| 4 | Test full run on different days of week (simulate dates) | Manual | 20min | Prompts contain correct modifiers |

### Sprint 4: Compilation + Remaining Items (1 day)

| # | Task | Files | Est. | Verification |
|---|------|-------|------|-------------|
| 1 | Write `compilation.py` — week video concat | `compilation.py` (NEW) | 1hr | Concat 3+ test videos, verify output duration |
| 2 | Integrate compilation into Sunday pipeline | `nightly_music.py` + cron | 30min | Sunday dry run shows compilation step |
| 3 | Write `pipeline_state.py` dataclass | `pipeline_state.py` (NEW) | 20min | Tests pass |
| 4 | Update hero/standard duration max in visualizer call | `nightly_music.py` | 10min | Hero ≤210s, Standard ≤180s |
| 5 | Shorts: reduce to 30s in config | `nightly-music.yaml` | 5min | Config updated |
| 6 | Fix B1-B4 (ordering, visualizer bg, thumbnail double-gen, Shorts frame/seconds) | Various | 1hr | Per bug fix, each verified |
| 7 | Update song-log schema for new fields (tier, mood, quality score) | `nightly_music.py` | 15min | Log entries contain new fields |
| 8 | Regression: existing tests still pass | Test suite | 30min | All 10 tests pass |
| 9 | End screen template (YouTube Studio one-time) | Manual YouTube setup | 15min | End screen appears on videos |

### Total: 6 days (Sprint 1-4)

---

## 11. What's Removed vs Kept

### REMOVED (from old Phase 2 plan)

| Feature | Reason |
|---------|--------|
| 10 songs/day scaling | Quality over quantity. 2 songs + Shorts is optimal. |
| Parallel MiniMax calls | Not needed for 2 songs. Sequential is simpler. |
| Async gen agent | Over-engineering for 2 songs. |
| Multi-agent coordinator | No benefit at 2 songs. Keep pipeline linear. |
| Growth agent (YouTube Analytics API) | Deferred. Analytics manually reviewed for now. |
| Quota management system | 6,800 units/day is safe. No action needed. |
| Animated visualizers (moviepy/manim) | Deferred to Phase 2b. Static SRT + mood colors first. |

### KEPT (from old Phase 2 plan)

| Feature | Reason |
|---------|--------|
| `pipeline_state.py` dataclass | Useful regardless of scale. Clean state management. |
| Fix B1-B4 | Ordering bug, visualizer bg, thumbnail double-gen, Shorts frame/seconds still exist. |
| End screen template (YouTube Studio) | One-time setup, high ROI. |
| Moviepy upgrade for Phase 2b | Only for animated visualizers — deferred. |

### CHANGED (from current Phase 1)

| Feature | Phase 1 | Phase 2 |
|---------|---------|---------|
| Upload schedule | Both at 18:00 | Hero 18:00, Standard 20:00 |
| Shorts duration | 45s | 30s |
| Video quality | All songs uploaded | Quality gate filters low-quality |
| Visualizer colors | Static `#FF6B6B\|#4ECDC4` | Dynamic from lyrics mood |
| Lyrics on video | No | Full SRT subtitles |
| Prompts | Static | Day-of-week theme modifier |
| Weekly album | No | Sunday compilation |
| Song count | 2 | 2 (same, but tiered) |

---

## Data Flow Diagram

```
CRON 2am SGT
  │
  ▼
nightly_music.py
  │
  ├── 1. Load config (updated Phase 2 schema)
  ├── 2. Inject weekly theme → prompts
  ├── 3. Fetch trending + dedup
  ├── 4. Generate 2 songs (sequential, no change)
  │       └── MiniMax API ×2
  │
  ├── 5. Score songs → quality_gate.py
  │       ├── Both pass → assign Hero (higher) + Standard (lower)
  │       ├── One passes → Hero only
  │       └── Both fail → SKIP DAY (Telegram alert)
  │
  ├── 6. For each passing song:
  │       ├── Detect mood → mood_colors.py (from lyrics)
  │       ├── Generate visualizer with:
  │       │     ├── SRT lyrics overlay (new)
  │       │     ├── Mood-based waveform colors (new)
  │       │     └── Duration cap (Hero ≤210s, Standard ≤180s)
  │       ├── Generate thumbnail
  │       ├── Generate Short (30s)
  │       └── Upload to YouTube:
  │             ├── Hero → publish_at 18:00
  │             └── Standard → publish_at 20:00
  │
  ├── 7. (If Sunday) Generate compilation → compilation.py
  │       └── Upload compilation video
  │
  ├── 8. Sync to D-drive
  ├── 9. Log (updated schema with tier, mood, score)
  └── 10. Telegram delivery (unchanged)
```

---

## ADR Summary

| # | Title | Status |
|---|-------|--------|
| 1 | Staggered Schedule with Hero/Standard Tiers | Proposed |
| 2 | Song Quality Gate | Proposed |
| 3 | SRT Lyrics on Long-Form Videos | Proposed |
| 4 | Mood-Based Color Palettes | Proposed |
| 5 | Weekly Themes Influence Prompts | Proposed |
| 6 | Weekly Compilation (Sunday Album) | Proposed |
| 7 | Remove 10 Songs/Day Scaling | Proposed |
