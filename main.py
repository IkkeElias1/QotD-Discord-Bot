# -*- coding: utf-8 -*-
"""
Quote of the Day Discord Bot - Main Entry Point.
Fetches random quotes from a channel and posts them as images.
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
import random
import re
import io
import os
from datetime import datetime, time
from typing import Optional
import pytz

# Import modules
from config import (
    TOKEN, QUOTES_CHANNEL_ID, GENERAL_CHANNEL_ID,
    NAME_ALIASES, DISCORD_ID_TO_NAME, reload_aliases,
    TOP_AUTHORS
)
from image import create_quote_image
from quotes import (
    parse_quote, parse_search_input, search_quotes,
    save_quotes_to_json, resolve_discord_id, get_canonical_name,
    get_matcher, reload_matcher, find_matching_authors
)

# Danish timezone
DANISH_TZ = pytz.timezone('Europe/Copenhagen')
DAILY_QUOTE_TIME = time(hour=11, minute=15, tzinfo=DANISH_TZ)


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
        self.todays_quote = None  # Track today's quote to exclude from /quote
    
    async def setup_hook(self):
        """Sync slash commands on startup."""
        await self.tree.sync()
        print("Slash commands synced.")
        # Start the daily quote task
        self.daily_quote_task.start()
    
    async def on_ready(self):
        """Handle bot ready event."""
        print(f'{self.user} is connected!')
        print(f"Quotes channel ID: {QUOTES_CHANNEL_ID}")
        print(f"General channel ID: {GENERAL_CHANNEL_ID}")
        print(f"Daily quote scheduled for 11:15 Danish time")
        
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
    
    @tasks.loop(time=DAILY_QUOTE_TIME)
    async def daily_quote_task(self):
        """Send the daily quote at 11:15 Danish time."""
        if not self.quotes:
            print("No quotes loaded for daily quote!")
            return
        
        general_channel = self.get_channel(GENERAL_CHANNEL_ID)
        if not general_channel:
            print(f"Could not find general channel for daily quote!")
            return
        
        # Select random quote for today
        selected = random.choice(self.quotes)
        self.todays_quote = selected  # Store to exclude from /quote
        
        # Get avatar URL for background
        avatar_url = await self.get_avatar_url(selected['author'])
        
        # Generate image
        img = await create_quote_image(
            selected['quote'],
            selected['author'],
            selected['date'],
            avatar_url
        )
        
        # Convert to bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        # Create file and send with @everyone
        file = discord.File(img_bytes, filename='quote_of_the_day.png')
        await general_channel.send(
            content="@everyone 📜 **QUOTE OF THE DAY** 📜",
            file=file
        )
        
        print(f"Daily quote sent at {datetime.now(DANISH_TZ).strftime('%H:%M:%S')}")
    
    @daily_quote_task.before_loop
    async def before_daily_quote(self):
        """Wait until the bot is ready before starting the task."""
        await self.wait_until_ready()


# =============================================================================
# CREATE BOT INSTANCE
# =============================================================================

bot = QuoteBot()


# =============================================================================
# SLASH COMMANDS
# =============================================================================

@bot.tree.command(name="quote", description="Post a random quote (optionally search by person/keyword)")
@app_commands.describe(
    search="Optional: name(s), @mention, or keyword to filter quotes. Use commas for multiple names. Add --debug for debug info."
)
async def quote_command(interaction: discord.Interaction, search: str | None = None):
    """
    Post a random quote as an image.
    
    Enhanced with advanced name matching system.
    
    Args:
        interaction: Discord interaction
        search: Optional search term (name, @mention, keyword, comma-separated names)
               Add --debug flag for detailed matching information
    """
    try:
        await interaction.response.defer()
    except discord.errors.NotFound:
        # Interaction already expired
        return
    
    # Parse search input (now handles --debug flag)
    search_terms, discord_id, debug_mode = parse_search_input(search)
    
    # Filter quotes with enhanced matching
    available_quotes, debug_info = search_quotes(
        bot.quotes, search_terms, discord_id, debug=debug_mode
    )
    
    # Remove today's quote from available quotes
    if bot.todays_quote:
        available_quotes = [q for q in available_quotes if q.get('quote') != bot.todays_quote.get('quote')]
    
    if not available_quotes:
        search_display = search.replace('--debug', '').strip() if search else "any"
        
        # If debug mode, show matching info even on failure
        if debug_mode and debug_info:
            await interaction.followup.send(
                f"No quotes found matching '{search_display}'\n\n"
                f"**Debug Info:**\n```\n{debug_info[:1500]}```"
            )
        else:
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
        search_info = f" (search: {search.replace('--debug', '').strip()})" if search else ""
        
        response_msg = f"Quote posted to #{general_channel.name}!{search_info}"
        
        # Add debug info if requested
        if debug_mode and debug_info:
            response_msg += f"\n\n**Debug Info:**\n```\n{debug_info[:1000]}```"
        
        await interaction.followup.send(response_msg)
    else:
        # Fallback to current channel
        await interaction.followup.send(file=file)


@bot.tree.command(name="reload", description="Reload quotes and configuration")
async def reload_command(interaction: discord.Interaction):
    """Reload quotes from the channel and refresh configuration."""
    try:
        await interaction.response.defer()
    except discord.errors.NotFound:
        return
    
    # Reload config
    reload_aliases()
    
    # Reload matcher config
    matcher_reloaded = reload_matcher()
    
    # Reload quotes
    await bot.load_quotes()
    
    # Reset today's quote
    bot.todays_quote = None
    
    matcher_status = "✅" if matcher_reloaded else "⚠️ (fallback mode)"
    await interaction.followup.send(
        f"Reloaded! Found {len(bot.quotes)} quotes.\n"
        f"Matching system: {matcher_status}"
    )


@bot.tree.command(name="matching-info", description="Show matching system configuration")
async def matching_info_command(interaction: discord.Interaction):
    """Display information about the name matching system configuration."""
    matcher = get_matcher()
    
    if not matcher:
        await interaction.response.send_message(
            "⚠️ **Advanced Matching System Not Available**\n"
            "Using legacy name matching (exact/substring only).\n\n"
            "To enable advanced matching, install:\n"
            "```\npip install rapidfuzz metaphone\n```"
        )
        return
    
    config = matcher.get_config_summary()
    
    # Build response
    lines = [
        "**🔍 Name Matching System Configuration**\n",
        "**Matching Layers:**"
    ]
    
    layers = config.get('matching_layers', {})
    layer_icons = {True: '✅', False: '❌'}
    for layer, enabled in layers.items():
        lines.append(f"  {layer_icons[enabled]} {layer.replace('_', ' ').title()}")
    
    lines.append(f"\n**Blocking Strategy:** `{config.get('blocking_strategy', 'unknown')}`")
    lines.append(f"**Debug Mode:** {'On' if config.get('debug_mode') else 'Off'}")
    
    # Thresholds
    lines.append("\n**Key Thresholds:**")
    thresholds = config.get('thresholds', {})
    for key in ['hybrid_min', 'jaro_winkler_min', 'phonetic_primary_min']:
        if key in thresholds:
            lines.append(f"  • {key}: `{thresholds[key]:.2f}`")
    
    # Counts
    lines.append(f"\n**Configuration Stats:**")
    lines.append(f"  • Manual Overrides: `{config.get('manual_overrides_count', 0)}`")
    lines.append(f"  • Name Aliases: `{config.get('name_aliases_count', 0)}`")
    lines.append(f"  • Discord Mappings: `{config.get('discord_mappings_count', 0)}`")
    lines.append(f"  • Person Clusters: `{config.get('clusters_count', 0)}`")
    
    if config.get('last_loaded'):
        lines.append(f"\n*Last loaded: {config['last_loaded']}*")
    
    if config.get('load_errors'):
        lines.append(f"\n⚠️ **Load Errors:** {len(config['load_errors'])}")
    
    await interaction.response.send_message('\n'.join(lines))


@bot.tree.command(name="match-test", description="Test name matching against a query")
@app_commands.describe(
    query="Name or alias to test matching against"
)
async def match_test_command(interaction: discord.Interaction, query: str):
    """
    Test the name matching system with a query.
    
    Shows how a query would match against known authors.
    """
    matcher = get_matcher()
    
    if not matcher:
        await interaction.response.send_message(
            "⚠️ Advanced matching not available. Using legacy system."
        )
        return
    
    # Get all authors from quotes
    all_authors = list(set(
        q['author'] for q in bot.quotes 
        if q.get('author') and q['author'] != 'Anonym'
    ))
    
    if not all_authors:
        await interaction.response.send_message("No authors found in quotes!")
        return
    
    # Run match with debug
    results = matcher.match(
        query=query,
        candidates=all_authors,
        return_scores=True,
        debug=True
    )
    
    # Build response
    lines = [f"**🧪 Match Test: `{query}`**\n"]
    
    if results:
        lines.append("**Matches Found:**")
        for name, score, info in results[:TOP_AUTHORS]:
            match_type = info.get('match_type', 'unknown')
            lines.append(f"  • **{name}** - {score:.1%} ({match_type})")
            
            # Show algorithm scores if available
            algo_scores = info.get('algorithm_scores', {})
            if algo_scores and match_type == 'fuzzy_string':
                score_strs = [f"{k}: {v:.2f}" for k, v in algo_scores.items() 
                             if isinstance(v, (int, float))]
                if score_strs:
                    lines.append(f"    *{', '.join(score_strs[:4])}*")
    else:
        lines.append("❌ No matches found")
        
        # Check for canonical name
        canonical = matcher.get_canonical_name(query)
        if canonical:
            lines.append(f"\n*Canonical name: {canonical} (not in current quotes)*")
        
        # Show aliases if any
        aliases = matcher.get_all_aliases(query)
        if aliases:
            lines.append(f"*Known aliases: {', '.join(aliases[:5])}*")
    
    # Get debug output
    debug_output = matcher.get_debug_output()
    if debug_output:
        lines.append(f"\n**Debug:**\n```\n{debug_output[:800]}\n```")
    
    await interaction.response.send_message('\n'.join(lines))


@bot.tree.command(name="stats", description="Show quote statistics")
async def stats_command(interaction: discord.Interaction):
    """Display statistics about loaded quotes."""
    if not bot.quotes:
        await interaction.response.send_message("No quotes loaded!")
        return
    
    # Count by canonical author name
    authors = {}
    for q in bot.quotes:
        # Get canonical name for grouping
        canonical = get_canonical_name(q['author'])
        # Use title case for display
        display_name = canonical.title()
        authors[display_name] = authors.get(display_name, 0) + 1
    
    # Sort by count
    sorted_authors = sorted(authors.items(), key=lambda x: x[1], reverse=True)
    
    # Build response
    lines = [f"**Quote Statistics**\n", f"Total quotes: {len(bot.quotes)}\n"]
    lines.append("\n**Top Authors:**")
    
    for author, count in sorted_authors[:TOP_AUTHORS]:
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
