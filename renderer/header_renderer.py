"""
Header/UI renderer for lanibombers.
Handles player card, inventory icons, stats text, and performance graphs.
"""

import os

import arcade
from PIL import Image
from typing import List
from cfg.bomb_dictionary import BOMB_TYPE_TO_ICON
from renderer.bitmap_text import BitmapText
from game_engine.entities.dynamic_entity import DynamicEntity


SPRITES_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "sprites")

# Size of performance graphs and distance between them
GRAPH_WIDTH = 200
GRAPH_HEIGHT = 120
GRAPH_MARGIN = 5


class HeaderRenderer:
    """Handles header UI rendering: player card, inventory, stats, perf graphs."""

    def __init__(self, transparent_texture, zoom, screen_height, show_stats):
        self.zoom = zoom
        self.transparent_texture = transparent_texture
        self.screen_height = screen_height

        # Load player card textures: sprite_id (1-4) -> texture
        self.player_card_textures = {}
        for sprite_id in range(1, 5):
            path = os.path.join(SPRITES_PATH, f"player_card_{sprite_id}.png")
            self.player_card_textures[sprite_id] = arcade.load_texture(path)

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

    def on_update(self, players: List[DynamicEntity], client_player_name: str):
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

        # Update the player card texture based on sprite_id (1-4)
        sprite_id = client_player.sprite_id
        if sprite_id in self.player_card_textures:
            self.player_card_sprite.texture = self.player_card_textures[sprite_id]
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
        self.player_name_sprites.draw(pixelated=True)
        self.dig_power_sprites.draw(pixelated=True)
        self.money_sprites.draw(pixelated=True)
        self.inventory_sprites.draw(pixelated=True)
        self.inventory_hatch_sprites.draw(pixelated=True)
        self.inventory_count_sprites.draw(pixelated=True)
        if show_stats:
            self.perf_graph_list.draw()
