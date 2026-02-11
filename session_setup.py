"""
Session Setup Tool for lanibombers.
Allows configuring game session parameters: starting money, market mode,
multipliers, map selection, and random map generation settings.
Saves to cfg/session.yaml.
"""

import os
import copy
import glob
import yaml
import arcade
import numpy as np
from PIL import Image
from enum import Enum
from dataclasses import dataclass, field
from typing import List

from renderer.bitmap_text import BitmapText
from renderer.tile_renderer import TileRenderer
from game_engine.map_loader import load_map
from game_engine.random_map_generator import RandomMapGenerator
from game_engine.render_state import RenderState


# ============================================================================
# Configuration
# ============================================================================

SPRITES_PATH = os.path.join(os.path.dirname(__file__), "assets", "sprites")
MAPS_PATH = os.path.join(os.path.dirname(__file__), "assets", "maps")

WINDOW_WIDTH = 1708
WINDOW_HEIGHT = 960
WINDOW_TITLE = "Session Setup"

DEFAULT_RANDOM_PARAMS = {
    "width": 64,
    "height": 45,
    "feature_size": 20,
    "threshold": 0.1,
    "min_treasure": 10,
    "max_treasure": 40,
    "min_tools": 5,
    "max_tools": 20,
}


class FieldType(Enum):
    OPTION = "option"
    NUMERIC = "numeric"
    MAP_ENTRY = "map_entry"
    TOGGLE = "toggle"
    SAVE = "save"


@dataclass
class MenuField:
    """A configurable field in the session setup menu."""
    name: str
    field_type: FieldType
    value: any
    options: List[any] = field(default_factory=list)
    option_names: List[str] = field(default_factory=list)
    selected_option_index: int = 0
    step: float = 1
    min_value: float = 0
    max_value: float = 9999
    indent: bool = False
    map_entry_index: int = -1


