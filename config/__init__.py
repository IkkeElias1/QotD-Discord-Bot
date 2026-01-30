# -*- coding: utf-8 -*-
"""
Configuration loader for Quote Bot.
Loads settings from .env and JSON config files.
"""

import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# =============================================================================
# DISCORD CONFIGURATION
# =============================================================================

TOKEN = os.getenv('DISCORD_TOKEN')
QUOTES_CHANNEL_ID = int(os.getenv('QUOTES_CHANNEL_ID', 0))
GENERAL_CHANNEL_ID = int(os.getenv('GENERAL_CHANNEL_ID', 0))

# =============================================================================
# IMAGE SETTINGS
# =============================================================================

IMAGE_WIDTH = int(os.getenv('IMAGE_WIDTH', 1200))
IMAGE_HEIGHT = int(os.getenv('IMAGE_HEIGHT', 675))
BACKGROUND_COLOR = (30, 30, 40)
TEXT_COLOR = (255, 255, 255)
ACCENT_COLOR = (255, 215, 0)
AUTHOR_COLOR = (180, 180, 180)

# =============================================================================
# ALIASES CONFIGURATION
# =============================================================================

def load_aliases():
    """Load name aliases and Discord ID mappings from JSON."""
    config_path = os.path.join(os.path.dirname(__file__), 'aliases.json')
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        name_aliases = data.get('name_aliases', {})
        
        # Convert string keys to int for Discord IDs
        discord_id_to_name = {
            int(k): v for k, v in data.get('discord_id_to_name', {}).items()
        }
        
        return name_aliases, discord_id_to_name
    
    except FileNotFoundError:
        print(f"Warning: aliases.json not found at {config_path}")
        return {}, {}
    except json.JSONDecodeError as e:
        print(f"Error parsing aliases.json: {e}")
        return {}, {}


# Load aliases on module import
NAME_ALIASES, DISCORD_ID_TO_NAME = load_aliases()


def reload_aliases():
    """Reload aliases from file (useful for hot-reloading)."""
    global NAME_ALIASES, DISCORD_ID_TO_NAME
    NAME_ALIASES, DISCORD_ID_TO_NAME = load_aliases()
    return NAME_ALIASES, DISCORD_ID_TO_NAME


# =============================================================================
# MATCHING SYSTEM CONFIGURATION
# =============================================================================

# Path to enhanced aliases configuration
ENHANCED_ALIASES_PATH = os.path.join(os.path.dirname(__file__), 'aliases_new.json')

# Path to matching configuration
MATCHING_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'matching_config.json')

def get_matching_config_path():
    """Get the path to the matching configuration file."""
    return MATCHING_CONFIG_PATH

def get_aliases_path():
    """Get the path to the enhanced aliases configuration file."""
    if os.path.exists(ENHANCED_ALIASES_PATH):
        return ENHANCED_ALIASES_PATH
    return os.path.join(os.path.dirname(__file__), 'aliases.json')
