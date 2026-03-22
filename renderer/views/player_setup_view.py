"""
PlayerSetupView — arcade.View for configuring player settings.

Split into three tabs (TAB to cycle) plus a save-confirmation screen (ESC):
  Tab 0 — Player: name, appearance, color + 2x player card + 2x mini-map preview
  Tab 1 — Controls: movement and action key bindings
  Tab 2 — Weapons: weapon hotkeys with icon header bar
  Save  — "Save changes?" Yes/No prompt (shown on ESC from any tab)
"""

import os
import yaml
import random
import arcade
from PIL import Image
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Any
from common.keymapper import arcade_key_to_string
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

SPRITES_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "sprites")
GRAPHICS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "graphics")

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
PLAYER_APPEARANCE_NAMES = ["1", "2", "3", "4"]

# Icon size (icons are 30x30 pixels)
ICON_SIZE = 30

# Tab indices
TAB_PLAYER = 0
TAB_CONTROLS = 1
TAB_WEAPONS = 2
TAB_SAVE = 3


class FieldType(Enum):
    TEXT = "text"
    OPTION = "option"
    HOTKEY = "hotkey"


@dataclass
class MenuField:
    """A configurable field in the setup menu."""

    name: str
    field_type: FieldType
    value: Any
    options: List[Any] = field(default_factory=list)
    option_names: List[str] = field(default_factory=list)
    selected_option_index: int = 0


# ███╗   ███╗██╗███╗   ██╗██╗███╗   ███╗ █████╗ ██████╗
# ████╗ ████║██║████╗  ██║██║████╗ ████║██╔══██╗██╔══██╗
# ██╔████╔██║██║██╔██╗ ██║██║██╔████╔██║███████║██████╔╝
# ██║╚██╔╝██║██║██║╚██╗██║██║██║╚██╔╝██║██╔══██║██╔═══╝
# ██║ ╚═╝ ██║██║██║ ╚████║██║██║ ╚═╝ ██║██║  ██║██║
# ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝


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

    def update(
        self, delta_time: float, mini_map: List[List[int]]
    ) -> Optional[Tuple[int, int]]:
        """Update player state. Returns (x, y) if a tile was destroyed."""
        destroyed_tile = None

        # Update animation frame
        frame_duration = (
            DIG_FRAME_DURATION if self.state == "dig" else WALK_FRAME_DURATION
        )
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

        for dx, dy, direction in [
            (1, 0, Direction.RIGHT),
            (-1, 0, Direction.LEFT),
            (0, 1, Direction.DOWN),
            (0, -1, Direction.UP),
        ]:
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


# ███████╗███████╗████████╗██╗   ██╗██████╗
# ██╔════╝██╔════╝╚══██╔══╝██║   ██║██╔══██╗
# ███████╗█████╗     ██║   ██║   ██║██████╔╝
# ╚════██║██╔══╝     ██║   ██║   ██║██╔═══╝
# ███████║███████╗   ██║   ╚██████╔╝██║
# ╚══════╝╚══════╝   ╚═╝    ╚═════╝ ╚═╝


