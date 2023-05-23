"""CogServerStatus.py

Handles tasks related to checking server status and info.
Date: 05/20/2023
Authors: David Wolfe (Red-Thirten)
Licensed under GNU GPLv3 - See LICENSE for more details.
"""

import re
import requests
from datetime import datetime

import discord
from discord.ext import commands, tasks
from bs4 import BeautifulSoup


STATUS_ONLINE_STR = "SERVERS: ONLINE 🟢"
STATUS_LIMITED_STR = "SERVERS: LIMITED 🟡"
STATUS_OFFLINE_STR = "SERVERS: OFFLINE 🔴"
QUERY_ROOT = "https://ps2online.com"
QUERY_GAME = "/oslist.php?game=bfield1942ps2"
# Cells start at 0
USER_ID_CELL = 2
NAME_CELL = 3
MAP_CELL = 4
GAMEMODE_CELL = 5
POPULATION_CELL = 6
VERSION_CELL = 7
ROOM_STATUS_CELL = 13
COUNTRY_CELL = 14
CMD_COOLDOWN = 60 # Seconds


last_known_server_names = []


async def get_live_servers():
    """Get Live Servers
    
    Returns nested list of all live servers and their subsequent statistics.
    Also updates `last_known_server_names`.
    """
    # Send a GET request to the webpage
    response = requests.get(QUERY_ROOT+QUERY_GAME)

    # Parse the HTML content
    soup = BeautifulSoup(response.content, 'lxml') # Use lxml as a more lenient HTML parser, because the site has broken closing tags

    # Find the table containing the data
    table = soup.find('table')

    # Retrieve all rows from the table (except the first header row)
    rows = table.find_all('tr')[1:]

    last_known_server_names.clear()
    servers = []
    # Extract data from each row
    for row in rows:
        # Retrieve all cells in the row
        cells = row.find_all(re.compile('^td')) # "Starts with td" to account for empty servers having extra CSS class in the tag

        data = []
        # Process the data in each cell
        for data_index, cell in enumerate(cells):
            # Extract image URL or text content, whichever is present
            image_tag = cell.find('img')
            if image_tag:
                data.append(image_tag['src'])
            else:
                data.append(cell.get_text())
                # If name cell, add to last known server names
                if data_index == NAME_CELL:
                    last_known_server_names.append(cell.get_text())
        servers.append(data)

    return servers

async def get_last_known_server_names(ctx: discord.AutocompleteContext):
    """Autocomplete Context: Get last known server names
    
    Returns current list of last known server names.
    """
    return last_known_server_names


