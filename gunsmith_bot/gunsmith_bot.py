import logging
import discord
from discord.ext import commands
import os
import asyncio
from dataclasses import dataclass
import constants
import pydest
from armory import Armory, loader

@dataclass
class State():
    current_manifest: str = ''
    destiny_api: object = None

current_state: State = State()

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s', 
                    datefmt='%Y-%m-%d %I:%M:%S %p')
logger = logging.getLogger('Gunsmith')  
logger.setLevel(logging.INFO)

logging.getLogger("discord").setLevel("WARNING")

if not (DISCORD_KEY := os.environ.get("DISCORD_KEY")):
    logger.error("Failed to retrieve DISCORD_KEY")
    raise ValueError("Please set the environment variable for DISCORD_KEY")

bot = commands.Bot(command_prefix="!", description='Retrieve rolls for Destiny 2 weapons')

@bot.event
async def on_ready():
    """
    Triggered when the bot successfully logs into Discord and is ready. Note that this is not limited to
    the start up of the bot.
    """
    logger.log(logging.INFO, f'We have logged in as {bot.user}')
    if not current_state.current_manifest:
        try:
            current_state.destiny_api = await loader.initialize_destiny()
            current_state.current_manifest = await loader.get_manifest(current_state.destiny_api)
        except pydest.PydestException:
            logger.critical("Failed to initialize PyDest. Quitting.")
            await bot.logout()
        except AttributeError:
            logger.critical("Failed to retrieve manifest. Quitting.")
            current_state.destiny_api.close()
            await bot.logout()

@bot.command()
async def gunsmith(ctx, *, arg):
    '''
    This function corresponds to the "!gunsmith <weapon>" command.

    Parameters
    ----------
    ctx
        The context of the command being invoked. Constructed by `discord.py`
    *args
        The arguments of the command, after "!gunsmith"
    '''
    weapon = arg

    armory = Armory(current_state.current_manifest)
    weapons = armory.get_weapon_details(weapon)
    result = weapons[0] #TODO: pagination

    DESCRIPTION = str(result.weapon_base_info) + "\n" + result.description
    embed = discord.Embed(title=result.name, description= DESCRIPTION, color=constants.DISCORD_BG_HEX)

    for perk in result.weapon_perks:
        embed.add_field(name=perk.name, value=str(perk), inline=False)

    await ctx.send(embed=embed)

@gunsmith.error
async def on_error(ctx, error):
    if hasattr(error, 'original'):
        logger.exception(error.original)
        if isinstance(error.original, ValueError):
            logger.error(ctx.message.content, exc_info=1)
            await ctx.send('Weapon could not be found.')
        if isinstance(error.original, TypeError):
            logger.error(ctx.message.content)
            logger.error('Failed to parse weapon', exec_info=1)
            await ctx.send('Failed to parse weapon. Please notify my creator.')
    if isinstance(error, commands.BadArgument):
        await ctx.send("Please enter the weapon name.")

logger.info("Starting up bot")
bot.run(DISCORD_KEY)