import logging
from logging.handlers import TimedRotatingFileHandler
import os
import asyncio
import datetime
from dataclasses import dataclass, field
import discord
from discord.ext import commands, tasks
import pydest
from armory import pydest_loader

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
    old_manifests: [str] = field(default_factory=list)

class CustomDefaultHelpCommand(commands.DefaultHelpCommand):
    def __init__(self):
        super().__init__(no_category="Misc")
        self.command_attrs['name'] = "gunsmith -help"
    
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
        for old_manifest in bot.current_state.old_manifests:
            try:
                os.remove("./" + old_manifest)
                logger.info(f"{old_manifest} was deleted")
            except OSError as ex:
                logger.critical(f"Failed to remove old manifest: {old_manifest}")
                logger.exception(ex)
        bot.current_state.old_manifests = [] # note: clears even if deletion is unsucessful

        if bot.current_state.destiny_api:
            await pydest_loader.update_manifest(bot.current_state.destiny_api)
            manifest_location = await pydest_loader.get_manifest(bot.current_state.destiny_api)
            if manifest_location != bot.current_state.current_manifest:
                logger.info(f"The manifest was updated. Adding {old_manifest} for deletion")
                bot.current_state.old_manifests.append(bot.current_state.current_manifest)
                bot.current_state.current_manifest = manifest_location

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
        except pydest.PydestException:
            logger.critical("Failed to initialize PyDest. Quitting.")
            await bot.logout()
        except AttributeError:
            logger.critical("Failed to retrieve manifest. Quitting.")
            await bot.current_state.destiny_api.close()
            await bot.logout()

logger.info("Starting up bot")
bot.add_cog(UpdateManifest(bot))
bot.load_extension("cogs.weapons")
bot.run(DISCORD_KEY)
logger.info("Shutting down bot")