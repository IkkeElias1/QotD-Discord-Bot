# Quote of the Day Discord Bot 💬

A Discord bot that fetches quotes from a dedicated channel and posts them as beautifully styled images.

## Features

- 🎨 **Styled Quote Images** - Generates beautiful quote images with author avatars
- 🔍 **Advanced Name Matching** - Multi-layer matching with fuzzy, phonetic, and alias support
- 🇩🇰 **Nordic Character Support** - Handles æ, ø, å and v/w interchange
- 👥 **Entity Disambiguation** - Distinguishes between different people with similar names
- 📊 **Statistics** - View quote stats and top contributors
- 🔄 **Hot Reload** - Reload quotes and config without restarting
- 🐛 **Debug Mode** - Detailed matching information for troubleshooting

## Commands

| Command | Description |
|---------|-------------|
| `/quote` | Post a random quote as an image |
| `/quote [search]` | Search by name(s), @mention, or keyword |
| `/quote [search] --debug` | Search with detailed matching debug info |
| `/stats` | Show quote statistics |
| `/reload` | Reload quotes and configuration |
| `/matching-info` | Show matching system configuration |
| `/match-test [query]` | Test name matching against a query |

### Search Examples
- `/quote jonathan` - Quotes from Jonathan
- `/quote jonethen` - Also matches Jonathan (typo tolerance)
- `/quote {name1}, {name2}` - Quotes from Elias or Magnus
- `/quote {@Username}` - Quotes from mentioned user
- `/quote {alias}` - Matches via custom alias
- `/quote {name} --debug` - Shows matching debug info

## Setup

### 1. Clone the repository
```bash
git clone https://github.com/IkkeElias1/QotD-Discord-Bot.git
cd QotD-Discord-Bot
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment
Copy the example files and fill in your values:
```bash
cp .env.example .env
cp config/aliases.json.example config/aliases.json
```

Edit `.env` with your Discord bot token and channel IDs:
```env
DISCORD_TOKEN=your_bot_token_here
QUOTES_CHANNEL_ID=123456789012345678
GENERAL_CHANNEL_ID=123456789012345678
```

### 4. Configure aliases (optional)
Edit `config/aliases.json` to add name variations and Discord ID mappings for your server members.

### 5. Run the bot
```bash
python main.py
```

## Configuration

### Environment Variables (`.env`)

| Variable | Description | Required |
|----------|-------------|----------|
| `DISCORD_TOKEN` | Your Discord bot token | ✅ |
| `QUOTES_CHANNEL_ID` | Channel ID to read quotes from | ✅ |
| `GENERAL_CHANNEL_ID` | Channel ID to post quote images | ✅ |
| `IMAGE_WIDTH` | Quote image width (default: 1200) | ❌ |
| `IMAGE_HEIGHT` | Quote image height (default: 675) | ❌ |

### Aliases (`config/aliases.json`)

Map name variations and Discord IDs to canonical names:
```json
{
  "name_aliases": {
    "john": ["john", "johnny", "jon"]
  },
  "discord_id_to_name": {
    "123456789012345678": "John"
  }
}
```

### Custom Fonts
By default, the system uses standard OS fonts. On **Linux**, this may result in smaller-than-intended text. You can override the default font on Linux, Windows, or macOS by following these steps:

1. **Download** a font file in `.ttf` (TrueType) format.
2. **Rename** the file to `font.ttf`.
3. **Move** the file into the project's **root directory**.

> [!IMPORTANT]
> Ensure the filename is exactly `font.ttf` for the system to recognize it on startup.

## Advanced Name Matching System

The bot includes a sophisticated nickname resolution system that handles:

### Matching Layers (Cascading)
1. **Exact Match** - Case-insensitive, normalized comparison
2. **Manual Overrides** - Custom alias mappings (e.g., "faxekondi_lover" → "Jonathan")
3. **Discord ID** - Resolution via ID or @mention
4. **Fuzzy String** - Jaro-Winkler, Levenshtein, token sort/set ratios
5. **Phonetic** - Double Metaphone algorithm
6. **Nickname Dictionary** - Standard name variations

### Configuration (`config/matching_config.json`)

```json
{
  "matching_layers": {
    "fuzzy_string": true,
    "phonetic": true,
    "standard_nicknames": false,
    "custom_aliases": true
  },
  "thresholds": {
    "hybrid_min": 0.75,
    "jaro_winkler_min": 0.85,
    "phonetic_primary_min": 0.95
  },
  "weights": {
    "jaro_winkler": 0.35,
    "levenshtein": 0.25,
    "token_sort": 0.20,
    "token_set": 0.20
  },
  "blocking_strategy": "multi_level",
  "debug_mode": false
}
```

### Enhanced Aliases (`config/aliases_new.json`)

```json
{
  "manual_overrides": {
    "faxekondi_lover": {
      "canonical_name": "Jonathan",
      "confidence": 1.0,
      "match_type": "associative",
      "notes": "References favorite Danish soda"
    }
  },
  "cluster_map": {
    "Person_1": {
      "canonical_name": "Jonathan",
      "aliases": ["jonathan", "jon", "jona", "johnny"],
      "discord_id": "123456789012345678",
      "quote_count": 47
    }
  }
}
```

### Nordic Character Handling

The system handles Danish/Norwegian/Swedish characters:
- **æ** → ae
- **ø** → o
- **å** → a
- **v/w interchange** - "valdemar" ↔ "waldemar", "walmart" → "Valdemar"

## Quote Format

The bot reads messages from the quotes channel. Quotes should be formatted with the text in quotation marks:

```
"This is the quote text" - Author Name
```

## Requirements

- Python 3.10+
- discord.py>=2.0.0
- Pillow>=9.0.0
- python-dotenv>=1.0.0
- aiohttp>=3.8.0
- pytz>=2023.3
- **rapidfuzz>=3.0.0** (for fuzzy matching)
- **metaphone>=0.6** (for phonetic matching)

## Running Tests

```bash
python -m pytest tests/ -v
```

## Project Structure

```
.
├── main.py                 # Bot entry point
├── quotes.py               # Quote parsing and search
├── image.py                # Quote image generation
├── config/
│   ├── __init__.py
│   ├── aliases.json        # Basic aliases (legacy)
│   ├── aliases_new.json    # Enhanced aliases with metadata
│   └── matching_config.json # Matching system configuration
├── matching/               # Advanced name matching module
│   ├── __init__.py
│   ├── core.py             # NameMatcher main class
│   ├── algorithms.py       # String similarity (RapidFuzz)
│   ├── phonetic.py         # Double Metaphone matching
│   ├── normalization.py    # Nordic character handling
│   ├── blocking.py         # Performance optimization
│   ├── entity_resolution.py # Clustering/disambiguation
│   ├── dictionaries.py     # Nickname dictionary
│   ├── config_manager.py   # Configuration loading
│   └── debug.py            # Debug logging
└── tests/
    └── test_matching.py    # Comprehensive test suite
```

## License

MIT License
