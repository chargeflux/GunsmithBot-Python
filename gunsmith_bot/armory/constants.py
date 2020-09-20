from enum import Enum

BUNGIE_URL_ROOT = "https://www.bungie.net"

class SocketCategoryHash(Enum):
    INTRINSICS = 3956125808
    WEAPON_PERKS = 4241085061

class PlugCategoryHash(Enum):
    INTRINSICS = 1744546145
    STOCKS = 577918720
    PERKS = 7906839
    FRAMES = 7906839
    BARRELS = 2833605196
    BOWSTRINGS = 3809303875
    MAGAZINES = 1806783418
    PROJECTILES = 2718120384
    MAGAZINES_GL = 2718120384
    BLADES = 1041766312
    GRIPS = 3962145884
    BATTERIES = 1757026848
    GUARDS = 683359327
    SCOPES = 2619833294
    ARROWS = 1257608559
    LAUNCHERS = 1202604782
    TUBES = 1202604782
    DEFAULT = -1 # User defined

    @classmethod
    def is_valid(cls, category_name):
        return category_name in cls.__members__

    def __str__(self):
        return self.title()

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
    GRENADE_LAUNCHER = 153950757
    LINEAR_FUSION_RIFLE = 1504945536
    TRACE_RIFLE = 2489664120
    BOW = 3317538576
    SUBMACHINE_GUN = 3954685534
    DUMMY = 3109687656

class WeaponTierType(Enum):
    BASIC = 3340296461
    UNCOMMON = 2395677314
    RARE = 2127292149
    LEGENDARY = 4008398120
    EXOTIC = 2759499571

class DamageType(Enum):
    KINETIC = 1
    ARC = 2
    SOLAR = 3
    VOID = 4

class WeaponStats(Enum):
    ACCURACY = 1591432999
    AIM_ASSISTANCE = 1345609583
    AMMO_CAPACITY = 925767036 
    BLAST_RADIUS = 3614673599
    CHARGE_RATE = 3022301683
    CHARGE_TIME = 2961396640
    DRAW_TIME = 447667954
    GUARD_EFFICIENCY = 2762071195
    GUARD_ENDURANCE = 3736848092
    GUARD_RESISTANCE = 209426660
    HANDLING = 943549884
    IMPACT = 4043523819
    MAGAZINE = 3871231066
    RANGE = 1240592695
    RECOIL = 2715839340
    RELOAD_SPEED = 4188031367
    ROUNDS_PER_MINUTE = 4284893193
    STABILITY = 155624089
    SWING_SPEED = 2837207746
    VELOCITY = 2523465841
    ZOOM = 3555269338

StatOrder = {
    WeaponStats.IMPACT: 0,
    WeaponStats.ACCURACY: 1,
    WeaponStats.RANGE: 2,
    WeaponStats.BLAST_RADIUS: 3,
    WeaponStats.VELOCITY: 4,
    WeaponStats.STABILITY: 5,
    WeaponStats.HANDLING: 6,
    WeaponStats.RELOAD_SPEED: 7,
    WeaponStats.SWING_SPEED: 8,
    WeaponStats.CHARGE_RATE: 9,
    WeaponStats.GUARD_RESISTANCE: 10,
    WeaponStats.GUARD_EFFICIENCY: 11,
    WeaponStats.GUARD_ENDURANCE: 12,
    WeaponStats.AIM_ASSISTANCE: 13,
    WeaponStats.ZOOM: 14,
    WeaponStats.RECOIL: 15,
    WeaponStats.ROUNDS_PER_MINUTE: 16,
    WeaponStats.CHARGE_TIME: 17,
    WeaponStats.DRAW_TIME: 18,
    WeaponStats.AMMO_CAPACITY: 19,
    WeaponStats.MAGAZINE: 20
}
    
PlugCategoryTables = [
    "intrinsics",
    "stocks",
    "perks1",
    "perks2",
    "barrels",
    "bowstrings",
    "magazines",
    "projectiles",
    "blades",
    "grips",
    "batteries",
    "guards",
    "scopes",
    "arrows",
    "launchers"
]