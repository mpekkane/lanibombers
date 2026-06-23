"""
Renderer for lanibombers.
Main graphics processing and display loop.
"""

import os
import random
import time
import arcade
import numpy as np
from typing import Callable, Dict, Optional, Tuple, List
from PIL import Image
from renderer.tile_renderer import TileRenderer
from renderer.entity_renderer import EntityRenderer
from renderer.header_renderer import HeaderRenderer
from renderer.margin_renderer import MarginRenderer
from renderer.bitmap_text import BitmapText
from game_engine.render_state import RenderState, ExplosionVisual
from game_engine.entities.dynamic_entity import DynamicEntity
from game_engine.entities.player import Player
from common.bomb_dictionary import BombType
from game_engine.clock import Clock
from game_engine.state_machine import ClientStateAction
from network_stack.messages.messages import ClientConnectionState

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

# Big overlay text (countdown / round end). Bitmap font is 8x8 base,
# zoom 12 matches the visual weight of the previous arcade font_size=100.
COOL_TEXT_ZOOM = 12


# ============================================================================
# Renderer
# ============================================================================


class GameView(arcade.View):
    """Main game view and renderer"""

    # ██╗███╗   ██╗██╗████████╗
    # ██║████╗  ██║██║╚══██╔══╝
    # ██║██╔██╗ ██║██║   ██║
    # ██║██║╚██╗██║██║   ██║
    # ██║██║ ╚████║██║   ██║
    # ╚═╝╚═╝  ╚═══╝╚═╝   ╚═╝

    def __init__(
        self,
        render_state_function: Callable[[], RenderState],
        client_player_name: str = "",
        show_stats: bool = False,
        show_grid: bool = True,
        item_hotkeys: Optional[Dict[BombType, str]] = None,
    ):
        super().__init__()
        self.client_player_name = client_player_name
        self.item_hotkeys = item_hotkeys or {}
        self.show_stats = show_stats
        self.render_state_function = render_state_function
        self.show_stats = show_stats
        self.show_grid = show_grid
        self.input_callback: Optional[Callable[[int, int], None]] = None
        self.input_callback_bound = False
        self.start_time = Clock.now()
        self.closing = False
        self.elapsed_since_closing = 0.0
        self.CLOSE_TIMEOUT = 5.0

    def on_show_view(self):
        self.initialize()

    def initialize(self):
        """
        Function that actually initializes the class.
        This is needed in client-side rendering, as the client does not initially
        have the renderstate, which has to be acquired from the server.
        But now we can open the window to show other stuff in beginning.
        """
        # Enable performance timings early if stats are requested
        if self.show_stats and not arcade.timings_enabled():
            arcade.enable_timings()

        self.window.set_update_rate(1 / TARGET_FPS)
        self.window.set_draw_rate(1 / TARGET_FPS)

        self.zoom = min(self.window.width // 640, self.window.height // 480)

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
            self.window.height,
            self.map_height,
            SPRITES_PATH,
        )
        self.header_renderer = HeaderRenderer(
            self.transparent_texture,
            self.zoom,
            self.window.height,
            self.show_stats,
            self.item_hotkeys,
        )
        self.margin_renderer = MarginRenderer(
            self.zoom, self.window.height, self.client_player_name
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

        # UI camera (Camera2D so we can offset its position for shake)
        self.ui_camera = arcade.Camera2D(
            viewport=arcade.LBWH(0, 0, self.window.width, self.window.height),
            position=(self.window.width / 2, self.window.height / 2),
        )

        # Nuke screen shake & white flash state
        self.NUKE_SHAKE_DURATION = 2.0  # seconds
        self.NUKE_FLASH_DURATION = 1.0  # seconds
        self.NUKE_SHAKE_MAX_AMP = 50 * self.zoom  # screen pixels (5 tiles)
        self._nuke_start_time = 0.0
        self._cam_position = (0.0, 0.0)

        # Bitmap text for large overlay text (countdown, round-end banner)
        self.cool_text = BitmapText(
            os.path.join(SPRITES_PATH, "font.png"),
            zoom=COOL_TEXT_ZOOM,
        )

        # White flash overlay sprite (1x1 white pixel scaled to cover viewport + shake margin)
        white_image = Image.new("RGBA", (1, 1), (255, 255, 255, 255))
        white_texture = arcade.Texture(white_image, name="nuke_flash_white")
        self._flash_sprite = arcade.Sprite()
        self._flash_sprite.texture = white_texture
        # Scale to cover viewport plus shake margin on each side
        flash_margin = self.NUKE_SHAKE_MAX_AMP * 2
        self._flash_sprite.width = self.viewport_pixels_x + flash_margin
        self._flash_sprite.height = self.viewport_pixels_y + flash_margin
        self._flash_sprite.visible = False
        self._flash_sprite_list = arcade.SpriteList()
        self._flash_sprite_list.append(self._flash_sprite)

    def on_update(self, delta_time: float):
        """Poll server and update tilemap"""
        if self.window.connection_state == ClientConnectionState.DISCONNECTED:
            self.window.connection_state = ClientConnectionState.NONE
            self.window.view_complete(ClientStateAction.RESTART)
            return

        state = self.render_state_function()
        if not state.running:
            if not self.closing:
                self.closing = True
            else:
                self.elapsed_since_closing += delta_time
                if self.elapsed_since_closing > self.CLOSE_TIMEOUT:
                    self.window.view_complete()

        current_time = time.perf_counter()  # Single timestamp for all updates

        # Calculate camera position based on client player
        client_player = self.find_client_player(state.players)
        cam_x, cam_y = self.calculate_camera_position(
            client_player.x if client_player else 0,
            client_player.y if client_player else 0,
            state.width,
            state.height,
        )

        # Store base camera position before shake is applied
        self._cam_position = (cam_x, cam_y)

        # Detect nuke explosions and latch start time
        if np.any(state.explosions == ExplosionVisual.NUKE):
            self._nuke_start_time = current_time

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
        self.margin_renderer.on_update(state.players, state.round_time_left)

    # ██╗  ██╗███████╗██╗     ██████╗ ███████╗██████╗ ███████╗
    # ██║  ██║██╔════╝██║     ██╔══██╗██╔════╝██╔══██╗██╔════╝
    # ███████║█████╗  ██║     ██████╔╝█████╗  ██████╔╝███████╗
    # ██╔══██║██╔══╝  ██║     ██╔═══╝ ██╔══╝  ██╔══██╗╚════██║
    # ██║  ██║███████╗███████╗██║     ███████╗██║  ██║███████║
    # ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝     ╚══════╝╚═╝  ╚═╝╚══════╝

    def find_client_player(self, players: List[Player]) -> Optional[Player]:
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

        # Compute nuke shake offset
        elapsed = time.perf_counter() - self._nuke_start_time
        shaking = elapsed < self.NUKE_SHAKE_DURATION
        if shaking:
            amp = self.NUKE_SHAKE_MAX_AMP * (1.0 - elapsed / self.NUKE_SHAKE_DURATION)
            shake_x = random.uniform(-amp, amp)
            shake_y = random.uniform(-amp, amp)
        else:
            shake_x = 0.0
            shake_y = 0.0

        # Draw game world with camera transformation (+ shake)
        cam_x, cam_y = self._cam_position
        self.game_camera.position = (cam_x + shake_x, cam_y + shake_y)
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

        # Draw white flash overlay (in game camera space, fades over 1 second)
        if elapsed < self.NUKE_FLASH_DURATION:
            alpha = int(255 * (1.0 - elapsed / self.NUKE_FLASH_DURATION))
            self._flash_sprite.alpha = alpha
            self._flash_sprite.position = (cam_x + shake_x, cam_y + shake_y)
            self._flash_sprite.visible = True
            self._flash_sprite_list.draw()
        else:
            self._flash_sprite.visible = False

        # Draw UI with shake (header without perf graphs, margin)
        center_x = self.window.width / 2
        center_y = self.window.height / 2
        self.ui_camera.position = (center_x + shake_x, center_y + shake_y)
        self.ui_camera.use()
        self.header_renderer.on_draw(show_stats=not shaking and self.show_stats)
        self.margin_renderer.on_draw()

        # Draw perf graphs without shake (stationary)
        if shaking and self.show_stats:
            self.ui_camera.position = (center_x, center_y)
            self.ui_camera.use()
            self.header_renderer.draw_perf_graphs()

        # initial position indicator
        elapsed = Clock.now() - self.start_time
        notify_len = 10
        if elapsed < notify_len:
            self.draw_player_position_indicator(notify_len)

        # round countdown
        if self.window.countdown is not None and self.window.countdown > 0:
            self.draw_countdown()

        # round end
        if self.closing:
            self.draw_end()

    def draw_player_position_indicator(self, notify_len: int):
        elapsed = Clock.now() - self.start_time
        state = self.render_state_function()
        client_player = self.find_client_player(state.players)

        ratio = elapsed / notify_len
        remaining = notify_len - elapsed
        alpha = int(255 * (1 - ratio))
        col = [
            client_player.color[0],
            client_player.color[1],
            client_player.color[2],
            alpha,
        ]

        if elapsed < notify_len / 2:
            radius = remaining**2
        else:
            radius = 25 + 5 * np.sin(5 * elapsed)

        arcade.draw_circle_outline(
            center_x=(client_player.x) * 20,
            center_y=(VIEWPORT_HEIGHT - client_player.y) * 20,
            radius=radius,
            color=col,
            border_width=remaining,
        )

    def draw_countdown(self):
        state = self.render_state_function()
        countdown = self.window.countdown
        text = str(int(countdown))

        color = GameView.countdown_color(countdown)

        self.cool_draw(text, color)

    def draw_end(self):
        self.cool_draw("Round end", arcade.color.WHITE)

    def cool_draw(self, text: str, color) -> None:
        cx = VIEWPORT_WIDTH / 2 * 20
        cy = VIEWPORT_HEIGHT / 2 * 20
        # BitmapText draws from top-left; convert center coords to top-left.
        text_w = self.cool_text.get_text_width(text)
        text_h = self.cool_text.get_text_height()
        x = cx - text_w / 2
        y = cy + text_h / 2

        black = (0, 0, 0, 255)
        white = (255, 255, 255, 255)

        # Shadow
        self.cool_text.draw_text(text, x + 5, y - 5, black)

        # Outline
        for dx, dy in [(-3, 0), (3, 0), (0, -3), (0, 3)]:
            self.cool_text.draw_text(text, x + dx, y + dy, white)

        # Main text
        self.cool_text.draw_text(text, x, y, color)

    @staticmethod
    def countdown_color(countdown: float) -> tuple[int, int, int]:
        if countdown > 3:
            return arcade.color.WHITE

        t = max(0.0, min(1.0, (3.0 - countdown) / 2.0))

        r = 255
        g = int(60 * (1.0 - t))
        b = int(40 * (1.0 - t))

        return (r, g, b)

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
        if self.input_callback is not None:
            self.input_callback(symbol, modifiers)

    def on_key_release(self, symbol: int, modifiers: int):
        pass
