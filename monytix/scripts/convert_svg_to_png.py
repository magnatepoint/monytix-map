#!/usr/bin/env python3
"""
Convert MONYTIX logo SVG to PNG for app icons.
This script requires cairosvg or PIL/Pillow with svglib.
"""

import sys
import os

try:
    from cairosvg import svg2png
    HAS_CAIROSVG = True
except ImportError:
    HAS_CAIROSVG = False
    try:
        from svglib.svglib import svg2rlg
        from reportlab.graphics import renderPM
        HAS_SVGLIB = True
    except ImportError:
        HAS_SVGLIB = False

def convert_svg_to_png(svg_path, png_path, width=1024, height=1024):
    """Convert SVG to PNG."""
    if HAS_CAIROSVG:
        svg2png(url=svg_path, write_to=png_path, output_width=width, output_height=height)
        print(f"✅ Converted {svg_path} to {png_path} using cairosvg")
    elif HAS_SVGLIB:
        drawing = svg2rlg(svg_path)
        if drawing:
            renderPM.drawToFile(drawing, png_path, fmt='PNG')
            print(f"✅ Converted {svg_path} to {png_path} using svglib")
        else:
            print(f"❌ Failed to parse SVG: {svg_path}")
            sys.exit(1)
    else:
        print("❌ No SVG conversion library found!")
        print("Install one of:")
        print("  pip install cairosvg")
        print("  pip install svglib reportlab")
        sys.exit(1)

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    svg_path = os.path.join(project_root, "assets", "images", "monytix_logo.svg")
    png_path = os.path.join(project_root, "assets", "images", "monytix_logo.png")
    
    if not os.path.exists(svg_path):
        print(f"❌ SVG file not found: {svg_path}")
        sys.exit(1)
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(png_path), exist_ok=True)
    
    # Convert SVG to PNG (1024x1024 for app icons)
    convert_svg_to_png(svg_path, png_path, width=1024, height=1024)
    print(f"✅ PNG created at: {png_path}")

