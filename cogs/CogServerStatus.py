"""CogServerStatus.py

Handles tasks related to checking server status and info.
Date: 02/18/2024
Authors: David Wolfe (Red-Thirten)
Licensed under GNU GPLv3 - See LICENSE for more details.
"""

import discord
from discord.ext import commands, tasks
import common.CommonStrings as CS


UPDATE_INTERVAL = 1.3 # Minutes
LFG_GAMEMODE_CHOICES = [
    discord.OptionChoice("Conquest", value=0), 
    discord.OptionChoice("Capture the Flag", value=1),
    discord.OptionChoice("Both (CQ & CTF)", value=2)
]


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
        Servers are listed in order of their player count, from highest to lowest.
        """
        ## Check for missing query data
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
            _embed.set_footer(text=f"Data fetched at: {self.bot.last_query_time.strftime('%I:%M:%S %p UTC')} -- {self.bot.config['API']['HumanURL']}")
            return [_embed]
        
        ## Check for no servers online
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
            _embed.set_footer(text=f"Data fetched at: {self.bot.last_query_time.strftime('%I:%M:%S %p UTC')} -- {self.bot.config['API']['HumanURL']}")
            return [_embed]

        ## Default - Build server status embeds
        _embeds = []

        # Build LFG embed (if not empty)
        _num_lfg = len(self.lfg)
        if _num_lfg > 0:
            _names = "```\n"
            _p_gamemodes = "```\n"
            _p_players = "```\n"
            for _d in self.lfg:
                _names += f"{_d['name']}\n"
                _p_gamemodes += f"{LFG_GAMEMODE_CHOICES[_d['gamemode']].name}\n"
                _p_players += f"{str(_d['min_players']).rjust(10)}\n"
            _names += "```"
            _p_gamemodes += "```"
            _p_players += "```"
            _embed = discord.Embed(
                title=f"{_num_lfg} members are looking to play", 
                description="Use `/lfg join` to join this list and get notified when enough players are online.", 
                color=discord.Colour.blurple()
            )
            _embed.set_author(
                name="Looking for Game (LFG) System", 
                icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/9/9c/Magnifying_glass_CC0.svg/1200px-Magnifying_glass_CC0.svg.png"
            )
            _embed.add_field(name="Members Waiting:", value=_names, inline=True)
            _embed.add_field(name="Preferred Gamemode:", value=_p_gamemodes, inline=True)
            _embed.add_field(name="Preferred # of Players:", value=_p_players, inline=True)
            _embeds.append(_embed)

        # Sort by player count and limit to top 3 server embeds
        _sorted_servers = sorted(servers, key=lambda x: x['numplayers'], reverse=True)
        _sorted_servers = _sorted_servers[:3]
        for _s in _sorted_servers:
            _embeds.append(self.bot.get_server_status_embed(_s))
        
        return _embeds
    
    async def do_lfg_check(self, servers: list[dict]):
        """Do Looking for Game Check
        
        Finds most populated public servers for each gamemode and checks LFG users
        if either server satisfies the user's LFG preferences. This includes gamemode
        and theoretical minimum users. The theoretical users is the sum of actual players
        and LFG users with similar preferences.
        """
        # Check for missing query data
        if servers == None:
            if len(self.lfg) > 0:
                self.bot.log("[LFG] Skipping LFG check (missing server data)")
            return

        # Find server with most players for each gamemode
        _cond_cq_public = lambda s: s['gametype'] == "conquest" and not s['n0'] and not s['n1'] and s['numplayers'] < s['maxplayers']
        _cond_ctf_public = lambda s: s['gametype'] == "capturetheflag" and not s['n0'] and not s['n1'] and s['numplayers'] < s['maxplayers']
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

        # Get handle for server status text channel
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

        ## Create live server list (excluding dead/unverified servers) & calculate players online
        _live_servers = []
        _total_players = 0
        if _servers != None:
            for _server in _servers:
                if (_server['is_alive'] and _server['verified']):
                    _live_servers.append(_server)
                    _total_players += _server['numplayers']
        else:
            # API query failed
            _live_servers = None
            _total_players = "???"
        
        ## Update bot's activity if total players has changed
        if _total_players != self.total_online:
            self.total_online = _total_players
            _activity = discord.Activity(type=discord.ActivityType.watching, name=f"{_total_players} Veterans online")
            await self.bot.change_presence(activity=_activity)

        ## Update server status channel name
        if self.server_status == "automatic":
            if _servers == None:
                await self.set_status_channel_name("unknown")
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
        
        ## Check LFG users
        await self.do_lfg_check(_live_servers)

        ## Update stats channel post
        _msg = f"## Total Players Online: {self.total_online}"
        _msg += "\n*Note: Only the top 3 most populated servers are displayed*"
        _embeds = self.get_server_status_embeds(_live_servers)
        # Post already exists
        if self.status_msg != None:
            try:
                await self.status_msg.edit(_msg, embeds=_embeds)
            except Exception as e:
                self.bot.log("[WARNING] Unable to edit server status message. Is the Discord API down?")
                self.bot.log(f"Exception:\n{e}", time=False)
        # First post needs to be made
        else:
            _text_channel = self.bot.get_channel(self.bot.config['ServerStatus']['ServerStatusTextChannelID'])
            self.status_msg = await _text_channel.send(_msg, embeds=_embeds)


    """Slash Command Group: /lfg
    
    A group of commands related to joining, editing, or leaving the Looking for Game (LFG) queue.
    """
    lfg = discord.SlashCommandGroup("lfg", "Commands related to joining, editing, or leaving the Looking for Game (LFG) queue")

    def get_dict_in_lfg_for_uid(self, uid: int) -> dict:
        """Get Dictionary in LFG list for UID
        
        Helper function for LFG Slash Commands.
        Returns None if not found in list.
        """
        for _d in self.lfg:
            if _d['uid'] == uid: return _d
        return None
    
    @lfg.command(name = "join", description="Join Looking for Game -- Get notified when multiple people are ready to play")
    async def lfg_join(
        self, 
        ctx, 
        gamemode: discord.Option(
            int, 
            description="Which gamemode(s) to look for", 
            choices=LFG_GAMEMODE_CHOICES, 
            required=True
        ), # type: ignore
        min_players: discord.Option(
            int, 
            description="Minimum players (playing and/or looking for game)", 
            min_value=1, 
            max_value=27, 
            required=True
        ) # type: ignore
    ):
        """Slash Command: /lfg join
        
        Looking for Game (LFG)
        Caller specifies what gamemode and minimum players they want to play with
        and get's added to the LFG list to be notified later when those requirements are met.
        """
        _lfg_user = self.get_dict_in_lfg_for_uid(ctx.author.id)
        
        # If caller already in LFG list, update preferences
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
        self.bot.log(f"[LFG] Added user {_lfg_user['name']} to LFG ({len(self.lfg)} total LFG).")

        # Send info message and reply embed
        _escaped_name = self.bot.escape_discord_formatting(_lfg_user['name'])
        _description = "Use `/lfg join` to let them know you want to play too!"
        _description += f"\nSee who else is looking to play: <#{self.bot.config['ServerStatus']['ServerStatusTextChannelID']}>"
        _embed = discord.Embed(
            title=f"{_escaped_name} is looking to play!", 
            description=_description, 
            color=discord.Colour.blurple()
        )
        _embed.set_author(
            name="Looking for Game (LFG) System", 
            icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/9/9c/Magnifying_glass_CC0.svg/1200px-Magnifying_glass_CC0.svg.png"
        )
        _embed.add_field(
            name="Preferred Gamemode:", 
            value=LFG_GAMEMODE_CHOICES[gamemode].name, 
            inline=True
        )
        _embed.add_field(
            name="Preferred # of Players:", 
            value=min_players, 
            inline=True
        )
        _embed.set_footer(text=f"{_lfg_user['name']}, check your DMs for a message with more info.")
        _msg = ":white_check_mark: You have successfully signed up for LFG (Looking for Game)!"
        _msg += "\n- You will get notification from me here when a server:"
        _msg += "\n  - Matches the gamemode you are looking for"
        _msg += "\n  - Meets your minimum number of people playing and/or waiting for that gamemode"
        _msg += "\n- Use `/lfg edit` (in the BF2MC Discord server; not here) to edit your notification preferences."
        _msg += "\n- Use `/lfg leave` to leave the LFG queue."
        await ctx.author.send(_msg)
        return await ctx.respond(embed=_embed)
    
    @lfg.command(name = "edit", description="Edit Looking for Game -- Get notified when multiple people are ready to play")
    async def lfg_edit(
        self, 
        ctx, 
        gamemode: discord.Option(
            int, 
            description="Which gamemode(s) to look for", 
            choices=LFG_GAMEMODE_CHOICES, 
            required=True
        ), # type: ignore
        min_players: discord.Option(
            int, 
            description="Minimum players (playing and/or looking for game)", 
            min_value=1, 
            max_value=27, 
            required=True
        ) # type: ignore
    ):
        """Slash Command: /lfg edit
        
        Looking for Game (LFG)
        Caller specifies what gamemode and minimum players they want to play with
        and get's added to the LFG list to be notified later when those requirements are met.
        """
        return await self.lfg_join(ctx, gamemode, min_players)
    
    @lfg.command(name = "leave", description="Leave Looking for Game -- Leave the LFG queue and not get notified")
    async def lfg_leave(self, ctx):
        """Slash Command: /lfg leave
        
        Removes the caller from the LFG list if they are present.
        """
        _lfg_user = self.get_dict_in_lfg_for_uid(ctx.author.id)

        if _lfg_user:
            self.lfg.remove(_lfg_user)
            self.bot.log(f"[LFG] Removed user {ctx.author.name} from LFG ({len(self.lfg)} total LFG).")
            _msg = "Successfully removed you from the Looking for Game queue."
            _msg += "\n\nYou will no longer get a notification (unless you sign up again)."
            return await ctx.respond(_msg, ephemeral=True)
        else:
            return await ctx.respond(":warning: You are not currently looking for a game.", ephemeral=True)
    
    
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
        ) # type: ignore
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
