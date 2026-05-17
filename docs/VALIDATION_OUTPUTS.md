# Validation Outputs — Pipeline Refactor (Stages A-I)

> **Purpose**: Each stage of the refactored pipeline produces a self-contained validation
> output that the operator inspects before approving the next stage. No stage depends
> on the next stage to verify itself.
>
> **Author**: EngineeringSeniorDeveloper
> **Date**: 2026-05-17
> **Status**: Specification — implement when stage code is written

---

## How to Read a Stage Template

Each stage defines:

1. **Console output** — exact format printed to stdout/stderr
2. **PASS condition** — the objective check(s) the operator performs
3. **FAIL signals** — what to look for that means the stage failed
4. **Inspectable artifacts** — files on disk the operator can open

---

## Stage A: Fetch + Dedup

### Console Output

```
[STAGE A] Fetch + Dedup — PASS
  Source: qq-douyin → 4 songs
  Source: kkbox → 2 songs (2 new)
  Source: my-fm → 0 songs (0 new)
  Total: 5 unique songs (after cross-source dedup)
  Weekly theme: Thursday 🌧️ (伤感抒情)
  Dedup: 2 removed (周杰伦 - 晴天, 林俊杰 - 她说)
  Pool fill: 0 needed (5 ≥ 2)
  Final: 2 songs ready for generation
```

### PASS Conditions

| Check | How to verify |
|-------|---------------|
| Source counts are > 0 | Each source line shows a number ≥ 0 |
| Dedup removed duplicates | If any songs match last 7 days, they appear in "Dedup: X removed" |
| Final count matches config | `Final: N songs` where N == `song_count` from config (usually 2) |
| Weekly theme shows correct day | Thursday = 🌧️ 伤感抒情, Saturday = 🌟 chill, etc. |

### FAIL Signals

| Signal | Meaning |
|--------|---------|
| `Total: 0 unique songs` | All sources returned empty — pipeline cannot proceed |
| `All sources failed, falling back to pool...` | Sources errored; pool used instead |
| `Final: 0 songs ready` | Dedup filtered everything and pool is empty |

### Inspectable Artifacts

None — this stage has no file output. Console is the only validation.

---

## Stage B: Song Generation

### Console Output

```
[STAGE B] Song Generation — 2/2 PASS
  Song 1: 春日暖阳
    MP3:  output/2026-05-17/01-春日暖阳.mp3       ✅ (187.5s, 5.2MB)
    Lyrics: output/2026-05-17/01-春日暖阳.txt    ✅ (1.4KB, 187 chars)
    Structure: has [Verse], [Chorus], [Bridge]
  Song 2: 回忆的风
    MP3:  output/2026-05-17/02-回忆的风.mp3       ✅ (165.3s, 4.8MB)
    Lyrics: output/2026-05-17/02-回忆的风.txt    ✅ (1.2KB, 152 chars)
    Structure: has [Verse], [Chorus]
```

### PASS Conditions

| Check | How to verify |
|-------|---------------|
| Both songs show `✅` | Status icons indicate file exists and passes validation |
| MP3 file size > 3MB | Real audio (not a placeholder). 3.5-6.5MB is normal for ~3min |
| Lyrics file has content | `.txt` file contains song lyrics (not empty) |
| Duration 120-210s | Songs shorter than 90s may be failures |
| Has `[Chorus]` marker | Chorus is required for later Shorts generation |
| Has `[Verse]` section | Indicates proper song structure |

**Bonus check**: Open the `.mp3` in a media player and listen for:
- Clean audio (no distortion)
- Proper vocal quality
- Chinese lyrics match the title

**Bonus check**: Open the `.txt` file and verify:
- Lyrics make sense as a coherent song
- Not placeholder text like "[Auto-generated lyrics]"
- Structure markers are present

### FAIL Signals

| Signal | Meaning |
|--------|---------|
| `Song N FAILED` | MiniMax API error or timeout — song did not generate |
| File size < 500KB | Likely a silent failure or truncated download |
| Lyrics < 50 chars | Too short — likely placeholder content |
| No `[Chorus]` marker | May affect Shorts generation later |
| Duration < 60s | Song was cut short, likely an API issue |

### Inspectable Artifacts

| File | Path pattern | What to check |
|------|-------------|---------------|
| MP3 | `output/YYYY-MM-DD/NN-title.mp3` | File size, duration, listen to it |
| Lyrics TXT | `output/YYYY-MM-DD/NN-title.txt` | Content, structure markers, character count |

