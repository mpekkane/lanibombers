import math
from typing import Tuple


def xy_to_tile(x: float, y: float) -> Tuple[int, int]:
    # FIXME: this is hard to tune with real-valued movement values
    treshold = 0.99
    vx = math.floor(x)
    vy = math.floor(y)
    dx = x - vx
    dy = y - vy
    if dx >= treshold:
        vx += 1
    if dy >= treshold:
        vy += 1
    return vx, vy
