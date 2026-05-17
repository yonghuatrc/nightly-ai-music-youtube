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

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Genre-specific prompt keywords")
    parser.add_argument("--genre", "-g", type=str, required=True, help="Genre name")
    args = parser.parse_args()
    prompt = build_genre_style_prompt("测试歌曲", "测试歌手", args.genre)
    print(prompt)
