from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, List, Tuple, Callable
import random
from collections import deque
import numpy as np
from heapq import heappop, heappush

from game_engine.agent_state import Action
from game_engine.render_state import RenderState
from game_engine.entities.dynamic_entity import DynamicEntity, Direction
from game_engine.entities import Player, Tile, TileType, BombType
from enum import Enum
from dataclasses import dataclass
from game_engine.clock import Clock
from game_engine.game_engine import EXPLOSION_MAP

GridPos = tuple[int, int]

_DIRECTION_TO_ACTION = {
    Direction.UP: Action.UP,
    Direction.DOWN: Action.DOWN,
    Direction.LEFT: Action.LEFT,
    Direction.RIGHT: Action.RIGHT,
}


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

    def print_path(
        self,
        occupancy: np.ndarray,
        goal_x: int,
        goal_y: int,
    ) -> None:
        path = self.path_to(goal_x, goal_y)

        height, width = occupancy.shape

        chars = np.full((height, width), "#", dtype="<U1")

        for y in range(height):
            for x in range(width):
                if occupancy[y, x]:
                    chars[y, x] = "."

        if path is None:
            print("No path")
            for y in range(height):
                print("".join(chars[y]))
            return

        for i, (x, y) in enumerate(path):
            chars[y, x] = str(i % 10)

        sx, sy = self.start
        chars[sy, sx] = "S"

        chars[goal_y, goal_x] = "G"

        for y in range(height):
            print("".join(chars[y]))


class MonsterSense(Enum):
    SMELL = "smell"
    VISION = "vision"


class MonsterState(Enum):
    IDLE = "idle"
    HUNTING = "hunting"


