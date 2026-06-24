from __future__ import annotations
from typing import List, Tuple
from game_engine.map_loader import MapData
from enum import IntEnum
import numpy as np
import random
from scipy.stats import qmc
from common.logger import get_logger


class SpawnType(IntEnum):
    EDGES = 0
    TRUE_RANDOM = 1
    UNIFORM_DIST_RANDOM = 2

    def to_string(self) -> str:
        if self == SpawnType.EDGES:
            return "edges"
        elif self == SpawnType.TRUE_RANDOM:
            return "true random"
        elif self == SpawnType.UNIFORM_DIST_RANDOM:
            return "uniform distance"
        else:
            raise ValueError("Unknown spawn type")

    @staticmethod
    def from_string(string: str) -> SpawnType:
        if string == "edges":
            return SpawnType.EDGES
        elif string == "true random":
            return SpawnType.TRUE_RANDOM
        elif string == "uniform distance":
            return SpawnType.UNIFORM_DIST_RANDOM
        else:
            raise ValueError("Unknown spawn type")


def get_spawn_points(
    num_players: int, map_data: MapData, type: SpawnType
) -> List[Tuple[int, int]]:
    log = get_logger()
    log.info(f"Get spawn points for {num_players} with type {type}")

    initial = _get_initial_points(num_players, map_data, type)
    refined = _refine(initial, map_data)

    if len(refined) > num_players:
        refined = refined[:num_players]

    stats(refined)
    return refined


def _refine(initial: List[Tuple[int, int]], map_data: MapData) -> List[Tuple[int, int]]:
    fixed: List[Tuple[int, int]] = []

    for i, point in enumerate(initial):
        h = _clamp(point[0], map_data.height - 1)
        w = _clamp(point[1], map_data.width - 1)

        found = False
        offset = 0

        while not found and offset < 100:
            min_h = _clamp(h - offset, map_data.height - 1)
            max_h = _clamp(h + offset, map_data.height - 1)
            min_w = _clamp(w - offset, map_data.width - 1)
            max_w = _clamp(w + offset, map_data.width - 1)

            for new_h in range(min_h, max_h + 1):
                for new_w in range(min_w, max_w + 1):
                    new_h = _clamp(new_h, map_data.height-1)
                    new_w = _clamp(new_w, map_data.width-1)
                    pos = (new_h, new_w)
                    tile = map_data.tiles[new_h][new_w]

                    if tile.tile_type.spawnable() and pos not in fixed:
                        fixed.append(pos)
                        found = True
                        break

                if found:
                    break
            if found:
                break
            offset += 1

    return fixed


def _get_initial_points(
    num_players: int, map_data: MapData, type: SpawnType
) -> List[Tuple[int, int]]:
    if type == SpawnType.EDGES:
        return _initial_edge(num_players, map_data)
    elif type == SpawnType.TRUE_RANDOM:
        return _initial_true_random(num_players, map_data)
    elif type == SpawnType.UNIFORM_DIST_RANDOM:
        return _poisson_disk_sampling(num_players, map_data)
    else:
        raise ValueError("Unknown spawntype")


def _initial_edge(num_players: int, map_data: MapData) -> List[Tuple[int, int]]:
    offset = 0
    width = map_data.width
    height = map_data.height

    starting_poses = [
        # 1-4 corners
        (offset, offset),
        (height - offset, width - offset),
        (offset, width - offset),
        (height - offset, offset),

        # 5-8 midpoints
        (offset, width // 2),
        (height - offset, width // 2),
        (height // 2, offset),
        (height // 2, width - offset),

        # 9-12 more wide
        (offset, width // 4),
        (height - offset, 3 * width // 4),
        (offset, 3 * width // 4),
        (height - offset, width // 4),

        # 13-16 more hi
        (height // 4, offset),
        (3 * height // 4, width - offset),
        (height // 4, width - offset),
        (3 * height // 4, offset),
    ]

    # starting_poses = [
    #     # 1-4 corners
    #     (offset, offset),
    #     (width - offset, height - offset),
    #     (width - offset, offset),
    #     (offset, height - offset),
    #     # 5-8 midpoints
    #     (width // 2, offset),
    #     (width // 2, height - offset),
    #     (offset, height // 2),
    #     (width - offset, height // 2),
    #     # 9-12 more wide
    #     (width // 4, offset),
    #     (3 * width // 4, height),
    #     (width // 4, offset - offset),
    #     (3 * width // 4, height - offset),
    # ]

    return starting_poses


def _initial_true_random(num_players: int, map_data: MapData) -> List[Tuple[int, int]]:
    width = map_data.width
    height = map_data.height

    init = []
    for _ in range(num_players):
        ok = False
        while not ok:
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)
            pos = (x, y)
            if pos not in init:
                init.append(pos)
                ok = True

    return init


def _poisson_disk_sampling(
    num_players: int, map_data: MapData
) -> List[Tuple[int, int]]:
    width = map_data.width
    height = map_data.height
    area_per_point = 1.0 / num_players
    radius = 0.8 * np.sqrt(area_per_point)
    engine = qmc.PoissonDisk(d=2, radius=radius, ncandidates=1000)
    samples = engine.integers(l_bounds=[0, 0], u_bounds=[height, width], n=num_players)

    return [tuple(p) for p in samples.astype(np.int32)]


def stats(poses: List[Tuple[int, int]]):
    log = get_logger()
    samples = np.array(poses)
    for i in range(samples.shape[0]):
        p = samples[i, :]
        dists = []
        for j in range(samples.shape[0]):
            if j == i:
                continue
            p2 = samples[j, :]
            d = np.linalg.norm(np.array(p) - np.array(p2))
            dists.append(d)
        if len(dists) > 0:
            da = np.array(dists)
            log.info(f"mean d: {da.mean()}")


def _clamp(val: int, mx: int) -> int:
    return max(min(val, mx), 0)