class CogServerStatus(discord.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.server_status = 0 # 0 = Offline, 1 = Limited, 2 = Online
    

    @commands.Cog.listener()
    async def on_ready(self):
        """Listener: On Cog Ready
        
        Runs when the cog is successfully cached within the Discord API.
        """
        print(f"{self.bot.get_datetime_str()}: [ServerStatus] Successfully cached!")
        
        if not self.StatusLoop.is_running():
            self.StatusLoop.change_interval(minutes=self.bot.config['ServerStatus']['CheckIntervalMinutes'])
            self.StatusLoop.start()
            print(f"{self.bot.get_datetime_str()}: [ServerStatus] StatusLoop started.")
    
    @tasks.loop(minutes=5)
    async def StatusLoop(self):
        """Task Loop: Status Loop
        
        Runs every interval period, checks online server status, and makes appropritate reporting updates.
        """
        #print(f"{self.bot.get_datetime_str()}: [ServerStatus] StatusLoop fired...")
        
        # Get status channel handle
        channel = self.bot.get_channel(self.bot.config['ServerStatus']['ChannelID'])
        # Get number of live servers (also updates last known server names)
        num_servers = len(await get_live_servers())

        # Update status channel name
        # NOTE: Discord limits channel name changes to twice every 10 min
        if num_servers >= self.bot.config['ServerStatus']['OnlineThreshold']:
            self.server_status = 2
            if channel.name != STATUS_ONLINE_STR:
                print(f"{self.bot.get_datetime_str()}: [ServerStatus] {STATUS_ONLINE_STR}")
                await channel.edit(name=STATUS_ONLINE_STR, reason="[BackstabBot] Server status updated.")
        elif num_servers != 0:
            self.server_status = 1
            if channel.name != STATUS_LIMITED_STR:
                print(f"{self.bot.get_datetime_str()}: [ServerStatus] {STATUS_LIMITED_STR}")
                await channel.edit(name=STATUS_LIMITED_STR, reason="[BackstabBot] Server status updated.")
        else:
            self.server_status = 0
            if channel.name != STATUS_OFFLINE_STR:
                print(f"{self.bot.get_datetime_str()}: [ServerStatus] {STATUS_OFFLINE_STR}")
                await channel.edit(name=STATUS_OFFLINE_STR, reason="[BackstabBot] Server status updated.")


    """Slash Command Group: /server
    
    A group of commands related to checking server status and info.
    """
    server = discord.SlashCommandGroup("server", "Commands related to checking official BF2:MC server status and info")
    
    @server.command(name = "status", description="Reports latest status check of official BF2:MC servers")
    async def status(self, ctx):
        """Slash Command: /server status
        
        Reports latest status check of official BF2:MC servers.
        Useful as backup if status channel has hit it's rate limit.
        """
        if self.server_status == 2:
            await ctx.respond(STATUS_ONLINE_STR, ephemeral=True)
        if self.server_status == 1:
            await ctx.respond(STATUS_LIMITED_STR, ephemeral=True)
        if self.server_status == 0:
            await ctx.respond(STATUS_OFFLINE_STR, ephemeral=True)
    
    @server.command(name = "info", description="Displays live info for a chosen server (ie. player count, gamemode, etc.)")
    @commands.cooldown(1, CMD_COOLDOWN, commands.BucketType.channel)
    async def info(
        self, 
        ctx, 
        server_name: discord.Option(
            str, 
            name="server", 
            description="Name of server to get info from", 
            autocomplete=discord.utils.basic_autocomplete(get_last_known_server_names), 
            max_length=255, 
            required=True
        )
    ):
        """Slash Command: /server info
        
        Displays live info for a chosen server (ie. player count, gamemode, etc.).
        """
        await ctx.defer()
        servers = await get_live_servers()

        for server in servers:
            if server[NAME_CELL] == server_name:
                population = [int(x) for x in server[POPULATION_CELL].split('/')]
                if population[0] == 0:
                    color = discord.Colour.yellow()
                elif population[0] == population[1]:
                    color = discord.Colour.red()
                else:
                    color = discord.Colour.green()
                
                if int(server[USER_ID_CELL]) == self.bot.config['ServerStatus']['OfficialID']:
                    description = "Official Server"
                else:
                    description = "Unofficial Server"
                
                
                thumbnail = "https://i.imgur.com/IXdNxnw.png" # Conquest default
                if server[GAMEMODE_CELL] == "Capture The Flag":
                    thumbnail = "https://i.imgur.com/0JaW4NO.png"
                
                _embed = discord.Embed(
                    title=server[NAME_CELL],
                    description=description,
                    color=color
                )
                _embed.set_author(
                    name="BF2:MC Server Info", 
                    icon_url=QUERY_ROOT + server[COUNTRY_CELL]
                )
                _embed.set_thumbnail(url=thumbnail)
                _embed.add_field(name="Players:", value=server[POPULATION_CELL], inline=False)
                _embed.add_field(name="Gamemode:", value=server[GAMEMODE_CELL], inline=True)
                room_status = "Unknown"
                if server[ROOM_STATUS_CELL] == "openplaying":
                    room_status = "Open / Playing"
                _embed.add_field(name="Status:", value=room_status, inline=True)
                _embed.add_field(name="Version:", value=server[VERSION_CELL], inline=True)
                _embed.add_field(name="Current Map:", value="", inline=False)
                _embed.set_image(url=QUERY_ROOT + server[MAP_CELL])
                _embed.set_footer(text=f"Data fetched at {datetime.utcnow().strftime('%I:%M:%S %p UTC')}")
                await ctx.respond(embed=_embed)
                return
        
        await ctx.respond(
            f":warning: A server with the name of \"{server_name}\" could not be found online!\n\n(It either went offline recently, or it's name was misspelled)", 
            ephemeral=True
        )


def setup(bot):
    """Called by Pycord to setup the cog"""
    cog = CogServerStatus(bot)
    cog.guild_ids = [bot.config['GuildID']]
    bot.add_cog(cog)
