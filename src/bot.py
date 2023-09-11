"""bot.py

A subclass of `discord.Bot` that adds ease-of-use instance variables and functions (e.g. database object).
Date: 09/11/2023
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
    #get_datetime_str
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
        print(msg, end='')
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
            self.db = SimpleMysql(
                host=self.config['MySQL']['Host'],
                port=self.config['MySQL']['Port'],
                db=self.config['MySQL']['DB_Name'],
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
        _player_count = server_data['playersCount']

        # Setup embed color based on total player count
        if _player_count == 0:
            _color = discord.Colour.yellow()
        elif _player_count == server_data['maxPlayers']:
            _color = discord.Colour.red()
        else:
            _color = discord.Colour.green()
        
        # (DEPRECIATED) Check if server is official
        """
        if server_data['id'] in self.config['ServerStatus']['OfficialIDs']:
            _description = "*Official Server*"
        else:
            _description = "*Unofficial Server*"
        """

        # Check match state
        if server_data['id'] in self.game_over_ids:
            _description = "*Match Completed*"
        elif _player_count < self.config['PlayerStats']['MatchMinPlayers']:
            _description = "*Waiting for Players*"
        else:
            _description = "*Match In-Progress*"
        
        # Get team players and sort by score
        _team1 = server_data['teams'][0]['players']
        _team2 = server_data['teams'][1]['players']
        _team1 = sorted(_team1, key=lambda x: x['score'], reverse=True)
        _team2 = sorted(_team2, key=lambda x: x['score'], reverse=True)
        
        # Setup Discord embed
        _embed = discord.Embed(
            title=server_data['serverName'],
            description=_description,
            color=_color
        )
        _embed.set_author(
            name="BF2:MC Server Info", 
            icon_url=CS.COUNTRY_FLAGS_URL.replace("<code>", server_data['country'].lower())
        )
        _embed.set_thumbnail(url=CS.GM_THUMBNAILS_URL.replace("<gamemode>", server_data['gameType']))
        _embed.add_field(name="Players:", value=f"{_player_count}/{server_data['maxPlayers']}", inline=False)
        _embed.add_field(name="Gamemode:", value=CS.GM_STRINGS[server_data['gameType']], inline=True)
        _embed.add_field(name="Time Elapsed:", value=self.sec_to_mmss(server_data['timeElapsed']), inline=True)
        _embed.add_field(name="Time Limit:", value=self.sec_to_mmss(server_data['timeLimit']), inline=True)
        _embed.add_field(
            name=CS.TEAM_STRINGS[server_data['teams'][0]['country']], 
            value=self.get_team_score_str(server_data['gameType'], server_data['teams'][0]['score']), 
            inline=False
        )
        _embed.add_field(name="Player:", value=self.get_player_attr_list_str(_team1, 'name'), inline=True)
        _embed.add_field(name="Score:", value=self.get_player_attr_list_str(_team1, 'score'), inline=True)
        _embed.add_field(name="Deaths:", value=self.get_player_attr_list_str(_team1, 'deaths'), inline=True)
        _embed.add_field(
            name=CS.TEAM_STRINGS[server_data['teams'][1]['country']],  
            value=self.get_team_score_str(server_data['gameType'], server_data['teams'][1]['score']), 
            inline=False
        )
        _embed.add_field(name="Player:", value=self.get_player_attr_list_str(_team2, 'name'), inline=True)
        _embed.add_field(name="Score:", value=self.get_player_attr_list_str(_team2, 'score'), inline=True)
        _embed.add_field(name="Deaths:", value=self.get_player_attr_list_str(_team2, 'deaths'), inline=True)
        _embed.set_image(url=CS.MAP_IMAGES_URL.replace("<map_name>", server_data['mapName']))
        _embed.set_footer(text=f"Data fetched at: {self.last_query.strftime('%I:%M:%S %p UTC')} -- {self.config['API']['HumanURL']}")

        return _embed
    
    async def query_api(self) -> dict:
        """Query API
        
        Returns JSON after querying API URL, or None if bad response.
        Also sets instance variables query_data and last_query.
        """
        self.log("[General] Querying API... ", end='', file=False)

        # DEBUGGING
        try:
            _DEBUG = self.config['DEBUG']
        except:
            _DEBUG = None

        # Move current data to old data
        self.old_query_data = self.cur_query_data

        # Make an HTTP GET request to the API endpoint
        if not _DEBUG:
            _response = requests.get(self.config['API']['EndpointURL'])
        self.last_query = datetime.utcnow()

        # Check if the request was successful (status code 200 indicates success)
        if _DEBUG:
            self.reload_config()
            self.cur_query_data = self.config['DEBUG']
            self.log("Success (DEBUG).", time=False, file=False)
        elif _response.status_code == 200:
            self.log("Success.", time=False, file=False)
            # Parse the JSON response
            self.cur_query_data = _response.json()
        else:
            self.log("Failed!", time=False, file=False)
            self.cur_query_data = None
        
        return self.cur_query_data
