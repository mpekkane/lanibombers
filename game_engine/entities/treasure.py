from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

from game_engine.entities.pickup import Pickup, PickupType
from cfg.tile_dictionary import (
    GOLD_SHIELD_ID,
    GOLD_EGG_ID,
    GOLD_COINS_ID,
    GOLD_BRACELET_ID,
    GOLD_BAR_ID,
    GOLD_CROSS_ID,
    GOLD_SCEPTRE_ID,
    GOLD_RUBY_ID,
    GOLD_CROWN_ID,
)


class TreasureType(Enum):
    GOLD_SHIELD = 'gold_shield'
    GOLD_EGG = 'gold_egg'
    GOLD_COINS = 'gold_coins'
    GOLD_BRACELET = 'gold_bracelet'
    GOLD_BAR = 'gold_bar'
    GOLD_CROSS = 'gold_cross'
    GOLD_SCEPTRE = 'gold_sceptre'
    GOLD_RUBY = 'gold_ruby'
    GOLD_CROWN = 'gold_crown'


# Point values for each treasure type
TREASURE_VALUES = {
    TreasureType.GOLD_CROWN: 100,
    TreasureType.GOLD_RUBY: 65,
    TreasureType.GOLD_SCEPTRE: 50,
    TreasureType.GOLD_CROSS: 35,
    TreasureType.GOLD_BAR: 30,
    TreasureType.GOLD_EGG: 25,
    TreasureType.GOLD_COINS: 15,
    TreasureType.GOLD_SHIELD: 15,
    TreasureType.GOLD_BRACELET: 10,
}


@dataclass
class Treasure(Pickup):
    """Gold treasure item that can be picked up for points."""
    treasure_type: TreasureType = TreasureType.GOLD_COINS

    @staticmethod
    def create(x: int, y: int, treasure_type: TreasureType) -> Treasure:
        if treasure_type == TreasureType.GOLD_CROWN:
            return Treasure(x=x, y=y, treasure_type=TreasureType.GOLD_CROWN, visual_id=GOLD_CROWN_ID)
        elif treasure_type == TreasureType.GOLD_RUBY:
            return Treasure(x=x, y=y, treasure_type=TreasureType.GOLD_RUBY, visual_id=GOLD_RUBY_ID)
        elif treasure_type == TreasureType.GOLD_SCEPTRE:
            return Treasure(x=x, y=y, treasure_type=TreasureType.GOLD_SCEPTRE, visual_id=GOLD_SCEPTRE_ID)
        elif treasure_type == TreasureType.GOLD_CROSS:
            return Treasure(x=x, y=y, treasure_type=TreasureType.GOLD_CROSS, visual_id=GOLD_CROSS_ID)
        elif treasure_type == TreasureType.GOLD_BAR:
            return Treasure(x=x, y=y, treasure_type=TreasureType.GOLD_BAR, visual_id=GOLD_BAR_ID)
        elif treasure_type == TreasureType.GOLD_EGG:
            return Treasure(x=x, y=y, treasure_type=TreasureType.GOLD_EGG, visual_id=GOLD_EGG_ID)
        elif treasure_type == TreasureType.GOLD_COINS:
            return Treasure(x=x, y=y, treasure_type=TreasureType.GOLD_COINS, visual_id=GOLD_COINS_ID)
        elif treasure_type == TreasureType.GOLD_SHIELD:
            return Treasure(x=x, y=y, treasure_type=TreasureType.GOLD_SHIELD, visual_id=GOLD_SHIELD_ID)
        elif treasure_type == TreasureType.GOLD_BRACELET:
            return Treasure(x=x, y=y, treasure_type=TreasureType.GOLD_BRACELET, visual_id=GOLD_BRACELET_ID)

    def __post_init__(self):
        self.pickup_type = PickupType.TREASURE
        if self.value == 0:
            self.value = TREASURE_VALUES.get(self.treasure_type, 100)
