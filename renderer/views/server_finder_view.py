from __future__ import annotations

import threading
from typing import List, Optional, Tuple

import arcade

from network_stack.shared.factory import get_scanner

# Defaults used when no config is available; can be overridden by the window later.
_DEFAULT_BASE_ADDR = "192.168"
_DEFAULT_SUBNET: Optional[int] = 1
_DEFAULT_PORT = 9999
_DEFAULT_TIMEOUT = 1.5

SELECTED_COLOR = arcade.color.YELLOW
NORMAL_COLOR = arcade.color.WHITE
HINT = "UP/DOWN: navigate  |  ENTER: connect  |  R: rescan  |  ESC: back"


class ServerFinderView(arcade.View):
    """Scans the LAN via UDP broadcast and lets the player pick a server."""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_show_view(self) -> None:
        self.window.background_color = arcade.color.BLACK

        # Reset all state — safe to call again on R/rescan.
        self._servers: List[Tuple[str, int]] = []
        self._selected: int = 0
        self._scanning: bool = False
        self._scan_elapsed: float = 0.0
        self._scan_done: bool = False
        self._connecting: bool = False
        self._pending_player_cfg: Optional[dict] = None
        self._connect_elapsed: float = 0.0
        self._connect_timeout: float = 5.0
        self._name_sent: bool = False

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

        # These writes happen from a non-main thread but are single assignments,
        # which is atomic enough for our display purposes.
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
            # Send Name as soon as the TCP handshake completes.
            if not self._name_sent and client is not None and client.connected:
                cfg = self._pending_player_cfg or {}
                name = cfg.get("player_name") or "Player"
                color_hex = cfg.get("color", "#FFFFFF")
                color_str = color_hex.lstrip("#")
                color = (int(color_str[0:2], 16), int(color_str[2:4], 16), int(color_str[4:6], 16))
                appearance_id = int(cfg.get("appearance_id") or 1)
                client.set_name(name, color, appearance_id)
                self._name_sent = True

            simulation = self.window.client_simulation
            if simulation is not None and simulation.has_state():
                from renderer.game_renderer import GameView
                player_cfg = self._pending_player_cfg or {}
                view = GameView(
                    simulation.get_render_state,
                    client_player_name=player_cfg.get("player_name", ""),
                )
                self._connecting = False
                self.window.show_view(view)
            elif self._connect_elapsed >= self._connect_timeout:
                print("[ServerFinderView] timed out waiting for first game state")
                self._connecting = False

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------

    def on_draw(self) -> None:
        self.clear()
        cx = self.window.width / 2
        cy = self.window.height

        # Title
        arcade.draw_text(
            "SERVER FINDER",
            cx,
            cy * 0.85,
            arcade.color.WHITE,
            font_size=36,
            anchor_x="center",
            anchor_y="center",
            bold=True,
        )

        if self._connecting:
            arcade.draw_text(
                "Connecting to server...",
                cx,
                cy * 0.55,
                arcade.color.LIGHT_GRAY,
                font_size=24,
                anchor_x="center",
                anchor_y="center",
            )
        elif self._scanning:
            arcade.draw_text(
                f"Scanning... {self._scan_elapsed:.1f}s",
                cx,
                cy * 0.55,
                arcade.color.LIGHT_GRAY,
                font_size=24,
                anchor_x="center",
                anchor_y="center",
            )
        elif self._scan_done and not self._servers:
            arcade.draw_text(
                "No servers found.  Press R to rescan or ESC to go back.",
                cx,
                cy * 0.55,
                arcade.color.LIGHT_GRAY,
                font_size=22,
                anchor_x="center",
                anchor_y="center",
            )
        else:
            for i, (ip, port) in enumerate(self._servers):
                color = SELECTED_COLOR if i == self._selected else NORMAL_COLOR
                prefix = "> " if i == self._selected else "  "
                arcade.draw_text(
                    f"{prefix}{ip}:{port}",
                    cx,
                    cy * 0.6 - i * 48,
                    color,
                    font_size=26,
                    anchor_x="center",
                    anchor_y="center",
                )

        # Hint bar
        arcade.draw_text(
            HINT,
            cx,
            40,
            arcade.color.LIGHT_GRAY,
            font_size=16,
            anchor_x="center",
            anchor_y="center",
        )

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

        self._pending_player_cfg = player_cfg
        self._connect_elapsed = 0.0
        self._name_sent = False
        self._connecting = True
