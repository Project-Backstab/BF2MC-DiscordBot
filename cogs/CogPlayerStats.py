"""CogPlayerStats.py

Handles tasks related to checking player stats and info.
Date: 10/09/2023
Authors: David Wolfe (Red-Thirten)
Licensed under GNU GPLv3 - See LICENSE for more details.
"""

from datetime import date

import discord
from discord.ext import commands, tasks
from discord.ext.pages import Paginator, Page
import common.CommonStrings as CS

SECONDS_PER_HOUR = 60.0 * 60.0
STATS_EPOCH_DATE_STR = "Oct. 20, 2023"


async def get_uniquenicks(ctx: discord.AutocompleteContext):
    """Autocomplete Context: Get unique nicknames
    
    Returns array of all uniquenicks in the backend's database.
    """
    _dbEntries = ctx.bot.db_backend.getAll(
        "Players", 
        ["uniquenick"]
    )
    if _dbEntries == None: return []
    
    return [_nick['uniquenick'] for _nick in _dbEntries]

async def get_owned_uniquenicks(ctx: discord.AutocompleteContext):
    """Autocomplete Context: Get owned unique nicknames
    
    Returns array of all uniquenicks in the backend's database.
    (Note: Can't use `leftJoin` because of two seperate schemas)
    """
    # Get owned profileids
    _dbEntries = ctx.bot.db_discord.getAll(
        "DiscordUserLinks", 
        ["profileid"],
	    ("discord_uid = %s", [ctx.interaction.user.id])
    )
    if _dbEntries == None: return []

    # Get uniquenicks from profileids
    _ids = [str(_id['profileid']) for _id in _dbEntries]
    _ids = ",".join(_ids) # Has to be comma seperated string for query to work
    _dbEntries = ctx.bot.db_backend.getAll(
        "Players",
        ["uniquenick"],
        (f"profileid IN ({_ids})", [])
    )
    if _dbEntries == None: return []

    return [_nick['uniquenick'] for _nick in _dbEntries]


