"""
Renderer for lanibombers.
Main graphics processing and display loop.
"""

import os
import arcade
import numpy as np

from game_engine.entities.bomb import BombType
from game_engine.entities import Direction, EntityType
from renderer.sprites import (
    PlayerSprite,
    MonsterSprite,
    PickupSprite,
    BombSprite,
    ExplosionSprite,
)
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

    def __init__(self, server, width=1280, height=960):
        super().__init__(width, height, "lanibombers", vsync=VSYNC)
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

        sprite_idx = 0
        for y in range(state.height):
            SPRITE_CENTER_Y = (
                self.height - (y * SPRITE_SIZE + SPRITE_CENTER_OFFSET) * self.zoom
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
                self.height - (y * SPRITE_SIZE + SPRITE_CENTER_OFFSET) * self.zoom
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
            center_y = self.height - (y + 1) * SPRITE_SIZE * self.zoom
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
            )
            sprite.update_from_pickup(pickup)
            self.pickup_sprites.append(sprite)

        self.pickup_sprite_list.extend(self.pickup_sprites)

        # Bomb textures: (bomb_type, state, frame) -> texture
        self.bomb_textures = {}
        # Big bomb - active frames 1-3 and defused
        for frame in range(1, 4):
            path = os.path.join(SPRITES_PATH, f"bigbomb{frame}.png")
            self.bomb_textures[(BombType.BIG_BOMB, "active", frame)] = (
                arcade.load_texture(path)
            )
        path = os.path.join(SPRITES_PATH, "bigbomb_defused.png")
        self.bomb_textures[(BombType.BIG_BOMB, "defused", 0)] = arcade.load_texture(
            path
        )

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
                self.height - (y * SPRITE_SIZE + SPRITE_CENTER_OFFSET) * self.zoom
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

        # Performance graph
        arcade.enable_timings()

        # Create a sprite list to put the performance graphs into
        self.perf_graph_list = arcade.SpriteList()

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
        self.perf_graph_list.draw()

    def run(self):
        arcade.run()
