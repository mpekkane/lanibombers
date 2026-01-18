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


# Explosion shape lookup tables
EXPLOSION_SMALL = _create_circular_pattern(3)    # 3x3
EXPLOSION_MEDIUM = _create_circular_pattern(5)   # 5x5
EXPLOSION_LARGE = _create_circular_pattern(7)    # 7x7
EXPLOSION_NUKE = _create_circular_pattern(25)    # 25x25


class ExplosionType(Enum):
    SMALL = 'small'
    MEDIUM = 'medium'
    LARGE = 'large'
    NUKE = 'nuke'
    FLAME = 'flame'
    DIRECTED_FLAME = 'directed_flame'


class Explosion(ABC):
    """
    Base class for explosion patterns.

    Each explosion takes a boolean array of solid blocks and returns
    a uint8 array with damage values.
    """

    def __init__(self, base_damage: int = 50):
        self.base_damage = base_damage

    @abstractmethod
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
        pass


class SmallExplosion(Explosion):
    """Small explosion with 1-tile radius."""

    def __init__(self, base_damage: int = 40):
        super().__init__(base_damage)

    def calculate_damage(self, origin_x: int, origin_y: int, solids: np.ndarray) -> np.ndarray:
        damage = np.zeros(solids.shape, dtype=np.uint8)
        pattern = EXPLOSION_SMALL
        radius = pattern.shape[0] // 2

        # Slice bounds for damage array
        d_y = slice(max(0, origin_y - radius), min(solids.shape[0], origin_y + radius + 1))
        d_x = slice(max(0, origin_x - radius), min(solids.shape[1], origin_x + radius + 1))

        # Slice bounds for pattern array
        p_y = slice(max(0, radius - origin_y), pattern.shape[0] - max(0, origin_y + radius + 1 - solids.shape[0]))
        p_x = slice(max(0, radius - origin_x), pattern.shape[1] - max(0, origin_x + radius + 1 - solids.shape[1]))

        np.place(damage[d_y, d_x], pattern[p_y, p_x], 51)

        return damage


class MediumExplosion(Explosion):
    """Medium explosion with 2-tile radius."""

    def __init__(self, base_damage: int = 50):
        super().__init__(base_damage)

    def calculate_damage(self, origin_x: int, origin_y: int, solids: np.ndarray) -> np.ndarray:
        damage = np.zeros(solids.shape, dtype=np.uint8)
        pattern = EXPLOSION_MEDIUM
        radius = pattern.shape[0] // 2

        d_y = slice(max(0, origin_y - radius), min(solids.shape[0], origin_y + radius + 1))
        d_x = slice(max(0, origin_x - radius), min(solids.shape[1], origin_x + radius + 1))

        p_y = slice(max(0, radius - origin_y), pattern.shape[0] - max(0, origin_y + radius + 1 - solids.shape[0]))
        p_x = slice(max(0, radius - origin_x), pattern.shape[1] - max(0, origin_x + radius + 1 - solids.shape[1]))

        np.place(damage[d_y, d_x], pattern[p_y, p_x], 51)

        return damage


class LargeExplosion(Explosion):
    """Large explosion with 3-tile radius."""

    def __init__(self, base_damage: int = 60):
        super().__init__(base_damage)

    def calculate_damage(self, origin_x: int, origin_y: int, solids: np.ndarray) -> np.ndarray:
        damage = np.zeros(solids.shape, dtype=np.uint8)
        pattern = EXPLOSION_LARGE
        radius = pattern.shape[0] // 2

        d_y = slice(max(0, origin_y - radius), min(solids.shape[0], origin_y + radius + 1))
        d_x = slice(max(0, origin_x - radius), min(solids.shape[1], origin_x + radius + 1))

        p_y = slice(max(0, radius - origin_y), pattern.shape[0] - max(0, origin_y + radius + 1 - solids.shape[0]))
        p_x = slice(max(0, radius - origin_x), pattern.shape[1] - max(0, origin_x + radius + 1 - solids.shape[1]))

        np.place(damage[d_y, d_x], pattern[p_y, p_x], 51)

        return damage


class NukeExplosion(Explosion):
    """Massive explosion with 25-tile diameter."""

    def __init__(self, base_damage: int = 100):
        super().__init__(base_damage)

    def calculate_damage(self, origin_x: int, origin_y: int, solids: np.ndarray) -> np.ndarray:
        damage = np.zeros(solids.shape, dtype=np.uint8)
        pattern = EXPLOSION_NUKE
        radius = pattern.shape[0] // 2

        d_y = slice(max(0, origin_y - radius), min(solids.shape[0], origin_y + radius + 1))
        d_x = slice(max(0, origin_x - radius), min(solids.shape[1], origin_x + radius + 1))

        p_y = slice(max(0, radius - origin_y), pattern.shape[0] - max(0, origin_y + radius + 1 - solids.shape[0]))
        p_x = slice(max(0, radius - origin_x), pattern.shape[1] - max(0, origin_x + radius + 1 - solids.shape[1]))

        np.place(damage[d_y, d_x], pattern[p_y, p_x], 51)

        return damage


class FlameExplosion(Explosion):
    """Flame explosion that spreads in all four cardinal directions."""

    def __init__(self, base_damage: int = 35):
        super().__init__(base_damage)

    def calculate_damage(self, origin_x: int, origin_y: int, solids: np.ndarray) -> np.ndarray:
        pass


class DirectedFlameExplosion(Explosion):
    """Directed flame that shoots in a single direction."""

    def __init__(self, direction: Direction, base_damage: int = 45):
        super().__init__(base_damage)
        self.direction = direction

    def calculate_damage(self, origin_x: int, origin_y: int, solids: np.ndarray) -> np.ndarray:
        pass
