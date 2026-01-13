"""
Mock server for testing the renderer.
Simulates a game server returning sprite index arrays.
"""

import os
import time
import array
import random

from cfg.tile_dictionary import EMPTY_TILE_ID, MONSTER_SPAWN_TILES
from game_engine.entities import Direction, EntityType, DynamicEntity
from game_engine.render_state import RenderState


MAP_PATH = os.path.join(os.path.dirname(__file__), 'assets', 'maps', 'ANZULABY.MNE')


class MockServer:
    """Simulates a game server returning sprite index arrays"""

    def __init__(self, map_path=MAP_PATH):
        self._load_map(map_path)
        self._init_players()
        self._init_monsters()

    def _load_map(self, path):
        """Load map from ASCII file, sprite indices are ASCII values"""
        self.grid = array.array('B')
        with open(path, 'rb') as f:
            for line in f:
                line = line.rstrip(b'\r\n')
                for char in line:
                    self.grid.append(char)
        self.height = 45
        self.width = 64

    def _init_players(self):
        """Initialize mock players"""
        self.players = [
            DynamicEntity(x=9, y=9, direction=Direction.RIGHT, entity_type=EntityType.PLAYER, name='Player1', colour=(255, 0, 0), sprite_id=1, state='dig'),
            DynamicEntity(x=8, y=18, direction=Direction.RIGHT, entity_type=EntityType.PLAYER, name='Player2', colour=(0, 255, 0), sprite_id=2, state='walk'),
        ]
        self.start_time = time.time()
        self.last_damage_time = self.start_time
        # Player 2 movement pattern: start position
        self.player2_start_x = 8
        self.player2_start_y = 18

    def _update_player2_movement(self):
        """Move player 2 in a square pattern"""
        elapsed = time.time() - self.start_time
        # Pattern: 4s right, 1s stop, 4s down, 1s stop, 4s left, 1s stop, 4s up, 1s stop = 20s cycle
        # Speed: 1.5 blocks/second (6 blocks in 4 seconds)
        cycle_time = elapsed % 20.0
        player = self.players[1]
        speed = 1.5  # blocks per second

        if cycle_time < 4.0:
            # Moving right
            player.x = self.player2_start_x + cycle_time * speed
            player.y = self.player2_start_y
            player.direction = Direction.RIGHT
            player.state = 'walk'
        elif cycle_time < 5.0:
            # Stopped after right
            player.x = self.player2_start_x + 6
            player.y = self.player2_start_y
            player.direction = Direction.RIGHT
            player.state = 'idle'
        elif cycle_time < 9.0:
            # Moving down
            player.x = self.player2_start_x + 6
            player.y = self.player2_start_y + (cycle_time - 5.0) * speed
            player.direction = Direction.DOWN
            player.state = 'walk'
        elif cycle_time < 10.0:
            # Stopped after down
            player.x = self.player2_start_x + 6
            player.y = self.player2_start_y + 6
            player.direction = Direction.DOWN
            player.state = 'idle'
        elif cycle_time < 14.0:
            # Moving left
            player.x = self.player2_start_x + 6 - (cycle_time - 10.0) * speed
            player.y = self.player2_start_y + 6
            player.direction = Direction.LEFT
            player.state = 'walk'
        elif cycle_time < 15.0:
            # Stopped after left
            player.x = self.player2_start_x
            player.y = self.player2_start_y + 6
            player.direction = Direction.LEFT
            player.state = 'idle'
        elif cycle_time < 19.0:
            # Moving up
            player.x = self.player2_start_x
            player.y = self.player2_start_y + 6 - (cycle_time - 15.0) * speed
            player.direction = Direction.UP
            player.state = 'walk'
        else:
            # Stopped after up
            player.x = self.player2_start_x
            player.y = self.player2_start_y
            player.direction = Direction.UP
            player.state = 'idle'

    def _init_monsters(self):
        """Initialize monsters from spawn tiles in the map"""
        self.monsters = []

        for i, tile_id in enumerate(self.grid):
            if tile_id in MONSTER_SPAWN_TILES:
                entity_type, direction = MONSTER_SPAWN_TILES[tile_id]
                x = i % self.width
                y = i // self.width

                monster = DynamicEntity(
                    x=x,
                    y=y,
                    direction=direction,
                    entity_type=entity_type,
                    state='walk'
                )
                self.monsters.append(monster)

                # Replace spawn tile with empty
                self.grid[i] = EMPTY_TILE_ID

    def _update_random_damage(self):
        """Deal damage to a random player and monster every 10 seconds"""
        current_time = time.time()
        if current_time - self.last_damage_time >= 10.0:
            self.last_damage_time = current_time

            # Damage a random alive player
            alive_players = [p for p in self.players if p.state != 'dead']
            if alive_players:
                player = random.choice(alive_players)
                player.take_damage(100)

            # Damage a random alive monster
            alive_monsters = [m for m in self.monsters if m.state != 'dead']
            if alive_monsters:
                monster = random.choice(alive_monsters)
                monster.take_damage(100)

    def get_render_state(self):
        """Returns RenderState with dimensions and sprite indices"""
        self._update_player2_movement()
        self._update_random_damage()
        return RenderState(
            width=self.width,
            height=self.height,
            tilemap=self.grid,
            players=self.players,
            monsters=self.monsters,
            pickups=[],
            bombs=[]
        )
