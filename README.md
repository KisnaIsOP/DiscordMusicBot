# 🎵 Harmony Hub - Discord Music Bot

<div align="center">
  
![Harmony Hub Banner](https://i.imgur.com/XQxYJfX.png)

[![Discord.py Version](https://img.shields.io/badge/discord.py-2.3.2-blue.svg)](https://discordpy.readthedocs.io/en/stable/)
[![Python Version](https://img.shields.io/badge/python-3.8+-yellow.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Railway Deploy](https://img.shields.io/badge/Railway-Deploy-purple.svg)](https://railway.app/)

*A powerful, modern Discord music bot with multi-platform support and interactive controls*

[Features](#✨-features) • [Commands](#🎮-commands) • [Installation](#🚀-installation) • [Configuration](#⚙️-configuration) • [Deployment](#🌐-deployment)

</div>

## ✨ Features

### 🎵 Multi-Platform Support
- **YouTube** - Stream from videos and playlists
- **Spotify** - Play tracks, albums, and playlists
- **SoundCloud** - Stream your favorite tracks
- **Direct URLs** - Support for direct audio links

### 🎚️ Advanced Playback
- **High Quality Audio** - Crystal clear 192kbps audio
- **Queue Management** - Add, remove, and view songs
- **Interactive Controls** - Buttons for easy control
- **Loop Mode** - Repeat your favorite tracks
- **Shuffle** - Mix up your playlist

### 🛠️ Technical Features
- **Auto Reconnect** - Stable connection handling
- **Error Recovery** - Robust error handling
- **Resource Efficient** - Optimized performance
- **Cross-Platform** - Works on all Discord platforms

## 🎮 Commands

### Essential Commands
| Command | Description |
|---------|-------------|
| `!play <song>` | Play a song or add to queue |
| `!pause` | Pause current playback |
| `!resume` | Resume playback |
| `!skip` | Skip to next song |
| `!stop` | Stop playback and clear queue |

### Queue Management
| Command | Description |
|---------|-------------|
| `!queue` | Display current queue |
| `!clear` | Clear the queue |
| `!remove <number>` | Remove specific song |
| `!shuffle` | Shuffle the queue |

### Extra Features
| Command | Description |
|---------|-------------|
| `!loop` | Toggle loop mode |
| `!nowplaying` | Show current song |
| `!join` | Join voice channel |
| `!leave` | Leave voice channel |

## 🚀 Installation

1. **Clone the Repository**
   ```bash
   git clone https://github.com/YourUsername/DiscordMusicBot.git
   cd DiscordMusicBot
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up Environment Variables**
   ```bash
   # Create .env file
   DISCORD_TOKEN=your_token_here
   SPOTIFY_CLIENT_ID=optional_spotify_id
   SPOTIFY_CLIENT_SECRET=optional_spotify_secret
   ```

## ⚙️ Configuration

### Required Dependencies
- Python 3.8+
- FFmpeg
- discord.py
- yt-dlp
- spotipy (optional)

### Optional Features
- Spotify API credentials for Spotify support
- Custom prefix configuration
- Volume control settings

## 🌐 Deployment

### Railway Deployment
1. Fork this repository
2. Create a new Railway project
3. Connect your GitHub repository
4. Add environment variables
5. Deploy!

### Manual Deployment
1. Install Python and FFmpeg
2. Set up environment variables
3. Run `python bot.py`

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 💖 Support

If you like this project, please give it a ⭐ star on GitHub!

---

<div align="center">
  
Made with ❤️ by [KISNA]

[GitHub](https://github.com/YourUsername) • [Discord](https://discord.gg/YourServer)

</div>
