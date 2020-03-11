import sqlite3
import os
import glob
import loader

class Armory:
    def __init__(self, current_manifest):
        self._current_manifest_path = current_manifest

    def update_current_manifest_path(current_manifest):
        self._current_manifest_path = current_manifest

    def __search_weapon__(name, current_manifest):
        with sqlite3.connect(current_manifest) as conn:
            cursor = conn.cursor()
            cursor.execute('''SELECT json_extract(DestinyInventoryItemDefinition.json, '$')
                        FROM DestinyInventoryItemDefinition, json_tree(DestinyInventoryItemDefinition.json, '$')
                        WHERE json_tree.key = 'name' AND json_tree.value = ?''', (name,))
            row = cursor.fetchone()
            if row == None:
                raise ValueError
            else:
                return row[0]
    
    def __process_weapon__(weapon_data):
        pass

    def get_weapon_details(name, current_manifest):
        weapon_data = __search_weapon__(name, current_manifest)
        found_weapon = Weapon(weapon_data)
        

class Weapon:
    def __init__(self, weapon_data):
        pass