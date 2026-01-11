"""
Renderer for lanibombers.
Main graphics processing and display loop.
"""

import os
from dataclasses import dataclass
from typing import List
import arcade
import array

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


# ============================================================================
# Game State
# ============================================================================

@dataclass
class GameState:
    """Game state with dimensions and sprite indices"""
    width: int
    height: int
    tilemap: array.array('B')


# ============================================================================
# Mock Server
# ============================================================================

class MockServer:
    """Simulates a game server returning sprite index arrays"""

    def __init__(self, map_path=MAP_PATH):
        self._load_map(map_path)

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

    def get_game_state(self):
        """Returns GameState with dimensions and sprite indices"""
        return GameState(
            width=self.width,
            height=self.height,
            tilemap=self.grid
        )


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

        # Map tile IDs to textures
        self.tile_id_to_texture_dictionary = list()

        for j in range(255):
            self.tile_id_to_texture_dictionary.insert(tile_id, self.textures['empty'])

        for tile_id, sprite_name in TILE_DICTIONARY.items():
            self.tile_id_to_texture_dictionary.insert(tile_id, self.textures[sprite_name])


        # Sprite pool
        self.sprite_list = arcade.SpriteList()
        self.sprite_list.initialize()
        self.sprite_list.preload_textures(self.textures.values())
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

        self.sprite_list.extend(self.sprites[:state.height * state.width])

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

        sprite_idx = 0

        for i in range(state.height * state.width):
            self.sprites[i].texture = self.tile_id_to_texture_dictionary[state.tilemap[i]]


    def on_draw(self):
        """Render the game"""
        self.clear()
        self.sprite_list.draw(pixelated=True)
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
