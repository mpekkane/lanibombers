from __future__ import annotations

import random
from typing import List, Tuple, Dict
from game_engine.clock import Clock
from game_engine.entities import DynamicEntity
from game_engine.entities import Bomb, BombType
from game_engine.entities import Tool, ToolType, Treasure
from common.bomb_dictionary import BOMB_TYPES
from dataclasses import dataclass, field
from game_engine.utils import xy_to_tile
from common.logger import get_logger
from common.player_constants import BASE_DIGGING_POWER
import struct


@dataclass
class Player(DynamicEntity):
    inventory: List[Tuple[BombType, int]] = field(default_factory=lambda: [])
    tools: Dict[ToolType, int] = field(default_factory=lambda: {})
    selected: int = 0
    dig_power: int = BASE_DIGGING_POWER
    selected_type: BombType = BombType.SMALL_BOMB

    byte_size = None
    _player_format = struct.Struct("!BBBBIBBB")

    def to_bytes(self) -> bytes:
        name = self.name.encode("utf-8")
        if len(self.name) > 20 or len(name) > 40:
            raise ValueError("Player name must fit in 20 characters and 40 UTF-8 bytes")
        for label, value, bits in (
            ("money", self.money, 14), ("dig power", self.dig_power, 7),
            ("selected inventory index", self.selected, 5),
        ):
            if not 0 <= value < 1 << bits:
                raise ValueError(f"Player {label} must fit in {bits} bits")
        if len(self.inventory) > 32:
            raise ValueError("Player inventory cannot exceed 32 entries")
        stats = (self.money | self.dig_power << 14 | self.selected << 21
                 | int(BombType(self.selected_type)) << 26)
        inventory = bytearray()
        for bomb_type, count in self.inventory:
            inventory.extend(bytes((int(BombType(bomb_type)), count)))
        tools = bytearray()
        for tool_type, count in self.tools.items():
            if not 0 <= count < 32:
                raise ValueError("Tool count must fit in 5 bits")
            tools.append(int(ToolType(tool_type)) << 5 | count)
        header = self._player_format.pack(
            self.sprite_id, *self.color, stats, len(name), len(self.inventory), len(tools)
        )
        return DynamicEntity.to_bytes(self) + header + name + inventory + tools

    @staticmethod
    def from_bytes(buffer: bytes) -> Player:
        base_size = DynamicEntity.byte_size
        base = DynamicEntity.from_bytes(buffer[:base_size])
        start = base_size + Player._player_format.size
        sprite, r, g, b, stats, name_size, inventory_size, tools_size = (
            Player._player_format.unpack(buffer[base_size:start])
        )
        if inventory_size > 32 or name_size > 40 or tools_size > len(ToolType):
            raise ValueError("Invalid player record counts")
        if len(buffer) != start + name_size + inventory_size * 2 + tools_size:
            raise ValueError("Invalid player record size")
        name = buffer[start:start + name_size].decode("utf-8")
        if len(name) > 20 or stats >> 31:
            raise ValueError("Invalid player name or reserved stats bits")
        start += name_size
        inventory = []
        for _ in range(inventory_size):
            inventory.append((BombType(buffer[start]), buffer[start + 1]))
            start += 2
        tools = {}
        for packed in buffer[start:]:
            tools[ToolType(packed >> 5)] = packed & 31
        return Player(
            id=base.id, x=base.x, y=base.y, speed=base.speed, health=base.health,
            direction=base.direction, entity_type=base.entity_type, state=base.state,
            name=name, sprite_id=sprite, color=(r, g, b), money=stats & 16383,
            dig_power=(stats >> 14) & 127, selected=(stats >> 21) & 31,
            selected_type=BombType((stats >> 26) & 31),
            inventory=inventory, tools=tools,
        )

    def test_inventory(self) -> None:
        self.inventory.append((BombType.SMALL_BOMB, 50))
        self.inventory.append((BombType.BIG_BOMB, 50))
        self.inventory.append((BombType.C4, 10))
        self.inventory.append((BombType.URETHANE, 10))
        self.inventory.append((BombType.LANDMINE, 20))
        self.inventory.append((BombType.SMALL_REMOTE, 20))
        self.inventory.append((BombType.BIG_REMOTE, 20))
        self.inventory.append((BombType.DYNAMITE, 20))
        self.inventory.append((BombType.NUKE, 5))
        self.inventory.append((BombType.SMALL_CROSS_BOMB, 10))
        self.inventory.append((BombType.BIG_CROSS_BOMB, 5))
        self.inventory.append((BombType.GRASSHOPPER, 10))
        self.inventory.append((BombType.FLAME_BARREL, 10))
        self.inventory.append((BombType.CRACKER_BARREL, 10))
        self.inventory.append((BombType.DIGGER_BOMB, 10))
        self.inventory.append((BombType.BIOSLIME, 20))
        self.inventory.append((BombType.METAL_PLATE, 20))
        self.inventory.append((BombType.FLAMETHROWER, 30))
        self.inventory.append((BombType.FIRE_EXTINGUISHER, 30))
        self.inventory.append((BombType.CLONE, 10))
        self.inventory.append((BombType.TELEPORT, 10))
        self.inventory.append((BombType.GRENADE, 15))

    def initialize_player(self, money: int) -> None:
        pass

    def select(self, target_type: BombType) -> None:
        for i, (bomb_type, _count) in enumerate(self.inventory):
            if bomb_type == target_type:
                self.set_selected(i)

        self.remove_empty_weapons()

    def remove_empty_weapons(self) -> None:
        for i, (weapon, count) in enumerate(self.inventory):
            if count <= 0:
                del self.inventory[i]

                if self.selected < i:
                    self.selected -= 1

                # Adjust selected index if it's now out of bounds
                if self.selected >= len(self.inventory) and self.inventory:
                    self.set_selected(len(self.inventory) - 1)

    def update_selected(self, change: int) -> None:
        self.selected += change
        self.set_selected_bomb_type()

    def set_selected(self, val: int) -> None:
        self.selected = val
        self.set_selected_bomb_type()

    def set_selected_bomb_type(self) -> None:
        selected_bomb_type, bomb_count = self.inventory[self.selected]
        self.selected_type = selected_bomb_type

    def plant_bomb(self) -> Bomb | None:
        if not self.inventory:
            return None

        # Ensure selected index is valid
        if self.selected >= len(self.inventory):
            self.set_selected(len(self.inventory) - 1)

        selected_bomb_type, bomb_count = self.inventory[self.selected]
        vx, vy = xy_to_tile(self.x, self.y)

        if bomb_count <= 0:
            return None

        bomb = Bomb(
            x=vx,
            y=vy,
            bomb_type=selected_bomb_type,
            placed_at=Clock.now(),
            owner_id=self.id,
            direction=self.direction,  # Pass player's direction for directed weapons
        )
        # Inventory is decremented on the engine thread after the placement
        # has been accepted (tile-occupancy check passes) — see
        # GameEngine.process_inputs.
        return bomb

    def pickup_tool(self, tool: Tool) -> None:
        log = get_logger()
        if tool.tool_type not in self.tools:
            self.tools[tool.tool_type] = 1
        else:
            self.tools[tool.tool_type] += 1

        # update dig power
        self.dig_power += tool.dig_power

        # heal with medpack
        if tool.tool_type == ToolType.MEDPACK:
            self.health = max(100, self.health)

        # random weapons from a crate
        if tool.tool_type == ToolType.CRATE:
            got_type = random.choice(BOMB_TYPES)
            got_amount = random.randint(0, 10)
            self.inventory.append((got_type, got_amount))
            log.info(f"Picked up {got_amount} {got_type}")

        log.info(f"Picked up {tool.tool_type}")
        log.info(f"Tools: {self.tools}")
        log.info(f"Health: {self.health}")

    def pickup_treasure(self, treasure: Treasure) -> None:
        self.add_money(treasure.value)

        log = get_logger()
        log.info(f"Picked up {treasure.treasure_type}")
        log.info(f"Money: {self.money}")

    def get_dig_power(self) -> int:
        return self.dig_power
