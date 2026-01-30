# -*- coding: utf-8 -*-
"""
Quote fetching and parsing for Quote Bot.
Handles parsing quotes from messages and searching.
"""

import re
import json
import os
from typing import List, Dict, Tuple, Optional, Any
from config import NAME_ALIASES, DISCORD_ID_TO_NAME, get_matching_config_path, get_aliases_path

# Import the new matching system
try:
    from matching import NameMatcher
    MATCHER_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Advanced matching not available: {e}")
    MATCHER_AVAILABLE = False

# Global matcher instance (lazy initialization)
_matcher: Optional['NameMatcher'] = None


def get_matcher() -> Optional['NameMatcher']:
    """
    Get the global NameMatcher instance.
    
    Creates the matcher on first access for lazy initialization.
    
    Returns:
        NameMatcher instance or None if not available
    """
    global _matcher
    
    if not MATCHER_AVAILABLE:
        return None
    
    if _matcher is None:
        try:
            _matcher = NameMatcher(
                config_path=get_matching_config_path(),
                aliases_path=get_aliases_path()
            )
            print("Advanced matching system initialized")
        except Exception as e:
            print(f"Warning: Could not initialize matcher: {e}")
            return None
    
    return _matcher


def reload_matcher() -> bool:
    """
    Reload the matcher configuration.
    
    Returns:
        True if reload was successful
    """
    global _matcher
    
    if _matcher is not None:
        return _matcher.reload_config()
    
    # Try to reinitialize
    _matcher = None
    return get_matcher() is not None


# =============================================================================
# SEARCH INPUT PARSING
# =============================================================================

def parse_search_input(search_string: str) -> Tuple[List[str], Optional[int], bool]:
    """
    Parse search input that can be:
    - Comma-separated names: "Elias, Magnus, Jonathan"
    - Discord mention: "@IkkeElias" or "<@123456>"
    - Discord ID: "561234642412313"
    - Single name/keyword: "jonathan"
    - Debug flag: "--debug"
    
    Returns:
        tuple: (list of search terms, optional discord_id, debug_flag)
    """
    if not search_string:
        return [], None, False
    
    search_string = search_string.strip()
    discord_id = None
    debug_mode = False
    
    # Check for debug flag
    if '--debug' in search_string:
        debug_mode = True
        search_string = search_string.replace('--debug', '').strip()
    
    if not search_string:
        return [], None, debug_mode
    
    # Check if it's a raw Discord ID (all digits, 17-19 chars)
    if search_string.isdigit() and len(search_string) > 15:
        discord_id = int(search_string)
        return [], discord_id, debug_mode
    
    # Check for Discord mention format <@123456> or <@!123456>
    mention_match = re.search(r'<@!?(\d+)>', search_string)
    if mention_match:
        discord_id = int(mention_match.group(1))
        return [], discord_id, debug_mode
    
    # Check for @username format (remove the @)
    if search_string.startswith('@'):
        search_string = search_string[1:]
    
    # Split by comma for multiple names
    if ',' in search_string:
        terms = [t.strip().lower() for t in search_string.split(',') if t.strip()]
    else:
        terms = [search_string.lower()]
    
    return terms, discord_id, debug_mode


# =============================================================================
# NAME MATCHING (Enhanced with new system)
# =============================================================================

def normalize_name(name: str) -> str:
    """Normalize a name for comparison."""
    matcher = get_matcher()
    if matcher:
        return matcher.normalizer.normalize(name)
    return name.lower().strip()


def get_canonical_name(name: str) -> str:
    """
    Get the canonical name for any alias.
    
    Uses the new matching system if available, falls back to legacy.
    """
    matcher = get_matcher()
    
    if matcher:
        canonical = matcher.get_canonical_name(name)
        if canonical:
            return canonical
    
    # Fallback to legacy system
    name_lower = normalize_name(name)
    
    for canonical, aliases in NAME_ALIASES.items():
        if name_lower in aliases or name_lower == canonical:
            return canonical
        for alias in aliases:
            if alias in name_lower or name_lower in alias:
                return canonical
    
    return name_lower


