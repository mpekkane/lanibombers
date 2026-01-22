"""
Bomb type definitions for lanibombers.
Central location for bomb types, names, and icon mappings.
"""

from enum import Enum
from game_engine.entities.explosion import ExplosionType


class BombType(Enum):
    BIG_BOMB = 'big_bomb'
    C4 = 'c4'
    C4_TILE = 'c4_tile'  # Internal: explosion from C4 tile chain reaction
    LANDMINE = 'landmine'
    REMOTE = 'remote'
    SMALL_BOMB = "small_bomb"
    URETHANE = "urethane"
    SMALL_CROSS_BOMB = "small_cross_bomb"
    BIG_CROSS_BOMB = "big_cross_bomb"
    DYNAMITE = "dynamite"
    NUKE = "nuke"
    GRASSHOPPER = "grasshopper"
    GRASSHOPPER_HOP = "grasshopper_hop"  # Internal: subsequent grasshopper explosions
    FLAME_BARREL = "flame_barrel"
    CRACKER_BARREL = "cracker_barrel"
    DIGGER_BOMB = "digger_bomb"

    def is_timed(self) -> bool:
        return self != BombType.LANDMINE and self != BombType.REMOTE and self != BombType.CRACKER_BARREL


# Bomb properties by type: (fuse_duration, explosion_type)
BOMB_PROPERTIES = {
    BombType.BIG_BOMB: (3.0, ExplosionType.MEDIUM),
    BombType.SMALL_BOMB: (2.0, ExplosionType.SMALL),
    BombType.C4: (4.0, ExplosionType.NONE),  # Flood fills with C4 tiles
    BombType.C4_TILE: (0.0, ExplosionType.MEDIUM),  # Instant explosion for chain reaction
    BombType.LANDMINE: (0.5, ExplosionType.SMALL),
    BombType.REMOTE: (-1.0, ExplosionType.MEDIUM),
    BombType.URETHANE: (4.0, ExplosionType.NONE),  # Flood fills with urethane tiles
    BombType.SMALL_CROSS_BOMB: (3.0, ExplosionType.SMALL_CROSS),
    BombType.BIG_CROSS_BOMB: (4.0, ExplosionType.BIG_CROSS),
    BombType.DYNAMITE: (3, ExplosionType.LARGE),
    BombType.NUKE: (6.0, ExplosionType.NUKE),
    BombType.GRASSHOPPER: (2.5, ExplosionType.SMALL),  # Initial explosion is small
    BombType.GRASSHOPPER_HOP: (0.0, ExplosionType.SMALL),  # Fuse set dynamically (1-4s random)
    BombType.FLAME_BARREL: (3.0, ExplosionType.NONE),  # Flood fills and damages tiles
    BombType.CRACKER_BARREL: (-1.0, ExplosionType.NONE),  # Triggered by damage, not timed
    BombType.DIGGER_BOMB: (3.0, ExplosionType.LARGE),  # Only damages bedrock tiles
}

# Available bomb types in default order (excludes internal types like C4_TILE, GRASSHOPPER_HOP)
BOMB_TYPES = [
    BombType.SMALL_BOMB,
    BombType.BIG_BOMB,
    BombType.DYNAMITE,
    BombType.C4,
    BombType.LANDMINE,
    BombType.REMOTE,
    BombType.URETHANE,
    BombType.SMALL_CROSS_BOMB,
    BombType.BIG_CROSS_BOMB,
    BombType.NUKE,
    BombType.GRASSHOPPER,
    BombType.FLAME_BARREL,
    BombType.CRACKER_BARREL,
    BombType.DIGGER_BOMB,
]

