from dataclasses import dataclass
from enum import Enum

@dataclass
class SocketCategoryHash:
    # Query DestinySocketCategoryDefinition with socketCategoryHash
    INTRINSICS: int = 3956125808
    WEAPON_PERKS: int = 4241085061

class PlugCategoryHash(Enum):
    Intrinsics = 3956125808
    Stocks = 577918720
    Perks = 7906839
    Frames = 7906839
    Barrels = 2833605196
    Bowstrings = 3809303875
    Magazines = 1806783418
    Projectiles = 2718120384
    Magazines_Gl = 2718120384
    Blades = 1041766312
    Grips = 3962145884
    Batteries = 1757026848
    Guards = 683359327
    Scopes = 2619833294
    Arrows = 1257608559
    Launchers = 1202604782
    Tubes = 1202604782

    @classmethod
    def is_valid(self, category_name):
        return category_name in self.__members__


class WeaponBase(Enum):
    WEAPON = 1
    KINETIC = 2
    ENERGY = 3
    POWER = 4
    AUTO_RIFLE = 5
    HAND_CANNON = 6
    PULSE_RIFLE = 7
    SCOUT_RIFLE = 8
    FUSION_RIFLE = 9
    SNIPER_RIFLE = 10
    SHOTGUN = 11
    MACHINE_GUN = 12
    ROCKET_LAUNCHER = 13
    SIDEARM = 14
    SWORD = 54
    GRENADE_LAUNCHERS = 153950757
    LINEAR_FUSION_RIFLES = 1504945536
    TRACE_RIFLES = 2489664120
    BOWS = 3317538576
    SUBMACHINE_GUNS = 3954685534

