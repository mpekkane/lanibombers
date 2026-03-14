"""
Shop screen renderer for lanibombers.
Players purchase weapons and items for the next round.
"""

import os
from typing import Callable, List, Tuple
from uuid import UUID

import arcade
import numpy as np
from PIL import Image

from cfg.bomb_dictionary import BombType
from cfg.item_dictionary import ItemType, get_item_icon
from game_engine.render_state import RenderState
from game_engine.entities.player import Player
from renderer.bitmap_text import BitmapText
from renderer.panel_builder import PanelBuilder
from renderer.player_colorizer import PlayerColorizer

SPRITES_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "sprites")
GRAPHICS_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "graphics")


class ShopRenderer(arcade.Window):
    """Shop screen where players buy weapons/items between rounds."""

    def __init__(
        self,
        get_state: Callable[[], RenderState],
        client_player_name: str,
        shop_items: List[Tuple[ItemType | str, int]],
        cursor_positions: List[Tuple[UUID, ItemType | str]],
        next_map_tiles: np.ndarray,
        width: int = 1708,
        height: int = 960,
    ):
        super().__init__(width, height, "lanibombers - Shop", vsync=True)
        self.get_state = get_state
        self.client_player_name = client_player_name
        self.shop_items = shop_items
        self.cursor_positions = cursor_positions
        self.next_map_tiles = next_map_tiles
        self.init_width = width
        self.init_height = height

    def initialize(self):
        """Set up rendering resources after window is ready."""
        self.zoom = min(self.init_width // 640, self.init_height // 480)

        # Load SHOPPIC.png background (640x480)
        bg_path = os.path.join(GRAPHICS_PATH, "SHOPPIC.png")
        bg_texture = arcade.load_texture(bg_path)
        self.bg_sprite = arcade.Sprite()
        self.bg_sprite.texture = bg_texture
        self.bg_sprite.scale = self.zoom
        self.bg_sprite.center_x = (640 / 2) * self.zoom
        self.bg_sprite.center_y = self.height - (480 / 2) * self.zoom
        self.bg_sprite_list = arcade.SpriteList()
        self.bg_sprite_list.append(self.bg_sprite)

        # BitmapText for all text rendering
        font_path = os.path.join(SPRITES_PATH, "font.png")
        self.bitmap_text = BitmapText(font_path, zoom=self.zoom)

        # Player info text sprite lists
        self.name_sprites = arcade.SpriteList()
        self.dig_power_sprites = arcade.SpriteList()
        self.money_sprites = arcade.SpriteList()
        self.item_qty_sprites = arcade.SpriteList()
        self.health_bar_sprites = arcade.SpriteList()

        # Cache for change detection
        self._cached_name = None
        self._cached_dig_power = None
        self._cached_money = None
        self._cached_item_qty = None
        self._cached_health = None

        # Map preview
        self.map_preview_sprite_list = arcade.SpriteList()
        self._build_map_preview(self.get_state())

        # Rounds left text
        self.rounds_left_sprites = arcade.SpriteList()

        # Load icon textures for all shop items
        self.icon_textures: dict[ItemType | str, arcade.Texture] = {}
        for item, _price in self.shop_items:
            icon_name = get_item_icon(item)
            if icon_name:
                path = os.path.join(SPRITES_PATH, f"{icon_name}_icon.png")
                if os.path.exists(path):
                    self.icon_textures[item] = arcade.load_texture(path)

        # Load item card background textures
        card_normal_path = os.path.join(SPRITES_PATH, "shop_card_normal.png")
        card_selected_path = os.path.join(SPRITES_PATH, "shop_card_selected.png")
        self.card_normal_texture = arcade.load_texture(card_normal_path)
        self._card_selected_image = Image.open(card_selected_path).convert("RGBA")

        # Caches for recolored selected card textures
        self._selected_card_cache: dict[tuple[int, int, int], arcade.Texture] = {}
        self._selected_image_cache: dict[tuple[int, int, int], Image.Image] = {}
        self._selected_strip_cache: dict[tuple[tuple[int, int, int], int, int], arcade.Texture] = {}

        # Item card sprite lists
        self.card_bg_sprites = arcade.SpriteList()
        self.card_icon_sprites = arcade.SpriteList()
        self.card_price_sprites = arcade.SpriteList()
        self._build_item_cards()

        # Quantity bar sprite list (rebuilt in on_update)
        self.quantity_bar_sprites = arcade.SpriteList()
        self._cached_inventory = None

        # Create a 1x1 white pixel texture for solid color bars
        white_img = Image.new("RGBA", (1, 1), (255, 255, 255, 255))
        self.white_texture = arcade.Texture(white_img, name="white_pixel")

        # Player colorizer for other player cards
        self.colorizer = PlayerColorizer(SPRITES_PATH)

        # Inventory overview bars (right side grid)
        self.overview_bar_sprites = arcade.SpriteList()
        self._cached_overview_key: object = None

        # Other players' card sprites
        self.other_player_sprites = arcade.SpriteList()
        self.other_player_name_sprites = arcade.SpriteList()
        self.other_player_info_sprites = arcade.SpriteList()
        self._cached_other_players = None

        # Panel builder for grey beveled panels
        self.panel_builder = PanelBuilder()

        # Build empty player card slots (up to 16 total, fill unused with panels)
        self.empty_card_sprites = arcade.SpriteList()
        card_x = 640
        card_w = 110
        card_h = 30
        icon_size = 30
        max_players = 16
        card_panel_texture = self.panel_builder.create_panel_texture(card_w, card_h)
        icon_panel_texture = self.panel_builder.create_panel_texture(icon_size, icon_size)
        # Slot 0: card panel + icon panel (above first enemy card)
        panel_0 = arcade.Sprite()
        panel_0.texture = card_panel_texture
        panel_0.scale = self.zoom
        panel_0.center_x = (card_x + card_w / 2) * self.zoom
        panel_0.center_y = self.height - (card_h / 2) * self.zoom
        self.empty_card_sprites.append(panel_0)

        icon_panel_0 = arcade.Sprite()
        icon_panel_0.texture = icon_panel_texture
        icon_panel_0.scale = self.zoom
        icon_panel_0.center_x = (card_x + card_w + icon_size / 2) * self.zoom
        icon_panel_0.center_y = self.height - (icon_size / 2) * self.zoom
        self.empty_card_sprites.append(icon_panel_0)

        # Slots 1..15: card panel + icon panel for other players
        for slot in range(1, max_players):
            slot_y = slot * card_h

            panel_sprite = arcade.Sprite()
            panel_sprite.texture = card_panel_texture
            panel_sprite.scale = self.zoom
            panel_sprite.center_x = (card_x + card_w / 2) * self.zoom
            panel_sprite.center_y = self.height - (slot_y + card_h / 2) * self.zoom
            self.empty_card_sprites.append(panel_sprite)

            icon_panel_sprite = arcade.Sprite()
            icon_panel_sprite.texture = icon_panel_texture
            icon_panel_sprite.scale = self.zoom
            icon_panel_sprite.center_x = (card_x + card_w + icon_size / 2) * self.zoom
            icon_panel_sprite.center_y = self.height - (slot_y + icon_size / 2) * self.zoom
            self.empty_card_sprites.append(icon_panel_sprite)

    def on_update(self, delta_time: float):  # noqa: ARG002
        state = self.get_state()

        # Find client player
        client_player = None
        for p in state.players:
            if p.name == self.client_player_name:
                client_player = p
                break

        if client_player is None:
            return

        # Find which shop item index the client player's cursor is on
        selected_index = -1
        for cursor_id, cursor_bomb in self.cursor_positions:
            if cursor_id == client_player.id:
                for idx, (item_type, _) in enumerate(self.shop_items):
                    if item_type == cursor_bomb:
                        selected_index = idx
                        break
                break

        # Text base position (design coords: 34, 16 at 1x)
        base_x = 34 * self.zoom
        base_y = self.height - 16 * self.zoom
        row_spacing = 14 * self.zoom

        # Row 0: Player name
        if client_player.name != self._cached_name:
            self._cached_name = client_player.name
            self.name_sprites = self.bitmap_text.create_text_sprites(
                client_player.name, base_x, base_y
            )

        # Row 1: Dig power
        if client_player.get_dig_power() != self._cached_dig_power:
            self._cached_dig_power = client_player.get_dig_power()
            self.dig_power_sprites = self.bitmap_text.create_text_sprites(
                str(client_player.get_dig_power()), base_x, base_y - row_spacing
            )

        # Row 2: Money
        if client_player.money != self._cached_money:
            self._cached_money = client_player.money
            self.money_sprites = self.bitmap_text.create_text_sprites(
                str(client_player.money), base_x, base_y - 2 * row_spacing
            )

        # Row 3: Count of item under cursor
        cursor_item = self.shop_items[selected_index][0] if 0 <= selected_index < len(self.shop_items) else None
        cursor_count = sum(c for bt, c in client_player.inventory if bt == cursor_item) if cursor_item else 0
        item_qty_key = (selected_index, cursor_count)
        if item_qty_key != self._cached_item_qty:
            self._cached_item_qty = item_qty_key
            self.item_qty_sprites = self.bitmap_text.create_text_sprites(
                str(cursor_count), base_x, base_y - 3 * row_spacing
            )

        # Quantity bars (rebuild if inventory or health changed)
        inventory_key = (tuple(client_player.inventory), client_player.health)
        if inventory_key != self._cached_inventory:
            self._cached_inventory = inventory_key
            self._build_quantity_bars(client_player)

        # Card backgrounds + inventory overview (rebuild if any cursor or inventory changed)
        overview_key = (
            selected_index,
            tuple(
                (p.name, p.color, tuple(p.inventory))
                for p in state.players
            ),
            tuple(self.cursor_positions),
        )
        if overview_key != self._cached_overview_key:
            self._cached_overview_key = overview_key
            self._build_card_backgrounds(selected_index, client_player.color, state.players)
            self._build_inventory_overview(state.players)

        # Other players' cards (rebuild if player data or cursors changed)
        other_key = (
            tuple(
                (p.name, p.sprite_id, p.color, p.money, p.get_dig_power(), p.health)
                for p in state.players
                if p.name != self.client_player_name
            ),
            tuple(self.cursor_positions),
        )
        if other_key != self._cached_other_players:
            self._cached_other_players = other_key
            self._build_other_player_cards(state.players)

    def on_draw(self):
        self.clear()
        self.default_camera.use()
        self.bg_sprite_list.draw(pixelated=True)
        self.name_sprites.draw(pixelated=True)
        self.dig_power_sprites.draw(pixelated=True)
        self.money_sprites.draw(pixelated=True)
        self.item_qty_sprites.draw(pixelated=True)
        self.map_preview_sprite_list.draw(pixelated=True)
        self.rounds_left_sprites.draw(pixelated=True)
        self.card_bg_sprites.draw(pixelated=True)
        self.card_icon_sprites.draw(pixelated=True)
        self.card_price_sprites.draw(pixelated=True)
        self.quantity_bar_sprites.draw(pixelated=True)
        self.overview_bar_sprites.draw(pixelated=True)
        self.empty_card_sprites.draw(pixelated=True)
        self.other_player_sprites.draw(pixelated=True)
        self.other_player_name_sprites.draw(pixelated=True)
        self.other_player_info_sprites.draw(pixelated=True)

    def _build_map_preview(self, state: RenderState) -> None:
        """Build the map preview sprite from next_map_tiles and treasure positions."""
        from cfg.tile_dictionary import (
            EMPTY_TILE_ID,
            DIRT_TILES,
            BEDROCK_TILES,
            BEDROCK_CORNER_TILES,
        )

        tiles = self.next_map_tiles
        h, w = tiles.shape

        # Create PIL image (1 pixel per tile)
        img = Image.new("RGBA", (w, h))
        pixels = img.load()
        assert pixels is not None

        COLOR_EMPTY = (101, 67, 33, 255)
        COLOR_DIRT = (181, 137, 87, 255)
        COLOR_BEDROCK = (128, 128, 128, 255)

        for y in range(h):
            for x in range(w):
                tile_id = int(tiles[y, x])
                if tile_id == EMPTY_TILE_ID:
                    pixels[x, y] = COLOR_EMPTY
                elif tile_id in DIRT_TILES:
                    pixels[x, y] = COLOR_DIRT
                elif tile_id in BEDROCK_TILES or tile_id in BEDROCK_CORNER_TILES:
                    pixels[x, y] = COLOR_BEDROCK
                else:
                    pixels[x, y] = COLOR_EMPTY

        # Overlay treasure positions (golden)
        COLOR_TREASURE = (255, 215, 0, 255)
        for pickup in state.pickups:
            px, py = int(pickup.x), int(pickup.y)
            if 0 <= px < w and 0 <= py < h:
                pixels[px, py] = COLOR_TREASURE

        texture = arcade.Texture(img, name="map_preview")
        sprite = arcade.Sprite()
        sprite.texture = texture
        sprite.scale = self.zoom
        sprite.center_x = (288 + w / 2) * self.zoom
        sprite.center_y = self.height - (51 + h / 2) * self.zoom

        self.map_preview_sprite_list = arcade.SpriteList()
        self.map_preview_sprite_list.append(sprite)

    def set_rounds_left(self, rounds: int) -> None:
        """Update the rounds left display text."""
        text = str(rounds)
        text_width = self.bitmap_text.get_text_width(text)
        center_x = 320 * self.zoom
        screen_y = self.height - 120 * self.zoom
        self.rounds_left_sprites = self.bitmap_text.create_text_sprites(
            text, center_x - text_width / 2, screen_y
        )

    def _get_selected_card_texture(self, color: tuple[int, int, int]) -> arcade.Texture:
        """Get a full selected card texture recolored to the given player color."""
        if color not in self._selected_card_cache:
            self._selected_card_cache[color] = arcade.Texture(self._get_selected_card_image(color))
        return self._selected_card_cache[color]

    def _get_selected_strip_texture(
        self, color: tuple[int, int, int], num_segments: int, segment_index: int
    ) -> arcade.Texture:
        """Get a cropped strip of the selected card texture recolored to player color.

        Only covers the colorable inner area (top 3px and bottom 4px margins excluded).
        """
        key = (color, num_segments, segment_index)
        if key not in self._selected_strip_cache:
            full_img = self._get_selected_card_image(color)
            margin_top = 3
            margin_bottom = 4
            inner_h = full_img.height - margin_top - margin_bottom
            seg_h = inner_h / num_segments
            top = margin_top + int(segment_index * seg_h)
            bottom = margin_top + int((segment_index + 1) * seg_h)
            strip = full_img.crop((0, top, full_img.width, bottom))
            self._selected_strip_cache[key] = arcade.Texture(strip)
        return self._selected_strip_cache[key]

    def _get_selected_card_image(self, color: tuple[int, int, int]) -> Image.Image:
        """Get the full recolored selected card as a PIL Image (cached)."""
        if color not in self._selected_image_cache:
            img = self._card_selected_image.copy()
            data = img.load()
            assert data is not None
            base = (0xDB, 0x00, 0x00)
            for y in range(img.height):
                for x in range(img.width):
                    r, g, b, a = data[x, y]
                    if (r, g, b) == base:
                        data[x, y] = (color[0], color[1], color[2], a)
            self._selected_image_cache[color] = img
        return self._selected_image_cache[color]

    def _build_card_backgrounds(
        self, selected_index: int, player_color: tuple[int, int, int], players: List[Player]
    ) -> None:
        """Build card background sprites for both grids.

        Left grid: full selected card for client player's cursor.
        Right grid: normal bg + proportional selected strips for other players' cursors.
        """
        self.card_bg_sprites = arcade.SpriteList()

        card_w = 64
        card_h = 48
        cols = 4

        # Build other-player cursor lookup: item_index -> list of (player_index, color)
        others = [p for p in players if p.name != self.client_player_name]
        num_others = len(others)
        other_cursor_indices: dict[int, list[tuple[int, tuple[int, int, int]]]] = {}
        for oi, player in enumerate(others):
            for cursor_id, cursor_item in self.cursor_positions:
                if cursor_id == player.id:
                    for idx, (shop_item, _) in enumerate(self.shop_items):
                        if shop_item == cursor_item:
                            other_cursor_indices.setdefault(idx, []).append((oi, player.color))
                            break
                    break

        # Left grid
        for i in range(len(self.shop_items)):
            col = i % cols
            row = i // cols
            card_left = 32 + col * card_w
            card_top = 96 + row * card_h

            bg_sprite = arcade.Sprite()
            if i == selected_index:
                bg_sprite.texture = self._get_selected_card_texture(player_color)
            else:
                bg_sprite.texture = self.card_normal_texture
            bg_sprite.scale = self.zoom
            bg_sprite.center_x = (card_left + card_w / 2) * self.zoom
            bg_sprite.center_y = self.height - (card_top + card_h / 2) * self.zoom
            self.card_bg_sprites.append(bg_sprite)

        # Right grid
        for i in range(len(self.shop_items)):
            col = i % cols
            row = i // cols
            card_left = 352 + col * card_w
            card_top = 96 + row * card_h

            # Normal background
            bg_sprite = arcade.Sprite()
            bg_sprite.texture = self.card_normal_texture
            bg_sprite.scale = self.zoom
            bg_sprite.center_x = (card_left + card_w / 2) * self.zoom
            bg_sprite.center_y = self.height - (card_top + card_h / 2) * self.zoom
            self.card_bg_sprites.append(bg_sprite)

            # Proportional selected strips for other players' cursors
            # Strips only cover the colorable inner area (3px top + 4px bottom margins)
            if num_others > 0 and i in other_cursor_indices:
                margin_top = 3
                margin_bottom = 4
                inner_h = card_h - margin_top - margin_bottom
                seg_h = inner_h / num_others
                for oi, color in other_cursor_indices[i]:
                    strip_texture = self._get_selected_strip_texture(color, num_others, oi)
                    strip_sprite = arcade.Sprite()
                    strip_sprite.texture = strip_texture
                    strip_sprite.scale = self.zoom
                    strip_sprite.center_x = (card_left + card_w / 2) * self.zoom
                    strip_top = card_top + margin_top + oi * seg_h
                    strip_sprite.center_y = self.height - (strip_top + seg_h / 2) * self.zoom
                    self.card_bg_sprites.append(strip_sprite)

    def _build_item_cards(self) -> None:
        """Build the item card icon and price grid for both left and right sides."""
        self.card_icon_sprites = arcade.SpriteList()
        self.card_price_sprites = arcade.SpriteList()

        card_w = 64
        card_h = 48
        cols = 4

        for grid_x in (32, 352):
            for i, (item_type, price) in enumerate(self.shop_items):
                col = i % cols
                row = i // cols

                card_left = grid_x + col * card_w
                card_top = 96 + row * card_h

                # Icon: 30x30 at card-relative (17, 3)
                icon_texture = self.icon_textures.get(item_type)
                if icon_texture:
                    icon_sprite = arcade.Sprite()
                    icon_sprite.texture = icon_texture
                    icon_sprite.scale = self.zoom
                    icon_sprite.center_x = (card_left + 17 + 15) * self.zoom
                    icon_sprite.center_y = self.height - (card_top + 3 + 15) * self.zoom
                    self.card_icon_sprites.append(icon_sprite)

                # Price text: centered in box (12,36)-(52,44) relative to card
                price_text = str(price)
                text_width = self.bitmap_text.get_text_width(price_text)
                box_left = card_left + 12
                box_width = 40  # 52 - 12
                text_x = (box_left + box_width / 2) * self.zoom - text_width / 2
                text_y = self.height - (card_top + 36) * self.zoom
                price_sprites = self.bitmap_text.create_text_sprites(
                    price_text, text_x, text_y, color=(255, 255, 0, 255)
                )
                for sprite in price_sprites:
                    self.card_price_sprites.append(sprite)

    def _build_quantity_bars(self, client_player: Player) -> None:
        """Build quantity bar sprites for each item card based on player inventory.

        For bombs: bar height = item count (1px per item).
        For kevlar vest: bar height = extra HP over 100 (1px per 50 HP).
        """
        from cfg.item_dictionary import PowerupType

        self.quantity_bar_sprites = arcade.SpriteList()

        # Build a lookup: BombType -> count from player inventory
        inventory_counts = {}
        for bomb_type, count in client_player.inventory:
            inventory_counts[bomb_type] = inventory_counts.get(bomb_type, 0) + count

        player_color = client_player.color
        extra_hp = max(0, client_player.health - 100)

        grid_x = 32
        grid_y = 96
        card_w = 64
        card_h = 48
        cols = 4
        max_bar_height = 41  # card_h - 3 (top) - 4 (bottom)

        for i, (item, _price) in enumerate(self.shop_items):
            col = i % cols
            row = i // cols

            card_left = grid_x + col * card_w
            card_top = grid_y + row * card_h

            # Determine bar height based on item type
            if item == PowerupType.KEVLAR_VEST:
                bar_height = min(extra_hp // 50, max_bar_height)
            elif isinstance(item, BombType):
                bar_height = min(inventory_counts.get(item, 0), max_bar_height)
            else:
                continue

            if bar_height <= 0:
                continue

            card_right = card_left + card_w
            card_bottom = card_top + card_h

            bar_x_center = card_right - 8 + 2.5  # center of 5px bar
            bar_bottom = card_bottom - 4
            bar_y_center = bar_bottom - bar_height / 2

            bar_sprite = arcade.Sprite()
            bar_sprite.texture = self.white_texture
            bar_sprite.width = 5 * self.zoom
            bar_sprite.height = bar_height * self.zoom
            bar_sprite.center_x = bar_x_center * self.zoom
            bar_sprite.center_y = self.height - bar_y_center * self.zoom
            bar_sprite.color = player_color
            self.quantity_bar_sprites.append(bar_sprite)

    def _build_inventory_overview(self, players: List[Player]) -> None:
        """Build right-side inventory overview bars for other players only.

        For each item slot, draws a vertical bar divided equally among non-client players.
        Each player's segment is filled proportionally to their item count,
        with a minimum of 1px if they own at least one.
        """
        self.overview_bar_sprites = arcade.SpriteList()

        others = [p for p in players if p.name != self.client_player_name]
        num_players = len(others)
        if num_players == 0:
            return

        # Build per-player inventory lookup
        player_inventories: list[dict] = []
        for player in others:
            inv: dict = {}
            for item, count in player.inventory:
                inv[item] = inv.get(item, 0) + count
            player_inventories.append(inv)

        grid_x = 352
        grid_y = 96
        card_w = 64
        card_h = 48
        cols = 4
        bar_width = 5
        max_bar_height = 41  # card_h - 3 (top) - 4 (bottom)
        segment_height = max_bar_height / num_players

        for i, (shop_item, _) in enumerate(self.shop_items):
            col = i % cols
            row = i // cols
            card_left = grid_x + col * card_w
            card_top = grid_y + row * card_h
            card_right = card_left + card_w

            # Same x-position as left-side quantity bars: right edge of card
            bar_x_center = card_right - 8 + 2.5
            # Stack segments top-down from bar_top (player 0 at top, matching card list)
            bar_top = card_top + 3

            for pi, player in enumerate(others):
                seg_top = bar_top + pi * segment_height

                count = player_inventories[pi].get(shop_item, 0)
                if count <= 0:
                    continue

                # Fill grows downward from segment top, min 1px if count > 0
                fill = max(1.0, min(count, segment_height))
                fill_center_y = seg_top + fill / 2

                bar = arcade.Sprite()
                bar.texture = self.white_texture
                bar.width = bar_width * self.zoom
                bar.height = fill * self.zoom
                bar.center_x = bar_x_center * self.zoom
                bar.center_y = self.height - fill_center_y * self.zoom
                bar.color = player.color
                self.overview_bar_sprites.append(bar)

    def _build_other_player_cards(self, players: List[Player]) -> None:
        """Build card sprites for non-client players on the right side."""
        self.other_player_sprites = arcade.SpriteList()
        self.other_player_name_sprites = arcade.SpriteList()
        self.other_player_info_sprites = arcade.SpriteList()

        others = [p for p in players if p.name != self.client_player_name]

        # Build cursor lookup: player_id -> cursor item
        cursor_lookup: dict = {}
        for cursor_id, cursor_item in self.cursor_positions:
            cursor_lookup[cursor_id] = cursor_item

        card_x = 640
        card_w = 110
        card_h = 30

        for i, player in enumerate(others):
            card_top = (i + 1) * card_h  # Shifted down by one card

            card_texture = self.colorizer.create_recolored_card(
                player.sprite_id, player.color
            )
            if card_texture:
                card_sprite = arcade.Sprite()
                card_sprite.texture = card_texture
                card_sprite.scale = self.zoom
                card_sprite.center_x = (card_x + card_w / 2) * self.zoom
                card_sprite.center_y = self.height - (card_top + card_h / 2) * self.zoom
                self.other_player_sprites.append(card_sprite)

            # Player name at card-relative (8, 1)
            name_x = (card_x + 8) * self.zoom
            name_y = self.height - (card_top + 1) * self.zoom
            name_sprites = self.bitmap_text.create_text_sprites(
                player.name, name_x, name_y
            )
            for sprite in name_sprites:
                self.other_player_name_sprites.append(sprite)

            # Dig power at card-relative (26, 11) in red
            dp_x = (card_x + 26) * self.zoom
            dp_y = self.height - (card_top + 11) * self.zoom
            dp_sprites = self.bitmap_text.create_text_sprites(
                str(player.get_dig_power()), dp_x, dp_y, color=(255, 0, 0, 255)
            )
            for sprite in dp_sprites:
                self.other_player_info_sprites.append(sprite)

            # Money at card-relative (26, 21) in yellow
            money_x = (card_x + 26) * self.zoom
            money_y = self.height - (card_top + 21) * self.zoom
            money_sprites = self.bitmap_text.create_text_sprites(
                str(player.money), money_x, money_y, color=(255, 255, 0, 255)
            )
            for sprite in money_sprites:
                self.other_player_info_sprites.append(sprite)

            # Extra HP bar: 1px per 50 HP over base 100, same style as inventory bars
            extra_hp = max(0, player.health - 100)
            if extra_hp > 0:
                bar_h = extra_hp // 50
                bar_x = (card_x + card_w - 8 + 2.5) * self.zoom
                bar_bottom_y = card_top + card_h - 4
                bar = arcade.Sprite()
                bar.texture = self.white_texture
                bar.width = 5 * self.zoom
                bar.height = bar_h * self.zoom
                bar.center_x = bar_x
                bar.center_y = self.height - (bar_bottom_y - bar_h / 2) * self.zoom
                bar.color = player.color
                self.other_player_info_sprites.append(bar)

            # Cursor item icon: 30x30 sprite anchored to right edge of card
            cursor_item = cursor_lookup.get(player.id)
            if cursor_item:
                icon_texture = self.icon_textures.get(cursor_item)
                if icon_texture:
                    icon_left = card_x + card_w
                    icon_top = card_top
                    icon_sprite = arcade.Sprite()
                    icon_sprite.texture = icon_texture
                    icon_sprite.scale = self.zoom
                    icon_sprite.center_x = (icon_left + 15) * self.zoom
                    icon_sprite.center_y = self.height - (icon_top + 15) * self.zoom
                    self.other_player_info_sprites.append(icon_sprite)

                    # Item count at top-left of icon (1px inset) — bombs only
                    if isinstance(cursor_item, BombType):
                        count = sum(c for bt, c in player.inventory if bt == cursor_item)
                        count_sprites = self.bitmap_text.create_text_sprites(
                            str(count),
                            (icon_left + 1) * self.zoom,
                            self.height - (icon_top + 1) * self.zoom,
                        )
                        for sprite in count_sprites:
                            self.other_player_info_sprites.append(sprite)

    def start(self):
        arcade.run()
