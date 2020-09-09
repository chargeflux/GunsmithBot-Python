import logging
import os
import asyncio
from sqlite3 import OperationalError
import discord
from discord.ext import commands
from armory import Armory
from . import constants

logger = logging.getLogger('Gunsmith.Weapons')

class Weapons(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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

    @gunsmith.command(name="-help",
                      hidden=True)
    async def help(self, ctx, *args):
        '''
        This function corresponds to the "?gunsmith -help" command.

        Parameters
        ----------
        ctx
            The context of the command being invoked. Constructed by `discord.py`
        *args
            The arguments of the command as a tuple separated by whitespace, after "?gunsmith -help"
        '''
        if not args:
            await ctx.send_help(*args)
        else:
            await ctx.send_help(' '.join(args))
        return

    @gunsmith.error
    @perk.error
    async def on_error(self, ctx, error):
        if ctx.invoked_with == "-perk":
            command_type = "perk"
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
            await ctx.send(f"Please enter the {command_type} name.")
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Please enter the {command_type} name. Run '?gunsmith -help' for more information.")
            return

def setup(bot):
    bot.add_cog(Weapons(bot))

def teardown(bot):
    logger.info("Tearing down cogs.weapon & pydest")
    asyncio.get_event_loop().run_until_complete(bot.current_state.destiny_api.close())