# Display names for bomb types
BOMB_TYPE_NAMES = {
    BombType.SMALL_BOMB: "Small Bomb",
    BombType.BIG_BOMB: "Big Bomb",
    BombType.DYNAMITE: "Dynamite",
    BombType.C4: "C4",
    BombType.LANDMINE: "Landmine",
    BombType.REMOTE: "Remote",
    BombType.URETHANE: "Urethane",
    BombType.SMALL_CROSS_BOMB: "Small Cross",
    BombType.BIG_CROSS_BOMB: "Big Cross",
    BombType.NUKE: "Nuke",
    BombType.GRASSHOPPER: "Grasshopper",
    BombType.FLAME_BARREL: "Flame Barrel",
    BombType.CRACKER_BARREL: "Cracker Barrel",
    BombType.DIGGER_BOMB: "Digger Bomb",
}

# Mapping from BombType to icon sprite name (without _icon suffix)
BOMB_TYPE_TO_ICON = {
    BombType.SMALL_BOMB: "small_bomb",
    BombType.BIG_BOMB: "big_bomb",
    BombType.DYNAMITE: "dynamite",
    BombType.C4: "c4",
    BombType.LANDMINE: "landmine",
    BombType.REMOTE: "small_remote",
    BombType.URETHANE: "urethane",
    BombType.SMALL_CROSS_BOMB: "small_crucifix",
    BombType.BIG_CROSS_BOMB: "big_crucifix",
    BombType.NUKE: "nuke",
    BombType.GRASSHOPPER: "grasshopper",
    BombType.FLAME_BARREL: "flame_barrel",
    BombType.CRACKER_BARREL: "cracker_barrel",
    BombType.DIGGER_BOMB: "digger_bomb",
}

# Reverse lookup: bomb type name -> BombType
BOMB_NAME_TO_TYPE = {name: bomb_type for bomb_type, name in BOMB_TYPE_NAMES.items()}

# Default hotkeys for weapons
DEFAULT_HOTKEYS = {
    BombType.SMALL_BOMB: "1",
    BombType.BIG_BOMB: "2",
    BombType.DYNAMITE: "3",
    BombType.C4: "4",
    BombType.LANDMINE: "5",
    BombType.REMOTE: "6",
    BombType.URETHANE: "7",
    BombType.SMALL_CROSS_BOMB: "8",
    BombType.BIG_CROSS_BOMB: "9",
    BombType.NUKE: "0",
    BombType.GRASSHOPPER: "q",
    BombType.FLAME_BARREL: "w",
    BombType.CRACKER_BARREL: "e",
    BombType.DIGGER_BOMB: "r",
}

# Hotkey assignment order for new items (1234567890, qwertyuiop, asdfghjkl, zxcvbnm)
HOTKEY_ORDER = "1234567890qwertyuiopasdfghjklzxcvbnm"

# Grasshopper bomb configuration
GRASSHOPPER_CONFIG = {
    'max_hops': 13,                    # Total number of explosions before stopping
    'max_hop_distance': 7,             # Maximum tiles to hop in x and y directions
    'fuse_min': 1.0,                   # Minimum fuse time for hops (seconds)
    'fuse_max': 4.0,                   # Maximum fuse time for hops (seconds)
    'first_hop_explosions': [          # Possible explosion types for first hop (equal chance)
        ExplosionType.SMALL,
        ExplosionType.MEDIUM,
    ],
    'shrink_chance': 1/3,              # Chance to shrink explosion size
    'stay_chance': 1/3,                # Chance to keep same explosion size
    'grow_chance': 1/3,                # Chance to grow explosion size
    'explosion_order': [               # Explosion sizes from smallest to largest
        ExplosionType.SMALL,
        ExplosionType.MEDIUM,
        ExplosionType.LARGE,
    ],
}

# Flame barrel bomb configuration
FLAME_BARREL_CONFIG = {
    'max_distance': 10,                # Maximum flood fill distance
    'damage': 50,                      # Damage applied to tiles in range
}

# Cracker barrel bomb configuration
CRACKER_BARREL_CONFIG = {
    'flood_fill_distance': 6,          # Flame barrel-like flood fill range
    'flood_fill_damage': 50,           # Damage applied to tiles in flood fill
    'scatter_explosions': 7,           # Number of random medium explosions
    'scatter_distance': 9,             # Max distance for scatter explosions
    'scatter_interval': 1.0 / 60.0,    # Time between scatter explosions (1/60 second)
}
