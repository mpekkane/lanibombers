import random
from renderer.shop_renderer import ShopView
from game_engine.shop import Shop
from uuid import UUID
from game_engine.session_parser import SessionPlayer
from game_engine.state_machine import ClientStateMachine, ClientState, ClientStateAction
from common.item_dictionary import READY_ITEM


class ShopAI:
    """Simple random AI for enemy players in the shop."""

    def __init__(
        self,
        id: UUID,
        name: str,
        shop: Shop,
        cols: int,
        callback: callable,
        left: int,
        right: int,
        up: int,
        down: int,
        fire: int
    ):
        self.id = id
        self.name = name
        self.shop = shop
        self.cols = cols
        self.num_items = len(shop.items)
        self.cursor_idx = 0
        self.ready = False
        self.max_actions = 50
        self.actions = 0

        self.fx = callback
        self.left = left
        self.right = right
        self.up = up
        self.down = down
        self.fire = fire

    def tick(self, item) -> None:
        if self.shop.get_player_state(self.name):
            return

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
        if (
            self.shop.get_player(self.name).money < cheapest
            or self.actions > self.max_actions
        ):
            ready_idx = self.num_items - 1  # Ready is last item
            if item != "ready":
                self._move_toward(ready_idx)
            else:
                self._try_purchase()
            return

        # 60% chance to move, 40% chance to buy
        if random.random() < 0.6:
            self._random_move()
        else:
            self._try_purchase()

    def _random_move(self) -> None:
        action = random.choice([self.left, self.right, self.up, self.down])
        self.fx(action, 0)

    def _move_toward(self, target: int) -> None:
        """Move one step toward a target item index."""
        cur_row = self.cursor_idx // self.cols
        cur_col = self.cursor_idx % self.cols
        tgt_row = target // self.cols
        tgt_col = target % self.cols

        if cur_row < tgt_row:
            self.fx(self.down, 0)
        elif cur_row > tgt_row:
            self.fx(self.up, 0)
            return

        if cur_col < tgt_col:
            self.fx(self.right, 0)
        elif cur_col > tgt_col:
            self.fx(self.left, 0)

    def _try_purchase(self) -> None:
        """Try to buy the item at the current cursor position."""
        self.fx(self.fire, 0)