---

## Stage C: Quality Gate

### Console Output

```
[STAGE C] Quality Gate
  Hero threshold: ≥ 6.0  |  Standard: ≥ 4.0  |  Reject: < 4.0

  Song 1: 春日暖阳
    Lyrics length:    8/10  (187 chars, scale: ≥200=10, ≥100=6, ≥50=3, <50=0)
    Has chorus:      10/10  (detected [Chorus] marker)
    Duration:        10/10  (187.5s, ideal 120-210s)
    Placeholder:     10/10  (no placeholder text detected)
    Vocabulary:       7.5/10  (45% unique words, scale: ≥50%=10, linear below)
    ────────────────────────────────────────
    TOTAL:           8.9/10  →  🏆 HERO

  Song 2: 回忆的风
    Lyrics length:    6/10  (152 chars)
    Has chorus:      10/10  (detected [Chorus] marker)
    Duration:         8/10  (165.3s)
    Placeholder:     10/10  (no placeholder text detected)
    Vocabulary:       5/10  (32% unique words)
    ────────────────────────────────────────
    TOTAL:           6.2/10  →  ✅ STANDARD

  Gate result: 1 hero, 1 standard, 0 rejected
```

### PASS Conditions

| Check | How to verify |
|-------|---------------|
| Each dimension scores ≥ 0 | No dimension returned negative or NaN |
| Total score matches formula | Mentally sanity-check: `lyrics*30% + chorus*25% + duration*20% + placeholder*15% + vocab*10%` |
| Verdict matches threshold | ≥6.0 = 🏆 HERO, ≥4.0 = ✅ STANDARD, <4.0 = ❌ REJECT |
| At least 1 song is HERO or STANDARD | Otherwise the day is skipped |

### Understanding Dimensions

| Dimension | Weight | What it measures | Why it matters |
|-----------|--------|-----------------|----------------|
| Lyrics length | 30% | Total characters in lyrics | Short lyrics → sparse song |
| Has chorus | 25% | Presence of `[Chorus]` marker | No chorus → no hook |
| Duration | 20% | Audio length in seconds | Too short = low quality; too long = boring |
| Placeholder check | 15% | Detects "[Auto-generated..." text | API sometimes returns placeholder junk |
| Vocabulary | 10% | Unique word ratio | Repetitive lyrics = low quality |

### FAIL Signals

| Signal | Meaning |
|--------|---------|
| `0 hero, 0 standard, 2 rejected` | Both songs failed quality — day is skipped |
| Song with great audio scored low | Thresholds may need calibration |
| All songs score exactly 5.0 | Quality gate is disabled (config issue) |

### Inspectable Artifacts

None — this stage produces only console output. The verdicts are attached to song data
for downstream stages.

---

## Stage D: Assets (Backgrounds + Thumbnails)

### Console Output

```
[STAGE D] Per-Song Assets
  Song 1: 春日暖阳  [🏆 HERO]
    bg.jpg:        output/.../01-春日暖阳-bg.jpg         ✅ (122KB, 1920x1080)
    bg-vertical.jpg: output/.../01-春日暖阳-bg-vertical.jpg ✅ (52KB, 1080x1920)
    thumb.jpg:     output/.../01-春日暖阳-thumb.jpg       ✅ (194KB, 1280x720)
    Prompt来源: MiniMax LLM
    Prompt: "唯美春日樱花飘落，温暖金色阳光洒在花瓣上，远景，朦胧美感"

  Song 2: 回忆的风  [✅ STANDARD]
    bg.jpg:        output/.../02-回忆的风-bg.jpg         ✅ (93KB, 1920x1080)
    bg-vertical.jpg: output/.../02-回忆的风-bg-vertical.jpg ✅ (44KB, 1080x1920)
    thumb.jpg:     output/.../02-回忆的风-thumb.jpg       ✅ (184KB, 1280x720)
    Prompt来源: LLM Fallback (rule-based)
    Prompt: "怀旧老街黄昏时分，暖色灯光，落叶，宁静氛围"
```

### PASS Conditions

| Check | How to verify |
|-------|---------------|
| All 3 files per song exist | bg.jpg + bg-vertical.jpg + thumb.jpg all show `✅` |
| File sizes > 10KB | A real image was generated (not a blank/failed response) |
| bg.jpg is 1920x1080 | Landscape resolution for visualizer background |
| bg-vertical.jpg is 1080x1920 | Portrait for Shorts |
| thumb.jpg is 1280x720 | YouTube thumbnail resolution |

