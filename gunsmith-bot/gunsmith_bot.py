import logging
from discord.ext import commands
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s', 
                    datefmt='%Y-%m-%d %I:%M:%S %p')

logger = logging.getLogger('Gunsmith')
logger.setLevel(logging.INFO)

logging.getLogger("discord").setLevel("WARNING")

if not (DISCORD_KEY := os.environ.get("DISCORD_KEY")):
    logger.error("Failed to retrieve DISCORD_KEY")
    raise ValueError("Please set the environment variable for DISCORD_KEY")

logger.info("Starting up bot")

bot = commands.Bot(command_prefix="!", description='Retrieve rolls for Destiny 2 weapons')

@bot.event
async def on_ready():
    logger.log(logging.INFO, f'We have logged in as {bot.user}')

@bot.command()
async def gunsmith(ctx, *args):
    if not args:
        return
    
    weapon = ' '.join(args)
    await ctx.send(weapon)

bot.run(DISCORD_KEY)