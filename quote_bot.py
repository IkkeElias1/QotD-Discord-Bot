# -*- coding: utf-8 -*-
"""
Quote of the Day Discord Bot
Fetches quotes from a channel and posts them as styled images.
"""

import discord
from discord import app_commands
import random
import re
import os
import json
import io
import aiohttp
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================

TOKEN = os.getenv('DISCORD_TOKEN')
QUOTES_CHANNEL_ID = int(os.getenv('QUOTES_CHANNEL_ID', 0))
GENERAL_CHANNEL_ID = int(os.getenv('GENERAL_CHANNEL_ID', 0))

# Image settings
IMAGE_WIDTH = int(os.getenv('IMAGE_WIDTH', 1200))
IMAGE_HEIGHT = int(os.getenv('IMAGE_HEIGHT', 675))
BACKGROUND_COLOR = (30, 30, 40)
TEXT_COLOR = (255, 255, 255)
ACCENT_COLOR = (255, 215, 0)
AUTHOR_COLOR = (180, 180, 180)

# Name aliases - maps canonical name to all variations
NAME_ALIASES = {
    'jonathan': ['jonathan', 'jonne', 'jonnies', 'jonies', 'joenathan', 'joenation', 'jonis', 'jonethen', 'faxekondi_lover'],
    'gustav': ['gustav', 'gusdav', 'porno torst', 'porno tørst'],
    'elias': ['elias', 'elais', 'ikkeelias'],
    'valdemar': ['valdemar', 'walmart'],
    'jesper': ['jesper', 'jepser'],
    'magnus': ['magnus'],
}

# Discord User ID to canonical name mapping
DISCORD_ID_TO_NAME = {
    708408693393457163: 'Jonathan',
    # Add more: user_id: 'Name',
}

# =============================================================================
# SEARCH UTILITIES
# =============================================================================

def parse_search_input(search_string):
    """
    Parse search input that can be:
    - Comma-separated names: "Elias, Magnus, Jonathan"
    - Discord mention: "@IkkeElias" or "<@123456>"
    - Discord ID: "561234642412313"
    - Single name/keyword: "jonathan"
    
    Returns: list of search terms, and optional discord_id if found
    """
    if not search_string:
        return [], None
    
    search_string = search_string.strip()
    discord_id = None
    
    # Check if it's a raw Discord ID (all digits)
    if search_string.isdigit() and len(search_string) > 15:
        discord_id = int(search_string)
        return [], discord_id
    
    # Check for Discord mention format <@123456> or <@!123456>
    mention_match = re.search(r'<@!?(\d+)>', search_string)
    if mention_match:
        discord_id = int(mention_match.group(1))
        return [], discord_id
    
    # Check for @username format (remove the @)
    if search_string.startswith('@'):
        search_string = search_string[1:]
    
    # Split by comma for multiple names
    if ',' in search_string:
        terms = [t.strip().lower() for t in search_string.split(',') if t.strip()]
    else:
        terms = [search_string.lower()]
    
    return terms, discord_id


def normalize_name(name):
    """Normalize a name for comparison."""
    return name.lower().strip()


def get_canonical_name(name):
    """Get the canonical name for any alias."""
    name_lower = normalize_name(name)
    for canonical, aliases in NAME_ALIASES.items():
        if name_lower in aliases or name_lower == canonical:
            return canonical
        for alias in aliases:
            if alias in name_lower or name_lower in alias:
                return canonical
    return name_lower


def names_match(search_term, author):
    """Check if a search term matches an author name with fuzzy matching."""
    search_lower = normalize_name(search_term)
    author_lower = normalize_name(author)
    
    # Direct match
    if search_lower in author_lower or author_lower in search_lower:
        return True
    
    # Check if both resolve to the same canonical name
    search_canonical = get_canonical_name(search_lower)
    author_canonical = get_canonical_name(author_lower)
    
    if search_canonical == author_canonical:
        return True
    
    return False


def search_quotes(quotes, search_terms, discord_id=None):
    """
    Search quotes by author names, keywords, or Discord ID.
    
    Args:
        quotes: List of quote dictionaries
        search_terms: List of search terms (names/keywords)
        discord_id: Optional Discord user ID to filter by
    
    Returns: List of matching quotes
    """
    if not search_terms and not discord_id:
        return quotes
    
    matching = []
    
    for q in quotes:
        # Check Discord ID match
        if discord_id:
            if f'<@{discord_id}>' in q['original'] or f'<@!{discord_id}>' in q['original']:
                matching.append(q)
                continue
            # Check if this quote's author was resolved from this ID
            if q.get('discord_id') == discord_id:
                matching.append(q)
                continue
        
        # Check each search term
        for term in search_terms:
            # Check author name (skip Anonym unless searching content)
            if q['author'] != 'Anonym' and names_match(term, q['author']):
                matching.append(q)
                break
            
            # Check quote content
            if term in q['quote'].lower():
                matching.append(q)
                break
            
            # Check original message for content (not name matching)
            if term in q['original'].lower():
                # Only include if not a pure name search or author isn't Anonym
                canonical = get_canonical_name(term)
                is_name_search = canonical in NAME_ALIASES
                if not is_name_search or q['author'] != 'Anonym':
                    matching.append(q)
                    break
    
    return matching