**Visual check** (recommended): Open each `.jpg` in Windows Photos and ask:
- Does the image match the song mood? (e.g., 春日暖阳 → spring/sunny vibe)
- Is it blurry, low quality, or defective?
- Does it violate the "no people, no faces, no text" rule?

### FAIL Signals

| Signal | Meaning |
|--------|---------|
| `✅ (0KB)` | File exists but is empty — generation failed silently |
| File size < 5KB | Pollinations returned an error image |
| `bg-vertical.jpg` matches `bg.jpg` dimensions | Wrong crop — vertical should be 9:16 |
| `Prompt来源: Fallback (rule-based)` | MiniMax LLM was unavailable; image may be generic |
| `Assets generation failed` | Pollinations rate-limited or down |

### Inspectable Artifacts

| File | What to check |
|------|---------------|
| `NN-title-bg.jpg` | Visual quality, mood match, resolution |
| `NN-title-bg-vertical.jpg` | Portrait crop quality, mood match |
| `NN-title-thumb.jpg` | Thumbnail clarity at 1280x720 |

---

## Stage E: Visualizer + SRT

### Console Output

```
[STAGE E] Visualizer + SRT
  Song 1: 春日暖阳  [Mood: romantic]
    viz.mp4:  output/.../01-春日暖阳-viz.mp4  ✅ (47MB, 1920x1080)
    viz.srt:  output/.../01-春日暖阳-viz.srt  ✅ (2.6KB, 42 subtitles)
    Codec:    H.264 ✅  |  Audio: AAC ✅
    Duration: 187.5s ✅ (matches source MP3: 187.5s)
    SRT:      42 entries, first at 0:01, last at 3:07
    Sections: Verse 4.0s/line, Chorus 2.7s/line, Bridge 4.4s/line
    Colors:   #FF9F9F | #FFC8A2 (romantic — soft pink + peach)

  Song 2: 回忆的风  [Mood: melancholy — rule-based]
    viz.mp4:  output/.../02-回忆的风-viz.mp4  ✅ (39MB, 1920x1080)
    viz.srt:  output/.../02-回忆的风-viz.srt  ✅ (2.1KB, 35 subtitles)
    Codec:    H.264 ✅  |  Audio: AAC ✅
    Duration: 165.3s ✅ (matches source MP3: 165.3s)
    SRT:      35 entries, first at 0:02, last at 2:45
    Sections: Verse 3.8s/line, Chorus 2.5s/line
    Colors:   #4ECDC4 | #95D5B2 (melancholy — teal + sage)
```

### PASS Conditions

| Check | How to verify |
|-------|---------------|
| MP4 file > 10MB | Real video was rendered |
| Resolution is 1920x1080 | `ffprobe -v error -select_streams v:0 -show_entries stream=width,height` |
| Codec is H.264 | `ffprobe -v error -select_streams v:0 -show_entries stream=codec_name` |
| Duration matches MP3 | `ffprobe` on both files — should differ by < 1s |
| SRT has entries | File is not empty; entries have proper SRT format `N\nHH:MM:SS,mmm --> HH:MM:SS,mmm\ntext\n\n` |
| SRT timing covers full song | Last subtitle ends near song duration |
| Mood colors are correct | `romantic` = pink palette, `melancholy` = blue palette, etc. |

**Visual check**: Play the `.mp4` and verify:
- Waveform appears at bottom of video
- Title text is visible at top
- Background image fills the frame
- Subtitles appear at correct times
- Colors match the mood (e.g., pink for romantic, teal for melancholy)
- No visual artifacts (green bars, black frame, etc.)

### FAIL Signals

| Signal | Meaning |
|--------|---------|
| `viz.mp4  ❌` or file missing | FFmpeg command failed (check stderr for ffmpeg error) |
| File size < 1MB (for ~3min song) | Video is blank or corrupted |
| Duration mismatch > 2s | MP4 was truncated — check FFmpeg args |
| Resolution mismatch | Scaling filters failed |
| `Codec: unknown` | FFprobe couldn't parse the file |
| `SRT: 0 entries` | SRT generation failed (lyrics parse error) |
| `Mood: unknown` | Mood detection failed — rule-based also failed; defaulted to chill |
| `Colors: #FF6B6B | #4ECDC4 (default)` | Phase 1 fallback used; mood detection was unavailable |

