import os
import json
import logging
import itertools
from dataclasses import dataclass
import aiosqlite
from . import constants

logger = logging.getLogger('Armory.Mods')

logging.getLogger("aiosqlite").setLevel("WARNING")

class ArmoryMods:
    '''
    Interfaces with Bungie's manifest to query for Mods

    Attributes 
    ----------
    current_manifest_path : str
        The path to Bungie's manifest of static definitions in Destiny 2
    '''

    def __init__(self, current_manifest_path):
        logger.debug(f"Setting manifest path: {current_manifest_path}")
        self.current_manifest_path = current_manifest_path
    
    def get_current_manifest_path(self):
        return self.current_manifest_path
    
    async def _search_mod(self, query):
        '''
        Search for a Destiny 2 mod in "DestinyInventoryItemDefinition" and extract JSON for all
        matches

        Parameters
        ----------
        query: str
            The name of the Destiny 2 mod to search

        Returns
        -------
        mod: Mod
            The mod found in the manifest
        '''
        async with aiosqlite.connect(self.current_manifest_path) as conn:
            cursor = await conn.cursor()
            await cursor.execute('''
            SELECT json FROM DestinyInventoryItemDefinition as item 
            WHERE json_extract(item.json, '$.displayProperties.name') LIKE ? and 
            json_extract(item.json, '$.itemCategoryHashes[0]') = 59 and 
            json_extract(item.json, '$.perks') is not NULL and 
            json_extract(item.json, '$.collectibleHash') is not NULL''', (query + "%",))

            result = await cursor.fetchone()
            if not result:
                raise ValueError("Mod not found")
            raw_mod_data = json.loads(result[0])
            if "itemCategoryHashes" in raw_mod_data:
                if constants.ModBase.MODS.value not in raw_mod_data["itemCategoryHashes"]:
                    raise ValueError("Mod not identified: {raw_mod_data['itemCategoryHashes']}")
                if constants.ModBase.ARMOR.value in raw_mod_data["itemCategoryHashes"]:
                    mod_category = constants.ModBase.ARMOR
                elif constants.ModBase.WEAPON.value in raw_mod_data["itemCategoryHashes"]: 
                    mod_category = constants.ModBase.WEAPON
                else:
                    raise ValueError(f"Could not identify mod category hashes: {raw_mod_data['itemCategoryHashes']}")
            
            perk_hashes = [i['perkHash'] for i in raw_mod_data['perks']]

            cursor = await conn.cursor()
            await cursor.execute(f'''
            SELECT json_extract(item.json, '$.displayProperties.description') FROM DestinySandboxPerkDefinition as item 
            WHERE json_extract(item.json, '$.hash') in ({",".join(["?"]*len(perk_hashes))})''', perk_hashes)

            mod_perk_descriptions = []
            async for description in cursor:
                if description_val := description[0]:
                    mod_perk_descriptions.append(description_val)

            collectible_hash = raw_mod_data['collectibleHash']
            cursor = await conn.cursor()
            await cursor.execute('''
            SELECT json_extract(item.json, '$.sourceString') FROM DestinyCollectibleDefinition as item 
            WHERE json_extract(item.json, '$.hash') = ?''', (collectible_hash,))

            mod_source = (await cursor.fetchone())[0]
            
            energy_cost = None
            energy_type = None
            armor_location = None
            if mod_category == constants.ModBase.ARMOR:
                energy_cost = raw_mod_data['plug']['energyCost']['energyCost']
                try:
                    energy_type = constants.EnergyTypeHash(raw_mod_data['plug']['energyCost']['energyTypeHash'])
                except:
                    raise ValueError(f"Energy Type Hash not known: {raw_mod_data['plug']['energyCost']['energyTypeHash']}")
                for hash in raw_mod_data['itemCategoryHashes']:
                    if (hash != constants.ModBase.MODS.value) and (hash != constants.ModBase.ARMOR.value):
                        try:
                            armor_location = constants.ModBase(hash)
                        except:
                            continue

            
            mod = Mod.from_raw_mod_data(raw_mod_data, mod_perk_descriptions, 
                                        mod_category, energy_cost,energy_type, armor_location, mod_source)
            
            return mod

    async def get_mod_details(self, query):
        '''
        Search and retrieve information about a Destiny 2 mod from Bungie's manifest

        Parameters
        ----------
        query: str
            The name of the Destiny 2 mod to search

        Returns
        -------
        mod: Mod
            The mod found in the manifest
        '''

        mod_result = await self._search_mod(query)

        return mod_result


@dataclass
class Mod:
    name: str
    description: str
    icon: str
    category: str
    energy_cost: int
    energy_type: str
    armor_location: str
    source: str

    @classmethod
    def from_raw_mod_data(cls, raw_mod_data, mod_perk_descriptions, mod_category: constants.ModBase, 
                          energy_cost, energy_type: constants.EnergyTypeHash, armor_location, mod_source):
        mod_details = raw_mod_data["displayProperties"]
        name = mod_details["name"]
        if mod_details['description']:
            description = mod_details['description'] + "\n- " + '\n- '.join(mod_perk_descriptions)
        else:
            if len(mod_perk_descriptions) > 1:
                description = '- ' + '\n- '.join(mod_perk_descriptions)
            else:
                description = mod_perk_descriptions[0]
        icon = constants.BUNGIE_URL_ROOT + mod_details["icon"]
        if mod_category == constants.ModBase.ARMOR:
            if armor_location:
                armor_location = armor_location.name.replace("_", " ").title()
            return cls(name, description, icon, mod_category.name.title(), 
                       energy_cost, energy_type.name.title(), armor_location, mod_source)
        else:
            return cls(name, description, icon, mod_category.name.title(), None, None, None, mod_source)

    def get_overview(self):
        overview = ''
        if self.energy_cost:
            if self.energy_type != "Any":
                overview = "**" + str(self.energy_cost) + " " + self.energy_type + " Energy"
            else:
                overview = "**" + str(self.energy_cost) + " Energy"
            if self.armor_location:
                overview += f" - {self.armor_location}**\n"
            else:
                overview += "**\n"# + self.source # FIXME: Source string is disabled until API improves
        # else:
        #     overview = self.source
        return overview

    def __str__(self):
        return self.name