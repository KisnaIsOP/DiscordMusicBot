import os
import asyncio
import discord
from discord.ext import commands
import yt_dlp
from collections import deque
from dotenv import load_dotenv
import re
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import logging
import shutil
from discord import ButtonStyle
from discord.ui import Button, View
from async_timeout import timeout
import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord')

# Load environment variables
load_dotenv()

# Constants for audio
YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'force-ipv4': True,
    'extract_flat': False,
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -af "volume=0.5"'
}

# Configure Spotify API (optional)
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')

# URL patterns for different platforms
URL_PATTERNS = {
    'youtube': r'(?:https?://)?(?:www\.)?(?:youtube\.com|youtu\.be)',
    'spotify': r'(?:https?://)?(?:open\.)?spotify\.com',
    'soundcloud': r'(?:https?://)?(?:www\.)?soundcloud\.com',
    'bandcamp': r'(?:https?://)?(?:www\.)?.*\.bandcamp\.com',
    'deezer': r'(?:https?://)?(?:www\.)?deezer\.com'
}

# Initialize Discord bot with required intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Add status variables
bot.uptime = None
bot.reconnect_attempts = 0
MAX_RECONNECT_ATTEMPTS = 5

class MusicControlsView(View):
    def __init__(self, music_player, ctx):
        super().__init__(timeout=None)
        self.music_player = music_player
        self.ctx = ctx
        self.setup_buttons()

    def setup_buttons(self):
        # Pause/Resume Button
        pause_button = Button(style=ButtonStyle.primary, label="⏸️ Pause", custom_id="pause")
        pause_button.callback = self.pause_callback
        self.add_item(pause_button)

        # Skip Button
        skip_button = Button(style=ButtonStyle.primary, label="⏭️ Skip", custom_id="skip")
        skip_button.callback = self.skip_callback
        self.add_item(skip_button)

        # Loop Button
        loop_button = Button(style=ButtonStyle.secondary, label="🔁 Loop", custom_id="loop")
        loop_button.callback = self.loop_callback
        self.add_item(loop_button)

        # Shuffle Button
        shuffle_button = Button(style=ButtonStyle.secondary, label="🔀 Shuffle", custom_id="shuffle")
        shuffle_button.callback = self.shuffle_callback
        self.add_item(shuffle_button)

        # Stop Button
        stop_button = Button(style=ButtonStyle.danger, label="⏹️ Stop", custom_id="stop")
        stop_button.callback = self.stop_callback
        self.add_item(stop_button)

    async def pause_callback(self, interaction: discord.Interaction):
        if interaction.user.voice and interaction.user.voice.channel == self.ctx.voice_client.channel:
            if self.ctx.voice_client.is_playing():
                self.ctx.voice_client.pause()
                await interaction.response.send_message("⏸️ Paused", ephemeral=True)
                # Update button label
                for child in self.children:
                    if child.custom_id == "pause":
                        child.label = "▶️ Resume"
                        break
            else:
                self.ctx.voice_client.resume()
                await interaction.response.send_message("▶️ Resumed", ephemeral=True)
                # Update button label
                for child in self.children:
                    if child.custom_id == "pause":
                        child.label = "⏸️ Pause"
                        break
            await interaction.message.edit(view=self)
        else:
            await interaction.response.send_message("❌ You must be in the same voice channel!", ephemeral=True)

    async def skip_callback(self, interaction: discord.Interaction):
        if interaction.user.voice and interaction.user.voice.channel == self.ctx.voice_client.channel:
            self.ctx.voice_client.stop()
            await interaction.response.send_message("⏭️ Skipped", ephemeral=True)
            await self.music_player.play_next(self.ctx)
        else:
            await interaction.response.send_message("❌ You must be in the same voice channel!", ephemeral=True)

    async def loop_callback(self, interaction: discord.Interaction):
        if interaction.user.voice and interaction.user.voice.channel == self.ctx.voice_client.channel:
            self.music_player.loop = not self.music_player.loop
            status = "enabled" if self.music_player.loop else "disabled"
            await interaction.response.send_message(f"🔁 Loop {status}", ephemeral=True)
            # Update button style
            for child in self.children:
                if child.custom_id == "loop":
                    child.style = ButtonStyle.success if self.music_player.loop else ButtonStyle.secondary
                    break
            await interaction.message.edit(view=self)
        else:
            await interaction.response.send_message("❌ You must be in the same voice channel!", ephemeral=True)

    async def shuffle_callback(self, interaction: discord.Interaction):
        if interaction.user.voice and interaction.user.voice.channel == self.ctx.voice_client.channel:
            if len(self.music_player.queue) > 1:
                current = self.music_player.queue[0]
                remaining = list(self.music_player.queue)[1:]
                random.shuffle(remaining)
                self.music_player.queue.clear()
                self.music_player.queue.append(current)
                self.music_player.queue.extend(remaining)
                await interaction.response.send_message("🔀 Queue shuffled!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Not enough songs in queue to shuffle!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ You must be in the same voice channel!", ephemeral=True)

    async def stop_callback(self, interaction: discord.Interaction):
        if interaction.user.voice and interaction.user.voice.channel == self.ctx.voice_client.channel:
            self.music_player.queue.clear()
            if self.ctx.voice_client:
                await self.ctx.voice_client.disconnect()
            await interaction.response.send_message("⏹️ Stopped and cleared queue", ephemeral=True)
            self.stop()
        else:
            await interaction.response.send_message("❌ You must be in the same voice channel!", ephemeral=True)

