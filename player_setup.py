"""
Player Setup Tool for lanibombers.
Allows players to configure their name, color, icon, hotkeys, and weapon order.
"""

import os
import yaml
import random
import arcade
from PIL import Image
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

from game_engine.entities import Direction
from renderer.bitmap_text import BitmapText
from renderer.player_colorizer import (
    PlayerColorizer,
    PLAYER_COLORS,
    PLAYER_COLOR_NAMES,
)
from cfg.bomb_dictionary import (
    BOMB_TYPES,
    BOMB_TYPE_NAMES,
    BOMB_TYPE_TO_ICON,
    BOMB_NAME_TO_TYPE,
    DEFAULT_HOTKEYS,
    HOTKEY_ORDER,
)


# ============================================================================
# Configuration
# ============================================================================

SPRITES_PATH = os.path.join(os.path.dirname(__file__), "assets", "sprites")

WINDOW_WIDTH = 1708
WINDOW_HEIGHT = 960
WINDOW_TITLE = "Player Setup"

SPRITE_SIZE = 10
MINI_MAP_SIZE = 8  # 8x8 tiles
PREVIEW_ZOOM = 2

# Animation settings
WALK_FRAME_DURATION = 0.15  # seconds per frame
DIG_FRAME_DURATION = 0.12
MOVE_SPEED = 2.0  # tiles per second
DIG_DURATION = 1.0  # seconds to dig

# Player appearance options (sprite_id 1-4)
PLAYER_APPEARANCES = [1, 2, 3, 4]
PLAYER_APPEARANCE_NAMES = ["Appearance 1", "Appearance 2", "Appearance 3", "Appearance 4"]

# Icon size (icons are 30x30 pixels)
ICON_SIZE = 30


class FieldType(Enum):
    TEXT = "text"
    OPTION = "option"
    HOTKEY = "hotkey"
    SAVE = "save"


@dataclass
class MenuField:
    """A configurable field in the setup menu."""
    name: str
    field_type: FieldType
    value: any
    options: List[any] = field(default_factory=list)
    option_names: List[str] = field(default_factory=list)
    selected_option_index: int = 0


class PreviewPlayer:
    """Manages the animated player in the mini-map preview."""

    def __init__(self):
        self.x = 4.0  # Start in middle
        self.y = 4.0
        self.direction = Direction.DOWN
        self.state = "walk"  # walk, dig, idle
        self.frame = 1
        self.frame_timer = 0.0
        self.move_timer = 0.0
        self.dig_timer = 0.0
        self.target_x = 4.0
        self.target_y = 4.0
        self.dig_target = None  # (x, y) of tile being dug

    def update(self, delta_time: float, mini_map: List[List[int]]) -> Optional[Tuple[int, int]]:
        """Update player state. Returns (x, y) if a tile was destroyed."""
        destroyed_tile = None

        # Update animation frame
        frame_duration = DIG_FRAME_DURATION if self.state == "dig" else WALK_FRAME_DURATION
        self.frame_timer += delta_time
        if self.frame_timer >= frame_duration:
            self.frame_timer = 0.0
            # Ping-pong animation: 1, 2, 3, 4, 3, 2, 1, ...
            if self.state == "walk" or self.state == "dig":
                self.frame = self.frame % 4 + 1

        if self.state == "dig":
            self.dig_timer += delta_time
            if self.dig_timer >= DIG_DURATION:
                # Finish digging - destroy the tile
                if self.dig_target:
                    tx, ty = self.dig_target
                    if 0 <= tx < MINI_MAP_SIZE and 0 <= ty < MINI_MAP_SIZE:
                        mini_map[ty][tx] = 0  # Set to empty
                        destroyed_tile = (tx, ty)
                self.state = "walk"
                self.dig_timer = 0.0
                self.dig_target = None
                self._choose_new_target(mini_map)

        elif self.state == "walk":
            # Move toward target
            dx = self.target_x - self.x
            dy = self.target_y - self.y
            dist = (dx * dx + dy * dy) ** 0.5

            if dist < 0.1:
                # Reached target, choose new action
                self.x = self.target_x
                self.y = self.target_y
                self._choose_new_action(mini_map)
            else:
                # Move toward target
                move_dist = MOVE_SPEED * delta_time
                if move_dist > dist:
                    move_dist = dist
                self.x += (dx / dist) * move_dist
                self.y += (dy / dist) * move_dist

                # Update direction based on movement
                if abs(dx) > abs(dy):
                    self.direction = Direction.RIGHT if dx > 0 else Direction.LEFT
                else:
                    self.direction = Direction.DOWN if dy > 0 else Direction.UP

        return destroyed_tile

    def _choose_new_action(self, mini_map: List[List[int]]):
        """Choose whether to walk or dig."""
        # Check for diggable tiles nearby
        diggable = []
        ix, iy = int(self.x), int(self.y)

        for dx, dy, direction in [(1, 0, Direction.RIGHT), (-1, 0, Direction.LEFT),
                                   (0, 1, Direction.DOWN), (0, -1, Direction.UP)]:
            nx, ny = ix + dx, iy + dy
            if 0 <= nx < MINI_MAP_SIZE and 0 <= ny < MINI_MAP_SIZE:
                if mini_map[ny][nx] == 1:  # Dirt tile
                    diggable.append((nx, ny, direction))

        # 30% chance to dig if there's a diggable tile
        if diggable and random.random() < 0.3:
            nx, ny, direction = random.choice(diggable)
            self.state = "dig"
            self.direction = direction
            self.dig_target = (nx, ny)
            self.dig_timer = 0.0
        else:
            self._choose_new_target(mini_map)

    def _choose_new_target(self, mini_map: List[List[int]]):
        """Choose a new walking target."""
        # Find walkable adjacent tiles
        walkable = []
        ix, iy = int(self.x), int(self.y)

        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            nx, ny = ix + dx, iy + dy
            if 0 <= nx < MINI_MAP_SIZE and 0 <= ny < MINI_MAP_SIZE:
                if mini_map[ny][nx] == 0:  # Empty tile
                    walkable.append((nx, ny))

        if walkable:
            self.target_x, self.target_y = random.choice(walkable)
        else:
            # No walkable tiles, stay in place
            self.target_x, self.target_y = self.x, self.y


