"""
Renderer for lanibombers.
Main graphics processing and display loop.
"""

import os
import arcade

from cfg.tile_dictionary import (
    TILE_DICTIONARY,
    EMPTY_TILE_NAMES,
    BEDROCK_TILE_NAMES,
    DIRT_TILE_NAMES,
)
from game_engine.entities import Direction, EntityType
from renderer.sprites import PlayerSprite, MonsterSprite
from mock_server import MockServer


# ============================================================================
# Configuration
# ============================================================================

SPRITES_PATH = os.path.join(os.path.dirname(__file__), 'assets', 'sprites')

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
    'empty_bedrock': 'transition_horizontal_empty_bedrock',
    'bedrock_empty': 'transition_horizontal_bedrock_empty',
    'empty_dirt': 'transition_horizontal_empty_dirt',
    'dirt_empty': 'transition_horizontal_dirt_empty',
}

# Vertical transition textures (10x6 pixels, between rows)
VERTICAL_TRANSITION_TEXTURES = {
    'empty_bedrock': 'transition_vertical_empty_bedrock',
    'bedrock_empty': 'transition_vertical_bedrock_empty',
    'empty_dirt': 'transition_vertical_empty_dirt',
    'dirt_empty': 'transition_vertical_dirt_empty',
}

# Build tile ID sets from TILE_DICTIONARY
EMPTY_TILE_IDS = {tile_id for tile_id, name in TILE_DICTIONARY.items() if name in EMPTY_TILE_NAMES}
BEDROCK_TILE_IDS = {tile_id for tile_id, name in TILE_DICTIONARY.items() if name in BEDROCK_TILE_NAMES}
DIRT_TILE_IDS = {tile_id for tile_id, name in TILE_DICTIONARY.items() if name in DIRT_TILE_NAMES}


# ============================================================================
# Renderer
# ============================================================================