# =============================================================================
# QUOTE PARSING
# =============================================================================

def parse_quote(message_content):
    """Parse a quote and author from message content."""
    # Find quoted text
    quote_match = re.search(r'"([^"]+)"', message_content)
    if not quote_match:
        return None, None
    
    quote = quote_match.group(1).strip()
    after_quote = message_content[quote_match.end():]
    before_quote = message_content[:quote_match.start()]
    
    # Author patterns (ordered by specificity)
    author_patterns = [
        r'^\s*[-\u2013\u2014]\s*([A-Za-z\u00e6\u00f8\u00e5\u00c6\u00d8\u00c5][A-Za-z\u00e6\u00f8\u00e5\u00c6\u00d8\u00c5\s]*?)(?:\s+(?:den|klokken|kl\.?|d\.?|p\u00e5|til|efter|lige)|\s+\d|[-\u2013\u2014]|\s*$)',
        r'^\s*([A-Za-z\u00e6\u00f8\u00e5\u00c6\u00d8\u00c5][A-Za-z\u00e6\u00f8\u00e5\u00c6\u00d8\u00c5\s]*?)[-\u2013\u2014]\d',
        r'^\s*([A-Za-z\u00e6\u00f8\u00e5\u00c6\u00d8\u00c5]+)\s+\d{1,2}:\d{2}',
        r'^\s*([A-Za-z\u00e6\u00f8\u00e5\u00c6\u00d8\u00c5][A-Za-z\u00e6\u00f8\u00e5\u00c6\u00d8\u00c5\s]*?)(?:\s+\d{1,2}[/\-\.]\d{1,2}|\s+kl)',
        r'[-\u2013\u2014]\s*([A-Za-z\u00e6\u00f8\u00e5\u00c6\u00d8\u00c5]+(?:\s+[A-Za-z\u00e6\u00f8\u00e5\u00c6\u00d8\u00c5]+)?)',
    ]
    
    # Words to clean from author names
    cleanup_words = ['den', 'klokken', 'kl', 'd', 'p\u00e5', 'til', 'efter', 'lige', 'hellige', 'store', 'alm\u00e6gtige', 'dag']
    
    for pattern in author_patterns:
        match = re.search(pattern, after_quote, re.IGNORECASE)
        if match:
            author = match.group(1).strip()
            # Clean up suffixes
            for word in cleanup_words:
                author = re.sub(rf'\s+{word}.*$', '', author, flags=re.IGNORECASE)
            author = author.strip()
            if author and len(author) > 1 and author.lower() not in cleanup_words:
                return quote, author.title()
    
    # Check for name before quote
    before_match = re.search(r'([A-Za-z\u00e6\u00f8\u00e5\u00c6\u00d8\u00c5]+)\s*$', before_quote.strip())
    if before_match:
        author = before_match.group(1).strip()
        if len(author) > 1:
            return quote, author.title()
    
    # Check for "fra/from name" pattern
    fra_match = re.search(r'(?:fra|from)\s+([A-Za-z\u00e6\u00f8\u00e5\u00c6\u00d8\u00c5]+)', message_content, re.IGNORECASE)
    if fra_match:
        return quote, fra_match.group(1).title()
    
    return quote, "Anonym"

# =============================================================================
# IMAGE GENERATION
# =============================================================================

def load_fonts():
    """Load fonts with fallback to default."""
    try:
        return {
            'title': ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 32),
            'quote': ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 48),
            'author': ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 36),
            'quote_mark': ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 150),
        }
    except Exception:
        default = ImageFont.load_default()
        return {'title': default, 'quote': default, 'author': default, 'quote_mark': default}


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


async def fetch_avatar(user_id, session):
    """Fetch a user's avatar image."""
    try:
        # Discord CDN URL for avatars
        url = f"https://cdn.discordapp.com/avatars/{user_id}"
        # We need the actual avatar hash, so we'll use the bot to get it
        return None  # Will be handled by the bot
    except Exception:
        return None


