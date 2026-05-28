from __future__ import annotations

from server_engine.server_base import BomberServerBase

import sys
import select
from pathlib import Path
from typing import Optional

from game_engine.clock import Clock


class ConsoleBomberServer(BomberServerBase):
    """
    Simple terminal UI using print/select.

    This class only handles presentation and admin input.
    Game/shop/lobby logic stays in BomberServerBase.

    Controls:
        STOPPED:
            s / y / Enter : start server
            q             : quit app

        LOBBY:
            s / y / Enter : start game, if players exist
            q             : stop server

        SHOP/GAME/END:
            q             : stop server
    """

    def __init__(
        self,
        cfg: str,
        session_setup: str,
        headless: bool,
        map_path: Optional[str],
        log_path: str = "logs/server.log",
    ) -> None:
        self.log_path = Path(log_path)

        self._quit_requested = False
        self._start_requested = False
        self._stop_server_requested = False

        self._last_draw_time = 0.0
        self._last_state_name = ""
        self._draw_interval = 1.0

        super().__init__(
            cfg,
            session_setup,
            headless,
            map_path,
            log=print,
        )

    ##################
    # UI lifecycle hooks
    ##################

    def ui_start(self) -> None:
        print("")
        print("LANIBOMBERS SERVER")
        print("=" * 40)
        print("Console controls:")
        print("  stopped : s/enter = start server, q = quit")
        print("  running : q = stop server")
        print("  lobby   : s/enter = start game")
        print("")

    def ui_stop(self) -> None:
        print("")
        print("Server UI closed.")

    def ui_tick(self) -> None:
        self._handle_input()
        self._draw_status_if_needed()

    def ui_should_quit(self) -> bool:
        return self._quit_requested

    def ui_start_requested(self) -> bool:
        if not self._start_requested:
            return False

        self._start_requested = False
        return True

    def ui_stop_server_requested(self) -> bool:
        if not self._stop_server_requested:
            return False

        self._stop_server_requested = False
        return True

    def ui_show_scores(self) -> None:
        print("")
        print("Scoreboard")
        print("=" * 20)

        for name, score in self.get_scoreboard_rows():
            print(f"{name} - {score}")

        print("")

    def ui_show_end_message(self) -> None:
        print("")
        print("Game has ended.")
        print("")

    ##################
    # input
    ##################

    def _read_line_nonblocking(self) -> str | None:
        try:
            ready, _, _ = select.select([sys.stdin], [], [], 0.0)
        except (OSError, ValueError):
            return None

        if not ready:
            return None

        line = sys.stdin.readline()
        if line == "":
            return None

        return line.strip()

    def _handle_input(self) -> None:
        line = self._read_line_nonblocking()
        if line is None:
            return

        state = self.state_machine.get_state()
        command = line.lower()

        if command in ("q", "quit", "exit"):
            if state.name == "STOPPED":
                self._quit_requested = True
            else:
                self._stop_server_requested = True
            return

        if command in ("", "s", "start", "y", "yes"):
            if state.name in ("STOPPED", "LOBBY"):
                self._start_requested = True

    ##################
    # drawing
    ##################

    def _draw_status_if_needed(self) -> None:
        now = Clock.now()
        state = self.state_machine.get_state()
        state_name = state.name

        if (
            state_name == self._last_state_name
            and now - self._last_draw_time < self._draw_interval
        ):
            return

        self._last_state_name = state_name
        self._last_draw_time = now

        self._draw_status()

    def _draw_status(self) -> None:
        state = self.state_machine.get_state()

        print("")
        print("-" * 40)
        print(f"State       : {state.name}")
        print(f"Players     : {len(self.players)}")
        print(f"Rounds left : {self.rounds_left}")

        if self.average_ping >= 0:
            print(f"Avg ping    : {self.average_ping / 1e6:.2f} ms")
        else:
            print("Avg ping    : -")

        if self.players:
            print("")
            print("Players")
            print("-" * 20)
            for i, player in enumerate(self.players):
                print(
                    f"{i + 1:>2}. "
                    f"{player.name:<18} "
                    f"score={player.score:<4} "
                    f"money={player.money:<4}"
                )

        print("")
        print(self._command_hint())

    def _command_hint(self) -> str:
        state = self.state_machine.get_state()

        if state.name == "STOPPED":
            return "Command: [s/enter] start server, [q] quit"

        if state.name == "LOBBY":
            if len(self.players) > 0:
                return "Command: [s/enter] start game, [q] stop server"
            return "Waiting for players... command: [q] stop server"

        if state.name == "SHOP":
            return "Shop running... command: [q] stop server"

        if state.name == "GAME":
            return "Game running... command: [q] stop server"

        if state.name == "END":
            return "Session ending... command: [q] stop server"

        return "Command: [q] quit"

    ##################
    # legacy aliases
    ##################

    def show_scores(self) -> None:
        self.ui_show_scores()

    def show_end_message(self) -> None:
        self.ui_show_end_message()

    def show_ping_stats(self, avg_s: float) -> None:
        print(f"average (ns): {self.average_ping} ns")
        print(f"average (s) : {avg_s} s")
        print(f"over pings  : {self.ping_count}")
        print(f"   & pongs  : {self.pong_count}")