def names_match(search_term: str, author: str) -> bool:
    """
    Check if a search term matches an author name.
    
    Uses advanced matching if available.
    """
    matcher = get_matcher()
    
    if matcher:
        results = matcher.match(search_term, [author], return_scores=True)
        if results:
            _, confidence, _ = results[0]
            return confidence >= 0.70  # Allow somewhat loose matching for search
    
    # Fallback to legacy matching
    search_lower = normalize_name(search_term)
    author_lower = normalize_name(author)
    
    # Direct match
    if search_lower in author_lower or author_lower in search_lower:
        return True
    
    # Check if both resolve to the same canonical name
    search_canonical = get_canonical_name(search_lower)
    author_canonical = get_canonical_name(author_lower)
    
    return search_canonical == author_canonical


def find_matching_authors(
    query: str,
    all_quotes: List[Dict],
    debug: bool = False
) -> Tuple[List[str], Optional[str]]:
    """
    Find all authors matching the query using advanced matching.
    
    Args:
        query: Search query (name, @mention, or keyword)
        all_quotes: List of all quote objects
        debug: Enable debug output
        
    Returns:
        Tuple of (list of matching author names, debug info string)
    """
    matcher = get_matcher()
    
    # Extract all unique authors (excluding Anonym)
    all_authors = list(set(
        q['author'] for q in all_quotes 
        if q.get('author') and q['author'] != 'Anonym'
    ))
    
    if not all_authors:
        return [], None
    
    debug_info = None
    
    # Check if query is a Discord mention
    if query.startswith('<@') and query.endswith('>'):
        discord_id = query.strip('<@!>')
        if matcher:
            discord_map = matcher.discord_id_map
            if discord_id in discord_map:
                name = discord_map[discord_id]
                # Find this name in our authors
                for author in all_authors:
                    if matcher.normalizer.normalize(author) == matcher.normalizer.normalize(name):
                        return [author], f"Discord ID {discord_id} → {name}"
                return [name], f"Discord ID {discord_id} → {name} (not in current quotes)"
    
    if matcher:
        # Use advanced matcher
        results = matcher.match(
            query=query,
            candidates=all_authors,
            return_scores=True,
            debug=debug
        )
        
        if results:
            matching_names = [name for name, score, _ in results]
            if debug:
                debug_info = matcher.get_debug_output()
            return matching_names, debug_info
        
        if debug:
            debug_info = matcher.get_debug_output()
    
    else:
        # Fallback to legacy matching
        matching = []
        for author in all_authors:
            if names_match(query, author):
                matching.append(author)
        return matching, None
    
    return [], debug_info


# =============================================================================
# QUOTE SEARCHING (Enhanced)
# =============================================================================

def search_quotes(
    quotes: List[Dict],
    search_terms: List[str],
    discord_id: Optional[int] = None,
    debug: bool = False
) -> Tuple[List[Dict], Optional[str]]:
    """
    Search quotes by author names, keywords, or Discord ID.
    
    Enhanced version that uses advanced matching system.
    
    Args:
        quotes: List of quote dictionaries
        search_terms: List of search terms (names/keywords)
        discord_id: Optional Discord user ID to filter by
        debug: Enable debug output
    
    Returns:
        Tuple of (list of matching quotes, debug info string)
    """
    if not search_terms and not discord_id:
        return quotes, None
    
    matching = []
    debug_info = None
    matched_authors = set()
    
    # First, try to match authors using the advanced system
    if search_terms:
        for term in search_terms:
            authors, term_debug = find_matching_authors(term, quotes, debug=debug)
            matched_authors.update(authors)
            if term_debug and debug:
                debug_info = (debug_info or "") + f"\n{term}: {term_debug}"
    
    for q in quotes:
        # Check Discord ID match
        if discord_id:
            if f'<@{discord_id}>' in q['original'] or f'<@!{discord_id}>' in q['original']:
                matching.append(q)
                continue
            if q.get('discord_id') == discord_id:
                matching.append(q)
                continue
        
        # Check if author was matched by the advanced system
        if q['author'] in matched_authors:
            matching.append(q)
            continue
        
        # Check each search term for content matching
        for term in search_terms:
            # Skip if author is Anonym for name searches
            if q['author'] == 'Anonym':
                # Only match content, not name patterns
                if term in q['quote'].lower():
                    matching.append(q)
                    break
            else:
                # Check quote content
                if term in q['quote'].lower():
                    matching.append(q)
                    break
    
    # Remove duplicates while preserving order
    seen = set()
    unique_matching = []
    for q in matching:
        q_id = (q['quote'], q['author'])
        if q_id not in seen:
            seen.add(q_id)
            unique_matching.append(q)
    
    return unique_matching, debug_info


