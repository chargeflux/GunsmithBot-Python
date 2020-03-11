import logging
import discord
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s', 
                    datefmt='%Y-%m-%d %I:%M:%S %p')

logger = logging.getLogger('Gunsmith')
logger.setLevel(logging.INFO)

logging.getLogger("discord").setLevel("WARNING")

if not (DISCORD_KEY := os.environ.get("DISCORD_KEY")):
    logger.error("Failed to retrieve DISCORD_KEY")
    raise ValueError("Please set the environment variable for DISCORD_KEY")

logger.info("Starting up bot client")

client = discord.Client()

@client.event
async def on_ready():
    logger.log(logging.INFO, f'We have logged in as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('!gunsmith'):
        logger.log(logging.DEBUG, message.content)
        await message.channel.send('Hello!')

client.run(DISCORD_KEY)
