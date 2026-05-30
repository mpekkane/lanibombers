from game_engine.monster_controller import MonsterController
from game_engine.entities import DynamicEntity, EntityType
from game_engine.render_state import RenderState
from game_engine.entities import Direction, Tile, TileType
from game_engine import GameEngine
import numpy as np


def get_tile(symbol: str) -> Tile:
    if symbol == "c":
        tiletype = TileType.CONCRETE
    elif symbol == "e":
        tiletype = TileType.EMPTY
    else:
        raise ValueError("unknown tile")

    return Tile.create(tiletype)


def get_map():
    map = [
        "ccccccccccccccccccccc",  # 0
        "ceeeeeeeeeeeeeeeeeeec",  # 1
        "ceeccccccceeeccccceec",  # 2
        "ceeeeeeeeceeeeeeeecec",  # 3
        "ceccccceeceeccccceeec",   # 4
        "ceeeeeceeeeeeceeeeeec",   # 5
        "cccccecccccccecccecec",   # 6
        "ceeeeeeeeeeeeeeeeeeec",   # 7
        "ceeccccceccccceeeeeec",   # 8
        "ceeeeeeeeceeeeeeeeeec",   # 9
        "ceeeeeeeeeeeeeeeeeeec",   # 10  monster at x=10, y=10
        "ceeeeeeeeceeeeeeeeeec",   # 11
        "ceeccccceccccceeeeeec",   # 12
        "ceeeeeeeeeeeeeeeeeeec",   # 13
        "cccccecccccccecccecec",   # 14
        "ceeeeeceeeeeeceeeeeec",   # 15
        "ceccccceeceeccccceeec",   # 16
        "ceeeeeeeeceeeeeeeecec",  # 17
        "ceeccccccceeeccccceec",  # 18
        "ceeeeeeeeeeeeeeeeeeec",  # 19
        "ccccccccccccccccccccc",  # 20
    ]
    width = len(map[0])
    height = len(map)
    tiles = [[get_tile(symbol) for symbol in row] for row in map]

    return tiles, width, height


def main():
    map, w, h = get_map()

    monster = DynamicEntity.create_monster(
        EntityType.SLIME, w / 2, h / 2, direction=Direction.LEFT
    )
    ctrl = MonsterController(monster, None)
    state = RenderState(
        width=w,
        height=h,
        tilemap=GameEngine.tilemap_to_numpy(map),
        explosions=np.array([]),
        players=[],
        monsters=[],
        pickups=[],
        bombs=[],
        server_time=0,
        sounds=[],
        running=True,
        round_time_left=60,
    )
    ctrl.ai.think(state, True, monster)


if __name__ == "__main__":
    main()
