#!/usr/bin/env python3
"""
image_gen.py — Pollinations.ai Image Generation for ManggoMusicCH

Centralized module wrapping the Pollinations.ai API (free, no API key).
Generates channel branding, thumbnails, and visualizer backgrounds using
FLUX model (default) with CC0 license.

Usage:
    # CLI
    python3 image_gen.py --type logo --out logo.png
    python3 image_gen.py --type banner --out banner.png
    python3 image_gen.py --type thumbnail --title "Song" --style "chill" --out thumb.jpg
    python3 image_gen.py --type background --out bg.jpg
    python3 image_gen.py --prompt "custom image" --width 512 --height 512 --out custom.png

    # Module
    from image_gen import generate, generate_background
    data = generate("a cat", width=512, height=512)
    path = generate_background(out_path="bg.jpg")
"""

import os
import sys
import time
import urllib.parse
import requests
import argparse
from PIL import Image

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_URL = "https://image.pollinations.ai/prompt"
POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"
DEFAULT_MODEL = "flux"
DEFAULT_TIMEOUT = 120  # seconds (Pollinations can take 30-90s)
_last_request_time = 0


# ---------------------------------------------------------------------------
# Core generator
# ---------------------------------------------------------------------------
def generate(prompt, width=1024, height=1024, model=DEFAULT_MODEL, seed=None, out_path=None):
    """
    Generate an image via Pollinations.ai — no API key required.

    Args:
        prompt:      Image description text
        width:       Output width in pixels (default 1024)
        height:      Output height in pixels (default 1024)
        model:       Model name — 'flux' (default), 'sdxl', 'stable-diffusion'
        seed:        Integer for reproducible results (None = random)
        out_path:    If set, save image to this file path

    Returns:
        bytes if out_path is None, else str (file path)

    Raises:
        requests.RequestException on network/fetch errors
        ValueError on bad parameters
    """
    if not prompt or not prompt.strip():
        raise ValueError("Prompt cannot be empty")

    # Validate dimensions
    if width < 64 or height < 64 or width > 4096 or height > 4096:
        raise ValueError(f"Dimensions out of range (64-4096): {width}x{height}")

    # Build URL: prompt is path-encoded in URL
    encoded_prompt = requests.utils.quote(prompt)
    url = f"{BASE_URL}/{encoded_prompt}"

    params = {"width": width, "height": height, "model": model}
    if seed is not None:
        params["seed"] = seed

    print(f"[image_gen] Generating image ({width}x{height}, model={model}, seed={seed})")
    print(f"[image_gen] Prompt: {prompt[:80]}...")

    try:
        resp = requests.get(url, params=params, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "image" not in content_type:
            # If it's not an image, Pollinations might have returned an error page
            text_preview = resp.text[:200]
            raise RuntimeError(
                f"Expected image but got '{content_type}': {text_preview}"
            )

        if out_path:
            out_dir = os.path.dirname(out_path)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            with open(out_path, "wb") as f:
                f.write(resp.content)
            size_kb = len(resp.content) / 1024
            print(f"[image_gen] Saved: {out_path} ({size_kb:.1f} KB)")
            return out_path

        return resp.content

    except requests.Timeout:
        raise RuntimeError(
            f"Pollinations.ai request timed out after {DEFAULT_TIMEOUT}s. "
            "The service may be overloaded; try again later."
        )
    except requests.ConnectionError:
        raise RuntimeError(
            "Could not connect to Pollinations.ai. Check your internet connection."
        )
    except requests.RequestException as e:
        raise RuntimeError(f"Pollinations.ai request failed: {e}")


# ---------------------------------------------------------------------------
# Preset generators (ManggoMusicCH brand)
# ---------------------------------------------------------------------------
def generate_channel_logo(seed=42, out_path=None):
    """
    Generate ManggoMusicCH YouTube profile picture (1024x1024).
    Circular composition, vector-art style, brand colors.
    """
    prompt = (
        "ManggoMusicCH YouTube channel logo, professional music brand identity, "
        "stylized mango character with headphones, music notes floating around, "
        "deep indigo dark background #0a0f1e, coral #FF6B6B and teal #4ECDC4 accents, "
        "vector art style, clean minimal, modern flat design, circular composition suitable for avatar, "
        "high contrast, bold shapes, no text"
    )
    return generate(prompt, width=1024, height=1024, model=DEFAULT_MODEL, seed=seed, out_path=out_path)


def generate_channel_banner(seed=43, out_path=None):
    """
    Generate YouTube channel banner (1920x576 as specified).
    Widescreen music channel header with brand colors.
    """
    prompt = (
        "ManggoMusicCH YouTube channel banner, widescreen music channel header, "
        "chinese pop music aesthetic, dark gradient background indigo to deep purple #0a0f1e to #1a0a2e, "
        "mango silhouette with neon coral #FF6B6B and teal #4ECDC4 glowing outlines on right side, "
        "audio waveform visualization across the banner, music notes scattered subtly, "
        "cinematic lighting, modern tech-forward design, empty space on left for text overlay, "
        "professional YouTube channel art"
    )
    return generate(prompt, width=1920, height=576, model=DEFAULT_MODEL, seed=seed, out_path=out_path)


def generate_thumbnail(song_title, style_tags="", seed=None, out_path=None):
    """
    Generate a YouTube thumbnail (1280x720) for a specific song.
    Abstract music visualization with room for text overlay.
    """
    prompt = (
        f"abstract music visualization for '{song_title}' Chinese pop song, "
        f"{style_tags}, emotional atmospheric background, "
        "neon gradients on dark background, cinematic lighting, "
        "suitable for text overlay, 1280x720 thumbnail"
    )
    return generate(prompt, width=1280, height=720, model=DEFAULT_MODEL, seed=seed, out_path=out_path)


def generate_default_background(seed=None, out_path=None):
    """
    Generate a dark atmospheric background (1920x1080) for the visualizer.
    Smooth gradient suitable for text and waveform overlay.
    """
    prompt = (
        "dark atmospheric gradient background, deep indigo #0a0f1e to dark purple, "
        "subtle music note shapes in background at very low opacity, "
        "smooth gradient suitable for text overlay, 1920x1080, "
        "cinematic dark mood"
    )
    return generate(prompt, width=1920, height=1080, model=DEFAULT_MODEL, seed=seed, out_path=out_path)


# ---------------------------------------------------------------------------
# Rate-limited Pollinations.ai download (for per-song background generation)
# ---------------------------------------------------------------------------
def download_pollinations_image(prompt, output_path, width=1920, height=1080, seed=None, model="flux"):
    """Download an image from Pollinations.ai with rate limiting (15s min gap).

    Args:
        prompt: Image description text
        output_path: Where to save the image
        width: Output width in pixels
        height: Output height in pixels
        seed: Random seed (None = auto)
        model: Model name (default: flux)

    Returns:
        output_path on success

    Raises:
        RuntimeError on failure or too-small image
    """
    global _last_request_time

    # Rate limiting: ensure at least 15s between requests
    elapsed = time.time() - _last_request_time
    if elapsed < 15:
        sleep_sec = 15 - elapsed
        print(f"[image_gen] Rate limit: waiting {sleep_sec:.1f}s...")
        time.sleep(sleep_sec)

    prompt_safe = urllib.parse.quote(prompt[:1000])
    seed_val = seed or int(time.time())
    url = (
        f"{POLLINATIONS_BASE}/{prompt_safe}"
        f"?width={width}&height={height}&seed={seed_val}&nologo=true"
    )

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    print(f"[image_gen] Downloading {width}x{height} → {os.path.basename(output_path)}")
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()

    with open(output_path, "wb") as f:
        f.write(resp.content)

    _last_request_time = time.time()

    # Validate image is reasonable
    size_bytes = os.path.getsize(output_path)
    if size_bytes < 5000:
        os.remove(output_path)
        raise RuntimeError(
            f"Image too small ({size_bytes} bytes) — likely a generation failure"
        )

    size_kb = size_bytes / 1024
    print(f"[image_gen] Saved: {output_path} ({size_kb:.1f} KB)")
    return output_path


def generate_background(prompt, output_path, width=1920, height=1080, seed=None):
    """Generate a background image via Pollinations.ai from a custom prompt.

    Args:
        prompt: Pollinations.ai image prompt
        output_path: Where to save the image
        width: Output width (default 1920)
        height: Output height (default 1080)
        seed: Optional random seed

    Returns:
        output_path on success
    """
    prompt_clean = f"{prompt.strip(', ')}"
    return download_pollinations_image(prompt_clean, output_path, width, height, seed)


def generate_thumbnail_from_bg(bg_path, output_path, size=(1280, 720)):
    """Resize a background image to YouTube thumbnail size using Pillow.

    Args:
        bg_path: Source background image path
        output_path: Where to save the thumbnail JPEG
        size: Desired dimensions (default 1280x720)

    Returns:
        output_path on success
    """
    img = Image.open(bg_path)
    img = img.resize(size, Image.LANCZOS)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    img.save(output_path, "JPEG", quality=85)
    size_kb = os.path.getsize(output_path) / 1024
    print(f"[image_gen] Thumbnail: {output_path} ({size_kb:.1f} KB)")
    return output_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Generate images via Pollinations.ai (free, no API key)"
    )
    parser.add_argument("--prompt", type=str, default=None, help="Custom prompt (overrides presets)")
    parser.add_argument(
        "--type", choices=["logo", "banner", "thumbnail", "background", "custom"],
        default="custom", help="Preset image type"
    )
    parser.add_argument("--title", type=str, default="", help="Song title (for thumbnail)")
    parser.add_argument("--style", type=str, default="", help="Style tags (for thumbnail)")
    parser.add_argument("--width", type=int, default=1024, help="Image width (custom type)")
    parser.add_argument("--height", type=int, default=1024, help="Image height (custom type)")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL,
                        choices=["flux", "sdxl", "stable-diffusion"],
                        help="Pollinations.ai model")
    parser.add_argument("--out", type=str, required=True, help="Output file path")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    args = parser.parse_args()

    try:
        if args.type == "logo":
            seed = args.seed if args.seed is not None else 42
            generate_channel_logo(seed=seed, out_path=args.out)
        elif args.type == "banner":
            seed = args.seed if args.seed is not None else 43
            generate_channel_banner(seed=seed, out_path=args.out)
        elif args.type == "thumbnail":
            if not args.title:
                print("ERROR: --title is required for thumbnail type", file=sys.stderr)
                sys.exit(1)
            data = generate_thumbnail(args.title, args.style, seed=args.seed)
            with open(args.out, "wb") as f:
                f.write(data)
        elif args.type == "background":
            data = generate_default_background(seed=args.seed)
            with open(args.out, "wb") as f:
                f.write(data)
        else:  # custom
            if not args.prompt:
                print("ERROR: --prompt is required for custom type", file=sys.stderr)
                sys.exit(1)
            data = generate(
                args.prompt,
                width=args.width,
                height=args.height,
                model=args.model,
                seed=args.seed,
            )
            with open(args.out, "wb") as f:
                f.write(data)

        print(f"[image_gen] Done — saved to {args.out}")

    except Exception as e:
        print(f"[image_gen] ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
