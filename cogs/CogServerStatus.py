"""CogServerStatus.py

Handles tasks related to checking server status and info.
Date: 05/25/2023
Authors: David Wolfe (Red-Thirten)
Licensed under GNU GPLv3 - See LICENSE for more details.
"""

import json
import requests
from datetime import datetime

import discord
from discord.ext import commands, tasks
import inflect

API_URL = "https://stats.bf2mc.net/api/servers/"
COUNTRY_FLAGS_URL = "https://stats.bf2mc.net/static/img/flags/<code>.png"
GM_THUMBNAILS_URL = "https://raw.githubusercontent.com/lilkingjr1/backstab-discord-bot/main/assets/gamemode_thumbnails/<gamemode>.png"
MAP_IMAGES_URL = "https://raw.githubusercontent.com/lilkingjr1/backstab-discord-bot/main/assets/map_images/<map_name>.png"
GM_STRINGS = {
    "conquest": "Conquest",
    "capturetheflag": "Capture the Flag"
}
TEAM_STRINGS = {
    "US": ":flag_us:  United States:",
    "CH": ":flag_cn:  China:",
    "ME": ":flag_ir:  Middle Eastern Coalition:",
    "EU": ":flag_eu:  European Union:"
}
STATUS_ONLINE_STR = "SERVERS: ONLINE 🟢"
STATUS_OFFLINE_STR = "SERVERS: OFFLINE 🔴"
STATUS_ERROR_STR = "SERVERS: UNKNOWN"

P = inflect.engine()


async def query_api():
    """Query API
    
    Returns JSON after querying API URL, or None if bad response.
    """
    # Make an HTTP GET request to the API endpoint
    _response = requests.get(API_URL)

    # Check if the request was successful (status code 200 indicates success)
    if _response.status_code == 200:
        # Parse the JSON response
        return _response.json()
    else:
        return None


