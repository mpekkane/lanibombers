"""Creates random maps"""

import os
import array
import random
from typing import List, Tuple
import numpy as np
from game_engine.map_loader import MapData
from game_engine.entities.tile import Tile
from game_engine.entities.treasure import TreasureType, Treasure
from game_engine.entities.tool import Tool, ToolType
from game_engine.entities import DynamicEntity
from game_engine.perlin import generate_and_threshold
from game_engine.map_loader import parse_map
from common.tile_dictionary import (
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
        """Determines if map square is bedrock"""
        if 0 <= x and x < width and 0 <= y and y < height:
            return map[x, y]
        else:
            return True

    def generate(
        self,
        x: int = 64,
        y: int = 45,
        feature_sizes: List[int] = [20, 5],
        threshold: float = 0.3,
        min_treasure: int = 10,
        max_treasure: int = 40,
        min_tools: int = 5,
        max_tools: int = 20,
        max_rooms: int = 5,
        room_chance: float = 0.1
    ) -> MapData:
        """Generate a random map.

        Args:
            x (int, optional): Generted map width. Defaults to 64.
            y (int, optional): Generted map height. Defaults to 45.
            feature_size (int, optional): "Size" of features. Large values have large bedrock formations. Small values result in scattered small features. Defaults to 20.
            threshold (float, optional): Noise control value. From -1 to 1. Larger values produce more bedrock. Defaults to 0.1.
            min_treasure (int, optional): Minimum number of generated treasures. Defaults to 10.
            max_treasure (int, optional): Maximum number of generated treasures. Defaults to 40.
            min_tools (int, optional): Minimum number of generated tools. Defaults to 5.
            max_tools (int, optional): Maximum number of generated tools. Defaults to 20.

        Returns:
            MapData: Map data in renderer-friendly format
        """
        _, map = generate_and_threshold(x, y, feature_sizes, threshold)  # type: ignore

        width: int = map.shape[0]  # type: ignore
        height: int = map.shape[1]  # type: ignore
        assert isinstance(width, int)
        assert isinstance(height, int)

        placed_items: List[Tuple[int, int]] = []

        # no monsters in random levels
        monsters: List[DynamicEntity] = []

        treasures: List[Treasure] = []
        dist_from_edge = 3
        num_treasure = random.randint(min_treasure, max_treasure)
        for _ in range(num_treasure):
            ok = False
            while not ok:
                x = random.randint(dist_from_edge, width - dist_from_edge)
                y = random.randint(dist_from_edge, height - dist_from_edge)
                if (x, y) not in placed_items:
                    ok = True
            type = random.choice(list(TreasureType))
            treasures.append(Treasure.create(x, y, type))
            placed_items.append((x, y))

        tools: List[Tool] = []
        num_tool = random.randint(min_tools, max_tools)
        for _ in range(num_tool):
            ok = False
            while not ok:
                x = random.randint(dist_from_edge, width - dist_from_edge)
                y = random.randint(dist_from_edge, height - dist_from_edge)
                if (x, y) not in placed_items:
                    ok = True
            type = random.choice(list(ToolType))
            tools.append(Tool.create(x, y, type))
            placed_items.append((x, y))

        empty_len = 8

        tiles: List[List[Tile]] = []
        tilemap = array.array("B")
        for y in range(height):
            tiles.append([])
            for x in range(width):
                # empty start locations
                if (
                    (y == 0 and x < empty_len)
                    or (y == 0 and x + empty_len >= width)
                    or (y == height - 1 and x < empty_len)
                    or (y == height - 1 and x + empty_len >= width)
                    or (x == 0 and y < empty_len)
                    or (x == 0 and y + empty_len >= height)
                    or (x == width - 1 and y < empty_len)
                    or (x == width - 1 and y + empty_len >= height)
                ):
                    tiles[y].append(Tile.create_empty())
                # else do regular generated map
                else:
                    if (x, y) in placed_items:
                        tiles[y].append(Tile.create_empty())
                    else:
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

        for _ in range(random.randint(0, max_rooms)):
            p = random.uniform(0, 1)
            if p < room_chance:
                room_w, room_h, room_map, room_data = self.get_room()
                left = random.randint(0, x-room_w)
                top = random.randint(0, y-room_h)
                init_offset = top * width + left

                for row in range(room_h):
                    for col in range(room_w):
                        idx = row * room_w + col
                        offset = row * width + col
                        tilemap[init_offset + offset] = room_map[idx]

                        tiles[top+row][left+col] = Tile.create_by_id(room_map[idx])

                for t in room_data.treasures:
                    t.x += left
                    t.y += top
                for t in room_data.tools:
                    t.x += left
                    t.y += top
                for m in room_data.monsters:
                    m.x += left
                    m.y += top

                treasures += room_data.treasures
                tools += room_data.tools
                monsters += room_data.monsters

        return MapData(
            width=width,
            height=height,
            tiles=tiles,
            tilemap=tilemap,
            monsters=monsters,
            treasures=treasures,
            tools=tools,
        )

    def get_room(self) -> Tuple[int, int, List, MapData]:
        rooms = os.listdir("common/room_templates")
        room = random.choice(rooms)
        path = f"common/room_templates/{room}"

        tiles: List[int] = []
        with open(path, "rb") as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                if i == 0:
                    width = int(line)
                elif i == 1:
                    height = int(line)
                else:
                    line = line.rstrip(b"\r\n")
                    for char in line:
                        tiles.append(char)

        tilemap = array.array("B", tiles)

        data = parse_map(tilemap, width, height)
        return width, height, tiles, data
