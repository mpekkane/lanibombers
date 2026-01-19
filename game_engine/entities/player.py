from typing import List, Tuple, Dict
from game_engine.clock import Clock
from game_engine.entities import DynamicEntity
from game_engine.entities import Bomb, BombType
from game_engine.entities import Tool, ToolType, Treasure
from dataclasses import dataclass, field
from game_engine.utils import xy_to_tile


@dataclass
class Player(DynamicEntity):
    inventory: List[Tuple[BombType, int]] = field(default_factory=lambda: [])
    tools: Dict[ToolType, int] = field(default_factory=lambda: {})
    selected = 0

    def _test_inventory(self) -> None:
        self.inventory.append((BombType.SMALL_BOMB, 50))
        self.inventory.append((BombType.BIG_BOMB, 50))
        self.inventory.append((BombType.C4, 10))
        self.inventory.append((BombType.LANDMINE, 20))
        self.inventory.append((BombType.REMOTE, 20))
        self.inventory.append((BombType.DYNAMITE, 20))
        self.inventory.append((BombType.NUKE, 5))
        self.inventory.append((BombType.SMALL_CROSS_BOMB, 10))
        self.inventory.append((BombType.BIG_CROSS_BOMB, 5))

    def choose(self) -> None:
        if not self.inventory:
            return

        self.selected += 1
        if self.selected >= len(self.inventory):
            self.selected = 0

        # FIXME: debug print
        selected_bomb_type, bomb_count = self.inventory[self.selected]
        print(selected_bomb_type, bomb_count)

    def plant_bomb(self) -> Bomb | None:
        if not self.inventory:
            return None

        # Ensure selected index is valid
        if self.selected >= len(self.inventory):
            self.selected = len(self.inventory) - 1

        selected_bomb_type, bomb_count = self.inventory[self.selected]
        vx, vy = xy_to_tile(self.x, self.y)

        bomb = Bomb(
            x=vx,
            y=vy,
            bomb_type=selected_bomb_type,
            placed_at=Clock.now(),
            owner_id=self.id,
        )
        new_count = bomb_count - 1

        if new_count <= 0:
            del self.inventory[self.selected]
            # Adjust selected index if it's now out of bounds
            if self.selected >= len(self.inventory) and self.inventory:
                self.selected = len(self.inventory) - 1

        else:
            self.inventory[self.selected] = selected_bomb_type, new_count

        return bomb

    def pickup_tool(self, tool: Tool) -> None:
        if tool.tool_type not in self.tools:
            self.tools[tool.tool_type] = 1
        else:
            self.tools[tool.tool_type] += 1
        print(f"Picked up {tool.tool_type}")
        print(f"Tools: {self.tools}")

    def pickup_treasure(self, treasure: Treasure) -> None:
        self.add_money(treasure.value)
        print(f"Picked up {treasure.treasure_type}")
        print(f"Money: {self.money}")

    def get_dig_power(self) -> int:
        default = 10
        #TODO: add tools
        return default