class CogServerStatus(discord.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.server_data = None
        self.last_query = None
        self.total_online = 0
    

    def get_team_score_str(self, gamemode: str, score: int) -> str:
        if gamemode == "conquest":
            return f"***{P.no('ticket', score)} remaining***"
        else:
            return f"***{P.no('flag', score)} captured***"
    
    def get_player_attr_list_str(self, players, attribute: str) -> str:
        _str = "```\n"
        for _i, _p in enumerate(players):
            if attribute == 'name':
                _str += f"{_i+1}. {_p[attribute]}\n"
            elif attribute == 'score':
                _str += f"  {str(_p[attribute]).rjust(2)} pts\n"
            else:
                _str += f"   {str(_p['deaths']).rjust(2)}\n"
        return _str + "```"
    
    def get_server_stat_embeds(self):
        _embeds = []

        if self.server_data != None:
            if self.server_data['count'] > 0:
                for s in self.server_data['results']:
                    # Get total player count
                    _player_count = len(s['players'])

                    # Setup embed color based on total player count
                    if _player_count == 0:
                        _color = discord.Colour.yellow()
                    elif _player_count == s['max_players']:
                        _color = discord.Colour.red()
                    else:
                        _color = discord.Colour.green()
                    
                    # Check if server is official
                    if s['id'] in self.bot.config['ServerStatus']['OfficialIDs']:
                        _description = "*Official Server*"
                    else:
                        _description = "*Unofficial Server*"
                    
                    # Parse player list into ordered teams
                    _team1 = []
                    _team2 = []
                    for _p in s['players']:
                        if _p['team'] == 0:
                            _team1.append(_p)
                        else:
                            _team2.append(_p)
                    _team1 = sorted(_team1, key=lambda x: x['score'], reverse=True)
                    _team2 = sorted(_team2, key=lambda x: x['score'], reverse=True)
                    
                    # Setup Discord embed
                    _embed = discord.Embed(
                        title=s['server_name'],
                        description=_description,
                        color=_color
                    )
                    _embed.set_author(
                        name="BF2:MC Server Info", 
                        icon_url=COUNTRY_FLAGS_URL.replace("<code>", s['country'].lower())
                    )
                    _embed.set_thumbnail(url=GM_THUMBNAILS_URL.replace("<gamemode>", s['game_type']))
                    _embed.add_field(name="Players:", value=f"{_player_count}/{s['max_players']}", inline=False)
                    _embed.add_field(name="Gamemode:", value=GM_STRINGS[s['game_type']], inline=True)
                    _embed.add_field(name="Time Elapsed:", value=s['time_elapsed'][3:], inline=True)
                    _embed.add_field(name="Time Limit:", value=s['time_limit'][3:], inline=True)
                    _embed.add_field(
                        name=TEAM_STRINGS[s['team1_country']], 
                        value=self.get_team_score_str(s['game_type'], s['team1_score']), 
                        inline=False
                    )
                    _embed.add_field(name="Player:", value=self.get_player_attr_list_str(_team1, 'name'), inline=True)
                    _embed.add_field(name="Score:", value=self.get_player_attr_list_str(_team1, 'score'), inline=True)
                    _embed.add_field(name="Deaths:", value=self.get_player_attr_list_str(_team1, 'deaths'), inline=True)
                    _embed.add_field(
                        name=TEAM_STRINGS[s['team2_country']], 
                        value=self.get_team_score_str(s['game_type'], s['team2_score']), 
                        inline=False
                    )
                    _embed.add_field(name="Player:", value=self.get_player_attr_list_str(_team2, 'name'), inline=True)
                    _embed.add_field(name="Score:", value=self.get_player_attr_list_str(_team2, 'score'), inline=True)
                    _embed.add_field(name="Deaths:", value=self.get_player_attr_list_str(_team2, 'deaths'), inline=True)
                    _embed.set_image(url=MAP_IMAGES_URL.replace("<map_name>", s['map_name']))
                    _embed.set_footer(text=f"Data fetched at: {self.last_query.strftime('%I:%M:%S %p UTC')}")
                    _embeds.append(_embed)
            else:
                _description = f"""
                There are no BF2:MC servers currently online :cry:
                Please check <#{self.bot.config['ServerStatus']['AnnouncementTextChannelID']}> for more info.
                """
                _embed = discord.Embed(
                    title=":red_circle:  Servers Offline",
                    description=_description,
                    color=discord.Colour.red()
                )
                _embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/8/8d/Computer_crash.svg/1200px-Computer_crash.svg.png")
                _embed.set_footer(text=f"Data fetched at: {self.last_query.strftime('%I:%M:%S %p UTC')}")
                _embeds.append(_embed)
        else:
            _description = """
            *The server stats API endpoint is currently down.*

            **BF2:MC servers may still be online.**
            **We just can't display any stats at this time.**

            """
            _embed = discord.Embed(
                    title=":yellow_circle:  Server Stats Unavailable",
                    description=_description,
                    color=discord.Colour.yellow()
                )
            _embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/8/8d/Computer_crash.svg/1200px-Computer_crash.svg.png")
            _embed.set_footer(text=f"Data fetched at: {self.last_query.strftime('%I:%M:%S %p UTC')}")
            _embeds.append(_embed)
        
        return _embeds
    

    @commands.Cog.listener()
    async def on_ready(self):
        """Listener: On Cog Ready
        
        Runs when the cog is successfully cached within the Discord API.
        """
        print(f"{self.bot.get_datetime_str()}: [ServerStatus] Successfully cached!")
        
        # Check that all channels in the config are valid
        _cfg_keys = [
            'StatusVoiceChannelID',
            'StatsTextChannelID',
            'AnnouncementTextChannelID'
        ]
        for _key in _cfg_keys:
            _channel_id = self.bot.config['ServerStatus'][_key]
            if self.bot.get_channel(_channel_id) == None:
                print(f"ERROR: [Config] Could not find valid channel with ID: {_channel_id}")
                await self.bot.close()
        
        # Start Status Loop
        if not self.StatusLoop.is_running():
            _config_interval = self.bot.config['ServerStatus']['UpdateIntervalMinutes']
            self.StatusLoop.change_interval(minutes=_config_interval)
            self.StatusLoop.start()
            print(f"{self.bot.get_datetime_str()}: [ServerStatus] StatusLoop started ({_config_interval} min. interval).")

        # Set stats channel description
        _text_channel = self.bot.get_channel(self.bot.config['ServerStatus']['StatsTextChannelID'])
        await _text_channel.edit(topic=f"Live server statistics (Updated every {P.no('second', round(_config_interval*60))})")
    

    @tasks.loop(minutes=5)
    async def StatusLoop(self):
        """Task Loop: Status Loop
        
        Runs every interval period, queries API, updates status voice channel, and updates info text channel.
        """
        # Query API for data
        print(f"{self.bot.get_datetime_str()}: [ServerStatus] Querying stats... ", end='')
        self.server_data = await query_api()
        self.last_query = datetime.utcnow()

        # Calculate total players online
        _total_online = 0
        for _s in self.server_data['results']:
            for _ in _s['players']:
                _total_online += 1
        
        ## Update bot's activity if total players has changed
        if _total_online != self.total_online:
            self.total_online = _total_online
            _activity = discord.Activity(type=discord.ActivityType.watching, name=f"{_total_online} Veterans online")
            await self.bot.change_presence(activity=_activity)

        ## Update status channel name
        # NOTE: Discord limits channel name changes to twice every 10 min
        _voice_channel = self.bot.get_channel(self.bot.config['ServerStatus']['StatusVoiceChannelID'])
        if self.server_data == None:
            if _voice_channel.name != STATUS_ERROR_STR:
                print(f"{self.bot.get_datetime_str()}: [ServerStatus] {STATUS_ERROR_STR}")
                await _voice_channel.edit(name=STATUS_ERROR_STR, reason="[BackstabBot] Server status updated.")
        elif self.server_data['count'] > 0:
            if _voice_channel.name != STATUS_ONLINE_STR:
                print(f"{self.bot.get_datetime_str()}: [ServerStatus] {STATUS_ONLINE_STR}")
                await _voice_channel.edit(name=STATUS_ONLINE_STR, reason="[BackstabBot] Server status updated.")
        else:
            if _voice_channel.name != STATUS_OFFLINE_STR:
                print(f"{self.bot.get_datetime_str()}: [ServerStatus] {STATUS_OFFLINE_STR}")
                await _voice_channel.edit(name=STATUS_OFFLINE_STR, reason="[BackstabBot] Server status updated.")

        ## Update stats channel post
        _text_channel = self.bot.get_channel(self.bot.config['ServerStatus']['StatsTextChannelID'])
        _last_message = None
        # Fetch the message history of the channel
        async for _m in _text_channel.history(limit=3):
            # Check if the message was sent by the user
            if _m.author == self.bot.user:
                _last_message = await _text_channel.fetch_message(_m.id)
                break
        if _last_message != None:
            await _last_message.edit(f"## Total Players: {self.total_online}", embeds=self.get_server_stat_embeds())
        else:
            await _text_channel.send(f"## Total Players: {self.total_online}", embeds=self.get_server_stat_embeds())
        
        ## Update interval if it differs from config & update channel description
        _config_interval = self.bot.config['ServerStatus']['UpdateIntervalMinutes']
        if self.StatusLoop.minutes != _config_interval:
            await _text_channel.edit(topic=f"Live server statistics (Updated every {P.no('second', round(_config_interval*60))})")
            self.StatusLoop.change_interval(minutes=_config_interval)
            print(f"{self.bot.get_datetime_str()}: [ServerStatus] Changed loop interval to {self.StatusLoop.minutes} min.")
        
        print("Done.")


    """Slash Command Group: /server
    
    A group of commands related to checking server status and info.
    """
    server = discord.SlashCommandGroup("server", "Commands related to checking official BF2:MC server status and info")
    
    @server.command(name = "count", description="Reports number of live BF2:MC servers")
    async def count(self, ctx):
        """Slash Command: /server count
        
        Reports number of live BF2:MC servers (since last status check).
        Useful as backup if status channel has hit it's rate limit.
        """
        if self.server_data != None:
            await ctx.respond(f"Number of live BF2:MC servers: {self.server_data['count']}", ephemeral=True)
        else:
            raise commands.CommandError("There was an error retrieving this data. The statistics API may be down at the moment.")


def setup(bot):
    """Called by Pycord to setup the cog"""
    cog = CogServerStatus(bot)
    cog.guild_ids = [bot.config['GuildID']]
    bot.add_cog(cog)
