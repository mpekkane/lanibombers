"""
Tile renderer for lanibombers.
Handles background tiles and transition rendering.
"""

import os

import arcade
import numpy as np

from cfg.tile_dictionary import (
    TILE_DICTIONARY,
    EMPTY_TILE_NAMES,
    BEDROCK_TILE_NAMES,
    DIRT_TILE_NAMES,
    BEDROCK_NW_ID,
    BEDROCK_NE_ID,
    BEDROCK_SE_ID,
    BEDROCK_SW_ID,
)

SPRITES_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "sprites")

SPRITE_SIZE = 10
SPRITE_CENTER_OFFSET = SPRITE_SIZE // 2

# Horizontal transition textures (8x10 pixels, between columns)
HORIZONTAL_TRANSITION_TEXTURES = {
    "empty_bedrock": "transition_horizontal_empty_bedrock",
    "bedrock_empty": "transition_horizontal_bedrock_empty",
    "empty_dirt": "transition_horizontal_empty_dirt",
    "dirt_empty": "transition_horizontal_dirt_empty",
    "empty_bedrock_burnt": "transition_horizontal_empty_bedrock_burnt",
    "bedrock_empty_burnt": "transition_horizontal_bedrock_empty_burnt",
    "empty_dirt_burnt": "transition_horizontal_empty_dirt_burnt",
    "dirt_empty_burnt": "transition_horizontal_dirt_empty_burnt",
}

# Vertical transition textures (10x6 pixels, between rows)
VERTICAL_TRANSITION_TEXTURES = {
    "empty_bedrock": "transition_vertical_empty_bedrock",
    "bedrock_empty": "transition_vertical_bedrock_empty",
    "empty_dirt": "transition_vertical_empty_dirt",
    "dirt_empty": "transition_vertical_dirt_empty",
    "empty_bedrock_burnt": "transition_vertical_empty_bedrock_burnt",
    "bedrock_empty_burnt": "transition_vertical_bedrock_empty_burnt",
    "empty_dirt_burnt": "transition_vertical_empty_dirt_burnt",
    "dirt_empty_burnt": "transition_vertical_dirt_empty_burnt",
}

BURNT_EMPTY_OFFSET = 256


