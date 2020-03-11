import discord
import os

if not (DISCORD_KEY := os.environ.get("DISCORD_KEY")):
    raise ValueError("Please set the environment variable for DISCORD_KEY")

client = discord.Client()

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('$!gunsmith'):
        await message.channel.send('Hello!')

client.run(DISCORD_KEY)