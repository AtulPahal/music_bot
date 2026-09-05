# Music Bot

A production-grade, highly configurable Discord music bot powered by **ytmusicapi** (YouTube Music search, playlists, and radio autoplay), **yt-dlp** (reliable audio stream extraction), and **FFmpeg** with **discord.py**.

**Legal Notice:** This bot is intended for personal and private server use only. Do not host it as a public bot or monetize it. It accesses YouTube Music content via ytmusicapi and yt-dlp.

---

## Features

- **Rich Playback:** Stream single songs, YouTube Shorts, full YouTube / YouTube Music playlists, and albums.
- **Robust Queue Engine:** FIFO queue with repeat modes (`off`, `track`, `queue`), history backtracking (`/back`), shuffling, deduplication (`/removedupes`), position jumping (`/jump`), and track swapping (`/move`).
- **Interactive Control Panels:** Dynamic `/control` panel and `/queue` paginator with visual progress bars, state indicators, and caller voice channel authorization security.
- **Radio Autoplay:** Automatic smart recommendations when the queue ends, with interactive "Play Now", "Add to Queue", and "Dismiss" buttons.
- **Zero Hardcoding:** Colors, timeouts, limits, FFmpeg options, yt-dlp options, presence status, and activity templates are completely configurable via `.env`.
- **Hybrid Commands:** Full parity between Discord Slash Commands (`/`) and text prefix commands (`!play`, `!skip`, etc.).
- **Voice Channel Auto-Cleanup:** Automatic disconnection when the voice channel becomes empty or after a configurable inactivity timeout.
- **Global Error Handling:** User-friendly embeds for permission errors, cooldowns, and missing arguments.
- **Cloud & Container Ready:** Built-in healthcheck HTTP server for Render, Koyeb, Railway, and Docker environments.

---

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (`brew install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- FFmpeg (`brew install ffmpeg`, `apt install ffmpeg`, or `choco install ffmpeg`)
- Discord Bot Token & Application ID ([Discord Developer Portal](https://discord.com/developers/applications))
- **Optional:** OAuth / Cookie credentials for YouTube Music (search and streaming work without any authentication)

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

Edit `.env` with your bot credentials:

```ini
DISCORD_BOT_TOKEN=your_discord_bot_token
DISCORD_CLIENT_ID=your_application_id
# Optional: Set your test server ID for instant slash command synchronization
DISCORD_GUILD_ID=your_guild_id
```

### 3. Run

```bash
# Run with uv
uv run music-bot

# Or run directly with Python
python -m bot
```

### Docker

```bash
docker compose up -d
```

### Render Deployment

When deploying on **Render**:
1. Create a **Background Worker** (or **Web Service**).
2. Set Environment Variables:
   - `DISCORD_BOT_TOKEN`: Your Discord bot token
   - `DISCORD_CLIENT_ID`: Your Discord application ID
   - `DISCORD_GUILD_ID`: (Optional) Your Discord server ID
3. If YouTube blocks cloud datacenter IPs with "Sign in to confirm you're not a bot", add:
   - `YTDL_COOKIES`: Paste your exported `cookies.txt` content directly as an environment variable in Render.

### Run Tests

```bash
uv run pytest -v
```

---

## Commands

### Music
| Command | Aliases | Description |
|---|---|---|
| `/play <query/url>` | `p` | Play a song, playlist, or add to queue |
| `/playskip <query>` | `ps` | Play a song immediately, skipping current track |
| `/playtop <query>` | `pt` | Add a track to the top of the queue |
| `/pause` | | Pause current playback |
| `/resume` | `unpause` | Resume paused playback |
| `/skip` | `s`, `next` | Skip current track |
| `/back` | `prev` | Replay previous track from history |
| `/replay` | `restart` | Replay the current track from beginning |
| `/stop` | | Stop playback and clear queue |
| `/nowplaying` | `np` | Display current track with visual progress bar |
| `/volume <0-200>` | `vol`, `v` | Adjust playback volume percentage |

### Queue
| Command | Aliases | Description |
|---|---|---|
| `/queue` | `q` | Interactive multi-page queue browser |
| `/qlist` | `ql` | Compact snapshot of upcoming tracks |
| `/history` | `hist` | Recently played tracks in the server |
| `/search <query>` | | Search YouTube Music with dropdown selector |
| `/shuffle` | | Randomize upcoming tracks |
| `/loop` | `repeat` | Cycle loop modes (`off` -> `track` -> `queue`) |
| `/remove <pos>` | `rm`, `del` | Remove a track by position number |
| `/move <from> <to>` | `mv` | Move a track between positions |
| `/jump <pos>` | `skipto` | Jump directly to a track in queue |
| `/clear` | | Clear all upcoming tracks |
| `/removedupes` | `dedupe` | Remove duplicate tracks from queue |

### Utility & Controls
| Command | Aliases | Description |
|---|---|---|
| `/control` | `panel`, `c` | Interactive music button control panel |
| `/join` | `connect`, `j` | Connect bot to your voice channel |
| `/disconnect` | `dc`, `leave` | Disconnect bot from voice |
| `/ping` | | Check gateway websocket latency |
| `/info` | `stats`, `about` | Display system stats, uptime, and versions |
| `/sync` | | Force re-sync slash commands (Owner Only) |
| `/help [command]` | | Dynamic help menu generated from loaded cogs |

---

## Configuration Reference

All settings can be customized in `.env`. See `.env.example` for the annotated list.

| Variable | Default | Description |
|---|---|---|
| `DISCORD_BOT_TOKEN` | *Required* | Discord bot authentication token |
| `DISCORD_CLIENT_ID` | *Required* | Discord bot application ID |
| `DISCORD_GUILD_ID` | `0` | Optional guild ID for instant slash command registration |
| `PORT` | `0` | Port for healthcheck HTTP server (auto-detected on Render) |
| `COMMAND_PREFIX` | `!` | Text command prefix |
| `DEFAULT_VOLUME` | `0.5` | Default volume (0.0 to 2.0) |
| `MAX_QUEUE_LENGTH` | `500` | Maximum songs allowed in queue |
| `AUTO_DISCONNECT_TIMEOUT` | `300` | Idle seconds before disconnecting from voice |
| `CONNECT_TIMEOUT` | `20.0` | Voice connection timeout in seconds |
| `YT_RADIO_ENABLED` | `true` | Enable autoplay radio suggestions on queue end |
| `SUGGESTION_TIMEOUT` | `30` | Seconds before autoplay suggestions auto-dismiss |
| `COLOR_PRIMARY` | `5865F2` | Hex color code for primary embeds |
| `COLOR_SUCCESS` | `57F287` | Hex color code for success embeds |
| `COLOR_ERROR` | `ED4245` | Hex color code for error embeds |
| `COLOR_WARNING` | `FEE75C` | Hex color code for warning embeds |
| `FFMPEG_BIN` | `ffmpeg` | Path or executable name for FFmpeg |
| `FFMPEG_OPTIONS` | `-vn -bufsize 64k` | FFmpeg audio output parameters |
| `YTDL_FORMAT` | `bestaudio/best` | yt-dlp audio format selector |
| `YTDL_PLAYER_CLIENTS` | `android` | Client fallback for bypassing datacenter bot checks |
| `YTDL_PLAYER_SKIP` | `configs,webpage` | Skip webpage download to avoid datacenter bot challenge |
| `YTDL_COOKIES` | `""` | Raw cookies.txt content pasted into environment variables |
| `YT_PROXY` | `""` | Optional HTTP/SOCKS5 proxy URL |
| `BUTTON_TIMEOUT` | `180` | Interactive UI component timeout seconds |
