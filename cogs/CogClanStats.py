"""CogClanStats.py

Handles tasks related to checking clan stats and info.
Date: 10/25/2023
Authors: David Wolfe (Red-Thirten)
Licensed under GNU GPLv3 - See LICENSE for more details.
"""

import discord
from discord.ext import commands
from discord.ext.pages import Paginator, Page
import common.CommonStrings as CS


async def get_clantags(ctx: discord.AutocompleteContext):
    """Autocomplete Context: Get clan tags
    
    Returns array of all clan tags in the backend's database.
    """
    _dbEntries = ctx.bot.db_backend.getAll(
        "Clans", 
        ["tag"]
    )
    if _dbEntries == None: return []
    
    return [_tag['tag'] for _tag in _dbEntries]


class CogClanStats(discord.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.Cog.listener()
    async def on_ready(self):
        """Listener: On Cog Ready
        
        Runs when the cog is successfully cached within the Discord API.
        """
        self.bot.log("[ClanStats] Successfully cached!")


    """Slash Command Group: /clan
    
    A group of commands related to checking clan stats.
    """
    clan = discord.SlashCommandGroup("clan", "Commands related to checking clan stats")

    @clan.command(name = "stats", description="Displays a specific clans's BF2:MC Online stats")
    @commands.cooldown(1, 180, commands.BucketType.member)
    async def stats(
        self,
        ctx,
        tag: discord.Option(
            str, 
            description="Tag of clan to look up", 
            autocomplete=discord.utils.basic_autocomplete(get_clantags), 
            min_length=2, 
            max_length=3, 
            required=True
        ) # type: ignore
    ):
        """Slash Command: /clan stats
        
        Displays a specific clans's BF2:MC Online stats.
        """
        await ctx.defer() # Temp fix for slow SQL queries
        _escaped_tag = self.bot.escape_discord_formatting(tag)

        ## Get clan data
        _clan_data = self.bot.db_backend.getOne(
            "Clans", 
            [
                "clanid",
                "name",
                "homepage",
                "info",
                "region",
                "score",
                "wins",
                "losses",
                "draws",
                "created_at"
            ], 
            ("tag=%s", [tag])
        )
        if _clan_data == None:
            return await ctx.respond(
                f':warning: A clan with the tag of "{_escaped_tag}" could not be found.', 
                #ephemeral=True
            )

        ## Get clan members
        _clan_members = self.bot.db_backend.leftJoin(
            ("ClanRanks", "Players"),
            (["`rank`"], ["uniquenick"]),
            ("profileid", "profileid"),
            ("clanid=%s", [_clan_data['clanid']]),
            ["`rank`", "ASC"]
        )
        if _clan_members == None:
            return await ctx.respond(
                f':warning: This clan has no members? Wat.', 
                #ephemeral=True
            )
        
        ## Get clan rank
        _clan_rank = self.bot.db_backend.getOne(
            "Leaderboard_clan",
            ["`rank`"], 
            ("clanid=%s", [_clan_data['clanid']])
        )
        if _clan_rank: 
            _clan_rank = f"#{_clan_rank['rank']}"
        else:
            _clan_rank = ""

        ## Calculate additional data
        # Determine embed color
        _color = discord.Colour.random(seed=_clan_data['clanid'])
        # Calculate total games & win percentage
        _total_games = _clan_data['wins'] + _clan_data['losses'] + _clan_data['draws']
        _win_percentage = (_clan_data['wins'] / max(_total_games, 1)) * 100
        _win_percentage = round(_win_percentage, 2)
        _win_percentage = str(_win_percentage) + "%"
        
        ## Build embeds/pages
        _embeds = {}
        _select_options = []
        _author_name = "BF2:MC Online  |  Clan Stats"
        _author_url = CS.CLAN_REGION_DATA[_clan_data['region']-1][1]
        # Summary
        _title = "Summary"
        _desc = f"**Tag: {_escaped_tag}**"
        _desc += f"\n**Rank: {_clan_rank}**"
        _desc += f"\n\n{_clan_data['homepage']}"
        _desc += f"\n\n{_clan_data['info']}"
        _e_summary = discord.Embed(
            title=_clan_data['name'],
            description=_desc,
            color=_color
        )
        _e_summary.set_author(
            name=_author_name, 
            icon_url=_author_url
        )
        _e_summary.set_thumbnail(url=CS.CLAN_THUMB_URL)
        _e_summary.add_field(name="Members:", value=len(_clan_members), inline=False)
        _e_summary.add_field(name="Score:", value=_clan_data['score'], inline=True)
        _e_summary.add_field(name="Games:", value=_total_games, inline=True)
        _e_summary.add_field(name="Win Percentage:", value=_win_percentage, inline=True)
        _e_summary.add_field(name="Wins:", value=_clan_data['wins'], inline=True)
        _e_summary.add_field(name="Losses:", value=_clan_data['losses'], inline=True)
        _e_summary.add_field(name="Draws:", value=_clan_data['draws'], inline=True)
        _e_summary.add_field(name="Region:", value=CS.CLAN_REGION_DATA[_clan_data['region']-1][0], inline=False)
        _e_summary.set_footer(text=f"Established {_clan_data['created_at'].strftime('%m/%d/%Y')} -- BFMCspy Official Stats")
        _embeds[_title] = _e_summary
        _select_options.append(
            discord.SelectOption(
                label=_title,
                description="General overview of clan",
                emoji="📊"
            )
        )
        # Members
        _title = "Members"
        _desc = f"**Tag: {_escaped_tag}**"
        _desc += f"\n**Rank: {_clan_rank}**"
        _desc += f"\n### Clan {_title}:"
        _members = "```\n"
        _roles = "```\n"
        for _m in _clan_members:
            _members += f"{_m['uniquenick']}\n"
            _roles += f"{CS.CLAN_RANK_STRINGS[_m['rank']]}\n"
        _members += "```"
        _roles += "```"
        _e_members = discord.Embed(
            title=_clan_data['name'],
            description=_desc,
            color=_color
        )
        _e_members.set_author(
            name=_author_name, 
            icon_url=_author_url
        )
        _e_members.set_thumbnail(url=CS.CLAN_THUMB_URL)
        _e_members.add_field(name="Nickname:", value=_members, inline=True)
        _e_members.add_field(name="Role:", value=_roles, inline=True)
        _e_members.set_footer(text=f"Established {_clan_data['created_at'].strftime('%m/%d/%Y')} -- BFMCspy Official Stats")
        _embeds[_title] = _e_members
        _select_options.append(
            discord.SelectOption(
                label=_title,
                description="List of clan members",
                emoji="👥"
            )
        )

        await ctx.respond(embed=_embeds["Summary"], view=self.ClanStatsView(_select_options, _embeds))
    
    class ClanStatsView(discord.ui.View):
        """Discord UI View: Clan Stats
        
        Handles the `/clan stats` view which includes a select menu of passed options
        to display various passed embed "pages".
        Automatically disables list selections after 180 sec.
        """
        def __init__(self, select_options: list[discord.SelectOption], embeds: dict):
            super().__init__(disable_on_timeout=True)
            self.embeds = embeds
            self.select_callback.placeholder = select_options[0].label
            self.select_callback.options = select_options
        
        @discord.ui.select(
            min_values = 1,
            max_values = 1
        )
        async def select_callback(self, select, interaction): # the function called when the user is done selecting options
            select.placeholder = select.values[0]
            await interaction.response.edit_message(
                embed=self.embeds[select.values[0]], 
                view=self
            )

    @clan.command(name = "leaderboard", description="See a top 50 leaderboard for a particular clan stat in BF2:MC Online")
    @commands.cooldown(1, 180, commands.BucketType.channel)
    async def leaderboard(
        self,
        ctx,
        stat: discord.Option(
            str, 
            name="leaderboard", 
            description="Leaderboard to display", 
            choices=[
                discord.OptionChoice("Score", value='score')
            ], 
            required=True
        ) # type: ignore
    ):
        """Slash Command: /clan leaderboard
        
        Displays a top 50 leaderboard of the specified BF2:MC Online clan stat.
        """
        _rank = 1
        _pages = []
        _dbEntries = self.bot.db_backend.getAll(
            "Clans", 
            ["name", "tag", stat], 
            None, 
            [stat, "DESC"], # Order highest first
            [50] # Limit to top 50 clans
        )
        _title = f":first_place:  BF2:MC Online | Top Clan {CS.LEADERBOARD_STRINGS[stat]} Leaderboard  :first_place:"
        if _dbEntries:
            _dbEntries = self.bot.split_list(_dbEntries, 10) # Split into pages of 10 entries each
            for _page in _dbEntries:
                _embed = discord.Embed(
                    title=_title,
                    description="*Top 50 clans across all servers.*",
                    color=discord.Colour.gold()
                )
                _clan_names = "```\n"
                _stats = "```\n"
                for _e in _page:
                    _rank_str = f"#{_rank}"
                    _tag_str = f"[{_e['tag']}]"
                    _clan_names += f"{_rank_str.ljust(3)} | {_tag_str.ljust(5)} {_e['name']}\n"
                    if stat == 'score':
                        _stats += f"{str(_e[stat]).rjust(6)} pts.\n"
                    else:
                        _stats += "\n"
                    _rank += 1
                _clan_names += "```"
                _stats += "```"
                _embed.add_field(name="Clan:", value=_clan_names, inline=True)
                _embed.add_field(name=f"{CS.LEADERBOARD_STRINGS[stat]}:", value=_stats, inline=True)
                _embed.set_footer(text="BFMCspy Official Stats")
                _pages.append(Page(embeds=[_embed]))
        else:
            _embed = discord.Embed(
                title=_title,
                description="No stats yet.",
                color=discord.Colour.gold()
            )
            _pages = [Page(embeds=[_embed])]
        _paginator = Paginator(pages=_pages, author_check=False)
        await _paginator.respond(ctx.interaction)


def setup(bot):
    """Called by Pycord to setup the cog"""
    cog = CogClanStats(bot)
    cog.guild_ids = [bot.config['GuildID']]
    bot.add_cog(cog)
