import logging
import os
import asyncio
import datetime
from dataclasses import dataclass, field
from sqlite3 import OperationalError
import discord
from discord.ext import commands, tasks
import pydest
import constants
from armory import Armory, loader

@dataclass
class State():
    current_manifest: str = ''
    destiny_api: pydest = None
    old_manifests: [str] = field(default_factory=list)

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

class UpdateManifest(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.update_manifest.start()

    def cog_unload(self):
        self.update_manifest.stop()

    @tasks.loop(hours=24)
    async def update_manifest(self):
        if current_state.destiny_api:
            await loader.update_manifest(current_state.destiny_api)
            manifest_location = await loader.get_manifest(current_state.destiny_api)
            if manifest_location != current_state.current_manifest:
                old_manifests.append(current_state.current_manifest)
                current_state.current_manifest = manifest_location
                

    @update_manifest.before_loop
    async def before_update_manifest(self):
        await self.bot.wait_until_ready()
        for old_manifest in current_state.old_manifests:
            try:
                os.remove(old_manifest)
            except OSError as ex:
                logger.critical(f"Failed to remove old manifest: {old_manifest}")
                logger.exception(ex)
        current_state.old_manifests = []

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
    arg
        The arguments of the command, after "!gunsmith"
    '''
    weapon = arg

    logger.info(ctx.message.content)

    if not os.path.exists(current_state.current_manifest):
        logger.critical(f"Manifest queried does not exist at {current_state.current_manifest}")
        await ctx.send("An error occured. Please try again!")
        return

    armory = Armory(current_state.current_manifest)

    logger.info(f"Searching for '{weapon}'")
    weapons = armory.get_weapon_details(weapon)

    logger.info(f"# of weapons found: {len(weapons)}")
    result = weapons[0] # TODO: pagination

    logger.info("Constructing weapon result")
    DESCRIPTION = str(result.weapon_base_info) + "\n" + result.description
    embed = discord.Embed(title=result.name, description= DESCRIPTION, color=constants.DISCORD_BG_HEX)
    embed.set_thumbnail(url=result.icon)

    for perk in result.weapon_perks:
        if (perk.idx + 1) % 3 == 0:
            embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(name=perk.name, value=perk, inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)

    logger.info("Sending weapon result")
    await ctx.send(embed=embed)

@gunsmith.error
async def on_error(ctx, error):
    if hasattr(error, 'original'):
        logger.exception(error.original)
        if isinstance(error.original, ValueError):
            logger.error(ctx.message.content)
            await ctx.send('Weapon could not be found.')
            return
        if isinstance(error.original, TypeError):
            logger.error(ctx.message.content)
            logger.error('Failed to parse weapon')
            await ctx.send('Failed to parse weapon. Please try again.')
            return
        if isinstance(error.original, discord.errors.HTTPException):
            if error.original.status == 429:
                logger.critical("Bot is rate-limited")
            return
        if isinstance(error.original, OperationalError):
            logger.error(ctx.message.content)
            logger.error('Failed to find manifest')
            await ctx.send('An error occured. Please try again.')
            return
    if isinstance(error, commands.BadArgument):
        await ctx.send("Please enter the weapon name.")
        return

logger.info("Starting up bot")
bot.add_cog(UpdateManifest(bot))
bot.run(DISCORD_KEY)