class PlayerSetupView(arcade.View):
    """Player setup GUI as an arcade.View with tabbed pages."""

    def __init__(self):
        super().__init__()

    def on_show_view(self):
        """Initialize (or re-initialize) when this view becomes active."""
        arcade.set_background_color(arcade.color.BLACK)

        self.zoom = 2
        self.map_zoom = PREVIEW_ZOOM

        # Current tab
        self._tab = TAB_PLAYER
        self._prev_tab = TAB_PLAYER  # for returning from save prompt
        self._save_selection = 0  # 0 = Yes, 1 = No

        # Load textures
        self._load_textures()

        # Initialize bitmap text renderer
        font_path = os.path.join(SPRITES_PATH, "font.png")
        self.bitmap_text = BitmapText(font_path, zoom=self.zoom)

        # Initialize player settings with defaults
        self.player_name = "Player"
        self.player_appearance_index = 0
        self.player_color_index = 0
        self.weapon_order = list(BOMB_TYPES)
        self.hotkeys = dict(DEFAULT_HOTKEYS)
        self.dig_power = 1
        self.money = 100
        self.up_key = "up arrow"
        self.down_key = "down arrow"
        self.left_key = "left arrow"
        self.right_key = "right arrow"
        self.stop_key = "right ctrl"
        self.fire_key = "space"
        self.choose_key = "right shift"
        self.remote_key = "enter"

        # Load saved config if it exists
        self._load_config()

        # Initialize menu fields per tab
        self._init_fields()

        # Snapshot initial state for dirty-checking
        self._initial_state = self._snapshot_state()

        # Per-tab field index
        self._tab_field_index = {TAB_PLAYER: 0, TAB_CONTROLS: 0, TAB_WEAPONS: 0}
        self.editing_text = False
        self.editing_hotkey = False
        self.text_cursor_visible = True
        self.cursor_blink_timer = 0.0

        # Initialize mini-map
        self._init_mini_map()

        # Initialize preview player
        self.preview_player = PreviewPlayer()

        # Respawn timer for refilling map
        self.map_respawn_timer = 0.0
        self.map_respawn_interval = 10.0

        # Initialize sprite lists
        self._init_sprite_lists()

        # Track state for updates
        self.last_appearance_index = -1
        self.last_color_index = -1
        self.last_player_name = None
        self.last_player_key = None

    def _load_textures(self):
        """Load all required textures."""
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
        z = self.zoom  # base zoom (2)

        # --- Player tab background ---
        bg_path = os.path.join(GRAPHICS_PATH, "PLAYERSETUP1.png")
        bg_texture = arcade.load_texture(bg_path)
        bg_sprite = arcade.Sprite()
        bg_sprite.texture = bg_texture
        bg_sprite.scale = z
        bg_sprite.center_x = (640 / 2) * z
        bg_sprite.center_y = self.window.height - (480 / 2) * z
        self.player_bg_sprite_list = arcade.SpriteList()
        self.player_bg_sprite_list.append(bg_sprite)

        # --- Player tab: card at 2x normal zoom ---
        # Design coord top-left: (129, 75) in 640x480 space
        card_zoom = z * 2
        self.card_sprite_list = arcade.SpriteList()
        self.card_sprite = arcade.Sprite()
        self.card_sprite.scale = card_zoom
        # Card texture is 110x30; position center from design top-left
        card_left = 129 * z
        card_top = self.window.height - 75 * z
        self.card_sprite.center_x = card_left + 55 * card_zoom
        self.card_sprite.center_y = card_top - 15 * card_zoom
        self.card_sprite.texture = self.transparent_texture
        self.card_sprite_list.append(self.card_sprite)

        self.card_left = card_left
        self.card_top = card_top
        self.card_zoom = card_zoom

        # Player card text sprite lists
        self.player_name_sprites = arcade.SpriteList()
        self.dig_power_sprites = arcade.SpriteList()
        self.money_sprites = arcade.SpriteList()

        # Bitmap text renderer at card zoom for card text
        font_path = os.path.join(SPRITES_PATH, "font.png")
        self.card_bitmap_text = BitmapText(font_path, zoom=card_zoom)

        # --- Player tab: mini-map at 2x normal zoom ---
        # Design coord top-left: (167, 75) in 640x480 space
        map_zoom = self.map_zoom * 2  # 4x
        self.minimap_sprite_list = arcade.SpriteList()
        self.minimap_sprites = []
        map_x = 367 * z
        map_y = self.window.height - 75 * z

        for ty in range(MINI_MAP_SIZE):
            row = []
            for tx in range(MINI_MAP_SIZE):
                sprite = arcade.Sprite()
                sprite.scale = map_zoom
                sprite.center_x = (
                    map_x
                    + tx * SPRITE_SIZE * map_zoom
                    + SPRITE_SIZE * map_zoom / 2
                )
                sprite.center_y = (
                    map_y
                    - ty * SPRITE_SIZE * map_zoom
                    - SPRITE_SIZE * map_zoom / 2
                )
                sprite.texture = self.transparent_texture
                row.append(sprite)
                self.minimap_sprite_list.append(sprite)
            self.minimap_sprites.append(row)

        # Preview player sprite
        self.preview_player_sprite_list = arcade.SpriteList()
        self.preview_player_sprite = arcade.Sprite()
        self.preview_player_sprite.scale = map_zoom
        self.preview_player_sprite.texture = self.transparent_texture
        self.preview_player_sprite_list.append(self.preview_player_sprite)

        self.map_origin_x = map_x
        self.map_origin_y = map_y
        self.actual_map_zoom = map_zoom

        # --- Weapons tab: icon header bar ---
        self.weapon_icon_sprite_list = arcade.SpriteList()
        self.weapon_icon_sprites = []
        icons_start_x = 110 * self.zoom
        icon_spacing = ICON_SIZE * self.zoom
        for i in range(len(BOMB_TYPES)):
            sprite = arcade.Sprite()
            sprite.scale = self.zoom
            sprite.center_x = icons_start_x + i * icon_spacing + icon_spacing / 2
            sprite.center_y = self.window.height - 15 * self.zoom
            sprite.texture = self.transparent_texture
            self.weapon_icon_sprites.append(sprite)
            self.weapon_icon_sprite_list.append(sprite)

        # Icon separator sprites
        self.separator_sprite_list = arcade.SpriteList()
        separator_path = os.path.join(SPRITES_PATH, "icon_separator.png")
        if os.path.exists(separator_path):
            self.separator_texture = arcade.load_texture(separator_path)
        else:
            self.separator_texture = self.transparent_texture

        for i in range(len(BOMB_TYPES) - 1):
            sprite = arcade.Sprite()
            sprite.scale = self.zoom
            sprite.texture = self.separator_texture
            sprite.center_x = icons_start_x + (i + 1) * icon_spacing
            sprite.center_y = self.window.height - 15 * self.zoom
            self.separator_sprite_list.append(sprite)

        # --- Shared ---
        # Menu highlight sprite
        self.highlight_sprite_list = arcade.SpriteList()
        self.highlight_sprite = arcade.Sprite()
        highlight_image = Image.new("RGBA", (600, 20 * self.zoom), (60, 60, 80, 255))
        self.highlight_texture = arcade.Texture(highlight_image, name="highlight")
        self.highlight_sprite.texture = self.highlight_texture
        self.highlight_sprite.scale = 1
        self.highlight_sprite_list.append(self.highlight_sprite)

        # Menu text sprites (regenerated as needed)
        self.menu_text_sprites = arcade.SpriteList()

        # Save prompt sprites
        self.save_prompt_sprites = arcade.SpriteList()
        self._cached_save_selection = -1

    # ------------------------------------------------------------------
    # Field definitions per tab
    # ------------------------------------------------------------------

    def _init_fields(self):
        """Initialize menu fields grouped by tab."""
        # Tab 0: Player
        self.player_fields: List[MenuField] = [
            MenuField(
                name="Name",
                field_type=FieldType.TEXT,
                value=self.player_name,
            ),
            MenuField(
                name="Appearance",
                field_type=FieldType.OPTION,
                value=PLAYER_APPEARANCES[self.player_appearance_index],
                options=PLAYER_APPEARANCES,
                option_names=PLAYER_APPEARANCE_NAMES,
                selected_option_index=self.player_appearance_index,
            ),
            MenuField(
                name="Color",
                field_type=FieldType.OPTION,
                value=PLAYER_COLORS[self.player_color_index],
                options=PLAYER_COLORS,
                option_names=PLAYER_COLOR_NAMES,
                selected_option_index=self.player_color_index,
            ),
        ]

        # Tab 1: Controls
        self.control_fields: List[MenuField] = [
            MenuField(name="Up", field_type=FieldType.HOTKEY, value=self.up_key),
            MenuField(name="Down", field_type=FieldType.HOTKEY, value=self.down_key),
            MenuField(name="Left", field_type=FieldType.HOTKEY, value=self.left_key),
            MenuField(name="Right", field_type=FieldType.HOTKEY, value=self.right_key),
            MenuField(name="Stop", field_type=FieldType.HOTKEY, value=self.stop_key),
            MenuField(name="Fire", field_type=FieldType.HOTKEY, value=self.fire_key),
            MenuField(name="Choose", field_type=FieldType.HOTKEY, value=self.choose_key),
            MenuField(name="Remote", field_type=FieldType.HOTKEY, value=self.remote_key),
        ]

        # Tab 2: Weapons
        self.weapon_fields: List[MenuField] = []
        for bomb_type in self.weapon_order:
            self.weapon_fields.append(
                MenuField(
                    name=f"{BOMB_TYPE_NAMES[bomb_type]} Hotkey",
                    field_type=FieldType.HOTKEY,
                    value=self.hotkeys.get(bomb_type, ""),
                )
            )

    def _current_fields(self) -> List[MenuField]:
        """Return the field list for the active tab."""
        if self._tab == TAB_PLAYER:
            return self.player_fields
        elif self._tab == TAB_CONTROLS:
            return self.control_fields
        elif self._tab == TAB_WEAPONS:
            return self.weapon_fields
        return []

    @property
    def current_field_index(self) -> int:
        return self._tab_field_index.get(self._tab, 0)

    @current_field_index.setter
    def current_field_index(self, value: int):
        self._tab_field_index[self._tab] = value

    # ------------------------------------------------------------------
    # Mini-map
    # ------------------------------------------------------------------

    def _init_mini_map(self):
        """Initialize the mini-map with a simple layout."""
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
                    if random.random() < 0.3:
                        self.mini_map[y][x] = 1

    # ------------------------------------------------------------------
    # Player card text (uses card_bitmap_text at 2x zoom)
    # ------------------------------------------------------------------

    def _update_player_card_text(self):
        """Update player name, dig power, and money on the card."""
        name_to_display = self.player_fields[0].value if self.player_fields[0].value else "Player"
        self.player_name_sprites = self.card_bitmap_text.create_text_sprites(
            name_to_display,
            self.card_left + 8 * self.card_zoom,
            self.card_top - 1 * self.card_zoom,
            color=(255, 255, 255, 255),
        )
        self.dig_power_sprites = self.card_bitmap_text.create_text_sprites(
            str(self.dig_power),
            self.card_left + 26 * self.card_zoom,
            self.card_top - 11 * self.card_zoom,
            color=(255, 0, 0, 255),
        )
        self.money_sprites = self.card_bitmap_text.create_text_sprites(
            str(self.money),
            self.card_left + 26 * self.card_zoom,
            self.card_top - 21 * self.card_zoom,
            color=(255, 255, 0, 255),
        )

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def on_update(self, delta_time: float):
        """Update game state."""
        # Cursor blink
        self.cursor_blink_timer += delta_time
        if self.cursor_blink_timer >= 0.5:
            self.cursor_blink_timer = 0.0
            self.text_cursor_visible = not self.text_cursor_visible

        # Preview player animation (runs on all tabs so it stays alive)
        self.preview_player.update(delta_time, self.mini_map)

        # Respawn dirt tiles periodically
        self.map_respawn_timer += delta_time
        if self.map_respawn_timer >= self.map_respawn_interval:
            self.map_respawn_timer = 0.0
            self._respawn_mini_map()

        if self._tab == TAB_SAVE:
            self._update_save_prompt()
            return

        # Update player card if appearance or color changed
        sprite_id = PLAYER_APPEARANCES[self.player_appearance_index]
        appearance_changed = self.player_appearance_index != self.last_appearance_index
        color_changed = self.player_color_index != self.last_color_index

        if appearance_changed or color_changed:
            self.last_appearance_index = self.player_appearance_index
            self.last_color_index = self.player_color_index
            self.player_colorizer.update_textures(sprite_id, self.player_color_index)
            card_texture = self.player_colorizer.get_card_texture(sprite_id)
            if card_texture:
                self.card_sprite.texture = card_texture
            else:
                self.card_sprite.texture = self.transparent_texture

        # Update player name text if changed
        current_name = self.player_fields[0].value
        if current_name != self.last_player_name:
            self.last_player_name = current_name
            self._update_player_card_text()

        if self._tab == TAB_PLAYER:
            self._update_player_tab(sprite_id)
        elif self._tab == TAB_WEAPONS:
            self._update_weapons_tab()

        self._update_menu_text()

    def _update_player_tab(self, sprite_id: int):
        """Update mini-map and preview player sprites."""
        # Mini-map tiles
        for ty in range(MINI_MAP_SIZE):
            for tx in range(MINI_MAP_SIZE):
                tile_id = self.mini_map[ty][tx]
                if tile_id in self.tile_textures:
                    self.minimap_sprites[ty][tx].texture = self.tile_textures[tile_id]
                else:
                    self.minimap_sprites[ty][tx].texture = self.transparent_texture

        # Preview player sprite
        player_key = (
            sprite_id,
            self.preview_player.state,
            self.preview_player.direction,
            self.preview_player.frame,
        )
        if player_key != self.last_player_key:
            self.last_player_key = player_key
            player_texture = self.player_colorizer.get_player_texture(
                sprite_id,
                self.preview_player.state,
                self.preview_player.direction,
                self.preview_player.frame,
            )
            if player_texture:
                self.preview_player_sprite.texture = player_texture
            else:
                self.preview_player_sprite.texture = self.transparent_texture

        # Preview player position
        mz = self.actual_map_zoom
        self.preview_player_sprite.center_x = (
            self.map_origin_x
            + self.preview_player.x * SPRITE_SIZE * mz
            + SPRITE_SIZE * mz / 2
        )
        self.preview_player_sprite.center_y = (
            self.map_origin_y
            - self.preview_player.y * SPRITE_SIZE * mz
            - SPRITE_SIZE * mz / 2
        )

    def _update_weapons_tab(self):
        """Update weapon icon sprites based on weapon_order."""
        for i, bomb_type in enumerate(self.weapon_order):
            if i < len(self.weapon_icon_sprites):
                if bomb_type in self.icon_textures:
                    self.weapon_icon_sprites[i].texture = self.icon_textures[bomb_type]
                else:
                    self.weapon_icon_sprites[i].texture = self.transparent_texture

    def _update_save_prompt(self):
        """Rebuild save prompt sprites when selection changes."""
        if self._save_selection == self._cached_save_selection:
            return
        self._cached_save_selection = self._save_selection

        cx = self.window.width / 2
        cy = self.window.height / 2

        self.save_prompt_sprites = arcade.SpriteList()

        # "Save changes?" centered
        question = "Save changes?"
        q_x = cx - len(question) * self.bitmap_text.char_width / 2
        q_sprites = self.bitmap_text.create_text_sprites(
            question, q_x, cy + 20, color=(255, 255, 255)
        )
        for s in q_sprites:
            self.save_prompt_sprites.append(s)

        # Yes / No options
        yes_color = (255, 255, 100) if self._save_selection == 0 else (120, 120, 120)
        no_color = (255, 255, 100) if self._save_selection == 1 else (120, 120, 120)

        gap = 60
        yes_str = "> Yes" if self._save_selection == 0 else "  Yes"
        no_str = "> No" if self._save_selection == 1 else "  No"

        yes_x = cx - gap
        no_x = cx + gap - len("  No") * self.bitmap_text.char_width

        yes_sprites = self.bitmap_text.create_text_sprites(
            yes_str, yes_x, cy - 20, color=yes_color
        )
        for s in yes_sprites:
            self.save_prompt_sprites.append(s)

        no_sprites = self.bitmap_text.create_text_sprites(
            no_str, no_x, cy - 20, color=no_color
        )
        for s in no_sprites:
            self.save_prompt_sprites.append(s)

    def _update_menu_text(self):
        """Update menu text sprites for the current tab."""
        self.menu_text_sprites = arcade.SpriteList()

        if self._tab == TAB_PLAYER:
            self._update_player_tab_text()
            return

        fields = self._current_fields()
        if not fields:
            return

        start_y = self.window.height - 38 * self.zoom
        line_height = 12 * self.zoom

        # Update highlight position
        highlight_y = (
            start_y - self.current_field_index * line_height - line_height / 2 + 4
        )
        self.highlight_sprite.center_x = self.window.width / 2
        self.highlight_sprite.center_y = highlight_y

        for i, menu_field in enumerate(fields):
            y = start_y - i * line_height
            is_selected = i == self.current_field_index

            # Field name
            name_color = (255, 255, 255, 255) if is_selected else (0x8B, 0x8B, 0x8B, 255)
            name_sprites = self.bitmap_text.create_text_sprites(
                menu_field.name + ":", 30, y, color=name_color
            )
            for s in name_sprites:
                self.menu_text_sprites.append(s)

            # Field value
            value_x = 500
            value_color = (255, 255, 255, 255) if is_selected else (0x8B, 0x8B, 0x8B, 255)

            if menu_field.field_type == FieldType.HOTKEY:
                hotkey_str = menu_field.value if menu_field.value else "(none)"
                if is_selected and self.editing_hotkey:
                    value_sprites = self.bitmap_text.create_text_sprites(
                        "Press a key...", value_x, y, color=(255, 200, 100, 255)
                    )
                else:
                    value_sprites = self.bitmap_text.create_text_sprites(
                        hotkey_str, value_x, y, color=value_color
                    )
                for s in value_sprites:
                    self.menu_text_sprites.append(s)

    def _update_player_tab_text(self):
        """Update text sprites for the player tab — values only, centered."""
        z = self.zoom
        cw = self.bitmap_text.char_width

        # Design center positions (640x480 space) for each field value
        # Name centered at (241, 168), Appearance at (241, 192), Color at (241, 216)
        field_positions = [
            (241 * z, self.window.height - 168 * z),
            (241 * z, self.window.height - 192 * z),
            (241 * z, self.window.height - 216 * z),
        ]

        for i, menu_field in enumerate(self.player_fields):
            is_selected = i == self.current_field_index
            center_x, y = field_positions[i]
            color = (255, 255, 255, 255) if is_selected else (0x8B, 0x8B, 0x8B, 255)

            if menu_field.field_type == FieldType.TEXT:
                value_str = menu_field.value
                x = center_x - len(value_str) * cw / 2
                sprites = self.bitmap_text.create_text_sprites(
                    value_str, x, y, color=color
                )

            elif menu_field.field_type == FieldType.OPTION:
                option_name = menu_field.option_names[menu_field.selected_option_index]
                x = center_x - len(option_name) * cw / 2
                sprites = self.bitmap_text.create_text_sprites(
                    option_name, x, y, color=color
                )
            else:
                continue

            for s in sprites:
                self.menu_text_sprites.append(s)

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------

    def on_draw(self):
        """Render the setup screen."""
        self.clear()
        self.window.default_camera.use()

        if self._tab == TAB_SAVE:
            self.save_prompt_sprites.draw(pixelated=True)
            return

        if self._tab == TAB_PLAYER:
            # Background
            self.player_bg_sprite_list.draw(pixelated=True)
            # Player card
            self.card_sprite_list.draw(pixelated=True)
            self.player_name_sprites.draw(pixelated=True)
            self.dig_power_sprites.draw(pixelated=True)
            self.money_sprites.draw(pixelated=True)
            # Mini-map
            self.minimap_sprite_list.draw(pixelated=True)
            self.preview_player_sprite_list.draw(pixelated=True)
            # Field values only (no highlight)
            self.menu_text_sprites.draw(pixelated=True)

        elif self._tab == TAB_WEAPONS:
            # Weapon icon header
            self.weapon_icon_sprite_list.draw(pixelated=True)
            self.separator_sprite_list.draw(pixelated=True)
            # Menu highlight and text
            self.highlight_sprite_list.draw(pixelated=True)
            self.menu_text_sprites.draw(pixelated=True)

        elif self._tab == TAB_CONTROLS:
            # Menu highlight and text only
            self.highlight_sprite_list.draw(pixelated=True)
            self.menu_text_sprites.draw(pixelated=True)

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def on_key_press(self, symbol: int, modifiers: int):
        """Handle key presses."""
        if self._tab == TAB_SAVE:
            self._handle_save_input(symbol)
            return

        fields = self._current_fields()
        current_field = fields[self.current_field_index] if fields else None

        # Handle text editing mode
        if self.editing_text and current_field:
            if symbol == arcade.key.ESCAPE or symbol == arcade.key.ENTER:
                self.editing_text = False
            elif symbol == arcade.key.BACKSPACE:
                if current_field.value:
                    current_field.value = current_field.value[:-1]
                    self.player_name = current_field.value
            else:
                char = self._key_to_char(symbol, modifiers, is_text=True)
                if char and len(current_field.value) < 20:
                    current_field.value += char
                    self.player_name = current_field.value
            return

        # Handle hotkey editing mode
        if self.editing_hotkey and current_field:
            if symbol == arcade.key.ESCAPE:
                self.editing_hotkey = False
            else:
                char = self._key_to_char(symbol, modifiers)
                if char:
                    current_field.value = char
                    # Update the right data depending on tab
                    if self._tab == TAB_CONTROLS:
                        self._sync_control_field(self.current_field_index, char)
                    elif self._tab == TAB_WEAPONS:
                        bomb_idx = self.current_field_index
                        if 0 <= bomb_idx < len(self.weapon_order):
                            self.hotkeys[self.weapon_order[bomb_idx]] = char
                self.editing_hotkey = False
            return

        # TAB cycles tabs
        if symbol == arcade.key.TAB:
            self._tab = (self._tab + 1) % 3
            return

        # ESC: exit immediately if no changes, otherwise show save prompt
        if symbol == arcade.key.ESCAPE:
            if not self._has_changes():
                self.window.view_complete()
                return
            self._prev_tab = self._tab
            self._tab = TAB_SAVE
            self._save_selection = 0
            self._cached_save_selection = -1
            return

        if not current_field:
            return

        # Normal navigation
        if symbol == arcade.key.UP:
            self.current_field_index = (self.current_field_index - 1) % len(fields)

        elif symbol == arcade.key.DOWN:
            self.current_field_index = (self.current_field_index + 1) % len(fields)

        elif symbol == arcade.key.LEFT:
            if current_field.field_type == FieldType.OPTION:
                current_field.selected_option_index = (
                    current_field.selected_option_index - 1
                ) % len(current_field.options)
                current_field.value = current_field.options[
                    current_field.selected_option_index
                ]
                self._sync_option_field(current_field)

            elif current_field.field_type == FieldType.HOTKEY and self._tab == TAB_WEAPONS:
                # Move weapon left in order
                bomb_idx = self.current_field_index
                if bomb_idx > 0:
                    self.weapon_order[bomb_idx], self.weapon_order[bomb_idx - 1] = (
                        self.weapon_order[bomb_idx - 1],
                        self.weapon_order[bomb_idx],
                    )
                    self.weapon_fields[bomb_idx], self.weapon_fields[bomb_idx - 1] = (
                        self.weapon_fields[bomb_idx - 1],
                        self.weapon_fields[bomb_idx],
                    )
                    self.current_field_index -= 1

        elif symbol == arcade.key.RIGHT:
            if current_field.field_type == FieldType.OPTION:
                current_field.selected_option_index = (
                    current_field.selected_option_index + 1
                ) % len(current_field.options)
                current_field.value = current_field.options[
                    current_field.selected_option_index
                ]
                self._sync_option_field(current_field)

            elif current_field.field_type == FieldType.HOTKEY and self._tab == TAB_WEAPONS:
                # Move weapon right in order
                bomb_idx = self.current_field_index
                if bomb_idx < len(self.weapon_order) - 1:
                    self.weapon_order[bomb_idx], self.weapon_order[bomb_idx + 1] = (
                        self.weapon_order[bomb_idx + 1],
                        self.weapon_order[bomb_idx],
                    )
                    self.weapon_fields[bomb_idx], self.weapon_fields[bomb_idx + 1] = (
                        self.weapon_fields[bomb_idx + 1],
                        self.weapon_fields[bomb_idx],
                    )
                    self.current_field_index += 1

        elif symbol == arcade.key.ENTER:
            if current_field.field_type == FieldType.TEXT:
                self.editing_text = True
                self.text_cursor_visible = True
                self.cursor_blink_timer = 0.0
            elif current_field.field_type == FieldType.HOTKEY:
                self.editing_hotkey = True

    def _handle_save_input(self, key: int):
        """Handle input on the save confirmation screen."""
        if key == arcade.key.LEFT:
            self._save_selection = 0
        elif key == arcade.key.RIGHT:
            self._save_selection = 1
        elif key == arcade.key.ENTER:
            if self._save_selection == 0:
                self._save_config()
            self.window.view_complete()
        elif key == arcade.key.ESCAPE:
            self._tab = self._prev_tab
            self._cached_save_selection = -1

    def _sync_option_field(self, menu_field: MenuField):
        """Sync an option field change back to internal state."""
        if menu_field.name == "Appearance":
            self.player_appearance_index = menu_field.selected_option_index
        elif menu_field.name == "Color":
            self.player_color_index = menu_field.selected_option_index

    def _sync_control_field(self, field_index: int, value: str):
        """Sync a control hotkey field back to the key variables."""
        attrs = ["up_key", "down_key", "left_key", "right_key",
                 "stop_key", "fire_key", "choose_key", "remote_key"]
        if 0 <= field_index < len(attrs):
            setattr(self, attrs[field_index], value)

    # ------------------------------------------------------------------
    # Dirty-checking
    # ------------------------------------------------------------------

    def _snapshot_state(self) -> tuple:
        """Capture current settings as a comparable tuple."""
        return (
            self.player_name,
            self.player_appearance_index,
            self.player_color_index,
            tuple(self.weapon_order),
            tuple((k.value, v) for k, v in self.hotkeys.items()),
            self.up_key, self.down_key, self.left_key, self.right_key,
            self.stop_key, self.fire_key, self.choose_key, self.remote_key,
        )

    def _has_changes(self) -> bool:
        """Check whether any settings differ from the initial state."""
        return self._snapshot_state() != self._initial_state

    # ------------------------------------------------------------------
    # Config load/save
    # ------------------------------------------------------------------

    def _load_config(self):
        """Load player configuration from cfg/player.yaml if it exists."""
        cfg_path = os.path.join(os.path.dirname(__file__), "..", "..", "cfg")
        yaml_path = os.path.join(cfg_path, "player.yaml")

        if not os.path.exists(yaml_path):
            return

        try:
            with open(yaml_path, "r") as f:
                config = yaml.safe_load(f)
        except (yaml.YAMLError, IOError):
            return

        if "player_name" in config:
            self.player_name = config["player_name"]
        if "appearance_id" in config:
            appearance_id = config["appearance_id"]
            if appearance_id in PLAYER_APPEARANCES:
                self.player_appearance_index = PLAYER_APPEARANCES.index(appearance_id)
        if "color" in config:
            color_hex = config["color"]
            try:
                r = int(color_hex[1:3], 16)
                g = int(color_hex[3:5], 16)
                b = int(color_hex[5:7], 16)
                color_tuple = (r, g, b)
                if color_tuple in PLAYER_COLORS:
                    self.player_color_index = PLAYER_COLORS.index(color_tuple)
            except (ValueError, IndexError):
                pass

        if "up" in config:
            self.up_key = config["up"]
        if "down" in config:
            self.down_key = config["down"]
        if "left" in config:
            self.left_key = config["left"]
        if "right" in config:
            self.right_key = config["right"]
        if "stop" in config:
            self.stop_key = config["stop"]
        if "fire" in config:
            self.fire_key = config["fire"]
        if "choose" in config:
            self.choose_key = config["choose"]
        if "remote" in config:
            self.remote_key = config["remote"]

        if "items" in config:
            items = config["items"]
            loaded_weapon_order = []
            used_hotkeys = set()
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

            missing_bomb_types = [
                bt for bt in BOMB_TYPES if bt not in loaded_weapon_order
            ]
            for bomb_type in missing_bomb_types:
                for key in HOTKEY_ORDER:
                    if key not in used_hotkeys:
                        self.hotkeys[bomb_type] = key
                        used_hotkeys.add(key)
                        break
                else:
                    self.hotkeys[bomb_type] = ""
                loaded_weapon_order.append(bomb_type)

            self.weapon_order = loaded_weapon_order

    def _save_config(self):
        """Save player configuration to cfg/player.yaml."""
        items = []
        for i, bomb_type in enumerate(self.weapon_order):
            items.append(
                {
                    "name": BOMB_TYPE_NAMES[bomb_type],
                    "hotkey": self.hotkeys.get(bomb_type, ""),
                    "menu_order": i,
                }
            )

        color = PLAYER_COLORS[self.player_color_index]
        color_hex = "#{:02X}{:02X}{:02X}".format(color[0], color[1], color[2])

        config = {
            "player_name": self.player_fields[0].value,
            "appearance_id": PLAYER_APPEARANCES[self.player_appearance_index],
            "color": color_hex,
            "up": self.control_fields[0].value,
            "down": self.control_fields[1].value,
            "left": self.control_fields[2].value,
            "right": self.control_fields[3].value,
            "stop": self.control_fields[4].value,
            "fire": self.control_fields[5].value,
            "choose": self.control_fields[6].value,
            "remote": self.control_fields[7].value,
            "items": items,
        }

        cfg_path = os.path.join(os.path.dirname(__file__), "..", "..", "cfg")
        os.makedirs(cfg_path, exist_ok=True)
        yaml_path = os.path.join(cfg_path, "player.yaml")
        with open(yaml_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    # ------------------------------------------------------------------
    # Key-to-char helper
    # ------------------------------------------------------------------

    def _key_to_char(
        self, key: int, modifiers: int, is_text: bool = False
    ) -> Optional[str]:
        """Convert arcade key code to character."""
        if is_text:
            if arcade.key.A <= key <= arcade.key.Z:
                char = chr(ord("a") + (key - arcade.key.A))
                if modifiers & arcade.key.MOD_SHIFT:
                    char = char.upper()
                return char
            if arcade.key.KEY_0 <= key <= arcade.key.KEY_9:
                return chr(ord("0") + (key - arcade.key.KEY_0))
            if key == arcade.key.SPACE:
                return " "
            punctuation = {
                arcade.key.MINUS: "-",
                arcade.key.EQUAL: "=",
                arcade.key.BRACKETLEFT: "[",
                arcade.key.BRACKETRIGHT: "]",
                arcade.key.SEMICOLON: ";",
                arcade.key.APOSTROPHE: "'",
                arcade.key.COMMA: ",",
                arcade.key.PERIOD: ".",
                arcade.key.SLASH: "/",
            }
            if key in punctuation:
                return punctuation[key]
            return None

        parsed_key = arcade_key_to_string(key)
        if parsed_key:
            return parsed_key
        return None
