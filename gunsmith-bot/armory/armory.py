import sqlite3
import os
import glob
import json
import logging
from dataclasses import dataclass
from . import constants

logger = logging.getLogger('Armory')

class Armory:
    def __init__(self, current_manifest):
        self._current_manifest_path = current_manifest

    def update_current_manifest_path(self, current_manifest):
        self._current_manifest_path = current_manifest

    def __search_weapon__(self, name):
        with sqlite3.connect(self._current_manifest_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT item.id, key, value FROM DestinyInventoryItemDefinition as item, json_each(item.json, '$')
            where json_extract(item.json, '$.displayProperties.name') LIKE ? and 
            json_extract(item.json, '$.sockets') is not null and
            (key) in ("displayProperties", "sockets", "itemCategoryHashes", "displaySource")''', (name + "%",))
            
            weapons = {}
            for row in cursor:
                weapons.setdefault(row[0], {}).update({row[1]: row[2]})

            if not weapons:
                raise ValueError
            else:
                return weapons
    
    def __process_weapon__(self, weapon_data):
        pass

    def get_weapon_details(self, name):
        weapons_data_raw = self.__search_weapon__(name)

        found_weapons = []
        for id, weapon_data_raw in weapons_data_raw.items():
            found_weapons.append(Weapon(id, weapon_data_raw, self._current_manifest_path))

        return found_weapons

class Weapon:
    def __init__(self, id, weapon_data_raw, current_manifest):
        self.db_id = id
        self._current_manifest_path = current_manifest
        self.weapon_base_info = WeaponBaseArchetype()
        self.name = None
        self.description = None
        self.icon = None
        self.intrinsic = None
        self.WeaponPerks = []

        self.__extract_data__(weapon_data_raw)
    
    def convert_hash(self, val):
        '''
        References:
        - Function originates from @vpzed: https://github.com/vpzed/Destiny2-API-Info/wiki/API-Introduction-Part-3-Manifest#manifest-lookups
        - https://github.com/Bungie-net/api/wiki/Obtaining-Destiny-Definitions-%22The-Manifest%22#step-4-open-and-use-the-data-contained-within
        '''
        if (val & (1 << (32 - 1))) != 0:
            val = val - (1 << 32)
        return val

    def __extract_data__(self, weapon_data_raw):
        with sqlite3.connect(self._current_manifest_path) as conn:
            cursor = conn.cursor()
            for key,value in weapon_data_raw.items():
                if key == "sockets":
                    socket_data = json.loads(value)
                    for category_data in socket_data["socketCategories"]:
                        if category_data["socketCategoryHash"] == constants.SocketCategoryHash().INTRINSICS:
                            for index in category_data['socketIndexes']:
                                socket = socket_data["socketEntries"][index]

                                plugs = []
                                if 'reusablePlugSetHash' in socket:
                                    reusablePlugSetHash = socket['reusablePlugSetHash']
                                    converted_reusablePlugSetHash = self.convert_hash(reusablePlugSetHash)

                                    cursor.execute(
                                    '''
                                    SELECT json_extract(j.value, '$.plugItemHash') 
                                    FROM DestinyPlugSetDefinition as item, 
                                    json_each(item.json, '$.reusablePlugItems') as j 
                                    WHERE item.id = ?''', (converted_reusablePlugSetHash,))

                                    for plug_res in cursor:
                                        plug_hash = plug_res[0]
                                        plug_cursor = conn.cursor()
                                        
                                        converted_plug_hash = self.convert_hash(plug_hash)

                                        plug_cursor.execute(
                                            '''
                                            SELECT json_extract(item.json, "$.displayProperties") 
                                            FROM DestinyInventoryItemDefinition as item 
                                            WHERE item.id = ?''', (converted_plug_hash,))
                                        
                                        plug_info = json.loads(plug_cursor.fetchone()[0])

                                        plugs.append(WeaponPerkPlugInfo(name = plug_info['name'], 
                                                                        description = plug_info['description'],
                                                                        icon = plug_info['icon']))
                            self.intrinsic = plugs
                        if category_data["socketCategoryHash"] == constants.SocketCategoryHash().WEAPON_PERKS:
                            for order_idx, index in enumerate(category_data['socketIndexes']):
                                socket = socket_data["socketEntries"][index]
                                socket_type_hash = socket['socketTypeHash']
                                converted_socket_type_hash = self.convert_hash(socket_type_hash)
                                    
                                # Assume plugWhitelist always has a len of 1
                                cursor.execute(
                                '''
                                SELECT json_extract(item.json, "$.plugWhitelist[0]") 
                                FROM DestinySocketTypeDefinition as item 
                                WHERE item.id = ?''', (converted_socket_type_hash,))
                            
                                plug_category_info = json.loads(cursor.fetchone()[0])

                                if not constants.PlugCategoryHash.is_valid(plug_category_info["categoryIdentifier"].title()):
                                    continue

                                plugs = []
                                if 'randomizedPlugSetHash' in socket:
                                    randomizedPlugSetHash = socket['randomizedPlugSetHash']
                                    
                                    converted_randomizedPlugSetHash = self.convert_hash(randomizedPlugSetHash)

                                    cursor.execute(
                                    '''
                                    SELECT json_extract(j.value, '$.plugItemHash') 
                                    FROM DestinyPlugSetDefinition as item, 
                                    json_each(item.json, '$.reusablePlugItems') as j
                                    WHERE item.id = ?''', (converted_randomizedPlugSetHash,))

                                    for plug_res in cursor:
                                        plug_hash = plug_res[0]
                                        converted_plug_hash = self.convert_hash(plug_hash)
                                        
                                        plug_cursor = conn.cursor()
                                        
                                        plug_cursor.execute(
                                            '''
                                            SELECT json_extract(item.json, "$.displayProperties") 
                                            FROM DestinyInventoryItemDefinition as item
                                            WHERE item.id = ?''', (converted_plug_hash,))
                                        
                                        plug_info = json.loads(plug_cursor.fetchone()[0])

                                        plugs.append(WeaponPerkPlugInfo(name = plug_info['name'], 
                                                                        description = plug_info['description'],
                                                                        icon = plug_info['icon']))

                                elif 'reusablePlugSetHash' in socket:
                                    reusablePlugSetHash = socket['reusablePlugSetHash']
                                    converted_reusablePlugSetHash = self.convert_hash(reusablePlugSetHash)

                                    cursor.execute(
                                    '''
                                    SELECT json_extract(j.value, '$.plugItemHash') 
                                    FROM DestinyPlugSetDefinition as item, 
                                    json_each(item.json, '$.reusablePlugItems') as j 
                                    WHERE item.id = ?''', (converted_reusablePlugSetHash,))

                                    for plug_res in cursor:
                                        plug_hash = plug_res[0]
                                        plug_cursor = conn.cursor()
                                        
                                        converted_plug_hash = self.convert_hash(plug_hash)

                                        plug_cursor.execute(
                                            '''
                                            SELECT json_extract(item.json, "$.displayProperties") 
                                            FROM DestinyInventoryItemDefinition as item 
                                            WHERE item.id = ?''', (converted_plug_hash,))
                                        
                                        plug_info = json.loads(plug_cursor.fetchone()[0])

                                        plugs.append(WeaponPerkPlugInfo(name = plug_info['name'], 
                                                                        description = plug_info['description'],
                                                                        icon = plug_info['icon']))

                                self.ProcessWeaponPerk(order_idx, plug_category_info["categoryHash"], plugs)
                                
                if key == "displayProperties":
                    display_data = json.loads(value)
                    self.name = display_data["name"]
                    self.description = display_data["description"]
                    self.icon = display_data["icon"]

                if key == "itemCategoryHashes":
                    item_categories_hashes = sorted(json.loads(value))
                    if item_categories_hashes.pop(0) != constants.WeaponBase.WEAPON.value:
                        logger.error("Item is not a weapon")
                        raise ValueError("Item is not a weapon")
                    
                    # Take only the first 2 hashes after weapon
                    for item_category_hash in item_categories_hashes[0:2]:
                        try:
                            category = constants.WeaponBase(item_category_hash)
                        except ValueError as e:
                            logger.error("Failed to match weapon category")
                            raise e
                        self.weapon_base_info.set_field(category)

    def ProcessWeaponPerk(self, order_idx, plug_category_hash, plugs): 
        plug_category = constants.PlugCategoryHash(plug_category_hash)
        self.WeaponPerks.append(WeaponPerk(idx = order_idx, 
                                           name = plug_category.name, 
                                           plugs = plugs))

@dataclass()
class WeaponPerkPlugInfo:
    name: str
    description: str
    icon: str

    def __str__(self):
        return self.name

@dataclass()
class WeaponPerk:
    idx: int
    name: str
    plugs: [WeaponPerkPlugInfo]

    def __str__(self):
        return '\n'.join(map(str,self.plugs))

@dataclass
class WeaponBaseArchetype:
    weapon_class: constants.WeaponBase = None
    weapon_type: constants.WeaponBase = None

    def set_field(self, input):
        if input.value < 5:
            self.weapon_class = input
        else:
            self.weapon_type = input

    def __str__(self):
        return '**' + self.weapon_class.name.title() + ' ' + self.weapon_type.name.replace('_',' ').title() + '**'


def setupLogger():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s', 
                        datefmt='%Y-%m-%d %I:%M:%S %p')
    logger.setLevel(logging.INFO)

if __name__ == "__main__":
    setupLogger()