from abc import ABC, abstractmethod
from enum import Enum
import numpy as np

from game_engine.entities.dynamic_entity import Direction


def _create_circular_pattern(diameter: int) -> np.ndarray:
    """Create a boolean array with True for cells within radius of center."""
    radius = diameter / 2
    center = diameter // 2
    y, x = np.ogrid[:diameter, :diameter]
    distance = np.sqrt((x - center) ** 2 + (y - center) ** 2)
    return distance < radius


def _create_cross_pattern(diameter: int) -> np.ndarray:
    """Create a boolean array with True for cells in cardinal directions only (cross shape)."""
    pattern = np.zeros((diameter, diameter), dtype=bool)
    center = diameter // 2
    # Horizontal line
    pattern[center, :] = True
    # Vertical line
    pattern[:, center] = True
    return pattern


# Explosion shape lookup tables
EXPLOSION_SMALL = _create_circular_pattern(3)    # 3x3
EXPLOSION_MEDIUM = _create_circular_pattern(4.4) # 5 wide middle row, rest smaller
EXPLOSION_LARGE = _create_circular_pattern(7)     # 7x7
EXPLOSION_NUKE = _create_circular_pattern(24.04)  # 25x25 cross
EXPLOSION_SMALL_CROSS = _create_cross_pattern(31) # 25-tile diameter cross
EXPLOSION_BIG_CROSS = _create_cross_pattern(127)  # 50-tile diameter cross

# Explosion damage amounts
DAMAGE_SMALL = 50
DAMAGE_MEDIUM = 50
DAMAGE_LARGE = 70
DAMAGE_NUKE = 200
DAMAGE_FLAME = 35
DAMAGE_DIRECTED_FLAME = 35
DAMAGE_SMALL_CROSS = 50
DAMAGE_BIG_CROSS = 50


class ExplosionType(Enum):
    NONE = 'none'  # No explosion (used for bombs that don't explode)
    SMALL = 'small'
    MEDIUM = 'medium'
    LARGE = 'large'
    NUKE = 'nuke'
    FLAME = 'flame'
    DIRECTED_FLAME = 'directed_flame'
    SMALL_CROSS = 'small_cross'
    BIG_CROSS = 'big_cross'


class Explosion(ABC):
    """
    Base class for explosion patterns.

    Each explosion takes a boolean array of solid blocks and returns
    a uint8 array with damage values.
    """

    def __init__(self, pattern: np.ndarray, base_damage: int = 50):
        self.pattern = pattern
        self.base_damage = base_damage

    def calculate_damage(self, origin_x: int, origin_y: int, solids: np.ndarray) -> np.ndarray:
        """
        Calculate damage pattern based on solid blocks.

        Args:
            origin_x: X coordinate of explosion center
            origin_y: Y coordinate of explosion center
            solids: Boolean numpy array where True = solid block

        Returns:
            uint8 numpy array with damage values (0 = no damage)
        """
        return self._apply_pattern(origin_x, origin_y, solids)

    def _apply_pattern(self, origin_x: int, origin_y: int, solids: np.ndarray) -> np.ndarray:
        """Apply the explosion pattern centered at origin, clipped to map bounds."""
        damage = np.zeros(solids.shape, dtype=np.uint8)
        pat_height, pat_width = self.pattern.shape
        map_height, map_width = solids.shape

        # Pattern center indices
        center_y = pat_height // 2
        center_x = pat_width // 2

        # Calculate the bounds in map coordinates (pattern extends from -center to +remaining)
        map_y_start = max(0, origin_y - center_y)
        map_y_end = min(map_height, origin_y + (pat_height - center_y))
        map_x_start = max(0, origin_x - center_x)
        map_x_end = min(map_width, origin_x + (pat_width - center_x))

        # Calculate corresponding bounds in pattern coordinates
        pat_y_start = map_y_start - (origin_y - center_y)
        pat_y_end = pat_y_start + (map_y_end - map_y_start)
        pat_x_start = map_x_start - (origin_x - center_x)
        pat_x_end = pat_x_start + (map_x_end - map_x_start)

        pattern_slice = self.pattern[pat_y_start:pat_y_end, pat_x_start:pat_x_end]
        np.place(damage[map_y_start:map_y_end, map_x_start:map_x_end], pattern_slice, self.base_damage)

        return damage


class SmallExplosion(Explosion):
    """Small explosion with 1-tile radius."""

    def __init__(self, base_damage: int = DAMAGE_SMALL):
        super().__init__(EXPLOSION_SMALL, base_damage)


class MediumExplosion(Explosion):
    """Medium explosion with 2-tile radius."""

    def __init__(self, base_damage: int = DAMAGE_MEDIUM):
        super().__init__(EXPLOSION_MEDIUM, base_damage)


class LargeExplosion(Explosion):
    """Large explosion with 3-tile radius."""

    def __init__(self, base_damage: int = DAMAGE_LARGE):
        super().__init__(EXPLOSION_LARGE, base_damage)


