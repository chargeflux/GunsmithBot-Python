import logging
import os
import asyncio
from sqlite3 import OperationalError
import discord
from discord.ext import commands
from armory import Armory, WeaponRollFinder, PlugCategoryTables
from . import constants

logger = logging.getLogger('Gunsmith.Weapons')

class Weapons(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self._help_text_search_by_perk()

    def _help_text_search_by_perk(self):
        if hasattr(self.search_by_perk, "help"):
            help_text = """Multiple perks of the same type (e.g., barrels) can be searched by separating with a comma.
            
"perks1" and "perks2" refer to the 2 columns that contain perks like Outlaw and Rampage. If both are specified, they will be considered as separate groups.
            
`?gunsmith -search -perks1 Outlaw, Snapshot Sights -perks2 Rampage` will only retrieve weapons that can roll Outlaw or Snapshot in one column and Rampage in the other.\n\n"""
            help_text += "Perk Types:\n" + "\n".join(PlugCategoryTables)
            self.search_by_perk.help = help_text

    @commands.group(invoke_without_command=True, 
            brief="Get information about weapons or perks", 
            description="Get the rolls for a weapon or information about a perk", 
            usage="<weapon>",
            help="")
    async def gunsmith(self, ctx, *, arg):
        '''
        This function corresponds to the "?gunsmith <weapon>" command.

        Parameters
        ----------
        ctx
            The context of the command being invoked. Constructed by `discord.py`
        arg
            The arguments of the command, after "?gunsmith"
        '''
        weapon = arg

        logger.info(ctx.message.content)

        if len(weapon) < 3:
            await ctx.send("Please enter a query of 3 or more characters!")
            return

        if not os.path.exists(self.bot.current_state.current_manifest):
            logger.critical(f"Manifest queried does not exist at {self.bot.current_state.current_manifest}")
            await ctx.send("An error occured. Please try again!")
            return

        armory = Armory(self.bot.current_state.current_manifest)

        logger.info(f"Searching for '{weapon}'")
        weapons = await armory.get_weapon_details(weapon)

        logger.info(f"# of weapons found: {len(weapons)}")
        result = weapons[0] # TODO: pagination

        logger.info("Constructing weapon result")
        DESCRIPTION = str(result.weapon_base_info) + "\n**" + result.intrinsic.name  + "**\n" + result.description
        STATS = '\n'.join([str(stat) for stat in result.weapon_stats])
        embed = discord.Embed(title=result.name, description= DESCRIPTION, color=constants.DISCORD_BG_HEX)
        embed.set_thumbnail(url=result.icon)

        field_idx = 0
        for perk in result.weapon_perks:
            if (field_idx + 1) % 3 == 0:
                if field_idx + 1 == 3:
                    embed.add_field(name="Stats", value=STATS, inline=True)
                else:
                    embed.add_field(name="\u200b", value="\u200b", inline=True)
                field_idx += 1
            embed.add_field(name=perk.name, value=perk, inline=True)
            field_idx += 1
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        
        light_gg_url = "https://www.light.gg/db/items/" + str(result.weapon_hash)
        embed.add_field(name="\u200b", value=light_gg_url, inline=False)

        logger.info("Sending weapon result")
        await ctx.send(embed=embed)
    
    @gunsmith.command(name="-default",
                      brief="Get default rolls for a weapon", 
                      description="Get default rolls for a weapon", 
                      usage="<weapon>",
                      help="")
    async def default_perks(self, ctx, *, arg):
        '''
        This function corresponds to the "?gunsmith -default <weapon>" command.

        Parameters
        ----------
        ctx
            The context of the command being invoked. Constructed by `discord.py`
        arg
            The arguments of the command, after "?gunsmith -default"
        '''
        weapon = arg

        logger.info(ctx.message.content)

        if len(weapon) < 3:
            await ctx.send("Please enter a query of 3 or more characters!")
            return

        if not os.path.exists(self.bot.current_state.current_manifest):
            logger.critical(f"Manifest queried does not exist at {self.bot.current_state.current_manifest}")
            await ctx.send("An error occured. Please try again!")
            return

        armory = Armory(self.bot.current_state.current_manifest)

        weapons = await armory.get_weapon_details(weapon, default=True)

        logger.info(f"# of weapons found: {len(weapons)}")
        result = weapons[0] # TODO: pagination

        logger.info("Constructing weapon result")
        DESCRIPTION = str(result.weapon_base_info) + "\n**" + result.intrinsic.name  + "**\n" + result.description
        embed = discord.Embed(title=result.name, description= DESCRIPTION, color=constants.DISCORD_BG_HEX)
        embed.set_thumbnail(url=result.icon)
        perk = result.weapon_perks[0]
        embed.add_field(name=perk.name, value=perk, inline=True)
        
        light_gg_url = "https://www.light.gg/db/items/" + str(result.weapon_hash)
        embed.add_field(name="\u200b", value=light_gg_url, inline=False)

        logger.info("Sending weapon result")
        await ctx.send(embed=embed)
        return

    @gunsmith.command(name="-perk",
                      brief="Get information about a perk", 
                      description="Get information about a perk", 
                      usage="<perk>",
                      help="")
    async def perk(self, ctx, *, arg):
        '''
        This function corresponds to the "?gunsmith -perk <perk>" command.

        Parameters
        ----------
        ctx
            The context of the command being invoked. Constructed by `discord.py`
        arg
            The arguments of the command, after "?gunsmith -perk"
        '''
        perk = arg

        logger.info(ctx.message.content)

        if len(perk) < 3:
            await ctx.send("Please enter a query of 3 or more characters!")
            return

        if not os.path.exists(self.bot.current_state.current_manifest):
            logger.critical(f"Manifest queried does not exist at {self.bot.current_state.current_manifest}")
            await ctx.send("An error occured. Please try again!")
            return

        armory = Armory(self.bot.current_state.current_manifest)

        logger.info(f"Searching for '{perk}'")
        perk_result = await armory.get_perk_details(perk)

        logger.info("Constructing perk result")
        DESCRIPTION = "**" + perk_result.name + "**\n" + perk_result.description
        embed = discord.Embed(title=perk_result.category, description=DESCRIPTION, color=constants.DISCORD_BG_HEX)
        embed.set_thumbnail(url=perk_result.icon)

        logger.info("Sending perk result")
        await ctx.send(embed=embed)
        return

    @gunsmith.command(name="-search",
                      brief="Search for weapons with specific perks", 
                      description="Search for weapons with specific perks", 
                      usage="-<perk type> <perk name>",
                      help="")
    async def search_by_perk(self, ctx, *, arg):
        '''
        This function corresponds to the "?gunsmith -search -<perk type> <perk name>" command.

        Parameters
        ----------
        ctx
            The context of the command being invoked. Constructed by `discord.py`
        arg
            The arguments of the command, after "?gunsmith -search"
        '''
        query = arg

        logger.info(ctx.message.content)

        if not os.path.exists(self.bot.current_state.current_manifest):
            logger.critical(f"Manifest queried does not exist at {self.bot.current_state.current_manifest}")
            await ctx.send("An error occured. Please try again!")
            return

        logger.info(f"Searching with parameters: '{query}'")

        weapon_plug_db = WeaponRollFinder(self.bot.current_state.current_manifest)
        result_count, results = await weapon_plug_db.process_query(query)

        if not result_count:
            await ctx.send("No weapons found! Check or modify your query. Use `?help -search` for help")
            return

        logger.info("Constructing weapon results")
        
        embed = discord.Embed(title="Weapon Results", description=f"{result_count} weapons found", color=constants.DISCORD_BG_HEX)

        field_idx = 0

        sorted_results_keys = sorted(results.keys())
        for weapon_type in sorted_results_keys:
            weapon_list = '\n'.join(results[weapon_type])
            embed.add_field(name=weapon_type, value=weapon_list, inline=True)

        logger.info("Sending weapon search results")
        await ctx.send(embed=embed)
        return

    @gunsmith.error
    @perk.error
    @search_by_perk.error
    @default_perks.error
    async def on_error(self, ctx, error):
        if ctx.invoked_with == "-perk":
            command_type = "perk"
        elif ctx.invoked_with == "-search":
            command_type = "weapon perks"
        else:
            command_type = "weapon"
        if hasattr(error, 'original'):
            logger.exception(error.original)
            if isinstance(error.original, ValueError):
                logger.error(f"Command: {ctx.message.content}")
                await ctx.send(f'{command_type.title()} could not be found.')
                return
            if isinstance(error.original, TypeError):
                logger.error(f"Command: {ctx.message.content}")
                logger.error(f'Failed to parse {command_type}')
                await ctx.send(f'Failed to parse {command_type}. Please try again.')
                return
            if isinstance(error.original, discord.errors.HTTPException):
                if error.original.status == 429:
                    logger.critical("Bot is rate-limited")
                return
            if isinstance(error.original, OperationalError):
                logger.error(f"Command: {ctx.message.content}")
                logger.error('Failed to find manifest')
                await ctx.send('An error occured. Please try again.')
                return
        if isinstance(error, commands.BadArgument):
            await ctx.send(f"Please enter the {command_type}.")
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Please enter the {command_type}. Run '?gunsmith -help' for more information.")
            return


def setup(bot):
    bot.add_cog(Weapons(bot))

def teardown(bot):
    logger.info("Tearing down cogs.weapon & pydest")
    asyncio.get_event_loop().run_until_complete(bot.current_state.destiny_api.close())
