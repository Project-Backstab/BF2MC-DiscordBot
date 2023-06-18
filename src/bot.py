"""bot.py

A subclass of `discord.Bot` that adds ease-of-use instance variables and functions (e.g. database object).
Date: 06/11/2023
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


class BackstabBot(discord.Bot):
    @staticmethod
    def get_datetime_str() -> str:
        """Return a formatted datetime string for logging"""
        _now = datetime.now()
        return _now.strftime("%m/%d/%Y %H:%M:%S")
    
    @staticmethod
    def escape_discord_formatting(text: str) -> str:
        """Return a string that escapes any of Discord's formatting special characters for the given string"""
        formatting_chars = ['*', '_', '`', '~', '|']
        escaped_chars = ['\\*', '\\_', '\\`', '\\~', '\\|']
        for char, escaped_char in zip(formatting_chars, escaped_chars):
            text = text.replace(char, escaped_char)
        return text
    
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
        self.infl = inflect.engine()
        # Database Initialization
        try:
            print(f"{BackstabBot.get_datetime_str()}: [Startup] Logging into MySQL database... ", end='')
            self.db = SimpleMysql(
                host=self.config['MySQL']['Host'],
                port=self.config['MySQL']['Port'],
                db=self.config['MySQL']['DB_Name'],
                user=self.config['MySQL']['User'],
                passwd=self.config['MySQL']['Pass'],
                autocommit=True,
                keep_alive=True
            )
            print("Done.")
        except Exception as e:
            print(f"ERROR: {e}")
            sys.exit(3)
    
    async def on_ready(self):
        """Event: On Ready
        
        Called when the bot successfully connects to the API and becomes online.
        Excessive API calls in this function should be avoided.
        """
        # Check that guild_id is valid
        _guild = self.get_guild(self.config['GuildID'])
        if _guild == None:
            print(f"ERROR: [Config] Could not find valid guild with ID: {self.config['GuildID']}")
            await self.close()
        
        print(f"{self.get_datetime_str()}: [Startup] {self.user} is ready and online!")
    
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
                print(f"ERROR: [Config] Could not find valid channel with ID: {_channel_id}")
                await self.close()
    
    async def query_api(self) -> dict:
        """Query API
        
        Returns JSON after querying API URL, or None if bad response.
        Also sets instance variables query_data and last_query.
        """
        print(f"{self.get_datetime_str()}: [General] Querying API... ", end='')

        # DEBUGGING
        try:
            _DEBUG = self.config['DEBUG']
        except:
            _DEBUG = None

        # Move current data to old data
        self.old_query_data = self.cur_query_data

        # Make an HTTP GET request to the API endpoint
        if not _DEBUG:
            _response = requests.get(self.config['API']['ApiURL'])
        self.last_query = datetime.utcnow()

        # Check if the request was successful (status code 200 indicates success)
        if _DEBUG:
            self.cur_query_data = _DEBUG
            print("Success (DEBUG).")
        elif _response.status_code == 200:
            print("Success.")
            # Parse the JSON response
            self.cur_query_data = _response.json()
        else:
            print("Failed!")
            self.cur_query_data = None
        
        return self.cur_query_data
