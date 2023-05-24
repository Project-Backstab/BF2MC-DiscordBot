"""CogServerStatus.py

Handles tasks related to checking server status and info.
Date: 05/23/2023
Authors: David Wolfe (Red-Thirten)
Licensed under GNU GPLv3 - See LICENSE for more details.
"""

import requests
from datetime import datetime

import discord
from discord.ext import commands, tasks

API_URL = "https://stats.bf2mc.net/api/servers/"
COUNTRY_FLAGS_URL = "https://stats.bf2mc.net/static/img/flags/<code>.png"
GM_THUMBNAILS_URL = "https://github.com/lilkingjr1/backstab-discord-bot/tree/dev/assets/gamemode_thumbnails/<gamemode>.png"
MAP_IMAGES_URL = "https://github.com/lilkingjr1/backstab-discord-bot/tree/dev/assets/map_images/<map_name>.png"
GM_STRINGS = {
    "conquest": "Conquest",
    "capturetheflag": "Capture the Flag"
}
STATUS_ONLINE_STR = "SERVERS: ONLINE 🟢"
STATUS_OFFLINE_STR = "SERVERS: OFFLINE 🔴"
STATUS_ERROR_STR = "SERVERS: UNKNOWN"


async def query_api():
    """Query API
    
    TODO
    """
    # Make an HTTP GET request to the API endpoint
    _response = requests.get(API_URL)

    # Check if the request was successful (status code 200 indicates success)
    if _response.status_code == 200:
        # Parse the JSON response
        return _response.json()
    else:
        return None


# async def get_last_known_server_names(ctx: discord.AutocompleteContext):
#     """Autocomplete Context: Get last known server names
    
#     Returns current list of last known server names.
#     """
#     return last_known_server_names


