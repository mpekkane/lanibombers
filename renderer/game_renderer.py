"""
Renderer for lanibombers.
Main graphics processing and display loop.
"""

import os
import time
import arcade
from typing import Callable, Optional, Tuple, List
from PIL import Image
from renderer.tile_renderer import TileRenderer
from renderer.entity_renderer import EntityRenderer
from renderer.header_renderer import HeaderRenderer
from game_engine.render_state import RenderState
from game_engine.entities.dynamic_entity import DynamicEntity

# ============================================================================
# Configuration
# ============================================================================

SPRITES_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "sprites")

TARGET_FPS = 60
VSYNC = True

SPRITE_SIZE = 10
UI_TOP_MARGIN = 30  # Pixels of free space at top for UI (before zoom)

# Viewport constants
VIEWPORT_WIDTH = 64  # Visible tiles horizontally
VIEWPORT_HEIGHT = 45  # Visible tiles vertically


# ============================================================================
# Renderer
# ============================================================================


class GameRenderer(arcade.Window):
    """Main game window and renderer"""

    # ██╗███╗   ██╗██╗████████╗
    # ██║████╗  ██║██║╚══██╔══╝
    # ██║██╔██╗ ██║██║   ██║
    # ██║██║╚██╗██║██║   ██║
    # ██║██║ ╚████║██║   ██║
    # ╚═╝╚═╝  ╚═══╝╚═╝   ╚═╝

    def __init__(
        self,
        render_state_function: Callable[[], RenderState],
        width: int = 1708,
        height: int = 960,
        client_player_name: str = "",
        show_stats: bool = True,
        show_grid: bool = True,
        window_name: str = "lanibombers"
    ):
        super().__init__(width, height, window_name, vsync=VSYNC)
        self.client_player_name = client_player_name
        self.show_stats = show_stats
        self.render_state_function = render_state_function
        self.show_stats = show_stats
        self.init_width = width
        self.init_height = height
        self.show_grid = show_grid
        self.input_callback = Optional[Callable[[int, int], None]]
        self.input_callback_bound = False

    def initialize(self):
        """
        Function that actually initializes the class.
        This is needed in client-side rendering, as the client does not initially
        have the renderstate, which has to be acquired from the server.
        But now we can open the window to show other stuff in beginning.
        """
        # Enable performance timings early if stats are requested
        if self.show_stats:
            arcade.enable_timings()

        self.set_update_rate(1 / TARGET_FPS)
        self.set_draw_rate(1 / TARGET_FPS)

        self.zoom = min(self.init_width // 640, self.init_height // 480)

        # Create transparent texture for empty transitions
        transparent_image = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        self.transparent_texture = arcade.Texture(transparent_image)

        # Get initial render state for map dimensions
        state = self.render_state_function()
        self.map_width = state.width
        self.map_height = state.height

        # Create sub-renderers
        self.tile_renderer = TileRenderer(
            state, self.transparent_texture, self.zoom, show_grid=self.show_grid
        )
        self.entity_renderer = EntityRenderer(
            state,
            self.transparent_texture,
            self.zoom,
            self.height,
            self.map_height,
            SPRITES_PATH,
        )
        self.header_renderer = HeaderRenderer(
            self.transparent_texture,
            self.zoom,
            self.height,
            self.show_stats,
        )

        # Calculate y offset for UI space at top
        self.ui_offset = UI_TOP_MARGIN * self.zoom

        # Create camera for scrolling (will be positioned in on_update)
        # Camera uses world coordinates where Y=0 is at bottom
        # Viewport limits render area to 64x45 tiles,
        # positioned at bottom-left of window
        self.viewport_pixels_x = VIEWPORT_WIDTH * SPRITE_SIZE * self.zoom
        self.viewport_pixels_y = VIEWPORT_HEIGHT * SPRITE_SIZE * self.zoom
        self.game_camera = arcade.Camera2D(
            viewport=arcade.LBWH(
                0, 0, int(self.viewport_pixels_x), int(self.viewport_pixels_y)
            ),
        )
        # Match projection size to viewport so 1 world pixel = 1 screen pixel
        self.game_camera.projection = arcade.LRBT(
            -self.viewport_pixels_x / 2,
            self.viewport_pixels_x / 2,
            -self.viewport_pixels_y / 2,
            self.viewport_pixels_y / 2,
        )

    def on_update(self, delta_time: float):
        """Poll server and update tilemap"""
        state = self.render_state_function()
        current_time = time.perf_counter()  # Single timestamp for all updates

        # Calculate camera position based on client player
        client_player = self.find_client_player(state.players)
        cam_x, cam_y = self.calculate_camera_position(
            client_player.x if client_player else 0,
            client_player.y if client_player else 0,
            state.width,
            state.height,
        )
        # Set camera to show 64x45 tile viewport centered on player
        self.game_camera.position = (cam_x, cam_y)

        # Calculate visible tile range using viewport dimensions (64x45 tiles)
        tile_size_px = SPRITE_SIZE * self.zoom
        half_view_x = self.viewport_pixels_x / 2
        half_view_y = self.viewport_pixels_y / 2

        # Calculate view bounds in world pixels
        view_left_px = cam_x - half_view_x
        view_right_px = cam_x + half_view_x
        view_bottom_world_y = cam_y - half_view_y
        view_top_world_y = cam_y + half_view_y

        # Convert to tile coordinates (game y=0 at top, world y=0 at bottom)
        # Add buffer of 1 tile on each side for partially visible tiles
        view_start_x = max(0, int(view_left_px / tile_size_px) - 1)
        view_end_x = min(state.width, int(view_right_px / tile_size_px) + 2)

        # World y to game y: game_y = map_height - (world_y / tile_size_px)
        # Top of view (high world y) = low game y (top rows)
        # Bottom of view (low world y) = high game y (bottom rows)
        view_start_y = max(
            0, int(self.map_height - view_top_world_y / tile_size_px) - 1
        )
        view_end_y = min(
            state.height, int(self.map_height - view_bottom_world_y / tile_size_px) + 2
        )

        # Delegate to sub-renderers
        self.tile_renderer.on_update(
            state, view_start_x, view_end_x, view_start_y, view_end_y
        )
        self.entity_renderer.on_update(
            state,
            current_time,
            delta_time,
            view_start_x,
            view_end_x,
            view_start_y,
            view_end_y,
        )
        self.header_renderer.on_update(state.players, self.client_player_name)

    # ██╗  ██╗███████╗██╗     ██████╗ ███████╗██████╗ ███████╗
    # ██║  ██║██╔════╝██║     ██╔══██╗██╔════╝██╔══██╗██╔════╝
    # ███████║█████╗  ██║     ██████╔╝█████╗  ██████╔╝███████╗
    # ██╔══██║██╔══╝  ██║     ██╔═══╝ ██╔══╝  ██╔══██╗╚════██║
    # ██║  ██║███████╗███████╗██║     ███████╗██║  ██║███████║
    # ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝     ╚══════╝╚═╝  ╚═╝╚══════╝

    def find_client_player(
        self, players: List[DynamicEntity]
    ) -> Optional[DynamicEntity]:
        """Find the client's player by name.

        Args:
            players: List of player entities from render state

        Returns:
            The client's player entity, or None if not found
        """
        for player in players:
            if player.name == self.client_player_name:
                return player
        return None

    def calculate_camera_position(
        self, player_x: float, player_y: float, map_width: int, map_height: int
    ) -> Tuple[float, float]:
        """Calculate camera position based on player and map size.

        Args:
            player_x: Player x position in tile coordinates
            player_y: Player y position in tile coordinates
            map_width: Map width in tiles
            map_height: Map height in tiles

        Returns:
            (cam_x, cam_y) in world pixel coordinates
        """
        # Use viewport dimensions (64x45 tiles), not window dimensions
        viewport_pixels_x = VIEWPORT_WIDTH * SPRITE_SIZE * self.zoom
        viewport_pixels_y = VIEWPORT_HEIGHT * SPRITE_SIZE * self.zoom
        half_view_x = viewport_pixels_x / 2
        half_view_y = viewport_pixels_y / 2
        map_pixels_x = map_width * SPRITE_SIZE * self.zoom
        map_pixels_y = map_height * SPRITE_SIZE * self.zoom

        # Small maps: position so map is at top-left of viewport
        if map_pixels_x <= viewport_pixels_x and map_pixels_y <= viewport_pixels_y:
            cam_x = half_view_x
            cam_y = map_pixels_y - half_view_y
            return (cam_x, cam_y)

        # Large maps: center on player (in world pixel coords)
        # Player position in world pixels
        # (Y inverted: row 0 at top in game coords, at bottom in world)
        player_world_x = player_x * SPRITE_SIZE * self.zoom
        player_world_y = (map_height - player_y) * SPRITE_SIZE * self.zoom

        cam_x = player_world_x
        cam_y = player_world_y

        # Clamp camera so we don't see beyond map edges
        cam_x = max(half_view_x, min(cam_x, map_pixels_x - half_view_x))
        cam_y = max(half_view_y, min(cam_y, map_pixels_y - half_view_y))

        return (cam_x, cam_y)

    # ██████╗ ██████╗  █████╗ ██╗    ██╗
    # ██╔══██╗██╔══██╗██╔══██╗██║    ██║
    # ██║  ██║██████╔╝███████║██║ █╗ ██║
    # ██║  ██║██╔══██╗██╔══██║██║███╗██║
    # ██████╔╝██║  ██║██║  ██║╚███╔███╔╝
    # ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝ ╚══╝╚══╝

    def on_draw(self):
        """Render the game"""
        self.clear()

        # Draw game world with camera transformation
        self.game_camera.use()
        self.tile_renderer.background_tile_sprite_list.draw(pixelated=True)  # type: ignore
        self.tile_renderer.vertical_transition_sprite_list.draw(pixelated=True)  # type: ignore
        self.tile_renderer.horizontal_transition_sprite_list.draw(pixelated=True)  # type: ignore
        self.tile_renderer.grid_sprite_list.draw(pixelated=True)  # type: ignore
        self.entity_renderer.pickup_sprite_list.draw(pixelated=True)  # type: ignore
        self.entity_renderer.bomb_sprite_list.draw(pixelated=True)  # type: ignore
        self.entity_renderer.monster_sprite_list.draw(pixelated=True)  # type: ignore
        self.entity_renderer.player_sprite_list.draw(pixelated=True)  # type: ignore
        self.entity_renderer.explosion_sprite_list.draw(pixelated=True)  # type: ignore

        # Draw UI without camera (use default projection)
        self.default_camera.use()
        self.header_renderer.on_draw(self.show_stats)

    # ██╗███╗   ██╗██████╗ ██╗   ██╗████████╗
    # ██║████╗  ██║██╔══██╗██║   ██║╚══██╔══╝
    # ██║██╔██╗ ██║██████╔╝██║   ██║   ██║
    # ██║██║╚██╗██║██╔═══╝ ██║   ██║   ██║
    # ██║██║ ╚████║██║     ╚██████╔╝   ██║
    # ╚═╝╚═╝  ╚═══╝╚═╝      ╚═════╝    ╚═╝

    def bind_input_callback(self, callback: Callable[[int, int], None]) -> None:
        self.input_callback = callback
        self.input_callback_bound = True

    def on_key_press(self, symbol: int, modifiers: int):
        if self.input_callback_bound:
            self.input_callback(symbol, modifiers)

    def on_key_release(self, symbol: int, modifiers: int):
        pass

    # ███╗   ███╗ █████╗ ██╗███╗   ██╗
    # ████╗ ████║██╔══██╗██║████╗  ██║
    # ██╔████╔██║███████║██║██╔██╗ ██║
    # ██║╚██╔╝██║██╔══██║██║██║╚██╗██║
    # ██║ ╚═╝ ██║██║  ██║██║██║ ╚████║
    # ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝

    def run(self):
        arcade.run()