### Inspectable Artifacts

| File | Path pattern | What to check |
|------|-------------|---------------|
| viz.mp4 | `NN-title-viz.mp4` | Play it, check waveform/title/SRT/mood colors |
| viz.srt | `NN-title.srt` | Open in text editor — verify SRT format and timing |

---

## Stage F: Shorts

### Console Output

```
[STAGE F] Shorts
  Song 1: 春日暖阳  [🏆 HERO]
    short.mp4: output/.../01-春日暖阳-short.mp4  ✅ (5.4MB, 1080x1920)
    Duration:  30.0s ✅ (target: 30s)
    Window:    Chorus at 45.2s - 75.2s (loudest 30s segment)
    SRT:       8 subtitles ✅

  Song 2: 回忆的风  [✅ STANDARD]
    short.mp4: output/.../02-回忆的风-short.mp4  ✅ (4.2MB, 1080x1920)
    Duration:  30.0s ✅ (target: 30s)
    Window:    Chorus at 38.5s - 68.5s (loudest 30s segment)
    SRT:       6 subtitles ✅
```

### PASS Conditions

| Check | How to verify |
|-------|---------------|
| File exists with `✅` | Short was generated |
| Resolution 1080x1920 | 9:16 portrait mode (verified via `ffprobe`) |
| Duration 28-32s | Target 30s ± 2s tolerance |
| Window identifies chorus section | The 30s comes from the song's loudest portion (usually chorus) |

**Visual check**: Open the Short and verify:
- Portrait orientation (vertical)
- Waveform fills the frame
- Background image is the vertical version
- Subtitles appear if applicable
- Video is from the most engaging part of the song

### FAIL Signals

| Signal | Meaning |
|--------|---------|
| `short.mp4  ❌` | Generation failed — check ffmpeg output |
| Duration < 10s | Something went wrong with the window selection |
| Resolution not 1080x1920 | Crop filter produced wrong aspect ratio |
| `Window: Song start (fallback)` | The loudest-window algorithm failed (song < 10s) |
| No Short for STANDARD songs | Expected — config may restrict Shorts to HERO only |

### Inspectable Artifacts

| File | What to check |
|------|---------------|
| `NN-title-short.mp4` | Play it, verify orientation, waveform, subtitle timing |

---

## Stage G: YouTube Upload

### Console Output

```
[STAGE G] YouTube Upload
  Song 1: 春日暖阳 [🏆 HERO]
    Long-form: ✅ video_id=abc123def
    URL:       https://youtube.com/watch?v=abc123def
    Scheduled: 2026-05-17T18:00:00+08:00 (6pm SGT)
    Thumbnail: ✅ Set
    SEO tags:  ✓ 16 tags applied

    Short:     ✅ video_id=xyz789ghi
    URL:       https://youtube.com/shorts/xyz789ghi
    Scheduled: 2026-05-17T12:00:00+08:00 (12pm SGT)
    Thumbnail: ✅ Set

  Song 2: 回忆的风 [✅ STANDARD]
    Long-form: ✅ video_id=def456jkl
    URL:       https://youtube.com/watch?v=def456jkl
    Scheduled: 2026-05-17T20:00:00+08:00 (8pm SGT)
    Thumbnail: ✅ Set

    Short:     ⏭ Skipped (STANDARD tier — no Shorts)
```

### PASS Conditions

| Check | How to verify |
|-------|---------------|
| video_id is non-empty | Upload returned a valid YouTube video ID |
| URL is valid format | `https://youtube.com/watch?v=...` |
| Scheduled time is correct HERO | HERO = 18:00 SGT, Standard = 20:00 SGT, Shorts = 12:00 SGT |
| Thumbnail shows `✅` | Thumbnail was attached to the video |
| Timezone is `+08:00` | Singapore time — confirms no UTC/SGT confusion |

**Critical verification**: Click each URL to open in a browser (or use incognito).
The video should:
- Appear on YouTube (may say "Private video" or "Scheduled")
- Show the correct title
- Show the correct thumbnail

### FAIL Signals

| Signal | Meaning |
|--------|---------|
| `❌ video_id=` (empty) | Upload failed — check error details |
| `Failed: YouTube API error: ...` | OAuth, quota, or API issue |
| `Failed: OAuth token expired` | Token refresh failed — needs manual re-auth |
| `Thumbnail ❌` | Thumbnail upload failed (video still uploaded) |
| Scheduled time is wrong timezone | UTC vs SGT bug (videos publish at wrong hour) |
| Both songs at same time | Staggered scheduling failed — both at 18:00 |

