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

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Daily genre rotation schedule")
    parser.add_argument("--all", action="store_true", help="Print full week schedule")
    parser.add_argument("--date", type=str, help="Get genre for specific date (YYYY-MM-DD)")
    args = parser.parse_args()

    if args.all:
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for d in range(7):
            g = GENRE_SCHEDULE[d]
            m = GENRE_METADATA[g]
            print(f"{day_names[d]:>9}: {m['emoji']} {g} ({m['style']})")
    elif args.date:
        print(get_daily_genre(args.date))
    else:
        print(get_daily_genre())
