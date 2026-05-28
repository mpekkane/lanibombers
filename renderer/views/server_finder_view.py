from __future__ import annotations

import os
import threading
from typing import List, Tuple

import arcade

from network_stack.shared.factory import get_scanner
from renderer.bitmap_text import BitmapText
from common.logger import get_logger
from network_stack.messages.messages import ClientConnectionState
from common.keymapper import key_to_char

# Defaults used when no config is available; can be overridden by the window later.
_DEFAULT_BASE_ADDR = "192.168"
_DEFAULT_SUBNET: int | None = 1
_DEFAULT_PORT = 9999
_DEFAULT_TIMEOUT = 1.5

SPRITES_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "sprites")
GRAPHICS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "assets", "graphics"
)

# Design coordinates (top-left origin, 640x480 base resolution)
SERVER_LIST_X = 217
SERVER_LIST_Y = 102
LINE_HEIGHT = 10  # 8px char + 2px gap


class ServerFinderView(arcade.View):
    """Scans the LAN via UDP broadcast and lets the player pick a server."""

    def __init__(
        self,
        window: arcade.Window | None = None,
        background_color: (
            Tuple[int, int, int] | Tuple[int, int, int, int] | None
        ) = None,
    ) -> None:
        super().__init__(window, background_color)
        self.log = get_logger()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_show_view(self) -> None:
        self.window.background_color = arcade.color.BLACK

        self._servers: List[Tuple[str, int]] = []
        self._selected: int = 0
        self._scanning: bool = False
        self._scan_elapsed: float = 0.0
        self._scan_done: bool = False
        self._connecting: bool = False
        self._connected: bool = False
        self._connect_elapsed: float = 0.0
        self._connect_timeout: float = 20.0
        self._name_sent: bool = False

        # Rendering resources
        self.zoom = min(self.window.width // 640, self.window.height // 480)

        # Background image
        bg_path = os.path.join(GRAPHICS_PATH, "SERVERFINDER.png")
        bg_texture = arcade.load_texture(bg_path)
        bg_sprite = arcade.Sprite()
        bg_sprite.texture = bg_texture
        bg_sprite.scale = self.zoom
        bg_sprite.center_x = (640 / 2) * self.zoom
        bg_sprite.center_y = self.window.height - (480 / 2) * self.zoom
        self.bg_sprite_list = arcade.SpriteList()
        self.bg_sprite_list.append(bg_sprite)

        # Bitmap text
        font_path = os.path.join(SPRITES_PATH, "font.png")
        self.bitmap_text = BitmapText(font_path, zoom=self.zoom)

        self.server_list_sprites = arcade.SpriteList()
        self._cached_server_key = None
        self.writing = False
        self.text_msg = ""
        self.chat_sprites = arcade.SpriteList()
        self.max_chat_line_len = 40
        self._start_scan()

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------

    def _start_scan(self) -> None:
        self._servers = []
        self._selected = 0
        self._scanning = True
        self._scan_elapsed = 0.0
        self._scan_done = False
        self._cached_server_key = None

        t = threading.Thread(target=self._run_scan, daemon=True)
        t.start()

    def _run_scan(self) -> None:
        """Runs in a background daemon thread; writes results back to main attrs."""
        try:
            from common.config_reader import ConfigReader

            cfg = ConfigReader("cfg/client_config.yaml").config or {}
            protocol = cfg.get("protocol", "tcp")
            base_addr = cfg.get("base_addr", _DEFAULT_BASE_ADDR)
            subnet = cfg.get("subnet", _DEFAULT_SUBNET)
            port = int(cfg.get("port", _DEFAULT_PORT))
            host = cfg.get("host", None)
            timeout_s = float(cfg.get("timeout", _DEFAULT_TIMEOUT))
            scanner = get_scanner(protocol, base_addr, subnet, port, host, timeout_s)
            results: List[Tuple[str, int]] = scanner.scan()
        except Exception as exc:
            self.log.error(f"[ServerFinderView] scan error: {exc}")
            results = []

        self._servers = results
        self._scanning = False
        self._scan_done = True

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def on_update(self, delta_time: float) -> None:
        # graceful disconnect handling
        if self.window.connection_state == ClientConnectionState.DISCONNECTED:
            self.window.connection_state = ClientConnectionState.NONE
            self._connected = False
            self.chat_sprites = arcade.SpriteList()
            if not self._scanning:
                self._start_scan()

        if self._connected:
            if self.window.shop is not None:
                self.window.view_complete()

        if self._scanning:
            self._scan_elapsed += delta_time

        if self._connecting:
            self._connect_elapsed += delta_time
            client = self.window.network_client
            if not self._name_sent and client is not None and client.connected:
                client.set_name(
                    self.window.name or "Player",
                    self.window.color,
                    self.window.appearance_id,
                )
                self._name_sent = True

            # simulation = self.window.client_simulation
            # if simulation is not None and simulation.has_state():
            #     self.window.view_complete()
            if self.window.connection_state == ClientConnectionState.CONNECTED:
                self._connected = True
                self._connecting = False
            elif self._connect_elapsed >= self._connect_timeout:
                self.log.warning(
                    "[ServerFinderView] timed out waiting for first game state"
                )
                self._connecting = False

        self._rebuild_server_list()

        if self.window.auto and not self._connected:
            if self._servers:
                if not self._connecting:
                    self._connect(self._servers[self._selected])
            else:
                if not self._scanning:
                    self._start_scan()

        if self._connected:
            chat_x = SERVER_LIST_X + 320 * self.zoom
            chat_y = self.window.height - SERVER_LIST_Y * self.zoom
            chat_line_h = LINE_HEIGHT * self.zoom
            sprites = arcade.SpriteList()
            msg_color = (0x8B, 0x8B, 0x8B)
            line = self.bitmap_text.create_text_sprites(
                "Chat: (y to type, ENTER to send)",
                chat_x,
                chat_y,
                color=(0xFF, 0xFF, 0xFF),
            )
            for s in line:
                sprites.append(s)
            if self.writing:
                line = self.bitmap_text.create_text_sprites(
                    f" > {self.text_msg}",
                    chat_x,
                    chat_y - chat_line_h,
                    color=(0xFF, 0xFF, 0x00),
                )
                for s in line:
                    sprites.append(s)
            log = self.window.chat_log
            N = 27
            show_log = log if len(log) <= N else log[len(log) - N:len(log)]
            for i, message in enumerate(show_log):
                line = self.bitmap_text.create_text_sprites(
                    message,
                    chat_x,
                    chat_y - (i + 2) * chat_line_h,
                    color=msg_color,
                )
                for s in line:
                    sprites.append(s)
            self.chat_sprites = sprites

    def _rebuild_server_list(self) -> None:
        """Rebuild server list sprites only when state changes."""
        if self._connecting:
            key = ("connecting",)
        elif self._connected:
            key = ("connected",)
        elif self._scanning:
            key = ("scanning", round(self._scan_elapsed, 1))
        elif self._scan_done and not self._servers:
            key = ("no_servers",)
        else:
            key = ("servers", tuple(self._servers), self._selected)

        if key == self._cached_server_key:
            return
        self._cached_server_key = key

        base_x = SERVER_LIST_X * self.zoom
        base_y = self.window.height - SERVER_LIST_Y * self.zoom
        line_h = LINE_HEIGHT * self.zoom

        if self._connecting:
            self.server_list_sprites = self.bitmap_text.create_text_sprites(
                "Connecting...", base_x, base_y
            )
        elif self._connected:
            self.server_list_sprites = self.bitmap_text.create_text_sprites(
                "Connected", base_x, base_y
            )
        elif self._scanning:
            self.server_list_sprites = self.bitmap_text.create_text_sprites(
                f"Scanning... {self._scan_elapsed:.1f}s", base_x, base_y
            )
        elif self._scan_done and not self._servers:
            self.server_list_sprites = self.bitmap_text.create_text_sprites(
                "No servers found", base_x, base_y, color=(0x67, 0x67, 0x67)
            )
        else:
            sprites = arcade.SpriteList()
            for i, (ip, port) in enumerate(self._servers):
                prefix = "> " if i == self._selected else "  "
                color = (
                    (0x8B, 0x8B, 0x8B) if i == self._selected else (0x67, 0x67, 0x67)
                )
                line = self.bitmap_text.create_text_sprites(
                    f"{prefix}{ip}:{port}",
                    base_x,
                    base_y - i * line_h,
                    color=color,
                )
                for s in line:
                    sprites.append(s)
            self.server_list_sprites = sprites

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------

    def on_draw(self) -> None:
        self.clear()
        self.window.default_camera.use()
        self.bg_sprite_list.draw(pixelated=True)
        self.server_list_sprites.draw(pixelated=True)
        self.chat_sprites.draw(pixelated=True)

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        if self._connected and not self.writing and symbol == arcade.key.Y:
            self.writing = True
            self.text_msg = ""
        elif self._connected and self.writing:
            if symbol == arcade.key.ESCAPE:
                self.writing = False
            elif symbol == arcade.key.ENTER:
                self.writing = False
                self.window.send_chat(self.text_msg)
            elif symbol == arcade.key.BACKSPACE:
                if self.text_msg:
                    self.text_msg = self.text_msg[:-1]
                    self.player_name = self.text_msg
            else:
                char = key_to_char(symbol, modifiers, is_text=True)
                if char and len(self.text_msg) < self.max_chat_line_len:
                    self.text_msg += char
                    self.player_name = self.text_msg
            return
        else:
            if symbol == arcade.key.ESCAPE:
                from renderer.views.main_menu_view import MainMenuView

                self.window.show_view(MainMenuView())
            elif symbol == arcade.key.R:
                self._start_scan()
            elif symbol == arcade.key.UP:
                if self._servers:
                    self._selected = (self._selected - 1) % len(self._servers)
            elif symbol == arcade.key.DOWN:
                if self._servers:
                    self._selected = (self._selected + 1) % len(self._servers)
            elif symbol in (arcade.key.RETURN, arcade.key.ENTER):
                if self._servers and not self._connected:
                    self._connect(self._servers[self._selected])

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def _connect(self, server: Tuple[str, int]) -> None:
        from common.config_reader import ConfigReader

        self.log.info(f"[ServerFinderView] connecting to {server[0]}:{server[1]}")

        player_cfg = ConfigReader("cfg/player.yaml").config
        self.window.connect(server[0], server[1], player_cfg)

        self._connect_elapsed = 0.0
        self._name_sent = False
        self._connecting = True
