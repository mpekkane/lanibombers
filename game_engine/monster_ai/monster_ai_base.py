from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, List, Tuple, Callable
import random
from collections import deque
import numpy as np

from game_engine.agent_state import Action
from game_engine.render_state import RenderState
from game_engine.entities.dynamic_entity import DynamicEntity
from game_engine.entities.player import Player
from game_engine.entities.tile import Tile, TileType
from enum import Enum
from dataclasses import dataclass

GridPos = tuple[int, int]


@dataclass
class PathMap:
    reachable: np.ndarray
    distance: np.ndarray
    parent: dict[GridPos, GridPos]
    start: GridPos

    def path_to(self, goal_x: int, goal_y: int) -> Optional[list[GridPos]]:
        goal = (goal_x, goal_y)

        if not self.reachable[goal_y, goal_x]:
            return None

        path = [goal]

        while path[-1] != self.start:
            path.append(self.parent[path[-1]])

        path.reverse()
        return path


class MonsterSense(Enum):
    SMELL = "smell"
    VISION = "vision"


class MonsterAI(ABC):
    """Abstract base class for monster AI behavior."""

    smell_radius: float
    view_radius: float
    occupancy: Optional[np.ndarray] = None
    fov: Optional[np.ndarray] = None
    fov_cache_key: Optional[Tuple[int, int]] = None
    path_map: Optional[PathMap] = None
    path_cache_key: Optional[Tuple[int, int]] = None

    @abstractmethod
    def think(
        self, state: RenderState, state_updated: bool, own_entity: DynamicEntity
    ) -> Optional[Action]:
        """Decide the next action based on current game state.

        Args:
            state: The latest game render state.
            state_updated: True if the state changed since the last think() call.
            own_entity: The monster/entity controlled by this AI.

        Returns:
            An Action to execute, or None to do nothing this tick.
        """
        ...

    ################
    # BEHAVIORS
    ################

    def random_behavior(self, threshold: float) -> Optional[Action]:
        r = random.random()
        if r > threshold:
            return random.choice(
                [
                    Action.LEFT,
                    Action.RIGHT,
                    Action.UP,
                    Action.DOWN,
                ]
            )
        else:
            return None

    def target_seeking_behavior(
        self,
        state: RenderState,
        own_entity: DynamicEntity,
        target: DynamicEntity,
    ) -> Optional[Action]:
        """Move greedily toward target, avoiding blocking cells.

        Uses full-map occupancy, so all coordinates are global map coordinates.

        Coordinate convention:
            occupancy[y, x]
            state.tilemap[y, x]
            entity.x -> x
            entity.y -> y
        """
        # If we have a smell trail
        if self.path_map is not None:
            return self.follow_path(target, own_entity)

        # If we don't, we have to go visually
        occupancy = self.get_occupancy(state, MonsterAI.can_see_through)
        height, width = occupancy.shape

        x = int(own_entity.x)
        y = int(own_entity.y)

        target_x = int(target.x)
        target_y = int(target.y)

        dx = target_x - x
        dy = target_y - y

        candidates: list[tuple[int, Action, int, int]] = []

        if dx < 0:
            candidates.append((abs(dx), Action.LEFT, x - 1, y))
        elif dx > 0:
            candidates.append((abs(dx), Action.RIGHT, x + 1, y))

        if dy > 0:
            candidates.append((abs(dy), Action.DOWN, x, y + 1))
        elif dy < 0:
            candidates.append((abs(dy), Action.UP, x, y - 1))

        candidates.sort(reverse=True, key=lambda item: item[0])

        for _, action, nx, ny in candidates:
            if 0 <= nx < width and 0 <= ny < height and occupancy[ny, nx]:
                return action

        return None

    ################
    # SENSES
    ################

    def smell(
        self, state: RenderState, own_entity: DynamicEntity
    ) -> List[Tuple[Player, float]]:
        """Get players within smell radius.

        Smell currently uses pure Manhattan distance and does not check blockers.
        """
        in_range: List[Tuple[Player, float]] = []

        path_map = self._get_path_sense(state, own_entity, MonsterSense.SMELL)

        for player in state.players:
            distance = self.manhattan(player, own_entity)
            if (
                distance <= self.smell_radius
                and path_map.reachable[int(player.y), int(player.x)]
            ):
                in_range.append((player, distance))

        return MonsterAI._sort(in_range)

    def see(
        self, state: RenderState, own_entity: DynamicEntity
    ) -> List[Tuple[Player, float]]:
        """Get players visible by field-of-view.

        FOV is computed on the full map. Therefore player/entity coordinates
        can be used directly as array coordinates, with NumPy indexing [y, x].
        """
        visible: List[Tuple[Player, float]] = []

        fov = self._get_los_sense(state, own_entity, MonsterSense.VISION)

        height, width = fov.shape

        for player in state.players:
            px = int(player.x)
            py = int(player.y)

            if 0 <= px < width and 0 <= py < height and fov[py, px]:
                distance = self.manhattan(player, own_entity)
                visible.append((player, distance))

        return MonsterAI._sort(visible)

    def _get_los_sense(
        self,
        state: RenderState,
        own_entity: DynamicEntity,
        dominant_sense: MonsterSense,
    ) -> np.ndarray:
        discriminator = MonsterAI.get_discriminator_function(dominant_sense)
        occupancy = self.get_occupancy(state, discriminator)

        origin_x = int(own_entity.x)
        origin_y = int(own_entity.y)

        fov = self.compute_fov(
            occupancy=occupancy,
            origin_x=origin_x,
            origin_y=origin_y,
            radius=int(self.view_radius),
        )

        # print("=" * 80)
        # print("Get LOS sense")
        # print("occupancy")
        # self._print_occupancy(occupancy, own_entity)
        # print("-" * 40)
        # print("fov")
        # self._print_occupancy(fov, own_entity)

        return fov

    def _get_path_sense(
        self,
        state: RenderState,
        own_entity: DynamicEntity,
        dominant_sense: MonsterSense,
    ) -> PathMap:
        discriminator = MonsterAI.get_discriminator_function(dominant_sense)
        occupancy = self.get_occupancy(state, discriminator)

        origin_x = int(own_entity.x)
        origin_y = int(own_entity.y)

        path_map = self.compute_path_map(
            occupancy=occupancy,
            origin_x=origin_x,
            origin_y=origin_y,
            radius=int(self.view_radius),
        )

        # print("=" * 80)
        # print("Get path sense")
        # print("occupancy")
        # self._print_occupancy(occupancy, own_entity)
        # print("-" * 40)
        # print("reachable")
        # self._print_occupancy(path_map.reachable, own_entity)

        return path_map

    def fuse_senses(
        self, measurements: List[List[Tuple[Player, float]]]
    ) -> List[Tuple[Player, float]]:
        fuselist: List[Tuple[Player, float]] = []

        for m in measurements:
            fuselist += m

        return MonsterAI._sort(fuselist)

    @staticmethod
    def _sort(measurements: List[Tuple[Player, float]]) -> List[Tuple[Player, float]]:
        return sorted(measurements, key=lambda item: item[1])

    ################
    # HELPERS
    ################

    def follow_path(self, target: DynamicEntity, own_entity: DynamicEntity):
        assert self.path_map is not None
        path = self.path_map.path_to(
            goal_x=int(target.x),
            goal_y=int(target.y),
        )
        if path is None or len(path) < 2:
            return None

        x = int(own_entity.x)
        y = int(own_entity.y)

        next_x, next_y = path[1]

        if next_x < x:
            return Action.LEFT
        if next_x > x:
            return Action.RIGHT
        if next_y < y:
            return Action.UP
        if next_y > y:
            return Action.DOWN

        return None

    @staticmethod
    def get_discriminator_function(sense: MonsterSense) -> Callable[[TileType], bool]:
        if sense == MonsterSense.VISION:
            return MonsterAI.can_see_through
        elif sense == MonsterSense.SMELL:
            return MonsterAI.can_smell_through
        else:
            raise ValueError("Unknown monster sense")

    def _print_occupancy(self, occupancy: np.ndarray, entity: DynamicEntity) -> None:
        rows = []

        for y in range(occupancy.shape[0]):
            row = ""

            for x in range(occupancy.shape[1]):

                if int(entity.x) == x and int(entity.y) == y:
                    row += "X"
                else:
                    row += "1" if occupancy[y, x] else "0"

            rows.append(row)

        print("\n".join(rows))

    def get_occupancy(
        self, state: RenderState, discriminator_function: Callable[[TileType], bool]
    ) -> np.ndarray:
        """Get full-map occupancy.

        The returned occupancy has the same shape as state.tilemap:

            occupancy.shape == state.tilemap.shape

        Coordinate convention:

            occupancy[y, x] == True   means transparent / smell-through
            occupancy[y, x] == False  means blocking

        This intentionally does not crop around the monster. Keeping this full-map
        shaped avoids local/global coordinate confusion in smell/visibility code.
        """
        if self.occupancy is None:
            self.occupancy = np.array(
                [
                    [
                        discriminator_function(Tile.visual_id_to_type(int(cell)))
                        for cell in row
                    ]
                    for row in state.tilemap
                ],
                dtype=bool,
            )
        return self.occupancy

    @staticmethod
    def get_neighbors(
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> list[tuple[int, int]]:
        candidates = [
            (x - 1, y),  # left
            (x + 1, y),  # right
            (x, y - 1),  # up
            (x, y + 1),  # down
        ]

        return [
            (nx, ny) for nx, ny in candidates if 0 <= nx < width and 0 <= ny < height
        ]

    def compute_path_map(
        self,
        occupancy: np.ndarray,
        origin_x: int,
        origin_y: int,
        radius: int,
        *,
        reveal_blocking_tiles: bool = False,
    ) -> PathMap:
        key = (origin_x, origin_y)
        if self.path_cache_key is not None and self.path_cache_key == key:
            assert self.path_map is not None
            return self.path_map

        height, width = occupancy.shape

        reachable = np.zeros_like(occupancy, dtype=bool)
        distance = np.full(occupancy.shape, fill_value=-1, dtype=int)
        parent: dict[GridPos, GridPos] = {}

        start = (origin_x, origin_y)

        if not (0 <= origin_x < width and 0 <= origin_y < height):
            return PathMap(reachable, distance, parent, start)

        if not occupancy[origin_y, origin_x]:
            return PathMap(reachable, distance, parent, start)

        radius = max(0, int(radius))

        queue: deque[GridPos] = deque([start])

        reachable[origin_y, origin_x] = True
        distance[origin_y, origin_x] = 0

        while queue:
            x, y = queue.popleft()
            d = distance[y, x]

            if d >= radius:
                continue

            for nx, ny in MonsterAI.get_neighbors(x, y, width, height):
                if distance[ny, nx] != -1:
                    continue

                if not occupancy[ny, nx]:
                    if reveal_blocking_tiles:
                        reachable[ny, nx] = True
                    continue

                reachable[ny, nx] = True
                distance[ny, nx] = d + 1
                parent[(nx, ny)] = (x, y)
                queue.append((nx, ny))

        path_map = PathMap(reachable, distance, parent, start)

        self.path_cache_key = key
        self.path_map = path_map
        return path_map

    def compute_fov(
        self,
        occupancy: np.ndarray,
        origin_x: int,
        origin_y: int,
        radius: int,
        *,
        reveal_blocking_tiles: bool = False,
    ) -> np.ndarray:
        """Compute recursive-shadowcasting field of view.

        Args:
            occupancy:
                Full-map boolean occupancy.

                occupancy[y, x] == True   means transparent / see-through.
                occupancy[y, x] == False  means blocking.

            origin_x:
                Global map x-coordinate of viewer.

            origin_y:
                Global map y-coordinate of viewer.

            radius:
                FOV radius in tiles.

            reveal_blocking_tiles:
                If True, blocking tiles themselves are visible, but block tiles
                behind them. If False, blocking tiles are not marked visible.

        Returns:
            Boolean array with same shape as occupancy.

            visible[y, x] == True means cell is visible.
        """
        key = (origin_x, origin_y)
        if self.fov_cache_key is not None and self.fov_cache_key == key:
            assert self.fov is not None
            return self.fov

        height, width = occupancy.shape
        visible = np.zeros_like(occupancy, dtype=bool)

        if not (0 <= origin_x < width and 0 <= origin_y < height):
            return visible

        radius = max(0, int(radius))
        radius_sq = radius * radius

        visible[origin_y, origin_x] = True

        def blocks_light(x: int, y: int) -> bool:
            if not (0 <= x < width and 0 <= y < height):
                return True

            return not bool(occupancy[y, x])

        def mark_visible(x: int, y: int) -> None:
            if 0 <= x < width and 0 <= y < height:
                visible[y, x] = True

        def cast_light(
            row: int,
            start_slope: float,
            end_slope: float,
            xx: int,
            xy: int,
            yx: int,
            yy: int,
        ) -> None:
            if start_slope < end_slope:
                return

            for distance in range(row, radius + 1):
                blocked = False
                new_start_slope = start_slope

                # This matches the standard recursive-shadowcasting pattern:
                # initialize one step before the row and increment at top of loop.
                dx = -distance - 1
                dy = -distance

                while dx <= 0:
                    dx += 1

                    x = origin_x + dx * xx + dy * xy
                    y = origin_y + dx * yx + dy * yy

                    left_slope = (dx - 0.5) / (dy + 0.5)
                    right_slope = (dx + 0.5) / (dy - 0.5)

                    if start_slope < right_slope:
                        continue

                    if end_slope > left_slope:
                        break

                    in_radius = dx * dx + dy * dy <= radius_sq

                    if in_radius:
                        if reveal_blocking_tiles or not blocks_light(x, y):
                            mark_visible(x, y)

                    if blocked:
                        if blocks_light(x, y):
                            new_start_slope = right_slope
                            continue

                        blocked = False
                        start_slope = new_start_slope

                    else:
                        if blocks_light(x, y) and distance < radius:
                            blocked = True

                            cast_light(
                                row=distance + 1,
                                start_slope=start_slope,
                                end_slope=left_slope,
                                xx=xx,
                                xy=xy,
                                yx=yx,
                                yy=yy,
                            )

                            new_start_slope = right_slope

                if blocked:
                    break

        # Octant transforms.
        #
        # These are the standard recursive-shadowcasting multipliers, written as
        # tuples of:
        #
        #     xx, xy, yx, yy
        #
        # Coordinate transform:
        #
        #     x = origin_x + dx * xx + dy * xy
        #     y = origin_y + dx * yx + dy * yy
        transforms = [
            (1, 0, 0, 1),
            (0, 1, 1, 0),
            (0, -1, 1, 0),
            (-1, 0, 0, 1),
            (-1, 0, 0, -1),
            (0, -1, -1, 0),
            (0, 1, -1, 0),
            (1, 0, 0, -1),
        ]

        for xx, xy, yx, yy in transforms:
            cast_light(
                row=1,
                start_slope=1.0,
                end_slope=0.0,
                xx=xx,
                xy=xy,
                yx=yx,
                yy=yy,
            )

        self.fov_cache_key = key
        self.fov = visible
        return visible

    ################
    # PROPERTIES
    ################

    @staticmethod
    def manhattan(a: DynamicEntity, b: DynamicEntity) -> float:
        return abs(a.x - b.x) + abs(a.y - b.y)

    @staticmethod
    def can_smell_through(tiletype: TileType) -> bool:
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

    @staticmethod
    def can_see_through(tiletype: TileType) -> bool:
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
            return False
        elif tiletype == TileType.C4:
            return False
        elif tiletype == TileType.BOULDER:
            return False
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