class SessionSetup(arcade.Window):
    """Session setup GUI application."""

    def __init__(self):
        super().__init__(WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_TITLE)
        arcade.set_background_color((40, 40, 60))

        self.zoom = 2

        # Initialize bitmap text renderer
        font_path = os.path.join(SPRITES_PATH, "font.png")
        self.bitmap_text = BitmapText(font_path, zoom=self.zoom)

        # Transparent texture needed by TileRenderer
        transparent_image = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        self.transparent_texture = arcade.Texture(transparent_image)

        # Discover maps
        self.map_files, self.map_names = self._discover_maps()

        # Initialize defaults
        self.starting_money = 500
        self.floating_market = False
        self.damage_multiplier = 1.0
        self.speed_multiplier = 1.0
        self.map_list = [{"file": self.map_files[0], "index": 0}]
        self.editing_map_entry = False
        self.edit_original_map_index = 0

        # Load saved config if it exists
        self._load_config()

        # Current field selection
        self.current_field_index = 0

        # Build the full fields list
        self._rebuild_fields()

        # Initialize sprite lists
        self._init_sprite_lists()

        # Map preview state
        self.map_preview_tile_renderer = None
        self.map_preview_file = None
        self.map_preview_random_params = None
        self.random_map_generator = RandomMapGenerator()

        # Preview camera on the right side of the window
        preview_x = 860
        preview_y = 260
        preview_w = 640
        preview_h = 450
        self.map_preview_viewport = (preview_x, preview_y, preview_w, preview_h)
        self.map_preview_camera = arcade.Camera2D(
            viewport=arcade.LBWH(preview_x, preview_y, preview_w, preview_h),
        )

        # Load initial preview
        self._load_map_preview()

    def _discover_maps(self):
        """Scan assets/maps/ for .MNE and .MNL files, append Random Map."""
        pattern_mne = os.path.join(MAPS_PATH, "*.MNE")
        pattern_mnl = os.path.join(MAPS_PATH, "*.MNL")
        files = sorted(glob.glob(pattern_mne)) + sorted(glob.glob(pattern_mnl))

        map_files = []
        map_names = []
        for f in files:
            basename = os.path.basename(f)
            map_files.append(basename)
            map_names.append(basename)

        # Append random map as last option
        map_files.append("RANDOM")
        map_names.append("Random Map")

        return map_files, map_names

    def _ensure_random_params(self, entry):
        """Ensure a map_list entry has random_params and expanded keys."""
        if "random_params" not in entry:
            entry["random_params"] = dict(DEFAULT_RANDOM_PARAMS)
        if "expanded" not in entry:
            entry["expanded"] = False

    def _make_random_map_fields(self, entry_index):
        """Create random map sub-fields for a specific map_list entry."""
        params = self.map_list[entry_index]["random_params"]
        return [
            MenuField(
                name="Width", field_type=FieldType.NUMERIC,
                value=params["width"],
                step=1, min_value=16, max_value=256, indent=True,
                map_entry_index=entry_index,
            ),
            MenuField(
                name="Height", field_type=FieldType.NUMERIC,
                value=params["height"],
                step=1, min_value=16, max_value=256, indent=True,
                map_entry_index=entry_index,
            ),
            MenuField(
                name="Feature Size", field_type=FieldType.NUMERIC,
                value=params["feature_size"],
                step=1, min_value=1, max_value=100, indent=True,
                map_entry_index=entry_index,
            ),
            MenuField(
                name="Threshold", field_type=FieldType.NUMERIC,
                value=params["threshold"],
                step=0.05, min_value=-1.0, max_value=1.0, indent=True,
                map_entry_index=entry_index,
            ),
            MenuField(
                name="Min Treasure", field_type=FieldType.NUMERIC,
                value=params["min_treasure"],
                step=1, min_value=0, max_value=200, indent=True,
                map_entry_index=entry_index,
            ),
            MenuField(
                name="Max Treasure", field_type=FieldType.NUMERIC,
                value=params["max_treasure"],
                step=1, min_value=0, max_value=200, indent=True,
                map_entry_index=entry_index,
            ),
            MenuField(
                name="Min Tools", field_type=FieldType.NUMERIC,
                value=params["min_tools"],
                step=1, min_value=0, max_value=200, indent=True,
                map_entry_index=entry_index,
            ),
            MenuField(
                name="Max Tools", field_type=FieldType.NUMERIC,
                value=params["max_tools"],
                step=1, min_value=0, max_value=200, indent=True,
                map_entry_index=entry_index,
            ),
        ]

    def _rebuild_fields(self):
        """Assemble self.fields from fixed fields + map entries + conditional sub-fields + Save."""
        # Floating market options
        fm_index = 1 if self.floating_market else 0

        self.fixed_fields = [
            MenuField(
                name="Starting Money", field_type=FieldType.NUMERIC,
                value=self.starting_money,
                step=100, min_value=0, max_value=10000,
            ),
            MenuField(
                name="Floating Market", field_type=FieldType.OPTION,
                value=self.floating_market,
                options=[False, True],
                option_names=["No", "Yes"],
                selected_option_index=fm_index,
            ),
            MenuField(
                name="Damage Multiplier", field_type=FieldType.NUMERIC,
                value=self.damage_multiplier,
                step=0.25, min_value=0.25, max_value=5.0,
            ),
            MenuField(
                name="Speed Multiplier", field_type=FieldType.NUMERIC,
                value=self.speed_multiplier,
                step=0.25, min_value=0.25, max_value=5.0,
            ),
        ]

        self.fields = list(self.fixed_fields)

        # Map entry fields (with per-entry random map dropdown)
        self.map_entry_fields = []
        for i, entry in enumerate(self.map_list):
            map_field = MenuField(
                name=f"Map {i + 1}",
                field_type=FieldType.MAP_ENTRY,
                value=entry["file"],
                options=self.map_files,
                option_names=self.map_names,
                selected_option_index=entry["index"],
                indent=True,
                map_entry_index=i,
            )
            self.map_entry_fields.append(map_field)
            self.fields.append(map_field)

            if entry["file"] == "RANDOM":
                self._ensure_random_params(entry)
                indicator = "[-]" if entry["expanded"] else "[+]"
                self.fields.append(MenuField(
                    name=f"{indicator} Random Map Options",
                    field_type=FieldType.TOGGLE,
                    value=entry["expanded"],
                    indent=True,
                    map_entry_index=i,
                ))
                if entry["expanded"]:
                    self.fields.extend(self._make_random_map_fields(i))

        self.fields.append(MenuField(
            name="Save", field_type=FieldType.SAVE,
            value=None,
        ))

        # Clamp field index
        if self.current_field_index >= len(self.fields):
            self.current_field_index = len(self.fields) - 1

    def _init_sprite_lists(self):
        """Initialize sprite lists for highlight, text, and instructions."""
        # Menu highlight sprite
        self.highlight_sprite_list = arcade.SpriteList()
        self.highlight_sprite = arcade.Sprite()
        highlight_image = Image.new("RGBA", (600, 20 * self.zoom), (60, 60, 80, 255))
        self.highlight_texture = arcade.Texture(highlight_image, name="session_highlight")
        self.highlight_sprite.texture = self.highlight_texture
        self.highlight_sprite.scale = 1
        self.highlight_sprite_list.append(self.highlight_sprite)

        # Text sprite lists
        self.menu_text_sprites = arcade.SpriteList()
        self.instructions_sprites = arcade.SpriteList()

        # Generate instructions text
        self._update_instructions()

    def _update_instructions(self):
        """Update the instructions text sprites."""
        instructions = "Up/Down: Navigate | Left/Right: Reorder/Change | Ins: Add map | Del: Remove map | Enter: Edit/Save | Esc: Exit"
        self.instructions_sprites = self.bitmap_text.create_text_sprites(
            instructions, 20, 30, color=(120, 120, 140, 255)
        )

    def _format_value(self, menu_field, is_selected):
        """Format a field's value for display."""
        if menu_field.field_type == FieldType.NUMERIC:
            val = menu_field.value
            # Multiplier fields: display as percentage
            if menu_field.name in ("Damage Multiplier", "Speed Multiplier"):
                text = f"{int(round(val * 100))}%"
            elif menu_field.name == "Threshold":
                text = f"{val:.2f}"
            else:
                text = str(int(val))

            if is_selected:
                return f"< {text} >"
            return text

        elif menu_field.field_type == FieldType.OPTION:
            name = menu_field.option_names[menu_field.selected_option_index]
            if is_selected:
                return f"< {name} >"
            return name

        elif menu_field.field_type == FieldType.MAP_ENTRY:
            name = menu_field.option_names[menu_field.selected_option_index]
            if self.editing_map_entry and is_selected:
                return f"< {name} >"
            return name

        elif menu_field.field_type == FieldType.TOGGLE:
            return ""

        elif menu_field.field_type == FieldType.SAVE:
            if is_selected:
                return "<Press Enter to save and exit>"
            return ""

        return ""

    def _update_menu_text(self):
        """Regenerate menu text sprites."""
        self.menu_text_sprites = arcade.SpriteList()

        start_y = self.height - 38 * self.zoom
        line_height = 12 * self.zoom

        # Empty map list warning
        if not self.map_list:
            warn_y = start_y - len(self.fixed_fields) * line_height
            warn_sprites = self.bitmap_text.create_text_sprites(
                "WARNING: EMPTY MAP LIST", 60, warn_y, color=(255, 100, 60, 255)
            )
            for s in warn_sprites:
                self.menu_text_sprites.append(s)

        for i, menu_field in enumerate(self.fields):
            y = start_y - i * line_height
            is_selected = (i == self.current_field_index)

            # Field name
            name_x = 60 if menu_field.indent else 30
            if is_selected and self.editing_map_entry and menu_field.field_type == FieldType.MAP_ENTRY:
                name_color = (255, 200, 100, 255)
            elif is_selected:
                name_color = (255, 255, 100, 255)
            elif menu_field.indent:
                name_color = (140, 140, 160, 255)
            else:
                name_color = (180, 180, 180, 255)

            label = menu_field.name + ":"
            if menu_field.field_type in (FieldType.SAVE, FieldType.TOGGLE):
                label = menu_field.name
            name_sprites = self.bitmap_text.create_text_sprites(
                label, name_x, y, color=name_color
            )
            for s in name_sprites:
                self.menu_text_sprites.append(s)

            # Field value
            value_x = 340
            value_str = self._format_value(menu_field, is_selected)

            if menu_field.field_type == FieldType.SAVE:
                if is_selected:
                    value_color = (100, 255, 100, 255)
                else:
                    value_color = (200, 200, 200, 255)
            elif is_selected:
                value_color = (255, 255, 255, 255)
            else:
                value_color = (200, 200, 200, 255)

            if value_str:
                value_sprites = self.bitmap_text.create_text_sprites(
                    value_str, value_x, y, color=value_color
                )
                for s in value_sprites:
                    self.menu_text_sprites.append(s)

    def _get_active_map_entry(self):
        """Return the map_list entry that should be previewed based on cursor position."""
        if not self.map_list:
            return None
        current_field = self.fields[self.current_field_index]
        # If cursor is on a MAP_ENTRY field, use its index
        if current_field.field_type == FieldType.MAP_ENTRY:
            idx = current_field.map_entry_index
            if 0 <= idx < len(self.map_list):
                return self.map_list[idx]
        # If cursor is on a sub-field (toggle, random params) with a map_entry_index
        if current_field.map_entry_index >= 0:
            idx = current_field.map_entry_index
            if idx < len(self.map_list):
                return self.map_list[idx]
        # Default to first entry
        return self.map_list[0]

    def _load_map_preview(self):
        """Load and create TileRenderer for the active map entry."""
        entry = self._get_active_map_entry()
        if entry is None:
            self.map_preview_tile_renderer = None
            self.map_preview_file = None
            self.map_preview_random_params = None
            return

        file = entry["file"]
        random_params = entry.get("random_params")

        # Skip reload if same map (and same random params for RANDOM)
        if file == self.map_preview_file:
            if file != "RANDOM":
                return
            if random_params == self.map_preview_random_params:
                return

        # Load map data
        if file == "RANDOM":
            self._ensure_random_params(entry)
            params = entry["random_params"]
            map_data = self.random_map_generator.generate(
                x=params["width"], y=params["height"],
                feature_size=params["feature_size"],
                threshold=params["threshold"],
                min_treasure=0, max_treasure=0,
                min_tools=0, max_tools=0,
            )
        else:
            map_data = load_map(os.path.join(MAPS_PATH, file))

        # Build RenderState
        tilemap_np = np.array(map_data.tilemap, dtype=np.uint8).reshape(
            map_data.height, map_data.width
        )
        state = RenderState(
            width=map_data.width, height=map_data.height,
            tilemap=tilemap_np,
            explosions=np.zeros_like(tilemap_np),
        )

        # Create TileRenderer at zoom=1
        self.map_preview_tile_renderer = TileRenderer(
            state, self.transparent_texture, zoom=1
        )
        self.map_preview_tile_renderer.on_update(
            state, 0, state.width, 0, state.height
        )

        # Set camera projection centered, matching the game camera pattern
        _, _, preview_w, preview_h = self.map_preview_viewport
        map_px_w = state.width * 10
        map_px_h = state.height * 10
        proj_w = max(map_px_w, preview_w)
        proj_h = max(map_px_h, preview_h)
        self.map_preview_camera.projection = arcade.LRBT(
            -proj_w / 2, proj_w / 2,
            -proj_h / 2, proj_h / 2,
        )
        self.map_preview_camera.position = (map_px_w / 2, map_px_h / 2)

        # Track loaded state
        self.map_preview_file = file
        self.map_preview_random_params = copy.deepcopy(random_params) if random_params else None

    def on_update(self, delta_time: float):
        """Update highlight position and menu text."""
        # Update highlight position
        start_y = self.height - 38 * self.zoom
        line_height = 20 * self.zoom
        highlight_y = start_y - self.current_field_index * line_height - line_height / 2 + 4
        self.highlight_sprite.center_x = self.width / 2
        self.highlight_sprite.center_y = highlight_y

        # Update menu text
        self._update_menu_text()

        # Check if map preview needs updating
        entry = self._get_active_map_entry()
        if entry is None:
            if self.map_preview_file is not None:
                self._load_map_preview()
        else:
            file = entry["file"]
            if file != self.map_preview_file:
                self._load_map_preview()
            elif file == "RANDOM":
                self._ensure_random_params(entry)
                if entry["random_params"] != self.map_preview_random_params:
                    self._load_map_preview()

    def on_draw(self):
        """Render the setup screen."""
        self.clear()

        # Draw highlight bar
        self.highlight_sprite_list.draw(pixelated=True)

        # Draw menu text
        self.menu_text_sprites.draw(pixelated=True)

        # Draw instructions
        self.instructions_sprites.draw(pixelated=True)

        # Draw map preview
        if self.map_preview_tile_renderer:
            self.map_preview_camera.use()
            self.map_preview_tile_renderer.background_tile_sprite_list.draw(pixelated=True)
            self.map_preview_tile_renderer.vertical_transition_sprite_list.draw(pixelated=True)
            self.map_preview_tile_renderer.horizontal_transition_sprite_list.draw(pixelated=True)
            self.default_camera.use()

    def _find_map_entry_index(self, field):
        """Find the index of a MAP_ENTRY field within self.map_list."""
        if field not in self.map_entry_fields:
            return -1
        return self.map_entry_fields.index(field)

    def _move_cursor_to_map_entry(self, map_list_index):
        """Move cursor to the MAP_ENTRY field for a given map_list index."""
        for i, f in enumerate(self.fields):
            if f.field_type == FieldType.MAP_ENTRY and f.map_entry_index == map_list_index:
                self.current_field_index = i
                return

    def on_key_press(self, key: int, modifiers: int):
        """Handle key presses."""
        current_field = self.fields[self.current_field_index]

        # MAP_ENTRY edit mode handling
        if self.editing_map_entry:
            if key == arcade.key.LEFT:
                current_field.selected_option_index = (
                    (current_field.selected_option_index - 1) % len(current_field.options)
                )
                current_field.value = current_field.options[current_field.selected_option_index]
                map_idx = self._find_map_entry_index(current_field)
                if map_idx >= 0:
                    self.map_list[map_idx]["file"] = current_field.value
                    self.map_list[map_idx]["index"] = current_field.selected_option_index

            elif key == arcade.key.RIGHT:
                current_field.selected_option_index = (
                    (current_field.selected_option_index + 1) % len(current_field.options)
                )
                current_field.value = current_field.options[current_field.selected_option_index]
                map_idx = self._find_map_entry_index(current_field)
                if map_idx >= 0:
                    self.map_list[map_idx]["file"] = current_field.value
                    self.map_list[map_idx]["index"] = current_field.selected_option_index

            elif key == arcade.key.ENTER:
                self.editing_map_entry = False
                # Check if random map visibility changed
                self._rebuild_fields()

            elif key == arcade.key.ESCAPE:
                # Revert to original
                current_field.selected_option_index = self.edit_original_map_index
                current_field.value = current_field.options[self.edit_original_map_index]
                map_idx = self._find_map_entry_index(current_field)
                if map_idx >= 0:
                    self.map_list[map_idx]["file"] = current_field.value
                    self.map_list[map_idx]["index"] = current_field.selected_option_index
                self.editing_map_entry = False
                self._rebuild_fields()

            return

        # Navigation
        if key == arcade.key.UP:
            self.current_field_index = (self.current_field_index - 1) % len(self.fields)

        elif key == arcade.key.DOWN:
            self.current_field_index = (self.current_field_index + 1) % len(self.fields)

        elif key == arcade.key.LEFT:
            if current_field.field_type == FieldType.OPTION:
                current_field.selected_option_index = (
                    (current_field.selected_option_index - 1) % len(current_field.options)
                )
                current_field.value = current_field.options[current_field.selected_option_index]
                self._sync_field_to_state(current_field)

            elif current_field.field_type == FieldType.NUMERIC:
                new_val = round(current_field.value - current_field.step, 4)
                current_field.value = max(current_field.min_value, new_val)
                self._sync_field_to_state(current_field)

            elif current_field.field_type == FieldType.MAP_ENTRY:
                # Reorder: swap with previous MAP_ENTRY
                map_idx = self._find_map_entry_index(current_field)
                if map_idx > 0:
                    self.map_list[map_idx], self.map_list[map_idx - 1] = (
                        self.map_list[map_idx - 1], self.map_list[map_idx]
                    )
                    new_map_idx = map_idx - 1
                    self._rebuild_fields()
                    self._move_cursor_to_map_entry(new_map_idx)

        elif key == arcade.key.RIGHT:
            if current_field.field_type == FieldType.OPTION:
                current_field.selected_option_index = (
                    (current_field.selected_option_index + 1) % len(current_field.options)
                )
                current_field.value = current_field.options[current_field.selected_option_index]
                self._sync_field_to_state(current_field)

            elif current_field.field_type == FieldType.NUMERIC:
                new_val = round(current_field.value + current_field.step, 4)
                current_field.value = min(current_field.max_value, new_val)
                self._sync_field_to_state(current_field)

            elif current_field.field_type == FieldType.MAP_ENTRY:
                # Reorder: swap with next MAP_ENTRY
                map_idx = self._find_map_entry_index(current_field)
                if map_idx < len(self.map_list) - 1:
                    self.map_list[map_idx], self.map_list[map_idx + 1] = (
                        self.map_list[map_idx + 1], self.map_list[map_idx]
                    )
                    new_map_idx = map_idx + 1
                    self._rebuild_fields()
                    self._move_cursor_to_map_entry(new_map_idx)

        elif key == arcade.key.ENTER:
            if current_field.field_type == FieldType.SAVE:
                self._save_config()
                arcade.close_window()
            elif current_field.field_type == FieldType.MAP_ENTRY:
                self.editing_map_entry = True
                self.edit_original_map_index = current_field.selected_option_index
            elif current_field.field_type == FieldType.TOGGLE:
                entry = self.map_list[current_field.map_entry_index]
                entry["expanded"] = not entry["expanded"]
                self._rebuild_fields()

        elif key == arcade.key.ESCAPE:
            arcade.close_window()

        elif key in (arcade.key.INSERT, arcade.key.EQUAL, arcade.key.NUM_ADD):
            # Add new map entry
            if current_field.field_type == FieldType.MAP_ENTRY:
                map_idx = self._find_map_entry_index(current_field)
                new_entry = copy.deepcopy(self.map_list[map_idx])
                new_entry.pop("expanded", None)
                self.map_list.insert(map_idx + 1, new_entry)
                self._rebuild_fields()
                self._move_cursor_to_map_entry(map_idx + 1)
            else:
                # Insert relative to owning map entry, or append to end
                owner_idx = current_field.map_entry_index
                if owner_idx >= 0 and owner_idx < len(self.map_list):
                    new_entry = copy.deepcopy(self.map_list[owner_idx])
                    new_entry.pop("expanded", None)
                    self.map_list.insert(owner_idx + 1, new_entry)
                    new_idx = owner_idx + 1
                elif self.map_list:
                    new_entry = copy.deepcopy(self.map_list[-1])
                    new_entry.pop("expanded", None)
                    self.map_list.append(new_entry)
                    new_idx = len(self.map_list) - 1
                else:
                    new_entry = {"file": self.map_files[0], "index": 0}
                    self.map_list.append(new_entry)
                    new_idx = 0
                self._rebuild_fields()
                self._move_cursor_to_map_entry(new_idx)

        elif key in (arcade.key.DELETE, arcade.key.MINUS, arcade.key.NUM_SUBTRACT):
            # Remove map entry (only when on a MAP_ENTRY)
            if current_field.field_type == FieldType.MAP_ENTRY:
                map_idx = self._find_map_entry_index(current_field)
                self.map_list.pop(map_idx)
                self._rebuild_fields()

    def _sync_field_to_state(self, changed_field):
        """Sync a changed field value back to internal state and rebuild if needed."""
        name = changed_field.name

        if name == "Starting Money":
            self.starting_money = int(changed_field.value)
        elif name == "Floating Market":
            self.floating_market = changed_field.value
        elif name == "Damage Multiplier":
            self.damage_multiplier = changed_field.value
        elif name == "Speed Multiplier":
            self.speed_multiplier = changed_field.value
        else:
            # Random map sub-fields — route to the owning entry's random_params
            idx = changed_field.map_entry_index
            if idx >= 0 and idx < len(self.map_list):
                params = self.map_list[idx].get("random_params")
                if params is not None:
                    key = {
                        "Width": "width", "Height": "height",
                        "Feature Size": "feature_size", "Threshold": "threshold",
                        "Min Treasure": "min_treasure", "Max Treasure": "max_treasure",
                        "Min Tools": "min_tools", "Max Tools": "max_tools",
                    }.get(name)
                    if key:
                        if key == "threshold":
                            params[key] = changed_field.value
                        else:
                            params[key] = int(changed_field.value)

    def _load_config(self):
        """Load session configuration from cfg/session.yaml if it exists."""
        cfg_path = os.path.join(os.path.dirname(__file__), "cfg")
        yaml_path = os.path.join(cfg_path, "session.yaml")

        if not os.path.exists(yaml_path):
            return

        try:
            with open(yaml_path, "r") as f:
                config = yaml.safe_load(f)
        except (yaml.YAMLError, IOError):
            return

        if not config:
            return

        if "starting_money" in config:
            self.starting_money = config["starting_money"]

        if "floating_market" in config:
            self.floating_market = bool(config["floating_market"])

        if "damage_multiplier" in config:
            self.damage_multiplier = float(config["damage_multiplier"])

        if "speed_multiplier" in config:
            self.speed_multiplier = float(config["speed_multiplier"])

        # Load maps list (new format) or single map (old format)
        if "maps" in config:
            self.map_list = []
            for map_val in config["maps"]:
                if isinstance(map_val, dict):
                    # RANDOM entry with params
                    fname = map_val.get("file", "RANDOM")
                    if fname in self.map_files:
                        idx = self.map_files.index(fname)
                        entry = {"file": fname, "index": idx}
                        if fname == "RANDOM":
                            params = dict(DEFAULT_RANDOM_PARAMS)
                            for k in params:
                                if k in map_val:
                                    params[k] = map_val[k]
                            entry["random_params"] = params
                        self.map_list.append(entry)
                elif isinstance(map_val, str):
                    if map_val in self.map_files:
                        idx = self.map_files.index(map_val)
                        self.map_list.append({"file": map_val, "index": idx})
        elif "map" in config:
            # Old format backward compat
            map_val = config["map"]
            if map_val in self.map_files:
                idx = self.map_files.index(map_val)
                entry = {"file": map_val, "index": idx}
                if map_val == "RANDOM" and "random_map" in config:
                    params = dict(DEFAULT_RANDOM_PARAMS)
                    rm = config["random_map"]
                    for k in params:
                        if k in rm:
                            params[k] = rm[k]
                    entry["random_params"] = params
                self.map_list = [entry]

    def _save_config(self):
        """Save session configuration to cfg/session.yaml."""
        maps_out = []
        for entry in self.map_list:
            if entry["file"] == "RANDOM" and "random_params" in entry:
                maps_out.append({"file": "RANDOM", **entry["random_params"]})
            else:
                maps_out.append(entry["file"])

        config = {
            "starting_money": self.starting_money,
            "floating_market": self.floating_market,
            "damage_multiplier": self.damage_multiplier,
            "speed_multiplier": self.speed_multiplier,
            "maps": maps_out,
        }

        cfg_path = os.path.join(os.path.dirname(__file__), "cfg")
        os.makedirs(cfg_path, exist_ok=True)

        yaml_path = os.path.join(cfg_path, "session.yaml")
        with open(yaml_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def main():
    """Run the session setup tool."""
    window = SessionSetup()
    arcade.run()


if __name__ == "__main__":
    main()