### Troubleshooting Failed Uploads

| Error | Likely cause | Fix |
|-------|-------------|-----|
| `quotaExceeded` | 10,000 units/day exceeded | Wait until next day or reduce song count |
| `authError` | OAuth token expired | Run `nightly_uploader.py --setup-auth` |
| `backendError` | YouTube API transient | Retry (pipeline does this automatically) |
| `videoTooLarge` | File > 128GB (unlikely) | Check file size |
| `invalidMetadata` | Title/description encoding issue | Check for unsupported characters |

### Inspectable Artifacts

| Artifact | How to access |
|----------|---------------|
| YouTube URL | Click link in console output |
| YouTube Studio | `https://studio.youtube.com/video/<video_id>/edit` (check scheduling) |
| Thumbnail | View on YouTube video page |

---

## Stage H: Notify + Sync + Log

### Console Output

```
[STAGE H] Notify + Sync + Log
  Log:
    → logs/song-log-2026-05.json
    ✅ Appended 2 entries (replaced 0 stale)
    Fields per entry: date, title, quality_score, verdict, mood, youtube_url, ...

  D-drive sync:
    → /mnt/d/Hermes/songs/nightly-songs/2026-05-17/
    ✅ 8 files synced:
      01-春日暖阳.mp3
      01-春日暖阳.txt
      01-春日暖阳-viz.mp4
      01-春日暖阳.srt
      01-春日暖阳-bg.jpg
      01-春日暖阳-bg-vertical.jpg
      02-回忆的风.mp3
      02-回忆的风.txt
      (short not synced — excluded from D-drive)

  Telegram:
    ✅ Batch sent (4 files via media group):
      🏆 Song #1: 春日暖阳 [8.9/10]
      ✅ Song #2: 回忆的风 [6.2/10]
```

### PASS Conditions

| Check | How to verify |
|-------|---------------|
| Log says `✅ Appended` | Song log file was updated |
| Log fields look complete | Quality scores, verdict, YouTube URLs are present |
| D-drive files listed match expectations | All expected output files are synced |
| Telegram says `✅ Batch sent` | Message was delivered to the bot |

**Critical verification**: Switch to Telegram app and check:
- Media group received (MP3 + lyrics)
- Caption shows quality scores + verdict
- YouTube links are clickable
- Emoji icons are correct (🏆 for HERO, ✅ for STANDARD)

**File verification**: Navigate to D-drive in Windows:
```
D:\Hermes\songs\nightly-songs\2026-05-17\
```
- All files should be present
- File sizes should match the originals

### FAIL Signals

| Signal | Meaning |
|--------|---------|
| `Log ❌` | JSON write failed — check disk space or permissions |
| `D-drive sync ❌` | Copy failed — WSL mount issue |
| `Telegram ❌` | Bot token invalid or network issue |
| D-drive shows 0 files | Sync path is wrong |
| Telegram caption shows `None` for score | Quality verdict not attached to song data |

### Inspectable Artifacts

| Artifact | Path | What to check |
|----------|------|---------------|
| Song log | `logs/song-log-2026-05.json` | JSON structure, completeness, no corruption |
| D-drive mirror | `/mnt/d/Hermes/songs/nightly-songs/YYYY-MM-DD/` | File presence, sizes |
| Telegram chat | @OpenCodeWorkerBot chat | Media group message, links, scores |

### Song Log JSON Structure

```json
{
  "date": "2026-05-17",
  "song_number": 1,
  "title": "春日暖阳",
  "quality_score": 8.9,
  "quality_verdict": "hero",
  "mood_label": "romantic",
  "color_palette": "#FF9F9F|#FFC8A2",
  "weekly_theme": "sad",
  "youtube_url": "https://youtube.com/watch?v=abc123def",
  "youtube_status": "ok",
  "short_youtube_url": "https://youtube.com/shorts/xyz789ghi",
  "short_upload_status": "ok",
  "d_drive_synced": true,
  "telegram_sent": true,
  "duration_sec": 187.5
}
```

---

## Stage I: Compilation (Sunday Only)

### Console Output

