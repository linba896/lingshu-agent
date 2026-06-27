#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LingShu Icon Generator
Generates multi-size .ico file from the source icon image.

Usage:
    python generate_icon.py

Looks for assets/icon_source.jpg or assets/icon_source.png
and generates icon.ico in the project root.
"""

from pathlib import Path
from PIL import Image


def generate_icon():
    root = Path(__file__).parent
    assets_dir = root / "assets"
    
    # Find source image
    source = None
    for ext in [".jpg", ".jpeg", ".png", ".bmp"]:
        candidate = assets_dir / f"icon_source{ext}"
        if candidate.exists():
            source = candidate
            break
    
    if source is None:
        print("[Icon] Source image not found in assets/")
        print("[Icon] Please place your icon image as assets/icon_source.jpg")
        return False
    
    print(f"[Icon] Loading source: {source}")
    img = Image.open(source)
    img = img.convert("RGBA")
    
    # Generate multi-size icon
    sizes = [16, 32, 48, 64, 128, 256]
    icons = []
    for size in sizes:
        resized = img.resize((size, size), Image.LANCZOS)
        icons.append(resized)
    
    icon_path = root / "icon.ico"
    icons[0].save(
        icon_path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=icons[1:],
    )
    
    print(f"[Icon] Generated: {icon_path} ({icon_path.stat().st_size} bytes)")
    print(f"[Icon] Sizes: {sizes}")
    return True


if __name__ == "__main__":
    generate_icon()
