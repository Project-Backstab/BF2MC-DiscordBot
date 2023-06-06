"""bot.py

A subclass of `discord.Bot` that adds ease-of-use instance variables and functions (e.g. database object).
Date: 06/05/2023
Authors: David Wolfe (Red-Thirten)
Licensed under GNU GPLv3 - See LICENSE for more details.
"""

import sys
import json
from datetime import datetime

import discord
from discord.ext import commands
from simplemysql import SimpleMysql


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
