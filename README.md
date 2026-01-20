# Quote of the Day Discord Bot 💬

A Discord bot that fetches quotes from a dedicated channel and posts them as beautifully styled images.

## Features

- 🎨 **Styled Quote Images** - Generates beautiful quote images with author avatars
- 🔍 **Smart Search** - Filter quotes by name, @mention, Discord ID, or keywords
- 👥 **Name Aliases** - Recognizes different spellings/nicknames for the same person
- 📊 **Statistics** - View quote stats and top contributors
- 🔄 **Hot Reload** - Reload quotes and config without restarting

## Commands

| Command | Description |
|---------|-------------|
| `/quote` | Post a random quote as an image |
| `/quote [search]` | Search by name(s), @mention, or keyword |
| `/stats` | Show quote statistics |
| `/reload` | Reload quotes and configuration |

### Search Examples
- `/quote jonathan` - Quotes from Jonathan
- `/quote elias, magnus` - Quotes from Elias or Magnus
- `/quote @Username` - Quotes from mentioned user

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

## Quote Format

The bot reads messages from the quotes channel. Quotes should be formatted with the text in quotation marks:

```
"This is the quote text" - Author Name
```

## Requirements

- Python 3.10+
- discord.py
- Pillow
- python-dotenv
- aiohttp

## License

MIT License
