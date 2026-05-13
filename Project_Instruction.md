# Project: Nightly AI Music — YouTube Channel

## Overview

Every night at 2am, generate 2 AI songs (trending SG/MY style across EN/ZH/KR/JP languages), deliver 9am Telegram notification with lyrics + audio files. Goal: populate a YouTube channel showcasing that AI-generated music can be high quality. 1-week trial run first.

**Owner:** Dennis Ng
**Status:** Planning
**Created:** 2026-05-05
**Trial:** 2026-05-06 to 2026-05-13 (7 nights)

---

## Background

Boss wants to start a YouTube channel that openly publishes AI-created songs daily — to demonstrate that AI music can be quality and enjoyable. The channel should be transparent that songs are AI-generated.

**The pitch:** "AI songs can be good. Here's proof, every day."

---

## The Deal

| Item | Value |
|------|-------|
| Songs per night | 2 |
| Trigger time | 2:00am daily |
| Delivery time | 9:00am Telegram |
| Languages | Random: English / Chinese / Korean / Japanese |
| Style source | Trending in Singapore + TikTok SG |
| Song log | Yes — prompt logged before each generation, 7-day dedup |
| Content allowed | Any lyrics (no filtering) |
| Rate limits | Ignored — 2 songs/night is within safe range |

---

## Pipeline Architecture

```
2:00am ──→ RESEARCH trending SG/MY charts
             (TikTok SG, Spotify SG/MY, YouTube SG, Google Trends)

           CHECK song-log.json (past 7 days)
           → avoid duplicating style_reference + language combo

           SELECT 2 styles (ideally different languages)
           → Random between EN/ZH/KR/JP
           → Style description in matching language:
              ZH/KR/JP songs → Chinese description ("仿林俊杰抒情风")
              EN songs → English description ("upbeat TikTok pop")

           GENERATE via MiniMax Music API
           → If failure: retry once, then skip song

           LOG prompt + lyrics + audio path to song-log.json

9:00am ──→ TELEGRAM: both songs
             → Audio file attached
             → Lyrics in message body
             → Song #1 details + Song #2 details
```

---

## Log Format

**File:** `~/.hermes/work_logs/nightly-songs/song-log.json`

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

---

## Implementation Tasks

### Task 1: Verify MiniMax Music API
**Goal:** Confirm API skill exists, credentials work, can generate music.

- Read skill: `skill_view(name='minimax-music-api')`
- Run a minimal test call to confirm auth
- If API fails → document error, escalate to Boss before proceeding

**Verification:** API returns valid response (song file or job ID) without auth error.

---

### Task 2: Build log + dedup infrastructure
**Goal:** Create the JSON log system and dedup checker.

Files to create:
- `~/.hermes/nightly-songs/` — output directory for audio files
- `~/.hermes/work_logs/nightly-songs/song-log.json` — master log (init with `[]`)
- `~/.hermes/scripts/check-duplicate.py` — Python dedup checker

```python
# check-duplicate.py logic:
# - Load song-log.json
# - Filter entries within last 7 days
# - Return set of (style_reference, language) tuples already used
# - Script prints list for inspection
```

**Verification:** Running `python check-duplicate.py` returns empty list on fresh log.

---

### Task 3: Verify Telegram file delivery
**Goal:** Confirm we can send audio files + long-form text to Telegram.

- Create small test audio file (or reuse existing)
- `send_message` with `MEDIA:/path/to/audio.mp3` + lyrics caption
- Confirm both audio and text arrive correctly

**Verification:** Telegram message shows audio player + lyrics text.

---

### Task 4: Write full nightly cron prompt
**Goal:** Create self-contained cron prompt that does the entire pipeline.

The prompt must include:
1. Research step — pull from TikTok SG, Spotify SG, YouTube SG (use web search)
2. Dedup check — call check-duplicate.py, interpret output
3. Style selection — pick 2 trending songs, respect language/prompt language rule
4. Generation — call MiniMax Music API for each song
5. Logging — append entry to song-log.json
6. Telegram delivery — send both songs at 9am (use separate send_message calls)

Language rule reminder in prompt:
- ZH/KR/JP song → style description in Chinese
- EN song → style description in English

**Create cron job:**
```python
cronjob(
  action='create',
  name='Nightly AI Music Generation',
  prompt=<full self-contained prompt>,
  schedule='0 2 * * *',
  skills=['minimax-music-api', 'web-search-guardrails']
)
```

**Verification:** Cron job created and appears in `cronjob(action='list')`.

---

### Task 5: DRY RUN — Full pipeline end-to-end
**Goal:** Execute everything RIGHT NOW (not scheduled) to prove it works before going live.

Steps:
1. Run the full nightly prompt manually as a one-off test
2. Check: audio files exist in `~/.hermes/nightly-songs/`
3. Check: `song-log.json` has 2 new entries
4. Check: Telegram received 2 audio files + lyrics
5. Check: No duplicate in log (run check-duplicate.py)

**This is the gate — Task 5 MUST pass before scheduling the cron.**

**Verification:** 2 songs in Telegram with lyrics, both logged correctly, dedup check clean.

---

## Test Plan (before and during trial)

### Test 1: Dedup
- Night 2 pipeline must not repeat Night 1's (style_reference + language)
- Run manually 2 nights in a row if needed to confirm

### Test 2: Multi-language coverage
- Over 7 nights, expect mix of EN/ZH/KR/JP
- Spot-check that style descriptions match language rules

### Test 3: Failure handling
- Break MiniMax API intentionally (wrong key)
- Confirm cron sends "generation failed" morning message

### Test 4: 7-day log pruning
- After Day 8, log should not grow indefinitely
- Entries older than 7 days should not affect dedup (but keep them for record)

---

## Success Criteria (end of 1-week trial)

| Metric | Target |
|--------|--------|
| Successful generations | ≥ 12/14 songs (allow 2 failures) |
| Morning notification rate | 7/7 days delivered by 9am |
| Dedup compliance | 0 duplicate style+language pairs |
| Audio playable | All files openable as MP3 |
| YouTube publishable | Boss can take audio file → upload to YouTube |

---

## Morning Notification Format

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

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| MiniMax API downtime at 2am | Songs missed | Retry once; if still fail, skip and notify |
| Song quality poor | Wasted nights | Boss can react to morning notification — adjust style prompt if needed |
| Duplicate style selected | Less variety | 7-day dedup check is aggressive enough |
| YouTube copyright claim | Channel risk | Boss is aware AI songs may trigger claims; project is explicit about AI origin |

---

## Next Action

**Execute Task 1:** Verify MiniMax Music API is callable and has valid credentials.

---

## Related

- MiniMax Music API skill: `minimax-music-api`
- Telegram delivery via: `send_message` tool
- Boss's YouTube channel goal: transparent AI music daily
