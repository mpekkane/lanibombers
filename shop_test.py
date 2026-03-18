"""
Test client for the shop renderer.
Populates mock data and opens the shop window for visual testing.
"""

import random
import numpy as np

from cfg.bomb_dictionary import BombType
from cfg.item_dictionary import PowerupType, READY_ITEM
from cfg.tile_dictionary import EMPTY_TILE_ID, DIRT_TILE_ID, ROCK1_TILE_ID
from common.config_reader import ConfigReader
from common.keymapper import map_keys
from game_engine.render_state import RenderState
from game_engine.entities.player import Player
from game_engine.entities.pickup import Pickup, PickupType
import arcade
from renderer.lanibombers_window import LanibombersWindow
from renderer.shop_renderer import ShopView


def make_mock_tilemap(width: int = 64, height: int = 45) -> np.ndarray:
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


ENEMY_COLORS = [
    (0xDB, 0x00, 0x00),
    (0x00, 0xA3, 0x00),
    (0xCC, 0xCC, 0x00),
    (0x80, 0x00, 0xCC),
    (0x00, 0x8B, 0x8B),
    (0xCC, 0x66, 0x00),
    (0xFF, 0x69, 0xB4),
    (0x55, 0x55, 0xDD),
    (0xAA, 0x55, 0x00),
    (0x00, 0xDD, 0xDD),
    (0xDD, 0x55, 0x55),
    (0x55, 0xAA, 0x55),
    (0xBB, 0xBB, 0x55),
    (0xAA, 0x00, 0x88),
    (0x88, 0x88, 0x88),
]

STARTER_INVENTORIES = [
    [(BombType.SMALL_BOMB, 20), (BombType.DYNAMITE, 5), (BombType.NUKE, 1)],
    [(BombType.SMALL_BOMB, 10), (BombType.BIG_BOMB, 25), (BombType.C4, 3)],
    [(BombType.SMALL_BOMB, 15), (BombType.BIG_BOMB, 5), (BombType.GRENADE, 3)],
    [(BombType.SMALL_BOMB, 40), (BombType.LANDMINE, 10)],
    [(BombType.SMALL_BOMB, 5), (BombType.URETHANE, 8), (BombType.FLAMETHROWER, 2)],
]


def make_mock_players() -> list[Player]:
    """Create mock players for testing (1 client + 15 enemies = 16 total)."""
    p1 = Player(
        name="TestPlayer",
        sprite_id=1,
        color=(0x00, 0x00, 0x8B),
        money=1500,
        x=5.0,
        y=5.0,
    )
    p1.dig_power = 25
    p1.inventory = [
        (BombType.SMALL_BOMB, 30),
        (BombType.BIG_BOMB, 15),
        (BombType.DYNAMITE, 8),
        (BombType.C4, 5),
        (BombType.LANDMINE, 12),
        (BombType.URETHANE, 20),
        (BombType.NUKE, 2),
        (BombType.GRENADE, 10),
    ]

    players = [p1]
    for i in range(15):
        enemy = Player(
            name=f"Enemy{i + 1}",
            sprite_id=(i % 4) + 1,
            color=ENEMY_COLORS[i],
            money=random.randint(400, 2000),
            x=float(5 + i * 4),
            y=float(5 + (i % 5) * 8),
        )
        enemy.dig_power = random.randint(5, 30)
        enemy.inventory = list(STARTER_INVENTORIES[i % len(STARTER_INVENTORIES)])
        players.append(enemy)

    return players


def make_mock_pickups() -> list[Pickup]:
    """Create some mock treasure pickups for map preview."""
    pickups = []
    for _ in range(15):
        pickups.append(Pickup(
            x=random.randint(2, 61),
            y=random.randint(2, 42),
            pickup_type=PickupType.TREASURE,
            value=100,
        ))
    return pickups


