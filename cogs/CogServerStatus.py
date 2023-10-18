"""CogServerStatus.py

Handles tasks related to checking server status and info.
Date: 10/18/2023
Authors: David Wolfe (Red-Thirten)
Licensed under GNU GPLv3 - See LICENSE for more details.
"""

import discord
from discord.ext import commands, tasks
import common.CommonStrings as CS


UPDATE_INTERVAL = 1.3 # Minutes


class CogServerStatus(discord.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.total_online = 0
        self.status_msg = None
        self.server_status = "automatic"
        self.lfg = []
    
    
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
    
    async def do_lfg_check(self, servers: list[dict]):
        """Do Looking for Game Check
        
        Finds most populated public servers for each gamemode and checks LFG users
        if either server satisfies the user's LFG preferences. This includes gamemode
        and theoretical minimum users. The theoretical users is the sum of actual players
        and LFG users with similar preferences.
        """
        # Find server with most players for each gamemode
        _cond_cq_public = lambda s: s['gametype'] == "conquest" and s['c0'] == -1 and s['c1'] == -1
        _cond_ctf_public = lambda s: s['gametype'] == "capturetheflag" and s['c0'] == -1 and s['c1'] == -1
        _cq_servers = [_s for _s in servers if _cond_cq_public(_s)]
        _ctf_servers = [_s for _s in servers if _cond_ctf_public(_s)]
        _cq_server_most = {"numplayers": -1}
        _ctf_server_most = {"numplayers": -1}
        if _cq_servers:
            _cq_server_most = max(_cq_servers, key=lambda x: x['numplayers'])
        if _ctf_servers:
            _ctf_server_most = max(_ctf_servers, key=lambda x: x['numplayers'])
        
        # Step through all LFG users
        _u_notified = []
        for _u in self.lfg:
            _cond_lfd_match = lambda p, u: p['uid'] != u['uid'] and p['min_players'] <= u['min_players'] and p['gamemode'] == u['gamemode']
            _num_theo = len([_p for _p in self.lfg if _cond_lfd_match(_p, _u)])
            # Determine server with most players based on user preference
            _server_most = None
            if _u['gamemode'] == 0:
                _server_most = _cq_server_most
            elif _u['gamemode'] == 1:
                _server_most = _ctf_server_most
            else:
                _server_most = max([_cq_server_most, _ctf_server_most], key=lambda x: x['numplayers'])
            # Send user a notification if necessary
            if 'hostname' in _server_most and _num_theo + _server_most['numplayers'] >= _u['min_players']:
                _embed = discord.Embed(
                    title="Game Found!",
                    description="Join **now** to play with others that are also looking to play!",
                    color=discord.Colour.green()
                )
                _embed.set_author(
                    name="BF2:MC Online  |  Looking for Game Notification", 
                    icon_url=CS.BOT_ICON_URL
                )
                _embed.set_thumbnail(url=CS.GM_THUMBNAILS_URL.replace("<gamemode>", _server_most['gametype']))
                _embed.add_field(name="Server Name:", value=_server_most['hostname'], inline=False)
                _embed.add_field(name="Current Players:", value=_server_most['numplayers'], inline=False)
                _embed.add_field(name="Players Looking to Play a Server Like This:", value=_num_theo, inline=False)
                _embed.set_image(url=CS.MAP_IMAGES_URL.replace("<map_name>", _server_most['map']))
                _footer = "Other LFG people are counting on you to join this server."
                _footer += "\nI assume you will, so I have gone ahead and removed you from LFG 👍"
                _embed.set_footer(text=_footer)
                self.bot.log(f'[LFG] {_u["name"]} -> "{_server_most["hostname"]}" | Message... ', end='')
                _user = self.bot.get_user(_u['uid'])
                if _user:
                    await _user.send(embed=_embed)
                    self.bot.log("Done.", time=False)
                else:
                    self.bot.log("Failed!", time=False)
                _u_notified.append(_u)
        # Remove notified users from LFG list
        for _u in _u_notified:
            self.lfg.remove(_u)
        if len(_u_notified) > 0:
            self.bot.log(f"[LFG] Matched users removed from LFG ({len(self.lfg)} still LFG)")
    
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
        
        ## Check LFG users
        await self.do_lfg_check(_live_servers)


    @discord.slash_command(name = "lfg", description="Looking for Game -- Get notified when multiple people are waiting to play")
    async def lfg(
        self, 
        ctx, 
        gamemode: discord.Option(
            int, 
            description="Which gamemode(s) to look for", 
            choices=[
                discord.OptionChoice("Conquest", value=0), 
                discord.OptionChoice("Capture the Flag", value=1),
                discord.OptionChoice("Both (Default)", value=2)
            ],
            default=2
        ),
        min_players: discord.Option(
            int, 
            description="Minimum players (playing and/or looking for game)", 
            min_value=1, 
            max_value=27, 
            default=3
        ),
        remove: discord.Option(
            bool, 
            description="Remove yourself from looking from game", 
            default=False
        )
    ):
        """Slash Command: /lfg
        
        Looking for Game (LFG)
        Caller specifies what gamemode and minimum players they want to play with
        and get's added to the LFG list to be notified later when those requirements are met.
        """
        _lfg_user = None

        # Check if they are already in the LFG list
        for _d in self.lfg:
            if _d['uid'] == ctx.author.id:
                # Remove them if specified
                if remove:
                    self.lfg.remove(_d)
                    self.bot.log(f"[LFG] Removed user {ctx.author.name} from LFG ({len(self.lfg)} total LFG).")
                    _msg = "Successfully removed you from the Looking for Game system."
                    _msg += "\n\nYou will no longer get a notification (unless you sign up again)."
                    return await ctx.respond(_msg, ephemeral=True)
                # Get pointer to existing user to update
                _lfg_user = _d
                break
        # If specified to remove, but couldn't find, display warning message
        if remove and not _lfg_user:
            return await ctx.respond(":warning: You are not currently looking for a game.", ephemeral=True)
        
        # Update preferences in LFG list
        if _lfg_user:
            if _lfg_user['gamemode'] != gamemode:
                _lfg_user['gamemode'] = gamemode
            if _lfg_user['min_players'] != min_players:
                _lfg_user['min_players'] = min_players
            _msg = ":white_check_mark: You have successfully updated your LFG preferences!"
            _msg += "\n\nYou will now get a notification when your new preferences are met."
            return await ctx.respond(_msg, ephemeral=True)
        
        # Add user to LFG list
        _lfg_user = {
            "uid": ctx.author.id,
            "name": ctx.author.name,
            "gamemode": gamemode,
            "min_players": min_players
        }
        self.lfg.append(_lfg_user)
        self.bot.log(f"[LFG] Added user {ctx.author.name} to LFG ({len(self.lfg)} total LFG).")
        _msg = ":white_check_mark: You have successfully signed up for LFG!"
        _msg += "\n\nYou will get a notification from me (via private message) when a server:"
        _msg += "\n- Matches the gamemode you are looking for"
        _msg += "\n- Meets your minimum number of people playing and/or waiting for that gamemode"
        _msg += "\n\n*(If you wish to remove yourself from LFG, use*  `/lfg remove True`  *)*"
        return await ctx.respond(_msg, ephemeral=True)

    
    """Slash Command Group: /server
    
    A group of commands related to checking server status and info.
    """
    server = discord.SlashCommandGroup("server", "Commands related to checking official BF2:MC server status and info")
    
    @server.command(name = "count", description="Reports number of live BF2:MC servers")
    @commands.cooldown(1, 30, commands.BucketType.member)
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
