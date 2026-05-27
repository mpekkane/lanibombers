from __future__ import annotations

from server_engine.server_base import BomberServerBase

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk
from pathlib import Path
from typing import Optional


class TkBomberServer(BomberServerBase):
    """
    Simple cross-platform Tkinter GUI.

    This class should only handle presentation and admin input.
    Game/shop/lobby logic should stay in BomberServerBase.

    Layout:
        - Top: header + controls
        - Middle: status cards
        - Lower middle: players / scoreboard
        - Bottom: actual log file tail
    """

    def __init__(
        self,
        cfg: str,
        session_setup: str,
        headless: bool,
        map_path: Optional[str],
        log_path: str = "logs/server.log",
        font_size: int = 24,
    ) -> None:
        self.log_path = Path(log_path)
        self.font_size = font_size

        self.root: Optional[tk.Tk] = None

        self.base_font: Optional[tkfont.Font] = None
        self.title_font: Optional[tkfont.Font] = None
        self.large_font: Optional[tkfont.Font] = None
        self.small_font: Optional[tkfont.Font] = None
        self.log_font: Optional[tkfont.Font] = None

        # Palette. Change these if you want another flavor.
        self.bg = "#eef2f7"
        self.header_bg = "#1f4e79"
        self.header_fg = "#ffffff"

        self.panel_bg = "#ffffff"
        self.panel_border = "#c7d1dd"

        self.text_fg = "#1f2933"
        self.muted_fg = "#5f6b7a"

        self.accent = "#2563eb"
        self.accent_hover = "#1d4ed8"

        self.start_bg = "#15803d"
        self.start_hover = "#166534"

        self.quit_bg = "#b91c1c"
        self.quit_hover = "#991b1b"

        self.log_bg = "#f8fafc"
        self.selection_bg = "#bfdbfe"

        self._quit_requested = False
        self._start_requested = False

        self.state_var: Optional[tk.StringVar] = None
        self.players_var: Optional[tk.StringVar] = None
        self.rounds_var: Optional[tk.StringVar] = None
        self.ping_var: Optional[tk.StringVar] = None
        self.footer_var: Optional[tk.StringVar] = None

        self.players_list: Optional[tk.Listbox] = None
        self.log_text: Optional[tk.Text] = None
        self.start_button: Optional[ttk.Button] = None

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
        self.root = tk.Tk()
        self.root.title("Lanibombers Server")
        self.root.geometry("1920x1080")
        self.root.minsize(960, 640)

        self._setup_fonts()
        self.root.configure(bg=self.bg)

        self.root.protocol("WM_DELETE_WINDOW", self._on_quit)

        self._build_widgets()

    def ui_stop(self) -> None:
        if self.root is None:
            return

        try:
            self.root.destroy()
        except tk.TclError:
            pass
        finally:
            self.root = None

    def ui_tick(self) -> None:
        if self.root is None:
            return

        self._update_status()
        self._update_players()
        self._update_log_tail()
        self._update_controls()

        try:
            self.root.update_idletasks()
            self.root.update()
        except tk.TclError:
            self._quit_requested = True

    def ui_should_quit(self) -> bool:
        return self._quit_requested

    def ui_start_requested(self) -> bool:
        if not self._start_requested:
            return False

        self._start_requested = False
        return True

    def ui_show_scores(self) -> None:
        # Scoreboard is already visible in the player list.
        return

    def ui_show_end_message(self) -> None:
        return

    ##################
    # widget construction
    ##################

    def _setup_fonts(self) -> None:
        # Native-ish proportional Tk font.
        font_family = "helvetica"
        log_font_family = "courier"
        self.base_font = tkfont.Font(family=font_family, size=self.font_size)
        self.title_font = tkfont.Font(
            family=font_family,
            size=self.font_size + 8,
            weight="bold",
        )
        self.large_font = tkfont.Font(
            family=font_family,
            size=self.font_size + 2,
            weight="bold",
        )
        self.small_font = tkfont.Font(
            family=font_family,
            size=max(10, self.font_size - 4),
        )
        self.log_font = tkfont.Font(
            family=log_font_family,
            size=max(10, self.font_size - 6),
        )

        style = ttk.Style()

        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            ".",
            font=self.base_font,
            background=self.bg,
            foreground=self.text_fg,
        )

        style.configure(
            "TFrame",
            background=self.bg,
        )

        style.configure(
            "Header.TFrame",
            background=self.header_bg,
        )

        style.configure(
            "TLabel",
            font=self.base_font,
            background=self.bg,
            foreground=self.text_fg,
        )

        style.configure(
            "Title.TLabel",
            font=self.title_font,
            background=self.header_bg,
            foreground=self.header_fg,
        )

        style.configure(
            "Footer.TLabel",
            font=self.small_font,
            background=self.bg,
            foreground=self.muted_fg,
        )

        style.configure(
            "Card.TFrame",
            background=self.panel_bg,
            relief="solid",
            borderwidth=1,
        )

        style.configure(
            "CardTitle.TLabel",
            font=self.small_font,
            background=self.panel_bg,
            foreground=self.muted_fg,
        )

        style.configure(
            "CardValue.TLabel",
            font=self.large_font,
            background=self.panel_bg,
            foreground=self.text_fg,
        )

        style.configure(
            "Panel.TLabelframe",
            background=self.bg,
            foreground=self.text_fg,
            borderwidth=1,
            relief="solid",
        )

        style.configure(
            "Panel.TLabelframe.Label",
            font=self.large_font,
            background=self.bg,
            foreground=self.header_bg,
        )

        style.configure(
            "TButton",
            font=self.base_font,
            padding=(18, 10),
        )

        style.configure(
            "Start.TButton",
            font=self.large_font,
            padding=(22, 12),
            background=self.start_bg,
            foreground="#ffffff",
            bordercolor=self.start_bg,
            focusthickness=2,
            focuscolor=self.start_bg,
        )
        style.map(
            "Start.TButton",
            background=[
                ("disabled", "#9ca3af"),
                ("active", self.start_hover),
                ("pressed", self.start_hover),
            ],
            foreground=[
                ("disabled", "#e5e7eb"),
                ("active", "#ffffff"),
                ("pressed", "#ffffff"),
            ],
        )

        style.configure(
            "Quit.TButton",
            font=self.base_font,
            padding=(18, 10),
            background=self.quit_bg,
            foreground="#ffffff",
            bordercolor=self.quit_bg,
            focusthickness=2,
            focuscolor=self.quit_bg,
        )
        style.map(
            "Quit.TButton",
            background=[
                ("active", self.quit_hover),
                ("pressed", self.quit_hover),
            ],
            foreground=[
                ("active", "#ffffff"),
                ("pressed", "#ffffff"),
            ],
        )

    def _build_widgets(self) -> None:
        assert self.root is not None

        self.state_var = tk.StringVar(value="-")
        self.players_var = tk.StringVar(value="0")
        self.rounds_var = tk.StringVar(value="0")
        self.ping_var = tk.StringVar(value="-")
        self.footer_var = tk.StringVar(value="")

        outer = ttk.Frame(self.root, padding=24)
        outer.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(outer, style="Header.TFrame", padding=(20, 16))
        header.pack(fill=tk.X)

        title = ttk.Label(
            header,
            text="LANIBOMBERS SERVER",
            style="Title.TLabel",
        )
        title.pack(side=tk.LEFT)

        button_row = ttk.Frame(header, style="Header.TFrame")
        button_row.pack(side=tk.RIGHT)

        self.start_button = ttk.Button(
            button_row,
            text="Start game",
            command=self._on_start,
            style="Start.TButton",
        )
        self.start_button.pack(side=tk.LEFT, padx=(0, 12))

        quit_button = ttk.Button(
            button_row,
            text="Quit",
            command=self._on_quit,
            style="Quit.TButton",
        )
        quit_button.pack(side=tk.LEFT)

        status = ttk.Frame(outer)
        status.pack(fill=tk.X, pady=(20, 16))

        self._make_status_card(status, "State", self.state_var).grid(
            row=0, column=0, sticky="nsew", padx=(0, 12)
        )
        self._make_status_card(status, "Players", self.players_var).grid(
            row=0, column=1, sticky="nsew", padx=(0, 12)
        )
        self._make_status_card(status, "Rounds left", self.rounds_var).grid(
            row=0, column=2, sticky="nsew", padx=(0, 12)
        )
        self._make_status_card(status, "Ping / Pong", self.ping_var).grid(
            row=0, column=3, sticky="nsew"
        )

        for col in range(4):
            status.columnconfigure(col, weight=1)

        main = ttk.PanedWindow(outer, orient=tk.VERTICAL)
        main.pack(fill=tk.BOTH, expand=True)

        players_frame = ttk.LabelFrame(
            main,
            text="Players / Scoreboard",
            padding=14,
            style="Panel.TLabelframe",
        )
        log_frame = ttk.LabelFrame(
            main,
            text=f"Log file: {self.log_path}",
            padding=14,
            style="Panel.TLabelframe",
        )

        main.add(players_frame, weight=1)
        main.add(log_frame, weight=3)

        self.players_list = tk.Listbox(
            players_frame,
            height=8,
            font=self.base_font,
            activestyle="none",
            bg=self.panel_bg,
            fg=self.text_fg,
            selectbackground=self.selection_bg,
            selectforeground="#000000",
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=self.panel_border,
            borderwidth=0,
        )
        self.players_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        players_scroll = ttk.Scrollbar(
            players_frame,
            orient=tk.VERTICAL,
            command=self.players_list.yview,
        )
        players_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.players_list.config(yscrollcommand=players_scroll.set)

        self.log_text = tk.Text(
            log_frame,
            height=12,
            wrap=tk.WORD,
            font=self.log_font,
            state=tk.DISABLED,
            bg=self.log_bg,
            fg=self.text_fg,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=self.panel_border,
            borderwidth=0,
            padx=12,
            pady=10,
        )
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        log_scroll = ttk.Scrollbar(
            log_frame,
            orient=tk.VERTICAL,
            command=self.log_text.yview,
        )
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=log_scroll.set)

        footer = ttk.Label(
            outer,
            textvariable=self.footer_var,
            anchor="w",
            padding=(0, 14, 0, 0),
            style="Footer.TLabel",
        )
        footer.pack(fill=tk.X)

    def _make_status_card(
        self,
        parent: ttk.Frame,
        title: str,
        variable: tk.StringVar,
    ) -> ttk.Frame:
        card = ttk.Frame(parent, padding=(18, 12), style="Card.TFrame")

        title_label = ttk.Label(
            card,
            text=title,
            style="CardTitle.TLabel",
        )
        title_label.pack(anchor="w")

        value_label = ttk.Label(
            card,
            textvariable=variable,
            style="CardValue.TLabel",
        )
        value_label.pack(anchor="w", pady=(4, 0))

        return card

    ##################
    # callbacks
    ##################

    def _on_start(self) -> None:
        self._start_requested = True

    def _on_quit(self) -> None:
        self._quit_requested = True

    ##################
    # updates
    ##################

    def _update_status(self) -> None:
        if (
            self.state_var is None
            or self.players_var is None
            or self.rounds_var is None
            or self.ping_var is None
            or self.footer_var is None
        ):
            return

        state = self.state_machine.get_state()

        self.state_var.set(state.name)
        self.players_var.set(str(len(self.players)))
        self.rounds_var.set(str(self.rounds_left))

        if self.average_ping >= 0:
            avg_ms = self.average_ping / 1e6
            ping_text = f"{self.ping_count}/{self.pong_count}, {avg_ms:.2f} ms"
        else:
            ping_text = f"{self.ping_count}/{self.pong_count}, avg -"

        self.ping_var.set(ping_text)
        self.footer_var.set(self._footer_text())

    def _update_players(self) -> None:
        if self.players_list is None:
            return

        old_top = self.players_list.yview()[0]

        self.players_list.delete(0, tk.END)

        if not self.players:
            self.players_list.insert(tk.END, "No players connected")
            return

        rows = self.get_scoreboard_rows()

        for i, (name, score) in enumerate(rows, start=1):
            player = self._get_session_player_by_name(name)

            if player is None:
                line = f"{i:>2}. {name:<18} score={score:<4}"
            else:
                line = (
                    f"{i:>2}. "
                    f"{player.name:<18} "
                    f"score={player.score:<4} "
                    f"money={player.money:<4}"
                )

            self.players_list.insert(tk.END, line)

        try:
            self.players_list.yview_moveto(old_top)
        except tk.TclError:
            pass

    def _get_session_player_by_name(self, name: str):
        for player in self.players:
            if player.name == name:
                return player
        return None

    def _update_log_tail(self) -> None:
        if self.log_text is None:
            return

        lines = self._read_log_tail(max_lines=200)
        text = "\n".join(lines)

        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.insert(tk.END, text)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

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

    def _update_controls(self) -> None:
        if self.start_button is None:
            return

        state = self.state_machine.get_state()

        if state.name == "LOBBY" and len(self.players) > 0:
            self.start_button.config(state=tk.NORMAL)
        else:
            self.start_button.config(state=tk.DISABLED)

    def _footer_text(self) -> str:
        state = self.state_machine.get_state()

        if state.name == "LOBBY":
            if len(self.players) > 0:
                return "Ready. Click Start game to begin."
            return "Waiting for players..."

        if state.name == "SHOP":
            return "Shop running..."

        if state.name == "GAME":
            return "Game running..."

        if state.name == "END":
            return "Session ending..."

        return ""
