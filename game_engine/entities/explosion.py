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
EXPLOSION_SMALL = _create_circular_pattern(2.5)  # 3x3 cross
EXPLOSION_MEDIUM = _create_circular_pattern(5)   # 5x5
EXPLOSION_LARGE = _create_circular_pattern(7)    # 7x7
EXPLOSION_NUKE = _create_circular_pattern(24.04)  # 25x25 cross
EXPLOSION_SMALL_CROSS = _create_cross_pattern(25)  # 25-tile diameter cross
EXPLOSION_BIG_CROSS = _create_cross_pattern(50)    # 50-tile diameter cross

# Explosion damage amounts
DAMAGE_SMALL = 50
DAMAGE_MEDIUM = 50
DAMAGE_LARGE = 70
DAMAGE_NUKE = 100
DAMAGE_FLAME = 35
DAMAGE_DIRECTED_FLAME = 35
DAMAGE_SMALL_CROSS = 50
DAMAGE_BIG_CROSS = 50


class ExplosionType(Enum):
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


class DirectedFlameExplosion(Explosion):
    """Directed flame that shoots in a single direction."""

    def __init__(self, direction: Direction, base_damage: int = DAMAGE_DIRECTED_FLAME):
        super().__init__(np.zeros((1, 1), dtype=bool), base_damage)
        self.direction = direction

    def calculate_damage(self, origin_x: int, origin_y: int, solids: np.ndarray) -> np.ndarray:
        pass  # TODO: implement directed flame logic