class PlayerSetup(arcade.Window):
    """Player setup GUI application."""

    def __init__(self):
        super().__init__(WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_TITLE)
        arcade.set_background_color((40, 40, 60))

        self.zoom = 2
        self.map_zoom = PREVIEW_ZOOM

        # Load textures
        self._load_textures()

        # Initialize bitmap text renderer
        font_path = os.path.join(SPRITES_PATH, "font.png")
        self.bitmap_text = BitmapText(font_path, zoom=self.zoom)

        # Initialize player settings with defaults
        self.player_name = "Player"
        self.player_appearance_index = 0
        self.player_color_index = 0  # Default to first color (matches appearance 1's base color)
        self.weapon_order = list(BOMB_TYPES)
        self.hotkeys = dict(DEFAULT_HOTKEYS)
        self.dig_power = 1
        self.money = 100

        # Load saved config if it exists
        self._load_config()

        # Initialize menu fields
        self._init_menu_fields()

        # Current field selection
        self.current_field_index = 0
        self.editing_text = False
        self.editing_hotkey = False
        self.text_cursor_visible = True
        self.cursor_blink_timer = 0.0

        # Initialize mini-map (0 = empty, 1 = dirt, 2 = concrete)
        self._init_mini_map()

        # Initialize preview player
        self.preview_player = PreviewPlayer()

        # Respawn timer for refilling map
        self.map_respawn_timer = 0.0
        self.map_respawn_interval = 10.0  # Respawn dirt every 10 seconds

        # Initialize sprite lists
        self._init_sprite_lists()

        # Track state for updates
        self.last_appearance_index = -1
        self.last_color_index = -1
        self.last_player_name = None
        self.last_player_key = None

    def _load_textures(self):
        """Load all required textures."""
        # Initialize player colorizer for player sprites and cards
        self.player_colorizer = PlayerColorizer(SPRITES_PATH)

        # Tile textures for mini-map
        self.tile_textures = {}
        tile_names = {
            0: "empty",
            1: "dirt1",
            2: "concrete",
        }
        for tile_id, tile_name in tile_names.items():
            path = os.path.join(SPRITES_PATH, f"{tile_name}.png")
            if os.path.exists(path):
                self.tile_textures[tile_id] = arcade.load_texture(path)

        # Create transparent texture
        transparent_image = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        self.transparent_texture = arcade.Texture(transparent_image)

        # Load weapon icon textures
        self.icon_textures = {}
        for bomb_type, icon_name in BOMB_TYPE_TO_ICON.items():
            path = os.path.join(SPRITES_PATH, f"{icon_name}_icon.png")
            if os.path.exists(path):
                self.icon_textures[bomb_type] = arcade.load_texture(path)

    def _init_sprite_lists(self):
        """Initialize all sprite lists."""
        # Player card sprite - starts at (0, 0) from top-left
        # Card is 110x30 pixels at zoom=1
        self.card_sprite_list = arcade.SpriteList()
        self.card_sprite = arcade.Sprite()
        self.card_sprite.scale = self.zoom
        card_left = 0
        card_top = self.height
        # Center position: left + half width, top - half height
        self.card_sprite.center_x = card_left + 55 * self.zoom
        self.card_sprite.center_y = card_top - 15 * self.zoom
        self.card_sprite.texture = self.transparent_texture
        self.card_sprite_list.append(self.card_sprite)

        # Store card position for text placement
        self.card_left = card_left
        self.card_top = card_top

        # Weapon icon sprites - positioned next to player card
        # Card is 110 pixels wide at zoom=1, so icons start at 110 * zoom
        self.weapon_icon_sprite_list = arcade.SpriteList()
        self.weapon_icon_sprites = []
        icons_start_x = 110 * self.zoom
        icon_spacing = ICON_SIZE * self.zoom
        for i in range(len(BOMB_TYPES)):
            sprite = arcade.Sprite()
            sprite.scale = self.zoom
            sprite.center_x = icons_start_x + i * icon_spacing + icon_spacing / 2
            sprite.center_y = card_top - 15 * self.zoom  # Same vertical center as card
            sprite.texture = self.transparent_texture
            self.weapon_icon_sprites.append(sprite)
            self.weapon_icon_sprite_list.append(sprite)

        # Icon separator sprites between weapon icons
        self.separator_sprite_list = arcade.SpriteList()
        separator_path = os.path.join(SPRITES_PATH, "icon_separator.png")
        if os.path.exists(separator_path):
            self.separator_texture = arcade.load_texture(separator_path)
        else:
            self.separator_texture = self.transparent_texture

        # Create separator sprites (one between each pair of icons)
        for i in range(len(BOMB_TYPES) - 1):
            sprite = arcade.Sprite()
            sprite.scale = self.zoom
            sprite.texture = self.separator_texture
            # Position at the right edge of each icon (except the last)
            sprite.center_x = icons_start_x + (i + 1) * icon_spacing
            sprite.center_y = card_top - 15 * self.zoom
            self.separator_sprite_list.append(sprite)

        # Mini-map tile sprites - positioned at right edge of window
        self.minimap_sprite_list = arcade.SpriteList()
        self.minimap_sprites = []
        map_width = MINI_MAP_SIZE * SPRITE_SIZE * self.map_zoom
        map_x = self.width - map_width - 10  # 10 pixels from right edge
        map_y = self.height - 30 * self.zoom  # 30 sprite pixels from top

        for ty in range(MINI_MAP_SIZE):
            row = []
            for tx in range(MINI_MAP_SIZE):
                sprite = arcade.Sprite()
                sprite.scale = self.map_zoom
                sprite.center_x = map_x + tx * SPRITE_SIZE * self.map_zoom + SPRITE_SIZE * self.map_zoom / 2
                sprite.center_y = map_y - ty * SPRITE_SIZE * self.map_zoom - SPRITE_SIZE * self.map_zoom / 2
                sprite.texture = self.transparent_texture
                row.append(sprite)
                self.minimap_sprite_list.append(sprite)
            self.minimap_sprites.append(row)

        # Preview player sprite
        self.preview_player_sprite_list = arcade.SpriteList()
        self.preview_player_sprite = arcade.Sprite()
        self.preview_player_sprite.scale = self.map_zoom
        self.preview_player_sprite.texture = self.transparent_texture
        self.preview_player_sprite_list.append(self.preview_player_sprite)

        # Store map origin for player positioning
        self.map_origin_x = map_x
        self.map_origin_y = map_y

        # Menu highlight sprite
        self.highlight_sprite_list = arcade.SpriteList()
        self.highlight_sprite = arcade.Sprite()
        # Create a colored rectangle texture for highlight
        highlight_image = Image.new("RGBA", (600, 20 * self.zoom), (60, 60, 80, 255))
        self.highlight_texture = arcade.Texture(highlight_image, name="highlight")
        self.highlight_sprite.texture = self.highlight_texture
        self.highlight_sprite.scale = 1
        self.highlight_sprite_list.append(self.highlight_sprite)

        # Text sprite lists (regenerated as needed)
        self.player_name_sprites = arcade.SpriteList()
        self.dig_power_sprites = arcade.SpriteList()
        self.money_sprites = arcade.SpriteList()
        self.menu_text_sprites = arcade.SpriteList()
        self.instructions_sprites = arcade.SpriteList()

        # Generate static text
        self._update_instructions()

    def _update_instructions(self):
        """Update the instructions text sprites."""
        instructions = "Up/Down: Navigate | Left/Right: Change | Enter: Edit | Esc: Exit"
        self.instructions_sprites = self.bitmap_text.create_text_sprites(
            instructions, 20, 30, color=(120, 120, 140, 255)
        )

    def _update_player_card_text(self):
        """Update player name, dig power, and money on the card."""
        # Player name
        name_to_display = self.fields[0].value if self.fields[0].value else "Player"
        self.player_name_sprites = self.bitmap_text.create_text_sprites(
            name_to_display,
            self.card_left + 8 * self.zoom,
            self.card_top - 1 * self.zoom,
            color=(255, 255, 255, 255)
        )

        # Dig power (red)
        self.dig_power_sprites = self.bitmap_text.create_text_sprites(
            str(self.dig_power),
            self.card_left + 26 * self.zoom,
            self.card_top - 11 * self.zoom,
            color=(255, 0, 0, 255)
        )

        # Money (yellow)
        self.money_sprites = self.bitmap_text.create_text_sprites(
            str(self.money),
            self.card_left + 26 * self.zoom,
            self.card_top - 21 * self.zoom,
            color=(255, 255, 0, 255)
        )

    def _init_menu_fields(self):
        """Initialize the menu fields."""
        self.fields = []

        # Player name field
        self.fields.append(MenuField(
            name="Player Name",
            field_type=FieldType.TEXT,
            value=self.player_name,
        ))

        # Player appearance field
        self.fields.append(MenuField(
            name="Player Appearance",
            field_type=FieldType.OPTION,
            value=PLAYER_APPEARANCES[self.player_appearance_index],
            options=PLAYER_APPEARANCES,
            option_names=PLAYER_APPEARANCE_NAMES,
            selected_option_index=self.player_appearance_index,
        ))

        # Player color field
        self.fields.append(MenuField(
            name="Player Color",
            field_type=FieldType.OPTION,
            value=PLAYER_COLORS[self.player_color_index],
            options=PLAYER_COLORS,
            option_names=PLAYER_COLOR_NAMES,
            selected_option_index=self.player_color_index,
        ))

        # Hotkey fields for each bomb type (in weapon_order)
        for bomb_type in self.weapon_order:
            self.fields.append(MenuField(
                name=f"{BOMB_TYPE_NAMES[bomb_type]} Hotkey",
                field_type=FieldType.HOTKEY,
                value=self.hotkeys.get(bomb_type, ""),
            ))

        # Save field
        self.fields.append(MenuField(
            name="Save",
            field_type=FieldType.SAVE,
            value=None,
        ))

    def _init_mini_map(self):
        """Initialize the mini-map with a simple layout."""
        # 0 = empty, 1 = dirt, 2 = concrete
        self.mini_map = [
            [2, 2, 2, 2, 2, 2, 2, 2],
            [2, 0, 0, 1, 1, 0, 0, 2],
            [2, 0, 1, 1, 1, 1, 0, 2],
            [2, 1, 1, 0, 0, 1, 1, 2],
            [2, 1, 1, 0, 0, 1, 1, 2],
            [2, 0, 1, 1, 1, 1, 0, 2],
            [2, 0, 0, 1, 1, 0, 0, 2],
            [2, 2, 2, 2, 2, 2, 2, 2],
        ]
        self.original_mini_map = [row[:] for row in self.mini_map]

    def _respawn_mini_map(self):
        """Respawn some dirt tiles in the mini-map."""
        for y in range(MINI_MAP_SIZE):
            for x in range(MINI_MAP_SIZE):
                if self.original_mini_map[y][x] == 1 and self.mini_map[y][x] == 0:
                    # 30% chance to respawn each missing dirt tile
                    if random.random() < 0.3:
                        self.mini_map[y][x] = 1

    def on_update(self, delta_time: float):
        """Update game state."""
        # Update cursor blink
        self.cursor_blink_timer += delta_time
        if self.cursor_blink_timer >= 0.5:
            self.cursor_blink_timer = 0.0
            self.text_cursor_visible = not self.text_cursor_visible

        # Update preview player
        self.preview_player.update(delta_time, self.mini_map)

        # Respawn dirt tiles periodically
        self.map_respawn_timer += delta_time
        if self.map_respawn_timer >= self.map_respawn_interval:
            self.map_respawn_timer = 0.0
            self._respawn_mini_map()

        # Update player card if appearance or color changed
        sprite_id = PLAYER_APPEARANCES[self.player_appearance_index]
        appearance_changed = self.player_appearance_index != self.last_appearance_index
        color_changed = self.player_color_index != self.last_color_index

        if appearance_changed or color_changed:
            self.last_appearance_index = self.player_appearance_index
            self.last_color_index = self.player_color_index
            # Regenerate textures with new color
            self.player_colorizer.update_textures(sprite_id, self.player_color_index)
            # Update card sprite texture
            card_texture = self.player_colorizer.get_card_texture(sprite_id)
            if card_texture:
                self.card_sprite.texture = card_texture
            else:
                self.card_sprite.texture = self.transparent_texture

        # Update player name text if changed
        current_name = self.fields[0].value
        if current_name != self.last_player_name:
            self.last_player_name = current_name
            self._update_player_card_text()

        # Update weapon icon sprites based on weapon_order
        for i, bomb_type in enumerate(self.weapon_order):
            if i < len(self.weapon_icon_sprites):
                if bomb_type in self.icon_textures:
                    self.weapon_icon_sprites[i].texture = self.icon_textures[bomb_type]
                else:
                    self.weapon_icon_sprites[i].texture = self.transparent_texture

        # Update mini-map tile sprites
        for ty in range(MINI_MAP_SIZE):
            for tx in range(MINI_MAP_SIZE):
                tile_id = self.mini_map[ty][tx]
                if tile_id in self.tile_textures:
                    self.minimap_sprites[ty][tx].texture = self.tile_textures[tile_id]
                else:
                    self.minimap_sprites[ty][tx].texture = self.transparent_texture

        # Update preview player sprite
        player_key = (sprite_id, self.preview_player.state,
                      self.preview_player.direction, self.preview_player.frame)

        if player_key != self.last_player_key:
            self.last_player_key = player_key
            player_texture = self.player_colorizer.get_player_texture(
                sprite_id, self.preview_player.state,
                self.preview_player.direction, self.preview_player.frame
            )
            if player_texture:
                self.preview_player_sprite.texture = player_texture
            else:
                self.preview_player_sprite.texture = self.transparent_texture

        # Update preview player position
        self.preview_player_sprite.center_x = (
            self.map_origin_x +
            self.preview_player.x * SPRITE_SIZE * self.map_zoom +
            SPRITE_SIZE * self.map_zoom / 2
        )
        self.preview_player_sprite.center_y = (
            self.map_origin_y -
            self.preview_player.y * SPRITE_SIZE * self.map_zoom -
            SPRITE_SIZE * self.map_zoom / 2
        )

        # Update highlight position
        start_y = self.height - 38 * self.zoom
        line_height = 20 * self.zoom
        highlight_y = start_y - self.current_field_index * line_height - line_height / 2 + 4
        self.highlight_sprite.center_x = self.width / 2
        self.highlight_sprite.center_y = highlight_y

        # Update menu text sprites
        self._update_menu_text()

    def _update_menu_text(self):
        """Update menu text sprites."""
        self.menu_text_sprites = arcade.SpriteList()

        start_y = self.height - 38 * self.zoom
        line_height = 12 * self.zoom

        for i, menu_field in enumerate(self.fields):
            y = start_y - i * line_height
            is_selected = (i == self.current_field_index)

            # Field name
            name_color = (255, 255, 100, 255) if is_selected else (180, 180, 180, 255)
            name_sprites = self.bitmap_text.create_text_sprites(
                menu_field.name + ":", 30, y, color=name_color
            )
            for s in name_sprites:
                self.menu_text_sprites.append(s)

            # Field value
            value_x = 340

            if menu_field.field_type == FieldType.TEXT:
                value_str = menu_field.value
                if is_selected and self.editing_text:
                    if self.text_cursor_visible:
                        value_str += "_"
                    value_color = (255, 255, 255, 255)
                else:
                    value_color = (200, 200, 200, 255)
                value_sprites = self.bitmap_text.create_text_sprites(value_str, value_x, y, color=value_color)
                for s in value_sprites:
                    self.menu_text_sprites.append(s)

                if is_selected and not self.editing_text:
                    hint_sprites = self.bitmap_text.create_text_sprites(
                        "<Enter to edit>", value_x + len(menu_field.value) * 8 * self.zoom + 20, y,
                        color=(100, 100, 100, 255)
                    )
                    for s in hint_sprites:
                        self.menu_text_sprites.append(s)

            elif menu_field.field_type == FieldType.OPTION:
                option_name = menu_field.option_names[menu_field.selected_option_index]
                if is_selected:
                    display_str = "< " + option_name + " >"
                    value_color = (255, 255, 255, 255)
                else:
                    display_str = option_name
                    value_color = (200, 200, 200, 255)
                value_sprites = self.bitmap_text.create_text_sprites(display_str, value_x, y, color=value_color)
                for s in value_sprites:
                    self.menu_text_sprites.append(s)

            elif menu_field.field_type == FieldType.HOTKEY:
                hotkey_str = menu_field.value if menu_field.value else "(none)"
                if is_selected and self.editing_hotkey:
                    value_sprites = self.bitmap_text.create_text_sprites(
                        "Press a key...", value_x, y, color=(255, 200, 100, 255)
                    )
                else:
                    value_color = (255, 255, 255, 255) if is_selected else (200, 200, 200, 255)
                    value_sprites = self.bitmap_text.create_text_sprites(hotkey_str, value_x, y, color=value_color)

                    if is_selected and not self.editing_hotkey:
                        hint_sprites = self.bitmap_text.create_text_sprites(
                            "<Enter to change>", value_x + 80, y, color=(100, 100, 100, 255)
                        )
                        for s in hint_sprites:
                            self.menu_text_sprites.append(s)

                for s in value_sprites:
                    self.menu_text_sprites.append(s)

            elif menu_field.field_type == FieldType.SAVE:
                if is_selected:
                    value_sprites = self.bitmap_text.create_text_sprites(
                        "<Press Enter to save and exit>", value_x, y, color=(100, 255, 100, 255)
                    )
                    for s in value_sprites:
                        self.menu_text_sprites.append(s)

    def on_draw(self):
        """Render the setup screen."""
        self.clear()

        # Draw player card
        self.card_sprite_list.draw(pixelated=True)

        # Draw weapon icons
        self.weapon_icon_sprite_list.draw(pixelated=True)

        # Draw icon separators
        self.separator_sprite_list.draw(pixelated=True)

        # Draw player card text
        self.player_name_sprites.draw(pixelated=True)
        self.dig_power_sprites.draw(pixelated=True)
        self.money_sprites.draw(pixelated=True)

        # Draw mini-map
        self.minimap_sprite_list.draw(pixelated=True)

        # Draw preview player
        self.preview_player_sprite_list.draw(pixelated=True)

        # Draw menu text
        self.menu_text_sprites.draw(pixelated=True)

        # Draw instructions
        self.instructions_sprites.draw(pixelated=True)

    def _load_config(self):
        """Load player configuration from cfg/player.yaml if it exists."""
        cfg_path = os.path.join(os.path.dirname(__file__), "cfg")
        yaml_path = os.path.join(cfg_path, "player.yaml")

        if not os.path.exists(yaml_path):
            return

        try:
            with open(yaml_path, "r") as f:
                config = yaml.safe_load(f)
        except (yaml.YAMLError, IOError):
            return

        # Load player name
        if "player_name" in config:
            self.player_name = config["player_name"]

        # Load appearance ID
        if "appearance_id" in config:
            appearance_id = config["appearance_id"]
            if appearance_id in PLAYER_APPEARANCES:
                self.player_appearance_index = PLAYER_APPEARANCES.index(appearance_id)

        # Load color
        if "color" in config:
            color_hex = config["color"]
            try:
                # Parse hex color string like "#00008B"
                r = int(color_hex[1:3], 16)
                g = int(color_hex[3:5], 16)
                b = int(color_hex[5:7], 16)
                color_tuple = (r, g, b)
                if color_tuple in PLAYER_COLORS:
                    self.player_color_index = PLAYER_COLORS.index(color_tuple)
            except (ValueError, IndexError):
                pass

        # Load items (weapon order and hotkeys)
        if "items" in config:
            items = config["items"]

            # Build weapon order from saved items
            loaded_weapon_order = []
            used_hotkeys = set()

            # Sort items by menu_order
            sorted_items = sorted(items, key=lambda x: x.get("menu_order", 0))

            for item in sorted_items:
                item_name = item.get("name", "")
                hotkey = item.get("hotkey", "")

                if item_name in BOMB_NAME_TO_TYPE:
                    bomb_type = BOMB_NAME_TO_TYPE[item_name]
                    loaded_weapon_order.append(bomb_type)
                    if hotkey:
                        self.hotkeys[bomb_type] = hotkey
                        used_hotkeys.add(hotkey.lower())

            # Find any bomb types that are in BOMB_TYPES but not in the config
            missing_bomb_types = [bt for bt in BOMB_TYPES if bt not in loaded_weapon_order]

            # Assign hotkeys to missing items from HOTKEY_ORDER
            for bomb_type in missing_bomb_types:
                # Find the next available hotkey
                for key in HOTKEY_ORDER:
                    if key not in used_hotkeys:
                        self.hotkeys[bomb_type] = key
                        used_hotkeys.add(key)
                        break
                else:
                    # No more keys available, leave without hotkey
                    self.hotkeys[bomb_type] = ""

                # Append to the end of the weapon order
                loaded_weapon_order.append(bomb_type)

            self.weapon_order = loaded_weapon_order

    def _save_config(self):
        """Save player configuration to cfg/player.yaml."""
        # Build items list with name, hotkey, and menu order
        items = []
        for i, bomb_type in enumerate(self.weapon_order):
            items.append({
                "name": BOMB_TYPE_NAMES[bomb_type],
                "hotkey": self.hotkeys.get(bomb_type, ""),
                "menu_order": i
            })

        # Get the selected color as hex string
        color = PLAYER_COLORS[self.player_color_index]
        color_hex = "#{:02X}{:02X}{:02X}".format(color[0], color[1], color[2])

        config = {
            "player_name": self.fields[0].value,
            "appearance_id": PLAYER_APPEARANCES[self.player_appearance_index],
            "color": color_hex,
            "items": items
        }

        # Ensure cfg directory exists
        cfg_path = os.path.join(os.path.dirname(__file__), "cfg")
        os.makedirs(cfg_path, exist_ok=True)

        # Write to player.yaml
        yaml_path = os.path.join(cfg_path, "player.yaml")
        with open(yaml_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    def on_key_press(self, key: int, modifiers: int):
        """Handle key presses."""
        current_field = self.fields[self.current_field_index]

        # Handle text editing mode
        if self.editing_text:
            if key == arcade.key.ESCAPE or key == arcade.key.ENTER:
                self.editing_text = False
            elif key == arcade.key.BACKSPACE:
                if current_field.value:
                    current_field.value = current_field.value[:-1]
                    self.player_name = current_field.value
            else:
                # Try to get character from key
                char = self._key_to_char(key, modifiers)
                if char and len(current_field.value) < 20:
                    current_field.value += char
                    self.player_name = current_field.value
            return

        # Handle hotkey editing mode
        if self.editing_hotkey:
            if key == arcade.key.ESCAPE:
                self.editing_hotkey = False
            else:
                # Set the hotkey
                char = self._key_to_char(key, modifiers)
                if char:
                    current_field.value = char
                    # Update hotkeys dict
                    bomb_index = self.current_field_index - 3  # Offset for name, appearance, and color fields
                    if 0 <= bomb_index < len(self.weapon_order):
                        self.hotkeys[self.weapon_order[bomb_index]] = char
                self.editing_hotkey = False
            return

        # Normal navigation
        if key == arcade.key.UP:
            self.current_field_index = (self.current_field_index - 1) % len(self.fields)

        elif key == arcade.key.DOWN:
            self.current_field_index = (self.current_field_index + 1) % len(self.fields)

        elif key == arcade.key.LEFT:
            if current_field.field_type == FieldType.OPTION:
                current_field.selected_option_index = (current_field.selected_option_index - 1) % len(current_field.options)
                current_field.value = current_field.options[current_field.selected_option_index]
                # Update the appropriate index based on which field we're on
                if self.current_field_index == 1:  # Appearance field
                    self.player_appearance_index = current_field.selected_option_index
                elif self.current_field_index == 2:  # Color field
                    self.player_color_index = current_field.selected_option_index

            elif current_field.field_type == FieldType.HOTKEY:
                # Move this weapon left in the weapon order
                bomb_index = self.current_field_index - 3  # Offset for name, appearance, and color fields
                if bomb_index > 0:
                    # Swap in weapon_order
                    self.weapon_order[bomb_index], self.weapon_order[bomb_index - 1] = \
                        self.weapon_order[bomb_index - 1], self.weapon_order[bomb_index]
                    # Swap menu fields
                    field_idx = self.current_field_index
                    self.fields[field_idx], self.fields[field_idx - 1] = \
                        self.fields[field_idx - 1], self.fields[field_idx]
                    # Move cursor to follow the item
                    self.current_field_index -= 1

        elif key == arcade.key.RIGHT:
            if current_field.field_type == FieldType.OPTION:
                current_field.selected_option_index = (current_field.selected_option_index + 1) % len(current_field.options)
                current_field.value = current_field.options[current_field.selected_option_index]
                # Update the appropriate index based on which field we're on
                if self.current_field_index == 1:  # Appearance field
                    self.player_appearance_index = current_field.selected_option_index
                elif self.current_field_index == 2:  # Color field
                    self.player_color_index = current_field.selected_option_index

            elif current_field.field_type == FieldType.HOTKEY:
                # Move this weapon right in the weapon order
                bomb_index = self.current_field_index - 3  # Offset for name, appearance, and color fields
                if bomb_index < len(self.weapon_order) - 1:
                    # Swap in weapon_order
                    self.weapon_order[bomb_index], self.weapon_order[bomb_index + 1] = \
                        self.weapon_order[bomb_index + 1], self.weapon_order[bomb_index]
                    # Swap menu fields
                    field_idx = self.current_field_index
                    self.fields[field_idx], self.fields[field_idx + 1] = \
                        self.fields[field_idx + 1], self.fields[field_idx]
                    # Move cursor to follow the item
                    self.current_field_index += 1

        elif key == arcade.key.ENTER:
            if current_field.field_type == FieldType.TEXT:
                self.editing_text = True
                self.text_cursor_visible = True
                self.cursor_blink_timer = 0.0

            elif current_field.field_type == FieldType.HOTKEY:
                self.editing_hotkey = True

            elif current_field.field_type == FieldType.SAVE:
                self._save_config()
                arcade.close_window()

        elif key == arcade.key.ESCAPE:
            arcade.close_window()

    def _key_to_char(self, key: int, modifiers: int) -> Optional[str]:
        """Convert arcade key code to character."""
        # Letters
        if arcade.key.A <= key <= arcade.key.Z:
            char = chr(ord('a') + (key - arcade.key.A))
            if modifiers & arcade.key.MOD_SHIFT:
                char = char.upper()
            return char

        # Numbers
        if arcade.key.KEY_0 <= key <= arcade.key.KEY_9:
            return chr(ord('0') + (key - arcade.key.KEY_0))

        # Space
        if key == arcade.key.SPACE:
            return ' '

        # Common punctuation
        punctuation = {
            arcade.key.MINUS: '-',
            arcade.key.EQUAL: '=',
            arcade.key.BRACKETLEFT: '[',
            arcade.key.BRACKETRIGHT: ']',
            arcade.key.SEMICOLON: ';',
            arcade.key.APOSTROPHE: "'",
            arcade.key.COMMA: ',',
            arcade.key.PERIOD: '.',
            arcade.key.SLASH: '/',
        }
        if key in punctuation:
            return punctuation[key]

        return None


def main():
    """Run the player setup tool."""
    window = PlayerSetup()
    arcade.run()


if __name__ == "__main__":
    main()
