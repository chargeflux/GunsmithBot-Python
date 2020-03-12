import logging
import discord
from discord.ext import commands
import os
import asyncio
import constants
from armory import Armory

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s', 
                    datefmt='%Y-%m-%d %I:%M:%S %p')

logger = logging.getLogger('Gunsmith')
logger.setLevel(logging.INFO)

logging.getLogger("discord").setLevel("WARNING")

if not (DISCORD_KEY := os.environ.get("DISCORD_KEY")):
    logger.error("Failed to retrieve DISCORD_KEY")
    raise ValueError("Please set the environment variable for DISCORD_KEY")

logger.info("Starting up bot")
current_manifest = None

bot = commands.Bot(command_prefix="!", description='Retrieve rolls for Destiny 2 weapons')

@bot.event
async def on_ready():
    logger.log(logging.INFO, f'We have logged in as {bot.user}')

@bot.command()
async def gunsmith(ctx, *args):
    if not args:
        return
    
    weapon = ' '.join(args)

    armory = Armory(current_manifest)
    weapons = armory.get_weapon_details(weapon)
    result = weapons[0] #TODO: pagination

    embed = discord.Embed(title=weapon, color=constants.DISCORD_BG_HEX)

    BARRELS = '\n'.join([perk.name for perk in result.barrels])
    MAGAZINES = '\n'.join([perk.name for perk in result.magazines])
    PERK_1 = '\n'.join([perk.name for perk in result.perks_1])
    PERK_2 = '\n'.join([perk.name for perk in (result.perks_2 or [])])

    embed.add_field(name="Barrel", value=BARRELS, inline=False)
    embed.add_field(name="Magazine", value=MAGAZINES, inline=False)
    embed.add_field(name="Perk 1", value=PERK_1, inline=False)
    if PERK_2:
        embed.add_field(name="Perk 2", value=PERK_2, inline=False)
    await ctx.send(embed=embed)

bot.run(DISCORD_KEY)