"""
Renderer for lanibombers.
Main graphics processing and display loop.
"""

import os
import time
from dataclasses import dataclass, field
from typing import List
from enum import Enum
import arcade
import array


# ============================================================================
# Dynamic Entities
# ============================================================================

class Direction(Enum):
    UP = 'up'
    DOWN = 'down'
    LEFT = 'left'
    RIGHT = 'right'


class EntityType(Enum):
    PLAYER = 'player'
    FURRYMAN = 'furryman'
    SLIME = 'slime'
    ALIEN = 'alien'
    GRENADEMONSTER = 'grenademonster'


@dataclass
class DynamicEntity:
    x: float
    y: float
    direction: Direction
    entity_type: EntityType
    name: str = ''
    colour: tuple = (255, 255, 255)
    speed: float = 0.0
    state: str = 'idle'
    sprite_id: int = 1  # Used for player entities (1-4)

# ============================================================================
# Configuration
# ============================================================================

MAP_PATH = os.path.join(os.path.dirname(__file__), 'assets', 'maps', 'ANZULABY.MNE')
SPRITES_PATH = os.path.join(os.path.dirname(__file__), 'assets', 'sprites')

TARGET_FPS = 60
VSYNC = True

SPRITE_SIZE = 10
SPRITE_CENTER_OFFSET = SPRITE_SIZE // 2

# Size of performance graphs and distance between them
GRAPH_WIDTH = 200
GRAPH_HEIGHT = 120
GRAPH_MARGIN = 5

# Map tile IDs to sprite names
TILE_DICTIONARY = {
    # Basic terrain
    48: 'empty',     
    49: 'concrete',  
    50: 'dirt1',     
    51: 'dirt2',     
    52: 'dirt3',     
    53: 'gravel1',   
    54: 'gravel2',   
    55: 'bedrock_nw',
    56: 'bedrock_ne',
    57: 'bedrock_se',
    #
    # 
    65: 'bedrock_sw',       
    66: 'boulder',          
    67: 'bedrock1',         
    68: 'bedrock2',         
    69: 'bedrock3',         
    70: 'bedrock4',         
    71: 'furryman_right_1', # FURRYMAN
    # more furryman
    # ??
    74: 'furryman_right_1', # FURRYMAN
    79: 'slime_right_1',    # SLIME
    80: 'slime_right_1',    # SLIME
    81: 'slime_right_1',    # SLIME
    # more slime or alien?
    83: 'alien_right_1',    # ALIEN
    84: 'alien_right_1',    # ALIEN
    86: 'alien_right_1',    # ALIEN
    #
    #
    101: 'landmine',
    #
    #
    108: 'securitydoor',  
    109: 'medpack',      
    #
    111: 'bioslime',      
    112: 'rock2', 
    113: 'rock1',
    #
    #
    121: 'crate',          
    #
    #
    143: 'smallpick',       
    144: 'bigpick',         
    145: 'drill',           
    146: 'gold_shield',     
    147: 'gold_egg',        
    148: 'gold_coins',      
    149: 'gold_bracelet',   
    150: 'gold_bar',        
    151: 'gold_cross',      
    152: 'gold_sceptre',    
    153: 'gold_ruby',       
    154: 'gold_crown',      
    155: 'urethane_block',  
    156: 'tunnel',          
    #
    #
    164: 'crackerbarrel', 
    #
    #
    172: 'brics1',
    #
    #
    180: 'doorswitch_red',
}

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

# Sprite names grouped by type for transition lookups
EMPTY_SPRITE_NAMES = {
    'empty',
    'boulder',
    'landmine',
    'crate',
    'smallpick',
    'bigpick',
    'drill',
    'gold_shield',
    'gold_egg',
    'gold_coins',
    'gold_bracelet',
    'gold_bar',
    'gold_cross',
    'gold_sceptre',
    'gold_ruby',
    'gold_crown',
    'tunnel',
    'crackerbarrel',
}

BEDROCK_SPRITE_NAMES = {'bedrock1', 'bedrock2', 'bedrock3', 'bedrock4'}
DIRT_SPRITE_NAMES = {'dirt1', 'dirt2', 'dirt3'}

# Build tile ID sets from TILE_DICTIONARY
EMPTY_TILE_IDS = {tile_id for tile_id, name in TILE_DICTIONARY.items() if name in EMPTY_SPRITE_NAMES}
BEDROCK_TILE_IDS = {tile_id for tile_id, name in TILE_DICTIONARY.items() if name in BEDROCK_SPRITE_NAMES}
DIRT_TILE_IDS = {tile_id for tile_id, name in TILE_DICTIONARY.items() if name in DIRT_SPRITE_NAMES}


# ============================================================================
# Game State
# ============================================================================

@dataclass
class GameState:
    """Game state with dimensions and sprite indices"""
    width: int
    height: int
    tilemap: array.array('B')
    players: List[DynamicEntity] = field(default_factory=list)


# ============================================================================
# Mock Server
# ============================================================================

