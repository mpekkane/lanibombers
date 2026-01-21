import array
import random
from typing import List
import numpy as np
from game_engine.map_loader import MapData
from game_engine.entities.tile import Tile
from game_engine.entities.treasure import TreasureType, Treasure
from game_engine.entities.tool import Tool, ToolType
from game_engine.entities import DynamicEntity
from game_engine.perlin import generate_and_threshold
from cfg.tile_dictionary import (
    BEDROCK_INSIDE_TILES,
    BEDROCK_NW_ID,
    BEDROCK_NE_ID,
    BEDROCK_SE_ID,
    BEDROCK_SW_ID,
    DIRT_TILES,
)


class RandomMapGenerator:
    def __init__(self) -> None:
        pass

    def is_bedrock(
        self, map: np.ndarray, x: int, y: int, width: int, height: int
    ) -> bool:
        if 0 <= x and x < width and 0 <= y and y < height:
            return map[x, y]
        else:
            return True

    def generate(
        self,
        feature_resolution: int = 3,
        aspect: float = 1.43,
        fidelity: int = 15,
        threshold: float = 0.1,
        min_treasure: int = 10,
        max_treasure: int = 40,
        min_tools: int = 5,
        max_tools: int = 20,
    ) -> MapData:
        _, map = generate_and_threshold(feature_resolution, aspect, fidelity, threshold)  # type: ignore

        width: int = map.shape[0]  # type: ignore
        height: int = map.shape[1]  # type: ignore
        assert isinstance(width, int)
        assert isinstance(height, int)

        tiles: List[List[Tile]] = []
        tilemap = array.array("B")
        for y in range(height):
            tiles.append([])
            for x in range(width):
                if map[x, y]:
                    north = self.is_bedrock(map, x, y - 1, width, height)  # type: ignore
                    south = self.is_bedrock(map, x, y + 1, width, height)  # type: ignore
                    west = self.is_bedrock(map, x - 1, y, width, height)  # type: ignore
                    east = self.is_bedrock(map, x + 1, y, width, height)  # type: ignore
                    if south and east and not north and not west:
                        rid = BEDROCK_NW_ID
                    elif south and west and not north and not east:
                        rid = BEDROCK_NE_ID
                    elif north and east and not south and not west:
                        rid = BEDROCK_SW_ID
                    elif north and west and not south and not east:
                        rid = BEDROCK_SE_ID
                    else:
                        rid = random.choice(list(BEDROCK_INSIDE_TILES))
                    tiles[y].append(Tile.create_by_id(tile_id=rid))
                else:
                    rid = random.choice(list(DIRT_TILES))
                    tiles[y].append(Tile.create_by_id(tile_id=rid))
                tilemap.append(tiles[y][x].to_byte())

        # no monsters in random levels
        monsters: List[DynamicEntity] = []

        treasures: List[Treasure] = []
        dist_from_edge = 3
        num_treasure = random.randint(min_treasure, max_treasure)
        for _ in range(num_treasure):
            x = random.randint(dist_from_edge, width - dist_from_edge)
            y = random.randint(dist_from_edge, height - dist_from_edge)
            type = random.choice(list(TreasureType))
            treasures.append(Treasure.create(x, y, type))

        tools: List[Tool] = []
        num_tool = random.randint(min_tools, max_tools)
        for _ in range(num_tool):
            x = random.randint(dist_from_edge, width - dist_from_edge)
            y = random.randint(dist_from_edge, height - dist_from_edge)
            type = random.choice(list(ToolType))
            tools.append(Tool.create(x, y, type))

        return MapData(
            width=width,
            height=height,
            tiles=tiles,
            tilemap=tilemap,
            monsters=monsters,
            treasures=treasures,
            tools=tools,
        )
