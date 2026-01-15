"""
Engine utility functions for pathfinding and AI.
"""

from collections import deque
from typing import Tuple, List

import numpy as np

from game_engine.entities.tile import Tile


def get_solid_map(tiles: List[List[Tile]], height: int, width: int) -> np.ndarray:
    """
    Return a numpy boolean array where True indicates a solid tile.

    Args:
        tiles: 2D list of Tile objects
        height: Map height
        width: Map width

    Returns:
        Boolean array with shape (height, width) where True = solid
    """
    solid_map = np.zeros((height, width), dtype=bool)
    for y in range(height):
        for x in range(width):
            solid_map[y, x] = tiles[y][x].solid
    return solid_map


def flood_fill(mask: np.ndarray, start: Tuple[int, int], max_dist: int) -> np.ndarray:
    """
    Flood fill from a starting location within walkable areas.

    Takes a solid map (boolean numpy array), starting location, and max distance
    and returns a boolean numpy array marking reachable cells within the
    boundaries of non-solid blocks.

    Args:
        mask: Boolean array where True = walkable (not solid)
        start: Starting position as (row, col)
        max_dist: Maximum distance to flood fill

    Returns:
        Boolean array marking reachable cells
    """
    rows, cols = mask.shape
    r, c = start

    if not mask[r, c]:
        return np.zeros_like(mask, dtype=bool)

    result = np.zeros_like(mask, dtype=np.uint8)
    result[r, c] = 1

    queue = deque()
    queue.append((r, c, 0))

    dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    while queue:
        r, c, d = queue.popleft()

        if d >= max_dist:
            continue

        nd = d + 1
        for dr, dc in dirs:
            nr, nc = r + dr, c + dc

            if 0 <= nr < rows and 0 <= nc < cols:
                if mask[nr, nc] and result[nr, nc] == 0:
                    result[nr, nc] = 1
                    queue.append((nr, nc, nd))

    return result.astype(bool)