class MockServer:
    """Simulates a game server returning sprite index arrays"""

    def __init__(self, map_path=MAP_PATH):
        self._load_map(map_path)
        self._init_players()

    def _load_map(self, path):
        """Load map from ASCII file, sprite indices are ASCII values"""
        self.grid = array.array('B')
        with open(path, 'rb') as f:
            for line in f:
                line = line.rstrip(b'\r\n')
                for char in line:
                    self.grid.append(char)
        self.height = 45
        self.width = 64

    def _init_players(self):
        """Initialize mock players"""
        self.players = [
            DynamicEntity(x=9, y=9, direction=Direction.RIGHT, entity_type=EntityType.PLAYER, name='Player1', colour=(255, 0, 0), sprite_id=1, state='idle'),
            DynamicEntity(x=8, y=18, direction=Direction.RIGHT, entity_type=EntityType.PLAYER, name='Player2', colour=(0, 255, 0), sprite_id=2, state='walk'),
        ]
        self.start_time = time.time()
        # Player 2 movement pattern: start position
        self.player2_start_x = 8
        self.player2_start_y = 18

    def _update_player2_movement(self):
        """Move player 2 in a square pattern"""
        elapsed = time.time() - self.start_time
        # Pattern: 4s right, 1s stop, 4s down, 1s stop, 4s left, 1s stop, 4s up, 1s stop = 20s cycle
        # Speed: 1.5 blocks/second (6 blocks in 4 seconds)
        cycle_time = elapsed % 20.0
        player = self.players[1]
        speed = 1.5  # blocks per second

        if cycle_time < 4.0:
            # Moving right
            player.x = self.player2_start_x + cycle_time * speed
            player.y = self.player2_start_y
            player.direction = Direction.RIGHT
            player.state = 'walk'
        elif cycle_time < 5.0:
            # Stopped after right
            player.x = self.player2_start_x + 6
            player.y = self.player2_start_y
            player.direction = Direction.RIGHT
            player.state = 'idle'
        elif cycle_time < 9.0:
            # Moving down
            player.x = self.player2_start_x + 6
            player.y = self.player2_start_y + (cycle_time - 5.0) * speed
            player.direction = Direction.DOWN
            player.state = 'walk'
        elif cycle_time < 10.0:
            # Stopped after down
            player.x = self.player2_start_x + 6
            player.y = self.player2_start_y + 6
            player.direction = Direction.DOWN
            player.state = 'idle'
        elif cycle_time < 14.0:
            # Moving left
            player.x = self.player2_start_x + 6 - (cycle_time - 10.0) * speed
            player.y = self.player2_start_y + 6
            player.direction = Direction.LEFT
            player.state = 'walk'
        elif cycle_time < 15.0:
            # Stopped after left
            player.x = self.player2_start_x
            player.y = self.player2_start_y + 6
            player.direction = Direction.LEFT
            player.state = 'idle'
        elif cycle_time < 19.0:
            # Moving up
            player.x = self.player2_start_x
            player.y = self.player2_start_y + 6 - (cycle_time - 15.0) * speed
            player.direction = Direction.UP
            player.state = 'walk'
        else:
            # Stopped after up
            player.x = self.player2_start_x
            player.y = self.player2_start_y
            player.direction = Direction.UP
            player.state = 'idle'

    def get_game_state(self):
        """Returns GameState with dimensions and sprite indices"""
        self._update_player2_movement()
        return GameState(
            width=self.width,
            height=self.height,
            tilemap=self.grid,
            players=self.players
        )


# ============================================================================
# Player Sprite
# ============================================================================

class PlayerSprite(arcade.Sprite):
    """Extended sprite class for player entities with animation support"""

    def __init__(self, sprite_id: int, colour: tuple, player_textures: dict, transparent_texture, zoom: float, screen_height: int):
        super().__init__()
        self.sprite_id = sprite_id
        self.colour = colour
        self.player_textures = player_textures
        self.transparent_texture = transparent_texture
        self.zoom = zoom
        self.screen_height = screen_height

        # Animation state
        self.current_frame = 1
        self.frame_timer = 0.0
        self.frames_per_second = 4  # Animation speed

        # Previous state for idle frame persistence
        self.last_direction = Direction.DOWN
        self.last_frame = 1

        self.scale = zoom
        self.texture = transparent_texture

    def update_from_entity(self, player: DynamicEntity, delta_time: float):
        """Update sprite position, texture and animation from player entity data"""
        # Update position
        self.center_x = (player.x + 0.5) * SPRITE_SIZE * self.zoom
        self.center_y = self.screen_height - (player.y + 0.5) * SPRITE_SIZE * self.zoom

        # Update animation frame if walking or digging
        if player.state in ('walk', 'dig'):
            self.frame_timer += delta_time
            frame_duration = 1.0 / self.frames_per_second
            if self.frame_timer >= frame_duration:
                self.frame_timer -= frame_duration
                self.current_frame = (self.current_frame % 4) + 1
            self.last_direction = player.direction
            self.last_frame = self.current_frame
        else:
            # Idle: keep last frame from walk/dig animation
            self.frame_timer = 0.0

        # Get texture based on state
        frame_to_use = self.current_frame if player.state in ('walk', 'dig') else self.last_frame
        texture = self.player_textures.get(
            (self.sprite_id, player.state, player.direction, frame_to_use),
            self.transparent_texture
        )
        self.texture = texture


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
        state = server.get_game_state()
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
        state = self.server.get_game_state()

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

        # Update players
        for i, player in enumerate(state.players):
            self.player_sprites[i].update_from_entity(player, delta_time)

    def on_draw(self):
        """Render the game"""
        self.clear()
        self.background_tile_sprite_list.draw(pixelated=True)
        self.vertical_transition_sprite_list.draw(pixelated=True)
        self.horizontal_transition_sprite_list.draw(pixelated=True)
        self.player_sprite_list.draw(pixelated=True)
        self.perf_graph_list.draw()


# ============================================================================
# Main
# ============================================================================

def main():
    server = MockServer()
    state = server.get_game_state()
    print(f"Loaded map: {state.width}x{state.height}")
    print(f"Sprites: {SPRITES_PATH}")

    renderer = GameRenderer(server)
    arcade.run()


if __name__ == '__main__':
    main()
