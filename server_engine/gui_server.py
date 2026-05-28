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

from game_engine.session_parser import Session


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

        quit_button = ttk.Button(
            button_row,
            text="Quit",
            command=self._on_quit,
            style="Quit.TButton",
            width=self.header_button_width,
        )
        quit_button.pack(side=tk.LEFT, padx=(0, 12))

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
        if state.name not in ("STARTING", "LOBBY"):
            messagebox.showwarning(
                "Session editor",
                "Editing the session is safest before the game has started.\n\n"
                "Return to lobby before applying session changes.",
                parent=self.root,
            )
            return

        win = tk.Toplevel(self.root)
        win.title("Session Setup")
        win.geometry("1900x1440")
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

        maps_frame = ttk.LabelFrame(
            container,
            text="Maps YAML",
            padding=12,
            style="Panel.TLabelframe",
        )
        maps_frame.pack(fill=tk.BOTH, expand=True, pady=(20, 12))

        maps_text = tk.Text(
            maps_frame,
            height=12,
            wrap=tk.NONE,
            font=self.log_font,
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
        maps_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        maps_scroll = ttk.Scrollbar(
            maps_frame,
            orient=tk.VERTICAL,
            command=maps_text.yview,
        )
        maps_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        maps_text.config(yscrollcommand=maps_scroll.set)

        maps_text.insert(
            "1.0",
            yaml.dump(
                {"maps": self.session_config.get("maps", [])},
                default_flow_style=False,
                sort_keys=False,
            ).strip(),
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
                maps_part = yaml.safe_load(maps_text.get("1.0", tk.END)) or {}
                if not isinstance(maps_part, dict):
                    raise ValueError("Maps YAML must be a mapping with key 'maps'.")
                maps = maps_part.get("maps", [])
                if not isinstance(maps, list):
                    raise ValueError("'maps' must be a list.")

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

            except Exception as exc:
                messagebox.showerror(
                    "Invalid session setup",
                    str(exc),
                    parent=win,
                )
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

            filename = filedialog.asksaveasfilename(
                parent=win,
                title="Save session YAML",
                initialfile="session.yaml",
                defaultextension=".yaml",
                filetypes=[
                    ("YAML files", "*.yaml *.yml"),
                    ("All files", "*.*"),
                ],
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
            filename = filedialog.askopenfilename(
                parent=win,
                title="Load session YAML",
                filetypes=[
                    ("YAML files", "*.yaml *.yml"),
                    ("All files", "*.*"),
                ],
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

            maps_text.delete("1.0", tk.END)
            maps_text.insert(
                "1.0",
                yaml.dump(
                    {"maps": config.get("maps", [])},
                    default_flow_style=False,
                    sort_keys=False,
                ).strip(),
            )

            if self._apply_session_config(config):
                status_var.set(f"Loaded and applied {filename}")

        def apply_ok_clicked() -> None:
            apply_clicked()
            if status_var.get().startswith("Applied"):
                win.destroy()

        apply_button = ttk.Button(
            button_row,
            text="Apply / OK",
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
        if self.start_button is None or self.session_button is None:
            return

        state = self.state_machine.get_state()

        if state.name == "LOBBY" and len(self.players) > 0:
            self.start_button.config(state=tk.NORMAL)
            self.session_button.config(state=tk.DISABLED)
        else:
            self.start_button.config(state=tk.DISABLED)
            self.session_button.config(state=tk.NORMAL)

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
