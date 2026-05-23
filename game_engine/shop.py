from typing import List, Optional, Union, Tuple
from common.bomb_dictionary import BombType
from common.item_dictionary import PowerupType, READY_ITEM, ItemType
from game_engine.session_parser import (
    SessionPlayer,
)
from game_engine.render_state import RenderState, ShopRenderState
from common.tile_dictionary import EMPTY_TILE_ID, DIRT_TILE_ID, ROCK1_TILE_ID
import random
from game_engine.entities.pickup import Pickup, PickupType
import numpy as np
from game_engine.entities.tool import TOOL_DIG_POWER, ToolType
from uuid import UUID
from game_engine.agent_state import Action


class Shop:
    def __init__(self, players: List[SessionPlayer], dynamic_pricing: bool) -> None:
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

        self.COLS = 4

        self.tilemap = self.make_mock_tilemap()
        self.pickups = self.make_mock_pickups()

        self.cursor_positions: List[Tuple[UUID, ItemType | str]] = []
        self.cursor_visual_positions: List[Tuple[UUID, int]] = []
        for p in players:
            self.cursor_positions.append((p.id, self.items[0][0]))
            self.cursor_visual_positions.append((p.id, 0))

    def update_state(self, items, state, cursor_positions):
        self.items = items
        self.state = state
        self.cursor_positions = cursor_positions

    def get_state(self) -> ShopRenderState:
        width, height = 64, 45

        gps = [p.to_player() for p in self.players]
        renderState = RenderState(
            width=width,
            height=height,
            tilemap=self.tilemap,
            explosions=np.zeros((height, width), dtype=np.uint8),
            players=gps,
            pickups=self.pickups,
        )

        return ShopRenderState(
            renderState=renderState, cursor_positions=self.cursor_positions
        )

    def get_player(self, player_name: str) -> Optional[SessionPlayer]:
        for p in self.players:
            if p.name == player_name:
                return p
        else:
            return None

    def get_player_by_id(self, id: UUID) -> Optional[SessionPlayer]:
        for p in self.players:
            if p.id == id:
                return p
        else:
            return None

    def move_player(self, id: UUID, action: Action):
        old = None
        for pid, vp in self.cursor_visual_positions:
            if pid == id:
                old = vp
        assert old is not None, "Player id not found in shop"
        num_items = len(self.items)

        row = old // self.COLS
        col = old % self.COLS
        max_row = (num_items - 1) // self.COLS

        new_pos = old
        if action == Action.UP:
            if row > 0:
                new_pos = (row - 1) * self.COLS + col
        elif action == Action.DOWN:
            new = (row + 1) * self.COLS + col
            if row < max_row and new < num_items:
                new_pos = new
        elif action == Action.LEFT:
            if col > 0:
                new_pos = row * self.COLS + (col - 1)
        elif action == Action.RIGHT:
            new = row * self.COLS + (col + 1)
            if col < self.COLS - 1 and new < num_items:
                new_pos = new

        print(f"Shop: move from {old} to {new_pos}")

        new_item = self.items[new_pos]
        self.move(id, new_item)
        for idx, (p_id, p_pos) in enumerate(self.cursor_visual_positions):
            if p_id == id:
                self.cursor_visual_positions[idx] = (p_id, new_pos)

    def move(self, id: UUID, pos: Union[ItemType, str]):
        for idx, (p_id, p_pos) in enumerate(self.cursor_positions):
            if p_id == id:
                self.cursor_positions[idx] = (p_id, pos)

    def get_player_cursor(self, id: UUID) -> Tuple[UUID, ItemType | str]:
        for idx, (p_id, p_pos) in enumerate(self.cursor_positions):
            if p_id == id:
                return self.cursor_positions[idx]

        raise ValueError("Unknown player")

    def get_player_cursor_index(self, id: UUID) -> Tuple[UUID, int]:
        for idx, (p_id, p_pos) in enumerate(self.cursor_visual_positions):
            if p_id == id:
                return self.cursor_visual_positions[idx]

        raise ValueError("Unknown player")

    def purchase_current(self, id: UUID) -> None:
        uid, idx = self.get_player_cursor_index(id)
        player = self.get_player_by_id(id)
        if player is None:
            return
        return self.purchase(idx, player.name)

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

        print(f"Shop: purchase {item_index}")

    def apply_powerup(self, player: SessionPlayer, item: PowerupType) -> None:
        """Apply a powerup to a player."""
        if item == PowerupType.KEVLAR_VEST:
            player.max_health += 50
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
