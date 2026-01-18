import math
from typing import Tuple, Union


def xy_to_tile(x: float, y: float) -> Tuple[int, int]:
    vx = math.floor(x)
    vy = math.floor(y)
    return vx, vy


def clamp(
    val: Union[int, float], min_val: Union[int, float], max_val: Union[int, float]
) -> Union[int, float]:
    return min(max_val, max(min_val, val))
