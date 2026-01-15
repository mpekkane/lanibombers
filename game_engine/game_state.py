import array
import time
from typing import List, Tuple, Dict
from cfg.tile_dictionary import EMPTY_TILE_ID, MONSTER_SPAWN_TILES
from game_engine.entities import Direction, EntityType, DynamicEntity
import random
from copy import deepcopy


class Game:
    def __init__(self, map_path: str):
        self.players: Dict[str, DynamicEntity] = {}
        self.monsters: List[DynamicEntity] = []
        self.grid = array.array("B")
        self.height: int
        self.width: int
        self.start_time: float
        self.last_damage_time: float
        self.prev_time: float = -1

        self._load_map(map_path)
        self._init_monsters()

    #  ██████╗ ███████╗████████╗
    # ██╔════╝ ██╔════╝╚══██╔══╝
    # ██║  ███╗█████╗     ██║
    # ██║   ██║██╔══╝     ██║
    # ╚██████╔╝███████╗   ██║
    #  ╚═════╝ ╚══════╝   ╚═╝

    def get_monsters(self) -> List[DynamicEntity]:
        return self.monsters

    def get_player(self, name: str) -> DynamicEntity:
        return self.players[name]

    def get_players(self) -> Dict[str, DynamicEntity]:
        return self.players

    def get_player_list(self) -> List[DynamicEntity]:
        return self.players.values()

    def get_grid(self) -> array.array:
        return self.grid

    def get_size(self) -> Tuple[int, int]:
        return self.width, self.height

    # ██╗███╗   ██╗██╗████████╗
    # ██║████╗  ██║██║╚══██╔══╝
    # ██║██╔██╗ ██║██║   ██║
    # ██║██║╚██╗██║██║   ██║
    # ██║██║ ╚████║██║   ██║
    # ╚═╝╚═╝  ╚═══╝╚═╝   ╚═╝

    def create_player(self, name: str) -> None:
        num_players = len(self.players)

        # FIXME: sensible positions
        ix = random.randint(10, 20)
        iy = random.randint(10, 20)
        player = DynamicEntity(
            x=ix,
            y=iy,
            direction=Direction.RIGHT,
            entity_type=EntityType.PLAYER,
            name=name,
            sprite_id=num_players+1,
            state="idle",
        )
        self.players[name] = deepcopy(player)
        print(f"Created player {name}. Total {len(self.players)}")

    def _load_map(self, path: str) -> None:
        """Load map from ASCII file, sprite indices are ASCII values"""
        with open(path, "rb") as f:
            for line in f:
                line = line.rstrip(b"\r\n")
                for char in line:
                    self.grid.append(char)
        # FIXME: variables
        self.height = 45
        self.width = 64

    def _mock_init_players(self):
        """Initialize mock players"""
        self.players = {
            "p1": DynamicEntity(
                x=9,
                y=9,
                direction=Direction.RIGHT,
                entity_type=EntityType.PLAYER,
                name="Player1",
                colour=(255, 0, 0),
                sprite_id=1,
                state="dig",
            ),
            "p2": DynamicEntity(
                x=8,
                y=18,
                direction=Direction.RIGHT,
                entity_type=EntityType.PLAYER,
                name="Player2",
                colour=(0, 255, 0),
                sprite_id=2,
                state="idle",
            ),
        }
        self.start_time = time.time()
        self.last_damage_time = self.start_time

    def _init_monsters(self):
        """Initialize monsters from spawn tiles in the map"""
        for i, tile_id in enumerate(self.grid):
            if tile_id in MONSTER_SPAWN_TILES:
                entity_type, direction = MONSTER_SPAWN_TILES[tile_id]
                x = i % self.width
                y = i // self.width

                monster = DynamicEntity(
                    x=x, y=y, direction=direction, entity_type=entity_type, state="walk"
                )
                self.monsters.append(monster)

                # Replace spawn tile with empty
                self.grid[i] = EMPTY_TILE_ID

    # ██╗   ██╗██████╗ ██████╗  █████╗ ████████╗███████╗
    # ██║   ██║██╔══██╗██╔══██╗██╔══██╗╚══██╔══╝██╔════╝
    # ██║   ██║██████╔╝██║  ██║███████║   ██║   █████╗
    # ██║   ██║██╔═══╝ ██║  ██║██╔══██║   ██║   ██╔══╝
    # ╚██████╔╝██║     ██████╔╝██║  ██║   ██║   ███████╗
    #  ╚═════╝ ╚═╝     ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚══════╝

    def update_state(self):
        if self.prev_time < 0:
            self.prev_time = time.time()
        elapsed = time.time() - self.prev_time
        # Speed: 1.5 blocks/second (6 blocks in 4 seconds)

        speed = 1.5  # blocks per second
        dt = elapsed * speed

        for key, player in self.players.items():
            dx = 0
            dy = 0
            if player.state == "walk":
                if player.direction == Direction.RIGHT:
                    dx = dt
                elif player.direction == Direction.LEFT:
                    dx = -dt
                elif player.direction == Direction.UP:
                    dy = -dt
                elif player.direction == Direction.DOWN:
                    dy = dt

            player.x += dx
            player.y += dy
        self.prev_time = time.time()