class MonsterAI(ABC):
    """Abstract base class for monster AI behavior."""

    # monster properties
    smell_radius: float  # range for smell sense
    view_radius: float  # range for vision sense
    bravery: int  # how much damage is the monster willing to take when hunting
    hunt_time: float  # how long does the monster hunt the player, seconds
    fire_delay: float = -1  # time between shots, seconds

    # store data
    state: MonsterState = MonsterState.IDLE
    occupancy: Optional[np.ndarray] = None
    fov: Optional[np.ndarray] = None
    fov_cache_key: Optional[Tuple[int, int]] = None
    path_map: Optional[PathMap] = None
    path_cache_key: Optional[Tuple[int, int]] = None
    last_fire: float = -1
    last_seen_time: float = -1
    hunt_target: Optional[DynamicEntity] = None
    hunting: bool = False
    danger_zone: np.ndarray = np.array([])
    danger_discount: float = 0.25

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

    def idle_behavior(self) -> Optional[Action]:
        self.hunting = False
        self.hunt_target = None
        self.state = MonsterState.IDLE
        return Action.STOP

    def random_behavior(self, threshold: float) -> Optional[Action]:
        self.state = MonsterState.IDLE
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
        self.state = MonsterState.HUNTING
        self.path_map = self._get_path_sense(
            state,
            own_entity,
            MonsterSense.VISION,
            avoid_danger=True,
            target_x=int(target.x),
            target_y=int(target.y),
        )

        # print("*" * 80)
        # self.path_map.print_path(
        #     self.get_occupancy(
        #         state, self.get_discriminator_function(MonsterSense.VISION)
        #     ),
        #     int(target.x),
        #     int(target.y),
        # )

        return self.follow_path(target, own_entity)

    def shooting_behavior(
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
        self.state = MonsterState.HUNTING
        occupancy = self.get_occupancy(state, MonsterAI.can_see_through)
        height, width = occupancy.shape

        x = int(own_entity.x)
        y = int(own_entity.y)

        target_x = int(target.x)
        target_y = int(target.y)

        dx = target_x - x
        dy = target_y - y

        if dx == 0 or dy == 0:
            if dx == 0:
                if target_y < y:
                    desired = Direction.UP
                else:
                    desired = Direction.DOWN
            else:
                if target_x < x:
                    desired = Direction.LEFT
                else:
                    desired = Direction.RIGHT

            if own_entity.direction == desired and (
                self.last_fire < 0 or Clock.now() - self.last_fire > self.fire_delay
            ):
                self.last_fire = Clock.now()
                return Action.FIRE
            else:
                return _DIRECTION_TO_ACTION[desired]

        candidates: list[tuple[int, Action, int, int]] = []

        if dx < 0:
            candidates.append((abs(dx), Action.LEFT, x - 1, y))
        elif dx > 0:
            candidates.append((abs(dx), Action.RIGHT, x + 1, y))

        if dy > 0:
            candidates.append((abs(dy), Action.DOWN, x, y + 1))
        elif dy < 0:
            candidates.append((abs(dy), Action.UP, x, y - 1))

        candidates.sort(reverse=False, key=lambda item: item[0])

        for _, action, nx, ny in candidates:
            if (
                0 <= nx < width
                and 0 <= ny < height
                and occupancy[ny, nx]
                and (self.danger_zone is None or self.danger_zone[ny, nx] <= 0)
            ):
                return action

    def hunting_behavior(
        self, state: RenderState, own_entity: DynamicEntity
    ) -> Optional[Action]:
        if self.hunt_target is None:
            return self.idle_behavior()

        if Clock.now() - self.last_seen_time > self.hunt_time:
            return self.idle_behavior()

        else:
            return self.target_seeking_behavior(state, own_entity, self.hunt_target)

    def bomb_avoidance_behavior(
        self, state: RenderState, own_entity: DynamicEntity
    ) -> Optional[Action]:
        path = self.shortest_path_out_of_area(
            occupancy=self.get_occupancy(state, MonsterAI.can_see_through),
            area=self.danger_zone,
            start_x=int(own_entity.x),
            start_y=int(own_entity.y),
        )

        if path is None:
            return None

        return self.path_to_next_action(path)

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

    def sense_bombs(
        self,
        state: RenderState,
        own_entity: DynamicEntity,
        dominant_sense: MonsterSense,
    ) -> bool:
        self.danger_zone = np.zeros((state.height, state.width)).astype(dtype=np.int32)

        if dominant_sense == MonsterSense.VISION:
            sensed = self._get_los_sense(state, own_entity, MonsterSense.VISION)
        elif dominant_sense == MonsterSense.SMELL:
            pathmap = self._get_path_sense(state, own_entity, MonsterSense.SMELL)
            sensed = pathmap.reachable

        assert self.danger_zone is not None
        # Cross explosions halt their arms at concrete; other explosions ignore
        # this mask, so it can be reused for every bomb.
        concrete = np.array(
            [
                [Tile.visual_id_to_type(int(cell)) == TileType.CONCRETE for cell in row]
                for row in state.tilemap
            ],
            dtype=bool,
        )
        for b in state.bombs:
            if b.bomb_type is BombType.LANDMINE:
                continue
            if sensed[int(b.y), int(b.x)]:
                explosion = EXPLOSION_MAP[b.explosion_type]
                damage_array = explosion.calculate_damage(b.x, b.y, concrete)
                self.danger_zone += damage_array
        danger_level = self.danger_zone[int(own_entity.y), int(own_entity.x)]

        # If more danger than the monster is willing to take, flee
        return danger_level * self.danger_discount > self.bravery

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
        avoid_danger: bool = False,
        target_x: Optional[int] = None,
        target_y: Optional[int] = None,
    ) -> PathMap:
        discriminator = MonsterAI.get_discriminator_function(dominant_sense)
        occupancy = self.get_occupancy(state, discriminator)

        origin_x = int(own_entity.x)
        origin_y = int(own_entity.y)

        if avoid_danger:
            cost_map = self.danger_zone

            path_map = self.compute_safe_short_path_map(
                occupancy=occupancy,
                danger_map=self.danger_zone,
                origin_x=origin_x,
                origin_y=origin_y,
                radius=int(self.view_radius),
                danger_threshold=self.bravery,
                target_x=target_x,
                target_y=target_y,
            )

        else:
            cost_map = None

            path_map = self.compute_path_map(
                occupancy=occupancy,
                origin_x=origin_x,
                origin_y=origin_y,
                radius=int(self.view_radius),
                cost_map=cost_map,
                target_x=target_x,
                target_y=target_y,
            )

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

    def hunt(self, target: DynamicEntity) -> None:
        self.last_seen_time = Clock.now()
        self.hunt_target = target
        self.hunting = True

    def follow_path(
        self,
        target: DynamicEntity,
        own_entity: DynamicEntity,
    ) -> Optional[Action]:
        assert self.path_map is not None

        path = self.path_map.path_to(
            goal_x=int(target.x),
            goal_y=int(target.y),
        )

        if path is None or len(path) < 2:
            return None

        total_danger = np.sum([float(self.danger_zone[y, x]) for x, y in path[1:]])
        if self.bravery < total_danger:
            return None

        x = int(own_entity.x)
        y = int(own_entity.y)

        next_x, next_y = path[1]

        dx = next_x - x
        dy = next_y - y

        if abs(dx) + abs(dy) != 1:
            return None

        if dx == -1:
            return Action.LEFT
        if dx == 1:
            return Action.RIGHT
        if dy == -1:
            return Action.UP
        if dy == 1:
            return Action.DOWN

        return None

    def visual_path(
        self, state: RenderState, own_entity: DynamicEntity, target: DynamicEntity
    ) -> Optional[Action]:
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
            if (
                0 <= nx < width
                and 0 <= ny < height
                and occupancy[ny, nx]
                and (self.danger_zone is None or self.danger_zone[ny, nx] <= 0)
            ):
                return action

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
                    row += "#" if occupancy[y, x] else "."

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
        cost_map: Optional[np.ndarray] = None,
        target_x: Optional[int] = None,
        target_y: Optional[int] = None,
        reveal_blocking_tiles: bool = False,
    ) -> PathMap:
        use_cache = cost_map is None and target_x is None and target_y is None
        key = (origin_x, origin_y)

        if use_cache and self.path_cache_key is not None and self.path_cache_key == key:
            assert self.path_map is not None
            return self.path_map

        height, width = occupancy.shape

        reachable = np.zeros_like(occupancy, dtype=bool)
        distance = np.full(occupancy.shape, fill_value=np.inf, dtype=float)
        parent: dict[GridPos, GridPos] = {}

        start = (origin_x, origin_y)

        if not (0 <= origin_x < width and 0 <= origin_y < height):
            return PathMap(reachable, distance, parent, start)

        if not occupancy[origin_y, origin_x]:
            return PathMap(reachable, distance, parent, start)

        if cost_map is None:
            move_cost = np.ones_like(occupancy, dtype=float)
        else:
            if cost_map.shape != occupancy.shape:
                raise ValueError("cost_map must have the same shape as occupancy")
            move_cost = cost_map.astype(float, copy=False)

        def target_tiebreaker(x: int, y: int) -> float:
            if target_x is None or target_y is None:
                return 0.0
            return abs(target_x - x) + abs(target_y - y)

        radius = max(0, int(radius))

        heap: list[tuple[float, float, GridPos]] = [
            (0.0, target_tiebreaker(origin_x, origin_y), start)
        ]

        reachable[origin_y, origin_x] = True
        distance[origin_y, origin_x] = 0.0

        while heap:
            current_cost, _, (x, y) = heappop(heap)

            if current_cost != distance[y, x]:
                continue

            if current_cost >= radius:
                continue

            for nx, ny in MonsterAI.get_neighbors(x, y, width, height):
                if not occupancy[ny, nx]:
                    if reveal_blocking_tiles:
                        reachable[ny, nx] = True
                    continue

                step_cost = float(move_cost[ny, nx])

                if step_cost < 0:
                    raise ValueError("cost_map cannot contain negative costs")

                new_cost = current_cost + step_cost

                if new_cost > radius:
                    continue

                if new_cost >= distance[ny, nx]:
                    continue

                reachable[ny, nx] = True
                distance[ny, nx] = new_cost
                parent[(nx, ny)] = (x, y)

                heappush(
                    heap,
                    (new_cost, target_tiebreaker(nx, ny), (nx, ny)),
                )

        path_map = PathMap(reachable, distance, parent, start)

        if use_cache:
            self.path_cache_key = key
            self.path_map = path_map

        return path_map

    def compute_safe_short_path_map(
        self,
        occupancy: np.ndarray,
        danger_map: np.ndarray,
        origin_x: int,
        origin_y: int,
        radius: int,
        danger_threshold: float,
        *,
        target_x: Optional[int] = None,
        target_y: Optional[int] = None,
    ) -> PathMap:
        """
        Find shortest paths while keeping total route danger below threshold.

        Primary objective:
            minimize number of steps

        Constraint:
            total danger along path <= danger_threshold

        Tie-breakers:
            lower total danger
            lower Manhattan distance to target, if target given
        """
        height, width = occupancy.shape

        if danger_map.shape != occupancy.shape:
            raise ValueError("danger_map must have the same shape as occupancy")

        reachable = np.zeros_like(occupancy, dtype=bool)

        # Here distance means number of steps, not danger.
        distance = np.full(occupancy.shape, fill_value=np.inf, dtype=float)

        # Track best known total danger for each cell.
        danger = np.full(occupancy.shape, fill_value=np.inf, dtype=float)

        parent: dict[GridPos, GridPos] = {}

        start = (origin_x, origin_y)

        if not (0 <= origin_x < width and 0 <= origin_y < height):
            return PathMap(reachable, distance, parent, start)

        if not occupancy[origin_y, origin_x]:
            return PathMap(reachable, distance, parent, start)

        radius = max(0, int(radius))
        danger_threshold = float(danger_threshold)

        def target_tiebreaker(x: int, y: int) -> float:
            if target_x is None or target_y is None:
                return 0.0
            return abs(target_x - x) + abs(target_y - y)

        # heap item:
        #   steps, total_danger, target_distance, position
        heap: list[tuple[int, float, float, GridPos]] = [
            (0, 0.0, target_tiebreaker(origin_x, origin_y), start)
        ]

        reachable[origin_y, origin_x] = True
        distance[origin_y, origin_x] = 0
        danger[origin_y, origin_x] = 0.0

        while heap:
            steps, total_danger, _, (x, y) = heappop(heap)

            if steps > distance[y, x]:
                continue

            if steps == distance[y, x] and total_danger > danger[y, x]:
                continue

            if steps >= radius:
                continue

            for nx, ny in MonsterAI.get_neighbors(x, y, width, height):
                if not occupancy[ny, nx]:
                    continue

                new_steps = steps + 1
                new_danger = total_danger + float(danger_map[ny, nx])

                if new_steps > radius:
                    continue

                if new_danger > danger_threshold:
                    continue

                old_steps = distance[ny, nx]
                old_danger = danger[ny, nx]

                # Prefer shorter paths.
                if new_steps > old_steps:
                    continue

                # Among equally short paths, prefer less danger.
                if new_steps == old_steps and new_danger >= old_danger:
                    continue

                reachable[ny, nx] = True
                distance[ny, nx] = new_steps
                danger[ny, nx] = new_danger
                parent[(nx, ny)] = (x, y)

                heappush(
                    heap,
                    (
                        new_steps,
                        new_danger,
                        target_tiebreaker(nx, ny),
                        (nx, ny),
                    ),
                )

        return PathMap(reachable, distance, parent, start)

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

    def shortest_path_out_of_area(
        self,
        occupancy: np.ndarray,
        area: Optional[np.ndarray],
        start_x: int,
        start_y: int,
    ) -> Optional[list[GridPos]]:
        """
        Find shortest cardinal path from start to the nearest walkable cell
        outside `area`.

        occupancy[y, x] == True means walkable.
        area[y, x] == True means inside the area to escape.

        Returns [(x, y), ...], including start and exit cell.
        Returns None if no exit is reachable.
        """
        start = (start_x, start_y)
        if area is None:
            return [start]

        height, width = occupancy.shape

        if area.shape != occupancy.shape:
            raise ValueError("area and occupancy must have the same shape")

        if not (0 <= start_x < width and 0 <= start_y < height):
            return None

        if not occupancy[start_y, start_x]:
            return None

        # Already outside.
        if area[start_y, start_x] <= 0:
            return [start]

        visited = np.zeros_like(occupancy, dtype=bool)
        visited[start_y, start_x] = True

        parent: dict[GridPos, GridPos] = {}

        queue: deque[GridPos] = deque([start])

        while queue:
            x, y = queue.popleft()

            for nx, ny in MonsterAI.get_neighbors(x, y, width, height):
                if visited[ny, nx]:
                    continue

                if not occupancy[ny, nx]:
                    continue

                visited[ny, nx] = True
                parent[(nx, ny)] = (x, y)

                # First outside cell found by BFS is shortest exit.
                if area[ny, nx] <= 0:
                    goal = (nx, ny)

                    path = [goal]
                    while path[-1] != start:
                        path.append(parent[path[-1]])

                    path.reverse()
                    return path

                queue.append((nx, ny))

        return None

    def path_to_next_action(self, path: list[GridPos]) -> Optional[Action]:
        if len(path) < 2:
            return None

        x, y = path[0]
        nx, ny = path[1]

        dx = nx - x
        dy = ny - y

        if abs(dx) + abs(dy) != 1:
            raise ValueError(f"Non-cardinal path step: {(x, y)} -> {(nx, ny)}")

        if dx == -1:
            return Action.LEFT
        if dx == 1:
            return Action.RIGHT
        if dy == -1:
            return Action.UP
        if dy == 1:
            return Action.DOWN

        return None

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
