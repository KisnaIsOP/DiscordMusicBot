# Discord Music Bot

A feature-rich Discord music bot that can play music from YouTube in your server's voice channels.

## Features

- Join/Leave voice channels
- Play music from YouTube URLs
- Queue system for multiple songs
- Pause/Resume functionality
- Skip current song
- Error handling for invalid URLs and unavailable voice channels

## Prerequisites

- Python 3.8 or higher
- FFmpeg installed on your system
- Discord Bot Token
- Discord Developer Portal Application

## Setup Instructions

1. **Install FFmpeg**
   - Download FFmpeg from the official website: https://ffmpeg.org/download.html
   - Add FFmpeg to your system's PATH

2. **Install Python Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**
   - Create a `.env` file in the project root
   - Add your Discord bot token:
     ```
     DISCORD_TOKEN=your_bot_token_here
     ```

4. **Run the Bot**
   ```bash
   python bot.py
   ```

## Commands

- `!join` - Join your current voice channel
- `!play <YouTube URL>` - Play a song from YouTube
- `!pause` - Pause the current song
- `!resume` - Resume the paused song
- `!skip` - Skip the current song
- `!leave` - Disconnect the bot from the voice channel

## Error Handling

The bot includes error handling for:
- Invalid YouTube URLs
- Unavailable voice channels
- Missing permissions
- Network connectivity issues

## 24/7 Hosting Options

### 1. Railway Deployment (Recommended)
1. Create a Railway account at https://railway.app using your GitHub account

2. Install Railway CLI (optional):
   ```bash
   npm i -g @railway/cli
   ```

3. Create a new project in Railway:
   - Go to https://railway.app/dashboard
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your bot repository

4. Set up environment variables:
   - In your Railway project dashboard
   - Go to "Variables"
   - Add `DISCORD_TOKEN=your_bot_token`

5. Add buildpacks (if needed):
   - Railway automatically detects Python projects
   - It will install FFmpeg automatically

6. Deploy:
   - Railway will automatically deploy when you push to your GitHub repository
   - You can also deploy manually from the dashboard

7. Monitor your bot:
   - Use the Railway dashboard to view logs
   - Use the `!status` command to check bot status
   - Set up monitoring with UptimeRobot (optional)

Benefits of Railway:
- Easy deployment process
- Free tier available
- Automatic HTTPS
- Built-in CI/CD
- Great documentation
- Good performance
- Easy environment variable management

### 2. Heroku Deployment
1. Create a Heroku account at https://heroku.com
2. Install the Heroku CLI
3. Login to Heroku CLI:
   ```bash
   heroku login
   ```
4. Create a new Heroku app:
   ```bash
   heroku create your-bot-name
   ```
5. Add buildpacks:
   ```bash
   heroku buildpacks:add heroku/python
   heroku buildpacks:add https://github.com/jonathanong/heroku-buildpack-ffmpeg-latest.git
   ```
6. Set up environment variables:
   ```bash
   heroku config:set DISCORD_TOKEN=your_bot_token
   ```
7. Deploy to Heroku:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git push heroku master
   ```
8. Start the worker:
   ```bash
   heroku ps:scale worker=1
   ```

### 3. Oracle Cloud (Free Tier)
1. Create an Oracle Cloud account
2. Launch a compute instance (ARM-based instances are free)
3. Connect via SSH
4. Install required packages:
   ```bash
   sudo apt update
   sudo apt install python3-pip ffmpeg
   ```
5. Clone your bot repository
6. Install dependencies and run the bot using PM2:
   ```bash
   npm install pm2 -g
   pm2 start bot.py --name "discord-bot" --interpreter python3
   ```

### 4. Running on a Raspberry Pi
1. Set up your Raspberry Pi with Raspberry Pi OS
2. Install required packages:
   ```bash
   sudo apt update
   sudo apt install python3-pip ffmpeg
   ```
3. Clone your bot repository
4. Install dependencies
5. Run the bot using PM2 or create a systemd service

## Maintaining 24/7 Operation
- Monitor the bot's status using the `!status` command
- Set up monitoring alerts (e.g., UptimeRobot)
- Regularly check logs for errors
- Keep your hosting platform's billing information up to date
- Ensure your bot token remains valid

## Notes

- Make sure to keep your Discord bot token secure
- The bot requires appropriate Discord permissions to function
- Ensure stable internet connection for optimal performance
