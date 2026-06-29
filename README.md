# Music Bot

A self-hosted Discord music bot powered by **ytmusicapi** (YouTube Music search and metadata) and **yt-dlp** (audio stream extraction). Plays music in Discord voice channels via FFmpeg.

**Legal Notice:** This bot is intended for personal/private server use only. Do not host it as a public bot or monetize it. It uses ytmusicapi and yt-dlp to access YouTube Music content, which may violate YouTube's Terms of Service. Use at your own risk.

---

## Features

- `/play` -- Search and play from YouTube Music
- `/pause` / `/resume` -- Toggle playback
- `/skip` -- Skip current track (shows next track info)
- `/back` -- Go back to the previous track
- `/stop` -- Stop and clear queue
- `/nowplaying` -- Show current track info
- `/queue` / `/qlist` -- Browse the queue
- `/history` -- Show recently played tracks
- `/volume <0-200>` -- Adjust volume
- `/shuffle` -- Randomize queue order
- `/loop` -- Cycle loop modes (off, track, queue)
- `/playskip` / `/playtop` / `/addq` -- Queue placement variants
- `/remove` / `/move` / `/clear` -- Queue management
- `/search` -- Select from search results
- Auto-suggest -- Radio recommendations when queue ends
- `/control` -- Interactive buttons (pause, skip, stop, loop, shuffle)
- `/join` / `/disconnect` -- Voice channel management
- `/sync` -- Re-sync slash commands (owner)

---

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (`brew install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- FFmpeg (`brew install ffmpeg`, `apt install ffmpeg`, or `choco install ffmpeg`)
- A Discord Bot Token ([Discord Developer Portal](https://discord.com/developers/applications))
- **Optional:** A Google Cloud Project with OAuth 2.0 credentials (search and playback work without it)

---

## Quick Start

### 1. Clone

```bash
git clone https://github.com/AtulPahal/music_bot.git
cd music_bot
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env` with your credentials. Only `DISCORD_BOT_TOKEN` and `DISCORD_CLIENT_ID` are required:

```ini
DISCORD_BOT_TOKEN=your_discord_bot_token
DISCORD_CLIENT_ID=your_application_id
```

### 3. Run

```bash
uv run music-bot
```

For Docker:

```bash
docker compose up -d
```

### Tests

```bash
uv run pytest tests/ -v
```

---

## Commands

### Music
| Command | Description |
|---|---|
| `/play <query>` | Play a song or add to queue |
| `/addq <query>` | Add to queue (starts if idle) |
| `/playskip <query>` | Skip to a song immediately |
| `/playtop <query>` | Add to front of queue |
| `/back` | Go back to previous track |
| `/pause` | Pause playback |
| `/resume` | Resume playback |
| `/skip` | Skip current track |
| `/stop` | Stop and clear queue |
| `/nowplaying` | Show current track |
| `/volume 0-200` | Set volume |

### Queue
| Command | Description |
|---|---|
| `/queue` | Show paginated queue |
| `/qlist` | Show compact queue |
| `/history` | Show recently played |
| `/search <query>` | Search and select |
| `/shuffle` | Shuffle queue |
| `/loop` | Toggle loop mode |
| `/remove <pos>` | Remove a track |
| `/move <from> <to>` | Move a track |
| `/clear` | Clear queue |

### Utility
| Command | Description |
|---|---|
| `/join` | Join your voice channel |
| `/disconnect` | Disconnect from voice |
| `/control` | Interactive control panel |
| `/ping` | Check latency |
| `/sync` | Re-sync slash commands (owner) |
| `/help` | Show this help |

---

## Project Structure

```
bot/
  __main__.py         Entry point
  bot.py              Bot class and GuildVoiceState
  config.py           Configuration from .env
  cogs/               Command modules
    music.py          Core music commands
    queue.py          Queue management
    player_ui.py      Interactive UI
    utility.py        Utility commands
  audio/
    queue.py          Queue data structures
    source.py         yt-dlp audio extraction
    player.py         Playback controller
    autosuggest.py    Radio suggestions
  ui/
    embeds.py         Embed builders
    buttons.py        Music control buttons
    paginator.py      Queue pagination
  utils/
    time.py           Time formatting
    url_helpers.py    URL parsing
    checks.py         Permission checks
  services/
    ytmusic.py        YTMusic async wrapper
tests/                Pytest test suite
```

---

## Configuration

All settings via `.env`. See `.env.example` for the full list.

| Variable | Required | Default | Description |
|---|---|---|---|
| `DISCORD_BOT_TOKEN` | Yes | -- | Discord bot token |
| `DISCORD_CLIENT_ID` | Yes | -- | Discord application ID |
| `DISCORD_GUILD_ID` | No | 0 | Guild for fast slash sync |
| `YTM_AUTH_MODE` | No | none | none, oauth, or cookie |
| `YTM_AUTH_FILE` | No | data/oauth.json | Auth file path |
| `GOOGLE_CLIENT_ID` | No | -- | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | No | -- | Google OAuth secret |
| `COMMAND_PREFIX` | No | ! | Text command prefix |
| `DEFAULT_VOLUME` | No | 0.5 | Default volume (0.0-2.0) |
| `YT_RADIO_ENABLED` | No | true | Auto-suggest on queue end |
| `SUGGESTION_TIMEOUT` | No | 30 | Suggestion auto-dismiss seconds |
| `AUTO_DISCONNECT_TIMEOUT` | No | 300 | Idle disconnect seconds |

---

## License

MIT
