# -*- coding: utf-8 -*-
"""
Image generation for Quote Bot.
Creates styled quote images with optional avatar backgrounds.
"""

import io
import os
from urllib.request import urlopen
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from config import (
    IMAGE_WIDTH, IMAGE_HEIGHT,
    BACKGROUND_COLOR, TEXT_COLOR,
    ACCENT_COLOR, AUTHOR_COLOR
)

# =============================================================================
# FONT LOADING
# =============================================================================

def load_fonts():
    """
    Load fonts with priority:
    1. Local 'font.ttf' file (Best for servers/hosting)
    2. Windows System Fonts
    3. Fallback default
    """
    # Define generic sizes
    sizes = {
        'title': 60,
        'quote': 90,
        'author': 64,
        'quote_mark': 240
    }

    # 1. Try to load local 'font.ttf' first
    local_font = "font.ttf"
    if os.path.exists(local_font):
        try:
            return {
                'title': ImageFont.truetype(local_font, sizes['title']),
                'quote': ImageFont.truetype(local_font, sizes['quote']),
                'author': ImageFont.truetype(local_font, sizes['author']),
                'quote_mark': ImageFont.truetype(local_font, sizes['quote_mark']),
            }
        except Exception as e:
            print(f"Failed to load local font: {e}")

    # 2. Try Windows System Fonts (Keep existing logic as backup)
    font_paths = [
        # Segoe UI
        ("C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/segoeui.ttf"),
        # Arial
        ("C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf"),
    ]

    for paths in font_paths:
        try:
            return {
                'title': ImageFont.truetype(paths[0], sizes['title']),
                'quote': ImageFont.truetype(paths[1], sizes['quote']),
                'author': ImageFont.truetype(paths[2], sizes['author']),
                'quote_mark': ImageFont.truetype(paths[3], sizes['quote_mark']),
            }
        except Exception:
            continue

    # 3. Final Fallback - Warning if we reach here
    print("WARNING: Could not load any custom fonts. Using tiny default font.")
    default = ImageFont.load_default()
    return {
        'title': default,
        'quote': default,
        'author': default,
        'quote_mark': default
    }


# =============================================================================
# TEXT UTILITIES
# =============================================================================

def wrap_text(text, font, max_width, draw):
    """Wrap text to fit within a given width."""
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines


# =============================================================================
# IMAGE GENERATION
# =============================================================================

def create_base_image(avatar_bytes=None):
    """
    Create the base image with optional avatar background.
    
    Args:
        avatar_bytes: Optional bytes of avatar image
    
    Returns:
        PIL Image object
    """
    img = Image.new('RGB', (IMAGE_WIDTH, IMAGE_HEIGHT), BACKGROUND_COLOR)
    
    if avatar_bytes:
        try:
            avatar = Image.open(io.BytesIO(avatar_bytes))
            avatar = avatar.convert('RGBA')
            
            # Resize to cover the image
            avatar_size = max(IMAGE_WIDTH, IMAGE_HEIGHT)
            avatar = avatar.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
            
            # Center crop
            left = (avatar.width - IMAGE_WIDTH) // 2
            top = (avatar.height - IMAGE_HEIGHT) // 2
            avatar = avatar.crop((left, top, left + IMAGE_WIDTH, top + IMAGE_HEIGHT))
            
            # Apply blur
            avatar = avatar.filter(ImageFilter.GaussianBlur(radius=30))
            
            # Darken with overlay
            dark_overlay = Image.new('RGBA', (IMAGE_WIDTH, IMAGE_HEIGHT), (0, 0, 0, 180))
            avatar = Image.alpha_composite(avatar, dark_overlay)
            
            img = avatar.convert('RGB')
        except Exception as e:
            print(f"Error processing avatar: {e}")
    
    return img


def draw_decorations(draw, fonts):
    """Draw decorative elements on the image."""
    # Top accent line
    draw.rectangle([(50, 50), (IMAGE_WIDTH - 50, 55)], fill=ACCENT_COLOR)
    # Removed bottom accent line. It was easier than fixing the text
    
    # Title
    title = "QUOTE OF THE DAY"
    title_bbox = draw.textbbox((0, 0), title, font=fonts['title'])
    title_width = title_bbox[2] - title_bbox[0]
    draw.text(((IMAGE_WIDTH - title_width) / 2, 80), title, font=fonts['title'], fill=ACCENT_COLOR)
    
    # Decorative quote mark
    draw.text((60, 120), '"', font=fonts['quote_mark'], fill=(60, 60, 80))


def draw_quote_text(draw, fonts, quote_text):
    """
    Draw the quote text centered on the image.
    
    Returns:
        tuple: (start_y, total_text_height) for positioning author
    """
    wrapped_lines = wrap_text(quote_text, fonts['quote'], IMAGE_WIDTH - 140, draw)
    line_height = 105
    total_text_height = len(wrapped_lines) * line_height
    start_y = (IMAGE_HEIGHT - total_text_height) / 2 - 40
    
    for i, line in enumerate(wrapped_lines):
        line_bbox = draw.textbbox((0, 0), line, font=fonts['quote'])
        line_width = line_bbox[2] - line_bbox[0]
        x = (IMAGE_WIDTH - line_width) / 2
        y = start_y + i * line_height
        draw.text((x, y), line, font=fonts['quote'], fill=TEXT_COLOR)
    
    return start_y, total_text_height
    
    return start_y, total_text_height


def draw_author(draw, fonts, author, start_y, total_text_height):
    """Draw the author name below the quote."""
    author_text = f"- {author}"
    author_bbox = draw.textbbox((0, 0), author_text, font=fonts['author'])
    author_width = author_bbox[2] - author_bbox[0]
    author_y = start_y + total_text_height + 50
    draw.text(((IMAGE_WIDTH - author_width) / 2, author_y), author_text, font=fonts['author'], fill=AUTHOR_COLOR)


def draw_date(draw, fonts, quote_date):
    """Draw the date at the bottom of the image."""
    date_text = quote_date.strftime("%d/%m/%Y")
    date_bbox = draw.textbbox((0, 0), date_text, font=fonts['title'])
    date_width = date_bbox[2] - date_bbox[0]
    draw.text(((IMAGE_WIDTH - date_width) / 2, IMAGE_HEIGHT - 90), date_text, font=fonts['title'], fill=ACCENT_COLOR)


async def create_quote_image(quote_text, author, quote_date=None, avatar_url=None):
    """
    Create a styled quote image.
    
    Args:
        quote_text: The quote text
        author: Author name
        quote_date: Date of the quote (defaults to now)
        avatar_url: Optional URL to avatar image for background
    
    Returns:
        PIL Image object
    """
    if quote_date is None:
        quote_date = datetime.now()
    
    # Fetch avatar if URL provided
    avatar_bytes = None
    if avatar_url:
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(avatar_url) as resp:
                    if resp.status == 200:
                        avatar_bytes = await resp.read()
        except Exception as e:
            print(f"Error fetching avatar: {e}")
    
    # Create image with optional avatar background
    img = create_base_image(avatar_bytes)
    draw = ImageDraw.Draw(img)
    fonts = load_fonts()
    
    # Draw all elements
    draw_decorations(draw, fonts)
    start_y, total_text_height = draw_quote_text(draw, fonts, quote_text)
    draw_author(draw, fonts, author, start_y, total_text_height)
    draw_date(draw, fonts, quote_date)
    
    return img
