import pytest
import sqlite3
import sys
import os
from gunsmith_bot.armory import Armory
from gunsmith_bot.armory.armory import WeaponBaseArchetype, constants

class TestArmory():
    def test_update_current_manifest(self):
        current_manifest_path = "/path/to/file"
        armory = Armory(current_manifest_path)
        assert armory.get_current_manifest() == current_manifest_path

        new_manifest_path = "/new/path/to/file"
        armory.update_current_manifest_path(new_manifest_path)
        assert armory.get_current_manifest() == new_manifest_path
    
    def test_get_current_manifest(self):
        current_manifest_path = "/path/to/file"
        armory = Armory(current_manifest_path)
        assert armory.get_current_manifest() == current_manifest_path
    
    def test_weapon_base_archetype(self):
        weapon_base_info = WeaponBaseArchetype()
        POWER_WEAPON = constants.WeaponBase(4)
        SWORD = constants.WeaponBase(54)
        weapon_base_info.set_field(POWER_WEAPON)
        weapon_base_info.set_field(SWORD)
        assert weapon_base_info.weapon_class == POWER_WEAPON
        assert weapon_base_info.weapon_type == SWORD