```
[STAGE I] Weekly Compilation
  Date: 2026-05-17 (Sunday)
  Source videos found: 7 (Mon-Sun Hero)
  Skipped days: Wed (no Hero video — was Standard only)
  ├─ Mon: 春日暖阳 (187s)
  ├─ Tue: 夜的思念 (195s)
  ├─ Wed: ⏭ skipped
  ├─ Thu: 雨中的约定 (201s)
  ├─ Fri: 星光舞曲 (178s)
  ├─ Sat: 微风轻语 (188s)
  └─ Sun: 晨光序曲 (182s)

  compilation.mp4: output/compilations/2026-05-17-compilation.mp4
    ✅ (320MB, 1920x1080)
    Duration: 15:31 (5 videos × ~3:00)
    Chapters: 5 (one per included day, with timestamps)
    Codec: H.264 ✅  |  Audio: AAC ✅

  Upload:
    ✅ video_id=comp123xyz
    URL: https://youtube.com/watch?v=comp123xyz
    Scheduled: 2026-05-17T18:00:00+08:00 (6pm SGT)
    Thumbnail: ✅ Set

  Cleanup:
    ✅ Source MP4s cleaned up (5 individual files removed)
```

### PASS Conditions

| Check | How to verify |
|-------|---------------|
| At least 2 source videos found | Compilation requires minimum 2 videos |
| compilation.mp4 exists and > 50MB | Real video was concatenated |
| Duration is reasonable | ~3 min per source video × number of days |
| Chapters are listed in output | Each included day has a timestamp |
| Upload succeeded with `✅` | video_id returned from YouTube |
| Scheduled at 18:00 SGT | Sunday evening timeslot |

**Critical verification**: Play the compilation MP4 and check:
- Videos play in correct day order (Mon-Sun)
- Transitions between songs are clean
- No black frames or glitches at seam points
- Audio stays in sync across concatenation
- Chapter timestamps in description jump to correct days
- Thumbnail represents the weekly compilation theme

### FAIL Signals

| Signal | Meaning |
|--------|---------|
| `< 2 videos from Mon-Sat` | Not enough content — compilation skipped |
| `Compilation skipped (disabled in config)` | Feature toggled off |
| `Codec mismatch — falling back to re-encode` | Videos had different codec params (slower but still succeeds) |
| `Re-encode failed` | Chained re-encode also failed — likely a corrupt source video |
| `Duration exceeds 12h` | YouTube limit — truncated |
| `Upload failed` | API error (see Stage G troubleshooting) |

### Chapter Format in YouTube Description

When chapters are generated, they appear in the video description as:

```
00:00 - Monday: 春日暖阳
03:12 - Tuesday: 夜的思念
06:31 - Thursday: 雨中的约定
10:04 - Friday: 星光舞曲
13:19 - Saturday: 微风轻语
```

YouTube auto-detects these as chapter markers when the first timestamp is `00:00`.

### Inspectable Artifacts

| Artifact | Path | What to check |
|----------|------|---------------|
| compilation.mp4 | `output/compilations/YYYY-MM-DD-compilation.mp4` | Play it, verify chapters, check quality |
| YouTube URL | From console output | Click link, verify scheduling |

---

## Quick Reference: File Names by Stage

| Stage | Creates | File Pattern |
|-------|---------|-------------|
| A | (none) | — |
| B | MP3, TXT | `NN-title.mp3`, `NN-title.txt` |
| C | (none) | — |
| D | bg.jpg, bg-vertical.jpg, thumb.jpg | `NN-title-bg.jpg`, `NN-title-bg-vertical.jpg`, `NN-title-thumb.jpg` |
| E | viz.mp4, viz.srt | `NN-title-viz.mp4`, `NN-title.srt` |
| F | short.mp4 | `NN-title-short.mp4` |
| G | (YouTube API) | video_id stored in console + log |
| H | log JSON, synced files | `logs/song-log-YYYY-MM.json`, D-drive copy |
| I | compilation.mp4 | `output/compilations/YYYY-MM-DD-compilation.mp4` |

---

## Quick Reference: What to Check Per Stage (30-Second Version)

| Stage | Quick check | Time |
|-------|------------|------|
| A | Are there songs for generation? | 5s |
| B | Can I play the MP3? | 30s |
| C | Are scores reasonable? | 10s |
| D | Do images match song mood? | 10s per image |
| E | Does the MP4 have waveform + SRT? | 20s per video |
| F | Is the Short vertical and ≈30s? | 20s per Short |
| G | Click YouTube URL — does it load? | 10s per URL |
| H | Check Telegram — did message arrive? | 10s |
| I | Can I jump between chapters? | 30s |
