import pydest
import os
import asyncio
import loader


if not (BUNGIE_KEY := os.environ.get("BUNGIE_KEY")):
    logger.error("Failed to retrieve BUNGIE_KEY")
    raise ValueError("Please set the environment variable for BUNGIE_KEY")


async def search_destiny_player():
    destiny = pydest.Pydest(BUNGIE_KEY)

    await destiny.api.search_destiny_player()

    await destiny.close()

asyncio.run(search_destiny_player())