class NukeExplosion(Explosion):
    """Massive explosion with 25-tile diameter."""

    def __init__(self, base_damage: int = DAMAGE_NUKE):
        super().__init__(EXPLOSION_NUKE, base_damage)


class SmallCrossExplosion(Explosion):
    """Cross-shaped explosion with 25-tile diameter (cardinal directions only)."""

    def __init__(self, base_damage: int = DAMAGE_SMALL_CROSS):
        super().__init__(EXPLOSION_SMALL_CROSS, base_damage)


class BigCrossExplosion(Explosion):
    """Cross-shaped explosion with 50-tile diameter (cardinal directions only)."""

    def __init__(self, base_damage: int = DAMAGE_BIG_CROSS):
        super().__init__(EXPLOSION_BIG_CROSS, base_damage)


class FlameExplosion(Explosion):
    """Flame explosion that spreads in all four cardinal directions."""

    def __init__(self, base_damage: int = DAMAGE_FLAME):
        super().__init__(np.zeros((1, 1), dtype=bool), base_damage)

    def calculate_damage(self, origin_x: int, origin_y: int, solids: np.ndarray) -> np.ndarray:
        pass  # TODO: implement flame spread logic


class DirectedFlameExplosion:
    """
    Directed flame that shoots in a 90-degree cone.

    Unlike other explosions, this uses flood fill combined with a cone mask
    to determine the affected area.
    """

    def __init__(self, direction: Direction, max_distance: int = 10, base_damage: int = DAMAGE_DIRECTED_FLAME):
        self.direction = direction
        self.max_distance = max_distance
        self.base_damage = base_damage

    def calculate_cone_mask(self, start_x: int, start_y: int, map_height: int, map_width: int) -> np.ndarray:
        """
        Create a 90-degree cone mask oriented in the direction.

        A tile (x, y) is in the cone if:
        - RIGHT: rx > 0 and |ry| <= rx
        - LEFT:  rx < 0 and |ry| <= |rx|
        - DOWN:  ry > 0 and |rx| <= ry
        - UP:    ry < 0 and |rx| <= |ry|
        where rx = x - start_x, ry = y - start_y

        The starting tile itself is always included.
        """
        cone_mask = np.zeros((map_height, map_width), dtype=bool)

        for y in range(map_height):
            for x in range(map_width):
                rx = x - start_x
                ry = y - start_y
                in_cone = False

                if self.direction == Direction.RIGHT:
                    in_cone = rx > 0 and abs(ry) <= rx
                elif self.direction == Direction.LEFT:
                    in_cone = rx < 0 and abs(ry) <= abs(rx)
                elif self.direction == Direction.DOWN:
                    in_cone = ry > 0 and abs(rx) <= ry
                elif self.direction == Direction.UP:
                    in_cone = ry < 0 and abs(rx) <= abs(ry)

                # Include the starting tile itself
                if rx == 0 and ry == 0:
                    in_cone = True

                cone_mask[y, x] = in_cone

        return cone_mask

    def calculate_area(self, origin_x: int, origin_y: int, walkable: np.ndarray, flood_fill_func) -> np.ndarray:
        """
        Calculate the affected area using flood fill ANDed with cone mask.

        Args:
            origin_x: X coordinate of the player/bomb
            origin_y: Y coordinate of the player/bomb
            walkable: Boolean array where True = walkable/empty
            flood_fill_func: The flood_fill function to use

        Returns:
            Boolean mask of affected tiles
        """
        map_height, map_width = walkable.shape

        # Calculate starting tile (one tile in front of origin)
        dx, dy = 0, 0
        if self.direction == Direction.RIGHT:
            dx = 1
        elif self.direction == Direction.LEFT:
            dx = -1
        elif self.direction == Direction.DOWN:
            dy = 1
        elif self.direction == Direction.UP:
            dy = -1

        start_x = origin_x + dx
        start_y = origin_y + dy

        # Check bounds - return empty mask if starting tile is out of bounds
        if not (0 <= start_x < map_width and 0 <= start_y < map_height):
            return np.zeros((map_height, map_width), dtype=bool)

        # Flood fill from starting tile
        fill_mask = flood_fill_func(walkable, (start_y, start_x), max_dist=self.max_distance)

        # Create cone mask
        cone_mask = self.calculate_cone_mask(start_x, start_y, map_height, map_width)

        # AND flood fill with cone mask
        return fill_mask & cone_mask

    def calculate_damage(self, origin_x: int, origin_y: int, walkable: np.ndarray, flood_fill_func) -> np.ndarray:
        """
        Calculate damage array for the directed flame.

        Args:
            origin_x: X coordinate of the player/bomb
            origin_y: Y coordinate of the player/bomb
            walkable: Boolean array where True = walkable/empty
            flood_fill_func: The flood_fill function to use

        Returns:
            uint8 array with damage values
        """
        area = self.calculate_area(origin_x, origin_y, walkable, flood_fill_func)
        damage = np.zeros(walkable.shape, dtype=np.uint8)
        damage[area] = self.base_damage
        return damage
