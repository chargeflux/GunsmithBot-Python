import os
import json
import sqlite3
import logging
from dataclasses import dataclass
from typing import List
import aiosqlite
from . import constants

logger = logging.getLogger('WeaponRollFinder')

logging.getLogger("aiosqlite").setLevel("WARNING")

class WeaponRollDB:
    '''
    Creates a database synchronously containing perks with weapon database ids 
    that can roll that perk in tables of plug categories (barrels, magazines etc.)

    Attributes 
    ----------
    current_manifest_path : str
        The path to Bungie's manifest of static definitions in Destiny 2
    
    weapon_db_path : str
        The path to the DB holding weapon db ids mapped to perks in tables of plug categories
    '''
    def __init__(self, current_manifest_path):
        logger.debug(f"Setting manifest path: {current_manifest_path}")
        self.current_manifest_path = current_manifest_path
        self.weapon_db_path = self.current_manifest_path + ".weapons"
    
    def check_DB_exists(self):
        if os.path.exists(self.current_manifest_path + ".weapons"):
            return True
        else:
            return False

    def initializeDB(self):
        self._create_weapons_db()
        raw_weapon_data = self._get_all_weapons_sockets()
        weapon_data = self._process_socket_data(raw_weapon_data)
        weapon_perk_ids = self._create_weapon_plug_dicts(weapon_data)
        self._store_plug_weapon_ids(weapon_perk_ids)
    
    def _create_weapons_db(self):
        create_table_sqls = ""
        for perk_type in constants.PlugCategoryTables:
            create_table_sql = f'''CREATE TABLE IF NOT EXISTS {perk_type} 
                                   (perk_name text NOT NULL, db_ids text NOT NULL);'''
            create_table_sqls += create_table_sql
        with sqlite3.connect(self.weapon_db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.executescript(create_table_sqls)
            except:
                logger.critical("Table creation failed")

    def _get_all_weapons_sockets(self):
        '''
        Get socket data for all Destiny 2 weapons from `DestinyInventoryItemDefinition` using
        the values in `itemCategoryHashes` that correspond to a weapon

        Returns
        -------
        data : [(int, str, str)]
            Returns a list of tuples containing the weapon's database id, weapon name 
            and socket data. Socket data is in the form of JSON
        '''
        weapon_sockets_sql = '''SELECT item.id, json_extract(item.json, "$.displayProperties.name") AS name, 
                                json_extract(item.json, "$.sockets") AS socket 
                                FROM DestinyInventoryItemDefinition AS item, json_each(item.json, '$.itemCategoryHashes') 
                                WHERE json_each.value = 1 AND socket IS NOT null;'''
        with sqlite3.connect(self.current_manifest_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(weapon_sockets_sql)
            except:
                logger.critical("Getting weapons failed")
            data = cursor.fetchall()
        return data
    
    def _process_socket_data(self, data):
        '''
        Processes socket data to obtain the intrinsic nature and perks for each weapon

        Parameters
        ----------
        data : [(int, str, str)]
            A list of tuples containing the weapon's database id, weapon name 
            and socket data. Socket data must be loaded as JSON

        Returns
        -------
        weapon_data : [WeaponPlugSet]
            Returns a list of weapon plug categories with perks that can slot in as a `WeaponPlugSet`
        '''
        weapon_data = []
        with sqlite3.connect(self.current_manifest_path) as conn:
            cursor = conn.cursor()
            for weapon in data:
                weapon_plugs = []
                socket_data = json.loads(weapon[2])
                for category_data in socket_data["socketCategories"]:
                    if category_data["socketCategoryHash"] == constants.SocketCategoryHash.INTRINSICS.value:
                        intrinsic_data = None
                        index = category_data['socketIndexes'][0]
                        socket = socket_data["socketEntries"][index]
                        intrinsic_data = self._process_socket_intrinsic_name(socket, cursor)
                        if intrinsic_data:
                            intrinsic = WeaponPlugSet(intrinsic_data[0], intrinsic_data[1])
                            weapon_plugs.append(intrinsic)
                    if category_data["socketCategoryHash"] == constants.SocketCategoryHash.WEAPON_PERKS.value:
                        weapon_perks_data = self._process_socket_data_perk_names(socket_data["socketEntries"], 
                                                                                 category_data['socketIndexes'], 
                                                                                 cursor)
                        for plug, data in weapon_perks_data.items():
                            weapon_plugs.append(WeaponPlugSet(plug, data))
                weapon = Weapon(str(weapon[0]), weapon[1], weapon_plugs)
                weapon_data.append(weapon)
        return weapon_data

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

    def _process_socket_intrinsic_name(self, socket, cursor):
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
        (str, [str]) or None
            Returns "intrinsics" (denotes category) and the corresponding intrinsic name
        '''

        if 'reusablePlugSetHash' not in socket:
            logger.error("reusablePlugSetHash not found in socket entry for intrinisic nature")
            return None

        reusablePlugSetHash = socket['reusablePlugSetHash']
        converted_reusablePlugSetHash = self._convert_hash(reusablePlugSetHash)

        cursor.execute(
        '''
        SELECT json_extract(j.value, '$.plugItemHash') 
        FROM DestinyPlugSetDefinition as item, 
        json_each(item.json, '$.reusablePlugItems') as j
        WHERE item.id = ?''', (converted_reusablePlugSetHash,))

        plug_hash = (cursor.fetchone())[0]
        
        converted_plug_hash = self._convert_hash(plug_hash)

        cursor.execute(
            '''
            SELECT json_extract(item.json, "$.displayProperties.name") 
            FROM DestinyInventoryItemDefinition as item 
            WHERE item.id = ?''', (converted_plug_hash,))
        
        intrinsic_name = (cursor.fetchone())[0]

        return constants.PlugCategoryHash.INTRINSICS.name.lower(), [intrinsic_name]

    def _process_socket_data_perk_names(self, socket_entries, socket_indexes, cursor):
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

        Returns
        -------
        perks : dict
            Returns a dict containing the different plug categories and associated perk names for the weapon
        '''
        perks = {}
        perks2 = False
        for order_idx, index in enumerate(socket_indexes):
            socket = socket_entries[index]
            socket_type_hash = socket['socketTypeHash']
            converted_socket_type_hash = self._convert_hash(socket_type_hash)
                
            # Assume plugWhitelist always has a len of 1
            cursor.execute(
            '''
            SELECT json_extract(item.json, "$.plugWhitelist[0]") 
            FROM DestinySocketTypeDefinition as item 
            WHERE item.id = ?''', (converted_socket_type_hash,))
        
            plug_category_info = json.loads((cursor.fetchone())[0])

            try:
                plug_category = constants.PlugCategoryHash(plug_category_info["categoryHash"])
            except ValueError:
                continue
            
            if plug_category == constants.PlugCategoryHash.PERKS:
                if "perks1" in perks:
                    perks2 = True

            if 'randomizedPlugSetHash' in socket:
                plug_set_hash = socket['randomizedPlugSetHash']
            elif 'reusablePlugSetHash' in socket:
                plug_set_hash = socket['reusablePlugSetHash']
            else:
                logger.error("randomizedPlugSetHash or reusablePlugSetHash not found in socket entry for weapon perks")
                continue
                
            converted_plug_set_hash = self._convert_hash(plug_set_hash)

            cursor.execute(
            '''
            SELECT json_extract(j.value, '$.plugItemHash'), json_extract(j.value, '$.currentlyCanRoll') 
            FROM DestinyPlugSetDefinition as item,
            json_each(item.json, '$.reusablePlugItems') as j
            WHERE item.id = ?''', (converted_plug_set_hash,))

            converted_plug_id_results = []

            for row in cursor:
                if row[1]:
                    converted_plug_id_results.append(self._convert_hash(row[0]))

            # SQL does not support binding to a list. Therefore we can dynamically insert question marks
            # based on the length of the converted_plug_id_results. Additionally, since we are only inserting 
            # question marks, we are not exposing ourselves to a security risk
            cursor.execute(
                f'''
                SELECT json_extract(item.json, "$.displayProperties.name") 
                FROM DestinyInventoryItemDefinition as item
                WHERE item.id in ({",".join(["?"]*len(converted_plug_id_results))})''', converted_plug_id_results)
            
            for perk in cursor:
                perk_name = perk[0]
                if plug_category.name.lower() == "perks":
                    if not perks2:
                        perks.setdefault("perks1", []).append(perk_name)
                    else:
                        perks.setdefault("perks2", []).append(perk_name)
                    continue
                perks.setdefault(plug_category.name.lower(), []).append(perk_name)
        return perks

    def _create_weapon_plug_dicts(self, weapon_data):
        '''
        Maps each plug category to a dictionary of associated perks and the weapon database ids
        that can roll that 
        
        Parameters
        ----------
        weapon_data : [WeaponPlugSet]
            A list of weapon plug categories with perks that can slot in as a `WeaponPlugSet`

        Returns
        -------
        data : dict
            Returns a dict containing the different plug categories mapped to a dict for associated perks and
            the weapon database ids that can roll that perk
        '''
        data = {}
        for weapon in weapon_data:
            for plug in weapon.plugs:
                for perk in plug.perks:
                    data.setdefault(plug.category, {}).setdefault(perk, []).append(weapon.db_id)
        return data

    def _store_plug_weapon_ids(self, plug_weapon_ids):
        '''
        Stores the dicts created from `self._create_weapon_plug_dicts` into the appropriate tables
        in the weapons rolls DB

        Parameters
        ----------
        plug_weapon_ids : dict
            A dict containing the different plug categories mapped to a dict for associated perks and
            the weapon database ids that can roll that perk
        '''
        with sqlite3.connect(self.weapon_db_path) as conn:
            cursor = conn.cursor()
            for plug_category, perk_data in plug_weapon_ids.items():
                table = plug_category
                sql = ''
                table_perks = []
                for perk_name, weapon_ids in perk_data.items():
                    weapon_ids_str = ','.join(weapon_ids)
                    table_perks.append((perk_name, weapon_ids_str))
                sql = f'''INSERT into {table} VALUES(?,?)'''
                cursor.executemany(sql, table_perks)

class WeaponRollFinder:
    def __init__(self, current_manifest_path):
        logger.debug(f"Setting manifest path: {current_manifest_path}")
        self.current_manifest_path = current_manifest_path
        self.weapon_db_path = current_manifest_path + ".weapons"
    
    async def find_all_perks_plug_nonperks1_2(self, category, perk_names):
        '''
        Find all perks that are not "traits", e.g., Outlaw, Rampage and get
        weapon database ids

        Parameters
        ----------
        category : str
            Plug category for perks to search for that corresponds to the table name
        
        perk_names: [str]
            The names of the perks associated with the plug category to search for
        
        Returns
        ----------
        perk_weapon_ids : [ints] or None
            Returns all weapon ids associated with the perk or perks 
        '''
        perk_weapon_ids = None
        async with aiosqlite.connect(self.weapon_db_path) as conn:
            cursor = await conn.cursor()
            db_ids = None
            for perk in perk_names:
                sql = f'''SELECT db_ids FROM {category} WHERE perk_name=?'''
                await cursor.execute(sql, (perk,))
                async for result in cursor:
                    result = result[0].split(",")
                    db_ids = set(map(int, result))
                if perk_weapon_ids:
                    perk_weapon_ids = perk_weapon_ids.intersection(db_ids)
                elif db_ids:
                    perk_weapon_ids = db_ids
                else:
                    logger.error(f"{perk} not found in {category}")
        return perk_weapon_ids
    
    async def _process_perk_groups(self, perk_groups, multiple=False):
        '''
        Find all perks that are "traits", e.g., Outlaw, Rampage and get
        weapon database ids. It is necessary to search both trait tables (`perks1` and `perks2`)
        and perform logic to find the relevant weapon database ids.

        Parameters
        ----------
        perk_groups : [str]
            Contains perk groups (up to 2) holding the perks that should be in their own
            respective group
        
        Returns
        ----------
        perk_weapon_ids : [ints] or None
            Returns all weapon ids associated with the perk or perks
        '''
        async with aiosqlite.connect(self.weapon_db_path) as conn:
            cursor = await conn.cursor()
            perk_weapon_ids = None
            
            if multiple:
                perk_plugs = {}
                for idx, perk_names in enumerate(perk_groups):
                    status = 0
                    perk_weapon_ids_current_group = None
                    
                    sql = f'''SELECT db_ids FROM perks1 
                                WHERE perk_name in ({",".join(["?"]*len(perk_names))})'''
                    await cursor.execute(sql, perk_names)

                    db_ids_perks1 = WeaponPlugSet("perks1", [])
                    async for result in cursor:
                        result = result[0].split(",")
                        result = set(map(int, result))
                        db_ids_perks1.perks.append(result)
                    if len(db_ids_perks1.perks) != len(perk_names):
                        db_ids_perks1 = None
                        logger.error(f"Not found in perks1 table: {perk_names}")
                    else:
                        status += 1
                        db_ids_perks1.perks = set.intersection(*db_ids_perks1.perks)
                        perk_plugs.setdefault(idx, []).append(db_ids_perks1)

                    sql = f'''SELECT db_ids FROM perks2 
                                WHERE perk_name in ({",".join(["?"]*len(perk_names))})'''
                    await cursor.execute(sql, perk_names)
                    db_ids_perks2 = WeaponPlugSet("perks2", [])
                    async for result in cursor:
                        result = result[0].split(",")
                        result = set(map(int, result))
                        db_ids_perks2.perks.append(result)
                    if len(db_ids_perks2.perks) != len(perk_names):
                        db_ids_perks2 = None
                        logger.error(f"Not found in perks2 table: {perk_names}")
                    else:
                        status += 1
                        db_ids_perks2.perks = set.intersection(*db_ids_perks2.perks)
                        perk_plugs.setdefault(idx, []).append(db_ids_perks2)
                    
                    if status == 0:
                        return None
                    perk_plugs[idx].insert(0, status)
                
                perk_plug_bigger = []
                if perk_plugs[0][0] < perk_plugs[1][0]:
                    perk_plug_smaller = perk_plugs[0][1]
                    perk_plug_bigger = perk_plugs[1][1:]
                elif perk_plugs[0][0] > perk_plugs[1][0]:
                    perk_plug_smaller = perk_plugs[1][1]
                    perk_plug_bigger = perk_plugs[0][1:]
                elif perk_plugs[0][0] == 1:
                    perk_plug_smaller = perk_plugs[0][1]
                    perk_plug_bigger = perk_plugs[1][1:]
                elif perk_plugs[0][0] == 2:
                    perk_plug_first = perk_plugs[0][1:]
                    perk_plug_second = perk_plugs[1][1:]
                    one_two_inter = perk_plug_first[0].perks.intersection(perk_plug_second[1].perks)
                    two_one_inter = perk_plug_first[1].perks.intersection(perk_plug_second[0].perks)
                    result = one_two_inter.union(two_one_inter)
                    perk_weapon_ids = result
                for bigger in perk_plug_bigger:
                    if bigger:
                        if perk_plug_smaller.category != bigger.category:
                            result = perk_plug_smaller.perks.intersection(bigger.perks)
                            perk_weapon_ids = result
            else:
                # only perks belonging to perks1 or perks2, not both
                for perk_names in perk_groups:
                    perk_weapon_ids_current_group = None
                    
                    sql = f'''SELECT db_ids FROM perks1 
                                WHERE perk_name in ({",".join(["?"]*len(perk_names))})'''
                    await cursor.execute(sql, perk_names)

                    db_ids_perks = []
                    async for result in cursor:
                        result = result[0].split(",")
                        result = set(map(int, result))
                        db_ids_perks.append(result)
                    if len(db_ids_perks) == len(perk_names):
                        perk_weapon_ids_current_group = set.intersection(*db_ids_perks)
                    else:
                        logger.error(f"Not found in perks1 table: {perk_names}")

                    sql = f'''SELECT db_ids FROM perks2 
                                WHERE perk_name in ({",".join(["?"]*len(perk_names))})'''
                    await cursor.execute(sql, perk_names)
                    db_ids_perks = []
                    async for result in cursor:
                        result = result[0].split(",")
                        result = set(map(int, result))
                        db_ids_perks.append(result)
                    if len(db_ids_perks) == len(perk_names):
                        if perk_weapon_ids_current_group:
                            perk_weapon_ids_current_table = set.intersection(*db_ids_perks)
                            perk_weapon_ids_current_group = perk_weapon_ids_current_group.union(perk_weapon_ids_current_table)
                    else:
                        logger.error(f"Not found in perks2 table: {perk_names}")

                    if perk_weapon_ids and perk_weapon_ids_current_group:
                        perk_weapon_ids.intersection(perk_weapon_ids_current_group)
                    elif perk_weapon_ids_current_group:
                        perk_weapon_ids = perk_weapon_ids_current_group
        return perk_weapon_ids

    async def _find_weapon_ids(self, query):
        '''
        Find all weapon ids from the query of perk parameters

        Parameters
        ----------
        query : dict
            A dict containing the plug category and the perks requested associated with it. 
            The perks are as a string and should be split as ", "
        
        Returns
        ----------
        result_weapon_ids : [ints] or None
            Returns all weapon database ids that fulfill the query
        '''
        result_weapon_ids = []
        if "perks2" in query:
            perk_weapon_ids = await self._process_perk_groups([query["perks1"], query["perks2"]], multiple=True)
            result_weapon_ids.append(perk_weapon_ids)
            query.pop("perks1")
            query.pop("perks2")
        if "perks1" in query:
            perk_weapon_ids = await self._process_perk_groups([query["perks1"]])
            result_weapon_ids.append(perk_weapon_ids)
            query.pop("perks1")
        for category, perk_names in query.items():
            perk_weapon_ids = await self.find_all_perks_plug_nonperks1_2(category, perk_names)
            result_weapon_ids.append(perk_weapon_ids)
        try:
            result_weapon_ids = list(set.intersection(*result_weapon_ids))
        except:
            logger.error("One of the query plugs was incorrect. No weapons found")
            result_weapon_ids = None

        return result_weapon_ids

    def _clean_up_query(self, raw_query):
        '''
        Find all weapon ids from the query of perk parameters

        Parameters
        ----------
        raw_query : str
            Formatted as -<perk type> <perk name>, <perk name> -<perk type> <perk name>
        
        Returns
        ----------
        query : dict or None
            Maps the associated list of perk names to each perk type/plug category
        '''
        raw_query = raw_query.split()
        current_key = None
        current_perks = ""
        query = {}
        for term in raw_query:
            if term.startswith("-"):
                if current_perks:
                    perks_list = current_perks.split(", ")
                    perks_list = [x.title() for x in perks_list]
                    query[current_key] = perks_list
                    current_perks = ""
                current_key = term[1:]
            else:
                if current_perks:
                    current_perks += " " + term
                else:
                    current_perks += term
        if current_perks:
            perks_list = current_perks.split(", ")
            perks_list = [x.title() for x in perks_list]
            query[current_key] = perks_list
        
        for category in query:
            if category not in constants.PlugCategoryTables:
                logger.error(f"{category} is not a valid plug category")
                return None
        
        return query
    
    def _parse_weapon_type(self, item_category_hashes):
        '''
        Parses the weapon type based on its `itemCategoryHashes`, e.g., auto rifle or sword

        Parameters
        ----------
        item_category_hashes : [int]            
        
        Returns
        ----------
        weapon_type : str
        '''
        weapon_type = None
        if constants.WeaponBase.DUMMY.value in item_category_hashes:
            return None
        for hash in item_category_hashes:
            try:
                category = constants.WeaponBase(hash)
                if category.value >= 5 and category:
                    weapon_type = category
                    break
            except ValueError:
                logger.debug(f"Failed to match weapon category hash: {hash}")
        return weapon_type.name.replace("_"," ").title()


    async def process_query(self, query):
        '''
        Parses the weapon type based on its `itemCategoryHashes`, e.g., auto rifle or sword

        Parameters
        ----------
        query : str
            Formatted as -<perk type> <perk name>, <perk name> -<perk type> <perk name>    
        
        Returns
        ----------
        weapon_count : int

        weapons : dict or None
            Each weapon type is mapped to a list of weapons of that type
        '''
        query = self._clean_up_query(query)
        if not query:
            logger.error("One of the query parameters was incorrect")
            return 0, None
        result = await self._find_weapon_ids(query)
        if result:
            async with aiosqlite.connect(self.current_manifest_path) as conn:
                cursor = await conn.cursor()
                sql = f'''SELECT json_extract(json,"$.displayProperties.name"), 
                        json_extract(json,"$.itemCategoryHashes")
                        from DestinyInventoryItemDefinition where 
                        id in ({",".join(["?"]*len(result))})'''
                
                await cursor.execute(sql, result)

                weapons = {}
                async for weapon in cursor:
                    category_hashes = json.loads(weapon[1])
                    weapon_type = self._parse_weapon_type(category_hashes)
                    if weapon_type:
                        weapons.setdefault(weapon_type, []).append(weapon[0]) 
                return len(result), weapons
        else:
            return 0, None

@dataclass
class WeaponPlugSet:
    category: str
    perks: [str]

@dataclass
class Weapon:
    db_id: str
    name: str # Useful for debugging
    plugs: List[WeaponPlugSet]