class CogServerStatus(discord.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.server_data = None
    

    def get_server_stat_embeds(self):
        _embeds = []

        if self.server_data != None:
            if self.server_data['count'] > 0:
                for s in self.server_data['results']:
                    _player_count = len(s['players'])

                    if _player_count == 0:
                        _color = discord.Colour.yellow()
                    elif _player_count == s['max_players']:
                        _color = discord.Colour.red()
                    else:
                        _color = discord.Colour.green()
                    
                    if s['id'] in self.bot.config['ServerStatus']['OfficialIDs']:
                        _description = "Official Server"
                    else:
                        _description = "Unofficial Server"
                    
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
                    _embed.add_field(name="Time Elapsed:", value=s['time_elapsed'], inline=True)
                    _embed.add_field(name="Time Limit:", value=s['time_limit'], inline=True)
                    _embed.add_field(name="Current Map:", value="", inline=False)
                    _embed.set_image(url=MAP_IMAGES_URL.replace("<map_name>", s['map_name']))
                    _embed.set_footer(text=f"Data fetched at {datetime.utcnow().strftime('%I:%M:%S %p UTC')}")
                    _embeds.append(_embed)
            else:
                _embed = discord.Embed(
                    title="No servers",
                    description="todo",
                    color=discord.Colour.yellow()
                )
            _embeds.append(_embed)
        else:
            _embed = discord.Embed(
                    title="API ERROR",
                    description="todo",
                    color=discord.Colour.red()
                )
            _embeds.append(_embed)
        
        return _embeds
    

    @commands.Cog.listener()
    async def on_ready(self):
        """Listener: On Cog Ready
        
        Runs when the cog is successfully cached within the Discord API.
        """
        print(f"{self.bot.get_datetime_str()}: [ServerStatus] Successfully cached!")
        
        # Start Status Loop
        if not self.StatusLoop.is_running():
            self.StatusLoop.change_interval(
                minutes=self.bot.config['ServerStatus']['UpdateIntervalMinutes']
            )
            self.StatusLoop.start()
            print(f"{self.bot.get_datetime_str()}: [ServerStatus] StatusLoop started.")
    

    @tasks.loop(minutes=5)
    async def StatusLoop(self):
        """Task Loop: Status Loop
        
        Runs every interval period, queries API, updates status voice channel, and updates info text channel.
        """
        #print(f"{self.bot.get_datetime_str()}: [ServerStatus] StatusLoop fired...")
        
        # Get status channel handle
        _channel = self.bot.get_channel(self.bot.config['ServerStatus']['VoiceChannelID'])
        # Query API for data
        _data = await query_api()
        self.server_data = _data

        # Update status channel name
        # NOTE: Discord limits channel name changes to twice every 10 min
        if _data == None:
            if _channel.name != STATUS_ERROR_STR:
                print(f"{self.bot.get_datetime_str()}: [ServerStatus] {STATUS_ERROR_STR}")
                await _channel.edit(name=STATUS_ERROR_STR, reason="[BackstabBot] Server status updated.")
        elif _data['count'] > 0:
            if _channel.name != STATUS_ONLINE_STR:
                print(f"{self.bot.get_datetime_str()}: [ServerStatus] {STATUS_ONLINE_STR}")
                await _channel.edit(name=STATUS_ONLINE_STR, reason="[BackstabBot] Server status updated.")
        else:
            if _channel.name != STATUS_OFFLINE_STR:
                print(f"{self.bot.get_datetime_str()}: [ServerStatus] {STATUS_OFFLINE_STR}")
                await _channel.edit(name=STATUS_OFFLINE_STR, reason="[BackstabBot] Server status updated.")


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
    
    @server.command(name = "info", description="Displays live info for a chosen server (ie. player count, gamemode, etc.)")
    #@commands.cooldown(1, CMD_COOLDOWN, commands.BucketType.channel)
    async def info(
        self, 
        ctx
    ):
        """Slash Command: /server info
        
        Displays live info for a chosen server (ie. player count, gamemode, etc.).
        """
        await ctx.respond(embeds=self.get_server_stat_embeds())
        # await ctx.defer()
        # servers = await get_live_servers()

        # for server in servers:
        #     if server[NAME_CELL] == server_name:
        #         population = [int(x) for x in server[POPULATION_CELL].split('/')]
        #         if population[0] == 0:
        #             color = discord.Colour.yellow()
        #         elif population[0] == population[1]:
        #             color = discord.Colour.red()
        #         else:
        #             color = discord.Colour.green()
                
        #         if int(server[USER_ID_CELL]) == self.bot.config['ServerStatus']['OfficialID']:
        #             description = "Official Server"
        #         else:
        #             description = "Unofficial Server"
                
                
        #         thumbnail = "https://i.imgur.com/IXdNxnw.png" # Conquest default
        #         if server[GAMEMODE_CELL] == "Capture The Flag":
        #             thumbnail = "https://i.imgur.com/0JaW4NO.png"
                
        #         _embed = discord.Embed(
        #             title=server[NAME_CELL],
        #             description=description,
        #             color=color
        #         )
        #         _embed.set_author(
        #             name="BF2:MC Server Info", 
        #             icon_url=QUERY_ROOT + server[COUNTRY_CELL]
        #         )
        #         _embed.set_thumbnail(url=thumbnail)
        #         _embed.add_field(name="Players:", value=server[POPULATION_CELL], inline=False)
        #         _embed.add_field(name="Gamemode:", value=server[GAMEMODE_CELL], inline=True)
        #         room_status = "Unknown"
        #         if server[ROOM_STATUS_CELL] == "openplaying":
        #             room_status = "Open / Playing"
        #         _embed.add_field(name="Status:", value=room_status, inline=True)
        #         _embed.add_field(name="Version:", value=server[VERSION_CELL], inline=True)
        #         _embed.add_field(name="Current Map:", value="", inline=False)
        #         _embed.set_image(url=QUERY_ROOT + server[MAP_CELL])
        #         _embed.set_footer(text=f"Data fetched at {datetime.utcnow().strftime('%I:%M:%S %p UTC')}")
        #         await ctx.respond(embed=_embed)
        #         return
        
        # await ctx.respond(
        #     f":warning: A server with the name of \"{server_name}\" could not be found online!\n\n(It either went offline recently, or it's name was misspelled)", 
        #     ephemeral=True
        # )


def setup(bot):
    """Called by Pycord to setup the cog"""
    cog = CogServerStatus(bot)
    cog.guild_ids = [bot.config['GuildID']]
    bot.add_cog(cog)
