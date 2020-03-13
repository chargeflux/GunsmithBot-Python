import sqlite3
import os
import glob
import json
from dataclasses import dataclass
from . import constants

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
            (key) in ("displayProperties", "sockets", "displaySource")''', (name + "%",))
            
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

        self.name = None
        self.description = None
        self.icon = None

        self.intrinsic = None
        self.barrels = None
        self.magazines = None
        self.perks_1 = None
        self.perks_2 = None

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
                        if category_data["socketCategoryHash"] == constants.SocketCategoryHash().INTRINSICS: # TODO
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

                                        plugs.append(WeaponPerkDetails(name = plug_info['name'], 
                                                         description = plug_info['description'],
                                                         icon = plug_info['icon']))
                            self.intrinsic = plugs
                        if category_data["socketCategoryHash"] == constants.SocketCategoryHash().WEAPON_PERKS:
                            for index in category_data['socketIndexes']:
                                socket = socket_data["socketEntries"][index]
                                socket_type_hash = socket['socketTypeHash']
                                converted_socket_type_hash = self.convert_hash(socket_type_hash)
                                    
                                # Assume plugWhitelist always has a len of 1
                                cursor.execute(
                                '''
                                SELECT json_extract(item.json, "$.plugWhitelist[0]") 
                                FROM DestinySocketTypeDefinition as item 
                                WHERE item.id = ?''', (converted_socket_type_hash,))

                                socket_type_info = json.loads(cursor.fetchone()[0])

                                plugs = []
                                if 'randomizedPlugSetHash' in socket: # TODO Handle static rolls: reusablePlugSetHash
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

                                        plugs.append(WeaponPerkDetails(name = plug_info['name'], 
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

                                        plugs.append(WeaponPerkDetails(name = plug_info['name'], 
                                                         description = plug_info['description'],
                                                         icon = plug_info['icon']))

                                if socket_type_info["categoryHash"] == constants.SocketTypeHash().BARRELS:
                                    self.barrels = plugs
                                if socket_type_info["categoryHash"] == constants.SocketTypeHash().MAGAZINES:
                                    self.magazines = plugs
                                if socket_type_info["categoryHash"] == constants.SocketTypeHash().FRAMES:
                                    if not self.perks_1:
                                        self.perks_1 = plugs
                                    else:
                                        self.perks_2 = plugs
                if key == "displayProperties":
                    display_data = json.loads(value)
                    self.name = display_data["name"]
                    self.description = display_data["description"]
                    self.icon = display_data["icon"]

@dataclass(eq = True)
class WeaponPerkDetails:
    name: str
    description: str
    icon: str