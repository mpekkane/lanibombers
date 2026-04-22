"""
Test client for the shop renderer.
Populates mock data and opens the shop window for visual testing.
"""

import random


from common.bomb_dictionary import BombType
from common.item_dictionary import READY_ITEM

from common.config_reader import ConfigReader
from common.keymapper import map_keys

from game_engine.entities.player import Player

import arcade
from renderer.lanibombers_window import LanibombersWindow
from renderer.shop_renderer import ShopView
from game_engine.shop import Shop
from uuid import UUID


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
            money=random.randint(100, 1000),
            x=float(5 + i * 4),
            y=float(5 + (i % 5) * 8),
        )
        enemy.dig_power = random.randint(5, 30)
        enemy.inventory = list(STARTER_INVENTORIES[i % len(STARTER_INVENTORIES)])
        players.append(enemy)

    return players


class EnemyAI:
    """Simple random AI for enemy players in the shop."""

    def __init__(
        self,
        id: UUID,
        name: str,
        player_index: int,
        shop: Shop,
        cols: int,
    ):
        self.id = id
        self.name = name
        self.player_index = player_index
        self.shop = shop
        self.cols = cols
        self.num_items = len(shop.items)
        self.cursor_idx = 0
        self.timer = random.uniform(1.0, 3.0)  # Initial delay before first action
        self.ready = False
        self.max_actions = 50
        self.actions = 0

    def tick(self, dt: float) -> None:
        if self.ready:
            return

        self.timer -= dt
        if self.timer > 0:
            return

        # Schedule next action (slow, 0.3-1.5s between actions)
        self.timer = random.uniform(0.1, 0.5)

        self.actions += 1
        # If out of money, navigate toward ready button and press it
        cheapest = min(
            (
                price
                for item, price in self.shop.items
                if item != READY_ITEM and price > 0
            ),
            default=0,
        )
        if self.shop.get_player(self.name).money < cheapest or self.actions > self.max_actions:
            ready_idx = self.num_items - 1  # Ready is last item
            if self.cursor_idx != ready_idx:
                self._move_toward(ready_idx)
            else:
                self.ready = True
                self._try_purchase()
                print(f"[AI] {self.name} is ready")
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
        self.shop.purchase(self.cursor_idx, self.name)

    def _update_cursor(self) -> None:
        """Update this player's entry in the shared cursor_positions list."""
        self.shop.move(
            self.id,
            self.shop.items[self.cursor_idx][0],
        )


def main():
    players = make_mock_players()

    shop = Shop(players, False)

    # preview

    client_player = players[0]

    # Read keybinds from player config
    config = ConfigReader("cfg/player.yaml")
    key_up, key_down, key_left, key_right, key_fire, _, _, _ = map_keys(config)

    cols = 4
    num_items = len(shop.items)

    # Mutable cursor index
    cursor = [0]

    # Cursor positions list shared with renderer (mutated in place)

    # Create enemy AI for each non-client player
    enemy_ais = []
    for i, p in enumerate(players[1:], start=1):
        enemy_ais.append(EnemyAI(p.id, p.name, i, shop, cols))

    window = LanibombersWindow()
    shopview = ShopView(
        get_state=shop.get_state,
        client_player_name="TestPlayer",
        shop_items=shop.items,
        cursor_positions=shop.cursor_positions,
        next_map_tiles=shop.tilemap,
        rounds_left=5,
    )

    # Hook into on_update for enemy AI ticks
    # Must patch BEFORE show_view so pyglet captures the patched methods
    original_on_update = shopview.on_update

    def on_update(delta_time: float):
        for ai in enemy_ais:
            ai.tick(delta_time)
        original_on_update(delta_time)

    shopview.on_update = on_update  # type: ignore[assignment]

    # Override on_key_press for shop navigation
    original_on_key_press = shopview.on_key_press

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
            shop.purchase(cursor[0], client_player.name)
        else:
            original_on_key_press(symbol, modifiers)
            return

        # Update cursor position in the shared list
        # shop.cursor_positions[0] = (client_player.id, shop.items[cursor[0]][0])
        shop.move(client_player.id, shop.items[cursor[0]][0])

    shopview.on_key_press = on_key_press  # type: ignore[assignment]

    window.show_view(shopview)
    arcade.run()


if __name__ == "__main__":
    main()