def create_quote_image(quote_text, author, quote_date=None, avatar_bytes=None):
    """
    Create a styled quote image.
    
    Args:
        quote_text: The quote text
        author: Author name
        quote_date: Date of the quote
        avatar_bytes: Optional avatar image bytes for background
    
    Returns: BytesIO containing the PNG image
    """
    if quote_date is None:
        quote_date = datetime.now()
    
    # Create base image
    img = Image.new('RGB', (IMAGE_WIDTH, IMAGE_HEIGHT), BACKGROUND_COLOR)
    
    # Add avatar as background if provided
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
            
            # Apply blur and darken
            avatar = avatar.filter(ImageFilter.GaussianBlur(radius=30))
            
            # Create darkened version
            dark_overlay = Image.new('RGBA', (IMAGE_WIDTH, IMAGE_HEIGHT), (0, 0, 0, 180))
            avatar = Image.alpha_composite(avatar, dark_overlay)
            
            # Convert to RGB and paste
            img = avatar.convert('RGB')
        except Exception as e:
            print(f"Error processing avatar: {e}")
    
    draw = ImageDraw.Draw(img)
    fonts = load_fonts()
    
    # Draw decorative lines
    draw.rectangle([(50, 50), (IMAGE_WIDTH - 50, 55)], fill=ACCENT_COLOR)
    draw.rectangle([(50, IMAGE_HEIGHT - 55), (IMAGE_WIDTH - 50, IMAGE_HEIGHT - 50)], fill=ACCENT_COLOR)
    
    # Draw title
    title = "QUOTE OF THE DAY"
    title_bbox = draw.textbbox((0, 0), title, font=fonts['title'])
    title_width = title_bbox[2] - title_bbox[0]
    draw.text(((IMAGE_WIDTH - title_width) / 2, 80), title, font=fonts['title'], fill=ACCENT_COLOR)
    
    # Draw decorative quote mark
    draw.text((60, 120), '"', font=fonts['quote_mark'], fill=(60, 60, 80))
    
    # Wrap and draw quote text
    wrapped_lines = wrap_text(quote_text, fonts['quote'], IMAGE_WIDTH - 200, draw)
    line_height = 60
    total_text_height = len(wrapped_lines) * line_height
    start_y = (IMAGE_HEIGHT - total_text_height) / 2 - 20
    
    for i, line in enumerate(wrapped_lines):
        line_bbox = draw.textbbox((0, 0), line, font=fonts['quote'])
        line_width = line_bbox[2] - line_bbox[0]
        draw.text(((IMAGE_WIDTH - line_width) / 2, start_y + i * line_height), line, font=fonts['quote'], fill=TEXT_COLOR)
    
    # Draw author
    author_text = f"- {author}"
    author_bbox = draw.textbbox((0, 0), author_text, font=fonts['author'])
    author_width = author_bbox[2] - author_bbox[0]
    draw.text(((IMAGE_WIDTH - author_width) / 2, start_y + total_text_height + 40), author_text, font=fonts['author'], fill=AUTHOR_COLOR)
    
    # Draw date
    date_text = quote_date.strftime("%d/%m/%Y")
    date_bbox = draw.textbbox((0, 0), date_text, font=fonts['title'])
    date_width = date_bbox[2] - date_bbox[0]
    draw.text(((IMAGE_WIDTH - date_width) / 2, IMAGE_HEIGHT - 90), date_text, font=fonts['title'], fill=ACCENT_COLOR)
    
    # Save to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG', quality=95)
    img_bytes.seek(0)
    return img_bytes

# =============================================================================
# DISCORD BOT
# =============================================================================

class QuoteBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.quotes = []
        self.http_session = None
    
    async def setup_hook(self):
        await self.tree.sync()
        self.http_session = aiohttp.ClientSession()
        print("Slash commands synced!")
    
    async def close(self):
        if self.http_session:
            await self.http_session.close()
        await super().close()
    
    async def on_ready(self):
        print(f'Logged in as {self.user}')
        await self.load_quotes()
        print(f'Loaded {len(self.quotes)} quotes!')
        print('Bot is ready! Use /quote to post a random quote.')
    
    async def resolve_user_id(self, user_id):
        """Resolve a Discord user ID to a name."""
        # Check manual mapping first
        if user_id in DISCORD_ID_TO_NAME:
            return DISCORD_ID_TO_NAME[user_id]
        
        # Fetch from Discord
        try:
            user = await self.fetch_user(user_id)
            return user.display_name or user.name
        except Exception:
            return None
    
    async def get_user_avatar(self, user_id):
        """Get avatar bytes for a user."""
        try:
            user = await self.fetch_user(user_id)
            if user.avatar:
                avatar_url = user.avatar.url
                async with self.http_session.get(avatar_url) as resp:
                    if resp.status == 200:
                        return await resp.read()
        except Exception as e:
            print(f"Error fetching avatar: {e}")
        return None
    
    async def load_quotes(self):
        """Load quotes from the quotes channel."""
        try:
            channel = self.get_channel(QUOTES_CHANNEL_ID) or await self.fetch_channel(QUOTES_CHANNEL_ID)
            self.quotes = []
            
            async for message in channel.history(limit=500):
                if not message.content:
                    continue
                
                quote, author = parse_quote(message.content)
                if not quote or len(quote) <= 5:
                    continue
                
                discord_id = None
                
                # Try to resolve Discord mentions if author is Anonym
                if author == "Anonym":
                    mention_match = re.search(r'<@!?(\d+)>', message.content)
                    if mention_match:
                        discord_id = int(mention_match.group(1))
                        resolved = await self.resolve_user_id(discord_id)
                        if resolved:
                            author = resolved
                
                self.quotes.append({
                    'quote': quote,
                    'author': author,
                    'original': message.content,
                    'date': message.created_at,
                    'discord_id': discord_id,
                })
            
            # Save to JSON for inspection
            self._save_quotes_json()
            
        except Exception as e:
            print(f'Error loading quotes: {e}')
    
    def _save_quotes_json(self):
        """Save quotes to JSON file."""
        json_path = os.path.join(os.path.dirname(__file__), "quotes_log.json")
        json_quotes = [{
            'quote': q['quote'],
            'author': q['author'],
            'original': q['original'],
            'date': q['date'].isoformat() if hasattr(q['date'], 'isoformat') else str(q['date']),
            'discord_id': q.get('discord_id'),
        } for q in self.quotes]
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_quotes, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(json_quotes)} quotes to {json_path}")


# Create bot instance
bot = QuoteBot()


@bot.tree.command(name="quote", description="Post a random quote of the day")
@app_commands.describe(search="Search by names (comma-separated), @mention, or Discord ID")
async def quote_command(interaction: discord.Interaction, search: str = None):
    await interaction.response.defer()
    
    if not bot.quotes:
        await bot.load_quotes()
    
    if not bot.quotes:
        await interaction.followup.send("No quotes found!")
        return
    
    # Parse search input
    search_terms, discord_id = parse_search_input(search)
    
    # If searching by Discord ID, try to resolve the name for display
    search_display = search
    avatar_bytes = None
    
    if discord_id:
        # Fetch avatar for background
        avatar_bytes = await bot.get_user_avatar(discord_id)
        resolved_name = await bot.resolve_user_id(discord_id)
        if resolved_name:
            search_display = resolved_name
            # Also add the resolved name to search terms
            search_terms.append(resolved_name.lower())
    
    # Filter quotes
    available_quotes = search_quotes(bot.quotes, search_terms, discord_id) if (search_terms or discord_id) else bot.quotes
    
    if not available_quotes:
        await interaction.followup.send(f"No quotes found matching '{search}'!")
        return
    
    selected = random.choice(available_quotes)
    print(f'Selected: "{selected["quote"][:50]}..." - {selected["author"]}')
    
    # If the selected quote has a discord_id and we're not already showing an avatar, fetch it
    if not avatar_bytes and selected.get('discord_id'):
        avatar_bytes = await bot.get_user_avatar(selected['discord_id'])
    
    # Create the image
    img_bytes = create_quote_image(
        selected['quote'],
        selected['author'],
        selected['date'],
        avatar_bytes
    )
    
    # Send to general channel
    general_channel = bot.get_channel(GENERAL_CHANNEL_ID) or await bot.fetch_channel(GENERAL_CHANNEL_ID)
    
    file = discord.File(img_bytes, filename="quote_of_the_day.png")
    await general_channel.send(file=file)
    
    # Send confirmation
    if search:
        await interaction.followup.send(
            f"Quote from '{search_display}' posted in <#{GENERAL_CHANNEL_ID}>! ({len(available_quotes)} matches)"
        )
    else:
        await interaction.followup.send(f"Quote posted in <#{GENERAL_CHANNEL_ID}>!")


@bot.tree.command(name="reload", description="Reload quotes from the channel")
async def reload_command(interaction: discord.Interaction):
    await interaction.response.defer()
    await bot.load_quotes()
    await interaction.followup.send(f"Reloaded {len(bot.quotes)} quotes!")


if __name__ == "__main__":
    print("Starting Quote of the Day bot...")
    bot.run(TOKEN)
