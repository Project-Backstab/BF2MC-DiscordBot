"""CogServerStatus.py

Handles tasks related to checking server status and info.
Date: 06/29/2023
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
    

    def get_team_score_str(self, gamemode: str, score: int) -> str:
        """Get Team Score String
        
        Returns a formatted string for the team's score given the current gamemode.
        """
        if gamemode == "conquest":
            return f"***{self.bot.infl.no('ticket', score)} remaining***"
        else:
            return f"***{self.bot.infl.no('flag', score)} captured***"
    
    def get_player_attr_list_str(self, players: list, attribute: str) -> str:
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
    
    def get_server_stat_embeds(self) -> list[discord.Embed]:
        """Get Server Statistic Embeds
        
        Returns a list of Discord Embeds that each display each server's current statistics.
        """
        _embeds = []

        if self.bot.cur_query_data != None:
            if self.bot.cur_query_data['count'] > 0:
                for s in self.bot.cur_query_data['results']:
                    # Get total player count
                    _player_count = len(s['players'])

                    # Setup embed color based on total player count
                    if _player_count == 0:
                        _color = discord.Colour.yellow()
                    elif _player_count == s['max_players']:
                        _color = discord.Colour.red()
                    else:
                        _color = discord.Colour.green()
                    
                    # Check if server is official
                    if s['id'] in self.bot.config['ServerStatus']['OfficialIDs']:
                        _description = "*Official Server*"
                    else:
                        _description = "*Unofficial Server*"
                    
                    # Parse player list into ordered teams
                    _team1 = []
                    _team2 = []
                    for _p in s['players']:
                        if _p['team'] == 0:
                            _team1.append(_p)
                        else:
                            _team2.append(_p)
                    _team1 = sorted(_team1, key=lambda x: x['score'], reverse=True)
                    _team2 = sorted(_team2, key=lambda x: x['score'], reverse=True)
                    
                    # Setup Discord embed
                    _embed = discord.Embed(
                        title=s['server_name'],
                        description=_description,
                        color=_color
                    )
                    _embed.set_author(
                        name="BF2:MC Server Info", 
                        icon_url=CS.COUNTRY_FLAGS_URL.replace("<code>", s['country'].lower())
                    )
                    _embed.set_thumbnail(url=CS.GM_THUMBNAILS_URL.replace("<gamemode>", s['game_type']))
                    _embed.add_field(name="Players:", value=f"{_player_count}/{s['max_players']}", inline=False)
                    _embed.add_field(name="Gamemode:", value=CS.GM_STRINGS[s['game_type']], inline=True)
                    _embed.add_field(name="Time Elapsed:", value=s['time_elapsed'][3:], inline=True)
                    _embed.add_field(name="Time Limit:", value=s['time_limit'][3:], inline=True)
                    _embed.add_field(
                        name=CS.TEAM_STRINGS[s['team1_country']], 
                        value=self.get_team_score_str(s['game_type'], s['team1_score']), 
                        inline=False
                    )
                    _embed.add_field(name="Player:", value=self.get_player_attr_list_str(_team1, 'name'), inline=True)
                    _embed.add_field(name="Score:", value=self.get_player_attr_list_str(_team1, 'score'), inline=True)
                    _embed.add_field(name="Deaths:", value=self.get_player_attr_list_str(_team1, 'deaths'), inline=True)
                    _embed.add_field(
                        name=CS.TEAM_STRINGS[s['team2_country']], 
                        value=self.get_team_score_str(s['game_type'], s['team2_score']), 
                        inline=False
                    )
                    _embed.add_field(name="Player:", value=self.get_player_attr_list_str(_team2, 'name'), inline=True)
                    _embed.add_field(name="Score:", value=self.get_player_attr_list_str(_team2, 'score'), inline=True)
                    _embed.add_field(name="Deaths:", value=self.get_player_attr_list_str(_team2, 'deaths'), inline=True)
                    _embed.set_image(url=CS.MAP_IMAGES_URL.replace("<map_name>", s['map_name']))
                    _embed.set_footer(text=f"Data fetched at: {self.bot.last_query.strftime('%I:%M:%S %p UTC')} -- {self.bot.config['API']['RootURL']}")
                    _embeds.append(_embed)
            else:
                _description = f"""
                There are no BF2:MC servers currently online :cry:
                Please check <#{self.bot.config['ServerStatus']['AnnouncementTextChannelID']}> for more info.
                """
                _embed = discord.Embed(
                    title=":red_circle:  Servers Offline",
                    description=_description,
                    color=discord.Colour.red()
                )
                _embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/8/8d/Computer_crash.svg/1200px-Computer_crash.svg.png")
                _embed.set_footer(text=f"Data fetched at: {self.bot.last_query.strftime('%I:%M:%S %p UTC')} -- {self.bot.config['API']['RootURL']}")
                _embeds.append(_embed)
        else:
            _description = """
            *The server stats API endpoint is currently down.*

            **BF2:MC servers may still be online.**
            **We just can't display any stats at this time.**

            """
            _embed = discord.Embed(
                    title=":yellow_circle:  Server Stats Unavailable",
                    description=_description,
                    color=discord.Colour.yellow()
                )
            _embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/8/8d/Computer_crash.svg/1200px-Computer_crash.svg.png")
            _embed.set_footer(text=f"Data fetched at: {self.bot.last_query.strftime('%I:%M:%S %p UTC')} -- {self.bot.config['API']['RootURL']}")
            _embeds.append(_embed)
        
        return _embeds
    
    async def set_status_channel_name(self, status: str):
        """Set Status Channel Name
        
        Sets the global server status for the given status string.
        Only updates the channel if the status has changed and is valid.
        NOTE: Discord limits channel name changes to twice every 10 min.
        """
        _voice_channel = self.bot.get_channel(self.bot.config['ServerStatus']['StatusVoiceChannelID'])
        if status in CS.STATUS_STRINGS and _voice_channel.name != CS.STATUS_STRINGS[status]:
            print(f"{self.bot.get_datetime_str()}: [ServerStatus] {CS.STATUS_STRINGS[status]}")
            await _voice_channel.edit(name=CS.STATUS_STRINGS[status], reason="[BackstabBot] Server status updated.")


    @commands.Cog.listener()
    async def on_ready(self):
        """Listener: On Cog Ready
        
        Runs when the cog is successfully cached within the Discord API.
        """
        print(f"{self.bot.get_datetime_str()}: [ServerStatus] Successfully cached!")
        
        # Check that all channels in the config are valid
        _cfg_sub_keys = [
            'StatusVoiceChannelID',
            'ServerStatsTextChannelID',
            'AnnouncementTextChannelID'
        ]
        await self.bot.check_channel_ids_for_cfg_key('ServerStatus', _cfg_sub_keys)

        # Get status message (if it exists) from message history (if we haven't already)
        if self.status_msg == None:
            _text_channel = self.bot.get_channel(self.bot.config['ServerStatus']['ServerStatsTextChannelID'])
            async for _m in _text_channel.history(limit=3):
                # Check if the message was sent by the user
                if _m.author == self.bot.user:
                    self.status_msg = await _text_channel.fetch_message(_m.id)
                    break
        
        # Start Status Loop
        if not self.StatusLoop.is_running():
            self.StatusLoop.start()
            print(f"{self.bot.get_datetime_str()}: [ServerStatus] StatusLoop started ({UPDATE_INTERVAL} min. interval).")
            # Set channel description if it is not correct
            _text_channel = self.bot.get_channel(self.bot.config['ServerStatus']['ServerStatsTextChannelID'])
            _topic = f"Live server statistics (Updated every {self.bot.infl.no('second', round(UPDATE_INTERVAL*60))})"
            if _text_channel.topic != _topic:
                await _text_channel.edit(topic=_topic)
    

    @tasks.loop(minutes=UPDATE_INTERVAL)
    async def StatusLoop(self):
        """Task Loop: Status Loop
        
        Runs every interval period, references bot's latest query data, 
        updates status voice channel, and updates info text channel.
        """
        ## Calculate total players online
        _total_online = 0
        if self.bot.cur_query_data != None:
            for _s in self.bot.cur_query_data['results']:
                for _ in _s['players']:
                    _total_online += 1
        
        ## Update bot's activity if total players has changed
        if _total_online != self.total_online:
            self.total_online = _total_online
            _activity = discord.Activity(type=discord.ActivityType.watching, name=f"{_total_online} Veterans online")
            await self.bot.change_presence(activity=_activity)

        ## Update status channel name
        if self.server_status == "automatic":
            if self.bot.cur_query_data == None:
                await self.set_status_channel_name("unknown")
            elif self.bot.cur_query_data['count'] > 0:
                await self.set_status_channel_name("online")
            else:
                await self.set_status_channel_name("offline")
        elif self.server_status == "online":
            await self.set_status_channel_name("online")
        elif self.server_status == "offline":
            await self.set_status_channel_name("offline")
        elif self.server_status == "unknown":
            await self.set_status_channel_name("unknown")

        ## Update stats channel post
        if self.status_msg != None:
            try:
                await self.status_msg.edit(f"## Total Players Online: {self.total_online}", embeds=self.get_server_stat_embeds())
            except:
                pass
        else:
            _text_channel = self.bot.get_channel(self.bot.config['ServerStatus']['ServerStatsTextChannelID'])
            await _text_channel.send(f"## Total Players Online: {self.total_online}", embeds=self.get_server_stat_embeds())


    """Slash Command Group: /server
    
    A group of commands related to checking server status and info.
    """
    server = discord.SlashCommandGroup("server", "Commands related to checking official BF2:MC server status and info")
    
    @server.command(name = "count", description="Reports number of live BF2:MC servers")
    async def count(self, ctx):
        """Slash Command: /server count
        
        Reports number of live BF2:MC servers (since last status check).
        Useful as backup if status channel has hit it's rate limit.
        """
        if self.bot.cur_query_data != None:
            await ctx.respond(f"Number of live BF2:MC servers: {self.bot.cur_query_data['count']}", ephemeral=True)
        else:
            raise commands.CommandError("There was an error retrieving this data. The statistics API may be down at the moment.")
    
    @server.command(name = "setstatus", description="Manually set the global server status, or set it to automatically update. Only admins can do this.")
    @discord.default_permissions(manage_channels=True) # Only members with Manage Channels permission can use this command.
    @commands.cooldown(2, 600, commands.BucketType.guild) # Discord limits channel name changes to twice every 10 min.
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
        """
        self.server_status = status
        status = status.capitalize()
        _msg = f"Global server status set to: {status}"
        _msg += f"\n\n(Please allow up to {self.bot.infl.no('second', UPDATE_INTERVAL*60)} for the status to change)"
        await ctx.respond(_msg, ephemeral=True)
        print(f"{self.bot.get_datetime_str()}: [PlayerStats] {ctx.author.name} set the global server status to: {status}")


def setup(bot):
    """Called by Pycord to setup the cog"""
    cog = CogServerStatus(bot)
    cog.guild_ids = [bot.config['GuildID']]
    bot.add_cog(cog)
