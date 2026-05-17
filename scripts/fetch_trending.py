#!/usr/bin/env python3
"""
fetch_trending.py — Fetch trending Chinese songs from configurable sources.

Usage:
    python3 fetch_trending.py --source qq-douyin --count 15
    python3 fetch_trending.py --source pool --count 10
    python3 fetch_trending.py --source qq-douyin --count 10 --language chinese

Output: JSON array of {song, artist, source, style_prompt}
"""

import argparse
import json
import os
import random
import re
import sys
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# ---------------------------------------------------------------------------
# CHINESE STYLE DIMENSIONS — used to build varied prompts per song
# ---------------------------------------------------------------------------
GENRES = [
    "华语流行抒情", "华语R&B", "华语民谣", "华语古风",
    "华语轻摇滚", "华语流行舞曲", "华语伤感情歌", "华语嘻哈",
    "华语电子流行", "华语流行说唱", "华语治愈系", "华语中国风",
    "华语仙侠风",
]

INSTRUMENTS = [
    "钢琴为主", "吉他伴奏", "弦乐铺底", "钢琴与弦乐",
    "电子节拍", "钢琴与吉他", "古筝与笛", "钢琴与鼓",
]

VOCALS = [
    "温暖男声", "温柔女声", "清澈男声", "磁性男声",
    "甜美女声", "治愈女声", "深情男声", "空灵女声",
]

MOODS = [
    "旋律朗朗上口", "情感充沛", "副歌高亢有力",
    "节奏明快", "温柔舒缓", "轻快活泼",
    "深情款款", "治愈温暖",
]

# ---------------------------------------------------------------------------
# HARDCODED CHINESE FALLBACK POOL (20+ entries, always works)
# ---------------------------------------------------------------------------
FALLBACK_POOL = [
    {"song": "晴天",       "artist": "周杰伦", "source": "pool",
     "style_prompt": "华语流行抒情，钢琴为主，温暖男声，旋律朗朗上口"},
    {"song": "告白气球",   "artist": "周杰伦", "source": "pool",
     "style_prompt": "华语流行，轻快R&B节奏，温暖男声，副歌旋律上口"},
    {"song": "七里香",     "artist": "周杰伦", "source": "pool",
     "style_prompt": "华语流行民谣，吉他伴奏，温暖男声，治愈温暖风格"},
    {"song": "演员",       "artist": "薛之谦", "source": "pool",
     "style_prompt": "华语伤感情歌，钢琴为主，深情男声，情感充沛"},
    {"song": "丑八怪",     "artist": "薛之谦", "source": "pool",
     "style_prompt": "华语流行抒情，钢琴与弦乐，磁性男声，副歌高亢有力"},
    {"song": "刚刚好",     "artist": "薛之谦", "source": "pool",
     "style_prompt": "华语伤感流行，钢琴与吉他，深情男声，温柔舒缓"},
    {"song": "她说",       "artist": "林俊杰", "source": "pool",
     "style_prompt": "华语抒情R&B，钢琴为主，温暖男声，情感充沛"},
    {"song": "可惜没如果", "artist": "林俊杰", "source": "pool",
     "style_prompt": "华语流行抒情，钢琴与弦乐，温暖男声，旋律朗朗上口"},
    {"song": "修炼爱情",  "artist": "林俊杰", "source": "pool",
     "style_prompt": "华语流行，电子节拍，温暖男声，轻快活泼风格"},
    {"song": "泡沫",       "artist": "邓紫棋", "source": "pool",
     "style_prompt": "华语流行抒情，钢琴为主，温柔女声，副歌高亢有力"},
    {"song": "光年之外",  "artist": "邓紫棋", "source": "pool",
     "style_prompt": "华语流行，电子流行节拍，治愈女声，节奏明快"},
    {"song": "句号",       "artist": "邓紫棋", "source": "pool",
     "style_prompt": "华语R&B流行，钢琴与鼓，温柔女声，情感充沛"},
    {"song": "年少有为",  "artist": "李荣浩", "source": "pool",
     "style_prompt": "华语流行抒情，吉他伴奏，温暖男声，深情款款"},
    {"song": "麻雀",       "artist": "李荣浩", "source": "pool",
     "style_prompt": "华语流行，轻摇滚节奏，温暖男声，旋律朗朗上口"},
    {"song": "不将就",     "artist": "李荣浩", "source": "pool",
     "style_prompt": "华语抒情R&B，钢琴与吉他，温暖男声，情感充沛"},
    {"song": "夜曲",       "artist": "周杰伦", "source": "pool",
     "style_prompt": "华语R&B流行，钢琴与弦乐，温暖男声，深情忧郁风格"},
    {"song": "成都",       "artist": "赵雷",    "source": "pool",
     "style_prompt": "华语民谣，吉他伴奏，清澈男声，治愈温暖风格"},
    {"song": "南山南",     "artist": "马頔",    "source": "pool",
     "style_prompt": "华语民谣，吉他为主，温暖男声，深情舒缓风格"},
    {"song": "小幸运",     "artist": "田馥甄", "source": "pool",
     "style_prompt": "华语流行抒情，钢琴为主，甜美女声，旋律朗朗上口"},
    {"song": "追光者",     "artist": "岑宁儿", "source": "pool",
     "style_prompt": "华语流行，吉他伴奏，治愈女声，温暖舒缓风格"},
    {"song": "起风了",     "artist": "买辣椒也用券", "source": "pool",
     "style_prompt": "华语流行，钢琴与弦乐，清澈男声，情感充沛副歌"},
    {"song": "有可能的夜晚","artist": "曾轶可", "source": "pool",
     "style_prompt": "华语流行，吉他伴奏，温柔女声，轻快活泼风格"},
    {"song": "老街",       "artist": "李荣浩", "source": "pool",
     "style_prompt": "华语流行抒情，吉他与弦乐，温暖男声，怀旧治愈风格"},
    {"song": "后来的我们", "artist": "五月天", "source": "pool",
     "style_prompt": "华语流行摇滚，吉他为主，温暖男声，情感充沛"},
    {"song": "突然好想你", "artist": "五月天", "source": "pool",
     "style_prompt": "华语流行摇滚，钢琴与吉他，温暖男声，深情款款"},
]


