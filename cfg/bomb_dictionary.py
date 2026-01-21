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

    def is_timed(self) -> bool:
        return self != BombType.LANDMINE and self != BombType.REMOTE


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
}

# Available bomb types in default order (excludes internal types like C4_TILE)
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
}

# Hotkey assignment order for new items (1234567890, qwertyuiop, asdfghjkl, zxcvbnm)
HOTKEY_ORDER = "1234567890qwertyuiopasdfghjklzxcvbnm"
