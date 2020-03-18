import sqlite3
import os
import glob
import json
import logging
import itertools
from dataclasses import dataclass
from typing import List
from . import constants

logger = logging.getLogger('Armory')

class Armory:
    '''
    Interfaces with Bungie's manifest to query for weapons

    Attributes 
    ----------
    _current_manifest_path : str
        The path to Bungie's manifest of static definitions in Destiny 2
    '''

    def __init__(self, current_manifest_path):
        logger.debug(f"Setting manifest path: {current_manifest_path}")
        self._current_manifest_path = current_manifest_path
    
    def get_current_manifest(self):
        return self._current_manifest_path

    def __search_weapon(self, search):
        '''
        Search for a Destiny 2 weapon in "DestinyInventoryItemDefinition" and extract JSON for all
        matches

        Parameters
        ----------
        name: str
            The name of the Destiny 2 weapon

        Returns
        -------
        weapons: [WeaponResult]
            The weapons found in the manifest where each is a `WeaponResult`
        '''
        with sqlite3.connect(self._current_manifest_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT item.id, json FROM DestinyInventoryItemDefinition as item 
            WHERE json_extract(item.json, '$.displayProperties.name') LIKE ?''', (search + "%",))

            weapons = []
            for row in cursor:
                raw_weapon_data = json.loads(row[1])
                if self.__validate_weapon_search(raw_weapon_data):
                    weapons.append(WeaponResult(row[0], raw_weapon_data))

            if not weapons:
                raise ValueError
            else:
                return weapons
    
    def __validate_weapon_search(self, raw_weapon_data):
        '''
        Validate the JSON of weapon found from querying the manifest

        Parameters
        ----------
        raw_weapon_data: dict()
            Derived from json data for the weapon

        Returns
        -------
        bool
            If the item found is a weapon
        '''
        if constants.WeaponBase.WEAPON.value not in raw_weapon_data["itemCategoryHashes"]:
            return False
        if 'sockets' not in raw_weapon_data.keys():
            return False
        return True


    def get_weapon_details(self, name):
        '''
        Search and retrieve information about a Destiny 2 weapon from Bungie's manifest

        Parameters
        ----------
        name: str
            The name of the Destiny 2 weapon

        Returns
        -------
        weapons : [Weapon]
            A list where each individual weapon is a `Weapon`
        '''

        weapon_results = self.__search_weapon(name)

        weapons = []
        for weapon_result in weapon_results:
            weapon = Weapon(weapon_result, self._current_manifest_path)
            if weapon.has_random_rolls:
                weapons.insert(0, weapon)
            else:
                weapons.append(weapon)

        return weapons

class WeaponResult:
    '''
    Represents the JSON data for a weapon

    Attributes
    ----------
    db_id: int
        The database id of the weapon in Bungie's manifest in "DestinyInventoryItemDefinition"
    
    display_properties_data: dict
        Holds information about the name, description and image of the weapon

    socket_data: dict
        Holds information about the intrinsic nature and possible perks for the weapon
    
    item_categories_hash_data: dict
        Holds information about the categories which this weapon is classifed as

    display_source_data: str
        Determines if it has random rolls or not
    
    tierTypeHash : dict
        Determines the tier type of the wepaon
    '''

    def __init__(self, db_id, raw_weapon_data):
        self.db_id = db_id
        self.display_properties_data = raw_weapon_data["displayProperties"]
        self.socket_data = raw_weapon_data["sockets"]
        self.item_categories_hash_data = sorted(raw_weapon_data["itemCategoryHashes"])
        self.display_source_data = raw_weapon_data["displaySource"]
        self.tier_type_hash = raw_weapon_data["inventory"]["tierTypeHash"]

class Weapon:
    '''
    Contains all the necessary information for a Destiny 2 weapon

    Attributes 
    ----------
    db_id : int
        The database id of the weapon in Bungie's manifest in "DestinyInventoryItemDefinition"
    
    _current_manifest_path : str
        The path to Bungie's manifest of static definitions in Destiny 2
    
    weapon_base_info: WeaponBaseArchetype
    
    name : str
        The name of the weapon
    
    description: str
        The description of the weapon

    icon: str
        The relative url to the icon of the weapon at bungie.net
    
    intrinsic: WeaponPerkPlugInfo
        Represents the intrinsic nature of the weapon, e.g., adaptive frame
    
    weapon_perks: [WeaponPerkPlugInfo]
        Holds all the possible plugs for each perk if random rolled. Otherwise it will show
        the static roll
    
    has_random_rolls: bool
        If the weapon has random rolls or not
    '''

    def __init__(self, weapon_result, current_manifest):
        self.db_id = weapon_result.db_id
        self._current_manifest_path = current_manifest

        self.weapon_base_info = self.__set_base_info(weapon_result.item_categories_hash_data, weapon_result.tier_type_hash)
        
        self.name = weapon_result.display_properties_data["name"]
        self.description = weapon_result.display_properties_data["description"]
        self.icon = constants.BUNGIE_URL_ROOT + weapon_result.display_properties_data["icon"]
        
        if weapon_result.display_source_data:
            self.has_random_rolls = True
        else:
            self.has_random_rolls = False

        self.intrinsic, self.weapon_perks = self.__process_socket_data(weapon_result.socket_data)
    
    def __convert_hash(self, val):
        '''
        Converts the item hash to the id used by the database

        References:
        - Function originates from @vpzed: https://github.com/vpzed/Destiny2-API-Info/wiki/API-Introduction-Part-3-Manifest#manifest-lookups
        - https://github.com/Bungie-net/api/wiki/Obtaining-Destiny-Definitions-%22The-Manifest%22#step-4-open-and-use-the-data-contained-within
        '''
        if (val & (1 << (32 - 1))) != 0:
            val = val - (1 << 32)
        return val

    def __process_socket_intrinsic(self, socket, cursor):
        '''
        Processes socket entry corresponding to information about the intrinsic nature of the weapon.
        This socket usually only has a "reusablePlugSetHash" field since intrinsic nature of 
        a weapon is not randomized. Use "DestinyPlugSetDefinition" and "DestinyInventoryItemDefinition" 
        with the hash to obtain the plug for this socket corresponding to intrinsic nature.

        Parameters
        ----------
        socket : dict
            The socket entry corresponding to the intrinsic nature of the weapon
        cursor : sqlite3.Cursor
            Necessary to query SQLite3 DB

        Returns
        -------
        WeaponPerkPlugInfo or None
        '''

        if 'reusablePlugSetHash' not in socket:
            logger.error("reusablePlugSetHash not found in socket entry for intrinisic nature")
            return None

        reusablePlugSetHash = socket['reusablePlugSetHash']
        converted_reusablePlugSetHash = self.__convert_hash(reusablePlugSetHash)

        cursor.execute(
        '''
        SELECT json_extract(j.value, '$.plugItemHash') 
        FROM DestinyPlugSetDefinition as item, 
        json_each(item.json, '$.reusablePlugItems') as j
        WHERE item.id = ?''', (converted_reusablePlugSetHash,))

        plug_hash = cursor.fetchone()[0]
        
        converted_plug_hash = self.__convert_hash(plug_hash)

        cursor.execute(
            '''
            SELECT json_extract(item.json, "$.displayProperties") 
            FROM DestinyInventoryItemDefinition as item 
            WHERE item.id = ?''', (converted_plug_hash,))
        
        plug_info = json.loads(cursor.fetchone()[0])

        return WeaponPerkPlugInfo(name = plug_info['name'], 
                                  description = plug_info['description'],
                                  icon = plug_info['icon'])

    def __process_socket_data_perks(self, socket_entries, socket_indexes, cursor):
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
        
        cursor : sqlite3.Cursor
            Necessary to query SQLite3 DB

        Returns
        -------
        weapon_perks : [WeaponPerk]
            Returns a list of weapon perks where each is a `WeaponPerk`
        '''
        weapon_perks = []
        for order_idx, index in enumerate(socket_indexes):
            socket = socket_entries[index]
            socket_type_hash = socket['socketTypeHash']
            converted_socket_type_hash = self.__convert_hash(socket_type_hash)
                
            # Assume plugWhitelist always has a len of 1
            cursor.execute(
            '''
            SELECT json_extract(item.json, "$.plugWhitelist[0]") 
            FROM DestinySocketTypeDefinition as item 
            WHERE item.id = ?''', (converted_socket_type_hash,))
        
            plug_category_info = json.loads(cursor.fetchone()[0])

            try:
                plug_category = constants.PlugCategoryHash(plug_category_info["categoryHash"])
            except ValueError:
                continue

            if 'randomizedPlugSetHash' in socket:
                plug_set_hash = socket['randomizedPlugSetHash']
            elif 'reusablePlugSetHash' in socket:
                plug_set_hash = socket['reusablePlugSetHash']
            else:
                logger.error("randomizedPlugSetHash or reusablePlugSetHash not found in socket entry for weapon perks")
                continue
                
            converted_plug_set_hash = self.__convert_hash(plug_set_hash)

            cursor.execute(
            '''
            SELECT json_extract(j.value, '$.plugItemHash') 
            FROM DestinyPlugSetDefinition as item, 
            json_each(item.json, '$.reusablePlugItems') as j
            WHERE item.id = ?''', (converted_plug_set_hash,))

            converted_plug_id_results = list(map(self.__convert_hash,itertools.chain.from_iterable(cursor)))

            # SQL does not support binding to a list. Therefore we can dynamically insert question marks
            # based on the length of the converted_plug_id_results. Additionally, since we are only inserting 
            # question marks, we are not exposing ourselves to a security risk
            cursor.execute(
                f'''
                SELECT json_extract(item.json, "$.displayProperties") 
                FROM DestinyInventoryItemDefinition as item
                WHERE item.id in ({",".join(["?"]*len(converted_plug_id_results))})''', converted_plug_id_results)
            
            plugs = []
            for plug in cursor:
                plug_info = json.loads(plug[0])
                plugs.append(WeaponPerkPlugInfo(name = plug_info['name'], 
                                                description = plug_info['description'],
                                                icon = plug_info['icon']))

            weapon_perks.append(WeaponPerk(idx = order_idx, name = plug_category.name.title(), plugs = plugs))
        return weapon_perks


    def __process_socket_data(self, socket_data):
        '''
        Processes socket data for information about the intrinsic nature and perks
        for the weapon.

        Parameters
        ----------
        socket_data : dict
            The socket data of the weapon to be processed

        Returns
        -------
        intrinsic : WeaponPerkPlugInfo
        
        weapon_perks : [WeaponPerk]
            Returns a list of weapon perks where each is a `WeaponPerk`
        '''
        with sqlite3.connect(self._current_manifest_path) as conn:
            cursor = conn.cursor()
            for category_data in socket_data["socketCategories"]:
                if category_data["socketCategoryHash"] == constants.SocketCategoryHash.INTRINSICS.value:
                        index = category_data['socketIndexes'][0] # assume only one intrinsic
                        socket = socket_data["socketEntries"][index]
                        intrinsic = self.__process_socket_intrinsic(socket, cursor)
                if category_data["socketCategoryHash"] == constants.SocketCategoryHash.WEAPON_PERKS.value:
                    weapon_perks = self.__process_socket_data_perks(socket_data["socketEntries"], 
                                                                    category_data['socketIndexes'], 
                                                                    cursor)
        return intrinsic, weapon_perks


    def __set_base_info(self, item_categories_hash_data, tier_type_hash):
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
                logger.error(f"Failed to match weapon category hash: {item_category_hash}")
        try: 
            weapon_tier = constants.WeaponTierType(tier_type_hash)
            weapon_base_info.weapon_tier_type = weapon_tier
        except ValueError:
            logger.error(f"Failed to match tier type hash: {tier_type_hash}")
        return weapon_base_info

@dataclass
class WeaponPerkPlugInfo:
    name: str
    description: str
    icon: str

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
    '''
    weapon_class: constants.WeaponBase = None
    weapon_type: constants.WeaponBase = None
    weapon_tier_type: constants.WeaponTierType = None

    def set_field(self, input: constants.WeaponBase):
        if input.value < 5:
            self.weapon_class = input
        else:
            self.weapon_type = input

    def __str__(self):
        str_to_construct = ''
        if self.weapon_class:
            str_to_construct = self.weapon_class.name.title()
        if self.weapon_type:
            str_to_construct += ' ' + self.weapon_type.name.replace('_',' ').title()
        if self.weapon_tier_type:
            str_to_construct += ' ' + '(' + self.weapon_tier_type.name.title() + ')'
        if str_to_construct:
            if str_to_construct[1] == "(":
                str_to_construct = str_to_construct[2:-1]
            return '**' + str_to_construct.strip() + '**'
        return ''

def setupLogger():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s', 
                        datefmt='%Y-%m-%d %I:%M:%S %p')
    logger.setLevel(logging.INFO)

if __name__ == "__main__":
    setupLogger()