class GameRenderer(arcade.Window):
    """Main game window and renderer"""

    def __init__(self, server, width=1280, height=960):
        super().__init__(width, height, "lanibombers", vsync=VSYNC)
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
        transparent_image = Image.new('RGBA', (1, 1), (0, 0, 0, 0))
        self.transparent_texture = arcade.Texture(transparent_image)

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
                    self.player_textures[(sprite_id, 'walk', direction, frame)] = walk_texture

                    # Idle sprites (same as walk, but won't animate)
                    self.player_textures[(sprite_id, 'idle', direction, frame)] = walk_texture

                    # Digging sprites
                    sprite_name = f"player{sprite_id}_dig_{direction.value}_{frame}"
                    path = os.path.join(SPRITES_PATH, f"{sprite_name}.png")
                    self.player_textures[(sprite_id, 'dig', direction, frame)] = arcade.load_texture(path)

        # Load monster textures: (entity_type, direction, frame) -> texture
        self.monster_textures = {}
        monster_types = [
            (EntityType.SLIME, 'slime'),
            (EntityType.FURRYMAN, 'furryman'),
            (EntityType.ALIEN, 'alien'),
            (EntityType.GRENADEMONSTER, 'grenademonster'),
        ]
        for entity_type, sprite_prefix in monster_types:
            for direction in Direction:
                for frame in range(1, 5):
                    sprite_name = f"{sprite_prefix}_{direction.value}_{frame}"
                    path = os.path.join(SPRITES_PATH, f"{sprite_name}.png")
                    texture = arcade.load_texture(path)
                    self.monster_textures[(entity_type, direction, frame)] = texture

        # Build tile pair to transition texture dictionaries
        # Key: (tile_id_left, tile_id_right) for horizontal, (tile_id_top, tile_id_bottom) for vertical
        self.horizontal_tile_pair_to_texture = {}
        self.vertical_tile_pair_to_texture = {}

        # Empty <-> Bedrock transitions
        for empty_id in EMPTY_TILE_IDS:
            for bedrock_id in BEDROCK_TILE_IDS:
                self.horizontal_tile_pair_to_texture[(empty_id, bedrock_id)] = self.horizontal_transition_textures['empty_bedrock']
                self.horizontal_tile_pair_to_texture[(bedrock_id, empty_id)] = self.horizontal_transition_textures['bedrock_empty']
                self.vertical_tile_pair_to_texture[(empty_id, bedrock_id)] = self.vertical_transition_textures['empty_bedrock']
                self.vertical_tile_pair_to_texture[(bedrock_id, empty_id)] = self.vertical_transition_textures['bedrock_empty']

        # Empty <-> Dirt transitions
        for empty_id in EMPTY_TILE_IDS:
            for dirt_id in DIRT_TILE_IDS:
                self.horizontal_tile_pair_to_texture[(empty_id, dirt_id)] = self.horizontal_transition_textures['empty_dirt']
                self.horizontal_tile_pair_to_texture[(dirt_id, empty_id)] = self.horizontal_transition_textures['dirt_empty']
                self.vertical_tile_pair_to_texture[(empty_id, dirt_id)] = self.vertical_transition_textures['empty_dirt']
                self.vertical_tile_pair_to_texture[(dirt_id, empty_id)] = self.vertical_transition_textures['dirt_empty']

        # Map tile IDs to textures
        self.tile_id_to_texture_dictionary = list()

        for j in range(255):
            self.tile_id_to_texture_dictionary.insert(j, self.transparent_texture)

        for tile_id, sprite_name in TILE_DICTIONARY.items():
            self.tile_id_to_texture_dictionary.insert(tile_id, self.textures[sprite_name])


        # Background tile sprite pool
        self.background_tile_sprite_list = arcade.SpriteList()
        self.background_tile_sprite_list.initialize()
        self.background_tile_sprite_list.preload_textures(self.textures.values())
        state = server.get_render_state()
        max_sprites = state.width * state.height
        self.sprites = [arcade.Sprite() for _ in range(max_sprites)]

        sprite_idx = 0
        for y in range(state.height):
            SPRITE_CENTER_Y = self.height - (y * SPRITE_SIZE + SPRITE_CENTER_OFFSET) * self.zoom
            for x in range(state.width):
                sprite = self.sprites[sprite_idx]
                sprite.center_x = (x * SPRITE_SIZE + SPRITE_CENTER_OFFSET) * self.zoom
                sprite.center_y = SPRITE_CENTER_Y
                sprite.scale = self.zoom
                sprite_idx += 1

        self.background_tile_sprite_list.extend(self.sprites[:state.height * state.width])

        # Horizontal transition sprite pool (between columns)
        self.horizontal_transition_sprite_list = arcade.SpriteList()
        self.horizontal_transition_sprite_list.initialize()
        self.horizontal_transition_sprite_list.preload_textures(self.horizontal_transition_textures.values())
        self.horizontal_transition_sprites = [arcade.Sprite() for _ in range(max_sprites)]

        sprite_idx = 0
        for y in range(state.height):
            center_y = self.height - (y * SPRITE_SIZE + SPRITE_CENTER_OFFSET) * self.zoom
            for x in range(state.width):
                sprite = self.horizontal_transition_sprites[sprite_idx]
                # Position at midpoint between tile x and tile x+1 (offset by 1)
                sprite.center_x = (x + 1) * SPRITE_SIZE * self.zoom
                sprite.center_y = center_y
                sprite.scale = self.zoom
                sprite_idx += 1

        self.horizontal_transition_sprite_list.extend(self.horizontal_transition_sprites[:max_sprites])

        # Vertical transition sprite pool (between rows)
        self.vertical_transition_sprite_list = arcade.SpriteList()
        self.vertical_transition_sprite_list.initialize()
        self.vertical_transition_sprite_list.preload_textures(self.vertical_transition_textures.values())
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
                sprite_idx += 1

        self.vertical_transition_sprite_list.extend(self.vertical_transition_sprites[:max_sprites])

        # Player sprite pool
        self.player_sprite_list = arcade.SpriteList()
        self.player_sprite_list.initialize()
        self.player_sprite_list.preload_textures(self.player_textures.values())
        self.player_sprites = []

        for player in state.players:
            sprite = PlayerSprite(
                sprite_id=player.sprite_id,
                colour=player.colour,
                player_textures=self.player_textures,
                transparent_texture=self.transparent_texture,
                zoom=self.zoom,
                screen_height=self.height
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
                zoom=self.zoom,
                screen_height=self.height
            )
            self.monster_sprites.append(sprite)

        self.monster_sprite_list.extend(self.monster_sprites)

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
        self.perf_graph_list.append(graph)

        # Create the on_update graph
        graph = arcade.PerfGraph(GRAPH_WIDTH, GRAPH_HEIGHT, graph_data="on_update")
        graph.position = starting_x + step_x, row_y
        self.perf_graph_list.append(graph)

        # Create the on_draw graph
        graph = arcade.PerfGraph(GRAPH_WIDTH, GRAPH_HEIGHT, graph_data="on_draw")
        graph.position = starting_x + step_x * 2, row_y
        self.perf_graph_list.append(graph)

    def on_update(self, delta_time):
        """Poll server and update tilemap"""
        state = self.server.get_render_state()

        # Update background tiles
        for i in range(state.height * state.width):
            self.sprites[i].texture = self.tile_id_to_texture_dictionary[state.tilemap[i]]

        # Update horizontal transitions
        for i in range(state.height * state.width):
            # Check if we're at the right edge of a row (no tile to the right)
            if (i + 1) % state.width == 0:
                self.horizontal_transition_sprites[i].texture = self.transparent_texture
            else:
                left_tile = state.tilemap[i]
                right_tile = state.tilemap[i + 1]
                texture = self.horizontal_tile_pair_to_texture.get((left_tile, right_tile), self.transparent_texture)
                self.horizontal_transition_sprites[i].texture = texture

        # Update vertical transitions
        last_row_start = (state.height - 1) * state.width
        for i in range(state.height * state.width):
            # Check if we're in the last row (no tile below)
            if i >= last_row_start:
                self.vertical_transition_sprites[i].texture = self.transparent_texture
            else:
                top_tile = state.tilemap[i]
                bottom_tile = state.tilemap[i + state.width]
                texture = self.vertical_tile_pair_to_texture.get((top_tile, bottom_tile), self.transparent_texture)
                self.vertical_transition_sprites[i].texture = texture

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
        self.monster_sprite_list.draw(pixelated=True)
        self.player_sprite_list.draw(pixelated=True)
        self.perf_graph_list.draw()


# ============================================================================
# Main
# ============================================================================

def main():
    server = MockServer()
    state = server.get_render_state()
    print(f"Loaded map: {state.width}x{state.height}")
    print(f"Sprites: {SPRITES_PATH}")

    renderer = GameRenderer(server)
    arcade.run()


if __name__ == '__main__':
    main()
