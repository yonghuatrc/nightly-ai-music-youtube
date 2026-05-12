#!/usr/bin/env python3
"""
check-duplicate.py
Reads song-log JSON files and returns (style_reference, language) pairs
from the last 7 days as JSON. Used by nightly_music.py for dedup.
Output: JSON array of {style_reference, language, date} objects.

Usage:
    python3 check-duplicate.py
    python3 check-duplicate.py --days 7
"""
import argparse
import glob
import json
import os
import sys
from datetime import datetime, timedelta


PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(PROJECT_DIR, "logs")


def load_recent_entries(days=7):
    cutoff = datetime.now().date() - timedelta(days=days)
    entries = []

    patterns = [
        os.path.join(LOG_DIR, "song-log-*.json"),
    ]
    for pattern in patterns:
        for path in sorted(glob.glob(pattern)):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    entries.extend(data)
            except (json.JSONDecodeError, OSError):
                continue

    recent = []
    for entry in entries:
        try:
            entry_date = datetime.strptime(entry.get("date", ""), "%Y-%m-%d").date()
            if entry_date >= cutoff:
                recent.append(entry)
        except (ValueError, TypeError):
            continue

    return recent


def get_blocked_pairs(days=7):
    entries = load_recent_entries(days)
    blocked = []
    for entry in entries:
        style_ref = entry.get("style_reference", "")
        language = entry.get("language", "")
        date = entry.get("date", "")
        if style_ref and language:
            blocked.append({
                "style_reference": style_ref,
                "language": language,
                "date": date,
            })
    return blocked


def main():
    parser = argparse.ArgumentParser(
        description="Check for duplicate style+language pairs in song log"
    )
    parser.add_argument("--days", type=int, default=7,
                        help="Number of days to look back (default: 7)")
    args = parser.parse_args()

    blocked = get_blocked_pairs(args.days)
    json.dump(blocked, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.flush()


if __name__ == "__main__":
    main()
