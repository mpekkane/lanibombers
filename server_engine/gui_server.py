from __future__ import annotations

from server_engine.server_base import BomberServerBase

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import Optional, Any
import tempfile
import copy
import yaml

from common.config_reader import resource_path
from game_engine.session_parser import Session

DEFAULT_RANDOM_PARAMS = {
    "width": 64,
    "height": 45,
    "feature_sizes": [20, 5],
    "threshold": 0.1,
    "min_treasure": 10,
    "max_treasure": 40,
    "min_tools": 5,
    "max_tools": 20,
    "max_rooms": 5,
    "room_chance": 0.1,
}


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
        ui_scale: float = 2.0,
    ) -> None:
        self._quit_requested = False
        self._start_requested = False
        self._stop_server_requested = False

        self.icon_dir = resource_path("assets/server")
        self.icons: dict[str, tk.PhotoImage] = {}

        self.log_path = Path(log_path)
        self.font_size = font_size
        self.ui_scale = ui_scale
        self.header_button_width = 14
        self.dialog_button_width = 16

        self.session_path = Path(session_setup)
        self.runtime_session_path = (
            Path(tempfile.gettempdir()) / "lanibombers_runtime_session.yaml"
        )
        self.session_config: dict[str, Any] = {}

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
        self.session_button: Optional[ttk.Button] = None

        super().__init__(
            cfg,
            session_setup,
            headless,
            map_path,
            log=lambda _text: None,
        )

        self.session_config = self._load_session_config_dict(self.session_path)
        self.debug_prints = False

    ##################
    # UI lifecycle hooks
    ##################

    def ui_start(self) -> None:
        self.root = tk.Tk()
        self.root.title("Lanibombers Server")

        self._setup_global_tk_scaling()
        self._setup_fonts()

        self.root.configure(bg=self.bg)

        # Start large, then try to maximize. This works better with large UI scaling.
        self.root.geometry("2560x1440")
        self.root.minsize(1400, 900)
        self._maximize_root_window()

        self.root.protocol("WM_DELETE_WINDOW", self._on_quit)

        self._load_icons()
        self._build_widgets()

    def _maximize_root_window(self) -> None:
        if self.root is None:
            return

        # Windows usually supports this.
        try:
            self.root.state("zoomed")
            return
        except tk.TclError:
            pass

        # Many Linux window managers support this.
        try:
            self.root.attributes("-zoomed", True)
            return
        except tk.TclError:
            pass

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

    def ui_stop_server_requested(self) -> bool:
        if not self._stop_server_requested:
            return False

        self._stop_server_requested = False
        return True

    ##################
    # widget construction
    ##################

    def _setup_global_tk_scaling(self) -> None:
        assert self.root is not None

        # Makes Tk's internal/default widgets and dialogs larger.
        self.root.tk.call("tk", "scaling", self.ui_scale)

        # Make named Tk fonts large too. This helps ttk internals and dialogs.
        named_fonts = [
            "TkDefaultFont",
            "TkTextFont",
            "TkHeadingFont",
            "TkMenuFont",
            "TkTooltipFont",
            "TkFixedFont",
            "TkCaptionFont",
            "TkSmallCaptionFont",
            "TkIconFont",
        ]

        for name in named_fonts:
            try:
                font = tkfont.nametofont(name)
            except tk.TclError:
                continue

            actual = font.actual()
            old_size = int(actual.get("size", self.font_size))

            if old_size < 0:
                old_size = abs(old_size)

            font.configure(size=max(self.font_size, old_size))

    def _setup_fonts(self) -> None:
        # Your chosen fonts.
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

        # Neutral blue header/action button.
        style.configure(
            "Session.TButton",
            font=self.large_font,
            padding=(22, 12),
            background=self.accent,
            foreground="#ffffff",
            bordercolor=self.accent,
            lightcolor=self.accent,
            darkcolor=self.accent,
            focusthickness=1,
            focuscolor=self.accent,
        )
        style.map(
            "Session.TButton",
            background=[
                ("disabled", "#9ca3af"),
                ("pressed", self.accent_hover),
                ("active", self.accent_hover),
                ("!disabled", self.accent),
            ],
            foreground=[
                ("disabled", "#e5e7eb"),
                ("!disabled", "#ffffff"),
            ],
            bordercolor=[
                ("disabled", "#9ca3af"),
                ("pressed", self.accent_hover),
                ("active", self.accent_hover),
                ("!disabled", self.accent),
            ],
            lightcolor=[
                ("disabled", "#9ca3af"),
                ("pressed", self.accent_hover),
                ("active", self.accent_hover),
                ("!disabled", self.accent),
            ],
            darkcolor=[
                ("disabled", "#9ca3af"),
                ("pressed", self.accent_hover),
                ("active", self.accent_hover),
                ("!disabled", self.accent),
            ],
        )

        # Green start/apply button.
        style.configure(
            "Start.TButton",
            font=self.large_font,
            padding=(22, 12),
            background=self.start_bg,
            foreground="#ffffff",
            bordercolor=self.start_bg,
            lightcolor=self.start_bg,
            darkcolor=self.start_bg,
            focusthickness=1,
            focuscolor=self.start_bg,
        )
        style.map(
            "Start.TButton",
            background=[
                ("disabled", "#9ca3af"),
                ("pressed", self.start_hover),
                ("active", self.start_hover),
                ("!disabled", self.start_bg),
            ],
            foreground=[
                ("disabled", "#e5e7eb"),
                ("!disabled", "#ffffff"),
            ],
            bordercolor=[
                ("disabled", "#9ca3af"),
                ("pressed", self.start_hover),
                ("active", self.start_hover),
                ("!disabled", self.start_bg),
            ],
            lightcolor=[
                ("disabled", "#9ca3af"),
                ("pressed", self.start_hover),
                ("active", self.start_hover),
                ("!disabled", self.start_bg),
            ],
            darkcolor=[
                ("disabled", "#9ca3af"),
                ("pressed", self.start_hover),
                ("active", self.start_hover),
                ("!disabled", self.start_bg),
            ],
        )

        # Red quit button.
        style.configure(
            "Quit.TButton",
            font=self.large_font,
            padding=(22, 12),
            background=self.quit_bg,
            foreground="#ffffff",
            bordercolor=self.quit_bg,
            lightcolor=self.quit_bg,
            darkcolor=self.quit_bg,
            focusthickness=1,
            focuscolor=self.quit_bg,
        )
        style.map(
            "Quit.TButton",
            background=[
                ("pressed", self.quit_hover),
                ("active", self.quit_hover),
                ("!disabled", self.quit_bg),
            ],
            foreground=[
                ("!disabled", "#ffffff"),
            ],
            bordercolor=[
                ("pressed", self.quit_hover),
                ("active", self.quit_hover),
                ("!disabled", self.quit_bg),
            ],
            lightcolor=[
                ("pressed", self.quit_hover),
                ("active", self.quit_hover),
                ("!disabled", self.quit_bg),
            ],
            darkcolor=[
                ("pressed", self.quit_hover),
                ("active", self.quit_hover),
                ("!disabled", self.quit_bg),
            ],
        )

        # Neutral dialog button.
        style.configure(
            "Dialog.TButton",
            font=self.base_font,
            padding=(18, 10),
            background="#e5e7eb",
            foreground=self.text_fg,
            bordercolor="#cbd5e1",
            lightcolor="#e5e7eb",
            darkcolor="#cbd5e1",
        )
        style.map(
            "Dialog.TButton",
            background=[
                ("pressed", "#cbd5e1"),
                ("active", "#d1d5db"),
                ("!disabled", "#e5e7eb"),
            ],
            foreground=[
                ("!disabled", self.text_fg),
            ],
            bordercolor=[
                ("pressed", "#94a3b8"),
                ("active", "#94a3b8"),
                ("!disabled", "#cbd5e1"),
            ],
        )

        style.configure(
            "TEntry",
            font=self.base_font,
            padding=(10, 8),
        )

        style.configure(
            "TCombobox",
            font=self.base_font,
            padding=(10, 8),
        )

        style.configure(
            "TCheckbutton",
            font=self.base_font,
            background=self.bg,
            foreground=self.text_fg,
        )

        style.configure(
            "Dialog.TFrame",
            background=self.bg,
        )

        style.configure(
            "DialogTitle.TLabel",
            font=self.title_font,
            background=self.bg,
            foreground=self.header_bg,
        )

        style.configure(
            "HeaderButton.TButton",
            font=self.large_font,
            padding=(22, 12),
            background=self.accent,
            foreground="#ffffff",
            bordercolor=self.accent,
            focusthickness=2,
            focuscolor=self.accent,
        )
        style.map(
            "HeaderButton.TButton",
            background=[
                ("disabled", "#9ca3af"),
                ("active", self.accent_hover),
                ("pressed", self.accent_hover),
            ],
            foreground=[
                ("disabled", "#e5e7eb"),
                ("active", "#ffffff"),
                ("pressed", "#ffffff"),
            ],
        )

        style.configure(
            "DialogButton.TButton",
            font=self.base_font,
            padding=(18, 10),
        )

        style.configure(
            "Icon.TButton",
            padding=(8, 8),
            background="#374151",
            foreground="#ffffff",
            bordercolor="#374151",
            lightcolor="#374151",
            darkcolor="#374151",
        )
        style.map(
            "Icon.TButton",
            background=[
                ("pressed", "#111827"),
                ("active", "#1f2937"),
                ("!disabled", "#374151"),
            ],
            bordercolor=[
                ("pressed", "#111827"),
                ("active", "#1f2937"),
                ("!disabled", "#374151"),
            ],
            lightcolor=[
                ("pressed", "#111827"),
                ("active", "#1f2937"),
                ("!disabled", "#374151"),
            ],
            darkcolor=[
                ("pressed", "#111827"),
                ("active", "#1f2937"),
                ("!disabled", "#374151"),
            ],
        )

        style.configure(
            "IconDanger.TButton",
            padding=(8, 8),
            background=self.quit_bg,
            foreground="#ffffff",
            bordercolor=self.quit_bg,
            lightcolor=self.quit_bg,
            darkcolor=self.quit_bg,
        )
        style.map(
            "IconDanger.TButton",
            background=[
                ("pressed", self.quit_hover),
                ("active", self.quit_hover),
                ("!disabled", self.quit_bg),
            ],
            bordercolor=[
                ("pressed", self.quit_hover),
                ("active", self.quit_hover),
                ("!disabled", self.quit_bg),
            ],
            lightcolor=[
                ("pressed", self.quit_hover),
                ("active", self.quit_hover),
                ("!disabled", self.quit_bg),
            ],
            darkcolor=[
                ("pressed", self.quit_hover),
                ("active", self.quit_hover),
                ("!disabled", self.quit_bg),
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
            width=self.header_button_width,
        )
        self.start_button.pack(side=tk.LEFT, padx=(0, 12))

        self.session_button = ttk.Button(
            button_row,
            text="Session",
            command=self._open_session_editor,
            style="Session.TButton",
            width=self.header_button_width,
        )
        self.session_button.pack(side=tk.LEFT, padx=(0, 12))

        self.quit_button = ttk.Button(
            button_row,
            text="Quit",
            command=self._on_stop_or_quit,
            style="Quit.TButton",
            width=self.header_button_width,
        )
        self.quit_button.pack(side=tk.LEFT, padx=(0, 12))

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
            insertbackground=self.text_fg,
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
    # session editor
    ##################

    def _load_session_config_dict(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return self._default_session_config_dict()

        try:
            with path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except (OSError, yaml.YAMLError):
            return self._default_session_config_dict()

        if not isinstance(data, dict):
            return self._default_session_config_dict()

        return self._normalize_session_config_dict(data)

    def _default_session_config_dict(self) -> dict[str, Any]:
        return {
            "starting_money": getattr(self.session, "starting_money", 500),
            "floating_market": getattr(self.session, "floating_market", False),
            "damage_multiplier": getattr(self.session, "damage_multiplier", 1.0),
            "speed_multiplier": getattr(self.session, "speed_multiplier", 1.0),
            "spawn_type": int(getattr(self.session, "spawn_type", 0)),
            "round_time": int(getattr(self.session, "round_time", 60)),
            "maps": [],
        }

    def _normalize_session_config_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        config = copy.deepcopy(data)

        config.setdefault("starting_money", 500)
        config.setdefault("floating_market", False)
        config.setdefault("damage_multiplier", 1.0)
        config.setdefault("speed_multiplier", 1.0)
        config.setdefault("spawn_type", 0)
        config.setdefault("round_time", 60)
        config.setdefault("maps", [])

        config["starting_money"] = int(config["starting_money"])
        config["floating_market"] = bool(config["floating_market"])
        config["damage_multiplier"] = float(config["damage_multiplier"])
        config["speed_multiplier"] = float(config["speed_multiplier"])
        config["spawn_type"] = int(config["spawn_type"])
        config["round_time"] = int(config["round_time"])

        if not isinstance(config["maps"], list):
            config["maps"] = []

        return config

    def _open_session_editor(self) -> None:
        if self.root is None:
            return

        state = self.state_machine.get_state()
        if state.name != "STOPPED":
            return

        win = tk.Toplevel(self.root)
        win.title("Session Setup")
        win.geometry("2500x2000")
        win.minsize(1500, 1200)
        win.transient(self.root)
        win.grab_set()
        win.configure(bg=self.bg)

        try:
            win.tk.call("tk", "scaling", self.ui_scale)
        except tk.TclError:
            pass

        container = ttk.Frame(win, padding=24, style="Dialog.TFrame")
        container.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(
            container,
            text="Session Setup",
            style="DialogTitle.TLabel",
        )
        title.pack(anchor="w", pady=(0, 16))

        form = ttk.Frame(container)
        form.pack(fill=tk.X)

        starting_money_var = tk.StringVar(
            value=str(self.session_config.get("starting_money", 500))
        )
        floating_market_var = tk.StringVar(
            value=(
                "Yes"
                if bool(self.session_config.get("floating_market", False))
                else "No"
            )
        )
        damage_multiplier_var = tk.StringVar(
            value=str(self.session_config.get("damage_multiplier", 1.0))
        )
        speed_multiplier_var = tk.StringVar(
            value=str(self.session_config.get("speed_multiplier", 1.0))
        )
        spawn_type_var = tk.StringVar(
            value=str(self.session_config.get("spawn_type", 0))
        )
        round_time_var = tk.StringVar(
            value=str(self.session_config.get("round_time", 60))
        )

        self._session_editor_row(form, 0, "Starting money", starting_money_var)
        self._session_editor_bool_row(form, 1, "Floating market", floating_market_var)
        self._session_editor_row(form, 2, "Damage multiplier", damage_multiplier_var)
        self._session_editor_row(form, 3, "Speed multiplier", speed_multiplier_var)

        ttk.Label(form, text="Spawn type").grid(
            row=4,
            column=0,
            sticky="w",
            pady=8,
            padx=(0, 16),
        )
        spawn_combo = ttk.Combobox(
            form,
            textvariable=spawn_type_var,
            values=["0", "1", "2"],
            state="readonly",
            width=20,
            font=self.base_font,
        )
        spawn_combo.grid(row=4, column=1, sticky="ew", pady=8)

        self._session_editor_row(form, 5, "Round time", round_time_var)

        form.columnconfigure(1, weight=1)

        maps_getter, maps_setter = self._build_maps_editor(
            parent=container,
            initial_maps=self.session_config.get("maps", []),
        )

        button_row = ttk.Frame(container)
        button_row.pack(fill=tk.X, pady=(10, 0))

        status_var = tk.StringVar(value="")
        status_label = ttk.Label(
            container,
            textvariable=status_var,
            style="Footer.TLabel",
            anchor="w",
        )
        status_label.pack(fill=tk.X, pady=(8, 0))

        def collect_config() -> Optional[dict[str, Any]]:
            try:
                maps = maps_getter()

                config = {
                    "starting_money": int(starting_money_var.get()),
                    "floating_market": floating_market_var.get() == "Yes",
                    "damage_multiplier": float(damage_multiplier_var.get()),
                    "speed_multiplier": float(speed_multiplier_var.get()),
                    "spawn_type": int(spawn_type_var.get()),
                    "round_time": int(round_time_var.get()),
                    "maps": maps,
                }
                return self._normalize_session_config_dict(config)

            except Exception:
                status_var.set("Invalid session setup.")
                return None

        def apply_clicked() -> None:
            config = collect_config()
            if config is None:
                return

            if self._apply_session_config(config):
                status_var.set("Applied session changes in memory.")
                self.footer_var.set("Session changes applied in memory.")

        def save_clicked() -> None:
            config = collect_config()
            if config is None:
                return

            filename = self._ask_filename_big(
                title="Save session YAML",
                mode="save",
                initialdir=self.session_path.parent,
                initialfile="session.yaml",
                patterns=("*.yaml", "*.yml"),
                default_extension=".yaml",
            )
            if not filename:
                return

            try:
                self._write_session_config(Path(filename), config)
            except OSError as exc:
                messagebox.showerror("Save failed", str(exc), parent=win)
                return

            status_var.set(f"Saved to {filename}")

        def load_clicked() -> None:
            filename = self._ask_filename_big(
                title="Load session YAML",
                mode="open",
                initialdir=self.session_path.parent,
                patterns=("*.yaml", "*.yml"),
            )
            if not filename:
                return

            config = self._load_session_config_dict(Path(filename))

            self.session_config = config

            starting_money_var.set(str(config["starting_money"]))
            floating_market_var.set("Yes" if bool(config["floating_market"]) else "No")
            damage_multiplier_var.set(str(config["damage_multiplier"]))
            speed_multiplier_var.set(str(config["speed_multiplier"]))
            spawn_type_var.set(str(config["spawn_type"]))
            round_time_var.set(str(config["round_time"]))

            maps_setter(config.get("maps", []))

            if self._apply_session_config(config):
                status_var.set(f"Loaded and applied {filename}")

        def apply_ok_clicked() -> None:
            apply_clicked()
            if status_var.get().startswith("Applied"):
                win.destroy()

        apply_button = ttk.Button(
            button_row,
            text="Apply",
            command=apply_ok_clicked,
            style="Start.TButton",
            width=self.dialog_button_width,
        )
        apply_button.pack(side=tk.LEFT, padx=(0, 12))

        save_button = ttk.Button(
            button_row,
            text="Save As...",
            command=save_clicked,
            style="Dialog.TButton",
            width=self.dialog_button_width,
        )
        save_button.pack(side=tk.LEFT, padx=(0, 12))

        load_button = ttk.Button(
            button_row,
            text="Load YAML...",
            command=load_clicked,
            style="Dialog.TButton",
            width=self.dialog_button_width,
        )
        load_button.pack(side=tk.LEFT, padx=(0, 12))

        close_button = ttk.Button(
            button_row,
            text="Cancel",
            command=win.destroy,
            style="Dialog.TButton",
            width=self.dialog_button_width,
        )
        close_button.pack(side=tk.RIGHT)

    def _session_editor_row(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.StringVar,
    ) -> None:
        ttk.Label(parent, text=label).grid(
            row=row,
            column=0,
            sticky="w",
            pady=8,
            padx=(0, 16),
        )

        entry = ttk.Entry(
            parent,
            textvariable=variable,
            font=self.base_font,
        )
        entry.grid(row=row, column=1, sticky="ew", pady=8)

    def _session_editor_bool_row(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.StringVar,
    ) -> None:
        ttk.Label(parent, text=label).grid(
            row=row,
            column=0,
            sticky="w",
            pady=8,
            padx=(0, 16),
        )

        combo = ttk.Combobox(
            parent,
            textvariable=variable,
            values=["No", "Yes"],
            state="readonly",
            width=20,
            font=self.base_font,
        )
        combo.grid(row=row, column=1, sticky="ew", pady=8)

    def _discover_map_files_for_editor(self) -> list[str]:
        """
        Discover available map files for the Tk session editor.

        Mirrors session_setup.py:
            - assets/maps/*.MNE
            - assets/maps/*.MNL
            - plus RANDOM
        """
        maps_dir = resource_path("assets/maps")

        files = sorted(p.name for p in maps_dir.glob("*.MNE"))
        files.extend(sorted(p.name for p in maps_dir.glob("*.MNL")))

        if "RANDOM" not in files:
            files.append("RANDOM")

        return files

    def _map_display_name(self, file_name: str) -> str:
        if file_name == "RANDOM":
            return "Random Map"
        return file_name

    def _normalize_random_params(self, data: dict[str, Any]) -> dict[str, Any]:
        params = copy.deepcopy(DEFAULT_RANDOM_PARAMS)

        for key in params:
            if key in data:
                params[key] = data[key]

        if "feature_size" in data and "feature_sizes" not in data:
            params["feature_sizes"] = [data["feature_size"]]

        feature_sizes = params.get("feature_sizes", [20, 5])
        if not isinstance(feature_sizes, list):
            feature_sizes = [int(feature_sizes)]

        if len(feature_sizes) == 0:
            feature_sizes = [20]

        params["feature_sizes"] = [int(v) for v in feature_sizes]

        params["width"] = int(params["width"])
        params["height"] = int(params["height"])
        params["threshold"] = float(params["threshold"])
        params["min_treasure"] = int(params["min_treasure"])
        params["max_treasure"] = int(params["max_treasure"])
        params["min_tools"] = int(params["min_tools"])
        params["max_tools"] = int(params["max_tools"])
        params["max_rooms"] = int(params["max_rooms"])
        params["room_chance"] = float(params["room_chance"])

        return params

    def _normalize_map_entry_for_editor(self, entry: Any) -> dict[str, Any]:
        """
        Internal editor representation:
            {"file": "foo.MNE"}
            {"file": "RANDOM", "random_params": {...}}
        """
        if isinstance(entry, str):
            return {"file": entry}

        if isinstance(entry, dict):
            file_name = str(entry.get("file", "RANDOM"))

            if file_name == "RANDOM":
                return {
                    "file": "RANDOM",
                    "random_params": self._normalize_random_params(entry),
                }

            return {"file": file_name}

        return {"file": "RANDOM", "random_params": copy.deepcopy(DEFAULT_RANDOM_PARAMS)}

    def _map_entry_to_yaml_value(self, entry: dict[str, Any]) -> Any:
        """
        Convert editor map entry back to session.yaml format.

        Normal map:
            "foo.MNE"

        Random map:
            {"file": "RANDOM", ...random params...}
        """
        file_name = entry.get("file", "RANDOM")

        if file_name == "RANDOM":
            params = self._normalize_random_params(entry.get("random_params", {}))
            return {"file": "RANDOM", **params}

        return file_name

    def _map_entry_summary(self, entry: dict[str, Any]) -> str:
        file_name = entry.get("file", "RANDOM")

        if file_name != "RANDOM":
            return ""

        params = self._normalize_random_params(entry.get("random_params", {}))
        feature_sizes = params.get("feature_sizes", [])

        if len(feature_sizes) >= 2:
            feature_text = f"{feature_sizes[0]}, {feature_sizes[1]}"
        elif len(feature_sizes) == 1:
            feature_text = str(feature_sizes[0])
        else:
            feature_text = "-"

        return (
            f"{params['width']}x{params['height']}  "
            f"features={feature_text}  "
            f"threshold={params['threshold']:.2f}  "
            f"rooms={params['max_rooms']}"
        )

    def _open_map_entry_editor(
        self,
        entry: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        if self.root is None:
            return None

        map_files = self._discover_map_files_for_editor()
        if "RANDOM" not in map_files:
            map_files.append("RANDOM")

        result: dict[str, Optional[dict[str, Any]]] = {"entry": None}

        win = tk.Toplevel(self.root)
        win.title("Edit map")
        win.geometry("1100x1850")
        win.minsize(900, 960)
        win.transient(self.root)
        win.grab_set()
        win.configure(bg=self.bg)

        container = ttk.Frame(win, padding=24, style="Dialog.TFrame")
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            container,
            text="Edit Map",
            style="DialogTitle.TLabel",
        ).pack(anchor="w", pady=(0, 16))

        form = ttk.Frame(container)
        form.pack(fill=tk.X)

        current_file = str(entry.get("file", "RANDOM"))
        if current_file not in map_files:
            current_file = "RANDOM"

        map_name_to_file = {self._map_display_name(name): name for name in map_files}
        file_to_map_name = {name: self._map_display_name(name) for name in map_files}

        map_var = tk.StringVar(value=file_to_map_name[current_file])

        ttk.Label(form, text="Map").grid(
            row=0,
            column=0,
            sticky="w",
            pady=8,
            padx=(0, 16),
        )

        map_combo = ttk.Combobox(
            form,
            textvariable=map_var,
            values=[file_to_map_name[name] for name in map_files],
            state="readonly",
            width=30,
            font=self.base_font,
        )
        map_combo.grid(row=0, column=1, sticky="ew", pady=8)

        params = self._normalize_random_params(entry.get("random_params", {}))

        width_var = tk.StringVar(value=str(params["width"]))
        height_var = tk.StringVar(value=str(params["height"]))

        feature_sizes = params.get("feature_sizes", [20, 5])
        feature_1_var = tk.StringVar(value=str(feature_sizes[0] if len(feature_sizes) > 0 else 20))
        feature_2_var = tk.StringVar(value=str(feature_sizes[1] if len(feature_sizes) > 1 else 0))

        threshold_var = tk.StringVar(value=str(params["threshold"]))
        min_treasure_var = tk.StringVar(value=str(params["min_treasure"]))
        max_treasure_var = tk.StringVar(value=str(params["max_treasure"]))
        min_tools_var = tk.StringVar(value=str(params["min_tools"]))
        max_tools_var = tk.StringVar(value=str(params["max_tools"]))
        max_rooms_var = tk.StringVar(value=str(params["max_rooms"]))
        room_chance_var = tk.StringVar(value=str(params["room_chance"]))

        random_frame = ttk.LabelFrame(
            container,
            text="Random Map Options",
            padding=12,
            style="Panel.TLabelframe",
        )

        self._session_editor_row(random_frame, 0, "Width", width_var)
        self._session_editor_row(random_frame, 1, "Height", height_var)
        self._session_editor_row(random_frame, 2, "Feature Size 1", feature_1_var)
        self._session_editor_row(random_frame, 3, "Feature Size 2", feature_2_var)
        self._session_editor_row(random_frame, 4, "Threshold", threshold_var)
        self._session_editor_row(random_frame, 5, "Min Treasure", min_treasure_var)
        self._session_editor_row(random_frame, 6, "Max Treasure", max_treasure_var)
        self._session_editor_row(random_frame, 7, "Min Tools", min_tools_var)
        self._session_editor_row(random_frame, 8, "Max Tools", max_tools_var)
        self._session_editor_row(random_frame, 9, "Max Rooms", max_rooms_var)
        self._session_editor_row(random_frame, 10, "Room Chance", room_chance_var)

        random_frame.columnconfigure(1, weight=1)
        form.columnconfigure(1, weight=1)

        def update_random_options_visibility(*_args: object) -> None:
            selected_file = map_name_to_file.get(map_var.get(), "RANDOM")

            if selected_file == "RANDOM":
                if not random_frame.winfo_ismapped():
                    random_frame.pack(fill=tk.BOTH, expand=True, pady=(20, 12))
            else:
                if random_frame.winfo_ismapped():
                    random_frame.pack_forget()

        map_combo.bind("<<ComboboxSelected>>", update_random_options_visibility)
        update_random_options_visibility()

        status_var = tk.StringVar(value="")
        status_label = ttk.Label(
            container,
            textvariable=status_var,
            style="Footer.TLabel",
            anchor="w",
        )
        status_label.pack(fill=tk.X, pady=(8, 0))

        def collect_entry() -> Optional[dict[str, Any]]:
            selected_file = map_name_to_file.get(map_var.get(), "RANDOM")

            if selected_file != "RANDOM":
                return {"file": selected_file}

            try:
                feature_1 = int(feature_1_var.get())
                feature_2 = int(feature_2_var.get())

                feature_sizes = [feature_1]
                if feature_2 > 0:
                    feature_sizes.append(feature_2)

                random_params = {
                    "width": int(width_var.get()),
                    "height": int(height_var.get()),
                    "feature_sizes": feature_sizes,
                    "threshold": float(threshold_var.get()),
                    "min_treasure": int(min_treasure_var.get()),
                    "max_treasure": int(max_treasure_var.get()),
                    "min_tools": int(min_tools_var.get()),
                    "max_tools": int(max_tools_var.get()),
                    "max_rooms": int(max_rooms_var.get()),
                    "room_chance": float(room_chance_var.get()),
                }

                return {
                    "file": "RANDOM",
                    "random_params": self._normalize_random_params(random_params),
                }

            except Exception:
                status_var.set("Invalid random map values.")
                return None

        def save_and_close() -> None:
            edited = collect_entry()
            if edited is None:
                return

            result["entry"] = edited
            win.destroy()

        def cancel() -> None:
            result["entry"] = None
            win.destroy()

        button_row = ttk.Frame(container)
        button_row.pack(fill=tk.X, pady=(16, 0))

        ttk.Button(
            button_row,
            text="Save",
            command=save_and_close,
            style="Start.TButton",
            width=self.dialog_button_width,
        ).pack(side=tk.LEFT, padx=(0, 12))

        ttk.Button(
            button_row,
            text="Cancel",
            command=cancel,
            style="Dialog.TButton",
            width=self.dialog_button_width,
        ).pack(side=tk.RIGHT)

        # Closing the edit-map window should save the map edit.
        win.protocol("WM_DELETE_WINDOW", save_and_close)

        win.wait_window()

        return result["entry"]

    def _load_icons(self) -> None:
        self._load_icon("add", "add.png")
        self._load_icon("copy", "copy.png")
        self._load_icon("down", "down.png")
        self._load_icon("edit", "edit.png")
        self._load_icon("remove", "remove.png")
        self._load_icon("up", "up.png")

    def _load_icon(self, name: str, filename: str) -> None:
        if self.root is None:
            return

        path = self.icon_dir / filename

        try:
            self.icons[name] = tk.PhotoImage(file=str(path))
        except tk.TclError:
            # Missing/bad icon: fall back to text button.
            return

    def _icon_button(
        self,
        parent: ttk.Frame,
        icon_name: str,
        fallback_text: str,
        command,
        *,
        style: str = "Dialog.TButton",
        width: int = 8,
    ) -> ttk.Button:
        icon = self.icons.get(icon_name)

        if icon is not None:
            return ttk.Button(
                parent,
                image=icon,
                command=command,
                style=style,
            )

        return ttk.Button(
            parent,
            text=fallback_text,
            command=command,
            style=style,
            width=width,
        )

    def _build_maps_editor(
        self,
        parent: ttk.Frame,
        initial_maps: list[Any],
    ):
        map_entries: list[dict[str, Any]] = [
            self._normalize_map_entry_for_editor(entry) for entry in initial_maps
        ]

        if not map_entries:
            map_files = self._discover_map_files_for_editor()
            first = map_files[0] if map_files else "RANDOM"
            map_entries.append(self._normalize_map_entry_for_editor(first))

        maps_frame = ttk.LabelFrame(
            parent,
            text="Maps",
            padding=12,
            style="Panel.TLabelframe",
        )
        maps_frame.pack(fill=tk.BOTH, expand=True, pady=(20, 12))

        top_row = ttk.Frame(maps_frame)
        top_row.pack(fill=tk.X, pady=(0, 12))

        add_button = self._icon_button(
            top_row,
            "add",
            "Add map",
            command=lambda: None,
            style="Icon.TButton",
            width=self.dialog_button_width,
        )
        add_button.pack(side=tk.LEFT)

        canvas = tk.Canvas(
            maps_frame,
            bg=self.panel_bg,
            highlightthickness=1,
            highlightbackground=self.panel_border,
            borderwidth=0,
        )
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(
            maps_frame,
            orient=tk.VERTICAL,
            command=canvas.yview,
        )
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.configure(yscrollcommand=scrollbar.set)

        rows_frame = ttk.Frame(canvas)
        rows_window = canvas.create_window((0, 0), window=rows_frame, anchor="nw")

        def update_scroll_region(_event: object | None = None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def update_window_width(event: tk.Event) -> None:
            canvas.itemconfigure(rows_window, width=event.width)

        rows_frame.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", update_window_width)

        def refresh_rows() -> None:
            for child in rows_frame.winfo_children():
                child.destroy()

            for index, entry in enumerate(map_entries):
                row = ttk.Frame(rows_frame, padding=(10, 8))
                row.pack(fill=tk.X, pady=(0, 6))

                number = ttk.Label(
                    row,
                    text=f"{index + 1:>2}.",
                    width=4,
                )
                number.pack(side=tk.LEFT, padx=(0, 8))

                name = ttk.Label(
                    row,
                    text=self._map_display_name(entry.get("file", "RANDOM")),
                    font=self.large_font,
                    width=22,
                )
                name.pack(side=tk.LEFT, padx=(0, 12))

                summary = ttk.Label(
                    row,
                    text=self._map_entry_summary(entry),
                    style="Footer.TLabel",
                )
                summary.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))

                edit_button = self._icon_button(
                    row,
                    "edit",
                    "Edit",
                    command=lambda i=index: edit_map(i),
                    style="Icon.TButton",
                    width=8,
                )
                edit_button.pack(side=tk.LEFT, padx=(0, 6))

                duplicate_button = self._icon_button(
                    row,
                    "copy",
                    "Copy",
                    command=lambda i=index: duplicate_map(i),
                    style="Icon.TButton",
                    width=8,
                )
                duplicate_button.pack(side=tk.LEFT, padx=(0, 6))

                up_button = self._icon_button(
                    row,
                    "up",
                    "Up",
                    command=lambda i=index: move_map(i, -1),
                    style="Icon.TButton",
                    width=6,
                )
                up_button.pack(side=tk.LEFT, padx=(0, 6))

                down_button = self._icon_button(
                    row,
                    "down",
                    "Down",
                    command=lambda i=index: move_map(i, 1),
                    style="Icon.TButton",
                    width=6,
                )
                down_button.pack(side=tk.LEFT, padx=(0, 6))

                remove_button = self._icon_button(
                    row,
                    "remove",
                    "Remove",
                    command=lambda i=index: remove_map(i),
                    style="IconDanger.TButton",
                    width=10,
                )
                remove_button.pack(side=tk.LEFT)

            update_scroll_region()

        def add_map() -> None:
            if map_entries:
                new_entry = copy.deepcopy(map_entries[-1])
            else:
                map_files = self._discover_map_files_for_editor()
                first = map_files[0] if map_files else "RANDOM"
                new_entry = self._normalize_map_entry_for_editor(first)

            map_entries.append(new_entry)
            refresh_rows()
            edit_map(len(map_entries) - 1)

        def duplicate_map(index: int) -> None:
            if index < 0 or index >= len(map_entries):
                return

            map_entries.insert(index + 1, copy.deepcopy(map_entries[index]))
            refresh_rows()

        def remove_map(index: int) -> None:
            if index < 0 or index >= len(map_entries):
                return

            map_entries.pop(index)

            if not map_entries:
                map_files = self._discover_map_files_for_editor()
                first = map_files[0] if map_files else "RANDOM"
                map_entries.append(self._normalize_map_entry_for_editor(first))

            refresh_rows()

        def move_map(index: int, direction: int) -> None:
            new_index = index + direction

            if index < 0 or index >= len(map_entries):
                return

            if new_index < 0 or new_index >= len(map_entries):
                return

            map_entries[index], map_entries[new_index] = (
                map_entries[new_index],
                map_entries[index],
            )
            refresh_rows()

        def edit_map(index: int) -> None:
            if index < 0 or index >= len(map_entries):
                return

            edited = self._open_map_entry_editor(map_entries[index])
            if edited is None:
                return

            map_entries[index] = edited
            refresh_rows()

        def get_maps() -> list[Any]:
            return [self._map_entry_to_yaml_value(entry) for entry in map_entries]

        def set_maps(new_maps: list[Any]) -> None:
            map_entries.clear()
            map_entries.extend(
                self._normalize_map_entry_for_editor(entry) for entry in new_maps
            )

            if not map_entries:
                map_files = self._discover_map_files_for_editor()
                first = map_files[0] if map_files else "RANDOM"
                map_entries.append(self._normalize_map_entry_for_editor(first))

            refresh_rows()

        add_button.config(command=add_map)

        refresh_rows()

        return get_maps, set_maps

    def _apply_session_config(self, config: dict[str, Any]) -> bool:
        """
        Apply config to the live server by rebuilding self.session from a temporary YAML.

        This does not modify cfg/session.yaml.
        """
        config = self._normalize_session_config_dict(config)

        try:
            self._write_session_config(self.runtime_session_path, config)
        except OSError as exc:
            if self.root is not None:
                messagebox.showerror("Session apply failed", str(exc), parent=self.root)
            return False

        new_session = Session.parse_session(str(self.runtime_session_path))

        if not new_session.valid:
            if self.root is not None:
                messagebox.showerror(
                    "Session apply failed",
                    "The edited session did not parse as a valid session.",
                    parent=self.root,
                )
            return False

        self.session = new_session
        self.session_config = copy.deepcopy(config)

        try:
            self.rounds_left = self.session.rounds_left()
        except Exception:
            self.rounds_left = 0

        return True

    def _write_session_config(self, path: Path, config: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding="utf-8") as f:
            yaml.dump(
                self._normalize_session_config_dict(config),
                f,
                default_flow_style=False,
                sort_keys=False,
            )

    ##################
    # callbacks
    ##################

    def _on_start(self) -> None:
        self._start_requested = True

    def _on_quit(self) -> None:
        self._quit_requested = True

    def _on_stop_or_quit(self) -> None:
        state = self.state_machine.get_state()

        if state.name == "STOPPED":
            self._quit_requested = True
        else:
            self._stop_server_requested = True

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
        if (
            self.start_button is None
            or self.session_button is None
            or self.quit_button is None
        ):
            return

        state = self.state_machine.get_state()

        if state.name == "STOPPED":
            self.start_button.config(
                text="Start server",
                state=tk.NORMAL,
                style="Start.TButton",
            )
            self.session_button.config(state=tk.NORMAL)
            self.quit_button.config(
                text="Quit",
                state=tk.NORMAL,
                style="Quit.TButton",
            )

        elif state.name == "LOBBY":
            self.start_button.config(
                text="Start game",
                state=tk.NORMAL if len(self.players) > 0 else tk.DISABLED,
                style="Start.TButton",
            )
            self.session_button.config(state=tk.DISABLED)
            self.quit_button.config(
                text="Stop",
                state=tk.NORMAL,
                style="Quit.TButton",
            )

        else:
            self.start_button.config(
                text="Start game",
                state=tk.DISABLED,
                style="Start.TButton",
            )
            self.session_button.config(state=tk.DISABLED)
            self.quit_button.config(
                text="Stop",
                state=tk.NORMAL,
                style="Quit.TButton",
            )

    def _footer_text(self) -> str:
        state = self.state_machine.get_state()

        if state.name == "STOPPED":
            return "Server stopped. Edit the session or click Start server."

        if state.name == "LOBBY":
            if len(self.players) > 0:
                return "Ready. Click Start game to begin, or Stop to close the server."
            return "Server running. Waiting for players..."

        if state.name == "SHOP":
            return "Shop running... Click Stop to return to stopped state."

        if state.name == "GAME":
            return "Game running... Click Stop to return to stopped state."

        if state.name == "END":
            return "Session ending..."

        return ""

    def _ask_filename_big(
        self,
        *,
        title: str,
        mode: str,
        initialdir: Optional[Path] = None,
        initialfile: str = "",
        patterns: tuple[str, ...] = ("*.yaml", "*.yml"),
        default_extension: str = ".yaml",
    ) -> Optional[str]:
        """
        Big Tk file picker.

        mode:
            "open" -> user selects existing file
            "save" -> user chooses/enters output filename
        """
        if self.root is None:
            return None

        if mode not in ("open", "save"):
            raise ValueError("mode must be 'open' or 'save'")

        current_dir = Path(initialdir or Path.cwd()).expanduser().resolve()
        selected: dict[str, Optional[str]] = {"path": None}

        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry("1400x1200")
        win.minsize(1000, 900)
        win.transient(self.root)
        win.grab_set()
        win.configure(bg=self.bg)

        container = ttk.Frame(win, padding=24, style="Dialog.TFrame")
        container.pack(fill=tk.BOTH, expand=True)

        path_var = tk.StringVar(value=str(current_dir))
        filename_var = tk.StringVar(value=initialfile)

        ttk.Label(
            container,
            text=title,
            style="DialogTitle.TLabel",
        ).pack(anchor="w", pady=(0, 16))

        ttk.Label(
            container,
            textvariable=path_var,
            style="Footer.TLabel",
        ).pack(anchor="w", pady=(0, 12))

        list_frame = ttk.Frame(container)
        list_frame.pack(fill=tk.BOTH, expand=True)

        files_list = tk.Listbox(
            list_frame,
            font=self.base_font,
            bg=self.panel_bg,
            fg=self.text_fg,
            selectbackground=self.selection_bg,
            selectforeground="#000000",
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=self.panel_border,
            borderwidth=0,
        )
        files_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=files_list.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        files_list.config(yscrollcommand=scroll.set)

        filename_row = ttk.Frame(container)
        filename_row.pack(fill=tk.X, pady=(16, 0))

        ttk.Label(filename_row, text="Filename").pack(side=tk.LEFT, padx=(0, 12))

        filename_entry = ttk.Entry(
            filename_row,
            textvariable=filename_var,
            font=self.base_font,
        )
        filename_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        entries: list[Path] = []

        def refresh() -> None:
            nonlocal current_dir, entries

            path_var.set(str(current_dir))
            files_list.delete(0, tk.END)

            try:
                dirs = sorted(
                    [p for p in current_dir.iterdir() if p.is_dir()],
                    key=lambda p: p.name.lower(),
                )

                file_candidates: list[Path] = []
                for pattern in patterns:
                    file_candidates.extend(current_dir.glob(pattern))

                files = sorted(set(file_candidates), key=lambda p: p.name.lower())

            except OSError:
                dirs = []
                files = []

            entries = dirs + files

            for p in entries:
                prefix = "[DIR] " if p.is_dir() else "      "
                files_list.insert(tk.END, prefix + p.name)

        def go_up() -> None:
            nonlocal current_dir

            parent = current_dir.parent
            if parent != current_dir:
                current_dir = parent
                refresh()

        def use_selected() -> None:
            nonlocal current_dir

            selection = files_list.curselection()
            if not selection:
                return

            p = entries[selection[0]]

            if p.is_dir():
                current_dir = p
                refresh()
                return

            filename_var.set(p.name)

            if mode == "open":
                selected["path"] = str(p)
                win.destroy()

        def confirm() -> None:
            name = filename_var.get().strip()

            if not name:
                return

            path = Path(name)

            if not path.is_absolute():
                path = current_dir / path

            if mode == "open":
                if not path.exists() or not path.is_file():
                    return

            if mode == "save":
                if path.suffix == "" and default_extension:
                    path = path.with_suffix(default_extension)

            selected["path"] = str(path)
            win.destroy()

        def cancel() -> None:
            selected["path"] = None
            win.destroy()

        files_list.bind("<Double-Button-1>", lambda _event: use_selected())
        files_list.bind("<Return>", lambda _event: use_selected())
        filename_entry.bind("<Return>", lambda _event: confirm())

        button_row = ttk.Frame(container)
        button_row.pack(fill=tk.X, pady=(16, 0))

        ttk.Button(
            button_row,
            text="Up",
            command=go_up,
            style="Dialog.TButton",
            width=self.dialog_button_width,
        ).pack(side=tk.LEFT, padx=(0, 12))

        ttk.Button(
            button_row,
            text="Open" if mode == "open" else "Save",
            command=confirm,
            style="Start.TButton",
            width=self.dialog_button_width,
        ).pack(side=tk.LEFT, padx=(0, 12))

        ttk.Button(
            button_row,
            text="Cancel",
            command=cancel,
            style="Dialog.TButton",
            width=self.dialog_button_width,
        ).pack(side=tk.RIGHT)

        refresh()

        if mode == "save":
            filename_entry.focus_set()
            filename_entry.selection_range(0, tk.END)

        win.wait_window()
        return selected["path"]