def make_shop_items():
    """Create the shop item list with prices."""
    return [
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


DIG_POWER_VALUES = {
    PowerupType.SMALL_PICK: 5,
    PowerupType.BIG_PICK: 10,
    PowerupType.DRILL: 20,
    PowerupType.SUPER_DRILL: 50,
}


def apply_powerup(player: Player, item: PowerupType) -> None:
    """Apply a powerup to a player."""
    if item == PowerupType.KEVLAR_VEST:
        player.health += 50
        return
    dp = DIG_POWER_VALUES.get(item)
    if dp is not None:
        player.dig_power += dp


def send_ready():
    """Stub: send ready message to server."""
    print("[STUB] Sending ready message to server")


class EnemyAI:
    """Simple random AI for enemy players in the shop."""

    def __init__(self, player: Player, player_index: int, shop_items: list,
                 cursor_positions: list, cols: int):
        self.player = player
        self.player_index = player_index
        self.shop_items = shop_items
        self.cursor_positions = cursor_positions
        self.cols = cols
        self.num_items = len(shop_items)
        self.cursor_idx = 0
        self.timer = random.uniform(1.0, 3.0)  # Initial delay before first action
        self.ready = False

    def tick(self, dt: float) -> None:
        if self.ready:
            return

        self.timer -= dt
        if self.timer > 0:
            return

        # Schedule next action (slow, 0.3-1.5s between actions)
        self.timer = random.uniform(0.3, 1.5)

        # If out of money, navigate toward ready button and press it
        cheapest = min(
            (price for item, price in self.shop_items if item != READY_ITEM and price > 0),
            default=0,
        )
        if self.player.money < cheapest:
            ready_idx = self.num_items - 1  # Ready is last item
            if self.cursor_idx != ready_idx:
                self._move_toward(ready_idx)
            else:
                self.ready = True
                print(f"[AI] {self.player.name} is ready")
            self._update_cursor()
            return

        # 60% chance to move, 40% chance to buy
        if random.random() < 0.6:
            self._random_move()
        else:
            self._try_purchase()

        self._update_cursor()

    def _random_move(self) -> None:
        """Move cursor one step in a random direction."""
        row = self.cursor_idx // self.cols
        col = self.cursor_idx % self.cols
        max_row = (self.num_items - 1) // self.cols

        directions = []
        if row > 0:
            directions.append(-self.cols)  # up
        if row < max_row:
            new = self.cursor_idx + self.cols
            if new < self.num_items:
                directions.append(self.cols)  # down
        if col > 0:
            directions.append(-1)  # left
        if col < self.cols - 1 and self.cursor_idx + 1 < self.num_items:
            directions.append(1)  # right

        if directions:
            self.cursor_idx += random.choice(directions)

    def _move_toward(self, target: int) -> None:
        """Move one step toward a target item index."""
        cur_row = self.cursor_idx // self.cols
        cur_col = self.cursor_idx % self.cols
        tgt_row = target // self.cols
        tgt_col = target % self.cols

        if cur_row < tgt_row:
            new = self.cursor_idx + self.cols
            if new < self.num_items:
                self.cursor_idx = new
                return
        elif cur_row > tgt_row:
            self.cursor_idx -= self.cols
            return

        if cur_col < tgt_col:
            self.cursor_idx += 1
        elif cur_col > tgt_col:
            self.cursor_idx -= 1

    def _try_purchase(self) -> None:
        """Try to buy the item at the current cursor position."""
        item, price = self.shop_items[self.cursor_idx]
        if item == READY_ITEM:
            return
        if price > self.player.money:
            return
        self.player.money -= price

        if isinstance(item, PowerupType):
            apply_powerup(self.player, item)
            return

        for i, (bt, count) in enumerate(self.player.inventory):
            if bt == item:
                self.player.inventory[i] = (bt, count + 1)
                return
        self.player.inventory.append((item, 1))

    def _update_cursor(self) -> None:
        """Update this player's entry in the shared cursor_positions list."""
        self.cursor_positions[self.player_index] = (
            self.player.id, self.shop_items[self.cursor_idx][0]
        )


def main():
    tilemap = make_mock_tilemap()
    players = make_mock_players()
    pickups = make_mock_pickups()
    shop_items = make_shop_items()
    client_player = players[0]

    # Read keybinds from player config
    config = ConfigReader("cfg/player.yaml")
    key_up, key_down, key_left, key_right, key_fire, _, _, _ = map_keys(config)

    width, height = 64, 45
    cols = 4
    num_items = len(shop_items)

    # Mutable cursor index
    cursor = [0]

    # Cursor positions list shared with renderer (mutated in place)
    cursor_positions = [
        (client_player.id, shop_items[cursor[0]][0]),
    ]
    for p in players[1:]:
        cursor_positions.append((p.id, shop_items[0][0]))

    def get_state() -> RenderState:
        return RenderState(
            width=width,
            height=height,
            tilemap=tilemap,
            explosions=np.zeros((height, width), dtype=np.uint8),
            players=players,
            pickups=pickups,
        )

    def purchase(item_index: int) -> None:
        """Stub: deduct money and add item to inventory."""
        item, price = shop_items[item_index]

        # Ready button is special
        if item == READY_ITEM:
            send_ready()
            return

        if client_player.money < price:
            return
        client_player.money -= price

        # Powerups apply immediately, not added to bomb inventory
        if isinstance(item, PowerupType):
            apply_powerup(client_player, item)
            return

        # Add bomb to inventory or increment existing count
        for i, (bt, count) in enumerate(client_player.inventory):
            if bt == item:
                client_player.inventory[i] = (bt, count + 1)
                return
        client_player.inventory.append((item, 1))

    # Create enemy AI for each non-client player
    enemy_ais = []
    for i, p in enumerate(players[1:], start=1):
        enemy_ais.append(EnemyAI(p, i, shop_items, cursor_positions, cols))

    window = LanibombersWindow()
    shop = ShopView(
        get_state=get_state,
        client_player_name="TestPlayer",
        shop_items=shop_items,
        cursor_positions=cursor_positions,
        next_map_tiles=tilemap,
        rounds_left=5,
    )
    window.show_view(shop)

    # Hook into on_update for enemy AI ticks
    original_on_update = shop.on_update

    def on_update(delta_time: float):
        for ai in enemy_ais:
            ai.tick(delta_time)
        original_on_update(delta_time)

    shop.on_update = on_update  # type: ignore[assignment]

    # Override on_key_press for shop navigation
    original_on_key_press = shop.on_key_press

    def on_key_press(symbol: int, modifiers: int):
        old = cursor[0]
        row = old // cols
        col = old % cols
        max_row = (num_items - 1) // cols

        if symbol == key_up:
            if row > 0:
                cursor[0] = (row - 1) * cols + col
        elif symbol == key_down:
            new = (row + 1) * cols + col
            if row < max_row and new < num_items:
                cursor[0] = new
        elif symbol == key_left:
            if col > 0:
                cursor[0] = row * cols + (col - 1)
        elif symbol == key_right:
            new = row * cols + (col + 1)
            if col < cols - 1 and new < num_items:
                cursor[0] = new
        elif symbol == key_fire:
            purchase(cursor[0])
        else:
            original_on_key_press(symbol, modifiers)
            return

        # Update cursor position in the shared list
        cursor_positions[0] = (client_player.id, shop_items[cursor[0]][0])

    shop.on_key_press = on_key_press  # type: ignore[assignment]
    arcade.run()


if __name__ == "__main__":
    main()
