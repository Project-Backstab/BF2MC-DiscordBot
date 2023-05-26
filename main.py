"""main.py

Main file to start Backstab
Date: 05/26/2023
Authors: David Wolfe (Red-Thirten)
Licensed under GNU GPLv3 - See LICENSE for more details.
"""

import sys

import discord
from discord.ext import commands
from src import BackstabBot

def main():
    VERSION = "2.0.2"
    AUTHORS = "Red-Thirten"
    COGS_LIST = [
        "CogServerStatus"
    ]

    """Discord Bot -- Main

    Pycord initialization, core functionality, and root slash commands.
    """
    # Create intents before creating bot instance
    intents = discord.Intents().default()
    intents.members = True
    intents.message_content = True
    # Setup activity of bot
    activity = discord.Activity(type=discord.ActivityType.watching, name="0 Veterans online")
    
    # Create the bot object
    bot = BackstabBot(intents=intents, activity=activity)

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


    @bot.slash_command(guild_ids=[bot.config['GuildID']], name = "about", description="Displays information about the Backstab Bot.")
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
            icon_url="https://raw.githubusercontent.com/lilkingjr1/backstab-discord-bot/main/assets/icon.png"
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
        await ctx.respond(embed=_embed, ephemeral=True)
        
    @bot.slash_command(guild_ids=[bot.config['GuildID']], name = "say", description="Makes the bot say something. Only admins can do this.")
    @discord.default_permissions(manage_channels=True) # Only members with Manage Channels permission can use this command.
    async def say(ctx, text: discord.Option(str)):
        """Slash Command: /say
        
        Makes the bot say something. Only admins can do this.
        """
        await ctx.send(text)
        await ctx.respond("...", ephemeral=True, delete_after=0)
        print(f"{bot.get_datetime_str()}: {ctx.author.name} made bot say \"{text}\"")
        
    @bot.slash_command(guild_ids=[bot.config['GuildID']], name = "reloadconfig", description="Reloads the bot's config file. Only admins can do this.")
    @discord.default_permissions(manage_channels=True) # Only members with Manage Channels permission can use this command.
    async def reloadconfig(ctx):
        """Slash Command: /reloadconfig
        
        Reloads the bot's config file. Only admins can do this.
        """
        bot.reload_config()
        await ctx.respond(f"Config reloaded.", ephemeral=True)
        print(f"{bot.get_datetime_str()}: {ctx.author.name} reloaded the config file.")

    @bot.slash_command(guild_ids=[bot.config['GuildID']], name = "shutdown", description="Cleanly shuts Backstab down. Only admins can do this.")
    @discord.default_permissions(manage_channels=True) # Only members with Manage Channels permission can use this command.
    async def shutdown(ctx):
        """Slash Command: /shutdown
        
        Cleanly shuts Backstab down. Only admins can do this.
        """
        print(f"{bot.get_datetime_str()}: [Shutdown] Shutdown command issued by {ctx.author.name}#{ctx.author.discriminator}.")
        await ctx.respond("Goodbye.", ephemeral=True)
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
