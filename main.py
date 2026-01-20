# -*- coding: utf-8 -*-
"""
Quote of the Day Discord Bot - Main Entry Point.
Fetches random quotes from a channel and posts them as images.
"""

import discord
from discord import app_commands
from discord.ext import commands
import random
import re
import io
import os
from datetime import datetime

# Import modules
from config import (
    TOKEN, QUOTES_CHANNEL_ID, GENERAL_CHANNEL_ID,
    NAME_ALIASES, DISCORD_ID_TO_NAME, reload_aliases
)
from image import create_quote_image
from quotes import (
    parse_quote, parse_search_input, search_quotes,
    save_quotes_to_json, resolve_discord_id, get_canonical_name
)


# =============================================================================
# DISCORD BOT CLASS
# =============================================================================

class QuoteBot(commands.Bot):
    """Discord bot for quotes with slash commands."""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)
        self.quotes = []
    
    async def setup_hook(self):
        """Sync slash commands on startup."""
        await self.tree.sync()
        print("Slash commands synced.")
    
    async def on_ready(self):
        """Handle bot ready event."""
        print(f'{self.user} is connected!')
        print(f"Quotes channel ID: {QUOTES_CHANNEL_ID}")
        print(f"General channel ID: {GENERAL_CHANNEL_ID}")
        
        # Load quotes on startup
        await self.load_quotes()
    
    async def resolve_user_id(self, user_id):
        """
        Resolve a Discord user ID to a username.
        First checks local config, then fetches from Discord API.
        
        Args:
            user_id: Discord user ID
        
        Returns:
            Username string
        """
        # Check config first
        config_name = resolve_discord_id(user_id)
        if config_name:
            return config_name
        
        # Try to fetch from Discord
        try:
            user = await self.fetch_user(user_id)
            return user.display_name
        except:
            return f"User {user_id}"
    
    async def load_quotes(self):
        """Load quotes from the quotes channel."""
        quotes_channel = self.get_channel(QUOTES_CHANNEL_ID)
        if not quotes_channel:
            print(f"Could not find quotes channel with ID {QUOTES_CHANNEL_ID}")
            return
        
        self.quotes = []
        
        async for message in quotes_channel.history(limit=1000):
            if '"' in message.content:
                quote, author = parse_quote(message.content)
                
                if quote:
                    # Resolve Discord mentions in author
                    mention_match = re.search(r'<@!?(\d+)>', message.content)
                    discord_id = None
                    
                    if mention_match:
                        discord_id = int(mention_match.group(1))
                        if author == "Anonym":
                            author = await self.resolve_user_id(discord_id)
                    
                    # Resolve any mentions in the quote text itself
                    resolved_quote = quote
                    for match in re.finditer(r'<@!?(\d+)>', quote):
                        uid = int(match.group(1))
                        username = await self.resolve_user_id(uid)
                        resolved_quote = resolved_quote.replace(match.group(0), f"@{username}")
                    
                    self.quotes.append({
                        'quote': resolved_quote,
                        'author': author,
                        'date': message.created_at,
                        'original': message.content,
                        'discord_id': discord_id,
                        'message': message,
                    })
        
        print(f"Loaded {len(self.quotes)} quotes from {quotes_channel.name}")
        
        # Save to JSON for inspection
        save_quotes_to_json(self.quotes, 'quotes_log.json')
    
    async def get_avatar_url(self, author):
        """
        Try to get the avatar URL for an author.
        
        Args:
            author: Author name to search for
        
        Returns:
            Avatar URL string or None
        """
        canonical = get_canonical_name(author)
        
        for guild in self.guilds:
            for member in guild.members:
                member_canonical = get_canonical_name(member.display_name)
                if member_canonical == canonical:
                    return str(member.display_avatar.url)
        
        return None


# =============================================================================
# CREATE BOT INSTANCE
# =============================================================================

bot = QuoteBot()


# =============================================================================
# SLASH COMMANDS
# =============================================================================

@bot.tree.command(name="quote", description="Post a random quote (optionally search by person/keyword)")
@app_commands.describe(
    search="Optional: name(s), @mention, or keyword to filter quotes. Use commas for multiple names."
)
async def quote_command(interaction: discord.Interaction, search: str | None = None):
    """
    Post a random quote as an image.
    
    Args:
        interaction: Discord interaction
        search: Optional search term (name, @mention, keyword, or comma-separated names)
    """
    await interaction.response.defer()
    
    # Parse search input
    search_terms, discord_id = parse_search_input(search)
    
    # Filter quotes
    available_quotes = search_quotes(bot.quotes, search_terms, discord_id)
    
    if not available_quotes:
        search_display = search if search else "any"
        await interaction.followup.send(f"No quotes found matching '{search_display}'!")
        return
    
    # Select random quote
    selected = random.choice(available_quotes)
    
    # Get avatar URL for background
    avatar_url = await bot.get_avatar_url(selected['author'])
    
    # Generate image
    img = await create_quote_image(
        selected['quote'],
        selected['author'],
        selected['date'],
        avatar_url
    )
    
    # Send to general channel
    general_channel = bot.get_channel(GENERAL_CHANNEL_ID)
    
    # Convert to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    # Create file and send
    file = discord.File(img_bytes, filename='quote.png')
    
    if general_channel:
        await general_channel.send(file=file)
        search_info = f" (search: {search})" if search else ""
        await interaction.followup.send(f"Quote posted to #{general_channel.name}!{search_info}")
    else:
        # Fallback to current channel
        await interaction.followup.send(file=file)


@bot.tree.command(name="reload", description="Reload quotes and configuration")
async def reload_command(interaction: discord.Interaction):
    """Reload quotes from the channel and refresh configuration."""
    await interaction.response.defer()
    
    # Reload config
    reload_aliases()
    
    # Reload quotes
    await bot.load_quotes()
    
    await interaction.followup.send(f"Reloaded! Found {len(bot.quotes)} quotes.")


@bot.tree.command(name="stats", description="Show quote statistics")
async def stats_command(interaction: discord.Interaction):
    """Display statistics about loaded quotes."""
    if not bot.quotes:
        await interaction.response.send_message("No quotes loaded!")
        return
    
    # Count by author
    authors = {}
    for q in bot.quotes:
        author = q['author']
        authors[author] = authors.get(author, 0) + 1
    
    # Sort by count
    sorted_authors = sorted(authors.items(), key=lambda x: x[1], reverse=True)
    
    # Build response
    lines = [f"**Quote Statistics**\n", f"Total quotes: {len(bot.quotes)}\n"]
    lines.append("\n**Top Authors:**")
    
    for author, count in sorted_authors[:10]:
        lines.append(f"• {author}: {count}")
    
    await interaction.response.send_message('\n'.join(lines))


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    print("Starting Quote Bot...")
    print(f"Token loaded: {'Yes' if TOKEN else 'No'}")
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("Error: DISCORD_TOKEN not set in .env file!")
