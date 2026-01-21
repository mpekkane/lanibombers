"""
Renderer for lanibombers.
Main graphics processing and display loop.
"""

import os
import arcade
import numpy as np

from game_engine.entities import Direction, EntityType
from cfg.bomb_dictionary import BombType, BOMB_TYPE_TO_ICON

from renderer.sprites import (
    PlayerSprite,
    MonsterSprite,
    PickupSprite,
    BombSprite,
    ExplosionSprite,
)
from renderer.bitmap_text import BitmapText
from cfg.tile_dictionary import (
    TILE_DICTIONARY,
    EMPTY_TILE_NAMES,
    BEDROCK_TILE_NAMES,
    DIRT_TILE_NAMES,
    PLAYER_DEATH_SPRITE,
    MONSTER_DEATH_SPRITE,
    TREASURE_TILES,
    TOOL_TILES,
)


# ============================================================================
# Configuration
# ============================================================================

SPRITES_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "sprites")

TARGET_FPS = 60
VSYNC = True

SPRITE_SIZE = 10
SPRITE_CENTER_OFFSET = SPRITE_SIZE // 2
UI_TOP_MARGIN = 30  # Pixels of free space at top for UI (before zoom)

# Size of performance graphs and distance between them
GRAPH_WIDTH = 200
GRAPH_HEIGHT = 120
GRAPH_MARGIN = 5

# Horizontal transition textures (8x10 pixels, between columns)
HORIZONTAL_TRANSITION_TEXTURES = {
    "empty_bedrock": "transition_horizontal_empty_bedrock",
    "bedrock_empty": "transition_horizontal_bedrock_empty",
    "empty_dirt": "transition_horizontal_empty_dirt",
    "dirt_empty": "transition_horizontal_dirt_empty",
}

# Vertical transition textures (10x6 pixels, between rows)
VERTICAL_TRANSITION_TEXTURES = {
    "empty_bedrock": "transition_vertical_empty_bedrock",
    "bedrock_empty": "transition_vertical_bedrock_empty",
    "empty_dirt": "transition_vertical_empty_dirt",
    "dirt_empty": "transition_vertical_dirt_empty",
}


# ============================================================================
# Renderer
# ============================================================================


