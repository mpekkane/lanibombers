"""
Mock server for testing the renderer.
Simulates a game server returning sprite index arrays.
"""

import os
import sys
import time
import random

from game_engine.entities import Direction, EntityType, DynamicEntity
from game_engine.entities.player import Player
from game_engine.entities.bomb import Bomb, BombType
from game_engine.game_engine import GameEngine
from game_engine.map_loader import load_map
from client_simulation import ClientSimulation

MAP_PATH = os.path.join(os.path.dirname(__file__), "assets", "maps", "ANZULABY.MNE")

# How many render frames between server state updates
SERVER_UPDATE_INTERVAL = 10


class MockServer:
    """Simulates a game server returning sprite index arrays"""

    def __init__(self, map_path=None):
        self.engine = GameEngine()
        if map_path == None:
            map_path = MAP_PATH
        map_data = load_map(map_path)
        self.engine.load_map(map_data)
        self.engine.start()
        self._init_players()
        self.start_time = time.time()
        self.last_damage_time = self.start_time
        self.last_bomb_time = self.start_time
        # Player 2 movement pattern: start position
        self.player2_start_x = 8
        self.player2_start_y = 18
        # Client simulator for client-side extrapolation
        self.client_simulation = ClientSimulation()
        self.frame_count = 0

    def _init_players(self):
        """Initialize mock players"""
        self.engine._create_players(
            [
                Player(
                    x=9,
                    y=9,
                    direction=Direction.RIGHT,
                    name="Player1",
                    color=(255, 0, 0),
                    sprite_id=1,
                    state="dig",
                ),
                Player(
                    x=8,
                    y=18,
                    direction=Direction.RIGHT,
                    entity_type=EntityType.PLAYER,
                    name="Player2",
                    color=(0, 255, 0),
                    sprite_id=2,
                    state="walk",
                    speed=1.5,
                ),
            ]
        )

    def _update_player2_movement(self):
        """Move player 2 in a square pattern"""
        elapsed = time.time() - self.start_time
        # Pattern: 4s right, 1s stop, 4s down, 1s stop, 4s left, 1s stop, 4s up, 1s stop = 20s cycle
        # Speed: 1.5 blocks/second (6 blocks in 4 seconds)
        cycle_time = elapsed % 20.0
        player = self.engine.players[1]
        speed = 1.5  # blocks per second

        if cycle_time < 4.0:
            # Moving right
            player.x = self.player2_start_x + cycle_time * speed
            player.y = self.player2_start_y
            player.direction = Direction.RIGHT
            player.state = "walk"
        elif cycle_time < 5.0:
            # Stopped after right
            player.x = self.player2_start_x + 6
            player.y = self.player2_start_y
            player.direction = Direction.RIGHT
            player.state = "idle"
        elif cycle_time < 9.0:
            # Moving down
            player.x = self.player2_start_x + 6
            player.y = self.player2_start_y + (cycle_time - 5.0) * speed
            player.direction = Direction.DOWN
            player.state = "walk"
        elif cycle_time < 10.0:
            # Stopped after down
            player.x = self.player2_start_x + 6
            player.y = self.player2_start_y + 6
            player.direction = Direction.DOWN
            player.state = "idle"
        elif cycle_time < 14.0:
            # Moving left
            player.x = self.player2_start_x + 6 - (cycle_time - 10.0) * speed
            player.y = self.player2_start_y + 6
            player.direction = Direction.LEFT
            player.state = "walk"
        elif cycle_time < 15.0:
            # Stopped after left
            player.x = self.player2_start_x
            player.y = self.player2_start_y + 6
            player.direction = Direction.LEFT
            player.state = "idle"
        elif cycle_time < 19.0:
            # Moving up
            player.x = self.player2_start_x
            player.y = self.player2_start_y + 6 - (cycle_time - 15.0) * speed
            player.direction = Direction.UP
            player.state = "walk"
        else:
            # Stopped after up
            player.x = self.player2_start_x
            player.y = self.player2_start_y
            player.direction = Direction.UP
            player.state = "idle"

    def _update_random_damage(self):
        """Deal damage to a random player and monster every 10 seconds"""
        current_time = time.time()
        if current_time - self.last_damage_time >= 10.0:
            self.last_damage_time = current_time

            # Damage a random alive player
            alive_players = [p for p in self.engine.players if p.state != "dead"]
            if alive_players:
                player = random.choice(alive_players)
                player.take_damage(100)

            # Damage a random alive monster
            alive_monsters = [m for m in self.engine.monsters if m.state != "dead"]
            if alive_monsters:
                monster = random.choice(alive_monsters)
                monster.take_damage(100)

    def _spawn_random_bomb(self):
        """Spawn a bomb at a random location every .5 seconds"""
        current_time = time.time()
        if current_time - self.last_bomb_time >= 0.5:
            self.last_bomb_time = current_time

            # Random position in playable area
            x = random.randint(5, 58)
            y = random.randint(5, 40)

            # Create bomb
            bomb = Bomb(
                x=x,
                y=y,
                bomb_type=BombType.BIG_BOMB,
                placed_at=current_time,
                owner_id=None,
            )
            self.engine.plant_bomb(bomb)

    def get_render_state(self):
        """Returns extrapolated RenderState, polling server every N frames"""
        self.frame_count += 1

        # Only poll actual server state every SERVER_UPDATE_INTERVAL frames
        if self.frame_count % SERVER_UPDATE_INTERVAL == 1:
            self._update_player2_movement()
            self._update_random_damage()
            self._spawn_random_bomb()
            server_state = self.engine.get_render_state()
            self.client_simulation.receive_state(server_state)

        return self.client_simulation.get_render_state()


def main():
    import arcade
    from renderer.game_renderer import GameRenderer

    filename = None
    if len(sys.argv) > 1:
        filename = sys.argv[1]

    server = MockServer(filename)
    state = server.get_render_state()
    print(f"Loaded map: {state.width}x{state.height}")

    renderer = GameRenderer(server)
    arcade.run()


if __name__ == "__main__":
    main()