# Music player class to handle music functionality
class MusicPlayer:
    def __init__(self):
        self.queue = []
        self.current_message = None
        self.current_view = None
        self.current_song = None
        self.loop = False
        self.spotify = None
        self.voice_client = None

    def detect_platform(self, url):
        """Detect the platform from the URL"""
        for platform, pattern in URL_PATTERNS.items():
            if re.search(pattern, url):
                return platform
        return None

    async def search_youtube(self, query, limit=1):
        """Search YouTube for a query and return top results"""
        try:
            search_query = f"ytsearch{limit}:{query}"
            with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                info = ydl.extract_info(search_query, download=False)
                if not info or 'entries' not in info:
                    return []
                
                results = []
                for entry in info['entries']:
                    if entry:
                        results.append({
                            'title': entry.get('title', 'Unknown Title'),
                            'url': entry.get('webpage_url', None),
                            'duration': str(datetime.timedelta(seconds=entry.get('duration', 0))),
                            'thumbnail': entry.get('thumbnail', None),
                            'channel': entry.get('uploader', 'Unknown')
                        })
                return results
        except Exception as e:
            logger.error(f"Search error: {str(e)}")
            return []

    async def process_url(self, url, ctx):
        """Process URL and add to queue"""
        try:
            # Detect platform
            platform = self.detect_platform(url)
            
            if platform == 'spotify':
                songs = await self.process_spotify(url)
                if not songs:
                    await ctx.send("❌ Could not process Spotify URL")
                    return
                
                for song in songs:
                    # Search for each song on YouTube
                    results = await self.search_youtube(song, limit=1)
                    if results:
                        self.queue.append(results[0])
                    else:
                        await ctx.send(f"⚠️ Could not find: {song}")
                
            else:
                # Direct YouTube/SoundCloud URL or search query
                if not url.startswith(('http://', 'https://')):
                    # It's a search query
                    results = await self.search_youtube(url, limit=1)
                    if not results:
                        await ctx.send("❌ No results found!")
                        return
                    self.queue.append(results[0])
                else:
                    # It's a direct URL
                    try:
                        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                            info = ydl.extract_info(url, download=False)
                            if not info:
                                await ctx.send("❌ Could not process URL")
                                return
                            
                            song_info = {
                                'title': info.get('title', 'Unknown Title'),
                                'url': info.get('webpage_url', url),
                                'duration': str(datetime.timedelta(seconds=info.get('duration', 0))),
                                'thumbnail': info.get('thumbnail', None),
                                'channel': info.get('uploader', 'Unknown'),
                                'platform': info.get('extractor', 'Unknown')
                            }
                            self.queue.append(song_info)
                    except Exception as e:
                        logger.error(f"URL processing error: {str(e)}")
                        await ctx.send(f"❌ Error processing URL: {str(e)}")
                        return

            # Create embed for queue addition
            song_info = self.queue[-1]
            embed = discord.Embed(
                title="Added to Queue",
                description=f"[{song_info['title']}]({song_info['url']})",
                color=discord.Color.green()
            )
            embed.add_field(name="Channel", value=song_info['channel'], inline=True)
            embed.add_field(name="Duration", value=song_info['duration'], inline=True)
            if song_info.get('thumbnail'):
                embed.set_thumbnail(url=song_info['thumbnail'])
            
            await ctx.send(embed=embed)
            
            # Start playing if not already playing
            if not ctx.voice_client.is_playing():
                await self.play_next(ctx)

        except Exception as e:
            logger.error(f"Error in process_url: {str(e)}")
            await ctx.send(f"❌ An error occurred while processing the URL: {str(e)}")

    async def create_source(self, ctx, url):
        """Create an audio source from URL"""
        try:
            with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    raise ValueError("Could not extract audio information")
                
                # Get the direct audio URL
                if 'formats' in info:
                    formats = info['formats']
                    # Try to get best audio-only format
                    audio_formats = [f for f in formats if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
                    if audio_formats:
                        url = audio_formats[0]['url']
                    else:
                        url = info['url']
                else:
                    url = info['url']

                # Create FFmpeg audio source
                return await discord.FFmpegOpusAudio.from_probe(url, **FFMPEG_OPTIONS)
                
        except Exception as e:
            logger.error(f"Error creating audio source: {str(e)}")
            await ctx.send(f"❌ Error creating audio source: {str(e)}")
            return None

    async def play_next(self, ctx):
        """Play the next song in queue"""
        try:
            if not self.queue:
                await ctx.send("Queue is empty!")
                return

            if not ctx.voice_client:
                await ctx.send("❌ Not connected to a voice channel!")
                return

            # Get the next song
            self.current_song = self.queue.pop(0)
            
            # Create audio source
            source = await self.create_source(ctx, self.current_song['url'])
            if not source:
                await self.play_next(ctx)
                return

            # Play the audio
            def after_playing(error):
                if error:
                    logger.error(f"Player error: {error}")
                asyncio.run_coroutine_threadsafe(self.song_finished(ctx, error), bot.loop)

            ctx.voice_client.play(source, after=after_playing)

            # Send now playing embed
            embed = await self.create_now_playing_embed(self.current_song)
            view = await self.create_player_view(ctx)
            if self.current_message:
                try:
                    await self.current_message.delete()
                except:
                    pass
            self.current_message = await ctx.send(embed=embed, view=view)

        except Exception as e:
            logger.error(f"Error in play_next: {str(e)}")
            await ctx.send(f"❌ Error playing next song: {str(e)}")

    async def create_now_playing_embed(self, song_info):
        embed = discord.Embed(
            title="🎵 Now Playing",
            description=f"[{song_info['title']}]({song_info['url']})",
            color=discord.Color.blue()
        )
        embed.add_field(name="Duration", value=song_info['duration'], inline=True)
        embed.add_field(name="Channel", value=song_info['channel'], inline=True)
        if song_info.get('thumbnail'):
            embed.set_thumbnail(url=song_info['thumbnail'])
        embed.set_footer(text="Use the buttons below to control playback!")
        return embed

    async def create_player_view(self, ctx):
        view = MusicControlsView(self, ctx)
        return view

    async def process_spotify(self, url):
        """Process Spotify URLs and convert to YouTube search queries"""
        try:
            # Extract track/playlist/album ID from URL
            if 'track' in url:
                # Extract track name from URL
                track_id = url.split('track/')[1].split('?')[0]
                if self.spotify:
                    track = self.spotify.track(track_id)
                    query = f"{track['name']} {' '.join([artist['name'] for artist in track['artists']])}"
                else:
                    # Fallback: Extract info from webpage
                    response = requests.get(url)
                    # Simple extraction of title from page
                    title = response.text.split('<title>')[1].split('</title>')[0]
                    # Clean up the title (remove "- song by" and "| Spotify")
                    title = title.split(' - song by ')[0].split(' | Spotify')[0]
                    query = title
                return [query]
            elif 'album' in url:
                if not self.spotify:
                    raise Exception("Please provide a direct YouTube link or song name instead of Spotify album URL")
                album = self.spotify.album(url)
                return [f"{track['name']} {' '.join([artist['name'] for artist in track['artists']])}"
                        for track in album['tracks']['items']]
            elif 'playlist' in url:
                if not self.spotify:
                    raise Exception("Please provide a direct YouTube link or song name instead of Spotify playlist URL")
                playlist = self.spotify.playlist(url)
                return [f"{track['track']['name']} {' '.join([artist['name'] for artist in track['track']['artists']])}"
                        for track in playlist['tracks']['items']]
            else:
                raise Exception("Unsupported Spotify URL type. Please provide a track, album, or playlist URL")
        except Exception as e:
            if not self.spotify:
                # If no Spotify credentials, suggest alternative
                return [url.split('track/')[1].split('?')[0].replace('-', ' ')]
            raise Exception(f"Error processing Spotify URL: {str(e)}")

    async def song_finished(self, ctx, error):
        """Handle song finish"""
        try:
            if error:
                logger.error(f"Error playing song: {str(error)}")
                await ctx.send(f"❌ Error playing song: {str(error)}")
            
            if self.loop and self.current_song:
                self.queue.append(self.current_song)
            
            if self.queue:
                await self.play_next(ctx)
            else:
                await ctx.send("Queue finished! Add more songs with !play")
                
        except Exception as e:
            logger.error(f"Error in song_finished: {str(e)}")
            await ctx.send(f"❌ Error handling song finish: {str(e)}")

@bot.command(name='play')
async def play(ctx, *, query):
    """Play a song from URL or search query"""
    try:
        # Check if user is in a voice channel
        if not ctx.author.voice:
            await ctx.send("❌ You must be in a voice channel to use this command!")
            return
            
        # Join voice channel if not already connected
        if not ctx.voice_client:
            await ctx.author.voice.channel.connect()
        elif ctx.voice_client.channel != ctx.author.voice.channel:
            await ctx.voice_client.move_to(ctx.author.voice.channel)

        # Show searching message for queries
        if not query.startswith(('http://', 'https://')):
            await ctx.send(f"🔍 Searching for: {query}")

        # Process the URL or search query
        await music_player.process_url(query, ctx)

    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

# Create music player instance
music_player = MusicPlayer()

# Healthcheck server
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Bot is healthy!")
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        return  # Disable logging for healthcheck requests

def start_healthcheck_server():
    port = int(os.getenv('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    logger.info(f"Starting healthcheck server on port {port}")
    server.serve_forever()

# Start healthcheck server in a separate thread
threading.Thread(target=start_healthcheck_server, daemon=True).start()

@bot.event
async def on_ready():
    """Event handler for when the bot is ready"""
    if not bot.uptime:
        bot.uptime = discord.utils.utcnow()
    
    activity = discord.Activity(
        type=discord.ActivityType.listening,
        name="!play | Music Bot"
    )
    await bot.change_presence(activity=activity)
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} servers')
    print(f'Latency: {round(bot.latency * 1000)}ms')

@bot.event
async def on_disconnect():
    """Handle disconnection events"""
    if bot.reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
        bot.reconnect_attempts += 1
        print(f"Bot disconnected. Attempt {bot.reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS} to reconnect...")
    else:
        print("Maximum reconnection attempts reached. Please check your internet connection and bot token.")

@bot.event
async def on_resumed():
    """Handle successful reconnection"""
    bot.reconnect_attempts = 0
    print("Bot successfully reconnected!")

@bot.event
async def on_error(event, *args, **kwargs):
    """Global error handler"""
    print(f"Error in {event}:")
    import traceback
    traceback.print_exc()

@bot.command(name='status')
async def status(ctx):
    """Check bot status and uptime"""
    if bot.uptime:
        uptime = discord.utils.utcnow() - bot.uptime
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        embed = discord.Embed(
            title="🤖 Bot Status",
            color=discord.Color.green()
        )
        embed.add_field(
            name="Uptime",
            value=f"{days}d {hours}h {minutes}m {seconds}s",
            inline=False
        )
        embed.add_field(
            name="Latency",
            value=f"{round(bot.latency * 1000)}ms",
            inline=False
        )
        embed.add_field(
            name="Servers",
            value=str(len(bot.guilds)),
            inline=False
        )
        await ctx.send(embed=embed)
    else:
        await ctx.send("Bot status information not available.")

@bot.command(name='join')
async def join(ctx):
    """Join the user's voice channel"""
    if not ctx.message.author.voice:
        await ctx.send("You must be in a voice channel to use this command!")
        return
    
    channel = ctx.message.author.voice.channel
    if ctx.voice_client is None:
        music_player.voice_client = await channel.connect()
    else:
        await ctx.voice_client.move_to(channel)
        music_player.voice_client = ctx.voice_client
    
    await ctx.send(f"Joined {channel.name}")

@bot.command(name='pause')
async def pause(ctx):
    """Pause the current song"""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("Paused ⏸️")
    else:
        await ctx.send("Nothing is playing!")

@bot.command(name='resume')
async def resume(ctx):
    """Resume the paused song"""
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("Resumed ▶️")
    else:
        await ctx.send("Nothing is paused!")

@bot.command(name='skip')
async def skip(ctx):
    """Skip the current song"""
    if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
        ctx.voice_client.stop()
        await ctx.send("Skipped ⏭️")
        await music_player.play_next(ctx)
    else:
        await ctx.send("Nothing to skip!")

@bot.command(name='leave')
async def leave(ctx):
    """Leave the voice channel"""
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        music_player.queue.clear()
        music_player.current = None
        music_player.voice_client = None
        await ctx.send("Disconnected 👋")
    else:
        await ctx.send("I'm not in a voice channel!")

@bot.command(name='search')
async def search(ctx, *, query):
    """Search for a song on YouTube"""
    try:
        # Send searching message
        search_msg = await ctx.send(f"🔍 Searching for: `{query}`")
        
        # Get search results
        results = await music_player.search_youtube(query)
        
        if not results:
            await search_msg.delete()
            await ctx.send("❌ No results found!")
            return
        
        # Create embed for search results
        embed = discord.Embed(
            title="🎵 Search Results",
            description="React with numbers to choose a song, or ❌ to cancel.",
            color=discord.Color.blue()
        )
        
        # Store search results for this user
        music_player.search_results[ctx.author.id] = results
        
        # Add results to embed
        for i, result in enumerate(results, 1):
            duration_min, duration_sec = divmod(result['duration'], 60)
            embed.add_field(
                name=f"{i}. {result['title']}",
                value=f"Channel: {result['channel']} | Duration: {duration_min}:{duration_sec:02d}",
                inline=False
            )
        
        # Delete searching message and send results
        await search_msg.delete()
        result_message = await ctx.send(embed=embed)
        
        # Add reaction numbers
        reactions = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '❌']
        for reaction in reactions[:len(results)] + ['❌']:
            await result_message.add_reaction(reaction)
        
        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in reactions
        
        try:
            reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)
            
            if str(reaction.emoji) == '❌':
                await result_message.delete()
                return
            
            # Get selected song index
            selected_index = reactions.index(str(reaction.emoji))
            selected_song = results[selected_index]
            
            # Play the selected song
            await play(ctx, query=selected_song['url'])
            
        except asyncio.TimeoutError:
            await result_message.delete()
            await ctx.send("⏱️ Search timed out!")
        
    except Exception as e:
        await ctx.send(f"❌ Error during search: {str(e)}")

