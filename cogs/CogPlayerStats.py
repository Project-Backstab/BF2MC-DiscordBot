"""CogPlayerStats.py

Handles tasks related to checking player stats and info.
Date: 03/30/2024
Authors: David Wolfe (Red-Thirten)
Licensed under GNU GPLv3 - See LICENSE for more details.
"""

import hashlib
from urllib.parse import quote as url_escape

import discord
from discord.ext import commands
from discord.ext.pages import Paginator, Page
import common.CommonStrings as CS

SECONDS_PER_HOUR = 60.0 * 60.0


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

    def is_medal_earned(self, earned_medals: int, medal_name: str) -> bool:
        if medal_name not in CS.MEDALS_DATA:
            return False
        return earned_medals & CS.MEDALS_DATA[medal_name][0] == CS.MEDALS_DATA[medal_name][0]

    def get_num_medals_earned(self, earned_medals: int) -> int:
        return bin(earned_medals)[2:].count("1")
    
    def get_profileid_for_nick(self, uniquenick: str) -> int:
        """Returns a profile ID for a given unique nickname, or None if the nickname doesn't exist."""
        _dbEntry = self.bot.db_backend.getOne(
            "Players", 
            ["profileid"], 
            ("uniquenick=%s", [uniquenick])
        )
        if _dbEntry:
            return _dbEntry['profileid']
        else:
            return None

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
            ["dis_uid", "color_r", "color_g", "color_b", "first_seen"], 
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
            ("profileid=%s and patchid=%s", [_cur_player['profileid'], 1])
        )
        if _legacy_patch == None:
            self.bot.db_discord.insert(
                "PlayerPatches", 
                {
                    "profileid": _cur_player['profileid'], 
                    "patchid": 1, 
                    "date_earned": _legacy_data['first_seen']
                }
            )
        return True


    @commands.Cog.listener()
    async def on_ready(self):
        """Listener: On Cog Ready
        
        Runs when the cog is successfully cached within the Discord API.
        """
        self.bot.log("[PlayerStats] Successfully cached!")


    """Slash Command Group: /player
    
    A group of commands related to checking player stats.
    """
    player = discord.SlashCommandGroup("player", "Commands related to checking player stats")

    @player.command(name = "stats", description="Displays a specific player's BF2:MC Online stats")
    @commands.cooldown(1, 180, commands.BucketType.member)
    async def stats(
        self,
        ctx,
        nickname: discord.Option(
            str, 
            description="Nickname of player to look up", 
            autocomplete=discord.utils.basic_autocomplete(get_uniquenicks), 
            max_length=255, 
            required=True
        ) # type: ignore
    ):
        """Slash Command: /player stats
        
        Displays a specific player's BF2:MC Online stats.
        """
        await ctx.defer() # Temp fix for slow SQL queries
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
        if _player_data == None or _player_data[0]['score'] == None:
            return await ctx.respond(
                f':warning: An account with the nickname of "{_escaped_nickname}" could not be found.', 
                #ephemeral=True
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
        
        ## Get match match history, sorted by date
        _match_history_data = self.bot.db_backend.call(
            "queryPlayerGameResults",
            [_player_data['profileid']]
        )
        # Remove games where the player did not select a team
        _match_history_data = [_m for _m in _match_history_data if _m[1] != -1]

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
        _rank_data = CS.RANK_DATA[_player_data['ran'] - 1]
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
                _patchid_str = str(_p['patchid'])
                try:
                    _patches_emoji += self.bot.config['Patches'][_patchid_str][2] + " "
                except Exception:
                    self.bot.log(f"[PlayerStats] WARNING: PatchID {_patchid_str} not found in config! Skipping.")
        if _patches_emoji == "": _patches_emoji = None
        # Calculate K/D ratio
        _kd_ratio = _player_data['kills'] / max(_player_data['deaths'], 1)
        _kd_ratio = round(_kd_ratio, 2)
        # Calculate average score per game
        _avg_score_per_game = _player_data['score'] / max(_player_data['ngp'], 1)
        _avg_score_per_game = round(_avg_score_per_game, 2)
        # Calculate win percentage
        _wins = 0
        for _m in _match_history_data:
            if _m[2] in [1, 2]:
                _wins += 1
        _win_percentage = (_wins / max(len(_match_history_data), 1)) * 100
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
        for _m in reversed(_match_history_data[:10]):
            if _m[2] in [1, 2]: # Major or Minor Victory
                _match_history += self.bot.config['Emoji']['MatchHistory']['Win'] + " "
            elif _m[2] == 0: #Loss
                _match_history += self.bot.config['Emoji']['MatchHistory']['Loss'] + " "
            elif _m[2] == 3: # Draw
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
        _author_url = CS.BOT_ICON_URL
        if _discord_data:
            _owner = self.bot.get_user(_discord_data['discord_uid'])
            if _owner:
                _author_name = f"{_owner.display_name}'s Player Stats"
                _author_url = _owner.display_avatar.url
        # Set clan if applicable
        _clan_name = ""
        if len(_clan_data) > 0:
            _escaped_nickname = f"{_clan_data[0][2]} {_escaped_nickname}"
            _clan_name = self.bot.escape_discord_formatting(_clan_data[0][1])
            _clan_name = f"\nMember of {_clan_name}"
        
        ## Build embeds/pages
        _embeds = {}
        _select_options = []
        # Summary
        _title = "Summary"
        _e_summary = discord.Embed(
            title=_escaped_nickname,
            description=f"***{_rank_data[0]}***{_clan_name}",
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
        _e_summary.add_field(name="PPH:", value=round(_player_data['pph']/100), inline=True)
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
                try:
                    _e_patches.add_field(
                        name=f"{self.bot.config['Patches'][str(_p['patchid'])][2]} {self.bot.config['Patches'][str(_p['patchid'])][0]}:", 
                        value=f"*Earned: {_p['date_earned'].strftime('%m/%d/%y')}*\n{self.bot.config['Patches'][str(_p['patchid'])][1]}", 
                        inline=False
                    )
                except Exception:
                    pass
            _e_patches.set_footer(text="BFMCspy Official Stats")
            _embeds[_title] = _e_patches
            _emoji = self.bot.config['Patches']['1'][2]
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
        _e_kits.add_field(name="Favorite Kit (Most Spawns):", value=_fav_kit, inline=False)
        _e_kits.add_field(name="Assult Kills:", value=_player_data['k1'], inline=True)
        _e_kits.add_field(name="Sniper Kills:", value=_player_data['k2'], inline=True)
        _e_kits.add_field(name="Special Op. Kills:", value=_player_data['k3'], inline=True)
        _e_kits.add_field(name="Combat Engineer Kills:", value=_player_data['k4'], inline=True)
        _e_kits.add_field(name="Support Kills:", value=_player_data['k5'], inline=True)
        _e_kits.set_footer(text="BFMCspy Official Stats")
        _embeds[_title] = _e_kits
        _select_options.append(
            discord.SelectOption(
                label=_title,
                description="Various kit statistics",
                emoji="🎒"
            )
        )

        await ctx.respond(embed=_embeds["Summary"], view=self.PlayerStatsView(_select_options, _embeds))
    
    class PlayerStatsView(discord.ui.View):
        """Discord UI View: Player Stats
        
        Handles the `/player stats` view which includes a select menu of passed options
        to display various passed embed "pages".
        Automatically disables list selections after 180 sec.
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
    
    @player.command(name = "self", description="Displays BF2:MC Online stats for a nickname you own")
    async def self(
        self,
        ctx,
        nickname: discord.Option(
            str, 
            description="Nickname to display stats for", 
            autocomplete=discord.utils.basic_autocomplete(get_owned_uniquenicks), 
            max_length=255, 
            required=True
        ) # type: ignore
    ):
        """Slash Command: /player self
        
        Alias for `/player stats`, but autocomplete only shows owned nicknames.
        """
        return await self.stats(ctx, nickname)

    @player.command(name = "leaderboard", description="See a top 50 leaderboard for a particular stat in BF2:MC Online")
    @commands.cooldown(8, 300, commands.BucketType.channel)
    async def leaderboard(
        self,
        ctx,
        stat: discord.Option(
            str, 
            name="leaderboard", 
            description="Leaderboard to display", 
            choices=[
                discord.OptionChoice(CS.LEADERBOARD_STRINGS['`rank`'], value='`rank`'),
                discord.OptionChoice(CS.LEADERBOARD_STRINGS['score'], value='score'),
                discord.OptionChoice(CS.LEADERBOARD_STRINGS['mv'], value='mv'),
                discord.OptionChoice(CS.LEADERBOARD_STRINGS['ttb'], value='ttb'),
                discord.OptionChoice(CS.LEADERBOARD_STRINGS['pph'], value='pph'),
                discord.OptionChoice(CS.LEADERBOARD_STRINGS['time'], value='time'),
                discord.OptionChoice(CS.LEADERBOARD_STRINGS['kills'], value='kills'),
                discord.OptionChoice(CS.LEADERBOARD_STRINGS['vehicles'], value='vehicles')
            ], 
            required=True
        ) # type: ignore
    ):
        """Slash Command: /player leaderboard
        
        Displays a top 50 leaderboard of the specified BF2:MC Online stat.
        """
        _rank = 1
        _pages = []
        _db_table = "PlayerStats"
        _db_columns = [stat]
        _order = "DESC"
        if stat == '`rank`': # Special query for overall rank
            _db_table = "Leaderboard_rank"
            _db_columns = ["ran"]
            _order = "ASC"
        _dbEntries = self.bot.db_backend.leftJoin(
            (_db_table, "Players"), 
            (
                _db_columns, 
                ["uniquenick"]
            ), 
            ("profileid", "profileid"), 
            None, 
            [stat, _order], # Order highest first
            [50] # Limit to top 50 players
        )
        _title = f":first_place:  BF2:MC Online | Top Player {CS.LEADERBOARD_STRINGS[stat]} Leaderboard  :first_place:"
        if _dbEntries:
            _dbEntries = self.bot.split_list(_dbEntries, 10) # Split into pages of 10 entries each
            for _page in _dbEntries:
                _embed = discord.Embed(
                    title=_title,
                    description="*Top 50 players across all servers.*",
                    color=discord.Colour.gold()
                )
                _nicknames = "```\n"
                _stats = "```\n"
                for _e in _page:
                    _rank_str = f"#{_rank}"
                    _nicknames += f"{_rank_str.ljust(3)} | {_e['uniquenick']}\n"
                    if stat == '`rank`':
                        _stats += f"{CS.RANK_DATA[_e['ran']-1][0].rjust(21)}\n"
                    elif stat == 'score':
                        _stats += f"{str(_e[stat]).rjust(6)} pts.\n"
                    elif stat == 'mv':
                        _stats += f" {self.bot.infl.no('game', _e[stat])} won\n"
                    elif stat == 'ttb':
                        _stats += f" {self.bot.infl.no('game', _e[stat])}\n"
                    elif stat == 'pph':
                        _stats += f"{str(round(_e[stat]/100)).rjust(4)} PPH\n"
                    elif stat == 'time':
                        _stats += f"{str(int(_e[stat]/SECONDS_PER_HOUR)).rjust(5)} hrs.\n"
                    elif stat == 'kills':
                        _stats += f"{str(_e[stat]).rjust(8)}\n"
                    elif stat == 'vehicles':
                        _stats += f"{str(_e[stat]).rjust(6)} destroyed\n"
                    else:
                        _stats += "\n"
                    _rank += 1
                _nicknames += "```"
                _stats += "```"
                _embed.add_field(name="Player:", value=_nicknames, inline=True)
                _embed.add_field(name=f"{CS.LEADERBOARD_STRINGS[stat]}:", value=_stats, inline=True)
                _embed.set_footer(text="BFMCspy Official Stats")
                _pages.append(Page(embeds=[_embed]))
        else:
            _embed = discord.Embed(
                title=_title,
                description="No stats yet.",
                color=discord.Colour.gold()
            )
            _pages = [Page(embeds=[_embed])]
        _paginator = Paginator(pages=_pages, author_check=False)
        await _paginator.respond(ctx.interaction)
    
    @player.command(name = "message", description="Send an in-game message to an online BF2:MC player. Only admins can do this.")
    async def player_message(
        self, 
        ctx,
        nickname: discord.Option(
            str, 
            description='BF2:MC Online nickname (or "all" to message all players)', 
            autocomplete=discord.utils.basic_autocomplete(get_uniquenicks), 
            max_length=255, 
            required=True
        ), # type: ignore
        message: discord.Option(
            str, 
            description="Message to send", 
            max_length=255, 
            required=True
        ) # type: ignore
    ):
        """Slash Command: /player message
        
        Sends an in-game message to an online BF2:MC player. Only admins can do this.
        """
        # Only members with Manage Channels permission can use this command.
        if not ctx.author.guild_permissions.manage_channels:
            _msg = ":warning: You do not have permission to run this command."
            return await ctx.respond(_msg, ephemeral=True)
        
        await ctx.defer(ephemeral=True) # Temp fix for slow SQL queries

        # Get and check profile ID for nickname (if specified)
        _escaped_nickname = self.bot.escape_discord_formatting(nickname)
        _profileid = None
        if nickname.lower() != "all":
            _profileid = self.get_profileid_for_nick(nickname)
            if _profileid == None:
                return await ctx.respond(
                    f':warning: An account with the nickname of "{_escaped_nickname}" could not be found.', 
                    ephemeral=True
                )
        
        # Send message and report if successful
        _response = await self.bot.query_api(
            "admin/message", 
            password=self.bot.config['API']['Password'], 
            message=url_escape(message), 
            profileid=_profileid
        )
        if _response:
            if _response['result'] == 'OK':
                self.bot.log(f'[Admin] {ctx.author.name} sent the following in-game message to {nickname}:\n\t"{message}"')
                return await ctx.respond(
                    f":white_check_mark: Message sent to {_escaped_nickname}!", 
                    ephemeral=True
                )
            else:
                return await ctx.respond(
                    f":warning: Unable to send message to {_escaped_nickname} because they are not currently online.", 
                    ephemeral=True
                )
        else:
            return await ctx.respond(
                f":warning: Message send failed! (See console for more details)", 
                ephemeral=True
            )
    
    @player.command(name = "kick", description="Kick an online BF2:MC player. Only admins can do this.")
    async def player_kick(
        self, 
        ctx,
        nickname: discord.Option(
            str, 
            description='BF2:MC Online nickname', 
            autocomplete=discord.utils.basic_autocomplete(get_uniquenicks), 
            max_length=255, 
            required=True
        ) # type: ignore
    ):
        """Slash Command: /player kick
        
        Kicks an online BF2:MC player. Only admins can do this.
        """
        # Only members with Manage Channels permission can use this command.
        if not ctx.author.guild_permissions.manage_channels:
            _msg = ":warning: You do not have permission to run this command."
            return await ctx.respond(_msg, ephemeral=True)
        
        await ctx.defer(ephemeral=True) # Temp fix for slow SQL queries

        # Get and check profile ID for nickname
        _escaped_nickname = self.bot.escape_discord_formatting(nickname)
        _profileid = self.get_profileid_for_nick(nickname)
        if _profileid == None:
            return await ctx.respond(
                f':warning: An account with the nickname of "{_escaped_nickname}" could not be found.', 
                ephemeral=True
            )
        
        # Kick player and report if successful
        _response = await self.bot.query_api(
            "admin/kick", 
            password=self.bot.config['API']['Password'], 
            profileid=_profileid
        )
        if _response:
            if _response['result'] == 'OK':
                self.bot.log(f"[Admin] {ctx.author.name} kicked {nickname} from BFMCspy.")
                return await ctx.respond(
                    f":white_check_mark: Kicked {_escaped_nickname}!", 
                    ephemeral=True
                )
            else:
                return await ctx.respond(
                    f":warning: Unable to kick {_escaped_nickname} because they are not currently online.", 
                    ephemeral=True
                )
        else:
            return await ctx.respond(
                f":warning: Kick failed! (See console for more details)", 
                ephemeral=True
            )

    """Slash Command Sub-Group: /player nickname
    
    A sub-group of commands related to claiming, customizing, and moderating a nickname.
    """
    nickname = player.create_subgroup("nickname", "Commands related to claiming, customizing, and moderating a nickname")
    
    @nickname.command(name = "claim", description="Claim ownership of an existing nickname")
    @commands.cooldown(5, 300, commands.BucketType.member)
    async def claim(
        self, 
        ctx,
        nickname: discord.Option(
            str, 
            description="Nickname to claim", 
            autocomplete=discord.utils.basic_autocomplete(get_uniquenicks), 
            max_length=255, 
            required=True
        ), # type: ignore
        password: discord.Option(
            str, 
            description="BFMCspy login password for nickname", 
            required=True
        ) # type: ignore
    ):
        """Slash Command: /player nickname claim
        
        Allows the caller to associate their Discord account with an existing nickname
        in the database, which allows them to 'own' that nickname as their own.

        A caller can only claim a nickname if they provide the correct password
        for the nickname.
        """
        _escaped_nickname = self.bot.escape_discord_formatting(nickname)

        # Check if the nickname is valid and get its password
        _profile = self.bot.db_backend.getOne(
            "Players", 
            ["profileid", "password"], 
            ("uniquenick=%s", [nickname])
        )
        if _profile == None:
            return await ctx.respond(
                f':warning: An account with the nickname of "{_escaped_nickname}" could not be found.', 
                ephemeral=True
            )

        # Check password
        _hash = hashlib.md5(password.encode()).hexdigest()
        if _hash != _profile['password']:
            _response = f':warning: Wrong password provided for "{_escaped_nickname}"!'
            _response += "\n\nPlease try again or contact an admin if you need help."
            return await ctx.respond(_response, ephemeral=True)
        
        # Insert or update Discord user link
        self.bot.db_discord.insertOrUpdate(
            "DiscordUserLinks", 
            {
                "profileid": _profile['profileid'],
                "discord_uid": ctx.author.id
            }, 
            ["profileid"]
        )
        self.bot.log(f'[PlayerStats] {ctx.author.name}#{ctx.author.discriminator} has claimed the nickname "{nickname}".')
        _response = f':white_check_mark: Nickname "{_escaped_nickname}" has successfully been claimed!'
        _response += "\n\nYour Discord name will now display alongside the nickname's stats."
        _response += "\nYou can also change your stats profile to a unique color with `/player nickname color` if you wish."
        return await ctx.respond(_response, ephemeral=True)
    
    @nickname.command(name = "color", description="Change the stats profile color for a nickname you own")
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def color(
        self, 
        ctx, 
        nickname: discord.Option(
            str, 
            description="Nickname you own", 
            autocomplete=discord.utils.basic_autocomplete(get_owned_uniquenicks), 
            max_length=255, 
            required=True
        ),  # type: ignore
        red: discord.Option(
            int, 
            description="Red Value | 0-255", 
            min_value=0, 
            max_value=255, 
            required=True
        ),  # type: ignore
        green: discord.Option(
            int, 
            description="Green Value | 0-255", 
            min_value=0, 
            max_value=255, 
            required=True
        ),  # type: ignore
        blue: discord.Option(
            int, 
            description="Blue Value | 0-255", 
            min_value=0, 
            max_value=255, 
            required=True
        ) # type: ignore
    ):
        """Slash Command: /player nickname color
        
        Changes the stats embed color in the database for a given nickname if the author owns said nickname.
        """
        _escaped_nickname = self.bot.escape_discord_formatting(nickname)

        # Check nickname exists
        _profileid = self.get_profileid_for_nick(nickname)
        if _profileid == None:
            return await ctx.respond(
                f':warning: An account with the nickname of "{_escaped_nickname}" could not be found.', 
                ephemeral=True
            )
        
        # Check nickname is owned by command caller
        _discord_uid = self.bot.db_discord.getOne(
            "DiscordUserLinks", 
            ["discord_uid"], 
            ("profileid=%s", [_profileid])
        )
        if _discord_uid == None or _discord_uid['discord_uid'] != ctx.author.id:
            return await ctx.respond(f':warning: You do not own the nickname "{_escaped_nickname}"\n\nPlease use `/player nickname claim` to claim it first.', ephemeral=True)
        
        # Insert or update profile customization colors
        self.bot.db_discord.insertOrUpdate(
            "ProfileCustomization", 
            {
                "profileid": _profileid,
                "color_r": red, 
                "color_g": green, 
                "color_b": blue
            }, 
            ["profileid"]
        )
        await ctx.respond(f'Successfully changed the stats profile color to ({red}, {green}, {blue}) for "{_escaped_nickname}"!', ephemeral=True)
    
    @nickname.command(name = "assign", description="Assigns a Discord member to a nickname. Only admins can do this.")
    async def assign(
        self, 
        ctx,
        member: discord.Option(
            discord.Member, 
            description="Discord member (Set to BackStab bot to remove ownership)"
        ),  # type: ignore
        nickname: discord.Option(
            str, 
            description="BF2:MC Online nickname", 
            autocomplete=discord.utils.basic_autocomplete(get_uniquenicks), 
            max_length=255, 
            required=True
        ) # type: ignore
    ):
        """Slash Command: /player nickname assign
        
        Assigns a Discord member to be the owner of a nickname. Only admins can do this.
        """
        # Only members with Manage Channels permission can use this command.
        if not ctx.author.guild_permissions.manage_channels:
            _msg = ":warning: You do not have permission to run this command."
            _msg += "\n\nPlease try using `/player nickname claim`, or contact an admin if you need to claim another nickname."
            return await ctx.respond(_msg, ephemeral=True)
        
        _escaped_nickname = self.bot.escape_discord_formatting(nickname)
        _profileid = self.get_profileid_for_nick(nickname)
        if _profileid == None:
            return await ctx.respond(
                f':warning: An account with the nickname of "{_escaped_nickname}" could not be found.', 
                ephemeral=True
            )
        
        # Assign if real member, or remove if bot
        if member != self.bot.user:
            self.bot.db_discord.insertOrUpdate(
                "DiscordUserLinks", 
                {"profileid": _profileid, "discord_uid": member.id}, 
                ["profileid"]
            )
        else:
            self.bot.db_discord.delete(
                "DiscordUserLinks",
                ("profileid = %s", [_profileid])
            )
            self.bot.db_discord.delete(
                "ProfileCustomization",
                ("profileid = %s", [_profileid])
            )
        self.bot.log(f'[PlayerStats] {ctx.author.name}#{ctx.author.discriminator} has assigned the nickname of "{nickname}" to {member.name}.')
        await ctx.respond(f':white_check_mark: {member.display_name} has successfully been assigned as the owner of nickname "{_escaped_nickname}"!', ephemeral=True)
    
    @nickname.command(name = "ownedby", description="See which nicknames are owned by a given Discord member")
    @commands.cooldown(1, 60, commands.BucketType.channel)
    async def ownedby(
        self, 
        ctx,
        member: discord.Option(
            discord.Member, 
            description="Discord member"
        ) # type: ignore
    ):
        """Slash Command: /player nickname ownedby
        
        Displays which nicknames are owned by a given Discord member.
        """
        _member_name = self.bot.escape_discord_formatting(member.display_name)

        _owned_profiles = self.bot.db_discord.getAll(
            "DiscordUserLinks", 
            ["profileid"], 
            ("discord_uid = %s", [member.id])
        )
        if _owned_profiles == None:
            return await ctx.respond(f"{_member_name} has not claimed or been assigned any BF2:MC Online nicknames yet.", ephemeral=True)

        _profiles_data = []
        for _op in _owned_profiles:
            _profile_data = self.bot.db_backend.getOne(
                "Players", 
                ["uniquenick", "created_at", "last_login"], 
                ("profileid = %s", [_op['profileid']])
            )
            _profiles_data.append(_profile_data)
        _nicknames = "```\n"
        _created = "```\n"
        _last_seen = "```\n"
        for _p in _profiles_data:
            _nicknames += f"{_p['uniquenick']}\n"
            _created += f"{_p['created_at'].strftime('%m/%d/%Y')}\n"
            _last_seen += f"{_p['last_login'].strftime('%m/%d/%Y')}\n"
        _nicknames += "```"
        _created += "```"
        _last_seen += "```"
        _embed = discord.Embed(
            title=f"{_member_name}'s BF2:MC Online Nicknames",
            color=member.color
        )
        _embed.set_thumbnail(url=member.display_avatar.url)
        _embed.add_field(name="Nicknames:", value=_nicknames, inline=True)
        _embed.add_field(name="Created:", value=_created, inline=True)
        _embed.add_field(name="Last Seen:", value=_last_seen, inline=True)
        _embed.set_footer(
            text="BF2:MC Online  |  Player Stats", 
            icon_url=CS.BOT_ICON_URL
        )
        await ctx.respond(embed=_embed)
    
    @nickname.command(name = "alts", description="Displays possible alt nicknames of a player. Only admins can do this.")
    async def alts(
        self, 
        ctx,
        nickname: discord.Option(
            str, 
            description="BF2:MC Online nickname", 
            autocomplete=discord.utils.basic_autocomplete(get_uniquenicks), 
            max_length=255, 
            required=True
        ) # type: ignore
    ):
        """Slash Command: /player nickname alts
        
        Displays possible alt nicknames of a player. Only admins can do this.
        """
        # Only members with Manage Channels permission can use this command.
        if not ctx.author.guild_permissions.manage_channels:
            _msg = ":warning: You do not have permission to run this command."
            return await ctx.respond(_msg, ephemeral=True)
        
        await ctx.defer(ephemeral=True) # Temp fix for slow SQL queries

        # Get IP and password hash of query nickname
        _escaped_nickname = self.bot.escape_discord_formatting(nickname)
        _nick_data = self.bot.db_backend.getOne(
            "Players", 
            ["last_login_ip", "password"], 
            ("uniquenick=%s", [nickname])
        )
        if _nick_data == None:
            return await ctx.respond(
                f':warning: An account with the nickname of "{_escaped_nickname}" could not be found.', 
                ephemeral=True
            )
        
        # Get all nicknames with same IP
        _alts_same_ip = self.bot.db_backend.getAll(
            "Players", 
            ["uniquenick"], 
            ("last_login_ip = %s and uniquenick != %s", [_nick_data['last_login_ip'], nickname])
        )
        if _alts_same_ip == None: _alts_same_ip = []
        # Get all nicknames with same password hash
        _alts_same_pass = self.bot.db_backend.getAll(
            "Players", 
            ["uniquenick"], 
            ("password = %s and uniquenick != %s", [_nick_data['password'], nickname])
        )
        if _alts_same_pass == None: _alts_same_pass = []
        _alts_both = [_alt for _alt in _alts_same_ip if _alt in _alts_same_pass]
        if _alts_both == None: _alts_both = []
        # Check if no alts found
        if len(_alts_same_ip) + len(_alts_same_pass) < 1:
            return await ctx.respond(
                f":information_source: {_escaped_nickname} likely doesn't have any alts.", 
                ephemeral=True
            )
        
        # Build embed
        _ip_list = "```\n"
        _pass_list = "```\n"
        _both_list = "```\n"
        for _alt in _alts_same_ip:
            _ip_list += f"{_alt['uniquenick']}\n"
        for _alt in _alts_same_pass:
            _pass_list += f"{_alt['uniquenick']}\n"
        for _alt in _alts_both:
            _both_list += f"{_alt['uniquenick']}\n"
        _ip_list += "```"
        _pass_list += "```"
        _both_list += "```"
        _embed = discord.Embed(
            title=f"{_escaped_nickname}'s Possible Alts",
            color=discord.Colour.blurple()
        )
        _embed.add_field(name="Based on IP (Likely):", value=_ip_list, inline=True)
        _embed.add_field(name="Based on Password (Less Likely):", value=_pass_list, inline=True)
        _embed.add_field(name="Both (Very Likely):", value=_both_list, inline=True)
        _embed.set_footer(text="BF2:MC Online  |  Player Stats (Confidential)", icon_url=CS.BOT_ICON_URL)
        await ctx.respond(embed=_embed, ephemeral=True)


def setup(bot):
    """Called by Pycord to setup the cog"""
    cog = CogPlayerStats(bot)
    cog.guild_ids = [bot.config['GuildID']]
    bot.add_cog(cog)