class TileRenderer:
    """Handles background tile and transition rendering."""

    def __init__(self, state, transparent_texture, zoom):
        self.zoom = zoom
        self.transparent_texture = transparent_texture

        EMPTY_TILE_IDS = {
            tile_id
            for tile_id, name in TILE_DICTIONARY.items()
            if name in EMPTY_TILE_NAMES
        }
        BEDROCK_TILE_IDS = {
            tile_id
            for tile_id, name in TILE_DICTIONARY.items()
            if name in BEDROCK_TILE_NAMES
        }
        DIRT_TILE_IDS = {
            tile_id
            for tile_id, name in TILE_DICTIONARY.items()
            if name in DIRT_TILE_NAMES
        }

        # Load sprite textures from files
        self.textures = {}
        for tile_id, sprite_name in TILE_DICTIONARY.items():
            if sprite_name not in self.textures:
                path = os.path.join(SPRITES_PATH, f"{sprite_name}.png")
                self.textures[sprite_name] = arcade.load_texture(path)

        # Load horizontal transition textures
        horizontal_transition_textures = {}
        for key, sprite_name in HORIZONTAL_TRANSITION_TEXTURES.items():
            path = os.path.join(SPRITES_PATH, f"{sprite_name}.png")
            horizontal_transition_textures[key] = arcade.load_texture(path)

        # Load vertical transition textures
        vertical_transition_textures = {}
        for key, sprite_name in VERTICAL_TRANSITION_TEXTURES.items():
            path = os.path.join(SPRITES_PATH, f"{sprite_name}.png")
            vertical_transition_textures[key] = arcade.load_texture(path)

        # Build transition texture lookup tables
        # Index 0 = transparent
        # Indices 1-4 = normal transitions
        # Indices 5-8 = burnt transitions (same order, offset by 4)
        self.horizontal_transition_textures_list = [
            transparent_texture,
            horizontal_transition_textures["empty_bedrock"],      # 1
            horizontal_transition_textures["bedrock_empty"],      # 2
            horizontal_transition_textures["empty_dirt"],         # 3
            horizontal_transition_textures["dirt_empty"],         # 4
            horizontal_transition_textures["empty_bedrock_burnt"],  # 5
            horizontal_transition_textures["bedrock_empty_burnt"],  # 6
            horizontal_transition_textures["empty_dirt_burnt"],     # 7
            horizontal_transition_textures["dirt_empty_burnt"],     # 8
        ]
        self.vertical_transition_textures_list = [
            transparent_texture,
            vertical_transition_textures["empty_bedrock"],      # 1
            vertical_transition_textures["bedrock_empty"],      # 2
            vertical_transition_textures["empty_dirt"],         # 3
            vertical_transition_textures["dirt_empty"],         # 4
            vertical_transition_textures["empty_bedrock_burnt"],  # 5
            vertical_transition_textures["bedrock_empty_burnt"],  # 6
            vertical_transition_textures["empty_dirt_burnt"],     # 7
            vertical_transition_textures["dirt_empty_burnt"],     # 8
        ]

        # Lookup tables: [effective_tile_id_1, effective_tile_id_2] -> texture index
        # 512x512 to accommodate burnt empty IDs (normal ID + 256)
        self.horizontal_transition_lookup = np.zeros((512, 512), dtype=np.uint8)
        self.vertical_transition_lookup = np.zeros((512, 512), dtype=np.uint8)

        empty_ids = np.array(list(EMPTY_TILE_IDS))
        bedrock_ids = np.array(list(BEDROCK_TILE_IDS))
        dirt_ids = np.array(list(DIRT_TILE_IDS))
        burnt_empty_ids = empty_ids + BURNT_EMPTY_OFFSET

        # Empty <-> Bedrock transitions (normal)
        self.horizontal_transition_lookup[np.ix_(empty_ids, bedrock_ids)] = 1
        self.horizontal_transition_lookup[np.ix_(bedrock_ids, empty_ids)] = 2
        self.vertical_transition_lookup[np.ix_(empty_ids, bedrock_ids)] = 1
        self.vertical_transition_lookup[np.ix_(bedrock_ids, empty_ids)] = 2

        # Empty <-> Dirt transitions (normal)
        self.horizontal_transition_lookup[np.ix_(empty_ids, dirt_ids)] = 3
        self.horizontal_transition_lookup[np.ix_(dirt_ids, empty_ids)] = 4
        self.vertical_transition_lookup[np.ix_(empty_ids, dirt_ids)] = 3
        self.vertical_transition_lookup[np.ix_(dirt_ids, empty_ids)] = 4

        # Burnt empty <-> Bedrock transitions
        self.horizontal_transition_lookup[np.ix_(burnt_empty_ids, bedrock_ids)] = 5
        self.horizontal_transition_lookup[np.ix_(bedrock_ids, burnt_empty_ids)] = 6
        self.vertical_transition_lookup[np.ix_(burnt_empty_ids, bedrock_ids)] = 5
        self.vertical_transition_lookup[np.ix_(bedrock_ids, burnt_empty_ids)] = 6

        # Burnt empty <-> Dirt transitions
        self.horizontal_transition_lookup[np.ix_(burnt_empty_ids, dirt_ids)] = 7
        self.horizontal_transition_lookup[np.ix_(dirt_ids, burnt_empty_ids)] = 8
        self.vertical_transition_lookup[np.ix_(burnt_empty_ids, dirt_ids)] = 7
        self.vertical_transition_lookup[np.ix_(dirt_ids, burnt_empty_ids)] = 8

        # Corner bedrock tiles have directional transitions
        # The direction in the name indicates the dirt side(s)
        # Horizontal: tile1 exposes RIGHT side, tile2 exposes LEFT side
        # Vertical: tile1 exposes BOTTOM side, tile2 exposes TOP side

        # bedrock_nw: top=dirt, left=dirt, bottom=bedrock, right=bedrock
        self.horizontal_transition_lookup[BEDROCK_NW_ID, empty_ids] = 2  # right=bedrock
        self.horizontal_transition_lookup[empty_ids, BEDROCK_NW_ID] = 3  # left=dirt
        self.vertical_transition_lookup[BEDROCK_NW_ID, empty_ids] = 2   # bottom=bedrock
        self.vertical_transition_lookup[empty_ids, BEDROCK_NW_ID] = 3   # top=dirt
        self.horizontal_transition_lookup[BEDROCK_NW_ID, burnt_empty_ids] = 6
        self.horizontal_transition_lookup[burnt_empty_ids, BEDROCK_NW_ID] = 7
        self.vertical_transition_lookup[BEDROCK_NW_ID, burnt_empty_ids] = 6
        self.vertical_transition_lookup[burnt_empty_ids, BEDROCK_NW_ID] = 7

        # bedrock_ne: top=dirt, right=dirt, bottom=bedrock, left=bedrock
        self.horizontal_transition_lookup[BEDROCK_NE_ID, empty_ids] = 4  # right=dirt
        self.horizontal_transition_lookup[empty_ids, BEDROCK_NE_ID] = 1  # left=bedrock
        self.vertical_transition_lookup[BEDROCK_NE_ID, empty_ids] = 2   # bottom=bedrock
        self.vertical_transition_lookup[empty_ids, BEDROCK_NE_ID] = 3   # top=dirt
        self.horizontal_transition_lookup[BEDROCK_NE_ID, burnt_empty_ids] = 8
        self.horizontal_transition_lookup[burnt_empty_ids, BEDROCK_NE_ID] = 5
        self.vertical_transition_lookup[BEDROCK_NE_ID, burnt_empty_ids] = 6
        self.vertical_transition_lookup[burnt_empty_ids, BEDROCK_NE_ID] = 7

        # bedrock_se: bottom=dirt, right=dirt, top=bedrock, left=bedrock
        self.horizontal_transition_lookup[BEDROCK_SE_ID, empty_ids] = 4  # right=dirt
        self.horizontal_transition_lookup[empty_ids, BEDROCK_SE_ID] = 1  # left=bedrock
        self.vertical_transition_lookup[BEDROCK_SE_ID, empty_ids] = 4   # bottom=dirt
        self.vertical_transition_lookup[empty_ids, BEDROCK_SE_ID] = 1   # top=bedrock
        self.horizontal_transition_lookup[BEDROCK_SE_ID, burnt_empty_ids] = 8
        self.horizontal_transition_lookup[burnt_empty_ids, BEDROCK_SE_ID] = 5
        self.vertical_transition_lookup[BEDROCK_SE_ID, burnt_empty_ids] = 8
        self.vertical_transition_lookup[burnt_empty_ids, BEDROCK_SE_ID] = 5

        # bedrock_sw: bottom=dirt, left=dirt, top=bedrock, right=bedrock
        self.horizontal_transition_lookup[BEDROCK_SW_ID, empty_ids] = 2  # right=bedrock
        self.horizontal_transition_lookup[empty_ids, BEDROCK_SW_ID] = 3  # left=dirt
        self.vertical_transition_lookup[BEDROCK_SW_ID, empty_ids] = 4   # bottom=dirt
        self.vertical_transition_lookup[empty_ids, BEDROCK_SW_ID] = 1   # top=bedrock
        self.horizontal_transition_lookup[BEDROCK_SW_ID, burnt_empty_ids] = 6
        self.horizontal_transition_lookup[burnt_empty_ids, BEDROCK_SW_ID] = 7
        self.vertical_transition_lookup[BEDROCK_SW_ID, burnt_empty_ids] = 8
        self.vertical_transition_lookup[burnt_empty_ids, BEDROCK_SW_ID] = 5

        # Precompute which tile IDs are "empty" for effective tilemap building
        self.is_empty_tile = np.zeros(256, dtype=np.uint16)
        for eid in EMPTY_TILE_IDS:
            self.is_empty_tile[eid] = BURNT_EMPTY_OFFSET

        # Map tile IDs to textures
        self.tile_id_to_texture_dictionary = list()

        for j in range(255):
            self.tile_id_to_texture_dictionary.insert(j, transparent_texture)

        for tile_id, sprite_name in TILE_DICTIONARY.items():
            self.tile_id_to_texture_dictionary.insert(
                tile_id, self.textures[sprite_name]
            )

        # Track which tiles have ever had an explosion (for burnt transitions)
        self.explosion_history = np.zeros((state.height, state.width), dtype=bool)

        # Background tile sprites - one per map tile at world positions
        self.background_tile_sprite_list = arcade.SpriteList()
        self.background_tile_sprite_list.initialize()
        self.background_tile_sprite_list.preload_textures(self.textures.values())
        tile_sprite_count = state.width * state.height
        self.sprites = [arcade.Sprite() for _ in range(tile_sprite_count)]

        # Position sprites at world coordinates (Y increases upward in world space)
        sprite_idx = 0
        for y in range(state.height):
            # World Y: row 0 at bottom, row (height-1) at top
            world_y = (state.height - 1 - y) * SPRITE_SIZE * zoom + SPRITE_CENTER_OFFSET * zoom
            for x in range(state.width):
                world_x = x * SPRITE_SIZE * zoom + SPRITE_CENTER_OFFSET * zoom
                sprite = self.sprites[sprite_idx]
                sprite.center_x = world_x
                sprite.center_y = world_y
                sprite.scale = zoom
                sprite.texture = transparent_texture
                sprite_idx += 1

        self.background_tile_sprite_list.extend(self.sprites)

        # Horizontal transition sprites - between columns
        h_transition_count = state.width * state.height
        self.horizontal_transition_sprite_list = arcade.SpriteList()
        self.horizontal_transition_sprite_list.initialize()
        self.horizontal_transition_sprite_list.preload_textures(
            horizontal_transition_textures.values()
        )
        self.horizontal_transition_sprites = [
            arcade.Sprite() for _ in range(h_transition_count)
        ]

        sprite_idx = 0
        for y in range(state.height):
            world_y = (state.height - 1 - y) * SPRITE_SIZE * zoom + SPRITE_CENTER_OFFSET * zoom
            for x in range(state.width):
                sprite = self.horizontal_transition_sprites[sprite_idx]
                # Position at midpoint between tile x and tile x+1
                world_x = (x + 1) * SPRITE_SIZE * zoom
                sprite.center_x = world_x
                sprite.center_y = world_y
                sprite.scale = zoom
                sprite.texture = transparent_texture
                sprite_idx += 1

        self.horizontal_transition_sprite_list.extend(self.horizontal_transition_sprites)

        # Vertical transition sprites - between rows
        v_transition_count = state.width * state.height
        self.vertical_transition_sprite_list = arcade.SpriteList()
        self.vertical_transition_sprite_list.initialize()
        self.vertical_transition_sprite_list.preload_textures(
            vertical_transition_textures.values()
        )
        self.vertical_transition_sprites = [arcade.Sprite() for _ in range(v_transition_count)]

        sprite_idx = 0
        for y in range(state.height):
            # Position at boundary between row y and row y+1
            world_y = (state.height - 1 - y - 1) * SPRITE_SIZE * zoom + SPRITE_SIZE * zoom
            for x in range(state.width):
                sprite = self.vertical_transition_sprites[sprite_idx]
                world_x = x * SPRITE_SIZE * zoom + SPRITE_CENTER_OFFSET * zoom
                sprite.center_x = world_x
                sprite.center_y = world_y
                sprite.scale = zoom
                sprite.texture = transparent_texture
                sprite_idx += 1

        self.vertical_transition_sprite_list.extend(self.vertical_transition_sprites)

    def on_update(self, state, view_start_x, view_end_x, view_start_y, view_end_y):
        """Update visible tile textures and transitions."""
        # Accumulate explosion history (OR in new explosions)
        self.explosion_history |= state.explosions.astype(bool)

        # Build effective tilemap: empty tiles with explosion history get shifted IDs
        # is_empty_tile[id] = 256 for empty tiles, 0 otherwise
        # explosion_history is bool, so multiplying gives 256 or 0
        effective_tilemap = state.tilemap.astype(np.uint16) + \
            self.is_empty_tile[state.tilemap] * self.explosion_history

        # Update only visible tile textures (no position updates needed - camera handles scrolling)
        for y in range(view_start_y, view_end_y):
            for x in range(view_start_x, view_end_x):
                sprite_idx = y * state.width + x
                self.sprites[sprite_idx].texture = self.tile_id_to_texture_dictionary[
                    state.tilemap[y, x]
                ]

        # Update visible horizontal transitions
        for y in range(view_start_y, view_end_y):
            for x in range(view_start_x, min(view_end_x, state.width - 1)):
                sprite_idx = y * state.width + x
                transition_idx = self.horizontal_transition_lookup[
                    effective_tilemap[y, x], effective_tilemap[y, x + 1]]
                self.horizontal_transition_sprites[sprite_idx].texture = \
                    self.horizontal_transition_textures_list[transition_idx]

        # Update visible vertical transitions
        for y in range(view_start_y, min(view_end_y, state.height - 1)):
            for x in range(view_start_x, view_end_x):
                sprite_idx = y * state.width + x
                transition_idx = self.vertical_transition_lookup[
                    effective_tilemap[y, x], effective_tilemap[y + 1, x]]
                self.vertical_transition_sprites[sprite_idx].texture = \
                    self.vertical_transition_textures_list[transition_idx]
