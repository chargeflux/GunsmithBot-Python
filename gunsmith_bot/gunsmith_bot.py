import logging
from logging.handlers import TimedRotatingFileHandler
import os
import glob
import asyncio
import datetime
from dataclasses import dataclass, field
import discord
from discord.ext import commands, tasks
import pydest
from armory import pydest_loader, WeaponRollDB

if not os.path.exists("logs/"):
    os.mkdir("logs")

logfmt = logging.Formatter(fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s', 
                           datefmt='%Y-%m-%d %I:%M:%S %p')
handler = TimedRotatingFileHandler("logs/gunsmith.log", 
                                   when="D", 
                                   interval=1,
                                   backupCount=5)
handler.setFormatter(logfmt)

logger = logging.getLogger('Gunsmith')
logging.basicConfig(level=logging.INFO, handlers=[handler])

logging.getLogger("discord").setLevel("WARNING")

if not (DISCORD_KEY := os.environ.get("DISCORD_KEY")):
    logger.error("Failed to retrieve DISCORD_KEY")
    raise ValueError("Please set the environment variable for DISCORD_KEY")

@dataclass
class State():
    current_manifest: str = ''
    destiny_api: pydest = None

class CustomDefaultHelpCommand(commands.DefaultHelpCommand):
    def __init__(self):
        super().__init__(no_category="Misc")
        self.command_attrs['name'] = "help"
    
    def get_ending_note(self):
        command_name = self.command_attrs['name']
        return "Type {0}{1} command for more info on a command.\n" \
               "You can also type {0}{1} category for more info on a category.".format(self.clean_prefix, command_name)

bot = commands.Bot(command_prefix="?", 
                   help_command=CustomDefaultHelpCommand(), 
                   description='Retrieve rolls for Destiny 2 weapons')
bot.current_state: State = State()

class UpdateManifest(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.update_manifest.start()

    def cog_unload(self):
        self.update_manifest.stop()

    @tasks.loop(hours=24)
    async def update_manifest(self):
        if bot.current_state.current_manifest:
            logger.info("Checking if old manifests and weapon roll dbs need to be deleted")
            files = glob.glob("*.content")
            for file in files:
                if file != bot.current_state.current_manifest:
                    try:
                        os.remove("./" + file)
                        logger.info(f"{file} was deleted")
                    except OSError as ex:
                        logger.critical(f"Failed to remove old file: {file}")
                        logger.exception(ex)
                    try:
                        os.remove("./" + file + ".weapons")
                        logger.info(f"{file + '.weapons'} was deleted")
                    except OSError as ex:
                        logger.critical(f"Failed to remove old weapons db: {file + '.weapons'}")
                        logger.exception(ex)

        if bot.current_state.destiny_api:
            await pydest_loader.update_manifest(bot.current_state.destiny_api)
            manifest_location = await pydest_loader.get_manifest(bot.current_state.destiny_api)
            if manifest_location != bot.current_state.current_manifest:
                logger.info(f"The manifest was updated: {manifest_location}")
                bot.current_state.current_manifest = manifest_location
            weapon_roll_db = WeaponRollDB(bot.current_state.current_manifest)
            if not weapon_roll_db.check_DB_exists():
                logger.info("Reinitalizing weapon roll database")
                weapon_roll_db.initializeDB()

    @update_manifest.before_loop
    async def before_update_manifest(self):
        await self.bot.wait_until_ready()

@bot.event
async def on_ready():
    """
    Triggered when the bot successfully logs into Discord and is ready. Note that this is not limited to
    the start up of the bot.
    """
    logger.info(f'We have logged in as {bot.user}')
    if not bot.current_state.current_manifest:
        try:
            bot.current_state.destiny_api = await pydest_loader.initialize_destiny()
            bot.current_state.current_manifest = await pydest_loader.get_manifest(bot.current_state.destiny_api)
            logger.info("Loaded current manifest")
            weapon_roll_db = WeaponRollDB(bot.current_state.current_manifest)
            if not weapon_roll_db.check_DB_exists():
                logger.info("Reinitalizing weapon roll database")
                weapon_roll_db.initializeDB()
        except pydest.PydestException:
            logger.critical("Failed to initialize PyDest. Quitting.")
            await bot.logout()
        except AttributeError:
            logger.critical("Failed to retrieve manifest. Quitting.")
            await bot.current_state.destiny_api.close()
            await bot.logout()

    logger.info("Checking if old manifests and weapon roll dbs need to be deleted")
    files = glob.glob("*.content")
    for file in files:
        if file != bot.current_state.current_manifest:
            try:
                os.remove("./" + file)
                logger.info(f"{file} was deleted")
            except OSError as ex:
                logger.critical(f"Failed to remove old file: {file}")
                logger.exception(ex)
            try:
                os.remove("./" + file + ".weapons")
                logger.info(f"{file + '.weapons'} was deleted")
            except OSError as ex:
                logger.critical(f"Failed to remove old weapons db: {file + '.weapons'}")
                logger.exception(ex)

logger.info("Starting up bot")
bot.add_cog(UpdateManifest(bot))
bot.load_extension("cogs.weapons")
bot.run(DISCORD_KEY)
logger.info("Shutting down bot")