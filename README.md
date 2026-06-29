# 🎵 Music Bot

A self-hosted Discord music bot powered by **ytmusicapi** (YouTube Music search & metadata) and **yt-dlp** (audio stream extraction). Plays music in Discord voice channels via FFmpeg.

> ⚠️ **Legal Notice**
>
> This bot is intended **for personal/private server use only**. Do not host it as a public bot or monetize it. It uses ytmusicapi and yt-dlp to access YouTube Music content, which may violate YouTube's Terms of Service. Use at your own risk. The authors are not responsible for any misuse.

---

## Features

### Phase 1 (MVP) ✓
- `/play <song name or URL>` — Search and play from YouTube Music
- `/pause` / `/resume` — Toggle playback
- `/skip` — Skip current track
- `/stop` — Stop and clear queue
- `/nowplaying` — Show current track info
- `/queue` — Browse the queue (paginated)
- `/volume <0-200>` — Adjust volume
- `/shuffle` — Randomize queue order
- `/loop` — Cycle loop modes (off → track → queue)
- `/playskip` / `/playtop` — Queue placement variants
- `/remove` / `/move` / `/clear` — Queue management
- `/search` — Select from search results
- **Auto-suggest** — Radio recommendations when queue ends
- `/control` — Interactive buttons (pause, skip, stop, loop, shuffle)
- `/join` / `/disconnect` — Voice channel management

### Future Phases
- Lyrics display
- Liked songs / history
- Playlist support
- Sound effects / bass boost

---

## Prerequisites

- Python 3.11+
- FFmpeg (`brew install ffmpeg`, `apt install ffmpeg`, or `choco install ffmpeg`)
- A Discord Bot Token ([Discord Developer Portal](https://discord.com/developers/applications))
- **Optional:** A Google Cloud Project with OAuth 2.0 credentials (for ytmusicapi library features — search and playback work without it)

---

## Quick Start

### 1. Clone & Install

```bash
git clone <your-repo-url>
cd music-bot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env` with your credentials. Only `DISCORD_BOT_TOKEN` and `DISCORD_CLIENT_ID` are required:

```ini
DISCORD_BOT_TOKEN=your_discord_bot_token
DISCORD_CLIENT_ID=your_application_id
DISCORD_GUILD_ID=guild_id_for_slash_sync
# Google OAuth is optional — leave blank for unauthenticated mode
# YTM_AUTH_MODE=none
# GOOGLE_CLIENT_ID=
# GOOGLE_CLIENT_SECRET=
```

### 3. Set Up YouTube Music Auth (Optional)

Search and playback work **without any auth**. For additional features
(library, playlists, ratings), set up OAuth:

```bash
uv run python -c "
from ytmusicapi import setup_oauth
setup_oauth(
    'YOUR_GOOGLE_CLIENT_ID',
    'YOUR_GOOGLE_CLIENT_SECRET',
    filepath='data/oauth.json'
)
"
```

Follow the printed URL to authorize and paste the redirect URL back.
Then set `YTM_AUTH_MODE=oauth` in your `.env`.

### 4. Run

```bash
# Option A: via uv (recommended)
uv run music-bot

# Option B: python -m bot (also works)
uv run python -m bot

# Option C: activate venv and run directly
source .venv/bin/activate
python -m bot
```

### Docker

```bash
cp .env.example .env
# Edit .env with your credentials
docker compose up -d
```

### Tests

```bash
# Run all 64+ tests
uv run pytest tests/ -v

# Run with coverage (requires pytest-cov)
uv run pytest tests/ --cov=bot
```

---

## Commands Reference

### 🎵 Music
| Command | Description |
|---|---|
| `/play <query/url>` | Play a song or add to queue |
| `/playskip <query>` | Skip to a song immediately |
| `/playtop <query>` | Add to front of queue |
| `/pause` | Pause playback |
| `/resume` | Resume playback |
| `/skip` | Skip current track |
| `/stop` | Stop and clear queue |
| `/nowplaying` | Show current track |
| `/volume <0-200>` | Set volume |

### 📋 Queue
| Command | Description |
|---|---|
| `/queue` | Show the queue |
| `/shuffle` | Shuffle queue |
| `/loop` | Toggle loop mode |
| `/remove <pos>` | Remove a track |
| `/move <from> <to>` | Move a track |
| `/clear` | Clear queue |
| `/search <query>` | Search and select |

### 🔧 Utility
| Command | Description |
|---|---|
| `/join` | Join your voice channel |
| `/disconnect` | Disconnect from voice |
| `/control` | Interactive control panel |
| `/ping` | Check latency |
| `/help` | Show this help |

---

## Project Structure

```
music-bot/
├── bot/
│   ├── __main__.py          # Entry point
│   ├── bot.py               # Bot class + GuildVoiceState
│   ├── config.py            # Config from .env
│   ├── cogs/                # Command modules
│   │   ├── music.py         # Core music commands
│   │   ├── queue.py         # Queue management
│   │   ├── player_ui.py     # Interactive UI
│   │   └── utility.py       # Utility commands
│   ├── audio/
│   │   ├── queue.py         # Queue data structures
│   │   ├── source.py        # yt-dlp audio extraction
│   │   ├── player.py        # Playback controller
│   │   └── autosuggest.py   # Radio suggestions
│   ├── ui/
│   │   ├── embeds.py        # Embed builders
│   │   ├── buttons.py       # Music control buttons
│   │   └── paginator.py     # Queue pagination
│   ├── utils/
│   │   ├── time.py          # Time formatting
│   │   ├── url_helpers.py   # URL parsing
│   │   └── checks.py        # Permission checks
│   └── services/
│       └── ytmusic.py       # YTMusic async wrapper
├── tests/
├── data/                    # Runtime data (oauth.json)
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## Configuration

All settings via `.env` file. See `.env.example` for the full list.

| Variable | Required | Default | Description |
|---|---|---|---|
| `DISCORD_BOT_TOKEN` | ✅ | — | Discord bot token |
| `DISCORD_CLIENT_ID` | ✅ | — | Discord application ID |
| `DISCORD_GUILD_ID` | ❌ | `0` | Guild for fast slash sync |
| `YTM_AUTH_MODE` | ❌ | `none` | `none` (unauthenticated), `oauth`, or `cookie` |
| `YTM_AUTH_FILE` | ❌ | `data/oauth.json` | Auth file path |
| `GOOGLE_CLIENT_ID` | ❌ | — | Google OAuth client ID (optional) |
| `GOOGLE_CLIENT_SECRET` | ❌ | — | Google OAuth secret (optional) |
| `COMMAND_PREFIX` | ❌ | `!` | Text command prefix |
| `DEFAULT_VOLUME` | ❌ | `0.5` | Default volume (0.0–2.0) |
| `YT_RADIO_ENABLED` | ❌ | `true` | Auto-suggest on queue end |
| `SUGGESTION_TIMEOUT` | ❌ | `30` | Suggestion auto-dismiss seconds |
| `AUTO_DISCONNECT_TIMEOUT` | ❌ | `300` | Idle disconnect seconds |

---

## License

MIT