class CogPlayerStats(discord.Cog):
    def __init__(self, bot):
        self.bot = bot
        ## Setup MySQL table 'DiscordUserLinks'
        #self.bot.db_discord.query("DROP TABLE DiscordUserLinks") # DEBUGGING
        self.bot.db_discord.query(
            "CREATE TABLE IF NOT EXISTS DiscordUserLinks ("
                "profileid INT PRIMARY KEY, "
                "discord_uid BIGINT NOT NULL"
            ")"
        )
        ## Setup MySQL table 'ProfileCustomization'
        #self.bot.db_discord.query("DROP TABLE ProfileCustomization") # DEBUGGING
        self.bot.db_discord.query(
            "CREATE TABLE IF NOT EXISTS ProfileCustomization ("
                "profileid INT PRIMARY KEY, "
                "color_r TINYINT UNSIGNED DEFAULT NULL, "
                "color_g TINYINT UNSIGNED DEFAULT NULL, "
                "color_b TINYINT UNSIGNED DEFAULT NULL"
            ")"
        )
        ## Setup MySQL table 'PlayerPatches'
        #self.bot.db_discord.query("DROP TABLE PlayerPatches") # DEBUGGING
        self.bot.db_discord.query(
            "CREATE TABLE IF NOT EXISTS PlayerPatches ("
                "id INT AUTO_INCREMENT PRIMARY KEY, "
                "profileid INT NOT NULL, "
                "patchid TINYINT UNSIGNED NOT NULL, "
                "date_earned DATE NOT NULL"
            ")"
        )
        ## Setup MySQL table 'map_stats'
        #self.bot.db_discord.query("DROP TABLE map_stats") # DEBUGGING
        self.bot.db_discord.query(
            "CREATE TABLE IF NOT EXISTS map_stats ("
                "map_id INT PRIMARY KEY, "
                "map_name TINYTEXT NOT NULL, "
                "conquest INT DEFAULT 0, "
                "capturetheflag INT DEFAULT 0"
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

    def get_num_medals_earned(self, earned_medals: int) -> int:
        return bin(earned_medals)[2:].count("1")

    def is_medal_earned(self, earned_medals: int, medal_name: str) -> bool:
        if medal_name not in CS.MEDALS_DATA:
            return False
        return earned_medals & CS.MEDALS_DATA[medal_name][0] == CS.MEDALS_DATA[medal_name][0]
    
    """
    def time_to_sec(self, time: str) -> int:
        # (DEPRECIATED) Turns a time string into seconds as an integer
        hours, minutes, seconds = time.split(':')
        return int(hours) * 3600 + int(minutes) * 60 + int(seconds)
    """
    
    def get_paginator_for_stat(self, stat: str) -> Paginator:
        """Returns a Leaderboard style Paginator for a given database stat"""
        _rank = 1
        _pages = []
        _dbEntries = self.bot.db_discord.getAll(
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
                _embed.set_footer(text={self.bot.config['API']['HumanURL']})
                _pages.append(Page(embeds=[_embed]))
        else:
            _embed = discord.Embed(
                title=f":first_place:  BF2:MC Online | Top {CS.LEADERBOARD_STRINGS[stat]} Leaderboard*  :first_place:",
                description="No stats yet.",
                color=discord.Colour.gold()
            )
            _pages = [Page(embeds=[_embed])]
        return Paginator(pages=_pages, author_check=False)
    
    async def record_map_stats(self, server_data: dict) -> bool:
        """Record Map Statistics
        
        Additively records map statistics to the database given a server's JSON data.
        New records are created for first-seen maps.
        Returns if it was successful or not.
        """
        self.bot.log(f"Recording map stats... ", end='', time=False)

        # Sanitize input (because I'm paranoid)
        if server_data == None or server_data['playersCount'] < self.bot.config['PlayerStats']['MatchMinPlayers']:
            self.bot.log("Failed! (Invalid server data passed)", time=False)
            return False
        
        # Determine if map was played on Conquest of CTF
        if server_data['gameType'] == "capturetheflag":
            _gamemode = "capturetheflag"
        else:
            _gamemode = "conquest"
        
        # Try to get map stat from DB
        _map_id = CS.MAP_DATA[server_data['mapName']][1]
        _dbEntry = self.bot.db_discord.getOne(
            "map_stats", 
            [_gamemode], 
            ("map_id=%s", [_map_id])
        )
        
        # Add 1 to gamemode times played
        _times_played = 1
        if _dbEntry != None:
            _times_played += _dbEntry[_gamemode]
        
        # Insert or Update stat in DB
        try:
            self.bot.db_discord.insertOrUpdate(
                "map_stats",
                {"map_id": _map_id, "map_name": server_data['mapName'], _gamemode: _times_played},
                "map_id"
            )
        except:
            self.bot.log("Failed! (DB insert or update)", time=False)
            return False

        self.bot.log("Done.", time=False)
        return True
    
    # async def check_stats_integrity(self, server_data: dict) -> bool:
    #     """Check Stats Integrity
        
    #     If enabled in the config, checks final round data of a server for any suspicious stats
    #     and reports them as a warning to the configured text channel.
    #     Returns:
    #     True == Clean
    #     False == Warning
    #     None == Disabled or Error
        
    #     The following are red flags that will trigger a warning:
    #     - Either team has 9 or more flags capped (CTF only)
    #     - Any player has 90 score or more
    #     - Any team collectively has 0 score and the server had active players (no resistance / didn't spawn)
    #     - Any team collectively has less than 2 deaths and more than 50 score (no resistance from enemy team)
    #     """
    #     if self.bot.config['PlayerStats']['IntegrityWarnings']['Enabled'] == False:
    #         return None
        
    #     self.bot.log(f"Checking stats integrity... ", end='', time=False)

    #     # Sanitize input (because I'm paranoid)
    #     if server_data == None:
    #         self.bot.log("Failed! (Invalid server data passed)", time=False)
    #         return None
        
    #     # Skip blacklisted Server IDs
    #     if server_data['id'] in self.bot.config['ServerStatus']['Blacklist']:
    #         self.bot.log("Blacklisted Server (Skipping).", time=False)
    #         return True
        
    #     async def _send_warning_msg(reason: str):
    #         """To be called by any of the flags to send the warning message"""
    #         self.bot.log("Warning!", time=False)
    #         _text_channel = self.bot.get_channel(
    #             self.bot.config['PlayerStats']['IntegrityWarnings']['TextChannelID']
    #         )
    #         _msg = ":warning: **Potentially Suspicious Game**"
    #         _msg += f"\n*Reason: ||{reason}||*"
    #         _embed = self.bot.get_server_status_embed(server_data)
    #         await _text_channel.send(_msg, embed=_embed)

    #     # Perform checks
    #     _s_col_score = 0
    #     for _t in server_data['teams']:
    #         for _p in _t['players']:
    #             _s_col_score += _p['score']
    #     for _t in server_data['teams']:
    #         # Check flags
    #         if (server_data['gameType'] == "capturetheflag" and _t['score'] >= 9):
    #             await _send_warning_msg("Many flags capped")
    #             return False
    #         _t_col_score = 0
    #         _t_col_deaths = 0
    #         # Check individual player score, and total collective score & deaths
    #         for _p in _t['players']:
    #             if _p['score'] >= 90:
    #                 await _send_warning_msg("Player with 90 pts. or more")
    #                 return False
    #             _t_col_score += _p['score']
    #             _t_col_deaths += _p['deaths']
    #         if _t_col_score < 1 and _s_col_score >= 50:
    #             await _send_warning_msg(f"Team {_t['country']} collectively didn't score any points (no resistance / didn't spawn?)")
    #             return False
    #         if _t_col_deaths < 2 and _t_col_score >= 50:
    #             await _send_warning_msg(f"Team {_t['country']} collectively died less than 2 times (no resistance from enemy team?)")
    #             return False
        
    #     self.bot.log("Clean.", time=False)
    #     return True

    async def check_legacy_uniquenick(self, uniquenick: str) -> bool:
        """Check Legacy Unique Nickname
        
        If a uniquenick does not have a current registered owner, but did have
        a legacy owner, assign the legacy owner, colors (if applicable), and
        legacy award to the uniquenick.
        """
        _cur_player = self.bot.db_backend.getOne(
            "Players", 
            ["profileid"], 
            ("uniquenick=%s", [uniquenick])
        )
        if _cur_player == None: return False # Bad uniquenick

        _cur_owner = self.bot.db_discord.getOne(
            "DiscordUserLinks", 
            ["discord_uid"], 
            ("profileid=%s", [_cur_player['profileid']])
        )
        if _cur_owner: return False # Nick already owned

        _legacy_data = self.bot.db_discord.getOne(
            "LegacyStats", 
            ["dis_uid", "color_r", "color_g", "color_b"], 
            ("nickname=%s", [uniquenick])
        )
        if _legacy_data == None: return False # Legacy data doesn't exist
        self.bot.log(f"[PlayerStats] Legacy nickname detected: {uniquenick}")

        # Set ownership using legacy owner
        if _legacy_data['dis_uid'] != None:
            self.bot.db_discord.insert(
                "DiscordUserLinks", 
                {
                    "profileid": _cur_player['profileid'], 
                    "discord_uid": _legacy_data['dis_uid']
                }
            )
        # Set profile customization using legacy customization (if present)
        if _legacy_data['color_r'] != None:
            self.bot.db_discord.insert(
                "ProfileCustomization", 
                {
                    "profileid": _cur_player['profileid'], 
                    "color_r": _legacy_data['color_r'], 
                    "color_g": _legacy_data['color_g'], 
                    "color_b": _legacy_data['color_b']
                }
            )
        # Award Legacy Patch if we haven't already
        _legacy_patch = self.bot.db_discord.getOne(
            "PlayerPatches", 
            ["id"], 
            ("profileid=%s and patchid=%s", [_cur_player['profileid'], 0])
        )
        if _legacy_patch == None:
            self.bot.db_discord.insert(
                "PlayerPatches", 
                {
                    "profileid": _cur_player['profileid'], 
                    "patchid": 0, 
                    "date_earned": date.today()
                }
            )
        return True


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


    """Slash Command Group: /stats
    
    A group of commands related to checking stats.
    """
    stats = discord.SlashCommandGroup("stats", "Commands related to checking player stats")

    @stats.command(name = "player", description="Displays a specific player's BF2:MC Online stats")
    @commands.cooldown(1, 180, commands.BucketType.member)
    async def player(
        self,
        ctx,
        nickname: discord.Option(
            str, 
            description="Nickname of player to look up", 
            autocomplete=discord.utils.basic_autocomplete(get_uniquenicks), 
            max_length=255, 
            required=True
        )
    ):
        """Slash Command: /stats player
        
        Displays a specific player's BF2:MC Online stats.
        """
        # await ctx.defer() TODO
        _escaped_nickname = self.bot.escape_discord_formatting(nickname)

        ## Get player data
        _player_data = self.bot.db_backend.leftJoin(
            ("Players", "PlayerStats"),
            (
                [
                    "profileid",
                    "created_at",
                    "last_login"
                ],
                [
                    "score",    # Total score
                    "ran",      # Rank
                    "pph",      # Points per hour
                    "kills",    # Total kills
                    "deaths",   # Total deaths
                    "suicides", # Total suicides
                    "time",     # Total time played (seconds)
                    "vehicles", # Total Vehicles destroyed
                    "lavd",     # Total LAV's destroyed, Light Armored Vehicle  (such as a Humvee or similar)
                    "mavd",     # Total MAV's destroyed, Medium Armored Vehicle (such as a Tank or similar)
                    "havd",     # Total HAV's destroyed, Heavy Armored Vehicle  (such as an APC or similar)
                    "hed",      # Total Helicopters destroyed
                    "bod",      # Total Boats destoyed
                    "k1",       # Total kills Assualt kit
                    "s1",       # Total spawns Assualt kit
                    "k2",       # Total kills Sniper kit
                    "s2",       # Total spawns Sniper kit
                    "k3",       # Total kills Special Op. kit
                    "s3",       # Total spawns Special Op. kit
                    "k4",       # Total kills Combat Engineer kit
                    "s4",       # Total spawns Combat Engineer kit
                    "k5",       # Total kills Support kit
                    "s5",       # Total spawns Support kit
                    "medals",   # Earned medals (byte encoded int)
                    "ttb",      # Total times top player / MVP
                    "mv",       # Total major victories
                    "ngp"       # Total participated game sessions
                ]
            ),
            ("profileid", "profileid"),
            ("uniquenick=%s", [nickname])
        )
        if _player_data == None or len(_player_data) < 1:
            return await ctx.respond(
                f':warning: We have not seen a player by the nickname of "{_escaped_nickname}" play BF2:MC Online since {STATS_EPOCH_DATE_STR}.', 
                ephemeral=True
            )
        _player_data = _player_data[0] # Should only return one entry, so let's isolate it

        ## Get Discord data (if available)
        await self.check_legacy_uniquenick(nickname)
        _discord_data = self.bot.db_discord.leftJoin(
            ("DiscordUserLinks", "ProfileCustomization"),
            (
                ["discord_uid"],
                ["color_r", "color_g", "color_b"]
            ),
            ("profileid", "profileid"),
            ("DiscordUserLinks.profileid=%s", [_player_data['profileid']])
        )
        if _discord_data != None and len(_discord_data) > 0: # Clean up result
            _discord_data = _discord_data[0]
        else:
            _discord_data = None
        
        ## Get Patches data
        _patches_data = self.bot.db_discord.getAll(
            "PlayerPatches", 
            ["patchid", "date_earned"], 
            ("profileid=%s", [_player_data['profileid']])
        )
        
        ## Get match win/lose/draw data and sort by date
        _match_results_data = self.bot.db_backend.call(
            # "queryPlayerWinLoseDraw", 
            "queryGameStatsResults",
            [_player_data['profileid']]
        )
        _match_wld_data = self.bot.db_backend.call(
            "queryPlayerWinLoseDraw", 
            [_player_data['profileid']]
        )

        ## Get match gamemode data
        _match_gamemode_data = self.bot.db_backend.call(
            "queryPlayerGametypesPlayed",
            [_player_data['profileid']]
        )

        ## Get team countries data
        _team_countries_data = self.bot.db_backend.call(
            "queryPlayerTeamCountriesPlayed",
            [_player_data['profileid']]
        )

        ## Get clan data (if available)
        _clan_data = self.bot.db_backend.call(
            "queryClanByProfileId",
            [_player_data['profileid']]
        )

        ## Calculate additional data
        _rank_data = CS.RANK_DATA[_player_data['ran'] + 1]
        # Get number of medals and build emoji string
        _num_medals = self.get_num_medals_earned(_player_data['medals'])
        _medals_emoji = ""
        for _m in CS.MEDALS_DATA:
            if self.is_medal_earned(_player_data['medals'], _m):
                _medals_emoji += self.bot.config['Emoji']['Medals'][_m] + " "
        if _medals_emoji == "": _medals_emoji = None
        # Determine earned ribbons
        _num_ribbons = 0
        _ribbons = []
        _ribbons_emoji = ""
        if _player_data['ngp'] >= 50:
            _id = 'Games_Played_50'
            _ribbons.append(_id)
            _ribbons_emoji += self.bot.config['Emoji']['Ribbons'][_id] + " "
            _num_ribbons += 1
        if _player_data['ngp'] >= 250:
            _id = 'Games_Played_250'
            _ribbons.append(_id)
            _ribbons_emoji += self.bot.config['Emoji']['Ribbons'][_id] + " "
            _num_ribbons += 1
        if _player_data['ngp'] >= 500:
            _id = 'Games_Played_500'
            _ribbons.append(_id)
            _ribbons_emoji += self.bot.config['Emoji']['Ribbons'][_id] + " "
            _num_ribbons += 1
        if _player_data['mv'] >= 5:
            _id = 'Major_Victories_5'
            _ribbons.append(_id)
            _ribbons_emoji += self.bot.config['Emoji']['Ribbons'][_id] + " "
            _num_ribbons += 1
        if _player_data['mv'] >= 20:
            _id = 'Major_Victories_20'
            _ribbons.append(_id)
            _ribbons_emoji += self.bot.config['Emoji']['Ribbons'][_id] + " "
            _num_ribbons += 1
        if _player_data['mv'] >= 50:
            _id = 'Major_Victories_50'
            _ribbons.append(_id)
            _ribbons_emoji += self.bot.config['Emoji']['Ribbons'][_id] + " "
            _num_ribbons += 1
        if _player_data['ttb'] >= 5:
            _id = 'Top_Player_5'
            _ribbons.append(_id)
            _ribbons_emoji += self.bot.config['Emoji']['Ribbons'][_id] + " "
            _num_ribbons += 1
        if _player_data['ttb'] >= 20:
            _id = 'Top_Player_20'
            _ribbons.append(_id)
            _ribbons_emoji += self.bot.config['Emoji']['Ribbons'][_id] + " "
            _num_ribbons += 1
        if _ribbons_emoji == "": _ribbons_emoji = None
        # Determine earned patches
        _patches_emoji = ""
        if _patches_data:
            for _p in _patches_data:
                _patches_emoji += self.bot.config['Patches'][_p['patchid']][2]
        if _patches_emoji == "": _patches_emoji = None
        # Calculate K/D ratio
        if _player_data['deaths'] < 1: _player_data['deaths'] = 1 # Div. by 0 safeguard
        _kd_ratio = _player_data['kills'] / _player_data['deaths']
        _kd_ratio = round(_kd_ratio, 2)
        # Calculate average score per game
        if _player_data['ngp'] < 1: _player_data['ngp'] = 1 # Div. by 0 safeguard
        _avg_score_per_game = _player_data['score'] / _player_data['ngp']
        _avg_score_per_game = round(_avg_score_per_game, 2)
        # Calculate win percentage
        _wins = 0
        for _m in _match_wld_data:
            if _m[5] == "win":
                _wins += 1
        _win_percentage = (_wins / _player_data['ngp']) * 100
        _win_percentage = round(_win_percentage, 2)
        _win_percentage = str(_win_percentage) + "%"
        # Calculate play time in hours
        _play_time = int(_player_data['time'] / SECONDS_PER_HOUR)
        _play_time = self.bot.infl.no('hour', _play_time)
        # Determine favorite gamemode
        _cq_games = 0
        _cf_games = 0
        for _m in _match_gamemode_data:
            if _m[0] == CS.GM_STRINGS['capturetheflag'][1]:
                _cf_games += 1
            else:
                _cq_games += 1
        _fav_gamemode = CS.GM_STRINGS['conquest'][0] # Default
        if _cf_games > _cq_games:
            _fav_gamemode = CS.GM_STRINGS['capturetheflag'][0]
        # Determine favorite team country
        _team_games = CS.TEAM_STRINGS.copy()
        for _k in _team_games: _team_games[_k] = 0
        for _m in _team_countries_data:
            for _k in CS.TEAM_STRINGS:
                if _m[0] == CS.TEAM_STRINGS[_k][1]:
                    _team_games[_k] += 1
        _fav_team = max(_team_games, key=_team_games.get)
        # Determine favorite kit
        _kit_spawns = {
            "Assualt":          _player_data['s1'],
            "Sniper":           _player_data['s2'],
            "Special Op.":      _player_data['s3'],
            "Combat Engineer":  _player_data['s4'],
            "Support":          _player_data['s5']
        }
        _fav_kit = max(_kit_spawns, key=lambda k: _kit_spawns[k])
        # Build match history string
        _match_history = ""
        for _m in reversed(_match_results_data):
            if _m[4] == 'win':
                _match_history += self.bot.config['Emoji']['MatchHistory']['Win'] + " "
            elif _m[4] == 'lose':
                _match_history += self.bot.config['Emoji']['MatchHistory']['Loss'] + " "
            elif _m[4] == 'draw':
                _match_history += self.bot.config['Emoji']['MatchHistory']['Draw'] + " "
        if _match_history != "":
            _match_history = "Past ⏪ " + _match_history + "⏪ Recent"
        else:
            _match_history = "None"
        # Determine embed color
        if _discord_data and _discord_data['color_r']:
            _color = discord.Colour.from_rgb(_discord_data['color_r'], _discord_data['color_g'], _discord_data['color_b'])
        else:
            _color = discord.Colour.random(seed=_player_data['profileid'])
        # Set owner if applicable
        _author_name = "BF2:MC Online  |  Player Stats"
        _author_url = "https://raw.githubusercontent.com/lilkingjr1/backstab-discord-bot/main/assets/icon.png"
        if _discord_data:
            _owner = self.bot.get_user(_discord_data['discord_uid'])
            if _owner:
                _author_name = f"{_owner.display_name}'s Player Stats"
                _author_url = _owner.display_avatar.url
        # Set clan if applicable
        if len(_clan_data) > 0:
            _escaped_nickname = f"{_clan_data[0][2]} {_escaped_nickname}"
        
        ## Build embeds/pages
        _embeds = {}
        _select_options = []
        # Summary
        _title = "Summary"
        _e_summary = discord.Embed(
            title=_escaped_nickname,
            description=f"***{_rank_data[0]}***",
            color=_color
        )
        _e_summary.set_author(
            name=_author_name, 
            icon_url=_author_url
        )
        _e_summary.set_thumbnail(url=_rank_data[1])
        if _medals_emoji:
            _e_summary.add_field(name="Medals:", value=_medals_emoji, inline=False)
        if _ribbons_emoji:
            _e_summary.add_field(name="Ribbons:", value=_ribbons_emoji, inline=False)
        if _patches_emoji:
            _e_summary.add_field(name="Patches:", value=_patches_emoji, inline=False)
        _e_summary.add_field(name="PPH:", value=int(_player_data['pph']), inline=True)
        _e_summary.add_field(name="Total Score:", value=_player_data['score'], inline=True)
        _e_summary.add_field(name="Medals:", value=_num_medals, inline=True)
        _e_summary.add_field(name="Match Result History:", value=_match_history, inline=False)
        _e_summary.add_field(name="Last Seen Online:", value=_player_data['last_login'].strftime('%m/%d/%Y'), inline=False)
        _e_summary.set_footer(text=f"First seen online: {_player_data['created_at'].strftime('%m/%d/%Y')} -- BFMCspy Official Stats")
        _embeds[_title] = _e_summary
        _select_options.append(
            discord.SelectOption(
                label=_title,
                description="General overview of stats",
                emoji="📊"
            )
        )
        # Stats Details
        _title = "Stats Details"
        _desc = f"***{_rank_data[0]}***"
        _desc += f"\n### {_title}:"
        _e_details = discord.Embed(
            title=_escaped_nickname,
            description=_desc,
            color=_color
        )
        _e_details.set_author(
            name=_author_name, 
            icon_url=_author_url
        )
        _e_details.set_thumbnail(url=_rank_data[1])
        _e_details.add_field(name="Kills:", value=_player_data['kills'], inline=True)
        _e_details.add_field(name="Deaths:", value=_player_data['deaths'], inline=True)
        _e_details.add_field(name="Suicides:", value=_player_data['suicides'], inline=True)
        _e_details.add_field(name="K/D Ratio:", value=_kd_ratio, inline=True)
        _e_details.add_field(name="Avg. Score/Game:", value=_avg_score_per_game, inline=True)
        _e_details.add_field(name="Play Time:", value=_play_time, inline=True)
        _e_details.add_field(name="MVP:", value=self.bot.infl.no('game', _player_data['ttb']), inline=True)
        _e_details.add_field(name="Total Games:", value=_player_data['ngp'], inline=True)
        _e_details.add_field(name="Win Percentage:", value=_win_percentage, inline=True)
        _e_details.add_field(name="Favorite Gamemode:", value=_fav_gamemode, inline=True)
        _e_details.add_field(name="Conquest Played:", value=self.bot.infl.no('game', _cq_games), inline=True)
        _e_details.add_field(name="CTF Played:", value=self.bot.infl.no('game', _cf_games), inline=True)
        _e_details.add_field(name="Favorite Team:", value=CS.TEAM_STRINGS[_fav_team][0][:-1], inline=True)
        _e_details.set_footer(text=f"First seen online: {_player_data['created_at'].strftime('%m/%d/%Y')} -- BFMCspy Official Stats")
        _embeds[_title] = _e_details
        _select_options.append(
            discord.SelectOption(
                label=_title,
                description="Additional detailed stats",
                emoji="📈"
            )
        )
        # Medals
        _title = "Medals"
        _desc = f"***{_rank_data[0]}***"
        _desc += f"\n### {_title} Earned: {_num_medals}"
        _e_medals = discord.Embed(
            title=_escaped_nickname,
            description=_desc,
            color=_color
        )
        _e_medals.set_author(
            name=_author_name, 
            icon_url=_author_url
        )
        _e_medals.set_thumbnail(url=_rank_data[1])
        for _m in CS.MEDALS_DATA:
            if self.is_medal_earned(_player_data['medals'], _m):
                _e_medals.add_field(
                    name=f"{self.bot.config['Emoji']['Medals'][_m]} {CS.MEDALS_DATA[_m][1]}:", 
                    value=CS.MEDALS_DATA[_m][2], 
                    inline=False
                )
        _e_medals.set_footer(text="BFMCspy Official Stats")
        _embeds[_title] = _e_medals
        _emoji = self.bot.config['Emoji']['Medals']['Expert_Shooting']
        _emoji = _emoji.split(":")[2][:-1]
        _emoji = await ctx.guild.fetch_emoji(_emoji)
        _select_options.append(
            discord.SelectOption(
                label=_title,
                description="All medals earned",
                emoji=_emoji
            )
        )
        # Ribbons
        _title = "Ribbons"
        _desc = f"***{_rank_data[0]}***"
        _desc += f"\n### {_title} Earned: {_num_ribbons}"
        _e_ribbons = discord.Embed(
            title=_escaped_nickname,
            description=_desc,
            color=_color
        )
        _e_ribbons.set_author(
            name=_author_name, 
            icon_url=_author_url
        )
        _e_ribbons.set_thumbnail(url=_rank_data[1])
        for _r in _ribbons:
            _e_ribbons.add_field(
                name=f"{self.bot.config['Emoji']['Ribbons'][_r]} {CS.RIBBONS_DATA[_r][0]}:", 
                value=CS.RIBBONS_DATA[_r][1], 
                inline=False
            )
        _e_ribbons.set_footer(text="BFMCspy Official Stats")
        _embeds[_title] = _e_ribbons
        _emoji = self.bot.config['Emoji']['Ribbons']['Games_Played_50']
        _emoji = _emoji.split(":")[2][:-1]
        _emoji = await ctx.guild.fetch_emoji(_emoji)
        _select_options.append(
            discord.SelectOption(
                label=_title,
                description="All ribbons earned",
                emoji=_emoji
            )
        )
        # Patches
        if _patches_data:
            _title = "Patches"
            _desc = f"***{_rank_data[0]}***"
            _desc += f"\n### {_title} Earned:"
            _e_patches = discord.Embed(
                title=_escaped_nickname,
                description=_desc,
                color=_color
            )
            _e_patches.set_author(
                name=_author_name, 
                icon_url=_author_url
            )
            _e_patches.set_thumbnail(url=_rank_data[1])
            for _p in _patches_data:
                _e_patches.add_field(
                    name=f"{self.bot.config['Patches'][_p['patchid']][2]} {self.bot.config['Patches'][_p['patchid']][0]}:", 
                    value=f"*Earned: {_p['date_earned'].strftime('%m/%d/%y')}*\n{self.bot.config['Patches'][_p['patchid']][1]}", 
                    inline=False
                )
            _e_patches.set_footer(text="BFMCspy Official Stats")
            _embeds[_title] = _e_patches
            _emoji = self.bot.config['Patches'][0][2]
            _emoji = _emoji.split(":")[2][:-1]
            _emoji = await ctx.guild.fetch_emoji(_emoji)
            _select_options.append(
                discord.SelectOption(
                    label=_title,
                    description="All patches earned from community events",
                    emoji=_emoji
                )
            )
        # Vehicles Destroyed
        _title = "Vehicles Destroyed"
        _desc = f"***{_rank_data[0]}***"
        _desc += f"\n### {_title}: {_player_data['vehicles']}"
        _e_vehicles = discord.Embed(
            title=_escaped_nickname,
            description=_desc,
            color=_color
        )
        _e_vehicles.set_author(
            name=_author_name, 
            icon_url=_author_url
        )
        _e_vehicles.set_thumbnail(url=_rank_data[1])
        _e_vehicles.add_field(name="LAVs:", value=_player_data['lavd'], inline=True)
        _e_vehicles.add_field(name="MAVs:", value=_player_data['mavd'], inline=True)
        _e_vehicles.add_field(name="HAVs:", value=_player_data['havd'], inline=True)
        _e_vehicles.add_field(name="Helicopters:", value=_player_data['hed'], inline=True)
        _e_vehicles.add_field(name="Boats:", value=_player_data['bod'], inline=True)
        _e_vehicles.set_footer(text="BFMCspy Official Stats")
        _embeds[_title] = _e_vehicles
        _select_options.append(
            discord.SelectOption(
                label=_title,
                description="Different types of vehicles destroyed",
                emoji="🚁"
            )
        )
        # Kit Stats
        _title = "Kit Stats"
        _desc = f"***{_rank_data[0]}***"
        _desc += f"\n### {_title}:"
        _e_kits = discord.Embed(
            title=_escaped_nickname,
            description=_desc,
            color=_color
        )
        _e_kits.set_author(
            name=_author_name, 
            icon_url=_author_url
        )
        _e_kits.set_thumbnail(url=_rank_data[1])
        _e_kits.add_field(name="Favorite Kit:", value=_fav_kit, inline=False)
        _e_kits.add_field(name="Assult Kills:", value=_player_data['lavd'], inline=True)
        _e_kits.add_field(name="Sniper Kills:", value=_player_data['mavd'], inline=True)
        _e_kits.add_field(name="Special Op. Kills:", value=_player_data['havd'], inline=True)
        _e_kits.add_field(name="Combat Engineer Kills:", value=_player_data['hed'], inline=True)
        _e_kits.add_field(name="Support Kills:", value=_player_data['bod'], inline=True)
        _e_kits.set_footer(text="BFMCspy Official Stats")
        _embeds[_title] = _e_kits
        _select_options.append(
            discord.SelectOption(
                label=_title,
                description="Various kit statistics",
                emoji="🎒"
            )
        )

        await ctx.respond(embed=_embeds["Summary"], view=PlayerStatsView(_select_options, _embeds))

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
    leaderboard = stats.create_subgroup("leaderboard", "Commands related to checking the  leaderboard for various player stats")

    @leaderboard.command(name = "score", description="See a leaderboard of the top scoring players of BF2:MC Online")
    @commands.cooldown(1, 180, commands.BucketType.channel)
    async def score(self, ctx):
        """Slash Command: /stats leaderboard score
        
        Displays a leaderboard of the top scoring players of BF2:MC Online.
        """
        paginator = self.get_paginator_for_stat('score')
        await paginator.respond(ctx.interaction)

    @leaderboard.command(name = "wins", description="See a leaderboard of the top winning players of BF2:MC Online")
    @commands.cooldown(1, 180, commands.BucketType.channel)
    async def wins(self, ctx):
        """Slash Command: /stats leaderboard wins
        
        Displays a leaderboard of the top winning players of BF2:MC Online.
        """
        paginator = self.get_paginator_for_stat('wins')
        await paginator.respond(ctx.interaction)

    @leaderboard.command(name = "mvp", description="See a leaderboard of players who were MVP in their games of BF2:MC Online")
    @commands.cooldown(1, 180, commands.BucketType.channel)
    async def mvp(self, ctx):
        """Slash Command: /stats leaderboard mvp
        
        Displays a leaderboard of players who were MVP in their games of BF2:MC Online.
        """
        paginator = self.get_paginator_for_stat('top_player')
        await paginator.respond(ctx.interaction)

    @leaderboard.command(name = "pph", description="See a leaderboard of players with the most points earned per hour on BF2:MC Online")
    @commands.cooldown(1, 180, commands.BucketType.channel)
    async def pph(self, ctx):
        """Slash Command: /stats leaderboard pph
        
        Displays a leaderboard of players with the most points earned per hour on BF2:MC Online.
        """
        paginator = self.get_paginator_for_stat('pph')
        await paginator.respond(ctx.interaction)

    @leaderboard.command(name = "playtime", description="See a leaderboard of players with the most hours played on BF2:MC Online")
    @commands.cooldown(1, 180, commands.BucketType.channel)
    async def playtime(self, ctx):
        """Slash Command: /stats leaderboard playtime
        
        Displays a leaderboard of players with the most hours played on BF2:MC Online.
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
        
        _dbEntries = self.bot.db_discord.getAll(
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
        _dbEntries = self.bot.db_discord.getAll("player_stats", ["id"])

        _total_players = 0
        if _dbEntries != None:
            _total_players = len(_dbEntries)
        
        _embed = discord.Embed(
            title=f"👥︎  Total Player Count (All-Time)",
            description=f"I have tracked **{_total_players}** unique nicknames play at least one game since {STATS_EPOCH_DATE_STR}*",
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
        _dbEntries = self.bot.db_discord.getAll("map_stats", ["conquest", "capturetheflag"])

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
            autocomplete=discord.utils.basic_autocomplete(get_uniquenicks), 
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
        _dbEntry = self.bot.db_discord.getOne(
            "player_stats", 
            ["id"], 
            ("dis_uid=%s", [ctx.author.id])
        )
        # Check if author already has a claimed nickname
        if not _dbEntry:
            _dbEntry = self.bot.db_discord.getOne(
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
                _str1 = f':warning: We have not seen the nickname of "{_escaped_nickname}" play BF2:MC Online since {STATS_EPOCH_DATE_STR}.'
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
            autocomplete=discord.utils.basic_autocomplete(get_uniquenicks), 
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
        _dbEntry = self.bot.db_discord.getOne(
            "player_stats", 
            ["id", "dis_uid"], 
            ("nickname=%s", [nickname])
        )
        _escaped_nickname = self.bot.escape_discord_formatting(nickname)
        # Check if the author owns the nickname
        if _dbEntry and _dbEntry['dis_uid'] == ctx.author.id:
            self.bot.db_discord.update(
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
            autocomplete=discord.utils.basic_autocomplete(get_uniquenicks), 
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
            return await ctx.respond(_msg, ephemeral=True)
        
        _dbEntry = self.bot.db_discord.getOne(
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
            self.bot.db_discord.update(
                "player_stats", 
                {"dis_uid": _uid}, 
                [f"id={_dbEntry['id']}"]
            )
            self.bot.log(f'[PlayerStats] {ctx.author.name}#{ctx.author.discriminator} has assigned the nickname of "{nickname}" to {member.display_name}.')
            await ctx.respond(f':white_check_mark: {member.name} has successfully been assigned as the owner of nickname "{_escaped_nickname}"!', ephemeral=True)
        else:
            await ctx.respond(f':warning: I have not seen a player by the nickname of "{_escaped_nickname}" play BF2:MC Online since {STATS_EPOCH_DATE_STR}.', ephemeral=True)
    
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
        _dbEntries = self.bot.db_discord.getAll(
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
            autocomplete=discord.utils.basic_autocomplete(get_uniquenicks), 
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
            return await ctx.respond(":warning: You do not have permission to run this command.", ephemeral=True)
        
        # Get existing nickname PID (if it exists)
        _dbPID = self.bot.db_discord.getOne(
            "player_stats", ["pid"], ("nickname=%s", [nickname])
        )
        # Get existing blacklist entry (if it exists)
        _dbEntry = self.bot.db_discord.getOne(
            "player_blacklist", ["id"], ("nickname=%s", [nickname])
        )
        _escaped_nickname = self.bot.escape_discord_formatting(nickname)
        # Add nickname
        if action == "Add":
            if not _dbEntry:
                _pid = None
                if _dbPID:
                    _pid = _dbPID['pid']
                self.bot.db_discord.insert(
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
                self.bot.db_discord.delete(
                    "player_blacklist", 
                    ("id = %s", [_dbEntry['id']])
                )
                self.bot.log(f'[PlayerStats] {ctx.author.name}#{ctx.author.discriminator} has removed the nickname of "{nickname}" from the blacklist.')
                await ctx.respond(f':white_check_mark: Removed "{_escaped_nickname}" from the blacklist.')
            else:
                await ctx.respond(f':warning: Could not find "{_escaped_nickname}" in the blacklist.', ephemeral=True)


class PlayerStatsView(discord.ui.View):
    """TODO
    
    """
    def __init__(self, select_options: list[discord.SelectOption], embeds: dict):
        super().__init__(disable_on_timeout=True)
        self.embeds = embeds
        self.select_callback.placeholder = select_options[0].label
        self.select_callback.options = select_options
    
    @discord.ui.select(
        min_values = 1,
        max_values = 1
    )
    async def select_callback(self, select, interaction): # the function called when the user is done selecting options
        select.placeholder = select.values[0]
        await interaction.response.edit_message(
            embed=self.embeds[select.values[0]], 
            view=self
        )


def setup(bot):
    """Called by Pycord to setup the cog"""
    cog = CogPlayerStats(bot)
    cog.guild_ids = [bot.config['GuildID']]
    bot.add_cog(cog)
