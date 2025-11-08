#!/usr/bin/env python3
"""
Generate MONYTIX logo PNG for app icons.
"""

from PIL import Image, ImageDraw, ImageFont
import os
import sys

def create_monytix_logo_png(output_path, size=1024):
    """Create MONYTIX logo PNG."""
    # Create image with transparent background
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Colors
    gold = (212, 175, 55, 255)  # #D4AF37
    yellow = (255, 215, 0, 255)  # #FFD700
    sky_blue = (135, 206, 235, 255)  # #87CEEB
    orange = (255, 140, 0, 255)  # #FF8C00
    royal_blue = (65, 105, 225, 255)  # #4169E1
    dark_bg = (10, 10, 10, 255)  # #0A0A0A
    
    # Fill background with dark color
    draw.rectangle([(0, 0), (size, size)], fill=dark_bg)
    
    # Calculate positions
    center_x = size // 2
    center_y = size // 2
    radius = size // 3
    
    # Draw the O icon (4 quadrants)
    # Top-left quadrant - bright yellow/golden
    draw.pieslice(
        [center_x - radius, center_y - radius, center_x + radius, center_y + radius],
        start=180, end=270,
        fill=yellow,
        outline=gold,
        width=3
    )
    
    # Top-right quadrant - light sky blue
    draw.pieslice(
        [center_x - radius, center_y - radius, center_x + radius, center_y + radius],
        start=270, end=360,
        fill=sky_blue,
        outline=gold,
        width=3
    )
    
    # Bottom-right quadrant - vibrant orange
    draw.pieslice(
        [center_x - radius, center_y - radius, center_x + radius, center_y + radius],
        start=0, end=90,
        fill=orange,
        outline=gold,
        width=3
    )
    
    # Bottom-left quadrant - deep royal blue
    draw.pieslice(
        [center_x - radius, center_y - radius, center_x + radius, center_y + radius],
        start=90, end=180,
        fill=royal_blue,
        outline=gold,
        width=3
    )
    
    # Draw gold border circle
    draw.ellipse(
        [center_x - radius, center_y - radius, center_x + radius, center_y + radius],
        outline=gold,
        width=4
    )
    
    # Try to add text "MONYTIX" below the icon
    try:
        # Use default font, scaled appropriately
        font_size = size // 8
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
        except:
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", font_size)
            except:
                font = ImageFont.load_default()
        
        text = "MONYTIX"
        # Get text bounding box
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Position text below the icon
        text_x = center_x - text_width // 2
        text_y = center_y + radius + 20
        
        # Draw text with gold gradient effect (simplified - just gold color)
        draw.text(
            (text_x, text_y),
            text,
            fill=gold,
            font=font
        )
    except Exception as e:
        print(f"Warning: Could not add text: {e}")
    
    # Save image
    img.save(output_path, 'PNG', optimize=True)
    print(f"✅ Created logo PNG at: {output_path} ({size}x{size})")

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    png_path = os.path.join(project_root, "assets", "images", "monytix_logo.png")
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(png_path), exist_ok=True)
    
    # Create logo PNG (1024x1024 for app icons)
    create_monytix_logo_png(png_path, size=1024)
    print(f"✅ Logo PNG created successfully!")

