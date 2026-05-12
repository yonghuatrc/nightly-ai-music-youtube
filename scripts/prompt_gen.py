#!/usr/bin/env python3
"""
prompt_gen.py — LLM-based image prompt generation for ManggoMusicCH

Uses MiniMax M2.7 text chat (via mmx CLI) to generate detailed image prompts
from song titles and lyrics, suitable for Pollinations.ai image generation.

Priority chain:
  1. MiniMax M2.7 text chat (via mmx CLI)
  2. Pollinations.ai text endpoint (fallback)
  3. Rule-based keyword extraction (last resort)

Usage:
    python3 prompt_gen.py --title "Song Title" --lyrics "..."
    python3 prompt_gen.py --title "Song" --lyrics "..." --orientation vertical --out prompt.json
"""

import subprocess
import json
import os
import urllib.parse

import requests

MMX_BIN = "/home/dennis/.hermes/node/bin/mmx"


# ---------------------------------------------------------------------------
# Backend 1: MiniMax M2.7 text chat (via mmx CLI)
# ---------------------------------------------------------------------------
def _call_minimax_llm(system, user, timeout=15):
    """Call MiniMax M2.7 text chat. Returns response text or None."""
    cmd = [
        MMX_BIN, "text", "chat",
        "--non-interactive", "--quiet", "--output", "json",
        "--temperature", "0.7", "--max-tokens", "300",
        "--message", f"system:{system}",
        "--message", f"user:{user}",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get("content", "").strip()
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Backend 2: Pollinations.ai text endpoint (free, no API key)
# ---------------------------------------------------------------------------
def _call_pollinations_text(prompt, timeout=10):
    """Fallback: use Pollinations.ai text endpoint."""
    try:
        url = f"https://text.pollinations.ai/{urllib.parse.quote(prompt)}"
        resp = requests.get(url, timeout=timeout)
        if resp.ok:
            return resp.text.strip()
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Backend 3: Rule-based fallback
# ---------------------------------------------------------------------------
def _rule_based_fallback(title, lyrics, style_tags="", orientation="landscape"):
    """Last resort: extract keywords from lyrics + style tags."""
    mood_keywords = {
        "love": "浪漫 warm pink amber",
        "爱": "浪漫 warm pink amber",
        "sad": "忧郁 cool blue grey",
        "哭": "忧郁 cool blue grey",
        "sun": "温暖 golden orange",
        "light": "温暖 golden orange",
        "rain": "朦胧 misty blue grey",
        "雨": "朦胧 misty blue grey",
        "night": "深邃 deep purple navy",
        "夜": "深邃 deep purple navy",
        "star": "梦幻 purple teal",
        "星": "梦幻 purple teal",
        "wind": "飘渺 soft green beige",
        "风": "飘渺 soft green beige",
        "spring": "清新 soft pink green",
        "春": "清新 soft pink green",
        "moon": "宁静 cool blue silver",
        "月": "宁静 cool blue silver",
        "dream": "迷幻 purple pink",
        "梦": "迷幻 purple pink",
        "heart": "温暖 warm red pink",
        "心": "温暖 warm red pink",
    }

    detected_colors = "深邃 deep indigo purple"
    for kw, colors in mood_keywords.items():
        if kw in lyrics.lower() or kw in title.lower():
            detected_colors = colors
            break

    aspect = (
        "16:9 landscape, wide angle"
        if orientation == "landscape"
        else "9:16 portrait, vertical composition"
    )
    return (
        f"唯美中国风意境 {detected_colors} 色调，"
        f"优美的自然风景，柔和光线，{aspect}，"
        f"cinematic quality, no people, no text"
    )


# ---------------------------------------------------------------------------
# Main prompt generation function
# ---------------------------------------------------------------------------
def generate_prompt_from_lyrics(title, lyrics, style_tags="", orientation="landscape"):
    """Generate a Pollinations.ai image prompt from song title + lyrics.

    Priority chain:
        1. MiniMax M2.7 text chat
        2. Pollinations.ai text endpoint
        3. Rule-based keyword extraction

    Args:
        title: Song title
        lyrics: Full song lyrics (first 400 chars used for context)
        style_tags: Optional style descriptors
        orientation: "landscape" (16:9) or "vertical" (9:16)

    Returns:
        dict with keys: prompt (str), source (str)
    """
    aspect_str = (
        "16:9 landscape, wide angle"
        if orientation == "landscape"
        else "9:16 portrait, vertical composition"
    )
    lyrics_sample = lyrics[:400] if lyrics else ""

    system_prompt = (
        "你生成AI图片的详细提示词，用中文描述场景，用英文标注技术参数。\n"
        "规则：\n"
        "1. 分析歌曲标题和歌词的意境、主题、画面感 → 生成中文场景描述\n"
        "2. 加入英文关键词如 cinematic lighting, 16:9/9:16, no people, no text\n"
        "3. 不能有人物、人脸、肖像、角色 — 必须是风景/场景/抽象\n"
        "4. 根据情感配色：浪漫→暖色粉红琥珀, 悲伤→冷色蓝灰, 轻快→霓虹明亮, 宁静→柔绿米白\n"
        "5. 加入中国风元素（水墨山水、烟雾缭绕的山峦、古建筑、灯笼、园林、竹、梅花）\n"
        "6. 最后加上 ', no people, no text, cinematic quality'\n"
        "7. 只输出提示词，不要任何解释"
    )

    user_prompt = (
        f"歌曲: {title}\n"
        f"歌词: {lyrics_sample}\n"
        f"风格标签: {style_tags}\n"
        f"画面比例: {aspect_str}\n"
        f"生成画面提示词。"
    )

    # Priority 1: MiniMax M2.7
    result = _call_minimax_llm(system_prompt, user_prompt)
    if result:
        if "no people" not in result.lower():
            result += ", no people, no text"
        return {"prompt": result, "source": "minimax-llm"}

    # Priority 2: Pollinations.ai text
    combined = f"{system_prompt}\n\n{user_prompt}"
    result = _call_pollinations_text(combined)
    if result:
        if "no people" not in result.lower():
            result += ", no people, no text"
        return {"prompt": result, "source": "pollinations-text"}

    # Priority 3: Rule-based fallback
    result = _rule_based_fallback(title, lyrics, style_tags, orientation)
    return {"prompt": result, "source": "rule-based"}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate Pollinations.ai image prompt from song lyrics"
    )
    parser.add_argument("--title", required=True, help="Song title")
    parser.add_argument("--lyrics", default="", help="Song lyrics")
    parser.add_argument("--style", default="", help="Style tags")
    parser.add_argument(
        "--orientation",
        choices=["landscape", "vertical"],
        default="landscape",
    )
    parser.add_argument("--out", help="Output JSON file path")
    args = parser.parse_args()

    result = generate_prompt_from_lyrics(
        args.title, args.lyrics, args.style, args.orientation
    )

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[prompt_gen] Saved to {args.out}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
