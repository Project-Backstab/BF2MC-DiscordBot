"""CogPlayerStats.py

Handles tasks related to checking player stats and info.
Date: 10/05/2023
Authors: David Wolfe (Red-Thirten)
Licensed under GNU GPLv3 - See LICENSE for more details.
"""

from datetime import datetime

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
                "discord_uid BIGINT NOT NULL, "
                "discord_name VARCHAR(32) NOT NULL"
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
    
    """
    def time_to_sec(self, time: str) -> int:
        # (DEPRECIATED) Turns a time string into seconds as an integer
        hours, minutes, seconds = time.split(':')
        return int(hours) * 3600 + int(minutes) * 60 + int(seconds)
    """
    
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

        TODO / Missing:
        Teams played
        Gamemodes played
        """
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
                    "hed`",     # Total Helicopters destroyed
                    "bod`",     # Total Boats destoyed
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
                    "ngp"       # Total game sessions
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

        ## Get Discord data (if availible)
        _discord_data = self.bot.db_backend.leftJoin(
            ("DiscordUserLinks", "ProfileCustomization"),
            (
                ["discord_uid"],
                ["color_r", "color_g", "color_b"]
            ),
            ("profileid", "profileid"),
            ("profileid=%s", [_player_data['profileid']])
        )
        if _discord_data != None: # Clean up result
            if len(_discord_data) > 0:
                _discord_data = _discord_data[0]
            else:
                _discord_data = None
        
        ## Get match history data
        _match_history_data = self.bot.db_backend.call(
            "queryGameStatsResults",
            [_player_data['profileid']]
        )

        ## DEBUGGING
        print(f"Player Data:\n{_player_data}\n")
        print(f"Discord Data:\n{_discord_data}\n")
        print(f"Match History:\n{_match_history_data}\n")
        await ctx.respond("Debug info printed to console.")

        # _rank_data = CS.get_rank_data(_dbEntry['score'], _dbEntry['pph'])
        # _total_games = _dbEntry['cq_games'] + _dbEntry['cf_games']
        # # Determine favorite gamemode
        # _fav_gamemode = CS.GM_STRINGS['conquest'] # Default
        # if _dbEntry['cf_games'] > _dbEntry['cq_games']:
        #     _fav_gamemode = CS.GM_STRINGS['capturetheflag']
        # # Determine favorite team
        # _team_games = {
        #     CS.TEAM_STRINGS['US'][:-1]: _dbEntry['us_games'],
        #     CS.TEAM_STRINGS['CH'][:-1]: _dbEntry['ch_games'],
        #     CS.TEAM_STRINGS['AC'][:-1]: _dbEntry['ac_games'],
        #     CS.TEAM_STRINGS['EU'][:-1]: _dbEntry['eu_games']
        # }
        # _fav_team = max(_team_games, key=_team_games.get)
        # # Determine earned ribbons
        # _ribbons = ""
        # if _total_games >= 50:
        #     _ribbons += self.bot.config['Emoji']['Ribbons']['GamesPlayed50']
        # if _total_games >= 250:
        #     _ribbons += self.bot.config['Emoji']['Ribbons']['GamesPlayed250']
        # if _total_games >= 500:
        #     _ribbons += self.bot.config['Emoji']['Ribbons']['GamesPlayed500']
        # if _dbEntry['wins'] >= 5:
        #     _ribbons += self.bot.config['Emoji']['Ribbons']['Victories5']
        # if _dbEntry['wins'] >= 20:
        #     _ribbons += self.bot.config['Emoji']['Ribbons']['Victories20']
        # if _dbEntry['wins'] >= 50:
        #     _ribbons += self.bot.config['Emoji']['Ribbons']['Victories50']
        # if _dbEntry['top_player'] >= 5:
        #     _ribbons += self.bot.config['Emoji']['Ribbons']['TopPlayer5']
        # if _dbEntry['top_player'] >= 20:
        #     _ribbons += self.bot.config['Emoji']['Ribbons']['TopPlayer20']
        # if _ribbons == "": _ribbons = "None"
        # # Calculate average score per game
        # if _total_games < 1: _total_games = 1 # Div. by 0 safeguard
        # _avg_score_per_game = _dbEntry['score'] / _total_games
        # _avg_score_per_game = round(_avg_score_per_game, 2)
        # # Calculate average score per life
        # _lives = _dbEntry['deaths']
        # if _lives < 1: _lives = 1 # Div. by 0 safeguard
        # _avg_score_per_life = _dbEntry['score'] / _lives
        # _avg_score_per_life = round(_avg_score_per_life, 2)
        # # Calculate win percentage
        # _win_percentage = (_dbEntry['wins'] / _total_games) * 100
        # _win_percentage = round(_win_percentage, 2)
        # _win_percentage = str(_win_percentage) + "%"
        # # Calculate play time in hours
        # _play_time = int(_dbEntry['playtime'] / SECONDS_PER_HOUR)
        # _play_time = self.bot.infl.no('hour', _play_time)
        # # Build match history string
        # _match_history = ""
        # for _c in _dbEntry['match_history']:
        #     if _c == 'W':
        #         _match_history += self.bot.config['Emoji']['MatchHistory']['Win'] + " "
        #     elif _c == 'L':
        #         _match_history += self.bot.config['Emoji']['MatchHistory']['Loss'] + " "
        #     elif _c == 'D':
        #         _match_history += self.bot.config['Emoji']['MatchHistory']['Draw'] + " "
        # if _match_history != "":
        #     _match_history = "Past ⏪ " + _match_history + "⏪ Recent"
        # else:
        #     _match_history = "None"
        # # Determine embed color
        # if _dbEntry['color_r']:
        #     _color = discord.Colour.from_rgb(_dbEntry['color_r'], _dbEntry['color_g'], _dbEntry['color_b'])
        # else:
        #     _color = discord.Colour.random(seed=_dbEntry['id'])
        # # Set owner if applicable
        # _author_name = "BF2:MC Online  |  Player Stats"
        # _author_url = "https://raw.githubusercontent.com/lilkingjr1/backstab-discord-bot/main/assets/icon.png"
        # if _dbEntry['dis_uid']:
        #     _owner = self.bot.get_user(_dbEntry['dis_uid'])
        #     if _owner:
        #         _author_name = f"{_owner.display_name}'s Player Stats"
        #         _author_url = _owner.display_avatar.url
        # # Build embed
        # _embed = discord.Embed(
        #     title=_escaped_nickname,
        #     description=f"*{_rank_data[0]}*",
        #     color=_color
        # )
        # _embed.set_author(
        #     name=_author_name, 
        #     icon_url=_author_url
        # )
        # _embed.set_thumbnail(url=_rank_data[1])
        # _embed.add_field(name="Ribbons:", value=_ribbons, inline=False)
        # _embed.add_field(name="PPH:", value=int(_dbEntry['pph']), inline=True)
        # _embed.add_field(name="Total Score:", value=_dbEntry['score'], inline=True)
        # _embed.add_field(name="MVP:", value=self.bot.infl.no('game', _dbEntry['top_player']), inline=True)
        # _embed.add_field(name="Avg. Score/Game:", value=_avg_score_per_game, inline=True)
        # _embed.add_field(name="Avg. Score/Life:", value=_avg_score_per_life, inline=True)
        # _embed.add_field(name="Play Time:", value=_play_time, inline=True)
        # _embed.add_field(name="Total Games:", value=_total_games, inline=True)
        # _embed.add_field(name="Games Won:", value=_dbEntry['wins'], inline=True)
        # _embed.add_field(name="Win Percentage:", value=_win_percentage, inline=True)
        # _embed.add_field(name="Match Result History:", value=_match_history, inline=False)
        # _embed.add_field(name="Favorite Team:", value=_fav_team, inline=True)
        # _embed.add_field(name="Favorite Gamemode:", value=_fav_gamemode, inline=True)
        # _embed.set_footer(text=f"First seen online: {_dbEntry['first_seen'].strftime('%m/%d/%Y')} -- Unofficial data*")
        # await ctx.respond(embed=_embed)

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
            await ctx.respond(_msg, ephemeral=True)
            return
        
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
            await ctx.respond(":warning: You do not have permission to run this command.", ephemeral=True)
            return
        
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

def setup(bot):
    """Called by Pycord to setup the cog"""
    cog = CogPlayerStats(bot)
    cog.guild_ids = [bot.config['GuildID']]
    bot.add_cog(cog)
