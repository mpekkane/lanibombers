from __future__ import annotations

from server_engine.server_base import BomberServerBase

import curses
import textwrap
from pathlib import Path
from typing import Any, Optional


class CursesBomberServer(BomberServerBase):
    """
    ncurses UI.

    This class should only handle presentation and admin input.
    Game/shop/lobby logic should stay in BomberServerBase.

    Layout:
        - Top/main: server status + players
        - Bottom: wrapped tail of actual log file
        - Footer: colored command row
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

        self.stdscr: Optional[Any] = None
        self._quit_requested = False
        self._start_requested = False

        # No curses printout buffer. UI-visible text comes from the actual log file.
        # If BomberServerBase still expects a text callback, swallow it here.
        super().__init__(
            cfg,
            session_setup,
            headless,
            map_path,
            log=lambda _text: None,
        )

        self.debug_prints = False

    ##################
    # UI lifecycle hooks
    ##################

    def ui_start(self) -> None:
        self.stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)

        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()

            curses.init_pair(1, curses.COLOR_CYAN, -1)  # titles
            curses.init_pair(2, curses.COLOR_YELLOW, -1)  # commands
            curses.init_pair(3, curses.COLOR_GREEN, -1)  # status/good
            curses.init_pair(4, curses.COLOR_RED, -1)  # quit/danger

        assert self.stdscr is not None
        self.stdscr.keypad(True)
        self.stdscr.nodelay(True)
        self.stdscr.timeout(100)

    def ui_stop(self) -> None:
        if self.stdscr is None:
            return

        try:
            self.stdscr.keypad(False)
            curses.nocbreak()
            curses.echo()
            curses.endwin()
        finally:
            self.stdscr = None

    def ui_tick(self) -> None:
        self._handle_keys()
        self._draw_screen()

    def ui_should_quit(self) -> bool:
        return self._quit_requested

    def ui_start_requested(self) -> bool:
        if not self._start_requested:
            return False

        self._start_requested = False
        return True

    def ui_show_scores(self) -> None:
        return

    def ui_show_end_message(self) -> None:
        return

    ##################
    # log file reader
    ##################

    def _read_log_tail(self, max_lines: int) -> list[str]:
        if max_lines <= 0:
            return []

        if not self.log_path.exists():
            return [f"No log file: {self.log_path}"]

        try:
            with self.log_path.open("r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError as exc:
            return [f"Could not read log file: {exc}"]

        return [line.rstrip("\n") for line in lines[-max_lines:]]

    ##################
    # input
    ##################

    def _handle_keys(self) -> None:
        if self.stdscr is None:
            return

        while True:
            key = self.stdscr.getch()

            if key == -1:
                break

            if key in (ord("q"), ord("Q")):
                self._quit_requested = True
                return

            if key in (ord("s"), ord("S"), ord("y"), ord("Y"), 10, 13):
                self._start_requested = True

    ##################
    # drawing helpers
    ##################

    def _safe_addstr(self, stdscr: Any, y: int, x: int, text: str) -> None:
        try:
            height, width = stdscr.getmaxyx()

            if y < 0 or y >= height:
                return

            if x < 0 or x >= width:
                return

            stdscr.addstr(y, x, text[: max(0, width - x - 1)])

        except curses.error:
            pass

    def _safe_addstr_attr(
        self,
        stdscr: Any,
        y: int,
        x: int,
        text: str,
        attr: int,
    ) -> None:
        try:
            height, width = stdscr.getmaxyx()

            if y < 0 or y >= height:
                return

            if x < 0 or x >= width:
                return

            stdscr.addstr(y, x, text[: max(0, width - x - 1)], attr)

        except curses.error:
            pass

    def _color(self, pair: int) -> int:
        if curses.has_colors():
            return curses.color_pair(pair)
        return curses.A_NORMAL

    ##################
    # drawing
    ##################

    def _draw_screen(self) -> None:
        if self.stdscr is None:
            return

        stdscr = self.stdscr
        stdscr.erase()

        state = self.state_machine.get_state()
        height, width = stdscr.getmaxyx()

        if height < 12 or width < 40:
            self._safe_addstr(stdscr, 0, 0, "Terminal too small")
            stdscr.refresh()
            return

        status_y = 3
        players_y = 10

        # Footer layout:
        #   blank spacer row
        #   separator row
        #   command row
        #   possible terminal bottom safety
        footer_height = 4

        # Max 16 players + title/separator = 18 rows.
        # But avoid letting players push logs too far down on smaller terminals.
        max_players_section_height = 18
        desired_top_end = players_y + max_players_section_height
        max_top_end = max(players_y + 4, height // 2)
        top_end = min(desired_top_end, max_top_end)

        # One empty row between players and log.
        log_y = min(top_end + 1, height - footer_height - 6)
        log_y = max(players_y + 4, log_y)

        log_height = max(4, height - log_y - footer_height)

        title_attr = self._color(1) | curses.A_BOLD
        self._safe_addstr_attr(
            stdscr,
            0,
            0,
            "LANIBOMBERS SERVER",
            title_attr,
        )
        self._safe_addstr(stdscr, 1, 0, "=" * min(60, max(0, width - 1)))

        state_attr = self._color(3) | curses.A_BOLD
        self._safe_addstr(stdscr, status_y, 0, "State          : ")
        self._safe_addstr_attr(stdscr, status_y, 17, state.name, state_attr)

        self._safe_addstr(
            stdscr, status_y + 1, 0, f"Players        : {len(self.players)}"
        )
        self._safe_addstr(
            stdscr, status_y + 2, 0, f"Rounds left    : {self.rounds_left}"
        )
        self._safe_addstr(
            stdscr, status_y + 3, 0, f"Ping count     : {self.ping_count}"
        )
        self._safe_addstr(
            stdscr, status_y + 4, 0, f"Pong count     : {self.pong_count}"
        )

        if self.average_ping >= 0:
            avg_ms = self.average_ping / 1e6
            self._safe_addstr(
                stdscr, status_y + 5, 0, f"Average ping   : {avg_ms:.2f} ms"
            )
        else:
            self._safe_addstr(stdscr, status_y + 5, 0, "Average ping   : -")

        self._draw_players(
            stdscr=stdscr,
            y=players_y,
            x=0,
            max_y=log_y - 2,
            width=width - 1,
        )

        self._draw_log_file(
            stdscr=stdscr,
            y=log_y,
            x=0,
            height=log_height,
            width=width - 1,
        )

        self._draw_footer(stdscr, height, width)

        stdscr.refresh()

    def _draw_players(
        self,
        stdscr: Any,
        y: int,
        x: int,
        max_y: int,
        width: int,
    ) -> None:
        title_attr = self._color(1) | curses.A_BOLD

        self._safe_addstr_attr(stdscr, y, x, "Players", title_attr)
        self._safe_addstr(stdscr, y + 1, x, "-" * min(60, max(0, width - 1)))

        first_row = y + 2

        if first_row > max_y:
            return

        if not self.players:
            self._safe_addstr(stdscr, first_row, x, "No players connected")
            return

        max_player_rows = max(0, max_y - first_row + 1)
        max_player_rows = min(max_player_rows, 16)

        for i, player in enumerate(self.players[:max_player_rows]):
            line = (
                f"{i + 1:>2}. "
                f"{player.name:<18} "
                f"score={player.score:<4} "
                f"money={player.money:<4}"
            )
            self._safe_addstr(stdscr, first_row + i, x, line)

        if len(self.players) > max_player_rows and max_player_rows > 0:
            self._safe_addstr(
                stdscr,
                first_row + max_player_rows - 1,
                x,
                f"... and {len(self.players) - max_player_rows + 1} more",
            )

    def _wrap_lines(self, lines: list[str], width: int) -> list[str]:
        if width <= 1:
            return lines

        wrapped: list[str] = []

        for line in lines:
            if not line:
                wrapped.append("")
                continue

            parts = textwrap.wrap(
                line,
                width=max(1, width - 1),
                replace_whitespace=False,
                drop_whitespace=False,
                break_long_words=True,
                break_on_hyphens=False,
            )

            if not parts:
                wrapped.append("")
            else:
                wrapped.extend(parts)

        return wrapped

    def _draw_panel(
        self,
        stdscr: Any,
        y: int,
        x: int,
        height: int,
        width: int,
        title: str,
        lines: list[str],
        wrap: bool = False,
    ) -> None:
        if height <= 0 or width <= 0:
            return

        title_attr = self._color(1) | curses.A_BOLD

        self._safe_addstr_attr(stdscr, y, x, title, title_attr)
        self._safe_addstr(stdscr, y + 1, x, "-" * max(0, width - 1))

        body_height = max(0, height - 2)

        if wrap:
            lines = self._wrap_lines(lines, width)

        visible_lines = lines[-body_height:]

        for i, line in enumerate(visible_lines):
            self._safe_addstr(stdscr, y + 2 + i, x, line[: width - 1])

    def _draw_log_file(
        self,
        stdscr: Any,
        y: int,
        x: int,
        height: int,
        width: int,
    ) -> None:
        # Read more physical lines than visible rows because wrapping expands them.
        max_lines = max(20, height * 2)
        lines = self._read_log_tail(max_lines)

        self._draw_panel(
            stdscr=stdscr,
            y=y,
            x=x,
            height=height,
            width=width,
            title=f"Log file: {self.log_path}",
            lines=lines,
            wrap=True,
        )

    def _draw_footer(self, stdscr: Any, height: int, width: int) -> None:
        footer_y = max(0, height - 3)

        # Spacer row above the command separator.
        self._safe_addstr(stdscr, footer_y - 1, 0, "")

        self._safe_addstr(stdscr, footer_y, 0, "-" * min(60, max(0, width - 1)))

        cmd_attr = self._color(2) | curses.A_BOLD
        quit_attr = self._color(4) | curses.A_BOLD

        state = self.state_machine.get_state()

        if state.name == "LOBBY":
            if len(self.players) > 0:
                self._safe_addstr_attr(
                    stdscr, footer_y + 1, 0, "S / Y / Enter", cmd_attr
                )
                self._safe_addstr(stdscr, footer_y + 1, 13, ": start game    ")
                self._safe_addstr_attr(stdscr, footer_y + 1, 30, "Q", quit_attr)
                self._safe_addstr(stdscr, footer_y + 1, 31, ": quit")
            else:
                self._safe_addstr(
                    stdscr, footer_y + 1, 0, "Waiting for players...       "
                )
                self._safe_addstr_attr(stdscr, footer_y + 1, 30, "Q", quit_attr)
                self._safe_addstr(stdscr, footer_y + 1, 31, ": quit")

        elif state.name == "SHOP":
            self._safe_addstr(stdscr, footer_y + 1, 0, "Shop running...              ")
            self._safe_addstr_attr(stdscr, footer_y + 1, 30, "Q", quit_attr)
            self._safe_addstr(stdscr, footer_y + 1, 31, ": quit")

        elif state.name == "GAME":
            self._safe_addstr(stdscr, footer_y + 1, 0, "Game running...              ")
            self._safe_addstr_attr(stdscr, footer_y + 1, 30, "Q", quit_attr)
            self._safe_addstr(stdscr, footer_y + 1, 31, ": quit")

        elif state.name == "END":
            self._safe_addstr(stdscr, footer_y + 1, 0, "Session ending...            ")
            self._safe_addstr_attr(stdscr, footer_y + 1, 30, "Q", quit_attr)
            self._safe_addstr(stdscr, footer_y + 1, 31, ": quit")

        else:
            self._safe_addstr_attr(stdscr, footer_y + 1, 0, "Q", quit_attr)
            self._safe_addstr(stdscr, footer_y + 1, 1, ": quit")
