import os
import glob
import json
import logging
from operator import attrgetter
import difflib
from dataclasses import dataclass
from typing import List
import aiosqlite
from . import constants

logger = logging.getLogger('Armory')

logging.getLogger("aiosqlite").setLevel("WARNING")

class Armory:
    '''
    Interfaces with Bungie's manifest to query for weapons

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

    async def _search_perk(self, query):
        '''
        Search for a Destiny 2 perk in "DestinyInventoryItemDefinition" and extract JSON for all
        matches

        Parameters
        ----------
        query: str
            The name of the Destiny 2 perk to search

        Returns
        -------
        weapon_perk: WeaponPerkPlugInfo
            The perk found in the manifest
        '''
        async with aiosqlite.connect(self.current_manifest_path) as conn:
            cursor = await conn.cursor()
            await cursor.execute('''
            SELECT json FROM DestinyInventoryItemDefinition as item 
            WHERE json_extract(item.json, '$.displayProperties.name') LIKE ?''', ("%" + query + "%",))

            weapon_perks = []

            async for row in cursor:
                raw_perk_data = json.loads(row[0])
                if "plug" in raw_perk_data:
                    try:
                        plug_category = constants.PlugCategoryHash(raw_perk_data["plug"]["plugCategoryHash"])
                        weapon_perk = WeaponPerkPlugInfo.from_raw_perk_data(raw_perk_data, plug_category)
                        weapon_perks.append([weapon_perk,"score"])
                    except ValueError:
                        continue
            
            for perk in weapon_perks:
                perk[1] = difflib.SequenceMatcher(None, perk[0].name, query).ratio()
            
            weapon_perks.sort(key = lambda x: x[1], reverse= True)

            if not weapon_perks:
                raise ValueError
            else:
                return weapon_perks[0][0]
    
    async def get_perk_details(self, query):
        '''
        Search and retrieve information about a Destiny 2 perk from Bungie's manifest

        Parameters
        ----------
        query: str
            The name of the Destiny 2 perk to search

        Returns
        -------
        perk : WeaponPerk
            The perk found in the manifest
        '''

        perk_result = await self._search_perk(query)

        return perk_result

    async def _search_weapon(self, query):
        '''
        Search for a Destiny 2 weapon in "DestinyInventoryItemDefinition" and extract JSON for all matches

        Parameters
        ----------
        query: str
            The name of the Destiny 2 weapon to search

        Returns
        -------
        weapons: [WeaponResult]
            The weapons found in the manifest where each is a `WeaponResult`
        '''
        async with aiosqlite.connect(self.current_manifest_path) as conn:
            cursor = await conn.cursor()
            await cursor.execute('''
            SELECT item.id, json FROM DestinyInventoryItemDefinition as item 
            WHERE json_extract(item.json, '$.displayProperties.name') LIKE ?''', ("%" + query + "%",))

            weapons = []
            async for row in cursor:
                raw_weapon_data = json.loads(row[1])
                if self._validate_weapon_search(raw_weapon_data):
                    weapons.append(WeaponResult(row[0], query, raw_weapon_data, self.current_manifest_path))

            if not weapons:
                raise ValueError
            else:
                return weapons
    
    def _validate_weapon_search(self, raw_weapon_data):
        '''
        Validate the JSON of weapon found from querying the manifest

        Parameters
        ----------
        raw_weapon_data: dict
            Derived from json data for the weapon

        Returns
        -------
        bool
            If the item found is a weapon
        '''
        if constants.WeaponBase.WEAPON.value not in raw_weapon_data.get("itemCategoryHashes", []):
            return False
        if constants.WeaponBase.DUMMY.value in raw_weapon_data["itemCategoryHashes"]:
            return False
        if 'sockets' not in raw_weapon_data.keys():
            return False
        return True


    async def get_weapon_details(self, query, default=False):
        '''
        Search and retrieve information about a Destiny 2 weapon from Bungie's manifest

        Parameters
        ----------
        query: str
            The name of the Destiny 2 weapon to search

        Returns
        -------
        weapons : [Weapon]
            A list where each individual weapon is a `Weapon`
        '''

        weapon_results = await self._search_weapon(query)

        weapons = []
        for weapon_result in weapon_results:
            weapon = await Weapon.from_weapon_result(weapon_result, default)
            if weapon.has_random_rolls or weapon.weapon_base_info.weapon_tier_type == constants.WeaponTierType.EXOTIC:
                weapons.insert(0, weapon)
            else:
                weapons.append(weapon)

        weapons.sort(key = attrgetter('similarity_score'), reverse= True)
        return weapons

    async def compare_weapons(self, query):
        '''
        Compare the stats between 2 Destiny 2 weapons

        Parameters
        ----------
        query: str
            The names of the 2 Destiny 2 weapons to compare

        Returns
        -------
        compare_result : ComparisonResult
        '''

        weapons = query.split(",")
        if len(weapons) != 2:
            raise ValueError

        to_compare = []
        for weapon in weapons:
            clean_weapon_query = weapon.strip()
            logger.info(f"Looking up {clean_weapon_query} for comparison")
            results = await self.get_weapon_details(clean_weapon_query)
            to_compare.append(results[0])

        compare_result = ComparisonResult(to_compare)
        return compare_result

class WeaponResult:
    '''
    Represents the JSON data for a weapon

    Attributes
    ----------
    db_id: int
        The database id of the weapon in Bungie's manifest in "DestinyInventoryItemDefinition"

    query: str
        The name of the Destiny 2 weapon to search
    
    display_properties_data: dict
        Holds information about the name and image of the weapon
    
    flavor_text: str
        Holds flavor text for weapon

    socket_data: dict
        Holds information about the intrinsic nature and possible perks for the weapon
    
    item_categories_hash_data: dict
        Holds information about the categories which this weapon is classifed as

    display_source_data: str
        Determines if it has random rolls or not
    
    tierTypeHash: int
        Determines the tier type of the weapon

    damage_type_id: int
        Determines the energy damage type

    power_cap_hashes: int
        Determines the power cap for each version of the weapon

    stats : dict
        Holds information about the stats for this weapon

    current_manifest_path : str
        The path to Bungie's manifest of static definitions in Destiny 2
    '''

    def __init__(self, db_id, query, raw_weapon_data, current_manifest_path):
        self.db_id = db_id
        self.query = query
        self.hash = raw_weapon_data["hash"]
        self.display_properties_data = raw_weapon_data["displayProperties"]
        self.flavor_text = raw_weapon_data["flavorText"]
        self.socket_data = raw_weapon_data["sockets"]
        self.item_categories_hash_data = sorted(raw_weapon_data["itemCategoryHashes"])
        self.display_source_data = raw_weapon_data["displaySource"]
        self.tier_type_hash = raw_weapon_data["inventory"]["tierTypeHash"]
        self.damage_type_id = raw_weapon_data["defaultDamageType"]
        self.screenshot = raw_weapon_data["screenshot"]
        
        power_cap_hashes = []
        for version in raw_weapon_data["quality"]["versions"]:
            power_cap_hashes.append(version['powerCapHash'])            
        self.power_cap_hashes = power_cap_hashes
        
        self.stats = raw_weapon_data["stats"]["stats"]
        self.current_manifest_path = current_manifest_path

class Weapon:
    '''
    Contains all the necessary information for a Destiny 2 weapon

    Constructed via the `Weapon.from_weapon_result` class method

    Attributes 
    ----------
    db_id : int
        The database id of the weapon in Bungie's manifest in "DestinyInventoryItemDefinition"
    
    current_manifest_path : str
        The path to Bungie's manifest of static definitions in Destiny 2
    
    weapon_base_info: WeaponBaseArchetype
    
    name : str
        The name of the weapon
    
    flavor_text: str
        The flavor text of the weapon

    icon: str
        The relative url to the icon of the weapon at bungie.net
    
    has_random_rolls: bool
        If the weapon has random rolls or not
    
    similarity_score: float
        The similarity score between the name of the weapon and query
    
    intrinsic: WeaponPerkPlugInfo
        Represents the intrinsic nature of the weapon, e.g., adaptive frame
    
    weapon_perks: [WeaponPerkPlugInfo]
        Holds all the possible plugs for each perk if random rolled. Otherwise it will show
        the static roll

    stats: WeaponStats
    '''

    def __init__(self, weapon_result, default=False):
        '''
        This class should be constructed through the class method `Weapon.from_weapon_result` not __init__.
        '''
        self.db_id = weapon_result.db_id
        self.weapon_hash = weapon_result.hash
        self.current_manifest_path = weapon_result.current_manifest_path

        self.weapon_base_info = self._set_base_info(weapon_result.item_categories_hash_data, 
                                                    weapon_result.tier_type_hash,
                                                    weapon_result.damage_type_id)

        self.name = weapon_result.display_properties_data["name"]
        self.flavor_text = weapon_result.flavor_text
        self.icon = constants.BUNGIE_URL_ROOT + weapon_result.display_properties_data["icon"]
        self.screenshot = constants.BUNGIE_URL_ROOT + weapon_result.screenshot
        
        if weapon_result.display_source_data:
            self.has_random_rolls = True
        else:
            self.has_random_rolls = False

        if not default:
            self.weapon_stats = self._set_stats_info(weapon_result.stats)

        self.similarity_score = difflib.SequenceMatcher(None, self.name, weapon_result.query).ratio()

        self._intrinsic = None
        self._weapon_perks = None


    @property
    def intrinsic(self):
        if not self._intrinsic:
            raise AttributeError("Intrinsic data is missing. Please call `Weapon.from_weapon_result` first!")
        return self._intrinsic
    
    @intrinsic.setter
    def intrinsic(self, value):
        self._intrinsic = value

    @property
    def weapon_perks(self):
        if not self._weapon_perks:
            raise AttributeError("Weapon perk data is missing. Please call `Weapon.from_weapon_result` first!")
        return self._weapon_perks
    
    @weapon_perks.setter
    def weapon_perks(self, value):
        self._weapon_perks = value

    @classmethod
    async def from_weapon_result(cls, weapon_result, default):
        new_weapon = cls(weapon_result, default)
        new_weapon.intrinsic, new_weapon.weapon_perks = await new_weapon._process_socket_data(weapon_result.socket_data, default)
        new_weapon.weapon_base_info.power_cap = await new_weapon._process_power_cap(weapon_result.power_cap_hashes)
        return new_weapon

    def _convert_hash(self, val):
        '''
        Converts the item hash to the id used by the database

        References:
        - Function originates from @vpzed: https://github.com/vpzed/Destiny2-API-Info/wiki/API-Introduction-Part-3-Manifest#manifest-lookups
        - https://github.com/Bungie-net/api/wiki/Obtaining-Destiny-Definitions-%22The-Manifest%22#step-4-open-and-use-the-data-contained-within
        '''
        if (val & (1 << (32 - 1))) != 0:
            val = val - (1 << 32)
        return val

    async def _process_socket_intrinsic(self, socket, cursor):
        '''
        Processes socket entry corresponding to information about the intrinsic nature of the weapon.
        This socket usually only has a "reusablePlugSetHash" field since intrinsic nature of 
        a weapon is not randomized. Use "DestinyPlugSetDefinition" and "DestinyInventoryItemDefinition" 
        with the hash to obtain the plug for this socket corresponding to intrinsic nature.

        Parameters
        ----------
        socket : dict
            The socket entry corresponding to the intrinsic nature of the weapon
        cursor : Cursor
            Necessary to query SQLite DB asynchronously via aiosqlite 

        Returns
        -------
        WeaponPerkPlugInfo or None
        '''

        if 'reusablePlugSetHash' not in socket:
            logger.error("reusablePlugSetHash not found in socket entry for intrinisic nature")
            return None

        reusablePlugSetHash = socket['reusablePlugSetHash']
        converted_reusablePlugSetHash = self._convert_hash(reusablePlugSetHash)

        await cursor.execute(
        '''
        SELECT json_extract(j.value, '$.plugItemHash') 
        FROM DestinyPlugSetDefinition as item, 
        json_each(item.json, '$.reusablePlugItems') as j
        WHERE item.id = ?''', (converted_reusablePlugSetHash,))

        plug_hash = (await cursor.fetchone())[0]
        
        converted_plug_hash = self._convert_hash(plug_hash)

        await cursor.execute(
            '''
            SELECT json_extract(item.json, "$.displayProperties") 
            FROM DestinyInventoryItemDefinition as item 
            WHERE item.id = ?''', (converted_plug_hash,))
        
        plug_info = json.loads((await cursor.fetchone())[0])

        return WeaponPerkPlugInfo(name = plug_info['name'], 
                                  description = plug_info['description'],
                                  icon = plug_info['icon'],
                                  category = constants.PlugCategoryHash.INTRINSICS)

    async def _process_socket_data_perks(self, socket_entries, socket_indexes, cursor, default):
        '''
        Processes socket entries corresponding to information about the perks of the weapon.
        Each socket usually has a "reusablePlugSetHash" field if it is a static-rolled weapon or
        "randomizedPlugSetHash" field if it is a random-rolled weapon. Use "socketTypeHash" 
        with "DestinySocketTypeDefinition" to verify if the category of whitelisted plugs for this
        socket is of interest. Then, use "DestinyPlugSetDefinition" and "DestinyInventoryItemDefinition" 
        with the hash to obtain the plug or plugs if random rolled for this socket.

        Parameters
        ----------
        socket_entries : dict
            The socket entries to be traversed to determine all plugs for weapon perks
        
        socket_indexes : dict
            The indexes corresponding to weapon perks
        
        cursor : Cursor
            Necessary to query SQLite DB asynchronously via aiosqlite
        
        default : bool
            Determine to retrieve only default rolls

        Returns
        -------
        weapon_perks : [WeaponPerk]
            Returns a list of weapon perks where each is a `WeaponPerk`
        '''
        weapon_perks = []
        default_plugs = []
        for order_idx, index in enumerate(socket_indexes):
            socket = socket_entries[index]
            socket_type_hash = socket['socketTypeHash']
            converted_socket_type_hash = self._convert_hash(socket_type_hash)
                
            # Assume plugWhitelist always has a len of 1
            await cursor.execute(
            '''
            SELECT json_extract(item.json, "$.plugWhitelist[0]") 
            FROM DestinySocketTypeDefinition as item 
            WHERE item.id = ?''', (converted_socket_type_hash,))
        
            plug_category_info = json.loads((await cursor.fetchone())[0])

            try:
                plug_category = constants.PlugCategoryHash(plug_category_info["categoryHash"])
            except ValueError:
                continue
            
            if default:
                default_plug_perk_hashes = []
                converted_default_plug_perk_hashes = []
                for item in socket["reusablePlugItems"]:
                    default_plug_perk_hashes.append(item["plugItemHash"])
                    converted_default_plug_perk_hashes.append(self._convert_hash(item["plugItemHash"]))
                if not default_plug_perk_hashes:
                    default_plug_perk_hashes.append(socket["singleInitialItemHash"])
                    converted_default_plug_perk_hashes.append(self._convert_hash(socket["singleInitialItemHash"]))
                
                await cursor.execute(
                    f'''
                    SELECT json_extract(item.json, "$.displayProperties") 
                    FROM DestinyInventoryItemDefinition as item
                    WHERE item.id in ({",".join(["?"]*len(converted_default_plug_perk_hashes))})''', 
                    converted_default_plug_perk_hashes)
                
                async for plug in cursor:
                    plug_info = json.loads(plug[0])
                    default_plugs.append(WeaponPerkPlugInfo(name = plug_info['name'],
                                        description = plug_info['description'],
                                        icon = plug_info['icon'],
                                        category = constants.PlugCategoryHash.DEFAULT))
                continue

            if 'randomizedPlugSetHash' in socket:
                plug_set_hash = socket['randomizedPlugSetHash']
            elif 'reusablePlugSetHash' in socket:
                plug_set_hash = socket['reusablePlugSetHash']
            else:
                logger.error("randomizedPlugSetHash or reusablePlugSetHash not found in socket entry for weapon perks")
                continue
                
            converted_plug_set_hash = self._convert_hash(plug_set_hash)

            await cursor.execute(
            '''
            SELECT json_extract(j.value, '$.plugItemHash'), json_extract(j.value, '$.currentlyCanRoll') 
            FROM DestinyPlugSetDefinition as item, 
            json_each(item.json, '$.reusablePlugItems') as j
            WHERE item.id = ?''', (converted_plug_set_hash,))

            converted_plug_id_results = []

            async for row in cursor:
                if row[1]:
                    converted_plug_id_results.append(self._convert_hash(row[0]))

            # SQL does not support binding to a list. Therefore we can dynamically insert question marks
            # based on the length of the converted_plug_id_results. Additionally, since we are only inserting 
            # question marks, we are not exposing ourselves to a security risk
            await cursor.execute(
                f'''
                SELECT json_extract(item.json, "$.displayProperties") 
                FROM DestinyInventoryItemDefinition as item
                WHERE item.id in ({",".join(["?"]*len(converted_plug_id_results))})''', 
                converted_plug_id_results)
            
            plugs = []
            async for plug in cursor:
                plug_info = json.loads(plug[0])
                plugs.append(WeaponPerkPlugInfo(name = plug_info['name'], 
                                                description = plug_info['description'],
                                                icon = plug_info['icon'],
                                                category = plug_category))
            
            weapon_perks.append(WeaponPerk(idx = order_idx, name = plug_category.name.title(), plugs = plugs))
        if default:
            weapon_perks.append(WeaponPerk(idx = len(weapon_perks), name = constants.PlugCategoryHash.DEFAULT.name.title(), plugs = default_plugs))
        return weapon_perks


    async def _process_socket_data(self, socket_data, default):
        '''
        Processes socket data for information about the intrinsic nature and perks
        for the weapon.

        Parameters
        ----------
        socket_data : dict
            The socket data of the weapon to be processed
        
        default : bool
            Determine to retrieve only default rolls

        Returns
        -------
        intrinsic : WeaponPerkPlugInfo
        
        weapon_perks : [WeaponPerk]
            Returns a list of weapon perks where each is a `WeaponPerk`
        '''
        intrinsic = None
        weapon_perks = []
        async with aiosqlite.connect(self.current_manifest_path) as conn:
            cursor = await conn.cursor()
            for category_data in socket_data["socketCategories"]:
                if category_data["socketCategoryHash"] == constants.SocketCategoryHash.INTRINSICS.value:
                        index = category_data['socketIndexes'][0] # assume only one intrinsic
                        socket = socket_data["socketEntries"][index]
                        intrinsic = await self._process_socket_intrinsic(socket, cursor)
                if category_data["socketCategoryHash"] == constants.SocketCategoryHash.WEAPON_PERKS.value:
                    weapon_perks = await self._process_socket_data_perks(socket_data["socketEntries"], 
                                                                    category_data['socketIndexes'], 
                                                                    cursor,
                                                                    default)
        return intrinsic, weapon_perks
    
    def _set_stats_info(self, stats):
        weapon_stats = []
        for idx, stat in enumerate(stats.values()):
            try:
                stat_hash = stat["statHash"]
                stat_type = constants.WeaponStats(stat_hash) 
                stat_value = stat["value"]
                if stat_value == 0:
                    logger.debug(f'{stat_type.name} had a value of 0')
                    continue
                weapon_stat_info = WeaponStatInfo(stat_type, stat_value)
            except ValueError:
                logger.debug(f"Failed to match weapon stat hash: {stat_hash}")
                continue
            weapon_stats.append(WeaponStat(idx,weapon_stat_info))
        weapon_stats.sort(key=lambda x: constants.StatOrder[x.stat.stat_type])
        return weapon_stats


    def _set_base_info(self, item_categories_hash_data, tier_type_hash, damage_type_id):
        '''
        Sets the base archetype information for the weapon 

        Parameters
        ----------
        item_categories_hash_data : [int]
            The hashes that correspond to the item categories that the weapon is classified as
        
        Returns
        -------
        WeaponBaseArchetype
        '''
        weapon_base_info = WeaponBaseArchetype()
        for item_category_hash in item_categories_hash_data[1:]:
            try:
                category = constants.WeaponBase(item_category_hash)
                weapon_base_info.set_field(category)
            except ValueError:
                logger.debug(f"Failed to match weapon category hash: {item_category_hash}")
        try: 
            weapon_tier = constants.WeaponTierType(tier_type_hash)
            weapon_base_info.weapon_tier_type = weapon_tier
        except ValueError:
            logger.debug(f"Failed to match tier type hash: {tier_type_hash}")
        try:
            weapon_damage_type = constants.DamageType(damage_type_id)
            weapon_base_info.weapon_damage_type = weapon_damage_type
            weapon_base_info.is_energy = damage_type_id > 1
        except ValueError:
            logger.debug(f"Failed to match damage type id: {damage_type_id}")
        return weapon_base_info
    
    async def _process_power_cap(self, power_cap_hashes):
        '''
        Retrieves the power caps for all versions of the weapon and returns the max power cap

        Parameters
        ----------
        power_cap_hashes : [int]
            The hashes that correspond to the power caps of all versions of the weapon
        
        Returns
        -------
        int
        '''
        power_caps = []
        async with aiosqlite.connect(self.current_manifest_path) as conn:
            cursor = await conn.cursor()

            await cursor.execute(f'''
            SELECT MAX(json_extract(json, '$.powerCap')) 
            FROM DestinyPowerCapDefinition AS item 
            WHERE json_extract(item.json, '$.hash') IN ({",".join(["?"]*len(power_cap_hashes))})''', power_cap_hashes)
            
            power_cap = (await cursor.fetchone())[0]
        return power_cap

class ComparisonResult:
    '''
    Contains information about stat differences between 2 Destiny 2 Weapons

    Attributes 
    ----------
    weapons_names : [str]
        A list of names for each of the 2 weapons being compared

    weapon_stat_diff : WeaponStatDiff
        Contains the deltas for all stats between the 2 weapons
    
    common_stat_names : [str]
        Contains the common stat names between the 2 weapons
    
    weapons_stats : [WeaponStatInfo]
        A list of weapon stats for each of the 2 weapons being compared
    '''

    def __init__(self, weapons):
        if len(weapons) != 2:
            raise 
        self.weapons_names = [weapon.name for weapon in weapons]
        self.weapon_stat_diff = None
        self.common_stat_names = None
        self._calculate_stat_diff(weapons)
        self.weapons_stats = [weapon.weapon_stats for weapon in weapons]

    def _calculate_stat_diff(self, weapons):
        '''
        Gets stat differences between weapons

        Parameters
        ----------
        weapon_results : [Weapon]
            A list of 2 Weapons
        '''
        weapon_stat_diff = []
        weapon_stat_base = []
        common_stats = set(weapons[0].weapon_stats) & set(weapons[1].weapon_stats)
        common_stats = [stat.stat.stat_type for stat in common_stats]
        common_stats.sort(key=lambda x: constants.StatOrder[x])
        w1_stats = filter(lambda x: x.stat.stat_type in common_stats, weapons[0].weapon_stats)
        w2_stats = filter(lambda x: x.stat.stat_type in common_stats, weapons[1].weapon_stats)
        w1_stats = sorted(w1_stats, key=lambda x: constants.StatOrder[x.stat.stat_type])
        w2_stats = sorted(w2_stats, key=lambda x: constants.StatOrder[x.stat.stat_type])
        for w1, w2 in zip(w1_stats, w2_stats):
            weapon_stat_base.append(w1.stat.value)
            weapon_stat_diff.append(w1.stat.value - w2.stat.value)
        
        self.weapon_stat_diff = WeaponStatDiff(weapon_stat_base, weapon_stat_diff)
        common_stat_names = [stat.name.replace("_"," ").title() if stat != constants.WeaponStats.RPM else "RPM" for stat in common_stats]
        self.common_stat_names = '\n'.join(common_stat_names)
    
    def get_stats_for_weapon(self, idx):
        '''
        Gets stats and difference for weapon

        Parameters
        ----------
        idx : [int]
            The index corresponding to the first or second weapon
        '''
        stats = []
        if idx == 0:
            for stat_base, stat_delta in self.weapon_stat_diff:
                if stat_delta < 0:
                    stats.append(str(stat_base))
                elif stat_delta > 0:
                    stats.append('**' + str(stat_base) + f" (+{stat_delta})**")
                else:
                    stats.append(str(stat_base))
            stats_str = '\n'.join(stats)
            return stats_str
        if idx == 1:
            for stat_base, stat_delta in self.weapon_stat_diff:
                if stat_delta < 0:
                    stats.append('**' + str(stat_base+stat_delta*-1) + f" (+{stat_delta*-1})**")
                elif stat_delta > 0:
                    stats.append(str(stat_base-stat_delta))
                else:
                    stats.append(str(stat_base))
            stats_str = '\n'.join(stats)
            return stats_str
        else:
            raise ValueError

@dataclass 
class WeaponStatDiff:
    base_values: list
    stat_diff: list

    def __iter__(self):
        for i in range(len(self.base_values)):
            yield self.base_values[i], self.stat_diff[i]

@dataclass
class WeaponPerkPlugInfo:
    name: str
    description: str
    icon: str
    category: str

    @classmethod
    def from_raw_perk_data(cls, raw_perk_data, plug_category: constants.PlugCategoryHash):
        perk_details = raw_perk_data["displayProperties"]
        name = perk_details["name"]
        description = perk_details["description"]
        icon = constants.BUNGIE_URL_ROOT + perk_details["icon"]
        return cls(name, description, icon, plug_category.name.title())

    def __str__(self):
        return self.name

@dataclass
class WeaponPerk:
    idx: int
    name: str
    plugs: List[WeaponPerkPlugInfo]

    def __str__(self):
        return '\n'.join(map(str,self.plugs))

@dataclass
class WeaponBaseArchetype:
    '''
    weapon_class: constants.WeaponBase
        Determines if the weapon is a kinetic, energy or power weapon
    
    weapon_type: constants.WeaponBase
        Determines if the weapon is a hand cannon, pulse rifle, sword, etc.

    weapon_tier_type: constants.WeaponTierType
        Determines the weapon's tier, e.g., legendary

    weapon_damage_type: constants.DamageType
        Determines the weapon's damage type

    is_energy: bool
        Determines if the weapon deals energy or kinetic damage
    '''
    weapon_class: constants.WeaponBase = None
    weapon_type: constants.WeaponBase = None
    weapon_tier_type: constants.WeaponTierType = None
    weapon_damage_type: constants.DamageType = None
    is_energy: bool = None
    power_cap: int = None

    def set_field(self, input: constants.WeaponBase):
        if input.value < 5:
            self.weapon_class = input
        else:
            self.weapon_type = input

    @property
    def power_cap(self):
        if not self._power_cap:
            raise AttributeError("No power cap!")
        return self._power_cap
    
    @power_cap.setter
    def power_cap(self, value):
        if str(value).startswith("9"):
            self._power_cap = None
        else:
            self._power_cap = value

    def __str__(self):
        str_to_construct = ''
        if self.is_energy:
            str_to_construct += self.weapon_damage_type.name.title() + " "
        if self.weapon_class:
            str_to_construct += self.weapon_class.name.title()
        if self.weapon_type:
            str_to_construct += ' ' + self.weapon_type.name.replace('_',' ').title()
        try:    
            str_to_construct += ' ' + '(' + str(self.power_cap) + ')'
        except AttributeError:
            pass
        if str_to_construct:
            if str_to_construct[1] == "(":
                str_to_construct = str_to_construct[2:-1]
            return '**' + str_to_construct.strip() + '**'
        return ''

@dataclass
class WeaponStatInfo:
    stat_type: constants.WeaponStats
    value: int

    def __str__(self):
        if self.stat_type == constants.WeaponStats.RPM:
            return f'**{self.stat_type.name.replace("_"," ")}**: ' + str(self.value)
        return f'**{self.stat_type.name.replace("_"," ").title()}**: ' + str(self.value)

@dataclass
class WeaponStat:
    idx: int
    stat: WeaponStatInfo

    def __str__(self):
        return str(self.stat)

    def __hash__(self):
        return hash(self.stat.stat_type)

    def __eq__(self, other):
        if not isinstance(other, type(self)): 
            return NotImplemented
        return self.stat.stat_type == other.stat.stat_type