# ---------------------------------------------------------------------------
# USER-AGENT
# ---------------------------------------------------------------------------
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/125.0.0.0 Safari/537.36"
}


# ---------------------------------------------------------------------------
# HELPERS — build style prompt from song + artist
# ---------------------------------------------------------------------------
def build_style_prompt(song, artist, genre=None):
    """Generate a MiniMax-compatible style description from a song+artist pair."""
    if genre:
        from genre_keywords import build_genre_style_prompt
        return build_genre_style_prompt(song, artist, genre)
    g = random.choice(GENRES)
    inst = random.choice(INSTRUMENTS)
    vocal = random.choice(VOCALS)
    mood = random.choice(MOODS)
    return f"类似{artist}的《{song}》风格，{g}，{inst}，{vocal}，{mood}"


# ---------------------------------------------------------------------------
# SOURCE 1: QQ Music 抖音热歌榜
# ---------------------------------------------------------------------------
QQ_DOUYIN_URL = "https://y.qq.com/n/ryqq/toplist/60"


def fetch_qq_douyin(count=15, genre=None):
    """Scrape QQ Music 抖音热歌榜 for song names and artists using embedded JSON data."""
    try:
        req = Request(QQ_DOUYIN_URL, headers=HEADERS)
        with urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        # The page has inline JSON with a rankList array containing
        # {title, singerName, ...} for each song.
        # Extract it from script context or by finding 'rankList' pattern
        results = []

        # Try to extract rankList JSON directly
        ranklist_match = re.search(r'"rankList":\s*(\[.*?\])\s*(?:,"historyarr"|\s*})', html, re.DOTALL)
        if ranklist_match:
            try:
                ranklist = json.loads(ranklist_match.group(1))
                for item in ranklist:
                    title = item.get("title", "")
                    singer = item.get("singerName", "")
                    if title and singer:
                        # Split multiple artists (e.g. "Justin Bieber/Nicki Minaj")
                        primary_artist = singer.split("/")[0].split("\\/")[0].strip()
                        # Only include Chinese songs
                        if re.search(r'[\u4e00-\u9fff]', title):
                            results.append({
                                "song": title.strip(),
                                "artist": primary_artist,
                                "source": "qq-douyin",
                            })
            except (json.JSONDecodeError, KeyError):
                pass

        if not results:
            # Fallback: parse song names from HTML song links
            song_matches = re.findall(
                r'/songDetail/[^"]+"[^>]*>([^<]+)<', html
            )
            # Find artist names from playlist__author links
            artist_matches = re.findall(
                r'playlist__author"[^>]*title="([^"]+)"', html
            )
            # Pair them
            for i, song_name in enumerate(song_matches):
                song_name = song_name.strip()
                if re.search(r'[\u4e00-\u9fff]', song_name):
                    artist = artist_matches[i] if i < len(artist_matches) else ""
                    results.append({
                        "song": song_name,
                        "artist": artist,
                        "source": "qq-douyin",
                    })

        # Deduplicate
        seen = set()
        unique = []
        for r in results:
            key = (r["song"], r["artist"])
            if key not in seen:
                seen.add(key)
                unique.append(r)

        if not unique:
            print("[fetch] qq-douyin: parsed 0 songs, falling back", file=sys.stderr)
            return None

        # Build style prompts
        for r in unique:
            r["style_prompt"] = build_style_prompt(r["song"], r["artist"], genre=genre)

        print(f"[fetch] qq-douyin: got {len(unique)} songs", file=sys.stderr)
        return unique[:count]

    except Exception as e:
        print(f"[fetch] qq-douyin error: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# SOURCE 2: KKBOX 華語單曲日榜
# ---------------------------------------------------------------------------
KKBOX_URL = "https://kma.kkbox.com/charts/daily/song?terr=tw&lang=tc&cate=297"


def fetch_kkbox(count=15, genre=None):
    """
    Attempt to scrape KKBOX daily chart.
    Note: Page loads chart data via JS. We try to find any embedded data
    or fall back to searching for KKBOX trending via web search pattern.
    """
    try:
        req = Request(KKBOX_URL, headers={
            **HEADERS,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        })
        with urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        # The page is JS-rendered, but sometimes songs appear in meta tags
        # or in JSON-LD structured data
        songs = []

        # Try JSON-LD / structured data
        jsonld = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)
        for jd in jsonld:
            try:
                data = json.loads(jd)
                # Look for song data in the structure
                if isinstance(data, dict):
                    items = data.get("itemListElement", []) or data.get("items", [])
                    for item in items:
                        if isinstance(item, dict):
                            name = item.get("name", "")
                            if name and re.search(r'[\u4e00-\u9fff]', name):
                                # Name might be "Song - Artist" or just "Song"
                                # Try to extract artist
                                songs.append({"song": name, "artist": "", "source": "kkbox"})
            except (json.JSONDecodeError, AttributeError):
                pass

        # Try state/initial data patterns
        state_data = re.findall(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', html, re.DOTALL)
        for sd in state_data:
            try:
                data = json.loads(sd)
                # Navigate the state structure looking for song data
                def find_songs(obj, depth=0):
                    found = []
                    if depth > 5:
                        return found
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            if k in ("song", "songs", "track", "tracks", "items", "charts", "data"):
                                found.extend(find_songs(v, depth + 1))
                            elif k in ("name", "title", "songName", "trackName"):
                                if isinstance(v, str) and re.search(r'[\u4e00-\u9fff]', v):
                                    artist = ""
                                    if "artist" in obj:
                                        artist = obj.get("artist", "") or obj.get("artistName", "")
                                    elif "singer" in obj:
                                        artist = obj.get("singer", "")
                                    found.append({"song": v, "artist": artist, "source": "kkbox"})
                            elif isinstance(v, (dict, list)):
                                found.extend(find_songs(v, depth + 1))
                    elif isinstance(obj, list):
                        for item in obj:
                            found.extend(find_songs(item, depth + 1))
                    return found
                songs.extend(find_songs(data))
            except (json.JSONDecodeError, AttributeError):
                pass

        # Deduplicate
        seen = set()
        unique = []
        for r in songs:
            key = (r["song"], r.get("artist", ""))
            if key not in seen:
                seen.add(key)
                unique.append(r)

        if unique:
            for r in unique:
                if not r.get("style_prompt"):
                    r["style_prompt"] = build_style_prompt(r["song"], r.get("artist", "华语歌手"), genre=genre)
            return unique[:count]

        # If still empty, fall back
        print("[fetch] kkbox: no song data found (JS-rendered page)", file=sys.stderr)
        return None

    except Exception as e:
        print(f"[fetch] kkbox error: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# SOURCE 3: MY FM RIM 劲爆排行榜
# ---------------------------------------------------------------------------
# MY FM doesn't have a structured web chart. We try to find chart info
# from MY FM website or fall back to pool.
MYFM_URL = "https://my.com.my/home-my-fm"


def fetch_myfm(count=15, genre=None):
    """
    Attempt to find MY FM RIM 劲爆排行榜 chart from MY FM website.
    The chart is primarily shared as Instagram images, but there may be
    text mentions on their website.
    """
    try:
        req = Request(MYFM_URL, headers=HEADERS)
        with urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        # Look for song names mentioned in text
        # MY FM posts typically have song names in article/list format
        songs = []

        # Find any Chinese text that looks like song names
        # e.g., "LBI利比《跳楼机》" or similar patterns
        chart_mentions = re.findall(r'[\u4e00-\u9fff]+[《（(][\u4e00-\u9fff\w]+[》）)]', html)
        for mention in chart_mentions:
            # Try to extract: Artist《Song》or Artist(Song) pattern
            m = re.match(r'([\u4e00-\u9fa5a-zA-Z\s]+)[（(《]([^）)》]+)[）)》]', mention)
            if m:
                artist = m.group(1).strip()
                song = m.group(2).strip()
                if song and re.search(r'[\u4e00-\u9fff]', song):
                    songs.append({
                        "song": song,
                        "artist": artist,
                        "source": "my-fm",
                    })

        # Deduplicate
        seen = set()
        unique = []
        for r in songs:
            key = r["song"]
            if key not in seen:
                seen.add(key)
                unique.append(r)

        if unique:
            for r in unique:
                r["style_prompt"] = build_style_prompt(r["song"], r["artist"], genre=genre)
            return unique[:count]

        print("[fetch] my-fm: no chart data found on website", file=sys.stderr)
        return None

    except Exception as e:
        print(f"[fetch] my-fm error: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# GENERIC WEB SEARCH — handles unknown sources dynamically
# ---------------------------------------------------------------------------
DDG_LITE_URL = "https://lite.duckduckgo.com/lite/"


def fetch_generic(source_name, count=15, genre=None):
    """
    Generic fetcher for unknown sources.
    Uses DuckDuckGo search to find trending songs for the given source name.
    Extracts Chinese song names from search snippets.
    """
    try:
        import urllib.parse
        # Search for the source + trending Chinese songs
        query = urllib.parse.quote(f"{source_name} 排行榜 2026 热门歌曲 华语")
        req = Request(f"{DDG_LITE_URL}?q={query}", headers=HEADERS)
        with urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        results = []

        # Extract search result snippets (DDG Lite format)
        snippets = re.findall(r'<a[^>]*class="result__a"[^>]*>(.*?)</a>', html, re.DOTALL)
        if not snippets:
            # Fallback: get any text between tags that looks like content
            snippets = re.findall(r'>([^<]{10,200})<', html)

        for snippet in snippets:
            text = re.sub(r'<[^>]+>', '', snippet).strip()
            # Pattern 1: "Song - Artist"
            pairs = re.findall(r'([\u4e00-\u9fff\w\s]{2,30})[—\-–]([\u4e00-\u9fff\w\s.]{2,30})', text)
            for song, artist in pairs:
                song = song.strip()
                artist = artist.strip()
                if re.search(r'[\u4e00-\u9fff]', song) and len(song) >= 2:
                    if not any(kw in song for kw in ["排行", "榜首", "冠军", "榜单", "最新", "热门"]):
                        results.append({"song": song, "artist": artist, "source": source_name})

            # Pattern 2: Artist《Song》
            pairs2 = re.findall(r'([\u4e00-\u9fff\w\s.]{2,20})[《（]([^》 ）]+)[》）]', text)
            for artist, song in pairs2:
                song = song.strip()
                artist = artist.strip()
                if re.search(r'[\u4e00-\u9fff]', song) and len(song) >= 2:
                    results.append({"song": song, "artist": artist, "source": source_name})

        # Deduplicate
        seen = set()
        unique = []
        for r in results:
            key = (r["song"], r["artist"])
            if key not in seen:
                seen.add(key)
                unique.append(r)

        if unique:
            for r in unique:
                r["style_prompt"] = build_style_prompt(r["song"], r["artist"], genre=genre)
            print(f"[fetch] {source_name}: got {len(unique)} songs via search", file=sys.stderr)
            return unique[:count]

        print(f"[fetch] {source_name}: no songs found in search results", file=sys.stderr)
        return None

    except Exception as e:
        print(f"[fetch] {source_name} search error: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# POOL FALLBACK
def fetch_pool(count=15, genre=None):
    """Return songs from the hardcoded Chinese fallback pool."""
    pool = list(FALLBACK_POOL)
    random.shuffle(pool)
    result = pool[:count]
    if genre:
        for r in result:
            r["style_prompt"] = build_style_prompt(r["song"], r["artist"], genre=genre)
    return result


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Fetch trending Chinese songs from configurable sources"
    )
    parser.add_argument(
        "--source", "-s",
        default="qq-douyin",
        help="Trending source to fetch from. Known: qq-douyin, kkbox, my-fm, pool. Unknown sources use generic web search."
    )
    parser.add_argument(
        "--count", "-c",
        type=int,
        default=15,
        help="Number of songs to return (default: 15)"
    )
    parser.add_argument(
        "--language", "-l",
        default="chinese",
        help="Language filter (default: chinese)"
    )
    parser.add_argument(
        "--genre", "-g",
        type=str,
        default=None,
        help="Genre for style prompt generation"
    )

    args = parser.parse_args()

    # Route to the correct fetcher
    known_fetchers = {
        "qq-douyin": fetch_qq_douyin,
        "kkbox": fetch_kkbox,
        "my-fm": fetch_myfm,
        "pool": fetch_pool,
    }

    fetcher = known_fetchers.get(args.source)
    if fetcher is None:
        print(f"[fetch] '{args.source}' is not a known source, using generic web search",
              file=sys.stderr)
        fetcher = lambda c, g=None: fetch_generic(args.source, c, genre=g)

    # Try primary source
    result = fetcher(args.count, args.genre)

    # Fall back to pool if primary source failed
    if result is None or len(result) == 0:
        source_label = args.source
        print(f"[fetch] {source_label} returned no results, falling back to pool",
              file=sys.stderr)
        result = fetch_pool(args.count, genre=args.genre)
        # Mark them as pool-sourced so user knows
        for r in result:
            r["source"] = f"{args.source}-fallback"

    # Ensure we have enough
    if len(result) < args.count:
        # Pad with pool entries
        pool = fetch_pool(args.count * 2, genre=args.genre)
        existing_keys = {(r["song"], r.get("artist", "")) for r in result}
        for r in pool:
            if (r["song"], r.get("artist", "")) not in existing_keys and len(result) < args.count:
                r["source"] = "pool-padding"
                result.append(r)

    # Output JSON
    json.dump(result[:args.count], sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.flush()


if __name__ == "__main__":
    main()
