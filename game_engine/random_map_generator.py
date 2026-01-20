from game_engine.map_loader import MapData
from game_engine.entities.tile import Tile, TileType
from cfg.tile_dictionary import (
    TILE_DICTIONARY
)
from game_engine.perlin import perlin_noise


class RandomMapGenerator:
    def __init__(self) -> None:
        pass

    def generate(self) -> MapData:
        width = 20
        height = 20
        tiles = [
            [Tile() for _ in range(width)] for _ in range(height)
        ]

        r = 0
        c = 0
        for key, val in TILE_DICTIONARY.items():
            tiles[r][c] = Tile.create_by_id(key)
            c += 1
            if c >= width:
                c = 0
                r += 1

        tilemap = None
        monsters = []
        treasures = []
        tools = []

        return MapData(
            width=width,
            height=height,
            tiles=tiles,
            tilemap=tilemap,
            monsters=monsters,
            treasures=treasures,
            tools=tools,
        )