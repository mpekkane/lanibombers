import array
import random
from typing import List
from game_engine.map_loader import MapData
from game_engine.entities.tile import Tile
from game_engine.entities.treasure import TreasureType, Treasure
from game_engine.entities.tool import Tool, ToolType
from game_engine.entities import DynamicEntity
from game_engine.perlin import generate_and_threshold
from cfg.tile_dictionary import (
    BEDROCK_INSIDE_TILES,
    BEDROCK_CORNER_TILES,
    DIRT_TILES
)


class RandomMapGenerator:
    def __init__(self) -> None:
        pass

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
                    # TODO: fix corner tiles
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
