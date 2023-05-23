"""main.py

Main file to start Backstab
Date: 05/22/2023
Authors: David Wolfe (Red-Thirten)
Licensed under GNU GPLv3 - See LICENSE for more details.
"""

import sys
import json

import discord
from discord.ext import commands
from src import BackstabBot

def main():
    VERSION = "1.0.1"
    AUTHORS = "Red-Thirten"
    COGS_LIST = [
        "CogServerStatus"
    ]

    # Load configuration file
    with open('config.cfg') as file:
        # Load the JSON data
        CONFIG = json.load(file)


    """Discord Bot -- Main

    Pycord initialization, core functionality, and root slash commands.
    """
    # Create intents before creating bot instance
    intents = discord.Intents().default()
    intents.members = True
    intents.message_content = True
    # Setup activity of bot
    activity = discord.Activity(type=discord.ActivityType.playing, name="Battlefield 2: Modern Combat Online")
    
    # Create the bot object
    bot = BackstabBot(CONFIG, intents=intents, activity=activity)

    # Add cogs to bot
    for cog in COGS_LIST:
        bot.load_extension(f'cogs.{cog}')
    
    @bot.event
    async def on_message(message):
        """Event: On Message
        
        Replies to 'good bot' messages directed at the bot.
        """
        if bot.user.mentioned_in(message):
            if 'good bot' in message.content.lower():
                await message.channel.send("Aww shucks!", reference=message)

    @bot.slash_command(guild_ids=[CONFIG['GuildID']], name = "about", description="Displays information about the Backstab Bot.")
    @commands.cooldown(1, 60, commands.BucketType.user) # A single user can only call this every 60 seconds
    async def about(ctx):
        """Slash Command: /about
        
        Displays information about the Backstab Bot.
        """
        _description = ("Backstab is a custom Discord bot, written for the Battlefield 2: Modern Combat Veterans community, "
                        "that can provide server status information and other useful related information.")
        _embed = discord.Embed(
            title="About:",
            description=_description,
            color=discord.Colour.blue()
        )
        _embed.set_author(
            name="Backstab", 
            icon_url="https://cdn.discordapp.com/banners/502923049541304320/95731bc0d72d26769cb94d90b92c71c7.webp"
        )
        _embed.set_thumbnail(url="https://cdn.discordapp.com/icons/502923049541304320/4d8d584de5d9baec281d4861c6b11781.webp?size=4096")
        # Construct string of bot commands for display
        _cmd_str = "```"
        for command in bot.commands:
            _cmd_str += f"/{command}\n"
        _cmd_str += "```"
        _embed.add_field(name="Commands:", value=_cmd_str, inline=True)
        _embed.add_field(name="Authors:", value=AUTHORS, inline=True)
        _embed.add_field(name="Version:", value=VERSION, inline=True)
        _embed.set_footer(text=f"Bot latency is {bot.latency}")
        await ctx.respond(embed=_embed)

    @bot.slash_command(guild_ids=[CONFIG['GuildID']], name = "shutdown", description="Cleanly shuts Backstab down. Only admins can do this.")
    @discord.default_permissions(administrator=True) # Only members with admin can use this command.
    async def shutdown(ctx):
        """Slash Command: /shutdown
        
        Cleanly shuts Backstab down. Only admins can do this.
        """
        print(f"{bot.get_datetime_str()}: [Shutdown] Shutdown command issued by {ctx.author.name}#{ctx.author.discriminator}.")
        await ctx.respond("Goodbye.")
        await bot.close()

    # Attempt to start the bot
    print(f"{bot.get_datetime_str()}: [Startup] Bot attempting to login to Discord...")
    try:
        bot.run(bot.config['DiscordToken'])
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
