"""bot.py

A subclass of `discord.Bot` that adds ease-of-use instance variables and functions (e.g. database object).
Date: 01/21/2024
Authors: David Wolfe (Red-Thirten)
Licensed under GNU GPLv3 - See LICENSE for more details.
"""

import sys
import json
import requests
from datetime import datetime

import discord
from discord.ext import commands
from simplemysql import SimpleMysql
import inflect
import common.CommonStrings as CS

LOG_FILE = "BackstabBot.log"


class BackstabBot(discord.Bot):
    @staticmethod
    def log(msg: str, time: bool = True, file: bool = True, end: str = '\n'):
        """Custom Logging

        msg: Message to log to the console.
        time: If a timestamp should be added to the beginning of the message.
        file: If the message should also be logged to file.
        end: Character to add to the end of the string.
        """
        if time:
            _timestamp = datetime.now()
            _timestamp = _timestamp.strftime("%m/%d/%Y %H:%M:%S")
            _timestamp += ": "
            msg = _timestamp + msg
        msg += end
        print(msg, end='', flush=True)
        if file:
            with open(LOG_FILE, 'a') as _file:
                _file.write(msg)
    
    @staticmethod
    def escape_discord_formatting(text: str) -> str:
        """Return a string that escapes any of Discord's formatting special characters for the given string"""
        if text == None: return "None"
        formatting_chars = ['*', '_', '`', '~', '|']
        escaped_chars = ['\\*', '\\_', '\\`', '\\~', '\\|']
        for char, escaped_char in zip(formatting_chars, escaped_chars):
            text = text.replace(char, escaped_char)
        return text
    
    @staticmethod
    def sec_to_mmss(seconds: int) -> str:
        """Return a MM:SS string given seconds"""
        minutes = seconds // 60
        seconds_remaining = seconds % 60
        return f"{minutes:02d}:{seconds_remaining:02d}"
    
    @staticmethod
    def split_list(lst: list, chunk_size: int) -> list[list]:
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
    
    @staticmethod
    def get_player_attr_list_str(players: list, attribute: str) -> str:
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
            elif attribute == 'deaths':
                _str += f"   {str(_p['deaths']).rjust(2)}\n"
        return _str + "```"
    
    @staticmethod
    def get_config() -> dict:
        """Loads config file and returns JSON data"""
        # Load configuration file
        with open('config.cfg') as file:
            # Load the JSON data
            _data = json.load(file)
        return _data
    

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = BackstabBot.get_config()
        self.cur_query_data = None
        self.old_query_data = None
        self.last_query = None
        self.game_over_ids = []
        self.infl = inflect.engine()
        self.log("", time=False) # Empty line to seperate runs in the log file
        self.log("[Startup] Bot successfully instantiated.")
        # Database Initialization
        try:
            self.log("[Startup] Logging into MySQL database... ", end='')
            self.db_discord = SimpleMysql(
                host=self.config['MySQL']['Host'],
                port=self.config['MySQL']['Port'],
                db=self.config['MySQL']['DiscordBot_DB_Name'],
                user=self.config['MySQL']['User'],
                passwd=self.config['MySQL']['Pass'],
                autocommit=True,
                keep_alive=True
            )
            self.db_backend = SimpleMysql(
                host=self.config['MySQL']['Host'],
                port=self.config['MySQL']['Port'],
                db=self.config['MySQL']['Backend_DB_Name'],
                user=self.config['MySQL']['User'],
                passwd=self.config['MySQL']['Pass'],
                autocommit=True,
                keep_alive=True
            )
            self.log("Done.", time=False)
        except Exception as e:
            self.log(f"ERROR: {e}", time=False)
            sys.exit(3)
    
    async def on_ready(self):
        """Event: On Ready
        
        Called when the bot successfully connects to the API and becomes online.
        Excessive API calls in this function should be avoided.
        """
        # Print invite link and close bot if it is not already in a guild
        if len(self.guilds) < 1:
            print("==========================================================================")
            print("Use following link to invite bot to guild, and then restart the bot:")
            print(f"https://discord.com/api/oauth2/authorize?client_id={self.application_id}&permissions=85072&scope=bot%20applications.commands")
            print("==========================================================================")
            await self.close()
        
        # Check that guild_id is valid
        _guild = self.get_guild(self.config['GuildID'])
        if _guild == None:
            self.log(f"ERROR: [Config] Could not find valid guild with ID: {self.config['GuildID']}", time=False)
            await self.close()
        
        self.log(f"[Startup] {self.user} is ready and online!")
    
    async def on_application_command_error(self, ctx, error):
        """Event: On Command Error
        
        Required for command cooldown failures.
        """
        if isinstance(error, commands.CommandError):
            await ctx.respond(error, ephemeral=True)
        else:
            raise error
    
    def reload_config(self):
        """Reloads config from file and reassigns its data to the bot"""
        self.config = BackstabBot.get_config()
    
    async def check_channel_ids_for_cfg_key(self, key: str, sub_keys: list):
        """Check Channel IDs for given Config Key

        Check channel ID validity for given list of sub-keys in the config.
        Displays an error and closes the bot if an ID is invalid.
        """
        for _sub_key in sub_keys:
            _channel_id = self.config[key][_sub_key]
            if self.get_channel(_channel_id) == None:
                self.log(f"ERROR: [Config] Could not find valid channel with ID: {_channel_id}", time=False)
                await self.close()

    def get_team_score_str(self, gamemode: str, score: int) -> str:
        """Get Team Score String
        
        Returns a formatted string for the team's score given the current gamemode.
        """
        if gamemode == "conquest":
            return f"***{self.infl.no('ticket', score)} remaining***"
        else:
            return f"***{self.infl.no('flag', score)} captured***"
    
    def get_server_status_embed(self, server_data: dict) -> discord.Embed:
        # Get total player count
        _player_count = server_data['numplayers']

        # Setup embed color based on total player count or clan game
        if _player_count == 0:
            _color = discord.Colour.yellow()
        elif _player_count == server_data['maxplayers']:
            _color = discord.Colour.red()
        else:
            _color = discord.Colour.green()

        # Check match state
        if _player_count < self.config['PlayerStats']['MatchMinPlayers']:
            _description = "*Waiting for Players*"
        elif server_data['timeelapsed'] <= 0:
            _description = "*Match Completed*"
        else:
            _description = "*Match In-Progress*"
        
        # Get team players and sort by score
        _team1 = []
        _team2 = []
        _no_team = []
        for _p in server_data['players']:
            if _p['team'] == 0:
                _team1.append(_p)
            elif _p['team'] == 1:
                _team2.append(_p)
            else:
                _no_team.append(_p)
        _team1 = sorted(_team1, key=lambda x: x['score'], reverse=True)
        _team2 = sorted(_team2, key=lambda x: x['score'], reverse=True)

        # Get hostname
        _title = server_data['hostname']

        # Check if clan game
        if server_data['c0'] > 0 or server_data['c1'] > 0:
            _clanNames = self.db_backend.getAll(
                "Clans", 
                ["name"], 
                ("clanid = %s or clanid = %s", [server_data['c0'], server_data['c1']])
            )
            # Check if valid clan IDs were found
            if len(_clanNames) == 2:
                _title = f"{_clanNames[0]['name']} vs. {_clanNames[1]['name']}"
                _description = f"*Private Clan Game*\n({server_data['hostname']})"
                _color = discord.Colour.orange()
        
        # Setup Discord embed
        _embed = discord.Embed(
            title=_title,
            description=_description,
            color=_color
        )
        _embed.set_author(
            name="BF2:MC Server Info", 
            icon_url=CS.get_country_flag_url(server_data['region'])
        )
        _embed.set_thumbnail(url=CS.GM_THUMBNAILS_URL.replace("<gamemode>", server_data['gametype']))
        _embed.add_field(name="Players:", value=f"{_player_count}/{server_data['maxplayers']}", inline=False)
        _embed.add_field(name="Gamemode:", value=CS.GM_STRINGS[server_data['gametype']][0], inline=True)
        _embed.add_field(name="Time Elapsed:", value=self.sec_to_mmss(server_data['timeelapsed']), inline=True)
        _embed.add_field(name="Time Limit:", value=self.sec_to_mmss(server_data['timelimit']), inline=True)
        _embed.add_field(
            name=CS.TEAM_STRINGS[server_data['team0']][0], 
            value=self.get_team_score_str(server_data['gametype'], server_data['score0']), 
            inline=False
        )
        _embed.add_field(name="Players:", value=self.get_player_attr_list_str(_team1, 'name'), inline=True)
        _embed.add_field(name="Score:", value=self.get_player_attr_list_str(_team1, 'score'), inline=True)
        _embed.add_field(name="Deaths:", value=self.get_player_attr_list_str(_team1, 'deaths'), inline=True)
        _embed.add_field(
            name=CS.TEAM_STRINGS[server_data['team1']][0],  
            value=self.get_team_score_str(server_data['gametype'], server_data['score1']), 
            inline=False
        )
        _embed.add_field(name="Players:", value=self.get_player_attr_list_str(_team2, 'name'), inline=True)
        _embed.add_field(name="Score:", value=self.get_player_attr_list_str(_team2, 'score'), inline=True)
        _embed.add_field(name="Deaths:", value=self.get_player_attr_list_str(_team2, 'deaths'), inline=True)
        if len(_no_team) > 0:
            _embed.add_field(
                name="👥︎  No Team:",  
                value="", 
                inline=False
            )
            _embed.add_field(name="Players:", value=self.get_player_attr_list_str(_no_team, 'name'), inline=True)
        _embed.set_image(url=CS.MAP_IMAGES_URL.replace("<map_name>", server_data['map']))
        _embed.set_footer(text=f"Data fetched at: {self.last_query.strftime('%I:%M:%S %p UTC')} -- {self.config['API']['HumanURL']}")

        return _embed
    
    async def query_api(self, url_subfolder: str, **kwargs) -> json:
        """Query API
        
        Returns JSON after querying API URL, or None if bad response.
        Also sets instance variable last_query.
        """

        # DEBUGGING
        try:
            _DEBUG = self.config[url_subfolder]
        except Exception:
            _DEBUG = None

        # Build URL string
        _url = self.config['API']['EndpointURL']
        if url_subfolder:
            _url += f"/{url_subfolder}"
        if kwargs:
            _url += "?"
            for _i, (_k, _v) in enumerate(kwargs.items()):
                if _i > 0:
                    _url += "&"
                _url += f"{_k}={_v}"

        # Make an HTTP GET request to the API endpoint
        self.log(f"[General] Querying API: {_url}", end='', file=False)
        if not _DEBUG:
            _response = requests.get(_url, timeout=3)
        self.last_query = datetime.utcnow()

        # Check if the request was successful (status code 200 indicates success)
        if _DEBUG:
            self.reload_config()
            self.log("\tSuccess (DEBUG).", time=False, file=False)
            return _DEBUG
        elif _response.status_code == 200:
            self.log("\tSuccess.", time=False, file=False)
            # Parse the JSON response
            return _response.json()
        else:
            self.log("\tFailed!", time=False, file=False)
            return None
    
    async def cmd_query_api(self, url_subfolder: str, **kwargs) -> json:
        """Command Query API
        
        Same as Query API, but raises a CommandError if the query failed.
        """
        _query = await self.query_api(url_subfolder, **kwargs)
        if _query == None:
            raise commands.CommandError(
                ":warning: There was an error retrieving this data. The BFMCspy API may be down at the moment."
            )
        return _query