# =============================================================================
# QUOTE PARSING
# =============================================================================

# Danish characters for regex patterns
DANISH_CHARS = r'A-Za-z\u00e6\u00f8\u00e5\u00c6\u00d8\u00c5'

# Author patterns (ordered by specificity)
AUTHOR_PATTERNS = [
    # "quote" - Author or "quote" -Author (with dash)
    rf'^\s*[-\u2013\u2014]\s*([{DANISH_CHARS}][{DANISH_CHARS}\s]*?)(?:\s+(?:den|klokken|kl\.?|d\.?|p\u00e5|til|efter|lige|i\s+respons)|\s+\d|[-\u2013\u2014]|\s*$)',
    # "quote" Author date (no dash, name followed by date)
    rf'^\s*([{DANISH_CHARS}]+)\s+(?:den\s+)?(?:hellige\s+)?(?:dag\s+)?(?:d\.?\s*)?\d{{1,2}}[/\-\.]\d{{1,2}}',
    # "quote" Author (parenthetical info)
    rf'^\s*([{DANISH_CHARS}]+)\s*\([^)]+\)',
    # "quote" Author I respons til / i response to
    rf'^\s*([{DANISH_CHARS}]+)\s+[Ii]\s+respons',
    # Author-date pattern
    rf'^\s*([{DANISH_CHARS}][{DANISH_CHARS}\s]*?)[-\u2013\u2014]\d',
    # Author time pattern
    rf'^\s*([{DANISH_CHARS}]+)\s+\d{{1,2}}:\d{{2}}',
    # Author with date/kl
    rf'^\s*([{DANISH_CHARS}][{DANISH_CHARS}\s]*?)(?:\s+\d{{1,2}}[/\-\.]\d{{1,2}}|\s+kl)',
    # Fallback: dash then name
    rf'[-\u2013\u2014]\s*([{DANISH_CHARS}]+(?:\s+[{DANISH_CHARS}]+)?)',
    # Direct name after quote (no punctuation) - must be a single word followed by space
    rf'^\s+([{DANISH_CHARS}]{{2,}})\s+',
]

# Words to clean from author names
CLEANUP_WORDS = ['den', 'klokken', 'kl', 'd', 'på', 'til', 'efter', 'lige', 'hellige', 'store', 'almægtige', 'dag', 'i', 'respons']


def parse_quote(message_content):
    """
    Parse a quote and author from message content.
    Handles nested quotes by finding the outermost quote.
    
    Args:
        message_content: Raw message text
    
    Returns:
        tuple: (quote_text, author_name) or (None, None) if no quote found
    """
    # Find the FIRST opening quote
    first_quote_pos = message_content.find('"')
    if first_quote_pos == -1:
        return None, None
    
    # Find the LAST closing quote that's followed by author info (dash, name, date pattern)
    # Look for patterns like: " - Name, " Name date, etc.
    content_after_first = message_content[first_quote_pos + 1:]
    
    # Try to find the end of the main quote by looking for closing quote followed by author pattern
    best_end = -1
    
    # Pattern: closing quote followed by dash or name pattern
    for match in re.finditer(r'"', content_after_first):
        pos = match.start()
        after_this_quote = content_after_first[pos + 1:]
        
        # Check if this looks like the end of the main quote
        # (followed by dash, name, or end of meaningful content)
        if re.match(r'\s*[-\u2013\u2014]', after_this_quote):
            best_end = pos
        elif re.match(rf'\s+[{DANISH_CHARS}]{{2,}}[\s\d]', after_this_quote):
            best_end = pos
        elif re.match(r'\s*$', after_this_quote) or re.match(r'\s*\n', after_this_quote):
            best_end = pos
        # Also check for "quote" Name date pattern
        elif re.match(rf'\s+[{DANISH_CHARS}]+\s+(?:den\s+)?\d', after_this_quote, re.IGNORECASE):
            best_end = pos
    
    # If no good end found, fall back to last quote mark
    if best_end == -1:
        best_end = content_after_first.rfind('"')
        if best_end == -1:
            return None, None
    
    quote = content_after_first[:best_end].strip()
    after_quote = content_after_first[best_end + 1:]
    before_quote = message_content[:first_quote_pos]
    
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