class GameRenderer(arcade.Window):
    """Main game window and renderer"""

    def __init__(self, server, width=1280, height=960, client_player_name: str = "", show_stats: bool = False):
        super().__init__(width, height, "lanibombers", vsync=VSYNC)
        self.client_player_name = client_player_name
        self.show_stats = show_stats
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

        self.set_update_rate(1 / TARGET_FPS)
        self.set_draw_rate(1 / TARGET_FPS)
        self.server = server

        self.zoom = min(width // 640, height // 480)

        # Load sprite textures from files
        self.textures = {}
        for tile_id, sprite_name in TILE_DICTIONARY.items():
            if sprite_name not in self.textures:
                path = os.path.join(SPRITES_PATH, f"{sprite_name}.png")
                self.textures[sprite_name] = arcade.load_texture(path)

        # Create transparent texture for empty transitions
        from PIL import Image

        transparent_image = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        self.transparent_texture = arcade.Texture(transparent_image)

        # Load death textures
        self.blood_texture = arcade.load_texture(
            os.path.join(SPRITES_PATH, f"{PLAYER_DEATH_SPRITE}.png")
        )
        self.blood_green_texture = arcade.load_texture(
            os.path.join(SPRITES_PATH, f"{MONSTER_DEATH_SPRITE}.png")
        )

        # Load horizontal transition textures
        self.horizontal_transition_textures = {}
        for key, sprite_name in HORIZONTAL_TRANSITION_TEXTURES.items():
            path = os.path.join(SPRITES_PATH, f"{sprite_name}.png")
            self.horizontal_transition_textures[key] = arcade.load_texture(path)

        # Load vertical transition textures
        self.vertical_transition_textures = {}
        for key, sprite_name in VERTICAL_TRANSITION_TEXTURES.items():
            path = os.path.join(SPRITES_PATH, f"{sprite_name}.png")
            self.vertical_transition_textures[key] = arcade.load_texture(path)

        # Load player textures: (sprite_id, state, direction, frame) -> texture
        self.player_textures = {}
        for sprite_id in range(1, 5):
            for direction in Direction:
                for frame in range(1, 5):
                    # Walking sprites
                    sprite_name = f"player{sprite_id}_{direction.value}_{frame}"
                    path = os.path.join(SPRITES_PATH, f"{sprite_name}.png")
                    walk_texture = arcade.load_texture(path)
                    self.player_textures[(sprite_id, "walk", direction, frame)] = (
                        walk_texture
                    )

                    # Idle sprites (same as walk, but won't animate)
                    self.player_textures[(sprite_id, "idle", direction, frame)] = (
                        walk_texture
                    )

                    # Digging sprites
                    sprite_name = f"player{sprite_id}_dig_{direction.value}_{frame}"
                    path = os.path.join(SPRITES_PATH, f"{sprite_name}.png")
                    self.player_textures[(sprite_id, "dig", direction, frame)] = (
                        arcade.load_texture(path)
                    )

        # Load monster textures: (entity_type, direction, frame) -> texture
        self.monster_textures = {}
        monster_types = [
            (EntityType.SLIME, "slime"),
            (EntityType.FURRYMAN, "furryman"),
            (EntityType.ALIEN, "alien"),
            (EntityType.GRENADEMONSTER, "grenademonster"),
        ]
        for entity_type, sprite_prefix in monster_types:
            for direction in Direction:
                for frame in range(1, 5):
                    sprite_name = f"{sprite_prefix}_{direction.value}_{frame}"
                    path = os.path.join(SPRITES_PATH, f"{sprite_name}.png")
                    texture = arcade.load_texture(path)
                    self.monster_textures[(entity_type, direction, frame)] = texture

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

        # Build transition texture lookup tables
        # Index 0 = transparent, other indices map to textures
        self.horizontal_transition_textures_list = [
            self.transparent_texture,
            self.horizontal_transition_textures["empty_bedrock"],
            self.horizontal_transition_textures["bedrock_empty"],
            self.horizontal_transition_textures["empty_dirt"],
            self.horizontal_transition_textures["dirt_empty"],
        ]
        self.vertical_transition_textures_list = [
            self.transparent_texture,
            self.vertical_transition_textures["empty_bedrock"],
            self.vertical_transition_textures["bedrock_empty"],
            self.vertical_transition_textures["empty_dirt"],
            self.vertical_transition_textures["dirt_empty"],
        ]

        # Lookup tables: [tile_id_1, tile_id_2] -> texture index
        self.horizontal_transition_lookup = np.zeros((256, 256), dtype=np.uint8)
        self.vertical_transition_lookup = np.zeros((256, 256), dtype=np.uint8)

        empty_ids = np.array(list(EMPTY_TILE_IDS))
        bedrock_ids = np.array(list(BEDROCK_TILE_IDS))
        dirt_ids = np.array(list(DIRT_TILE_IDS))

        # Empty <-> Bedrock transitions
        self.horizontal_transition_lookup[np.ix_(empty_ids, bedrock_ids)] = 1
        self.horizontal_transition_lookup[np.ix_(bedrock_ids, empty_ids)] = 2
        self.vertical_transition_lookup[np.ix_(empty_ids, bedrock_ids)] = 1
        self.vertical_transition_lookup[np.ix_(bedrock_ids, empty_ids)] = 2

        # Empty <-> Dirt transitions
        self.horizontal_transition_lookup[np.ix_(empty_ids, dirt_ids)] = 3
        self.horizontal_transition_lookup[np.ix_(dirt_ids, empty_ids)] = 4
        self.vertical_transition_lookup[np.ix_(empty_ids, dirt_ids)] = 3
        self.vertical_transition_lookup[np.ix_(dirt_ids, empty_ids)] = 4

        # Map tile IDs to textures
        self.tile_id_to_texture_dictionary = list()

        for j in range(255):
            self.tile_id_to_texture_dictionary.insert(j, self.transparent_texture)

        for tile_id, sprite_name in TILE_DICTIONARY.items():
            self.tile_id_to_texture_dictionary.insert(
                tile_id, self.textures[sprite_name]
            )

        # Background tile sprite pool
        self.background_tile_sprite_list = arcade.SpriteList()
        self.background_tile_sprite_list.initialize()
        self.background_tile_sprite_list.preload_textures(self.textures.values())
        state = server.get_render_state()
        max_sprites = state.width * state.height
        self.sprites = [arcade.Sprite() for _ in range(max_sprites)]

        # Calculate y offset for UI space at top
        self.ui_offset = UI_TOP_MARGIN * self.zoom
        ui_offset = self.ui_offset

        sprite_idx = 0
        for y in range(state.height):
            SPRITE_CENTER_Y = (
                self.height - ui_offset - (y * SPRITE_SIZE + SPRITE_CENTER_OFFSET) * self.zoom
            )
            for x in range(state.width):
                sprite = self.sprites[sprite_idx]
                sprite.center_x = (x * SPRITE_SIZE + SPRITE_CENTER_OFFSET) * self.zoom
                sprite.center_y = SPRITE_CENTER_Y
                sprite.scale = self.zoom
                sprite_idx += 1

        self.background_tile_sprite_list.extend(
            self.sprites[: state.height * state.width]
        )

        # Horizontal transition sprite pool (between columns)
        self.horizontal_transition_sprite_list = arcade.SpriteList()
        self.horizontal_transition_sprite_list.initialize()
        self.horizontal_transition_sprite_list.preload_textures(
            self.horizontal_transition_textures.values()
        )
        self.horizontal_transition_sprites = [
            arcade.Sprite() for _ in range(max_sprites)
        ]

        sprite_idx = 0
        for y in range(state.height):
            center_y = (
                self.height - ui_offset - (y * SPRITE_SIZE + SPRITE_CENTER_OFFSET) * self.zoom
            )
            for x in range(state.width):
                sprite = self.horizontal_transition_sprites[sprite_idx]
                # Position at midpoint between tile x and tile x+1 (offset by 1)
                sprite.center_x = (x + 1) * SPRITE_SIZE * self.zoom
                sprite.center_y = center_y
                sprite.scale = self.zoom
                sprite.texture = self.transparent_texture
                sprite_idx += 1

        self.horizontal_transition_sprite_list.extend(
            self.horizontal_transition_sprites[:max_sprites]
        )

        # Vertical transition sprite pool (between rows)
        self.vertical_transition_sprite_list = arcade.SpriteList()
        self.vertical_transition_sprite_list.initialize()
        self.vertical_transition_sprite_list.preload_textures(
            self.vertical_transition_textures.values()
        )
        self.vertical_transition_sprites = [arcade.Sprite() for _ in range(max_sprites)]

        sprite_idx = 0
        for y in range(state.height):
            # Position at boundary between row y and row y+1 (offset by 1)
            center_y = self.height - ui_offset - (y + 1) * SPRITE_SIZE * self.zoom
            for x in range(state.width):
                sprite = self.vertical_transition_sprites[sprite_idx]
                sprite.center_x = (x * SPRITE_SIZE + SPRITE_CENTER_OFFSET) * self.zoom
                sprite.center_y = center_y
                sprite.scale = self.zoom
                sprite.texture = self.transparent_texture
                sprite_idx += 1

        self.vertical_transition_sprite_list.extend(
            self.vertical_transition_sprites[:max_sprites]
        )

        # Player sprite pool
        self.player_sprite_list = arcade.SpriteList()
        self.player_sprite_list.initialize()
        self.player_sprite_list.preload_textures(self.player_textures.values())
        self.player_sprites = []

        for player in state.players:
            sprite = PlayerSprite(
                sprite_id=player.sprite_id,
                color_variant=player.color,
                player_textures=self.player_textures,
                transparent_texture=self.transparent_texture,
                blood_texture=self.blood_texture,
                zoom=self.zoom,
                screen_height=self.height,
                y_offset=self.ui_offset,
            )
            self.player_sprites.append(sprite)

        self.player_sprite_list.extend(self.player_sprites)

        # Monster sprite pool
        self.monster_sprite_list = arcade.SpriteList()
        self.monster_sprite_list.initialize()
        self.monster_sprite_list.preload_textures(self.monster_textures.values())
        self.monster_sprites = []

        for monster in state.monsters:
            sprite = MonsterSprite(
                entity_type=monster.entity_type,
                monster_textures=self.monster_textures,
                transparent_texture=self.transparent_texture,
                blood_green_texture=self.blood_green_texture,
                zoom=self.zoom,
                screen_height=self.height,
                y_offset=self.ui_offset,
            )
            self.monster_sprites.append(sprite)

        self.monster_sprite_list.extend(self.monster_sprites)

        # Pickup textures: visual_id -> texture (for treasures and tools)
        self.pickup_textures = {}
        pickup_tile_ids = set(TREASURE_TILES.keys()) | set(TOOL_TILES.keys())
        for tile_id in pickup_tile_ids:
            sprite_name = TILE_DICTIONARY.get(tile_id)
            if sprite_name:
                path = os.path.join(SPRITES_PATH, f"{sprite_name}.png")
                self.pickup_textures[tile_id] = arcade.load_texture(path)

        # Pickup sprite list (dynamic length)
        self.pickup_sprite_list = arcade.SpriteList()
        self.pickup_sprite_list.initialize()
        self.pickup_sprite_list.preload_textures(self.pickup_textures.values())
        self.pickup_sprites = []

        for pickup in state.pickups:
            sprite = PickupSprite(
                pickup_textures=self.pickup_textures,
                transparent_texture=self.transparent_texture,
                zoom=self.zoom,
                screen_height=self.height,
                y_offset=self.ui_offset,
            )
            sprite.update_from_pickup(pickup)
            self.pickup_sprites.append(sprite)

        self.pickup_sprite_list.extend(self.pickup_sprites)

        # Bomb textures: (bomb_type, state, frame) -> texture
        self.bomb_textures = {}
        self._load_bomb_textures()

        # Bomb sprite list (dynamic length)
        self.bomb_sprite_list = arcade.SpriteList()
        self.bomb_sprite_list.initialize()
        self.bomb_sprite_list.preload_textures(self.bomb_textures.values())
        self.bomb_sprites = []

        for bomb in state.bombs:
            sprite = BombSprite(
                bomb_textures=self.bomb_textures,
                transparent_texture=self.transparent_texture,
                zoom=self.zoom,
                screen_height=self.height,
                y_offset=self.ui_offset,
            )
            sprite.update_from_bomb(bomb)
            self.bomb_sprites.append(sprite)

        self.bomb_sprite_list.extend(self.bomb_sprites)

        # Explosion textures indexed by frame (0=transparent, 1=explosion, 2=smoke1, 3=smoke2)
        self.explosion_frame_textures = [
            self.transparent_texture,
            arcade.load_texture(os.path.join(SPRITES_PATH, "explosion.png")),
            arcade.load_texture(os.path.join(SPRITES_PATH, "smoke1.png")),
            arcade.load_texture(os.path.join(SPRITES_PATH, "smoke2.png")),
        ]

        # Explosion sprite list (static, one sprite per tile)
        self.explosion_sprite_list = arcade.SpriteList()
        self.explosion_sprite_list.initialize()
        self.explosion_sprite_list.preload_textures(self.explosion_frame_textures)

        sprite_idx = 0
        for y in range(state.height):
            center_y = (
                self.height - ui_offset - (y * SPRITE_SIZE + SPRITE_CENTER_OFFSET) * self.zoom
            )
            for x in range(state.width):
                sprite = ExplosionSprite(
                    explosion_textures=self.explosion_frame_textures,
                    transparent_texture=self.transparent_texture,
                    zoom=self.zoom,
                    screen_height=self.height,
                )
                sprite.center_x = (x * SPRITE_SIZE + SPRITE_CENTER_OFFSET) * self.zoom
                sprite.center_y = center_y
                sprite.scale = self.zoom
                sprite.texture = self.transparent_texture
                sprite_idx += 1
                self.explosion_sprite_list.append(sprite)

        # Header UI sprite list
        self.header_sprite_list = arcade.SpriteList()
        self.header_sprite_list.initialize()

        # Player card sprite (110x30 pixels, positioned at top-left corner)
        self.player_card_sprite = arcade.Sprite()
        self.player_card_sprite.texture = self.transparent_texture
        self.player_card_sprite.scale = self.zoom
        # Position at top-left: center_x = half width, center_y = screen height - half height
        card_width = 110
        card_height = 30
        self.player_card_sprite.center_x = (card_width / 2) * self.zoom
        self.player_card_sprite.center_y = self.height - (card_height / 2) * self.zoom
        self.header_sprite_list.append(self.player_card_sprite)

        # Bitmap text for header
        font_path = os.path.join(SPRITES_PATH, "font.png")
        self.bitmap_text = BitmapText(font_path, zoom=self.zoom)

        # Player name text sprite list (updated in update_header)
        self.player_name_sprites = arcade.SpriteList()
        self.current_player_name = None  # Use None so first comparison triggers text creation

        # Fight power and money text sprite lists
        self.dig_power_sprites = arcade.SpriteList()
        self.money_sprites = arcade.SpriteList()
        self.current_dig_power = None
        self.current_money = None

        # Inventory icons sprite list (updated in update_header)
        self.inventory_sprites = arcade.SpriteList()
        self.inventory_count_sprites = arcade.SpriteList()  # Text for item counts
        self.inventory_hatch_sprites = arcade.SpriteList()  # Hatch overlay for non-selected
        self.current_inventory = None  # Track inventory to detect changes
        self.current_selected = None  # Track selected index to detect changes

        # Performance graph (only if show_stats is enabled)
        self.perf_graph_list = arcade.SpriteList()
        if self.show_stats:
            arcade.enable_timings()

            # Calculate position helpers for the row of 3 performance graphs
            row_y = self.height - GRAPH_HEIGHT / 2
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

    def on_update(self, delta_time):
        """Poll server and update tilemap"""
        state = self.server.get_render_state()

        # Update background tiles
        for y in range(state.height):
            for x in range(state.width):
                i = y * state.width + x
                self.sprites[i].texture = self.tile_id_to_texture_dictionary[
                    state.tilemap[y, x]
                ]

        # Update horizontal transitions using sliding window view
        h_pairs = np.lib.stride_tricks.sliding_window_view(state.tilemap, (1, 2))[:, :, 0, :]
        h_indices = self.horizontal_transition_lookup[h_pairs[:, :, 0], h_pairs[:, :, 1]].ravel()

        for y in range(state.height):
            for x in range(state.width - 1):
                self.horizontal_transition_sprites[y * state.width + x].texture = \
                    self.horizontal_transition_textures_list[h_indices[y * (state.width - 1) + x]]

        # Update vertical transitions using sliding window view
        v_pairs = np.lib.stride_tricks.sliding_window_view(state.tilemap, (2, 1))[:, :, :, 0]
        v_indices = self.vertical_transition_lookup[v_pairs[:, :, 0], v_pairs[:, :, 1]].ravel()

        for i, idx in enumerate(v_indices):
            self.vertical_transition_sprites[i].texture = self.vertical_transition_textures_list[idx]

        # Update pickups (dynamic list)
        pickup_count = len(state.pickups)
        current_count = len(self.pickup_sprites)

        # Add new sprites if needed
        while len(self.pickup_sprites) < pickup_count:
            sprite = PickupSprite(
                pickup_textures=self.pickup_textures,
                transparent_texture=self.transparent_texture,
                zoom=self.zoom,
                screen_height=self.height,
                y_offset=self.ui_offset,
            )
            self.pickup_sprites.append(sprite)
            self.pickup_sprite_list.append(sprite)

        # Remove excess sprites if needed
        while len(self.pickup_sprites) > pickup_count:
            sprite = self.pickup_sprites.pop()
            self.pickup_sprite_list.remove(sprite)

        # Update existing sprites
        for i, pickup in enumerate(state.pickups):
            self.pickup_sprites[i].update_from_pickup(pickup)

        # Update bombs (dynamic list)
        bomb_count = len(state.bombs)

        # Add new sprites if needed
        while len(self.bomb_sprites) < bomb_count:
            sprite = BombSprite(
                bomb_textures=self.bomb_textures,
                transparent_texture=self.transparent_texture,
                zoom=self.zoom,
                screen_height=self.height,
                y_offset=self.ui_offset,
            )
            self.bomb_sprites.append(sprite)
            self.bomb_sprite_list.append(sprite)

        # Remove excess sprites if needed
        while len(self.bomb_sprites) > bomb_count:
            sprite = self.bomb_sprites.pop()
            self.bomb_sprite_list.remove(sprite)

        # Update existing sprites
        for i, bomb in enumerate(state.bombs):
            self.bomb_sprites[i].update_from_bomb(bomb)

        # Update explosions (static list, texture based on 2D array)
        for y in range(state.height):
            for x in range(state.width):
                i = y * state.width + x
                explosion_type = state.explosions[y, x]
                self.explosion_sprite_list[i].update_from_type(explosion_type)

        # Update monsters
        for i, monster in enumerate(state.monsters):
            self.monster_sprites[i].update_from_entity(monster, delta_time)

        # Update players
        for i, player in enumerate(state.players):
            self.player_sprites[i].update_from_entity(player, delta_time)

        # Update header UI
        self.update_header(state.players, self.client_player_name)

    def update_header(self, players, client_player_name: str):
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
            text_y = self.height - self.zoom
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
            text_y = self.height - 11 * self.zoom
            self.dig_power_sprites = self.bitmap_text.create_text_sprites(
                f"{client_player.get_dig_power()}", text_x, text_y, color=(255, 0, 0, 255)
            )

        # Update money text (only recreate if changed)
        if client_player.money != self.current_money:
            self.current_money = client_player.money
            # Position: 26 pixels from left, 21 pixels down (11+11-1)
            text_x = 26 * self.zoom
            text_y = self.height - 21 * self.zoom
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
                icon_center_y = self.height - (icon_size / 2) * self.zoom

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
                    self.height - 1 * self.zoom,  # 1 pixel from top
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
                    separator_sprite.center_y = self.height - (icon_size / 2) * self.zoom
                    self.inventory_sprites.append(separator_sprite)
                    # Move x position past the separator
                    icon_x += separator_width * self.zoom

    def _load_bomb_textures(self):
        """Load all bomb textures into self.bomb_textures dict."""
        # Helper to load animated bomb with 3 frames
        def load_animated(bomb_type, base_name, has_defused=True):
            for frame in range(1, 4):
                path = os.path.join(SPRITES_PATH, f"{base_name}{frame}.png")
                self.bomb_textures[(bomb_type, "active", frame)] = arcade.load_texture(path)
            if has_defused:
                path = os.path.join(SPRITES_PATH, f"{base_name}_defused.png")
                self.bomb_textures[(bomb_type, "defused", 0)] = arcade.load_texture(path)

        # Helper to load single-frame bomb (same texture for all frames)
        def load_static(bomb_type, sprite_name, defused_name=None):
            path = os.path.join(SPRITES_PATH, f"{sprite_name}.png")
            texture = arcade.load_texture(path)
            for frame in range(1, 4):
                self.bomb_textures[(bomb_type, "active", frame)] = texture
            if defused_name:
                defused_path = os.path.join(SPRITES_PATH, f"{defused_name}.png")
                self.bomb_textures[(bomb_type, "defused", 0)] = arcade.load_texture(defused_path)
            else:
                self.bomb_textures[(bomb_type, "defused", 0)] = texture

        # Animated bombs (3 frames + defused)
        load_animated(BombType.BIG_BOMB, "bigbomb")
        load_animated(BombType.SMALL_BOMB, "smallbomb")
        load_animated(BombType.DYNAMITE, "dynamite")
        load_animated(BombType.NUKE, "nuke", has_defused=False)

        # Static bombs (single frame)
        load_static(BombType.C4, "c4_bomb")
        load_static(BombType.URETHANE, "urethane")
        load_static(BombType.LANDMINE, "landmine")
        load_static(BombType.SMALL_CROSS_BOMB, "smallcrucifix")
        load_static(BombType.BIG_CROSS_BOMB, "bigcrucifix")

    def on_draw(self):
        """Render the game"""
        self.clear()
        self.background_tile_sprite_list.draw(pixelated=True)
        self.vertical_transition_sprite_list.draw(pixelated=True)
        self.horizontal_transition_sprite_list.draw(pixelated=True)
        self.pickup_sprite_list.draw(pixelated=True)
        self.bomb_sprite_list.draw(pixelated=True)
        self.monster_sprite_list.draw(pixelated=True)
        self.player_sprite_list.draw(pixelated=True)
        self.explosion_sprite_list.draw(pixelated=True)
        self.header_sprite_list.draw(pixelated=True)
        self.player_name_sprites.draw(pixelated=True)
        self.dig_power_sprites.draw(pixelated=True)
        self.money_sprites.draw(pixelated=True)
        self.inventory_sprites.draw(pixelated=True)
        self.inventory_hatch_sprites.draw(pixelated=True)
        self.inventory_count_sprites.draw(pixelated=True)
        if self.show_stats:
            self.perf_graph_list.draw()

    def run(self):
        arcade.run()
