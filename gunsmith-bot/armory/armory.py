import sqlite3
import os
import glob
import json
from dataclasses import dataclass
import loader
import constants

class Armory:
    def __init__(self, current_manifest):
        self._current_manifest_path = current_manifest

    def update_current_manifest_path(self, current_manifest):
        self._current_manifest_path = current_manifest

    def __search_weapon__(self, name):
        with sqlite3.connect(self._current_manifest_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT item.id, key, value FROM DestinyInventoryItemDefinition AS item, json_each(item.json, '$')
            where json_extract(item.json, '$.displayProperties.name') = ? and 
            (key) in ("displayProperties", "sockets", "displaySource")''', (name,))
            
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

                                    cursor.execute(
                                    '''
                                    SELECT json_extract(j.value, '$.plugItemHash') 
                                    FROM DestinyPlugSetDefinition AS item, 
                                    json_each(item.json, '$.reusablePlugItems') as j
                                    where json_extract(item.json, '$.hash') = ?''', (reusablePlugSetHash,))

                                    for plug_res in cursor:
                                        plug_hash = plug_res[0]
                                        plug_cursor = conn.cursor()

                                        plug_cursor.execute(
                                            '''
                                            SELECT value FROM DestinyInventoryItemDefinition AS item, 
                                            json_each(item.json, '$') WHERE json_extract(item.json, '$.hash') = ? 
                                            AND key = "displayProperties"''', (plug_hash,))
                                        
                                        plug_info = json.loads(plug_cursor.fetchone()[0])

                                        plugs.append(WeaponPerkDetails(name = plug_info['name'], 
                                                         description = plug_info['description'],
                                                         icon = plug_info['icon']))
                            self.intrinsic = plugs
                        if category_data["socketCategoryHash"] == constants.SocketCategoryHash().WEAPON_PERKS:
                            for index in category_data['socketIndexes']:
                                socket = socket_data["socketEntries"][index]
                                socket_type_hash = socket['socketTypeHash']

                                cursor.execute(
                                '''
                                SELECT value FROM DestinySocketTypeDefinition AS item, 
                                json_each(item.json, '$.plugWhitelist')
                                WHERE json_extract(item.json, '$.hash') = ?''', (socket_type_hash,))

                                socket_type_info = json.loads(cursor.fetchone()[0])

                                plugs = []
                                if 'randomizedPlugSetHash' in socket: # TODO Handle static rolls: reusablePlugSetHash
                                    randomizedPlugSetHash = socket['randomizedPlugSetHash']

                                    cursor.execute(
                                    '''
                                    SELECT json_extract(j.value, '$.plugItemHash') 
                                    FROM DestinyPlugSetDefinition AS item, 
                                    json_each(item.json, '$.reusablePlugItems') as j
                                    where json_extract(item.json, '$.hash') = ?''', (randomizedPlugSetHash,))

                                    for plug_res in cursor:
                                        plug_hash = plug_res[0]
                                        plug_cursor = conn.cursor()

                                        plug_cursor.execute(
                                            '''
                                            SELECT value FROM DestinyInventoryItemDefinition AS item, 
                                            json_each(item.json, '$') WHERE json_extract(item.json, '$.hash') = ? 
                                            AND key = "displayProperties"''', (plug_hash,))
                                        
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

@dataclass
class WeaponPerkDetails:
    name: str
    description: str
    icon: str