"""CogPlayerStats.py

Handles tasks related to checking player stats and info.
Date: 09/09/2023
Authors: David Wolfe (Red-Thirten)
Licensed under GNU GPLv3 - See LICENSE for more details.
"""

from datetime import datetime

import discord
from discord.ext import commands, tasks
from discord.ext.pages import Paginator, Page
import common.CommonStrings as CS


SECONDS_PER_HOUR = 60.0 * 60.0

player_playtime_data = {}
disconnected_player_data = []


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
        ## Setup MySQL table 'player_stats'
        #self.bot.db.query("DROP TABLE player_stats") # DEBUGGING
        self.bot.db.query(
            "CREATE TABLE IF NOT EXISTS player_stats ("
                "id INT AUTO_INCREMENT PRIMARY KEY, "
                "pid INT DEFAULT NULL, "
                "nickname TINYTEXT NOT NULL, "
                "first_seen DATE NOT NULL, "
                "last_seen TIMESTAMP DEFAULT NULL, "
                "score INT NOT NULL, "
                "deaths INT NOT NULL, "
                "pph DECIMAL(5,2) UNSIGNED NOT NULL, "
                "playtime INT UNSIGNED NOT NULL, "
                "us_games INT NOT NULL, "
                "ch_games INT NOT NULL, "
                "ac_games INT NOT NULL, "
                "eu_games INT NOT NULL, "
                "cq_games INT NOT NULL, "
                "cf_games INT NOT NULL, "
                "wins INT NOT NULL, "
                "losses INT NOT NULL, "
                "top_player INT NOT NULL, "
                "dis_uid BIGINT DEFAULT NULL, "
                "color_r TINYINT UNSIGNED DEFAULT NULL, "
                "color_g TINYINT UNSIGNED DEFAULT NULL, "
                "color_b TINYINT UNSIGNED DEFAULT NULL, "
                "match_history CHAR(10) DEFAULT 'NNNNNNNNNN'"
            ")"
        )
        ## Setup MySQL table 'map_stats'
        #self.bot.db.query("DROP TABLE map_stats") # DEBUGGING
        self.bot.db.query(
            "CREATE TABLE IF NOT EXISTS map_stats ("
                "map_id INT PRIMARY KEY, "
                "map_name TINYTEXT NOT NULL, "
                "conquest INT DEFAULT 0, "
                "capturetheflag INT DEFAULT 0"
            ")"
        )
        ## Setup MySQL table 'player_blacklist'
        #self.bot.db.query("DROP TABLE player_blacklist") # DEBUGGING
        self.bot.db.query(
            "CREATE TABLE IF NOT EXISTS player_blacklist ("
                "id INT AUTO_INCREMENT PRIMARY KEY, "
                "pid INT DEFAULT NULL, "
                "nickname TINYTEXT NOT NULL"
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
    
    """
    def time_to_sec(self, time: str) -> int:
        # (DEPRECIATED) Turns a time string into seconds as an integer
        hours, minutes, seconds = time.split(':')
        return int(hours) * 3600 + int(minutes) * 60 + int(seconds)
    """
    
    async def record_player_stats(self, old_server_data: dict, new_server_data: dict):
        """Record Player Statistics
        
        Takes old and new data for a single server and checks all the players in the data.
        If a player stays connected (ie. they appear in both data sets), their playtime (based
        on query interval) is accumulated to the `player_playtime_data` in-memory dictionary.
        If a player disconnects (ie. they disapear from new data), they (along with their,
        Server ID, Team ID, and Playtime) are moved to the `disconnected_players_data` in-memory list.
        """
        _all_old_players = old_server_data['teams'][0]['players'] + old_server_data['teams'][1]['players']
        _all_new_players = new_server_data['teams'][0]['players'] + new_server_data['teams'][1]['players']
        for _p_o in _all_old_players:
            # Check if player stayed connected
            _player_stayed = False
            for _p_n in _all_new_players:
                if _p_o['id'] == _p_n['id']:
                    _player_stayed = True
                    break
            # Player stayed connected
            if _player_stayed:
                # Accumulate playtime
                if _p_o['name'] in player_playtime_data:
                    player_playtime_data[_p_o['name']] += self.bot.config['PlayerStats']['QueryIntervalSeconds']
                else:
                    #print(f"+ {_p_o['name']}") # DEBUGGING
                    player_playtime_data[_p_o['name']] = self.bot.config['PlayerStats']['QueryIntervalSeconds']
            # Player disconnected & participated in game
            elif _p_o['score'] != 0 or _p_o['deaths'] != 0:
                #print(f"- {_p_o['name']}") # DEBUGGING
                _p_o['serverID'] = old_server_data['id']
                if _p_o in old_server_data['teams'][0]['players']:
                    _p_o['teamID'] = old_server_data['teams'][0]['id']
                else:
                    _p_o['teamID'] = old_server_data['teams'][1]['id']
                _p_o['playtime'] = 0
                if _p_o['name'] in player_playtime_data:
                    _p_o['playtime'] = player_playtime_data[_p_o['name']]
                    player_playtime_data.pop(_p_o['name'])
                disconnected_player_data.append(_p_o)

    async def record_round_stats(self, server_data: dict) -> str:
        """Record Round Statistics
        
        Additively records end-round player statistics to the database given a server's JSON data.
        New records are created for first-seen players.
        Returns nickname string of the top player.
        """
        self.bot.log(f"Recording round stats... ", end='', time=False)

        # Sanitize input (because I'm paranoid)
        if server_data == None or server_data['playersCount'] < self.bot.config['PlayerStats']['MatchMinPlayers']:
            self.bot.log("Failed! (Invalid server data passed)", time=False)
            return None
        
        # Get blacklisted nicknames
        _nickname_blacklist = []
        _dbEntries = self.bot.db.getAll("player_blacklist", ["nickname"])
        if _dbEntries:
            for _dbEntry in _dbEntries:
                _nickname_blacklist.append(_dbEntry['nickname'])
        
        # Calculate winning team ID (-1 = Draw)
        _winning_team_ID = -1
        if server_data['teams'][0]['score'] > server_data['teams'][1]['score']:
            _winning_team_ID = server_data['teams'][0]['id']
        elif server_data['teams'][0]['score'] < server_data['teams'][1]['score']:
            _winning_team_ID = server_data['teams'][1]['id']
        
        # Calculate top player
        _top_player = None
        if server_data['playersCount'] >= self.bot.config['PlayerStats']['MvpMinPlayers']:
            _all_players = server_data['teams'][0]['players'] + server_data['teams'][1]['players']
            for _p in _all_players:
                # Skip player if their nickname is blacklisted
                if _p['name'] in _nickname_blacklist: continue
                # Replace if no top player, score is higher, or score is identical and deaths are lower
                if (_top_player == None
                    or _p['score'] > _top_player['score']
                    or (_p['score'] == _top_player['score'] and _p['deaths'] < _top_player['deaths'])):
                    _top_player = _p
            _top_player = _top_player['name']

        # Add connected players' playtime data
        for _t in server_data['teams']:
            for _p in _t['players']:
                try:
                    _p['playtime'] = player_playtime_data[_p['name']]
                    player_playtime_data.pop(_p['name'])
                except:
                    self.bot.log(f"\n[WARNING] \"{_p['name']}\" was not found in player playtime data! Ignoring playtime... ", time=False, end="")
                    _p['playtime'] = 0

        # Add disconnected players to server's data
        #print(f"\nDC'd players:\n{disconnected_player_data}") # DEBUGGING
        for _dc_p in disconnected_player_data.copy():
            if _dc_p['serverID'] == server_data['id']:
                for _t in server_data['teams']:
                    if _dc_p['teamID'] == _t['id']:
                        _t['players'].append(_dc_p)
                        disconnected_player_data.remove(_dc_p)
                        break

        # Calculate and record stats for each player in game
        for _t in server_data['teams']:
            for _p in _t['players']:
                # Skip player if their nickname is blacklisted
                if _p['name'] in _nickname_blacklist: continue
                # Skip player if they did not participate in the game
                if _p['score'] == 0 and _p['deaths'] == 0: continue
                # Find player in DB
                _dbEntry = self.bot.db.getOne(
                    "player_stats", 
                    [
                        "id",
                        "pid",
                        "score",
                        "deaths",
                        "pph",
                        "playtime",
                        "us_games",
                        "ch_games",
                        "ac_games",
                        "eu_games",
                        "cq_games",
                        "cf_games",
                        "wins",
                        "losses",
                        "top_player",
                        "match_history"
                    ], 
                    ("nickname=%s", [_p['name']])
                )
                ## Sum round stats with existing player stats
                # Copy existing DB entry for summation, or prepare a new entry for new players
                if _dbEntry == None:
                    _summed_stats = {
                        "pid": None,
                        "score": 0,
                        "deaths": 0,
                        "pph": 0,
                        "playtime": 0,
                        "us_games": 0,
                        "ch_games": 0,
                        "ac_games": 0,
                        "eu_games": 0,
                        "cq_games": 0,
                        "cf_games": 0,
                        "wins": 0,
                        "losses": 0,
                        "top_player": 0,
                        "match_history": 'NNNNNNNNNN'
                    }
                else:
                    _summed_stats = _dbEntry.copy()
                # Add scores and deaths
                _summed_stats['score'] += _p['score']
                _summed_stats['deaths'] += _p['deaths']
                # Add match result & history
                if _winning_team_ID == _t['id']:
                    _summed_stats['wins'] += 1
                    _summed_stats['match_history'] = _summed_stats['match_history'][1:] + 'W'
                elif _winning_team_ID == -1:
                    _summed_stats['match_history'] = _summed_stats['match_history'][1:] + 'D'
                else:
                    _summed_stats['losses'] += 1
                    _summed_stats['match_history'] = _summed_stats['match_history'][1:] + 'L'
                # Add team they played for
                _team = _t['country']
                if _team == "US":
                    _summed_stats['us_games'] += 1
                elif _team == "CH":
                    _summed_stats['ch_games'] += 1
                elif _team == "AC":
                    _summed_stats['ac_games'] += 1
                else:
                    _summed_stats['eu_games'] += 1
                # Add gamemode they played (if they didn't disconnect [indicated by 'serverID' key])
                if 'serverID' not in _p:
                    if server_data['gameType'] == "capturetheflag":
                        _summed_stats['cf_games'] += 1
                    else:
                        _summed_stats['cq_games'] += 1
                # Add if they were the top player
                if _p['name'] == _top_player:
                    _summed_stats['top_player'] += 1

                ## Calculate new PPH
                _pph = 0.0
                _pph_time_span_hrs = self.bot.config['PlayerStats']['PphTimeSpanHrs']
                # Convert to hours
                _db_time_hours = _summed_stats['playtime'] / SECONDS_PER_HOUR
                _game_time_hours = _p['playtime'] / SECONDS_PER_HOUR
                # Calculate total hours
                _total_hours = _db_time_hours + _game_time_hours
                # In case a player only played one hour (or less) total
                if _total_hours <= 1.0:
                    _pph = _summed_stats['score']
                # In case a player played less then 5 hours total
                elif _total_hours < _pph_time_span_hrs:
                    _pph = _summed_stats['score'] / _total_hours
                # In case a player played for more than 5 hours straight
                elif _game_time_hours >= _pph_time_span_hrs:
                    _pph = _p['score'] / _game_time_hours
                # In case we have in total more then 5 hours played
                else:
                    """
                    <---------------------- PPH_TIME_SPAN 5H ---------------------------------->
                    <---------------------- gap_time_span 4H50 ---------------><-- GAME 10m --->
                    <---------------------- gap_score  -----------------------><-- stat.score ->
                    """
                    # Calculate the gap for the pph time span
                    _gap_time_span = _pph_time_span_hrs - _game_time_hours
                    # Calculate the gap score with the database pph
                    _gap_score = float(_summed_stats['pph']) * _gap_time_span
                    ## Calculate new pph
                    _pph = (_gap_score + _p['score']) / _pph_time_span_hrs
                # Fix minimal and maximum
                if _pph < 0:
                    _pph = 1
                elif _pph > 200:
                    _pph = 200
                _summed_stats['pph'] = _pph
                
                # Add playtime
                _summed_stats['playtime'] += _p['playtime']

                # Replace last-seen timestamp
                _summed_stats['last_seen'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

                # Add OpenSpy PID if it is missing
                if _summed_stats['pid'] == None:
                    _summed_stats['pid'] = _p['id']
                
                # Update player
                if _dbEntry != None:
                    self.bot.db.update("player_stats", _summed_stats, [f"id={_dbEntry['id']}"])
                # Insert new player
                else:
                    _summed_stats['nickname'] = _p['name']
                    _summed_stats['first_seen'] = datetime.now().date()
                    self.bot.db.insert("player_stats", _summed_stats)
        
        self.bot.log("Done.", time=False)
        return _top_player
    
    async def record_map_stats(self, server_data: dict):
        """Record Map Statistics
        
        Additively records map statistics to the database given a server's JSON data.
        New records are created for first-seen maps.
        """
        self.bot.log(f"Recording map stats... ", end='', time=False)

        # Sanitize input (because I'm paranoid)
        if server_data == None or server_data['playersCount'] < self.bot.config['PlayerStats']['MatchMinPlayers']:
            self.bot.log("Failed! (Invalid server data passed)", time=False)
            return None
        
        # Determine if map was played on Conquest of CTF
        if server_data['gameType'] == "capturetheflag":
            _gamemode = "capturetheflag"
        else:
            _gamemode = "conquest"
        
        # Try to get map stat from DB
        _map_id = CS.MAP_DATA[server_data['mapName']][1]
        _dbEntry = self.bot.db.getOne(
            "map_stats", 
            [_gamemode], 
            ("map_id=%s", [_map_id])
        )
        
        # Add 1 to gamemode times played
        _times_played = 1
        if _dbEntry != None:
            _times_played += _dbEntry[_gamemode]
        
        # Insert or Update stat in DB
        self.bot.db.insertOrUpdate(
			"map_stats",
			{"map_id": _map_id, "map_name": server_data['mapName'], _gamemode: _times_played},
			"map_id"
		)

        self.bot.log("Done.", time=False)
    
    def get_paginator_for_stat(self, stat: str) -> Paginator:
        """Returns a Leaderboard style Paginator for a given database stat"""
        _rank = 1
        _pages = []
        _dbEntries = self.bot.db.getAll(
            "player_stats", 
            ["nickname", stat], 
            None, 
            [stat, "DESC"], # Order highest first
            [0, 50] # Limit to top 50 players
        )
        if _dbEntries:
            _dbEntries = self.split_list(_dbEntries, 10) # Split into pages of 10 entries each
            for _page in _dbEntries:
                _embed = discord.Embed(
                    title=f":first_place:  BF2:MC Online | Top {CS.LEADERBOARD_STRINGS[stat]} Leaderboard  :first_place:",
                    description=f"*Top 50 players across all servers.*",
                    color=discord.Colour.gold()
                )
                _nicknames = "```\n"
                _stats = "```\n"
                for _e in _page:
                    _rank_str = f"#{_rank}"
                    _nicknames += f"{_rank_str.ljust(3)} | {_e['nickname']}\n"
                    if stat == 'score':
                        _stats += f"{str(_e[stat]).rjust(6)} pts.\n"
                    elif stat == 'wins':
                        _stats += f" {self.bot.infl.no('game', _e[stat])} won\n"
                    elif stat == 'top_player':
                        _stats += f" {self.bot.infl.no('game', _e[stat])}\n"
                    elif stat == 'pph':
                        _stats += f"{str(int(_e[stat])).rjust(4)} PPH\n"
                    elif stat == 'playtime':
                        _stats += f"{str(int(_e[stat]/SECONDS_PER_HOUR)).rjust(5)} hrs.\n"
                    else:
                        _stats += "\n"
                    _rank += 1
                _nicknames += "```"
                _stats += "```"
                _embed.add_field(name="Player:", value=_nicknames, inline=True)
                _embed.add_field(name=f"{CS.LEADERBOARD_STRINGS[stat]}:", value=_stats, inline=True)
                _embed.set_footer(text=f"Unofficial data* -- {self.bot.config['API']['HumanURL']}")
                _pages.append(Page(embeds=[_embed]))
        else:
            _embed = discord.Embed(
                title=f":first_place:  BF2:MC Online | Top {CS.LEADERBOARD_STRINGS[stat]} Leaderboard*  :first_place:",
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
        self.bot.log("[PlayerStats] Successfully cached!")
        
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
            self.bot.log(f"[PlayerStats] StatsLoop started ({_config_interval} sec. interval).")
    

    @tasks.loop(seconds=10)
    async def StatsLoop(self):
        """Task Loop: Stats Loop
        
        Runs every interval period, queries API for new data, 
        and records player data for any server that has finished a round.
        """
        ## Query API for new data
        await self.bot.query_api()

        ## Record stats
        # Only check if old data exists (so we can compare), and current data exists (avoid errors)
        if self.bot.old_query_data != None and self.bot.cur_query_data != None:
            # For all existing servers...
            for _s_o in self.bot.old_query_data['servers']:
                _server_found = False
                # Search all current data for matching server
                for _s_n in self.bot.cur_query_data['servers']:
                    # If matching server is found in new data...
                    if _s_o['id'] == _s_n['id']:
                        _server_found = True
                        _old_time = _s_o['timeElapsed']
                        _new_time = _s_n['timeElapsed']
                        # Record old data if current time is equal to old time (indicating a game finished),
                        # this is the first detection (times will equal until next game),
                        # the server isn't empty, and game was at least a few sec. long.
                        if (_old_time == _new_time 
                            and _s_o['id'] not in self.bot.game_over_ids
                            and _s_o['playersCount'] >= self.bot.config['PlayerStats']['MatchMinPlayers']
                            and _old_time >= self.bot.config['PlayerStats']['MatchMinTimeSec']
                           ):
                            self.bot.log("[PlayerStats] A server has finished a game:")
                            self.bot.log(f"Server      : {_s_o['serverName']}", time=False)
                            # Record round stats and get top player nickname
                            _top_player = await self.record_round_stats(_s_o)
                            self.bot.log(f"Gamemode    : {CS.GM_STRINGS[_s_o['gameType']]}", time=False)
                            self.bot.log(f"Final Score : {_s_o['teams'][0]['score']} / {_s_o['teams'][1]['score']}", time=False)
                            self.bot.log(f"Map         : {CS.MAP_DATA[_s_o['mapName']][0]}", time=False)
                            self.bot.log(f"Top Player  : {_top_player}", time=False)
                            #self.bot.log(f"Orig. Time : {_s_o['timeElapsed']} ({_old_time} sec.)", time=False, file=False) # DEBUGGING
                            #self.bot.log(f"New Time   : {_s_n['timeElapsed']} ({_new_time} sec.)", time=False, file=False)
                            await self.record_map_stats(_s_o)
                            # Send temp message to player stats channel that stats were recorded
                            _text_channel = self.bot.get_channel(self.bot.config['PlayerStats']['PlayerStatsTextChannelID'])
                            _desc_text = f"Gamemode: *{CS.GM_STRINGS[_s_o['gameType']]}*"
                            _desc_text += f"\nMap: *{CS.MAP_DATA[_s_o['mapName']][0]}*"
                            _desc_text += f"\nFinal Score: *{_s_o['teams'][0]['score']} / {_s_o['teams'][1]['score']}*"
                            _desc_text += f"\nMVP: *{self.bot.escape_discord_formatting(_top_player)}*"
                            _embed = discord.Embed(
                                title="Player Stats Saved!",
                                description=_desc_text,
                                color=discord.Colour.green()
                            )
                            _embed.set_author(
                                name=f"\"{_s_o['serverName']}\" has finished a game...", 
                                icon_url="https://raw.githubusercontent.com/lilkingjr1/backstab-discord-bot/main/assets/icon.png"
                            )
                            _embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/0/04/Save-icon-floppy-disk-transparent-with-circle.png")
                            _embed.set_footer(text=f"Data captured at final game time of {self.bot.sec_to_mmss(_s_o['timeElapsed'])}")
                            await _text_channel.send(embed=_embed, delete_after=self.bot.config['PlayerStats']['DelStatsSavedMsgSec'])
                            # Mark server as being in post game state
                            self.bot.game_over_ids.append(_s_o['id'])
                        # Remove server from list if new game started
                        elif _s_o['id'] in self.bot.game_over_ids and _old_time > _new_time:
                            self.bot.log(f"[PlayerStats] \"{_s_n['serverName']}\" has started a new game on {CS.MAP_DATA[_s_n['mapName']][0]}.")
                            self.bot.game_over_ids.remove(_s_o['id'])
                        # Record player stats if game is not over & is a valid running game
                        elif (_s_o['id'] not in self.bot.game_over_ids
                              and _s_o['playersCount'] >= self.bot.config['PlayerStats']['MatchMinPlayers']
                             ):
                            await self.record_player_stats(_s_o, _s_n)
                        break
                # If server has gone offline, record last known data
                if not _server_found:
                    self.bot.log(f"[PlayerStats] \"{_s_o['serverName']}\" has gone offline!")
                    await self.record_round_stats(_s_o)
                    # Remove server from game over list (if it happens to be in there)
                    if _s_o['id'] in self.bot.game_over_ids:
                        self.bot.game_over_ids.remove(_s_o['id'])
        
        ## Update query interval if it differs from config
        _config_interval = self.bot.config['PlayerStats']['QueryIntervalSeconds']
        if self.StatsLoop.seconds != _config_interval:
            self.StatsLoop.change_interval(seconds=_config_interval)
            self.bot.log(f"[PlayerStats] Changed query interval to {self.StatsLoop.seconds} sec.")


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
                "pph",
                "playtime",
                "us_games",
                "ch_games",
                "ac_games",
                "eu_games",
                "cq_games",
                "cf_games",
                "wins",
                "losses",
                "top_player",
                "dis_uid",
                "color_r",
                "color_g",
                "color_b",
                "match_history"
            ], 
            ("nickname=%s", [nickname])
        )
        _escaped_nickname = self.bot.escape_discord_formatting(nickname)
        if _dbEntry:
            _rank_data = CS.get_rank_data(_dbEntry['score'], _dbEntry['pph'])
            _total_games = _dbEntry['cq_games'] + _dbEntry['cf_games']
            # Determine favorite gamemode
            _fav_gamemode = CS.GM_STRINGS['conquest'] # Default
            if _dbEntry['cf_games'] > _dbEntry['cq_games']:
                _fav_gamemode = CS.GM_STRINGS['capturetheflag']
            # Determine favorite team
            _team_games = {
                CS.TEAM_STRINGS['US'][:-1]: _dbEntry['us_games'],
                CS.TEAM_STRINGS['CH'][:-1]: _dbEntry['ch_games'],
                CS.TEAM_STRINGS['AC'][:-1]: _dbEntry['ac_games'],
                CS.TEAM_STRINGS['EU'][:-1]: _dbEntry['eu_games']
            }
            _fav_team = max(_team_games, key=_team_games.get)
            # Determine earned ribbons
            _ribbons = ""
            if _total_games >= 50:
                _ribbons += self.bot.config['Emoji']['Ribbons']['GamesPlayed50']
            if _total_games >= 250:
                _ribbons += self.bot.config['Emoji']['Ribbons']['GamesPlayed250']
            if _total_games >= 500:
                _ribbons += self.bot.config['Emoji']['Ribbons']['GamesPlayed500']
            if _dbEntry['wins'] >= 5:
                _ribbons += self.bot.config['Emoji']['Ribbons']['Victories5']
            if _dbEntry['wins'] >= 20:
                _ribbons += self.bot.config['Emoji']['Ribbons']['Victories20']
            if _dbEntry['wins'] >= 50:
                _ribbons += self.bot.config['Emoji']['Ribbons']['Victories50']
            if _dbEntry['top_player'] >= 5:
                _ribbons += self.bot.config['Emoji']['Ribbons']['TopPlayer5']
            if _dbEntry['top_player'] >= 20:
                _ribbons += self.bot.config['Emoji']['Ribbons']['TopPlayer20']
            if _ribbons == "": _ribbons = "None"
            # Calculate average score per game
            if _total_games < 1: _total_games = 1 # Div. by 0 safeguard
            _avg_score_per_game = _dbEntry['score'] / _total_games
            _avg_score_per_game = round(_avg_score_per_game, 2)
            # Calculate average score per life
            _lives = _dbEntry['deaths']
            if _lives < 1: _lives = 1 # Div. by 0 safeguard
            _avg_score_per_life = _dbEntry['score'] / _lives
            _avg_score_per_life = round(_avg_score_per_life, 2)
            # Calculate win percentage
            _win_percentage = (_dbEntry['wins'] / _total_games) * 100
            _win_percentage = round(_win_percentage, 2)
            _win_percentage = str(_win_percentage) + "%"
            # Calculate play time in hours
            _play_time = int(_dbEntry['playtime'] / SECONDS_PER_HOUR)
            _play_time = self.bot.infl.no('hour', _play_time)
            # Build match history string
            _match_history = ""
            for _c in _dbEntry['match_history']:
                if _c == 'W':
                    _match_history += self.bot.config['Emoji']['MatchHistory']['Win'] + " "
                elif _c == 'L':
                    _match_history += self.bot.config['Emoji']['MatchHistory']['Loss'] + " "
                elif _c == 'D':
                    _match_history += self.bot.config['Emoji']['MatchHistory']['Draw'] + " "
            if _match_history != "":
                _match_history = "Past ⏪ " + _match_history + "⏪ Recent"
            else:
                _match_history = "None"
            # Determine embed color
            if _dbEntry['color_r']:
                _color = discord.Colour.from_rgb(_dbEntry['color_r'], _dbEntry['color_g'], _dbEntry['color_b'])
            else:
                _color = discord.Colour.random(seed=_dbEntry['id'])
            # Set owner if applicable
            _author_name = "BF2:MC Online  |  Player Stats"
            _author_url = "https://raw.githubusercontent.com/lilkingjr1/backstab-discord-bot/main/assets/icon.png"
            if _dbEntry['dis_uid']:
                _owner = self.bot.get_user(_dbEntry['dis_uid'])
                if _owner:
                    _author_name = f"{_owner.display_name}'s Player Stats"
                    _author_url = _owner.display_avatar.url
            # Build embed
            _embed = discord.Embed(
                title=_escaped_nickname,
                description=f"*{_rank_data[0]}*",
                color=_color
            )
            _embed.set_author(
                name=_author_name, 
                icon_url=_author_url
            )
            _embed.set_thumbnail(url=_rank_data[1])
            _embed.add_field(name="Ribbons:", value=_ribbons, inline=False)
            _embed.add_field(name="PPH:", value=int(_dbEntry['pph']), inline=True)
            _embed.add_field(name="Total Score:", value=_dbEntry['score'], inline=True)
            _embed.add_field(name="MVP:", value=self.bot.infl.no('game', _dbEntry['top_player']), inline=True)
            _embed.add_field(name="Avg. Score/Game:", value=_avg_score_per_game, inline=True)
            _embed.add_field(name="Avg. Score/Life:", value=_avg_score_per_life, inline=True)
            _embed.add_field(name="Play Time:", value=_play_time, inline=True)
            _embed.add_field(name="Total Games:", value=_total_games, inline=True)
            _embed.add_field(name="Games Won:", value=_dbEntry['wins'], inline=True)
            _embed.add_field(name="Win Percentage:", value=_win_percentage, inline=True)
            _embed.add_field(name="Match Result History:", value=_match_history, inline=False)
            _embed.add_field(name="Favorite Team:", value=_fav_team, inline=True)
            _embed.add_field(name="Favorite Gamemode:", value=_fav_gamemode, inline=True)
            _embed.set_footer(text=f"First seen online: {_dbEntry['first_seen'].strftime('%m/%d/%Y')} -- Unofficial data*")
            await ctx.respond(embed=_embed)
        else:
            await ctx.respond(f':warning: We have not seen a player by the nickname of "{_escaped_nickname}" play BF2:MC Online since June of 2023.', ephemeral=True)

    @stats.command(name = "rankreqs", description="Displays the requirements to reach every rank")
    @commands.cooldown(1, 180, commands.BucketType.channel)
    async def rankreqs(
        self,
        ctx
    ):
        """Slash Command: /stats rankreqs
        
        Displays the requirements to reach every rank.
        """
        _ranks = "```\n"
        _score = "```\n"
        _pph = "```\n"
        for _i, (_reqs, _rank) in enumerate(CS.RANK_DATA.items()):
            _ranks += f"{(str(_i+1) + '.').ljust(4)}{_rank[0]}\n"
            if _rank[0] == "Private":
                _score += f"{str(0).rjust(6)} pts.\n"
                _pph += f"{str(0).rjust(5)} PPH\n"
            else:
                _score += f"{str(_reqs[0]).rjust(6)} pts.\n"
                _pph += f"{str(_reqs[1]).rjust(5)} PPH\n"
        _ranks += "```"
        _score += "```"
        _pph += "```"
        _embed = discord.Embed(
            title=f":military_medal:  BF2:MC Online | Rank Requirements  :military_medal:",
            description=f"The following are the requirements to reach each respective rank.\n*Each requirement must be met to reach the rank.*",
            color=discord.Colour.dark_blue()
        )
        _embed.add_field(name="Ranks:", value=_ranks, inline=True)
        _embed.add_field(name="Score:", value=_score, inline=True)
        _embed.add_field(name="Points per Hour:", value=_pph, inline=True)
        _embed.set_footer(text="Source: The original online game (un-modified).\nThe only thing missing are the Medal requirements (which are currently un-trackable).")
        await ctx.respond(embed=_embed)

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

    @leaderboard.command(name = "mvp", description="See an unofficial leaderboard of players who were MVP in their games of BF2:MC Online")
    @commands.cooldown(1, 180, commands.BucketType.channel)
    async def mvp(self, ctx):
        """Slash Command: /stats leaderboard mvp
        
        Displays an unofficial leaderboard of players who were MVP in their games of BF2:MC Online.
        """
        paginator = self.get_paginator_for_stat('top_player')
        await paginator.respond(ctx.interaction)

    @leaderboard.command(name = "pph", description="See an unofficial leaderboard of players with the most points earned per hour on BF2:MC Online")
    @commands.cooldown(1, 180, commands.BucketType.channel)
    async def pph(self, ctx):
        """Slash Command: /stats leaderboard pph
        
        Displays an unofficial leaderboard of players with the most points earned per hour on BF2:MC Online.
        """
        paginator = self.get_paginator_for_stat('pph')
        await paginator.respond(ctx.interaction)

    @leaderboard.command(name = "playtime", description="See an unofficial leaderboard of players with the most hours played on BF2:MC Online")
    @commands.cooldown(1, 180, commands.BucketType.channel)
    async def playtime(self, ctx):
        """Slash Command: /stats leaderboard playtime
        
        Displays an unofficial leaderboard of players with the most hours played on BF2:MC Online.
        """
        paginator = self.get_paginator_for_stat('playtime')
        await paginator.respond(ctx.interaction)

    """Slash Command Sub-Group: /stats mostplayed
    
    A sub-group of commands related to checking "most played" stats.
    """
    mostplayed = stats.create_subgroup("mostplayed", 'Commands related to checking "most played" related stats')

    @mostplayed.command(name = "map", description="See which maps have been played the most for a given gamemode")
    @commands.cooldown(1, 180, commands.BucketType.channel)
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
        """Slash Command: /stats mostplayed map
        
        Displays which maps have been played the most for a given gamemode.
        """
        _gm_id = "conquest"
        if gamemode == "Capture the Flag":
            _gm_id = "capturetheflag"
        
        _dbEntries = self.bot.db.getAll(
            "map_stats", 
            ["map_name", _gm_id], 
            None, 
            [_gm_id, "DESC"], 
            [0, 5]
        )

        if _dbEntries != None:
            _maps = "```\n"
            _games = "```\n"
            for _i, _dbEntry in enumerate(_dbEntries):
                _maps += f"{_i+1}. {CS.MAP_DATA[_dbEntry['map_name']][0]}\n"
                _games += f"{self.bot.infl.no('game', _dbEntry[_gm_id]).rjust(11)}\n"
            _maps += "```"
            _games += "```"
            _embed = discord.Embed(
                title=f"🗺  Most Played *{gamemode}* Maps",
                description=f"*Currently, the most played {gamemode} maps are...*",
                color=discord.Colour.dark_blue()
            )
            _embed.add_field(name="Map:", value=_maps, inline=True)
            _embed.add_field(name="Games Played:", value=_games, inline=True)
            _embed.add_field(name="Most Played Map:", value="", inline=False)
            _embed.set_image(url=CS.MAP_IMAGES_URL.replace("<map_name>", _dbEntries[0]['map_name']))
            _embed.set_footer(text=f"{self.bot.config['API']['HumanURL']}")
            await ctx.respond(embed=_embed)
        else:
            await ctx.respond(f":warning: No data for {gamemode} yet. Please try again later.", ephemeral=True)

    """Slash Command Sub-Group: /stats total
    
    A sub-group of commands related to checking "total count" stats.
    """
    total = stats.create_subgroup("total", 'Commands related to checking "total count" related stats')
    
    @total.command(name = "playercount", description="Displays the count of unique nicknames with recorded stats")
    @commands.cooldown(1, 1800, commands.BucketType.channel)
    async def playercount(self, ctx):
        """Slash Command: /stats total playercount
        
        Displays the count of unique nicknames with recorded stats.
        """
        _dbEntries = self.bot.db.getAll("player_stats", ["id"])

        _total_players = 0
        if _dbEntries != None:
            _total_players = len(_dbEntries)
        
        _embed = discord.Embed(
            title=f"👥︎  Total Player Count (All-Time)",
            description=f"I have tracked **{_total_players}** unique nicknames play at least one game since June of 2023*",
            color=discord.Colour.dark_blue()
        )
        _embed.set_footer(text="*Real player count may be lower due to players having multiple accounts")
        await ctx.respond(embed=_embed)
    
    @total.command(name = "games", description="Displays the total number of games played across all servers")
    @commands.cooldown(1, 1800, commands.BucketType.channel)
    async def games(self, ctx):
        """Slash Command: /stats total games
        
        Displays the total number of games played across all servers.
        """
        _dbEntries = self.bot.db.getAll("map_stats", ["conquest", "capturetheflag"])

        _total_games = 0
        if _dbEntries != None:
            for _dbEntry in _dbEntries:
                _total_games += _dbEntry['conquest'] + _dbEntry['capturetheflag']
        
        _embed = discord.Embed(
            title=f"🎮  Total Games (All Servers)",
            description=f"I have tracked **{_total_games}** unique games played across all servers since July of 2023",
            color=discord.Colour.dark_blue()
        )
        await ctx.respond(embed=_embed)

    """Slash Command Sub-Group: /stats nickname
    
    A sub-group of commands related to claiming, customizing, and moderating a nickname.
    """
    nickname = stats.create_subgroup("nickname", "Commands related to claiming, customizing, and moderating a nickname")
    
    @nickname.command(name = "claim", description="Claim ownership of an existing nickname with stats")
    @commands.cooldown(1, 60, commands.BucketType.member)
    async def claim(
        self, 
        ctx,
        nickname: discord.Option(
            str, 
            description="Nickname to claim", 
            autocomplete=discord.utils.basic_autocomplete(get_player_nicknames), 
            max_length=255, 
            required=True
        )
    ):
        """Slash Command: /stats nickname claim
        
        Allows the caller to associate their Discord account with an existing nickname
        in the database, which allows them to 'own' that nickname as their own.

        A caller can only claim a nickname if the nickname is valid and unclaimed,
        and they haven't already claimed a nickname before.

        Utilizes a `discord.ui.View` to verify that the caller actually wants to claim
        the nickname they specified.
        """
        _dbEntry = self.bot.db.getOne(
            "player_stats", 
            ["id"], 
            ("dis_uid=%s", [ctx.author.id])
        )
        # Check if author already has a claimed nickname
        if not _dbEntry:
            _dbEntry = self.bot.db.getOne(
                "player_stats", 
                ["id", "dis_uid"], 
                ("nickname=%s", [nickname])
            )
            _escaped_nickname = self.bot.escape_discord_formatting(nickname)
            # Check if the nickname is valid
            if _dbEntry:
                # Check if the nickname is unclaimed
                if not _dbEntry['dis_uid']:
                    _str1 = "You are only allowed to claim **one** nickname and this action **cannot** be undone!"
                    _str2 = f'Are you ***absolutely*** sure you want to claim the BF2:MC Online nickname of "**{_escaped_nickname}**"?'
                    _str3 = "*(Claiming a nickname you do not actually own will result in disciplinary action)*"
                    # Respond with buttons View
                    await ctx.respond(
                        _str1 + "\n\n" + _str2 + "\n" + _str3, 
                        view=self.ClaimNickname(_dbEntry['id'], nickname, ctx.author), 
                        ephemeral=True
                    )
                else:
                    # Get owner's display name and display error
                    _owner = self.bot.get_user(_dbEntry['dis_uid'])
                    if _owner:
                        _owner_name = self.bot.escape_discord_formatting(_owner.display_name)
                    else:
                        _owner_name = "*{User Left Server}*"
                    _str1 = f':warning: The nickname "{_escaped_nickname}" has already been claimed by: {_owner_name}'
                    _str2 = "If you have proof that you own this nickname, please contact an admin."
                    await ctx.respond(_str1 + "\n\n" + _str2, ephemeral=True)
            else:
                _str1 = f':warning: We have not seen the nickname of "{_escaped_nickname}" play BF2:MC Online since June of 2023.'
                _str2 = "(A nickname must have been used to play at least 1 game before it can be claimed)"
                await ctx.respond(_str1 + "\n\n" + _str2, ephemeral=True)
        else:
            _str1 = ":warning: You have already claimed your one and only nickname!"
            _str2 = "Please contact an admin (with proof of ownership) if you need another nickname associated with your account."
            _str3 = "(Note: Adding additional nicknames is an exception; not a right)"
            await ctx.respond(_str1 + "\n\n" + _str2 + "\n" + _str3, ephemeral=True)
    
    class ClaimNickname(discord.ui.View):
        """Discord UI View: Claim Nickname Confirmation
        
        Helper class.
        Displays confirmation button that will actually perform the nickname claim in the database.
        """
        def __init__(self, id, nickname, author, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.id = id
            self.nickname = nickname
            self.author = author
        
        @discord.ui.button(label="Yes, I'm sure!", style=discord.ButtonStyle.danger, emoji="✅")
        async def yes_button_callback(self, button, interaction):
            interaction.client.db.update(
                "player_stats", 
                {"dis_uid": self.author.id}, 
                [f"id={self.id}"]
            )
            interaction.client.log(f'[PlayerStats] {self.author.name}#{self.author.discriminator} has claimed the nickname "{self.nickname}".')
            _escaped_nickname = interaction.client.escape_discord_formatting(self.nickname)
            _str1 = f':white_check_mark: Nickname "{_escaped_nickname}" has successfully been claimed!'
            _str2 = "Your Discord name will now display alongside the nickname's stats."
            _str3 = "You can also change your stats banner to a unique color with `/stats nickname color` if you wish."
            await interaction.response.edit_message(
                content= _str1 + "\n\n" + _str2 + "\n" + _str3, 
                view = None
            )
        
        @discord.ui.button(label="No, cancel.", style=discord.ButtonStyle.primary, emoji="❌")
        async def no_button_callback(self, button, interaction):
            await interaction.response.edit_message(
                content="Nickname claim has been canceled.", 
                view = None
            )
    
    @nickname.command(name = "color", description="Change the stats banner color for a nickname you own")
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def color(
        self, 
        ctx, 
        nickname: discord.Option(
            str, 
            description="Nickname you own", 
            autocomplete=discord.utils.basic_autocomplete(get_player_nicknames), 
            max_length=255, 
            required=True
        ), 
        red: discord.Option(
            int, 
            description="Red Value | 0-255", 
            min_value=0, 
            max_value=255, 
            required=True
        ), 
        green: discord.Option(
            int, 
            description="Green Value | 0-255", 
            min_value=0, 
            max_value=255, 
            required=True
        ), 
        blue: discord.Option(
            int, 
            description="Blue Value | 0-255", 
            min_value=0, 
            max_value=255, 
            required=True
        )
    ):
        """Slash Command: /stats nickname color
        
        Changes the stats embed color in the database for a given nickname if the author owns said nickname.
        """
        _dbEntry = self.bot.db.getOne(
            "player_stats", 
            ["id", "dis_uid"], 
            ("nickname=%s", [nickname])
        )
        _escaped_nickname = self.bot.escape_discord_formatting(nickname)
        # Check if the author owns the nickname
        if _dbEntry and _dbEntry['dis_uid'] == ctx.author.id:
            self.bot.db.update(
                "player_stats", 
                {
                    "color_r": red, 
                    "color_g": green, 
                    "color_b": blue
                }, 
                [f"id={_dbEntry['id']}"]
            )
            await ctx.respond(f'Successfully changed the stats banner color to ({red}, {green}, {blue}) for "{_escaped_nickname}"!', ephemeral=True)
        else:
            await ctx.respond(f':warning: You do not own the nickname "{_escaped_nickname}"\n\nPlease use `/stats nickname claim` to claim it first.', ephemeral=True)
    
    @nickname.command(name = "assign", description="Assigns a Discord member to a nickname. Only admins can do this.")
    async def assign(
        self, 
        ctx,
        member: discord.Option(
            discord.Member, 
            description="Discord member (Set to BackStab bot to remove ownership)"
        ), 
        nickname: discord.Option(
            str, 
            description="BF2:MC Online nickname", 
            autocomplete=discord.utils.basic_autocomplete(get_player_nicknames), 
            max_length=255, 
            required=True
        )
    ):
        """Slash Command: /stats nickname assign
        
        Assigns a Discord member to be the owner of a nickname. Only admins can do this.
        """
        # Only members with Manage Channels permission can use this command.
        if not ctx.author.guild_permissions.manage_channels:
            _msg = ":warning: You do not have permission to run this command."
            _msg += "\n\nPlease try using `/stats nickname claim`, or contact an admin if you need to claim another nickname."
            await ctx.respond(_msg, ephemeral=True)
            return
        
        _dbEntry = self.bot.db.getOne(
            "player_stats", 
            ["id"], 
            ("nickname=%s", [nickname])
        )
        _escaped_nickname = self.bot.escape_discord_formatting(nickname)
        # Check if nickname is valid
        if _dbEntry:
            _uid = None
            # Check if specified member is not bot and get UID
            if member != self.bot.user:
                _uid = member.id
            # Update database
            self.bot.db.update(
                "player_stats", 
                {"dis_uid": _uid}, 
                [f"id={_dbEntry['id']}"]
            )
            self.bot.log(f'[PlayerStats] {ctx.author.name}#{ctx.author.discriminator} has assigned the nickname of "{nickname}" to {member.display_name}.')
            await ctx.respond(f':white_check_mark: {member.name} has successfully been assigned as the owner of nickname "{_escaped_nickname}"!', ephemeral=True)
        else:
            await ctx.respond(f':warning: I have not seen a player by the nickname of "{_escaped_nickname}" play BF2:MC Online since June of 2023.', ephemeral=True)
    
    @nickname.command(name = "ownedby", description="See which nicknames are owned by a given Discord member")
    @commands.cooldown(1, 60, commands.BucketType.channel)
    async def ownedby(
        self, 
        ctx,
        member: discord.Option(
            discord.Member, 
            description="Discord member"
        )
    ):
        """Slash Command: /stats nickname ownedby
        
        Displays which nicknames are owned by a given Discord member.
        """
        _dbEntries = self.bot.db.getAll(
            "player_stats", 
            ["nickname", "first_seen", "score", "pph"], 
            ("dis_uid = %s", [member.id])
        )
        _member_name = self.bot.escape_discord_formatting(member.display_name)

        if _dbEntries != None:
            _nicknames = "```\n"
            _rank = "```\n"
            _first_seen = "```\n"
            for _dbEntry in _dbEntries:
                _nicknames += f"{_dbEntry['nickname']}\n"
                _rank += f"{CS.get_rank_data(_dbEntry['score'], _dbEntry['pph'])[0]}\n"
                _first_seen += f"{_dbEntry['first_seen'].strftime('%m/%d/%Y')}\n"
            _nicknames += "```"
            _rank += "```"
            _first_seen += "```"
            _footer_text = "BF2:MC Online  |  Player Stats"
            _footer_icon_url = "https://raw.githubusercontent.com/lilkingjr1/backstab-discord-bot/main/assets/icon.png"
            _embed = discord.Embed(
                title=f"{_member_name}'s BF2:MC Online Nicknames",
                color=member.color
            )
            _embed.set_thumbnail(url=member.display_avatar.url)
            _embed.add_field(name="Nicknames:", value=_nicknames, inline=True)
            _embed.add_field(name="Rank:", value=_rank, inline=True)
            _embed.add_field(name="First Seen:", value=_first_seen, inline=True)
            _embed.set_footer(text=_footer_text, icon_url=_footer_icon_url)
            await ctx.respond(embed=_embed)
        else:
            await ctx.respond(f"{_member_name} has not claimed or been assigned any BF2:MC Online nicknames yet.", ephemeral=True)

    @nickname.command(name = "blacklist", description="Add or remove a nickname from the BF2:MC Online stats blacklist. Only admins can do this.")
    async def blacklist(
        self,
        ctx,
        action: discord.Option(
            str, 
            description="Add or Remove", 
            choices=["Add", "Remove"], 
            required=True
        ),
        nickname: discord.Option(
            str, 
            description="Nickname of player (can be nickname not currently in the database)", 
            autocomplete=discord.utils.basic_autocomplete(get_player_nicknames), 
            max_length=255, 
            required=True
        )
    ):
        """Slash Command: /stats nickname blacklist
        
        Adds or removes a nickname from the BF2:MC Online stats blacklist.
        Nicknames on the blacklist will not accumulate stats when games end.
        Existing stats for the nickname will not be adjusted or removed.
        Only admins can do this.
        """
        # Only members with Manage Channels permission can use this command.
        if not ctx.author.guild_permissions.manage_channels:
            await ctx.respond(":warning: You do not have permission to run this command.", ephemeral=True)
            return
        
        # Get existing nickname PID (if it exists)
        _dbPID = self.bot.db.getOne(
            "player_stats", ["pid"], ("nickname=%s", [nickname])
        )
        # Get existing blacklist entry (if it exists)
        _dbEntry = self.bot.db.getOne(
            "player_blacklist", ["id"], ("nickname=%s", [nickname])
        )
        _escaped_nickname = self.bot.escape_discord_formatting(nickname)
        # Add nickname
        if action == "Add":
            if not _dbEntry:
                _pid = None
                if _dbPID:
                    _pid = _dbPID['pid']
                self.bot.db.insert(
                    "player_blacklist", 
                    {"pid": _pid, "nickname": nickname}
                )
                self.bot.log(f'[PlayerStats] {ctx.author.name}#{ctx.author.discriminator} has added the nickname of "{nickname}" to the blacklist.')
                _msg = f':white_check_mark: "{_escaped_nickname}" has been added to the stats blacklist.'
                _msg += "\n\nThis nickname will not accumulate stats when games end as long as they are on this list."
                _msg += "\nExisting stats for this nickname will not be adjusted or removed."
                await ctx.respond(_msg)
            else:
                await ctx.respond(f'"{_escaped_nickname}" is already blacklisted.', ephemeral=True)
        # Remove nickname
        else:
            if _dbEntry:
                self.bot.db.delete(
                    "player_blacklist", 
                    ("id = %s", [_dbEntry['id']])
                )
                self.bot.log(f'[PlayerStats] {ctx.author.name}#{ctx.author.discriminator} has removed the nickname of "{nickname}" from the blacklist.')
                await ctx.respond(f':white_check_mark: Removed "{_escaped_nickname}" from the blacklist.', ephemeral=True)
            else:
                await ctx.respond(f':warning: Could not find "{_escaped_nickname}" in the blacklist.', ephemeral=True)

def setup(bot):
    """Called by Pycord to setup the cog"""
    cog = CogPlayerStats(bot)
    cog.guild_ids = [bot.config['GuildID']]
    bot.add_cog(cog)
