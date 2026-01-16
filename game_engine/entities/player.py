import time
import math
from typing import List, Tuple
from game_engine.entities import DynamicEntity
from game_engine.entities import Bomb, BombType
from dataclasses import dataclass, field


@dataclass
class Player(DynamicEntity):
    inventory: List[Tuple[BombType, int]] = field(default_factory=lambda: [])
    selected = 0

    def _test_inventory(self):
        self.inventory.append((BombType.BIG_BOMB, 100))

    def plant_bomb(self) -> Bomb:
        selected_bomb_type, bomb_count = self.inventory[self.selected]

        bomb = Bomb(
            x=math.floor(self.x),
            y=math.floor(self.y),
            bomb_type=selected_bomb_type,
            placed_at=time.time(),
            owner_id=self.id,
        )
        new_count = bomb_count - 1

        if new_count <= 0:
            del self.inventory[self.selected]

        return bomb
