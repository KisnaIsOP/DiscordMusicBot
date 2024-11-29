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

# Load environment variables
load_dotenv()

# Configure YT-DLP with support for multiple platforms
YTDLP_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,  # Allow playlist support
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    # Add support for more platforms
    'extractors': ['youtube', 'soundcloud', 'bandcamp', 'spotify', 'deezer'],
    'extractor_args': {
        'youtube': {
            'skip_dash_manifest': True,
            'nocheckcertificate': True
        }
    }
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

# Configure FFMPEG options
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

# Initialize bot with command prefix and required intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True  # Required for voice channel events
bot = commands.Bot(command_prefix='!', intents=intents)

# Add status variables
bot.uptime = None
bot.reconnect_attempts = 0
MAX_RECONNECT_ATTEMPTS = 5

# Music player class to handle music functionality
class MusicPlayer:
    def __init__(self):
        self.queue = deque()
        self.current = None
        self.voice_client = None
        self.yt_dlp = yt_dlp.YoutubeDL(YTDLP_OPTIONS)
        self.search_results = {}
        # Initialize Spotify client if credentials are available
        if SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET:
            self.spotify = spotipy.Spotify(
                client_credentials_manager=SpotifyClientCredentials(
                    client_id=SPOTIFY_CLIENT_ID,
                    client_secret=SPOTIFY_CLIENT_SECRET
                )
            )
        else:
            self.spotify = None

    def detect_platform(self, url):
        """Detect the platform from the URL"""
        for platform, pattern in URL_PATTERNS.items():
            if re.search(pattern, url):
                return platform
        return None

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

    async def add_to_queue(self, url, search=False):
        """Add a song to the queue with multi-platform support"""
        try:
            platform = self.detect_platform(url) if not search else None
            queries = []

            if platform == 'spotify':
                # Convert Spotify URL to YouTube search queries
                queries = await self.process_spotify(url)
            else:
                queries = [url]

            added_songs = []
            for query in queries:
                loop = asyncio.get_event_loop()
                if search or platform == 'spotify':
                    # Search on YouTube
                    results = await self.search_youtube(query, limit=1)
                    if not results:
                        continue
                    data = await loop.run_in_executor(None, lambda: self.yt_dlp.extract_info(results[0]['url'], download=False))
                else:
                    # Direct URL from supported platform
                    data = await loop.run_in_executor(None, lambda: self.yt_dlp.extract_info(query, download=False))

                if 'entries' in data:
                    # Playlist
                    for entry in data['entries']:
                        if entry:
                            song_info = self._create_song_info(entry)
                            self.queue.append(song_info)
                            added_songs.append(song_info)
                else:
                    # Single track
                    song_info = self._create_song_info(data)
                    self.queue.append(song_info)
                    added_songs.append(song_info)

            return added_songs
        except Exception as e:
            raise Exception(f"An error occurred while processing the URL: {str(e)}")

    def _create_song_info(self, data):
        """Create song info dictionary from data"""
        return {
            'url': data['url'],
            'title': data['title'],
            'webpage_url': data.get('webpage_url', data['url']),
            'duration': data.get('duration', 0),
            'thumbnail': data.get('thumbnail', None),
            'channel': data.get('uploader', 'Unknown'),
            'platform': data.get('extractor', 'Unknown')
        }

    async def play_next(self):
        """Play the next song in the queue"""
        if self.queue and self.voice_client:
            if not self.voice_client.is_playing():
                self.current = self.queue.popleft()
                self.voice_client.play(
                    discord.FFmpegPCMAudio(self.current['url'], **FFMPEG_OPTIONS),
                    after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(), bot.loop)
                )
                return self.current['title']
        return None

    async def search_youtube(self, query, limit=5):
        """Search YouTube for a query and return top results"""
        try:
            # Prepare search query
            search_query = f"ytsearch{limit}:{query}"
            
            # Get search results
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: self.yt_dlp.extract_info(search_query, download=False))
            
            if 'entries' not in data:
                return []

            results = []
            for entry in data['entries']:
                if entry:
                    results.append({
                        'title': entry.get('title', 'N/A'),
                        'url': entry.get('webpage_url', None),
                        'duration': entry.get('duration', 0),
                        'channel': entry.get('uploader', 'N/A')
                    })
            return results
        except Exception as e:
            print(f"Error searching YouTube: {e}")
            return []

# Create music player instance
music_player = MusicPlayer()

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

@bot.command(name='play')
async def play(ctx, *, query):
    """Play a song from YouTube URL or search query"""
    if not ctx.voice_client:
        await join(ctx)
    
    try:
        # Check if the query is a URL
        is_url = query.startswith(('http://', 'https://', 'www.'))
        
        # Send a "Searching..." message for non-URL queries
        if not is_url:
            search_msg = await ctx.send(f"🔍 Searching for: `{query}`")
        
        # Add to queue (with search if it's not a URL)
        song_info = await music_player.add_to_queue(query, search=not is_url)
        
        # Delete the searching message if it exists
        if not is_url:
            await search_msg.delete()
        
        # Create an embed for the song
        embed = discord.Embed(
            title="Added to Queue",
            description=f"[{song_info[0]['title']}]({song_info[0]['webpage_url']})",
            color=discord.Color.green()
        )
        embed.add_field(name="Channel", value=song_info[0]['channel'], inline=True)
        
        # Add duration field if available
        if song_info[0]['duration']:
            minutes, seconds = divmod(song_info[0]['duration'], 60)
            embed.add_field(name="Duration", value=f"{minutes}:{seconds:02d}", inline=True)
        
        # Add thumbnail if available
        if song_info[0]['thumbnail']:
            embed.set_thumbnail(url=song_info[0]['thumbnail'])
        
        await ctx.send(embed=embed)
        
        # Start playing if not already playing
        if not ctx.voice_client.is_playing():
            current_song = await music_player.play_next()
            if current_song:
                await ctx.send(f"🎵 Now playing: **{current_song}**")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

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
        current_song = await music_player.play_next()
        if current_song:
            await ctx.send(f"Now playing: {current_song}")
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
