"""CogPlayerStats.py

Handles tasks related to checking player stats and info.
Date: 06/11/2023
Authors: David Wolfe (Red-Thirten)
Licensed under GNU GPLv3 - See LICENSE for more details.
"""

from datetime import datetime

import discord
from discord.ext import commands, tasks
from discord.ext.pages import Paginator, Page
import common.CommonStrings as CS


DEL_STATS_SAVED_MSG_SEC = 60


async def get_player_nicknames(ctx: discord.AutocompleteContext):
    """Autocomplete Context: Get player nicknames
    
    Returns array of all player nicknames in the bot's database.
    """
    _dbEntries = ctx.bot.db.getAll(
        "player_stats", 
        ["nickname"]
    )
    if _dbEntries:
        return [player['nickname'] for player in _dbEntries]
    else:
        return []


class CogPlayerStats(discord.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.game_over_ids = []
        #self.bot.db.query("DROP TABLE player_stats") # DEBUGGING
        self.bot.db.query(
            "CREATE TABLE IF NOT EXISTS player_stats ("
                "id INT AUTO_INCREMENT PRIMARY KEY, "
                "nickname TINYTEXT NOT NULL, "
                "first_seen DATE NOT NULL, "
                "score INT NOT NULL, "
                "deaths INT NOT NULL, "
                "us_games INT NOT NULL, "
                "ch_games INT NOT NULL, "
                "ac_games INT NOT NULL, "
                "eu_games INT NOT NULL, "
                "cq_games INT NOT NULL, "
                "cf_games INT NOT NULL, "
                "wins INT NOT NULL, "
                "losses INT NOT NULL, "
                "top_player INT NOT NULL"
            ")"
        )
    
    def split_list(self, lst: list, chunk_size: int) -> list[list]:
        """Split a list into smaller lists of equal size"""
        if chunk_size <= 0:
            return [lst]
        else:
            num_chunks = len(lst) // chunk_size
            remainder = len(lst) % chunk_size
            result = [lst[i*chunk_size:(i+1)*chunk_size] for i in range(num_chunks)]
            if remainder:
                result.append(lst[-remainder:])
            return result
    
    def time_to_sec(self, time: str) -> int:
        """Turns a time string into seconds as an integer"""
        hours, minutes, seconds = time.split(':')
        return int(hours) * 3600 + int(minutes) * 60 + int(seconds)
    
    async def record_player_stats(self, server_data: dict) -> str:
        """Record Player Statistics
        
        Additively records player statistics to the database given a server's JSON data.
        New records are created for first-seen players.
        Returns nickname string of the top player.
        """
        print(f"Recording round stats... ", end='')

        # Sanitize input (because I'm paranoid)
        if server_data == None or len(server_data['players']) < 2:
            return None
        
        # Calculate top player
        _top_player = None
        for _p in server_data['players']:
            if (_top_player == None
                or _p['score'] > _top_player['score']
                or (_p['score'] == _top_player['score'] and _p['deaths'] < _top_player['deaths'])):
                _top_player = _p
        _top_player = _top_player['name']

        # Calculate and record stats for each player in game
        for _p in server_data['players']:
            _dbEntry = self.bot.db.getOne(
                "player_stats", 
                [
                    "id",
                    "score",
                    "deaths",
                    "us_games",
                    "ch_games",
                    "ac_games",
                    "eu_games",
                    "cq_games",
                    "cf_games",
                    "wins",
                    "losses",
                    "top_player"
                ], 
                ("nickname=%s", [_p['name']])
            )
            
            # Sum round stats with existing player stats
            if _dbEntry == None:
                _summed_stats = {
                    "score": 0,
                    "deaths": 0,
                    "us_games": 0,
                    "ch_games": 0,
                    "ac_games": 0,
                    "eu_games": 0,
                    "cq_games": 0,
                    "cf_games": 0,
                    "wins": 0,
                    "losses": 0,
                    "top_player": 0
                }
            else:
                _summed_stats = _dbEntry.copy()
            # Add scores and deaths
            _summed_stats['score'] += _p['score']
            _summed_stats['deaths'] += _p['deaths']
            # Detect player's team and if that team won or lost (draws are omitted)
            if _p['team'] == 0:
                _team = server_data['team1_country']
                if server_data['team1_score'] > server_data['team2_score']:
                    _summed_stats['wins'] += 1
                elif server_data['team1_score'] < server_data['team2_score']:
                    _summed_stats['losses'] += 1
            else:
                _team = server_data['team2_country']
                if server_data['team1_score'] < server_data['team2_score']:
                    _summed_stats['wins'] += 1
                elif server_data['team1_score'] > server_data['team2_score']:
                    _summed_stats['losses'] += 1
            # Add team they played for
            if _team == "US":
                _summed_stats['us_games'] += 1
            elif _team == "CH":
                _summed_stats['ch_games'] += 1
            elif _team == "AC":
                _summed_stats['ac_games'] += 1
            else:
                _summed_stats['eu_games'] += 1
            # Add gamemode they played
            if server_data['game_type'] == "capturetheflag":
                _summed_stats['cf_games'] += 1
            else:
                _summed_stats['cq_games'] += 1
            # Add if they were the top player
            if _p['name'] == _top_player:
                _summed_stats['top_player'] += 1
            
            # Update player
            if _dbEntry != None:
                self.bot.db.update("player_stats", _summed_stats, [f"id={_dbEntry['id']}"])
            # Insert new player
            else:
                _summed_stats['nickname'] = _p['name']
                _summed_stats['first_seen'] = datetime.now().date()
                self.bot.db.insert("player_stats", _summed_stats)
        
        print("Done.")
        return _top_player
    
    def get_paginator_for_stat(self, stat: str) -> Paginator:
        """Returns a Leaderboard style Paginator for a given database stat"""
        _rank = 1
        _pages = []
        _dbEntries = self.bot.db.getAll("player_stats", ["nickname", stat], None, [stat, "DESC"], [0, 50]) # Limit to top 50 players
        if _dbEntries:
            _dbEntries = self.split_list(_dbEntries, 10) # Split into pages of 10 entries each
            for _page in _dbEntries:
                _embed = discord.Embed(
                    title=f":first_place:  BF2:MC Online | Top {stat.capitalize()} Leaderboard  :first_place:",
                    description=f"*Top 50 players across all servers.*",
                    color=discord.Colour.gold()
                )
                _nicknames = "```\n"
                _stats = "```\n"
                for _e in _page:
                    _rank_str = f"#{_rank}"
                    _nicknames += f"{_rank_str.ljust(3)} | {_e['nickname']}\n"
                    if stat == 'score':
                        _stats += f"{str(_e[stat]).rjust(5)} pts.\n"
                    elif stat == 'wins':
                        _stats += f" {self.bot.infl.no('game', _e[stat])} won\n"
                    else:
                        _stats += "\n"
                    _rank += 1
                _nicknames += "```"
                _stats += "```"
                _embed.add_field(name="Player:", value=_nicknames, inline=True)
                _embed.add_field(name=f"{stat.capitalize()}:", value=_stats, inline=True)
                _embed.set_footer(text=f"Unofficial data* -- {self.bot.config['API']['RootURL']}")
                _pages.append(Page(embeds=[_embed]))
        else:
            _embed = discord.Embed(
                title=f":first_place:  BF2:MC Online | Top {stat.capitalize()} Leaderboard*  :first_place:",
                description="No stats yet.",
                color=discord.Colour.gold()
            )
            _pages = [Page(embeds=[_embed])]
        return Paginator(pages=_pages, author_check=False)


    @commands.Cog.listener()
    async def on_ready(self):
        """Listener: On Cog Ready
        
        Runs when the cog is successfully cached within the Discord API.
        """
        print(f"{self.bot.get_datetime_str()}: [PlayerStats] Successfully cached!")
        
        # Check that all channels in the config are valid
        _cfg_sub_keys = [
            'PlayerStatsTextChannelID'
        ]
        await self.bot.check_channel_ids_for_cfg_key('PlayerStats', _cfg_sub_keys)
        
        # Start Status Loop
        if not self.StatsLoop.is_running():
            _config_interval = self.bot.config['PlayerStats']['QueryIntervalSeconds']
            self.StatsLoop.change_interval(seconds=_config_interval)
            self.StatsLoop.start()
            print(f"{self.bot.get_datetime_str()}: [PlayerStats] StatsLoop started ({_config_interval} sec. interval).")
    

    @tasks.loop(seconds=10)
    async def StatsLoop(self):
        """Task Loop: Stats Loop
        
        Runs every interval period, queries API for new data, 
        and records player data for any server that has finished a round.
        """
        ## Query API for new data
        await self.bot.query_api()

        ## Check each server if game over -> record stats
        # Only check if old data exists (so we can compare), and current data exists (avoid errors)
        if self.bot.old_query_data != None and self.bot.cur_query_data != None:
            # For all existing servers...
            for _s_o in self.bot.old_query_data['results']:
                _server_found = False
                # Search all current data for matching server
                for _s_n in self.bot.cur_query_data['results']:
                    if _s_o['id'] == _s_n['id']:
                        _server_found = True
                        # Record old data if current time is equal to old time (indicating a game finished),
                        # this is the first detection (times will equal until next game),
                        # and the server isn't empty.
                        _old_time = self.time_to_sec(_s_o['time_elapsed'])
                        _new_time = self.time_to_sec(_s_n['time_elapsed'])
                        if (_old_time == _new_time 
                            and _s_o['id'] not in self.game_over_ids
                            and len(_s_n['players']) > 1):
                            print(f"{self.bot.get_datetime_str()}: [PlayerStats] A server has finished a game:")
                            print(f"Server     : {_s_o['server_name']}")
                            print(f"Map        : {CS.MAP_STRINGS[_s_o['map_name']]}")
                            print(f"Orig. Time : {_s_o['time_elapsed']} ({_old_time} sec.)")
                            print(f"New Time   : {_s_n['time_elapsed']} ({_new_time} sec.)")
                            # Record stats and get top player nickname
                            _top_player = await self.record_player_stats(_s_o)
                            print(f"Top Player : {_top_player}")
                            # Send temp message to player stats channel that stats were recorded
                            _text_channel = self.bot.get_channel(self.bot.config['PlayerStats']['PlayerStatsTextChannelID'])
                            _embed = discord.Embed(
                                title="Player Stats Saved!",
                                description=f"Map Played: *{CS.MAP_STRINGS[_s_o['map_name']]}*\nTop Player: *{self.bot.escape_discord_formatting(_top_player)}*",
                                color=discord.Colour.green()
                            )
                            _embed.set_author(
                                name=f"\"{_s_o['server_name']}\" has finished a game...", 
                                icon_url="https://raw.githubusercontent.com/lilkingjr1/backstab-discord-bot/main/assets/icon.png"
                            )
                            _embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/0/04/Save-icon-floppy-disk-transparent-with-circle.png")
                            _embed.set_footer(text=f"Data captured at final game time of {_s_o['time_elapsed']}")
                            await _text_channel.send(embed=_embed, delete_after=DEL_STATS_SAVED_MSG_SEC)
                            # Mark server as being in post game state
                            self.game_over_ids.append(_s_o['id'])
                        # Remove server from list if new game started
                        elif _s_o['id'] in self.game_over_ids and _old_time > _new_time:
                            print(f"{self.bot.get_datetime_str()}: [PlayerStats] \"{_s_o['server_name']}\" has started a new game on {CS.MAP_STRINGS[_s_n['map_name']]}.")
                            self.game_over_ids.remove(_s_o['id'])
                        break
                # If server has gone offline, record last known data
                if not _server_found:
                    print(f"{self.bot.get_datetime_str()}: [PlayerStats] \"{_s_o['server_name']}\" has gone offline!")
                    await self.record_player_stats(_s_o)
                    # Remove server from game over list (if it happens to be in there)
                    if _s_o['id'] in self.game_over_ids:
                        self.game_over_ids.remove(_s_o['id'])
        
        ## Update interval if it differs from config & update channel description
        _config_interval = self.bot.config['PlayerStats']['QueryIntervalSeconds']
        if self.StatsLoop.seconds != _config_interval:
            self.StatsLoop.change_interval(seconds=_config_interval)
            print(f"{self.bot.get_datetime_str()}: [PlayerStats] Changed loop interval to {self.StatsLoop.seconds} sec.")


    """Slash Command Group: /stats
    
    A group of commands related to checking player stats.
    """
    stats = discord.SlashCommandGroup("stats", "Commands related to checking unofficial player stats")

    @stats.command(name = "player", description="Displays a specific player's unofficial BF2:MC Online stats")
    @commands.cooldown(1, 180, commands.BucketType.member)
    async def player(
        self,
        ctx,
        nickname: discord.Option(
            str, 
            description="Nickname of player to look up", 
            autocomplete=discord.utils.basic_autocomplete(get_player_nicknames), 
            max_length=255, 
            required=True
        )
    ):
        """Slash Command: /stats player
        
        Displays a specific player's unofficial BF2:MC Online stats.
        """
        _dbEntry = self.bot.db.getOne(
            "player_stats", 
            [
                "id",
                "first_seen",
                "score",
                "deaths",
                "us_games",
                "ch_games",
                "ac_games",
                "eu_games",
                "cq_games",
                "cf_games",
                "wins",
                "losses",
                "top_player"
            ], 
            ("nickname=%s", [nickname])
        )
        _escaped_nickname = self.bot.escape_discord_formatting(nickname)
        if _dbEntry:
            _rank_data = CS.get_rank_data(_dbEntry['score'])
            _total_games = _dbEntry['cq_games'] + _dbEntry['cf_games']
            _fav_gamemode = CS.GM_STRINGS['conquest'] # Default
            if _dbEntry['cf_games'] > _dbEntry['cq_games']:
                _fav_gamemode = CS.GM_STRINGS['capturetheflag']
            _team_games = {
                CS.TEAM_STRINGS['US'][:-1]: _dbEntry['us_games'],
                CS.TEAM_STRINGS['CH'][:-1]: _dbEntry['ch_games'],
                CS.TEAM_STRINGS['AC'][:-1]: _dbEntry['ac_games'],
                CS.TEAM_STRINGS['EU'][:-1]: _dbEntry['eu_games']
            }
            _fav_team = max(_team_games, key=_team_games.get)
            _ribbons = ""
            if _total_games >= 50:
                _ribbons += ":beginner: 50 Games\n"
            if _total_games >= 250:
                _ribbons += ":fleur_de_lis: 250 Games\n"
            if _total_games >= 500:
                _ribbons += ":trident: 500 Games\n"
            if _dbEntry['wins'] >= 5:
                _ribbons += ":third_place: 5 Victories\n"
            if _dbEntry['wins'] >= 20:
                _ribbons += ":second_place: 20 Victories\n"
            if _dbEntry['wins'] >= 50:
                _ribbons += ":first_place: 50 Victories\n"
            if _dbEntry['top_player'] >= 5:
                _ribbons += ":military_medal: 5 Top Player\n"
            if _dbEntry['top_player'] >= 20:
                _ribbons += ":medal: 20 Top Player\n"
            _embed = discord.Embed(
                title=_escaped_nickname,
                description=f"*{_rank_data[0]}*",
                color=discord.Colour.random(seed=_dbEntry['id'])
            )
            _embed.set_author(
                name="BF2:MC Online  |  Player Stats", 
                icon_url="https://raw.githubusercontent.com/lilkingjr1/backstab-discord-bot/main/assets/icon.png"
            )
            _embed.set_thumbnail(url=_rank_data[1])
            _embed.add_field(name="Total Score:", value=_dbEntry['score'], inline=True)
            _embed.add_field(name="Total Deaths:", value=_dbEntry['deaths'], inline=True)
            _embed.add_field(name="Ribbons:", value=_ribbons[:-1], inline=True)
            _embed.add_field(name="Total Games:", value=_total_games, inline=True)
            _embed.add_field(name="Games Won:", value=_dbEntry['wins'], inline=True)
            _embed.add_field(name="Games Lost:", value=_dbEntry['losses'], inline=True)
            _embed.add_field(name="Favorite Team:", value=_fav_team, inline=True)
            _embed.add_field(name="Favorite Gamemode:", value=_fav_gamemode, inline=True)
            _embed.set_footer(text=f"First seen online: {_dbEntry['first_seen'].strftime('%m/%d/%Y')} -- Unofficial data*")
            await ctx.respond(embed=_embed)
        else:
            await ctx.respond(f':warning: We have not seen a player by the nickname of "{_escaped_nickname}" play BF2:MC Online since June of 2023.', ephemeral=True)

    """Slash Command Sub-Group: /stats leaderboard
    
    A sub-group of commands related to checking the leaderboard for various player stats.
    """
    leaderboard = stats.create_subgroup("leaderboard", "Commands related to checking the unofficial leaderboard for various player stats")

    @leaderboard.command(name = "score", description="See an unofficial leaderboard of the top scoring players of BF2:MC Online")
    @commands.cooldown(1, 180, commands.BucketType.channel)
    async def score(self, ctx):
        """Slash Command: /stats leaderboard score
        
        Displays an unofficial leaderboard of the top scoring players of BF2:MC Online.
        """
        paginator = self.get_paginator_for_stat('score')
        await paginator.respond(ctx.interaction)

    @leaderboard.command(name = "wins", description="See an unofficial leaderboard of the top winning players of BF2:MC Online")
    @commands.cooldown(1, 180, commands.BucketType.channel)
    async def wins(self, ctx):
        """Slash Command: /stats leaderboard wins
        
        Displays an unofficial leaderboard of the top winning players of BF2:MC Online.
        """
        paginator = self.get_paginator_for_stat('wins')
        await paginator.respond(ctx.interaction)


def setup(bot):
    """Called by Pycord to setup the cog"""
    cog = CogPlayerStats(bot)
    cog.guild_ids = [bot.config['GuildID']]
    bot.add_cog(cog)
