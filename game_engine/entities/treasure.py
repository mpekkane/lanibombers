from dataclasses import dataclass
from enum import Enum

from game_engine.entities.pickup import Pickup, PickupType


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

    def __post_init__(self):
        self.pickup_type = PickupType.TREASURE
        if self.value == 0:
            self.value = TREASURE_VALUES.get(self.treasure_type, 100)
