"""CogServerStats.py

Handles tasks related to checking server stats and info.
Date: 01/12/2024
Authors: David Wolfe (Red-Thirten)
Licensed under GNU GPLv3 - See LICENSE for more details.
"""

import discord
from discord.ext import commands
import common.CommonStrings as CS

STATS_EPOCH_DATE_STR = "Oct. 20, 2023"


class CogServerStats(discord.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.Cog.listener()
    async def on_ready(self):
        """Listener: On Cog Ready
        
        Runs when the cog is successfully cached within the Discord API.
        """
        self.bot.log("[ServerStats] Successfully cached!")


    """Slash Command Group: /mostplayed
    
    A group of commands related to checking "most played" stats.
    """
    mostplayed = discord.SlashCommandGroup("mostplayed", 'Commands related to checking "most played" related stats')

    @mostplayed.command(name = "map", description="See which maps have been played the most for a given gamemode")
    @commands.cooldown(2, 180, commands.BucketType.channel)
    async def map(
        self, 
        ctx, 
        gamemode: discord.Option(
            str, 
            description="Which gamemode to see the most played maps for", 
            choices=["Conquest", "Capture the Flag"], 
            required=True
        )
    ):
        """Slash Command: /mostplayed map
        
        Displays which maps have been played the most for a given gamemode.
        Excludes games recorded in the DB with less than the configured `MatchMinPlayers`.
        """
        # Determine gametype ID
        _gt_id = 1
        if gamemode == "Capture the Flag":
            _gt_id = 2
        
        # Get all games for that gametype
        _games = self.bot.db_backend.getAll(
            "GameStats", 
            ["mapid"], 
            (
                "gametype = %s and numplayers >= %s",
                [_gt_id, self.bot.config['PlayerStats']['MatchMinPlayers']]
            )
        )
        if _games == None:
            return await ctx.respond(f":warning: No data for {gamemode} yet. Please try again later.", ephemeral=True)
        
        # Create a dictionary to count the occurrences of each 'mapid'
        _mapid_counts = {}
        for _g in _games:
            _mapid_counts[_g['mapid']] = _mapid_counts.get(_g['mapid'], 0) + 1

        # Sort the 'mapid' counts in descending order
        _sorted_mapid_counts = sorted(_mapid_counts.items(), key=lambda x: x[1], reverse=True)

        # Limit to the top 5 most occurring 'mapid' values and their counts
        _sorted_mapid_counts = _sorted_mapid_counts[:5]
        
        _maps = "```\n"
        _games = "```\n"
        for _i, _map_data in enumerate(_sorted_mapid_counts):
            _maps += f"{_i+1}. {CS.MAP_STRINGS[_map_data[0]]}\n"
            _games += f"{self.bot.infl.no('game', _map_data[1]).rjust(11)}\n"
        _maps += "```"
        _games += "```"
        _url_map_name = CS.MAP_STRINGS[_sorted_mapid_counts[0][0]].lower().replace(" ", "")
        _embed = discord.Embed(
            title=f"🗺  Most Played *{gamemode}* Maps",
            description=f"*Currently, the most played {gamemode} maps are...*",
            color=discord.Colour.dark_blue()
        )
        _embed.add_field(name="Map:", value=_maps, inline=True)
        _embed.add_field(name="Games Played:", value=_games, inline=True)
        _embed.add_field(name="Most Played Map:", value="", inline=False)
        _embed.set_image(url=CS.MAP_IMAGES_URL.replace("<map_name>", _url_map_name))
        _embed.set_footer(text="BFMCspy Official Stats")
        await ctx.respond(embed=_embed)

    """Slash Command Group: /total
    
    A group of commands related to checking "total count" stats.
    """
    total = discord.SlashCommandGroup("total", 'Commands related to checking "total count" related stats')
    
    @total.command(name = "playercount", description="Displays the total count of unique registered players")
    @commands.cooldown(1, 60, commands.BucketType.channel)
    async def playercount(self, ctx):
        """Slash Command: /total playercount
        
        Displays the total count of unique registered players by IP address.
        """
        _dbResult = self.bot.db_backend.call(
            "queryPlayerCount",
            [True]
        )
        
        _embed = discord.Embed(
            title=f"👥︎  Total Player Count",
            description=f"There are currently **{_dbResult[0][0]:,}** uniquely registered players",
            color=discord.Colour.dark_blue()
        )
        _embed.set_footer(text="BFMCspy Official Stats")
        await ctx.respond(embed=_embed)
    
    @total.command(name = "games", description="Displays the total number of games played across all servers")
    @commands.cooldown(3, 180, commands.BucketType.channel)
    async def games(
        self, 
        ctx, 
        clan_games_filter: discord.Option(
            int, 
            name="game_types",
            description="Which types of games to count", 
            choices=[
                discord.OptionChoice("Only public games", value=0), 
                discord.OptionChoice("Only clan games", value=1),
                discord.OptionChoice("Both public & clan games", value=2)
            ],
            default=2
        )
    ):
        """Slash Command: /total games
        
        Displays the total number of games played across all servers.
        Option option to restrict to just public or clan games.
        """
        if clan_games_filter == 0:
            _filter = "Public"
            _db_condition = "clanid_t0 = 0 and clanid_t1 = 0 and numplayers >= %s"
        elif clan_games_filter == 1:
            _filter = "Clan"
            _db_condition = "clanid_t0 <> 0 and clanid_t1 <> 0 and numplayers >= %s"
        else:
            _filter = "Public & Clan"
            _db_condition = "numplayers >= %s"

        _dbResults = self.bot.db_backend.getAll(
            "GameStats", 
            ["id"], 
            (
                _db_condition, 
                [self.bot.config['PlayerStats']['MatchMinPlayers']]
            )
        )
        
        _embed = discord.Embed(
            title=f"🎮  Total Games ({_filter})",
            description=f"**{len(_dbResults):,}** unique games have been played across all servers since {STATS_EPOCH_DATE_STR}",
            color=discord.Colour.dark_blue()
        )
        _embed.set_footer(text="BFMCspy Official Stats")
        await ctx.respond(embed=_embed)
    
    @total.command(name = "kills", description="Displays the total number of kills across all players")
    @commands.cooldown(1, 180, commands.BucketType.channel)
    async def kills(self, ctx):
        """Slash Command: /total kills
        
        Displays the total number of kills across all players.
        """
        _dbResults = self.bot.db_backend.getAll(
            "PlayerStats", 
            ["kills"]
        )
        
        _total_kills = 0
        for _p in _dbResults:
            _total_kills += _p['kills']

        _embed = discord.Embed(
            title=f"💀  Total Player Kills",
            description=f"All players have fragged a total of **{_total_kills:,}** enemies since {STATS_EPOCH_DATE_STR}",
            color=discord.Colour.dark_blue()
        )
        _embed.set_footer(text="BFMCspy Official Stats")
        await ctx.respond(embed=_embed)
    
    @total.command(name = "vehicles", description="Displays the total number of vehicles destroyed across all players")
    @commands.cooldown(1, 180, commands.BucketType.channel)
    async def vehicles(self, ctx):
        """Slash Command: /total vehicles
        
        Displays the total number of vehicles destroyed across all players.
        """
        _dbResults = self.bot.db_backend.getAll(
            "PlayerStats", 
            ["vehicles"]
        )
        
        _total_vehicles = 0
        for _p in _dbResults:
            _total_vehicles += _p['vehicles']

        _embed = discord.Embed(
            title=f"🚙  Total Vehicles Destroyed",
            description=f"All players have destroyed a total of **{_total_vehicles:,}** vehicles since {STATS_EPOCH_DATE_STR}",
            color=discord.Colour.dark_blue()
        )
        _embed.set_footer(text="BFMCspy Official Stats")
        await ctx.respond(embed=_embed)


def setup(bot):
    """Called by Pycord to setup the cog"""
    cog = CogServerStats(bot)
    cog.guild_ids = [bot.config['GuildID']]
    bot.add_cog(cog)
