import logging
import discord
from discord.ext import commands
import os
import constants

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

    embed = discord.Embed(title=weapon, color=constants.DISCORD_BG_HEX)
    embed.add_field(name="Barrel", value="", inline=True)
    embed.add_field(name="Magazine", value="", inline=True)
    embed.add_field(name="Perk 1", value="", inline=True)
    embed.add_field(name="Perk 2", value="", inline=True)
    await ctx.send(embed=embed)

bot.run(DISCORD_KEY)