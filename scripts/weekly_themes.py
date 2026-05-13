#!/usr/bin/env python3
"""
weekly_themes.py — Day-of-week mood/theme modifiers for song prompt generation.

Sprint 3 of Phase 2: Injects weekly themes into song prompts so each day's
content has a consistent mood/vibe. Helps search discovery, channel identity,
and algorithm clustering.

Usage:
    from weekly_themes import get_today_theme, apply_theme_to_prompt

    theme = get_today_theme("2026-05-18")  # Monday
    if theme:
        prompt = apply_theme_to_prompt(base_prompt, theme, song_number=1)
"""

import datetime

WEEKLY_THEMES = {
    "Monday":    {"emoji": "🌅", "mood": "upbeat",    "style": "正能量华语流行",       "keywords": "开工,向上,阳光,希望,奋斗"},
    "Tuesday":   {"emoji": "💔", "mood": "melancholy", "style": "R&B抒情慢歌",          "keywords": "思念,深夜,回忆,遗憾,错过"},
    "Wednesday": {"emoji": "💌", "mood": "romantic",   "style": "华语浪漫情歌",         "keywords": "爱,心动,告白,温柔,甜蜜"},
    "Thursday":  {"emoji": "🌧️", "mood": "sad",        "style": "华语伤感抒情",         "keywords": "雨,泪,离别,心痛,孤独"},
    "Friday":    {"emoji": "🎉", "mood": "energetic",  "style": "华语流行舞曲",         "keywords": "周末,狂欢,自由,快乐,释放"},
    "Saturday":  {"emoji": "🌟", "mood": "chill",      "style": "华语治愈民谣",         "keywords": "星空,宁静,温暖,放松,治愈"},
    "Sunday":    {"emoji": "🌙", "mood": "calm",       "style": "华语轻柔安眠",         "keywords": "晚安,梦境,温柔,月光,安宁"},
}


def get_today_theme(date_str=None):
    """Get the weekly theme for a given date.

    Args:
        date_str: "YYYY-MM-DD" format. If None, uses today.

    Returns:
        dict with emoji, mood, style, keywords keys, or None if day not in table.
    """
    if date_str:
        try:
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return None
    else:
        dt = datetime.datetime.now()

    day_name = dt.strftime("%A")  # "Monday", "Tuesday", etc.
    return WEEKLY_THEMES.get(day_name)


def apply_theme_to_prompt(base_prompt, theme, song_number=1):
    """Inject weekly theme into a song prompt.

    Args:
        base_prompt: Original style prompt from fetch_trending.
        theme: dict from get_today_theme().
        song_number: 1=Hero (strongly themed), 2=Standard (more subtle).
                     Higher numbers also use subtle styling.

    Returns:
        Modified prompt string with theme injected. Returns base_prompt
        unchanged if theme is None.
    """
    if not theme:
        return base_prompt

    # Song 1 (Hero): strongly themed with full style + keywords
    # Song 2+ (Standard/others): more subtle, just mood
    if song_number == 1:
        modifier = f"{theme['style']}，{theme['keywords']}主题"
    else:
        modifier = f"{theme['mood']}风格"

    return f"{base_prompt}，{modifier}"
