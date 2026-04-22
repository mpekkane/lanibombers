"""
Shop item type definitions for lanibombers.
Unified abstraction over BombType and PowerupType for the shop system.
"""

from enum import Enum
from typing import Union

from common.bomb_dictionary import BombType


class PowerupType(Enum):
    KEVLAR_VEST = "kevlar_vest"
    SUPER_DRILL = "super_drill"
    SMALL_PICK = "small_pick"
    BIG_PICK = "big_pick"
    DRILL = "drill"


# Union of purchasable types
ItemType = Union[BombType, PowerupType]

# Special sentinel for the ready button (not a real item)
READY_ITEM = "ready"

# Display names for powerups
POWERUP_TYPE_NAMES: dict[PowerupType, str] = {
    PowerupType.KEVLAR_VEST: "Kevlar Vest",
    PowerupType.SUPER_DRILL: "Super Drill",
    PowerupType.SMALL_PICK: "Small Pick",
    PowerupType.BIG_PICK: "Big Pick",
    PowerupType.DRILL: "Drill",
}

# Icon sprite names for powerups (without _icon suffix)
POWERUP_TYPE_TO_ICON: dict[PowerupType, str] = {
    PowerupType.KEVLAR_VEST: "kevlar_vest",
    PowerupType.SUPER_DRILL: "super_drill",
    PowerupType.SMALL_PICK: "small_pick",
    PowerupType.BIG_PICK: "big_pick",
    PowerupType.DRILL: "drill",
}

# Ready button icon
READY_ICON = "ready"


def get_item_icon(item: ItemType | str) -> str | None:
    """Get icon sprite name for any shop item (BombType, PowerupType, or READY_ITEM)."""
    from common.bomb_dictionary import BOMB_TYPE_TO_ICON
    if isinstance(item, BombType):
        return BOMB_TYPE_TO_ICON.get(item)
    elif isinstance(item, PowerupType):
        return POWERUP_TYPE_TO_ICON.get(item)
    elif item == READY_ITEM:
        return READY_ICON
    return None


def get_item_name(item: ItemType | str) -> str | None:
    """Get display name for any shop item."""
    from common.bomb_dictionary import BOMB_TYPE_NAMES
    if isinstance(item, BombType):
        return BOMB_TYPE_NAMES.get(item)
    elif isinstance(item, PowerupType):
        return POWERUP_TYPE_NAMES.get(item)
    elif item == READY_ITEM:
        return "Ready"
    return None
