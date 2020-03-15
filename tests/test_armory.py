import pytest
import sys
import os
from gunsmith_bot.armory import Armory

class TestArmory():
    def test_update_current_manifest(self):
        current_manifest_path = "/path/to/file"
        armory = Armory(current_manifest_path)
        assert armory.get_current_manifest() == current_manifest_path

        new_manifest_path = "/new/path/to/file"
        armory.update_current_manifest_path(new_manifest_path)
        assert armory.get_current_manifest() == new_manifest_path