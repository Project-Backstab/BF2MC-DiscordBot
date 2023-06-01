"""CogServerStatus.py

Handles tasks related to checking server status and info.
Date: 05/31/2023
Authors: David Wolfe (Red-Thirten)
Licensed under GNU GPLv3 - See LICENSE for more details.
"""

import json
import requests
from datetime import datetime

import discord
from discord.ext import commands, tasks
from discord.ext.pages import Paginator, Page
import inflect

ROOT_URL = "https://stats.bf2mc.net"
API_URL = "https://stats.bf2mc.net/api/servers/"
COUNTRY_FLAGS_URL = "https://stats.bf2mc.net/static/img/flags/<code>.png"
GM_THUMBNAILS_URL = "https://raw.githubusercontent.com/lilkingjr1/backstab-discord-bot/main/assets/gamemode_thumbnails/<gamemode>.png"
MAP_IMAGES_URL = "https://raw.githubusercontent.com/lilkingjr1/backstab-discord-bot/main/assets/map_images/<map_name>.png"
STATUS_ONLINE_STR = "SERVERS: ONLINE 🟢"
STATUS_OFFLINE_STR = "SERVERS: OFFLINE 🔴"
STATUS_ERROR_STR = "SERVERS: UNKNOWN"
GM_STRINGS = {
    "conquest": "Conquest",
    "capturetheflag": "Capture the Flag"
}
TEAM_STRINGS = {
    "US": ":flag_us:  United States:",
    "CH": ":flag_cn:  China:",
    "AC": ":flag_ir:  Middle Eastern Coalition:",
    "EU": ":flag_eu:  European Union:"
}
RANK_DATA = {
    (0, 25): ("Private", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/pv2.png"),
    (25, 50): ("Private 1st Class", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/pfc.png"),
    (50, 100): ("Corporal", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/cpl.png"),
    (100, 150): ("Sergeant", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/sgt.png"),
    (150, 225): ("Sergeant 1st Class", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/sfc.png"),
    (225, 360): ("Master Sergeant", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/msg.png"),
    (360, 550): ("Sgt. Major", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/sgm.png"),
    (550, 750): ("Command Sgt. Major", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/csm.png"),
    (750, 1050): ("Warrant Officer", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/wo1.png"),
    (1050, 1500): ("Chief Warrant Officer", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/cw4.png"),
    (1500, 2000): ("2nd Lieutenant", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/2lt.png"),
    (2000, 2800): ("1st Lieutenant", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/1lt.png"),
    (2800, 4000): ("Captain", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/cpt.png"),
    (4000, 5800): ("Major", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/maj.png"),
    (5800, 8000): ("Lieutenant Colonel", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/ltc.png"),
    (8000, 12000): ("Colonel", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/col.png"),
    (12000, 16000): ("Brigadier General", "https://www.military-ranks.org/images/ranks/army/large/brigadier-general.png"),
    (16000, 22000): ("Major General", "https://www.military-ranks.org/images/ranks/army/large/major-general.png"),
    (22000, 32000): ("Lieutenant General", "https://www.military-ranks.org/images/ranks/army/large/lieutenant-general.png"),
    (32000, float('inf')): ("5 Star General", "https://www.military-ranks.org/images/ranks/army/large/general-of-the-army.png")
}

P = inflect.engine()


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


class CogServerStatus(discord.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.server_data = None
        self.last_query = None
        self.total_online = 0
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
    

    async def query_api(self):
        """Query API
        
        Returns JSON after querying API URL, or None if bad response.
        """
        print(f"{self.bot.get_datetime_str()}: [ServerStatus] Querying API... ", end='')

        # Make an HTTP GET request to the API endpoint
        _response = requests.get(API_URL)

        # Check if the request was successful (status code 200 indicates success)
        if _response.status_code == 200:
            print("Success.")
            # Parse the JSON response
            return _response.json()
        else:
            print("Failed.")
            return None
    
    def get_team_score_str(self, gamemode: str, score: int) -> str:
        """Get Team Score String
        
        Returns a formatted string for the team's score given the current gamemode.
        """
        if gamemode == "conquest":
            return f"***{P.no('ticket', score)} remaining***"
        else:
            return f"***{P.no('flag', score)} captured***"
    
    def get_player_attr_list_str(self, players, attribute: str) -> str:
        """Get Player Attribute List String
        
        Returns a formatted code block string that contains a list of a given attribute for all players.
        Accepted Attributes: name, score, deaths
        """
        _str = "```\n"
        for _i, _p in enumerate(players):
            if attribute == 'name':
                _str += f"{_i+1}. {_p[attribute]}\n"
            elif attribute == 'score':
                _str += f"  {str(_p[attribute]).rjust(2)} pts\n"
            else:
                _str += f"   {str(_p['deaths']).rjust(2)}\n"
        return _str + "```"
    
    def get_server_stat_embeds(self) -> list:
        """Get Server Statistic Embeds
        
        Returns a list of Discord Embeds that each display each server's current statistics.
        """
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
                    _embed.set_footer(text=f"Data fetched at: {self.last_query.strftime('%I:%M:%S %p UTC')} -- {ROOT_URL}")
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
                _embed.set_footer(text=f"Data fetched at: {self.last_query.strftime('%I:%M:%S %p UTC')} -- {ROOT_URL}")
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
            _embed.set_footer(text=f"Data fetched at: {self.last_query.strftime('%I:%M:%S %p UTC')} -- {ROOT_URL}")
            _embeds.append(_embed)
        
        return _embeds
    
    def sum_player_stats(self, orig_stats, player_new_stats, game_data, top_player_name: str) -> dict:
        """Sum Player Stats
        
        Helper function for record_player_stats().
        Returns a dictionary of key player statistic values that is the sum of the `orig_stats`
        dictionary and relevant values from the `player_new_stats` & `game_data` dictionaries.
        Will start with a zeroed out dictionary if `orig_stats` is None.
        """
        if orig_stats == None:
            _final_stats = {
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
            _final_stats = orig_stats.copy()
        # Add scores and deaths
        _final_stats['score'] += player_new_stats['score']
        _final_stats['deaths'] += player_new_stats['deaths']
        # Detect player's team and if that team won or lost (draws are omitted)
        if player_new_stats['team'] == 0:
            _team = game_data['team1_country']
            if game_data['team1_score'] > game_data['team2_score']:
                _final_stats['wins'] += 1
            elif game_data['team1_score'] < game_data['team2_score']:
                _final_stats['losses'] += 1
        else:
            _team = game_data['team2_country']
            if game_data['team1_score'] < game_data['team2_score']:
                _final_stats['wins'] += 1
            elif game_data['team1_score'] > game_data['team2_score']:
                _final_stats['losses'] += 1
        # Add team they played for
        if _team == "US":
            _final_stats['us_games'] += 1
        elif _team == "CH":
            _final_stats['ch_games'] += 1
        elif _team == "AC":
            _final_stats['ac_games'] += 1
        else:
            _final_stats['eu_games'] += 1
        # Add gamemode they played
        if game_data['game_type'] == "capturetheflag":
            _final_stats['cf_games'] += 1
        else:
            _final_stats['cq_games'] += 1
        # Add if they were the top player
        if player_new_stats['name'] == top_player_name:
            _final_stats['top_player'] += 1
        
        return _final_stats
    
    async def record_player_stats(self, server_data):
        """Record Player Statistics
        
        Additively records player statistics given a server's JSON data to the database.
        New records are created for first-seen players.
        """
        print(f"\tRecording round stats... ", end='')

        # Find top scoring player in game
        _top_player = None
        for _p in server_data['players']:
            if (_top_player == None
                or _p['score'] > _top_player['score']
                or (_p['score'] == _top_player['score'] and _p['deaths'] < _top_player['deaths'])):
                _top_player = _p

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
            _summed_stats = self.sum_player_stats(_dbEntry, _p, server_data, _top_player['name'])
            if _dbEntry != None:
                # Update player
                self.bot.db.update("player_stats", _summed_stats, [f"id={_dbEntry['id']}"])
            else:
                # Insert new player
                _summed_stats['nickname'] = _p['name']
                _summed_stats['first_seen'] = datetime.now().date()
                self.bot.db.insert("player_stats", _summed_stats)
        
        print("Done.")
    
    def split_list(self, lst, chunk_size) -> list[list]:
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
                    description=f"*Unofficial\* top 50 players across all servers.*",
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
                        _stats += f" {P.no('game', _e[stat])} won\n"
                    else:
                        _stats += "\n"
                    _rank += 1
                _nicknames += "```"
                _stats += "```"
                _embed.add_field(name="Player:", value=_nicknames, inline=True)
                _embed.add_field(name=f"{stat.capitalize()}:", value=_stats, inline=True)
                _embed.set_footer(text=f"*Some match final moments may be ommited -- {ROOT_URL}")
                _pages.append(Page(embeds=[_embed]))
        else:
            _embed = discord.Embed(
                title=f":first_place:  BF2:MC Online | Top {stat.capitalize()} Leaderboard*  :first_place:",
                description="No stats yet.",
                color=discord.Colour.gold()
            )
            _pages = [Page(embeds=[_embed])]
        return Paginator(pages=_pages, author_check=False)
    
    def get_rank_data(self, score: int) -> tuple:
        """Returns rank name and image as a tuple given a score"""
        for score_range, rank_data in RANK_DATA.items():
            if score_range[0] <= score < score_range[1]:
                return rank_data
    
    def time_to_sec(self, time: str) -> int:
        """Turns a time string into seconds as an integer"""
        hours, minutes, seconds = time.split(':')
        return int(hours) * 3600 + int(minutes) * 60 + int(seconds)


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
        ## Query API for data
        _new_data = await self.query_api()
        self.last_query = datetime.utcnow()

        ## Check each server if game over -> record stats
        # Only check if original data exists
        if self.server_data != None:
            # For all existing servers...
            for _s_o in self.server_data['results']:
                _server_found = False
                # Search all new data for matching server
                for _s_n in _new_data['results']:
                    if _s_o['id'] == _s_n['id']:
                        _server_found = True
                        # Record original data if new time elapsed is lower (indicating a new game)
                        _original_time = self.time_to_sec(_s_o['time_elapsed'])
                        _new_time = self.time_to_sec(_s_n['time_elapsed'])
                        if _original_time > _new_time:
                            print(f"{self.bot.get_datetime_str()}: [ServerStatus] A server has finished a game:")
                            print(f"\tServer    : {_s_o['server_name']}")
                            print(f"\tMap       : {_s_o['map_name']}")
                            print(f"\tOrig. Time: {_s_o['time_elapsed']} ({_original_time} sec.)")
                            print(f"\tNew Time  : {_s_n['time_elapsed']} ({_new_time} sec.)")
                            await self.record_player_stats(_s_o)
                        break
                # If server has gone offline, record last known data
                if not _server_found:
                    print(f"{self.bot.get_datetime_str()}: [ServerStatus] \"{_s_o['server_name']}\" has gone offline!")
                    await self.record_player_stats(_s_o)
        # Replace original data with new data
        self.server_data = _new_data
        
        ## Calculate total players online
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
            _rank_data = self.get_rank_data(_dbEntry['score'])
            _total_games = _dbEntry['cq_games'] + _dbEntry['cf_games']
            _fav_gamemode = GM_STRINGS['conquest'] # Default
            if _dbEntry['cf_games'] > _dbEntry['cq_games']:
                _fav_gamemode = GM_STRINGS['capturetheflag']
            _team_games = {
                TEAM_STRINGS['US'][:-1]: _dbEntry['us_games'],
                TEAM_STRINGS['CH'][:-1]: _dbEntry['ch_games'],
                TEAM_STRINGS['AC'][:-1]: _dbEntry['ac_games'],
                TEAM_STRINGS['EU'][:-1]: _dbEntry['eu_games']
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
    cog = CogServerStatus(bot)
    cog.guild_ids = [bot.config['GuildID']]
    bot.add_cog(cog)
