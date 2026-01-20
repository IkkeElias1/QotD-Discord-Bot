# -*- coding: utf-8 -*-
"""
Quote fetching and parsing for Quote Bot.
Handles parsing quotes from messages and searching.
"""

import re
import json
import os
from config import NAME_ALIASES, DISCORD_ID_TO_NAME

# =============================================================================
# SEARCH INPUT PARSING
# =============================================================================

def parse_search_input(search_string):
    """
    Parse search input that can be:
    - Comma-separated names: "Elias, Magnus, Jonathan"
    - Discord mention: "@IkkeElias" or "<@123456>"
    - Discord ID: "561234642412313"
    - Single name/keyword: "jonathan"
    
    Returns:
        tuple: (list of search terms, optional discord_id)
    """
    if not search_string:
        return [], None
    
    search_string = search_string.strip()
    discord_id = None
    
    # Check if it's a raw Discord ID (all digits, 17-19 chars)
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


# =============================================================================
# NAME MATCHING
# =============================================================================

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
    
    return search_canonical == author_canonical


# =============================================================================
# QUOTE SEARCHING
# =============================================================================

def search_quotes(quotes, search_terms, discord_id=None):
    """
    Search quotes by author names, keywords, or Discord ID.
    
    Args:
        quotes: List of quote dictionaries
        search_terms: List of search terms (names/keywords)
        discord_id: Optional Discord user ID to filter by
    
    Returns:
        List of matching quotes
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
            
            # Check original message for content
            if term in q['original'].lower():
                canonical = get_canonical_name(term)
                is_name_search = canonical in NAME_ALIASES
                if not is_name_search or q['author'] != 'Anonym':
                    matching.append(q)
                    break
    
    return matching


# =============================================================================
# QUOTE PARSING
# =============================================================================

# Danish characters for regex patterns
DANISH_CHARS = r'A-Za-z\u00e6\u00f8\u00e5\u00c6\u00d8\u00c5'

# Author patterns (ordered by specificity)
AUTHOR_PATTERNS = [
    rf'^\s*[-\u2013\u2014]\s*([{DANISH_CHARS}][{DANISH_CHARS}\s]*?)(?:\s+(?:den|klokken|kl\.?|d\.?|p\u00e5|til|efter|lige)|\s+\d|[-\u2013\u2014]|\s*$)',
    rf'^\s*([{DANISH_CHARS}][{DANISH_CHARS}\s]*?)[-\u2013\u2014]\d',
    rf'^\s*([{DANISH_CHARS}]+)\s+\d{{1,2}}:\d{{2}}',
    rf'^\s*([{DANISH_CHARS}][{DANISH_CHARS}\s]*?)(?:\s+\d{{1,2}}[/\-\.]\d{{1,2}}|\s+kl)',
    rf'[-\u2013\u2014]\s*([{DANISH_CHARS}]+(?:\s+[{DANISH_CHARS}]+)?)',
]

# Words to clean from author names
CLEANUP_WORDS = ['den', 'klokken', 'kl', 'd', 'på', 'til', 'efter', 'lige', 'hellige', 'store', 'almægtige', 'dag']


def parse_quote(message_content):
    """
    Parse a quote and author from message content.
    
    Args:
        message_content: Raw message text
    
    Returns:
        tuple: (quote_text, author_name) or (None, None) if no quote found
    """
    # Find quoted text
    quote_match = re.search(r'"([^"]+)"', message_content)
    if not quote_match:
        return None, None
    
    quote = quote_match.group(1).strip()
    after_quote = message_content[quote_match.end():]
    before_quote = message_content[:quote_match.start()]
    
    # Try each author pattern
    for pattern in AUTHOR_PATTERNS:
        match = re.search(pattern, after_quote, re.IGNORECASE)
        if match:
            author = match.group(1).strip()
            
            # Clean up suffixes
            for word in CLEANUP_WORDS:
                author = re.sub(rf'\s+{word}.*$', '', author, flags=re.IGNORECASE)
            
            author = author.strip()
            if author and len(author) > 1 and author.lower() not in CLEANUP_WORDS:
                return quote, author.title()
    
    # Check for name before quote (pattern: name "quote")
    before_match = re.search(rf'([{DANISH_CHARS}]+)\s*$', before_quote.strip())
    if before_match:
        author = before_match.group(1).strip()
        if len(author) > 1:
            return quote, author.title()
    
    # Check for "fra/from name" pattern
    fra_match = re.search(rf'(?:fra|from)\s+([{DANISH_CHARS}]+)', message_content, re.IGNORECASE)
    if fra_match:
        return quote, fra_match.group(1).title()
    
    return quote, "Anonym"


# =============================================================================
# QUOTE STORAGE
# =============================================================================

def save_quotes_to_json(quotes, filepath):
    """
    Save quotes to a JSON file.
    
    Args:
        quotes: List of quote dictionaries
        filepath: Path to save JSON file
    """
    json_quotes = [{
        'quote': q['quote'],
        'author': q['author'],
        'original': q['original'],
        'date': q['date'].isoformat() if hasattr(q['date'], 'isoformat') else str(q['date']),
        'discord_id': q.get('discord_id'),
    } for q in quotes]
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(json_quotes, f, ensure_ascii=False, indent=2)
    
    print(f"Saved {len(json_quotes)} quotes to {filepath}")


def resolve_discord_id(user_id):
    """
    Resolve a Discord user ID to a name using the config mapping.
    
    Args:
        user_id: Discord user ID
    
    Returns:
        Name string or None if not found
    """
    return DISCORD_ID_TO_NAME.get(user_id)
