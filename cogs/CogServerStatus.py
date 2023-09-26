"""CogServerStatus.py

Handles tasks related to checking server status and info.
Date: 09/25/2023
Authors: David Wolfe (Red-Thirten)
Licensed under GNU GPLv3 - See LICENSE for more details.
"""

import discord
from discord.ext import commands, tasks
from discord.ext.pages import Paginator, Page
import common.CommonStrings as CS


UPDATE_INTERVAL = 1.3 # Minutes


class CogServerStatus(discord.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.total_online = 0
        self.status_msg = None
        self.server_status = "automatic"
    
    
    def get_server_status_embeds(self, servers: list[dict]) -> list[discord.Embed]:
        """Get Server Statistic Embeds
        
        Returns a list of Discord Embeds that each display each server's current statistics.
        """
        # Check for missing query data
        if servers == None:
            _description = """
            *BFMCspy API endpoint is currently down.*

            **Game servers may still be online.**
            **We just can't display any status at this time.**
            """
            _embed = discord.Embed(
                    title=":yellow_circle:  Server Stats Unavailable",
                    description=_description,
                    color=discord.Colour.yellow()
                )
            _embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/8/8d/Computer_crash.svg/1200px-Computer_crash.svg.png")
            _embed.set_footer(text=f"Data fetched at: {self.bot.last_query.strftime('%I:%M:%S %p UTC')} -- {self.bot.config['API']['HumanURL']}")
            return [_embed]
        
        # Check for no servers online
        if len(servers) < 1:
            _description = f"""
            There are no game servers currently online :cry:
            Please check <#{self.bot.config['ServerStatus']['AnnouncementTextChannelID']}> for more info.
            """
            _embed = discord.Embed(
                title=":red_circle:  Servers Offline",
                description=_description,
                color=discord.Colour.red()
            )
            _embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/8/8d/Computer_crash.svg/1200px-Computer_crash.svg.png")
            _embed.set_footer(text=f"Data fetched at: {self.bot.last_query.strftime('%I:%M:%S %p UTC')} -- {self.bot.config['API']['HumanURL']}")
            return [_embed]

        # Default - Build server stat embeds
        _embeds = []
        for _s in servers:
            _embeds.append(self.bot.get_server_status_embed(_s))
        
        return _embeds
    
    async def set_status_channel_name(self, status: str):
        """Set Status Channel Name
        
        Sets the global server status for the given status string.
        Only updates the channel if the status has changed and is valid.
        NOTE: Discord limits channel name changes to twice every 10 min.
        """
        _voice_channel = self.bot.get_channel(self.bot.config['ServerStatus']['StatusVoiceChannelID'])
        if status in CS.STATUS_STRINGS and _voice_channel.name != CS.STATUS_STRINGS[status]:
            self.bot.log(f"[ServerStatus] {CS.STATUS_STRINGS[status]}")
            await _voice_channel.edit(name=CS.STATUS_STRINGS[status], reason="[BackstabBot] Server status updated.")


    @commands.Cog.listener()
    async def on_ready(self):
        """Listener: On Cog Ready
        
        Runs when the cog is successfully cached within the Discord API.
        """
        self.bot.log("[ServerStatus] Successfully cached!")
        
        # Check that all channels in the config are valid
        _cfg_sub_keys = [
            'StatusVoiceChannelID',
            'ServerStatusTextChannelID',
            'AnnouncementTextChannelID'
        ]
        await self.bot.check_channel_ids_for_cfg_key('ServerStatus', _cfg_sub_keys)

        # Get handle for server stats text channel
        _text_channel = self.bot.get_channel(self.bot.config['ServerStatus']['ServerStatusTextChannelID'])

        # Get status message (if it exists) from message history (if we haven't already)
        if self.status_msg == None:
            async for _m in _text_channel.history(limit=3):
                # Check if the message was sent by the user
                if _m.author == self.bot.user:
                    self.status_msg = await _text_channel.fetch_message(_m.id)
                    break
        
        # Start Status Loop
        if not self.StatusLoop.is_running():
            self.StatusLoop.start()
            self.bot.log(f"[ServerStatus] StatusLoop started ({UPDATE_INTERVAL} min. interval).")
            # Set channel description if it is not correct
            _topic = f"Live server statistics (Updated every {self.bot.infl.no('second', round(UPDATE_INTERVAL*60))})"
            if _text_channel.topic != _topic:
                await _text_channel.edit(topic=_topic)
    

    @tasks.loop(minutes=UPDATE_INTERVAL)
    async def StatusLoop(self):
        """Task Loop: Status Loop
        
        Runs every interval period, queries latest live server data, 
        updates status voice channel, and updates info text channel.
        """
        ## Query API for servers
        _servers = await self.bot.query_api("servers/live")

        ## Create live server list (excluding dead and unverified servers) & calculate players online
        _live_servers = []
        _total_players = 0
        if _servers != None:
            for _server in _servers:
                if _server['is_alive'] and _server['verified']:
                    _live_servers.append(_server)
                    _total_players += _server['numplayers']
        
        ## Update bot's activity if total players has changed
        if _total_players != self.total_online:
            self.total_online = _total_players
            _activity = discord.Activity(type=discord.ActivityType.watching, name=f"{_total_players} Veterans online")
            await self.bot.change_presence(activity=_activity)

        ## Update server status channel name
        if self.server_status == "automatic":
            if _servers == None:
                await self.set_status_channel_name("unknown")
                _live_servers = None
            elif len(_live_servers) > 0:
                await self.set_status_channel_name("online")
            else:
                await self.set_status_channel_name("offline")
        elif self.server_status == "online":
            await self.set_status_channel_name("online")
        elif self.server_status == "offline":
            await self.set_status_channel_name("offline")
        elif self.server_status == "unknown":
            await self.set_status_channel_name("unknown")
            _live_servers = None

        ## Update stats channel post
        # Post already exists
        if self.status_msg != None:
            try:
                await self.status_msg.edit(f"## Total Players Online: {self.total_online}", embeds=self.get_server_status_embeds(_live_servers))
            except Exception as e:
                self.bot.log("[WARNING] Unable to edit server stats message. Is the Discord API down?")
                self.bot.log(f"Exception:\n{e}", time=False)
        # First post needs to be made
        else:
            _text_channel = self.bot.get_channel(self.bot.config['ServerStatus']['ServerStatusTextChannelID'])
            self.status_msg = await _text_channel.send(f"## Total Players Online: {self.total_online}", embeds=self.get_server_status_embeds(_live_servers))


    """Slash Command Group: /server
    
    A group of commands related to checking server status and info.
    """
    server = discord.SlashCommandGroup("server", "Commands related to checking official BF2:MC server status and info")
    
    @server.command(name = "count", description="Reports number of live BF2:MC servers")
    async def count(self, ctx):
        """Slash Command: /server count
        
        Reports number of live BF2:MC servers.
        Useful as backup if status channel has hit it's rate limit.
        """
        # Query API for servers
        _servers = await self.bot.cmd_query_api("servers/live")
        
        # Count live and verified servers
        _total_servers = 0
        for _server in _servers:
            if _server['is_alive'] and _server['verified']:
                _total_servers += 1
        
        await ctx.respond(f"Number of live BF2:MC servers: {_total_servers}", ephemeral=True)
    
    @server.command(name = "setstatus", description="Manually set the global server status, or set it to automatically update. Only admins can do this.")
    async def setstatus(
        self, 
        ctx, 
        status: discord.Option(
            str, 
            description="Status to set the global server status to", 
            choices=["automatic", "online", "offline", "unknown"], 
            required=True
        )
    ):
        """Slash Command: /server setstatus
        
        Manually sets the global server status, or sets it to automatically update. Only admins can do this.
        Note: Discord limits channel name changes to twice every 10 min!
        """
        # Only members with Manage Channels permission can use this command.
        if not ctx.author.guild_permissions.manage_channels:
            await ctx.respond(":warning: You do not have permission to run this command.", ephemeral=True)
            return

        self.server_status = status
        status = status.capitalize()
        _msg = f"Global server status set to: {status}"
        _msg += f"\n\n(Please allow up to {self.bot.infl.no('second', UPDATE_INTERVAL*60)} for the status to change)"
        await ctx.respond(_msg)
        self.bot.log(f"[ServerStats] {ctx.author.name} set the global server status to: {status}")


def setup(bot):
    """Called by Pycord to setup the cog"""
    cog = CogServerStatus(bot)
    cog.guild_ids = [bot.config['GuildID']]
    bot.add_cog(cog)
