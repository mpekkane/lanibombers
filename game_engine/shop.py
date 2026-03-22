from typing import List, Optional, Dict, Any, Union, Tuple
from cfg.bomb_dictionary import BombType
from cfg.item_dictionary import PowerupType, READY_ITEM, ItemType
from game_engine.entities import Player
from game_engine.render_state import RenderState
from cfg.tile_dictionary import EMPTY_TILE_ID, DIRT_TILE_ID, ROCK1_TILE_ID
import random
from game_engine.entities.pickup import Pickup, PickupType
import numpy as np
from game_engine.entities.tool import TOOL_DIG_POWER, ToolType
from uuid import UUID


class Shop:
    def __init__(self, players: List[Player], dynamic_pricing: bool) -> None:
        self.players = players
        self.state = []
        for p in self.players:
            self.state.append((p.name, False))
        self.dynamic_pricing = dynamic_pricing
        self.items = [
            (BombType.SMALL_BOMB, 10),
            (BombType.BIG_BOMB, 25),
            (BombType.DYNAMITE, 30),
            (BombType.C4, 50),
            (BombType.LANDMINE, 20),
            (BombType.SMALL_REMOTE, 40),
            (BombType.BIG_REMOTE, 60),
            (BombType.URETHANE, 35),
            (BombType.SMALL_CROSS_BOMB, 45),
            (BombType.BIG_CROSS_BOMB, 80),
            (BombType.NUKE, 200),
            (BombType.GRASSHOPPER, 55),
            (BombType.FLAME_BARREL, 40),
            (BombType.CRACKER_BARREL, 45),
            (BombType.DIGGER_BOMB, 30),
            (BombType.BIOSLIME, 25),
            (BombType.METAL_PLATE, 15),
            (BombType.FLAMETHROWER, 70),
            (BombType.FIRE_EXTINGUISHER, 50),
            (BombType.CLONE, 80),
            (BombType.TELEPORT, 60),
            (BombType.GRENADE, 35),
            (PowerupType.KEVLAR_VEST, 100),
            (PowerupType.SUPER_DRILL, 150),
            (PowerupType.SMALL_PICK, 20),
            (PowerupType.BIG_PICK, 40),
            (PowerupType.DRILL, 60),
            (READY_ITEM, 0),
        ]

        self.tilemap = self.make_mock_tilemap()
        self.pickups = self.make_mock_pickups()

        self.cursor_positions: List[Tuple[UUID, ItemType | str]] = []
        for p in players:
            self.cursor_positions.append((p.id, self.items[0][0]))

    def get_state(self) -> RenderState:
        width, height = 64, 45
        return RenderState(
            width=width,
            height=height,
            tilemap=self.tilemap,
            explosions=np.zeros((height, width), dtype=np.uint8),
            players=self.players,
            pickups=self.pickups,
        )

    def get_player(self, player_name: str) -> Optional[Player]:
        for p in self.players:
            if p.name == player_name:
                return p
        else:
            return None

    def move(self, id: UUID, pos: Union[ItemType, str]):
        for idx, (p_id, p_pos) in enumerate(self.cursor_positions):
            if p_id == id:
                self.cursor_positions[idx] = (p_id, pos)

    def purchase(self, item_index: int, player_name: str) -> None:
        """Stub: deduct money and add item to inventory."""
        item, price = self.items[item_index]
        client_player = self.get_player(player_name)
        if client_player is None:
            return

        # Ready button is special
        if item == READY_ITEM:
            self.send_ready()
            for i, (name, state) in enumerate(self.state):
                if name == player_name:
                    self.state[i] = (name, True)

            all_ready = True
            for _, state in self.state:
                if not state:
                    all_ready = False
                    break
            if all_ready:
                print("*" * 40)
                print("All ready!")
                print("*" * 40)
            return

        if client_player.money < price:
            return
        client_player.money -= price

        # Powerups apply immediately, not added to bomb inventory
        if isinstance(item, PowerupType):
            self.apply_powerup(client_player, item)
            return

        # Add bomb to inventory or increment existing count
        for i, (bt, count) in enumerate(client_player.inventory):
            if bt == item:
                client_player.inventory[i] = (bt, count + 1)
                return
        client_player.inventory.append((item, 1))

    def apply_powerup(self, player: Player, item: PowerupType) -> None:
        """Apply a powerup to a player."""
        if item == PowerupType.KEVLAR_VEST:
            player.health += 50
            return
        dp = TOOL_DIG_POWER.get(ToolType.from_powerup(item))
        if dp is not None:
            player.dig_power += dp

    def send_ready(self):
        """Stub: send ready message to server."""
        print("[STUB] Sending ready message to server")

    # ███╗   ███╗ ██████╗  ██████╗██╗  ██╗███████╗
    # ████╗ ████║██╔═══██╗██╔════╝██║ ██╔╝██╔════╝
    # ██╔████╔██║██║   ██║██║     █████╔╝ ███████╗
    # ██║╚██╔╝██║██║   ██║██║     ██╔═██╗ ╚════██║
    # ██║ ╚═╝ ██║╚██████╔╝╚██████╗██║  ██╗███████║
    # ╚═╝     ╚═╝ ╚═════╝  ╚═════╝╚═╝  ╚═╝╚══════╝

    def make_mock_tilemap(self, width: int = 64, height: int = 45) -> np.ndarray:
        """Generate a random tilemap for map preview."""
        tiles = np.full((height, width), EMPTY_TILE_ID, dtype=np.uint8)

        # Fill borders with bedrock
        tiles[0, :] = ROCK1_TILE_ID
        tiles[-1, :] = ROCK1_TILE_ID
        tiles[:, 0] = ROCK1_TILE_ID
        tiles[:, -1] = ROCK1_TILE_ID

        # Scatter dirt and bedrock randomly
        for y in range(1, height - 1):
            for x in range(1, width - 1):
                r = random.random()
                if r < 0.5:
                    tiles[y, x] = DIRT_TILE_ID
                elif r < 0.6:
                    tiles[y, x] = ROCK1_TILE_ID

        return tiles

    def make_mock_pickups(self) -> list[Pickup]:
        """Create some mock treasure pickups for map preview."""
        pickups = []
        for _ in range(15):
            pickups.append(
                Pickup(
                    x=random.randint(2, 61),
                    y=random.randint(2, 42),
                    pickup_type=PickupType.TREASURE,
                    value=100,
                )
            )
        return pickups
