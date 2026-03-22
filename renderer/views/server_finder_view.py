from __future__ import annotations

import os
import threading
from typing import List, Tuple

import arcade

from network_stack.shared.factory import get_scanner
from renderer.bitmap_text import BitmapText

# Defaults used when no config is available; can be overridden by the window later.
_DEFAULT_BASE_ADDR = "192.168"
_DEFAULT_SUBNET: int | None = 1
_DEFAULT_PORT = 9999
_DEFAULT_TIMEOUT = 1.5

SPRITES_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "sprites")
GRAPHICS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "graphics")

# Design coordinates (top-left origin, 640x480 base resolution)
SERVER_LIST_X = 217
SERVER_LIST_Y = 102
LINE_HEIGHT = 10  # 8px char + 2px gap


class ServerFinderView(arcade.View):
    """Scans the LAN via UDP broadcast and lets the player pick a server."""

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
        self._connect_elapsed: float = 0.0
        self._connect_timeout: float = 5.0
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
            print(f"[ServerFinderView] scan error: {exc}")
            results = []

        self._servers = results
        self._scanning = False
        self._scan_done = True

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def on_update(self, delta_time: float) -> None:
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

            simulation = self.window.client_simulation
            if simulation is not None and simulation.has_state():
                self.window.view_complete()
            elif self._connect_elapsed >= self._connect_timeout:
                print("[ServerFinderView] timed out waiting for first game state")
                self._connecting = False

        self._rebuild_server_list()

    def _rebuild_server_list(self) -> None:
        """Rebuild server list sprites only when state changes."""
        if self._connecting:
            key = ("connecting",)
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
                color = (0x8B, 0x8B, 0x8B) if i == self._selected else (0x67, 0x67, 0x67)
                line = self.bitmap_text.create_text_sprites(
                    f"{prefix}{ip}:{port}",
                    base_x, base_y - i * line_h,
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

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def on_key_press(self, key: int, _modifiers: int) -> None:
        if key == arcade.key.ESCAPE:
            from renderer.views.main_menu_view import MainMenuView
            self.window.show_view(MainMenuView())
        elif key == arcade.key.R:
            self._start_scan()
        elif key == arcade.key.UP:
            if self._servers:
                self._selected = (self._selected - 1) % len(self._servers)
        elif key == arcade.key.DOWN:
            if self._servers:
                self._selected = (self._selected + 1) % len(self._servers)
        elif key in (arcade.key.RETURN, arcade.key.ENTER):
            if self._servers:
                self._connect(self._servers[self._selected])

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def _connect(self, server: Tuple[str, int]) -> None:
        from common.config_reader import ConfigReader

        print(f"[ServerFinderView] connecting to {server[0]}:{server[1]}")

        player_cfg = ConfigReader("cfg/player.yaml").config
        self.window.connect(server[0], server[1], player_cfg)

        self._connect_elapsed = 0.0
        self._name_sent = False
        self._connecting = True
