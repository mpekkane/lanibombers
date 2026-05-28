from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
import random

from game_engine.agent_state import Action
from game_engine.render_state import RenderState
from game_engine.entities.dynamic_entity import DynamicEntity
from game_engine.entities.player import Player
from game_engine.entities.tile import Tile, TileType
import numpy as np


class MonsterAI(ABC):
    """Abstract base class for monster AI behavior."""

    visibility_radius: float

    @abstractmethod
    def think(
        self, state: RenderState, state_updated: bool, own_entity: DynamicEntity
    ) -> Optional[Action]:
        """Decide the next action based on current game state.

        Args:
            state: The latest game render state.
            state_updated: True if the state changed since the last think() call.

        Returns an Action to execute, or None to do nothing this tick.
        """
        ...

    ################
    # BEHAVIORS
    ################

    def random_behavior(self, threshold: float) -> Optional[Action]:
        r = random.random()
        if r > threshold:
            return random.choice(list(Action))
        else:
            return None

    def target_seeking_behavior(
        self, state: RenderState, own_entity: DynamicEntity, target: DynamicEntity
    ):
        occupancy = self.get_occupancy(state, own_entity)

        r = int(self.visibility_radius)
        cx, cy = r, r

        dx = int(target.x) - int(own_entity.x)
        dy = int(target.y) - int(own_entity.y)

        candidates: list[tuple[int, Action, int, int]] = []

        if dx < 0:
            candidates.append((abs(dx), Action.LEFT, cx - 1, cy))
        elif dx > 0:
            candidates.append((abs(dx), Action.RIGHT, cx + 1, cy))

        if dy > 0:
            candidates.append((abs(dy), Action.DOWN, cx, cy + 1))
        elif dy < 0:
            candidates.append((abs(dy), Action.UP, cx, cy - 1))

        candidates.sort(reverse=True, key=lambda x: x[0])

        for _, action, nx, ny in candidates:
            if 0 <= ny < occupancy.shape[0] and 0 <= nx < occupancy.shape[1]:
                if occupancy[ny, nx]:
                    return action

        return None

    ################
    # BASE SKILLS
    ################

    def get_visible_players(
        self, state: RenderState, own_entity: DynamicEntity
    ) -> List[Tuple[Player, float]]:
        """Get players in range"""
        in_range = []
        for player in state.players:
            distance = self.manhattan(player, own_entity)
            if distance <= self.visibility_radius:
                in_range.append((player, distance))

        if len(in_range) > 0:
            dists = np.array(in_range)[:, 1]
            indices = np.argsort(dists)
            in_range = list(np.array(in_range)[indices])
        return in_range

    def get_occupancy(self, state: RenderState, own_entity: DynamicEntity) -> np.ndarray:
        """Get occupancy of cells in visible range"""
        r = int(self.visibility_radius)
        diameter = 2 * r + 1

        x = int(own_entity.x)
        y = int(own_entity.y)

        # Desired world-space bounds around entity, inclusive
        wanted_min_x = x - r
        wanted_max_x = x + r + 1
        wanted_min_y = y - r
        wanted_max_y = y + r + 1

        # Clamped map-space bounds
        min_x = max(wanted_min_x, 0)
        max_x = min(wanted_max_x, state.width)
        min_y = max(wanted_min_y, 0)
        max_y = min(wanted_max_y, state.height)

        submap = state.tilemap[min_y:max_y, min_x:max_x]

        updated_occupancy = np.array(
            [
                [MonsterAI.can_move_through(Tile.visual_id_to_type(int(cell))) for cell in row]
                for row in submap
            ],
            dtype=bool,
        )

        # Full fixed-size occupancy map, padded with False
        occupancy = np.zeros((diameter, diameter), dtype=bool)

        # Where the clamped submap lands in the fixed-size view
        dst_y0 = min_y - wanted_min_y
        dst_x0 = min_x - wanted_min_x

        h, w = updated_occupancy.shape

        occupancy[
            dst_y0 : dst_y0 + h,
            dst_x0 : dst_x0 + w,
        ] = updated_occupancy

        return occupancy

    ################
    # PROPERTIES
    ################

    @staticmethod
    def manhattan(a: DynamicEntity, b: DynamicEntity) -> float:
        return abs(a.x - b.x) + abs(a.y - b.y)

    @staticmethod
    def can_move_through(tiletype: TileType) -> bool:
        if tiletype == TileType.EMPTY:
            return True
        elif tiletype == TileType.BEDROCK:
            return False
        elif tiletype == TileType.DIRT:
            return False
        elif tiletype == TileType.CONCRETE:
            return False
        elif tiletype == TileType.URETHANE:
            return False
        elif tiletype == TileType.BIOSLIME:
            return True
        elif tiletype == TileType.C4:
            return False
        elif tiletype == TileType.BOULDER:
            return True
        elif tiletype == TileType.BRICKS:
            return False
        elif tiletype == TileType.SWITCH:
            return False
        elif tiletype == TileType.SECURITY_DOOR:
            return False
        elif tiletype == TileType.TUNNEL:
            return True
        else:
            raise ValueError("Invalid tile type")
