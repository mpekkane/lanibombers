"""
Header/UI renderer for lanibombers.
Handles player card, inventory icons, stats text, and performance graphs.
"""

import os

import arcade
from PIL import Image
from typing import Dict, List, Optional
from common.bomb_dictionary import BombType, BOMB_TYPE_TO_ICON
from renderer.bitmap_text import BitmapText
from renderer.player_colorizer import PlayerColorizer
from game_engine.entities.player import Player


SPRITES_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "sprites")

# Size of performance graphs and distance between them
GRAPH_WIDTH = 200
GRAPH_HEIGHT = 120
GRAPH_MARGIN = 5


class HeaderRenderer:
    """Handles header UI rendering: player card, inventory, stats, perf graphs."""

    def __init__(self, transparent_texture, zoom, screen_height, show_stats,
                 item_hotkeys: Optional[Dict[BombType, str]] = None):
        self.zoom = zoom
        self.transparent_texture = transparent_texture
        self.screen_height = screen_height
        self.item_hotkeys = item_hotkeys or {}

        # Player colorizer for recolored cards
        self.colorizer = PlayerColorizer(SPRITES_PATH)
        self.cached_card_texture: Optional[arcade.Texture] = None
        self.cached_card_key: Optional[tuple] = None  # (sprite_id, color)

        # Load inventory icon textures: BombType -> texture
        self.inventory_icon_textures = {}
        for bomb_type, icon_name in BOMB_TYPE_TO_ICON.items():
            path = os.path.join(SPRITES_PATH, f"{icon_name}_icon.png")
            self.inventory_icon_textures[bomb_type] = arcade.load_texture(path)

        # Load icon separator texture
        self.icon_separator_texture = arcade.load_texture(
            os.path.join(SPRITES_PATH, "icon_separator.png")
        )

        # Create cross-hatch texture for non-selected inventory items (30x30)
        hatch_size = 30
        hatch_image = Image.new('RGBA', (hatch_size, hatch_size), (0, 0, 0, 0))
        hatch_pixels = hatch_image.load()
        assert hatch_pixels is not None
        hatch_color = (103, 103, 103, 255)  # Grey #676767
        # Draw diagonal hatch pattern - pixel every 4th on diagonals
        for y in range(hatch_size):
            for x in range(hatch_size):
                if (x + y) % 4 == 0:
                    hatch_pixels[x, y] = hatch_color
        self.hatch_texture = arcade.Texture(hatch_image, name="inventory_hatch")

        # Header UI sprite list
        self.header_sprite_list = arcade.SpriteList()
        self.header_sprite_list.initialize()

        # Player card sprite (110x30 pixels, positioned at top-left corner)
        self.player_card_sprite = arcade.Sprite()
        self.player_card_sprite.texture = transparent_texture
        self.player_card_sprite.scale = zoom
        # Position at top-left: center_x = half width, center_y = screen height - half height
        card_width = 110
        card_height = 30
        self.player_card_sprite.center_x = (card_width / 2) * zoom
        self.player_card_sprite.center_y = screen_height - (card_height / 2) * zoom
        self.header_sprite_list.append(self.player_card_sprite)

        # Damage overlay (black rectangle over health bar on player card)
        self.damage_overlay_sprites = arcade.SpriteList()
        black_image = Image.new('RGBA', (1, 1), (0, 0, 0, 255))
        self.damage_overlay = arcade.Sprite()
        self.damage_overlay.texture = arcade.Texture(black_image, name="damage_overlay")
        self.damage_overlay.visible = False
        self.damage_overlay_sprites.append(self.damage_overlay)
        self.current_health = None

        # Bitmap text for header
        font_path = os.path.join(SPRITES_PATH, "font.png")
        self.bitmap_text = BitmapText(font_path, zoom=zoom)

        # Player name text sprite list (updated in on_update)
        self.player_name_sprites = arcade.SpriteList()
        self.current_player_name = None  # Use None so first comparison triggers text creation

        # Fight power and money text sprite lists
        self.dig_power_sprites = arcade.SpriteList()
        self.money_sprites = arcade.SpriteList()
        self.current_dig_power = None
        self.current_money = None

        # Inventory icons sprite list (updated in on_update)
        self.inventory_sprites = arcade.SpriteList()
        self.inventory_count_sprites = arcade.SpriteList()  # Text for item counts
        self.inventory_hatch_sprites = arcade.SpriteList()  # Hatch overlay for non-selected
        self.current_inventory = None  # Track inventory to detect changes
        self.current_selected = None  # Track selected index to detect changes
        self.hotkey_text_sprites = arcade.SpriteList()  # Hotkey labels on icons

        # Performance graph (only if show_stats is enabled)
        self.perf_graph_list = arcade.SpriteList()
        if show_stats:
            # Calculate position helpers for the row of 3 performance graphs
            row_y = screen_height - GRAPH_HEIGHT / 2
            starting_x = GRAPH_WIDTH / 2
            step_x = GRAPH_WIDTH + GRAPH_MARGIN

            # Create the FPS performance graph
            graph = arcade.PerfGraph(GRAPH_WIDTH, GRAPH_HEIGHT, graph_data="FPS")
            graph.position = starting_x, row_y
            graph.alpha = 128
            self.perf_graph_list.append(graph)

            # Create the on_update graph
            graph = arcade.PerfGraph(GRAPH_WIDTH, GRAPH_HEIGHT, graph_data="on_update")
            graph.position = starting_x + step_x, row_y
            graph.alpha = 128
            self.perf_graph_list.append(graph)

            # Create the on_draw graph
            graph = arcade.PerfGraph(GRAPH_WIDTH, GRAPH_HEIGHT, graph_data="on_draw")
            graph.position = starting_x + step_x * 2, row_y
            graph.alpha = 128
            self.perf_graph_list.append(graph)

    def on_update(self, players: List[Player], client_player_name: str):
        """Update header UI elements based on the client player's state.

        Args:
            players: List of player entities from render state
            client_player_name: Name of the client's player to find
        """
        # Update player name text (only recreate sprites if name changed)
        if client_player_name != self.current_player_name:
            self.current_player_name = client_player_name
            # Use "Player 1" if name is empty
            display_name = client_player_name if client_player_name else "Player 1"
            # Position: 8 pixels from left edge, 1 pixel down from top
            text_x = 8 * self.zoom
            text_y = self.screen_height - self.zoom
            self.player_name_sprites = self.bitmap_text.create_text_sprites(
                display_name, text_x, text_y
            )

        # Find the client's player by name
        client_player = None
        for player in players:
            if player.name == client_player_name:
                client_player = player
                break

        if client_player is None:
            # No matching player found, hide the card
            self.player_card_sprite.texture = self.transparent_texture
            return

        # Update the player card texture (recolored per player color)
        sprite_id = client_player.sprite_id
        card_key = (sprite_id, client_player.color)
        if card_key != self.cached_card_key:
            self.cached_card_key = card_key
            self.cached_card_texture = self.colorizer.create_recolored_card(
                sprite_id, client_player.color
            )
        if self.cached_card_texture is not None:
            self.player_card_sprite.texture = self.cached_card_texture
        else:
            self.player_card_sprite.texture = self.transparent_texture

        # Update dig_power text (only recreate if changed)
        if client_player.get_dig_power() != self.current_dig_power:
            self.dig_power = client_player.get_dig_power()
            # Position: 26 pixels from left, 11 pixels down (8+3)
            text_x = 26 * self.zoom
            text_y = self.screen_height - 11 * self.zoom
            self.dig_power_sprites = self.bitmap_text.create_text_sprites(
                f"{client_player.get_dig_power()}", text_x, text_y, color=(255, 0, 0, 255)
            )

        # Update money text (only recreate if changed)
        if client_player.money != self.current_money:
            self.current_money = client_player.money
            # Position: 26 pixels from left, 21 pixels down (11+11-1)
            text_x = 26 * self.zoom
            text_y = self.screen_height - 21 * self.zoom
            self.money_sprites = self.bitmap_text.create_text_sprites(
                f"{client_player.money}", text_x, text_y, color=(255, 255, 0, 255)
            )

        # Update damage overlay on health bar (right edge of card)
        if client_player.health != self.current_health:
            self.current_health = client_player.health
            damage_ratio = (100 - client_player.health) / 100
            if damage_ratio > 0:
                overlay_height = 26 * damage_ratio
                self.damage_overlay.width = 8 * self.zoom
                self.damage_overlay.height = overlay_height * self.zoom
                self.damage_overlay.center_x = 104 * self.zoom
                self.damage_overlay.center_y = self.screen_height - (2 + overlay_height / 2) * self.zoom
                self.damage_overlay.visible = True
            else:
                self.damage_overlay.visible = False

        # Update inventory icons (only recreate if changed)
        # inventory is List[Tuple[BombType, int]]
        inventory = getattr(client_player, 'inventory', [])
        selected = getattr(client_player, 'selected', 0)
        # Convert to tuple for comparison (includes counts and selection)
        inventory_key = (tuple(inventory), selected)
        if inventory_key != self.current_inventory:
            self.current_inventory = inventory_key
            # Clear existing sprites
            self.inventory_sprites = arcade.SpriteList()
            self.inventory_count_sprites = arcade.SpriteList()
            self.inventory_hatch_sprites = arcade.SpriteList()
            self.hotkey_text_sprites = arcade.SpriteList()

            # Start position: just past the player card (110 pixels from left)
            icon_x = 110 * self.zoom
            icon_size = 30  # Icon size in pixels
            separator_width = 3  # Separator width in pixels

            for i, (bomb_type, count) in enumerate(inventory):
                # Track icon left edge for count text positioning
                icon_left_x = icon_x
                icon_center_x = icon_x + (icon_size / 2) * self.zoom
                icon_center_y = self.screen_height - (icon_size / 2) * self.zoom

                # Add icon sprite
                icon_texture = self.inventory_icon_textures.get(bomb_type)
                if icon_texture:
                    icon_sprite = arcade.Sprite()
                    icon_sprite.texture = icon_texture
                    icon_sprite.scale = self.zoom
                    icon_sprite.center_x = icon_center_x
                    icon_sprite.center_y = icon_center_y
                    self.inventory_sprites.append(icon_sprite)

                # Add hatch overlay for non-selected items
                if i != selected:
                    hatch_sprite = arcade.Sprite()
                    hatch_sprite.texture = self.hatch_texture
                    hatch_sprite.scale = self.zoom
                    hatch_sprite.center_x = icon_center_x
                    hatch_sprite.center_y = icon_center_y
                    self.inventory_hatch_sprites.append(hatch_sprite)

                # Add count text at top-left corner of icon
                count_text_sprites = self.bitmap_text.create_text_sprites(
                    str(count),
                    icon_left_x + 1 * self.zoom,  # 1 pixel from left edge
                    self.screen_height - 1 * self.zoom,  # 1 pixel from top
                )
                for sprite in count_text_sprites:
                    self.inventory_count_sprites.append(sprite)

                # Add hotkey label at bottom-right of icon
                hotkey_label = self.item_hotkeys.get(bomb_type, "")
                if hotkey_label:
                    char_width = self.bitmap_text.char_width
                    text_width = char_width * len(hotkey_label)
                    hotkey_x = icon_left_x + (icon_size * self.zoom) - text_width - 1 * self.zoom
                    hotkey_y = self.screen_height - (icon_size - self.bitmap_text.char_height / self.zoom - 1) * self.zoom
                    hotkey_sprites = self.bitmap_text.create_text_sprites(
                        hotkey_label, hotkey_x, hotkey_y
                    )
                    for sprite in hotkey_sprites:
                        self.hotkey_text_sprites.append(sprite)

                # Move x position past the icon
                icon_x += icon_size * self.zoom

                # Add separator sprite (except after the last icon)
                if i < len(inventory) - 1:
                    separator_sprite = arcade.Sprite()
                    separator_sprite.texture = self.icon_separator_texture
                    separator_sprite.scale = self.zoom
                    separator_sprite.center_x = icon_x + (separator_width / 2) * self.zoom
                    separator_sprite.center_y = self.screen_height - (icon_size / 2) * self.zoom
                    self.inventory_sprites.append(separator_sprite)
                    # Move x position past the separator
                    icon_x += separator_width * self.zoom

    def on_draw(self, show_stats: bool):
        """Draw all header UI sprite lists."""
        self.header_sprite_list.draw(pixelated=True)
        self.damage_overlay_sprites.draw(pixelated=True)
        self.player_name_sprites.draw(pixelated=True)
        self.dig_power_sprites.draw(pixelated=True)
        self.money_sprites.draw(pixelated=True)
        self.inventory_sprites.draw(pixelated=True)
        self.inventory_hatch_sprites.draw(pixelated=True)
        self.inventory_count_sprites.draw(pixelated=True)
        self.hotkey_text_sprites.draw(pixelated=True)
        if show_stats:
            self.perf_graph_list.draw()

    def draw_perf_graphs(self):
        """Draw only the performance graphs. Used by game_renderer to draw
        graphs after resetting camera shake so they remain stationary."""
        self.perf_graph_list.draw()