@bot.command(name='nowplaying', aliases=['np'])
async def nowplaying(ctx):
    """Display information about the currently playing song"""
    if not music_player.current:
        await ctx.send("Nothing is playing right now!")
        return
    
    song = music_player.current
    embed = discord.Embed(
        title="Now Playing",
        description=f"[{song['title']}]({song['webpage_url']})",
        color=discord.Color.blue()
    )
    embed.add_field(name="Channel", value=song['channel'], inline=True)
    
    if song['duration']:
        minutes, seconds = divmod(song['duration'], 60)
        embed.add_field(name="Duration", value=f"{minutes}:{seconds:02d}", inline=True)
    
    if song['thumbnail']:
        embed.set_thumbnail(url=song['thumbnail'])
    
    await ctx.send(embed=embed)

@bot.command(name='queue', aliases=['q'])
async def queue(ctx):
    """Display the current music queue"""
    if not music_player.queue and not music_player.current:
        await ctx.send("The queue is empty!")
        return
    
    embed = discord.Embed(
        title="Music Queue",
        color=discord.Color.blue()
    )
    
    if music_player.current:
        embed.add_field(
            name="Now Playing",
            value=f"[{music_player.current['title']}]({music_player.current['webpage_url']})",
            inline=False
        )
    
    if music_player.queue:
        queue_text = ""
        for i, song in enumerate(music_player.queue, 1):
            if i > 10:  # Show only first 10 songs
                queue_text += f"\nAnd {len(music_player.queue) - 10} more songs..."
                break
            queue_text += f"\n{i}. [{song['title']}]({song['webpage_url']})"
        
        embed.add_field(
            name="Up Next",
            value=queue_text if queue_text else "No songs in queue",
            inline=False
        )
    
    await ctx.send(embed=embed)

# Run the bot
bot.run(os.getenv('DISCORD_TOKEN'))
