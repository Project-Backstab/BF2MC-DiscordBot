"""main.py

Main file to start Backstab
Date: 05/17/2024
Authors: David Wolfe (Red-Thirten)
Licensed under GNU GPLv3 - See LICENSE for more details.
"""

import sys

import discord
from discord.ext import commands

from iso639 import languages
from langdetect import detect as LangDetect
from deep_translator import GoogleTranslator

from src import BackstabBot
import common.CommonStrings as CS

def main():
    VERSION = "4.3.4"
    AUTHORS = "Red-Thirten"
    COGS_LIST = [
        "CogServerStatus",
        "CogServerStats",
        "CogPlayerStats",
        "CogClanStats"
    ]

    print(
        f"Backstab Discord Bot - v{VERSION}\n"
        "Copyright (c) 2024 David Wolfe (Red-Thirten)"
    )

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
    

    def get_translated_msg_embed(
            msg: discord.Message,
            from_lang: str,
            to_lang: str,
            replyable: bool = True
        ) -> discord.Embed:
        """Helper Function: Get Translated Message Embed
        
        msg = Discord Message object to translate
        from_lang = ISO-639 code for source language
        to_lang = ISO-639 code for target language
        replyable = If reply footer text should be displayed
        """
        # Try to translate message and return None if error
        try:
            _translated_msg = GoogleTranslator(source=from_lang, target=to_lang).translate(msg.content)
        except Exception:
            bot.log("[Translate] Could not translate message:")
            bot.log(f'\t{msg.author.display_name}: [{from_lang} -> en] "{msg.content}"', time=False)
            return None
        # Build and send embed message
        _author_name = f"{msg.author.display_name}:"
        _author_url = msg.author.display_avatar.url
        _footer_text = f"Best attempt to translate {languages.get(part1=from_lang).name} to {languages.get(part1=to_lang).name}"
        if replyable:
            _footer_text += "\n(Reply to this bot message to reply to the original author in their language)"
        _footer_url = CS.LANG_FLAGS_URL.replace("<code>", from_lang)
        _embed = discord.Embed(
            description=f">>> {_translated_msg}",
            color=discord.Colour.teal()
        )
        _embed.set_author(name=_author_name, icon_url=_author_url)
        _embed.set_footer(text=_footer_text, icon_url=_footer_url)
        return _embed
    
    @bot.event
    async def on_message(message):
        """Event: On Message
        
        Replies to 'good bot' messages directed at the bot.
        Translates messages sent in specific channels and in specific languages
        to English based on the config file.
        """
        ## Bot message
        # Ignore messages sent by bots
        if message.author.bot:
            return

        ## Good bot
        if bot.user.mentioned_in(message):
            if 'good bot' in message.content.lower():
                await message.channel.send("Aww shucks!", reference=message)
                return
        
        ## Translate
        # Return if not enabled
        if not bot.config['Translate']['Enabled']:
            return
        # Return if message not in config channels
        if message.channel.id not in bot.config['Translate']['TextChannelIDs']:
            return
        # Return if message is less than configured character length
        if len(message.content) < bot.config['Translate']['MinCharLength']:
            return
        # Return if message contains any string in config blacklist
        if any(_s.lower() in message.content.lower() for _s in bot.config['Translate']['Blacklist']):
            return
        # Try to detect message language and return if error
        try:
            _from_lang = LangDetect(message.content)
        except Exception:
            bot.log("[Translate] Could not detect language of message:")
            bot.log(f'\t{message.author.display_name}: "{message.content}"', time=False)
            return
        # If message's detected language is in config's FromLangs
        if _from_lang in bot.config['Translate']['FromLangs']:
            # Translate it to primary language
            _embed = get_translated_msg_embed(message, _from_lang, bot.config['Translate']['PrimaryLang'])
            if _embed:
                await message.channel.send(embed=_embed, reference=message, mention_author=False)
        # Else if user reply to translation embed
        elif message.reference:
            _cached_msg = message.reference.cached_message
            if _cached_msg and _cached_msg.embeds and _cached_msg.embeds[0]:
                _cached_embed = _cached_msg.embeds[0]
                if "translate" in _cached_embed.footer.text:
                    _to_lang = _cached_embed.footer.icon_url[-6:-4]
                    # If author is trying to reply to a primary language embed
                    if _to_lang == bot.config['Translate']['PrimaryLang']:
                        return
                    _embed = get_translated_msg_embed(message, _from_lang, _to_lang, False)
                    if _embed:
                        await message.channel.send(embed=_embed, reference=message, mention_author=False)



    @bot.slash_command(guild_ids=[bot.config['GuildID']], name = "about", description="Displays information about the Backstab Bot.")
    async def about(ctx):
        """Slash Command: /about
        
        Displays information about the Backstab Bot.
        """
        _description = ("BackStab is a custom Discord bot, written for the Battlefield 2: Modern Combat Veterans community, "
                        "that can provide server status information and other useful related information.")
        _embed = discord.Embed(
            title="About:",
            description=_description,
            color=discord.Colour.blue()
        )
        _embed.set_author(
            name="BackStab Bot", 
            icon_url=CS.BOT_ICON_URL
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
    async def say(ctx, text: discord.Option(str)): # type: ignore
        """Slash Command: /say
        
        Makes the bot say something. Only admins can do this.
        """
        await ctx.send(text)
        await ctx.respond("...", ephemeral=True, delete_after=0)
        bot.log(f"{ctx.author.name} made bot say \"{text}\"")
        
    @bot.slash_command(guild_ids=[bot.config['GuildID']], name = "dm", description="Makes the bot send a Direct Message to a member. Only admins can do this.")
    @discord.default_permissions(manage_channels=True) # Only members with Manage Channels permission can use this command.
    async def dm(
        ctx, 
        member: discord.Option(
            discord.Member, 
            description="Discord member to send DM to",
            required=True
        ),  # type: ignore
        title: discord.Option(
            str, 
            description="Title of message",
            required=True
        ),  # type: ignore
        color: discord.Option(
            str, 
            description="Accent color of message",
            choices=[
                "Blurple",
                "Green",
                "Yellow",
                "Red"
            ],
            required=True
        ),  # type: ignore
        message: discord.Option(
            str, 
            description="Message text",
            required=True
        ) # type: ignore
    ):
        """Slash Command: /dm
        
        Makes the bot send a Direct Message to a member. Only admins can do this.
        """
        await ctx.defer(ephemeral=True)
        # Determine color
        _embed_color = discord.Colour.blurple()
        if color == "Green": _embed_color = discord.Colour.green()
        elif color == "Yellow": _embed_color = discord.Colour.yellow()
        elif color == "Red": _embed_color = discord.Colour.red()
        # Build embed for message
        _embed = discord.Embed(
            title=title,
            description=message,
            color=_embed_color
        )
        _embed.set_author(
            name="BFMCspy Admin Team", 
            icon_url="https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/main/assets/emojis/patches/BFMCspy_Launch.png"
        )
        _footer = "Do not reply to this message; it will not be read."
        _footer += "\nPlease contact the admin team via Mod Mail if you wish to reply."
        _embed.set_footer(text=_footer)
        # Send message
        await member.send(embed=_embed)
        await ctx.respond("Message sent.", ephemeral=True)
        bot.log(f'{ctx.author.name} made bot send the following message to {member.name}:\n\tTitle: {title}\n\tMessage: "{message}"')
        
    @bot.slash_command(guild_ids=[bot.config['GuildID']], name = "reloadconfig", description="Reloads the bot's config file. Only admins can do this.")
    @discord.default_permissions(manage_channels=True) # Only members with Manage Channels permission can use this command.
    async def reloadconfig(ctx):
        """Slash Command: /reloadconfig
        
        Reloads the bot's config file. Only admins can do this.
        """
        bot.reload_config()
        await ctx.respond(f"Config reloaded.", ephemeral=True)
        bot.log(f"{ctx.author.name} reloaded the config file.")

    @bot.slash_command(guild_ids=[bot.config['GuildID']], name = "shutdown", description="Cleanly shuts Backstab down. Only admins can do this.")
    @discord.default_permissions(manage_channels=True) # Only members with Manage Channels permission can use this command.
    async def shutdown(ctx):
        """Slash Command: /shutdown
        
        Cleanly shuts Backstab down. Only admins can do this.
        """
        bot.log(f"[Shutdown] Shutdown command issued by {ctx.author.name}#{ctx.author.discriminator}.")
        await ctx.respond("Goodbye.", ephemeral=True)
        await bot.close()


    # Attempt to start the bot
    bot.log("[Startup] Bot attempting to login to Discord...")
    try:
        bot.run(bot.config['DiscordToken'])
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
