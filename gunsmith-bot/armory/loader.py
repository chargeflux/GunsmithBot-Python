import logging
import pydest
import os
import asyncio

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s', 
                    datefmt='%Y-%m-%d %I:%M:%S %p')

logger = logging.getLogger('Loader')
logger.setLevel(logging.INFO)

if not (BUNGIE_KEY := os.environ.get("BUNGIE_KEY")):
    logger.error("Failed to retrieve BUNGIE_KEY")
    raise ValueError("Please set the environment variable for BUNGIE_KEY")



async def get_manifest(destiny):
    return destiny._manifest.manifest_files['en']

async def update_manifest(destiny):
    try:
        await destiny.update_manifest()
    except pydest.PydestException:
        logger.error("Failed to update manifest")

    return destiny

async def initialize_destiny():
    destiny = pydest.Pydest(BUNGIE_KEY)

    await destiny.update_manifest()

    return destiny