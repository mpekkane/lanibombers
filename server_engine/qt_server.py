from __future__ import annotations

from server_engine.server_base import BomberServerBase

import sys
import copy
import tempfile
from pathlib import Path
from typing import Optional, Any

import yaml

from common.config_reader import resource_path
from game_engine.session_parser import Session
from game_engine.spawn_points import SpawnType

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase, QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QFormLayout,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QSplitter,
    QDialog,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QFileDialog,
    QMessageBox,
)

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

# Window size at which the responsive font scale equals 1.0.
DESIGN_WIDTH = 1280
DESIGN_HEIGHT = 800
MIN_SCALE = 0.85
MAX_SCALE = 1.6


class _MainWindow(QMainWindow):
    """QMainWindow that reports its close to the server (for app quit)."""

    def __init__(self, on_close) -> None:
        super().__init__()
        self._on_close = on_close

    def closeEvent(self, event: QCloseEvent) -> None:
        self._on_close()
        event.accept()


class QtBomberServer(BomberServerBase):
    """
    Modern PySide6 (Qt6) server GUI.

    Presentation/admin input only; game/shop/lobby logic stays in
    BomberServerBase. The base drives a poll loop (ui_start, repeated ui_tick,
    ui_stop), so instead of running Qt's own event loop we pump events with
    ``QApplication.processEvents()`` each tick.
    """

    def __init__(
        self,
        cfg: str,
        session_setup: str,
        headless: bool,
        map_path: Optional[str],
        log_path: str = "logs/server.log",
        font_size: int = 24,
        ui_scale: float = 1.0,
    ) -> None:
        self._quit_requested = False
        self._start_requested = False
        self._stop_server_requested = False

        self.log_path = Path(log_path)
        # font_size historically defaulted to 24 (Tk px). Treat 24 as the
        # baseline "looks right" and let other values scale relative to it.
        self._user_scale = max(0.5, font_size / 24.0) * ui_scale
        self._responsive_scale = 1.0

        self.session_path = Path(session_setup)
        self.runtime_session_path = (
            Path(tempfile.gettempdir()) / "lanibombers_runtime_session.yaml"
        )
        self.session_config: dict[str, Any] = {}

        self.app: Optional[QApplication] = None
        self.win: Optional[_MainWindow] = None

        # Widgets filled in during ui_start.
        self.start_button: Optional[QPushButton] = None
        self.session_button: Optional[QPushButton] = None
        self.quit_button: Optional[QPushButton] = None
        self.state_value: Optional[QLabel] = None
        self.players_value: Optional[QLabel] = None
        self.rounds_value: Optional[QLabel] = None
        self.ping_value: Optional[QLabel] = None
        self.players_list: Optional[QListWidget] = None
        self.log_view: Optional[QPlainTextEdit] = None
        self.footer_label: Optional[QLabel] = None

        self._sans_family = "Sans Serif"
        self._mono_family = "Monospace"
        self._last_applied_scale = 0.0

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
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setStyle("Fusion")

        self._sans_family = self._resolve_family(
            ["Inter", "Segoe UI", "Noto Sans", "DejaVu Sans", "Ubuntu", "Liberation Sans"],
            QFont.StyleHint.SansSerif,
        )
        self._mono_family = self._resolve_family(
            ["Cascadia Mono", "JetBrains Mono", "DejaVu Sans Mono", "Liberation Mono",
             "Source Code Pro", "Noto Sans Mono"],
            QFont.StyleHint.Monospace,
        )

        self.win = _MainWindow(self._on_quit)
        self.win.setWindowTitle("Lanibombers Server")
        self.win.resize(DESIGN_WIDTH, DESIGN_HEIGHT)
        self.win.setMinimumSize(820, 560)

        self._build_ui()
        self._apply_responsive_scale(force=True)
        self.win.show()

    def ui_stop(self) -> None:
        if self.win is not None:
            try:
                self.win.close()
            except Exception:
                pass
            self.win = None
        if self.app is not None:
            self.app.processEvents()

    def ui_tick(self) -> None:
        if self.app is None or self.win is None:
            return

        self._apply_responsive_scale()
        self._update_status()
        self._update_players()
        self._update_log_tail()
        self._update_controls()

        self.app.processEvents()

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

    def ui_stop_server_requested(self) -> bool:
        if not self._stop_server_requested:
            return False
        self._stop_server_requested = False
        return True

    ##################
    # widget construction
    ##################

    def _resolve_family(self, candidates: list[str], hint: QFont.StyleHint) -> str:
        available = set(QFontDatabase.families())
        for family in candidates:
            if family in available:
                return family
        probe = QFont()
        probe.setStyleHint(hint)
        return probe.defaultFamily() or candidates[-1]

    def _build_ui(self) -> None:
        assert self.win is not None

        central = QWidget()
        central.setObjectName("root")
        self.win.setCentralWidget(central)

        outer = QVBoxLayout(central)
        outer.setContentsMargins(20, 20, 20, 16)
        outer.setSpacing(16)

        outer.addWidget(self._build_header())
        outer.addWidget(self._build_status_row())

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setObjectName("split")
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_players_panel())
        splitter.addWidget(self._build_log_panel())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([220, 440])
        outer.addWidget(splitter, 1)

        self.footer_label = QLabel("")
        self.footer_label.setObjectName("footer")
        outer.addWidget(self.footer_label)

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("header")
        lay = QHBoxLayout(header)
        lay.setContentsMargins(22, 16, 16, 16)
        lay.setSpacing(12)

        title = QLabel("LANIBOMBERS")
        title.setObjectName("title")
        subtitle = QLabel("SERVER")
        subtitle.setObjectName("subtitle")

        title_box = QHBoxLayout()
        title_box.setSpacing(10)
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        title_wrap = QWidget()
        title_wrap.setLayout(title_box)

        lay.addWidget(title_wrap)
        lay.addStretch(1)

        self.start_button = QPushButton("Start server")
        self.start_button.setObjectName("startBtn")
        self.start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_button.clicked.connect(self._on_start)

        self.session_button = QPushButton("Session")
        self.session_button.setObjectName("sessionBtn")
        self.session_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.session_button.clicked.connect(self._open_session_editor)

        self.quit_button = QPushButton("Quit")
        self.quit_button.setObjectName("quitBtn")
        self.quit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quit_button.clicked.connect(self._on_stop_or_quit)

        for btn in (self.start_button, self.session_button, self.quit_button):
            btn.setProperty("kind", "action")
            lay.addWidget(btn)

        return header

    def _build_status_row(self) -> QWidget:
        row = QWidget()
        grid = QGridLayout(row)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(14)

        self.state_value = QLabel("-")
        self.players_value = QLabel("0")
        self.rounds_value = QLabel("0")
        self.ping_value = QLabel("-")

        cards = [
            ("STATE", self.state_value),
            ("PLAYERS", self.players_value),
            ("ROUNDS LEFT", self.rounds_value),
            ("PING / PONG", self.ping_value),
        ]
        for col, (title, value) in enumerate(cards):
            grid.addWidget(self._make_card(title, value), 0, col)
            grid.setColumnStretch(col, 1)

        return row

    def _make_card(self, title: str, value_label: QLabel) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(6)

        t = QLabel(title)
        t.setObjectName("cardTitle")
        value_label.setObjectName("cardValue")

        lay.addWidget(t)
        lay.addWidget(value_label)
        return card

    def _build_players_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(16, 14, 16, 16)
        lay.setSpacing(10)

        head = QLabel("PLAYERS / SCOREBOARD")
        head.setObjectName("panelTitle")
        lay.addWidget(head)

        self.players_list = QListWidget()
        self.players_list.setObjectName("players")
        self.players_list.setFont(QFont(self._mono_family))
        self.players_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.players_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        lay.addWidget(self.players_list, 1)
        return panel

    def _build_log_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(16, 14, 16, 16)
        lay.setSpacing(10)

        head = QLabel(f"LOG  ·  {self.log_path}")
        head.setObjectName("panelTitle")
        lay.addWidget(head)

        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("log")
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont(self._mono_family))
        self.log_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        lay.addWidget(self.log_view, 1)
        return panel

    ##################
    # responsive scaling / theming
    ##################

    def _apply_responsive_scale(self, force: bool = False) -> None:
        if self.win is None or self.app is None:
            return

        w = self.win.width()
        h = self.win.height()
        scale = min(w / DESIGN_WIDTH, h / DESIGN_HEIGHT)
        scale = max(MIN_SCALE, min(scale, MAX_SCALE)) * self._user_scale

        if not force and abs(scale - self._last_applied_scale) < 0.02:
            return
        self._last_applied_scale = scale

        base = round(15 * scale)
        self.app.setFont(QFont(self._sans_family, base))
        if self.players_list is not None:
            self.players_list.setFont(QFont(self._mono_family, max(9, round(14 * scale))))
        if self.log_view is not None:
            self.log_view.setFont(QFont(self._mono_family, max(9, round(13 * scale))))
        self.win.setStyleSheet(self._stylesheet(scale))

    def _stylesheet(self, scale: float) -> str:
        def px(v: float) -> int:
            return max(1, round(v * scale))

        return f"""
        QWidget#root {{ background: #0b1220; }}
        QWidget {{ color: #e5e9f0; }}

        QFrame#header {{
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #1e3a8a, stop:1 #1e293b);
            border-radius: {px(14)}px;
        }}
        QLabel#title {{ font-size: {px(26)}px; font-weight: 800; letter-spacing: {px(2)}px; color: #ffffff; }}
        QLabel#subtitle {{ font-size: {px(26)}px; font-weight: 300; letter-spacing: {px(6)}px; color: #93c5fd; }}

        QFrame#card {{
            background: #111a2e;
            border: 1px solid #24304a;
            border-radius: {px(12)}px;
        }}
        QLabel#cardTitle {{ color: #8aa0bf; font-size: {px(12)}px; font-weight: 600; letter-spacing: {px(1)}px; }}
        QLabel#cardValue {{ color: #f8fafc; font-size: {px(26)}px; font-weight: 700; }}

        QFrame#panel {{
            background: #0f1729;
            border: 1px solid #24304a;
            border-radius: {px(12)}px;
        }}
        QLabel#panelTitle {{ color: #8aa0bf; font-size: {px(12)}px; font-weight: 700; letter-spacing: {px(1)}px; }}

        QListWidget#players, QPlainTextEdit#log {{
            background: #0b1322;
            border: 1px solid #1d2740;
            border-radius: {px(10)}px;
            padding: {px(8)}px;
            color: #cdd6e6;
            selection-background-color: #1d4ed8;
        }}
        QListWidget#players::item {{ padding: {px(3)}px {px(4)}px; }}

        QLabel#footer {{ color: #6b7c99; font-size: {px(13)}px; padding-top: {px(2)}px; }}

        QPushButton[kind="action"] {{
            border: none;
            border-radius: {px(10)}px;
            padding: {px(11)}px {px(20)}px;
            font-size: {px(15)}px;
            font-weight: 700;
            color: #ffffff;
        }}
        QPushButton#startBtn {{ background: #16a34a; }}
        QPushButton#startBtn:hover {{ background: #15803d; }}
        QPushButton#sessionBtn {{ background: #2563eb; }}
        QPushButton#sessionBtn:hover {{ background: #1d4ed8; }}
        QPushButton#quitBtn {{ background: #dc2626; }}
        QPushButton#quitBtn:hover {{ background: #b91c1c; }}
        QPushButton:disabled {{ background: #334155; color: #94a3b8; }}

        QScrollBar:vertical {{ background: transparent; width: {px(12)}px; margin: {px(2)}px; }}
        QScrollBar::handle:vertical {{ background: #2b3a59; border-radius: {px(5)}px; min-height: {px(30)}px; }}
        QScrollBar::handle:vertical:hover {{ background: #3b4d73; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar:horizontal {{ background: transparent; height: {px(12)}px; margin: {px(2)}px; }}
        QScrollBar::handle:horizontal {{ background: #2b3a59; border-radius: {px(5)}px; min-width: {px(30)}px; }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ height: 0; width: 0; }}

        /* Dialogs */
        QDialog {{ background: #0b1220; }}
        QLabel {{ font-size: {px(15)}px; }}
        QLabel#dialogTitle {{ font-size: {px(22)}px; font-weight: 800; color: #f8fafc; }}
        QLabel#dialogHint {{ color: #6b7c99; font-size: {px(13)}px; }}
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
            background: #0f1729;
            border: 1px solid #2b3a59;
            border-radius: {px(8)}px;
            padding: {px(8)}px {px(10)}px;
            font-size: {px(15)}px;
            color: #e5e9f0;
            selection-background-color: #1d4ed8;
        }}
        QComboBox::drop-down {{ border: none; width: {px(22)}px; }}
        QComboBox QAbstractItemView {{
            background: #0f1729; color: #e5e9f0;
            selection-background-color: #1d4ed8; border: 1px solid #2b3a59;
        }}
        QCheckBox {{ font-size: {px(15)}px; spacing: {px(8)}px; }}
        QPushButton[kind="dialog"] {{
            border: none; border-radius: {px(9)}px;
            padding: {px(10)}px {px(18)}px; font-size: {px(14)}px; font-weight: 600;
            background: #233048; color: #e5e9f0;
        }}
        QPushButton[kind="dialog"]:hover {{ background: #2d3c59; }}
        QPushButton#primary {{ background: #16a34a; color: white; }}
        QPushButton#primary:hover {{ background: #15803d; }}
        QListWidget#maps {{
            background: #0b1322; border: 1px solid #1d2740; border-radius: {px(10)}px;
            padding: {px(6)}px; font-size: {px(14)}px;
        }}
        QListWidget#maps::item {{ padding: {px(7)}px {px(8)}px; border-radius: {px(6)}px; }}
        QListWidget#maps::item:selected {{ background: #1d4ed8; color: white; }}
        """

    ##################
    # updates
    ##################

    def _update_status(self) -> None:
        if self.state_value is None:
            return
        state = self.state_machine.get_state()
        self.state_value.setText(state.name)
        self.players_value.setText(str(len(self.players)))
        self.rounds_value.setText(str(self.rounds_left))

        if self.average_ping >= 0:
            avg_ms = self.average_ping / 1e6
            ping_text = f"{self.ping_count}/{self.pong_count} · {avg_ms:.2f} ms"
        else:
            ping_text = f"{self.ping_count}/{self.pong_count} · -"
        self.ping_value.setText(ping_text)

        if self.footer_label is not None:
            self.footer_label.setText(self._footer_text())

    def _update_players(self) -> None:
        if self.players_list is None:
            return

        scroll = self.players_list.verticalScrollBar()
        prev = scroll.value()

        self.players_list.clear()
        if not self.players:
            self.players_list.addItem("No players connected")
            return

        rows = self.get_scoreboard_rows()
        for i, (name, score) in enumerate(rows, start=1):
            player = self._get_session_player_by_name(name)
            if player is None:
                line = f"{i:>2}.  {name:<18} score={score:<5}"
            else:
                line = (
                    f"{i:>2}.  {player.name:<18} "
                    f"score={player.score:<5} money={player.money:<5}"
                )
            self.players_list.addItem(line)

        scroll.setValue(min(prev, scroll.maximum()))

    def _get_session_player_by_name(self, name: str):
        for player in self.players:
            if player.name == name:
                return player
        return None

    def _update_log_tail(self) -> None:
        if self.log_view is None:
            return
        lines = self._read_log_tail(max_lines=300)
        text = "\n".join(lines)
        if text == self.log_view.toPlainText():
            return
        scroll = self.log_view.verticalScrollBar()
        at_bottom = scroll.value() >= scroll.maximum() - 4
        self.log_view.setPlainText(text)
        if at_bottom:
            scroll.setValue(scroll.maximum())

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
        if self.start_button is None or self.session_button is None or self.quit_button is None:
            return

        state = self.state_machine.get_state()

        if state.name == "STOPPED":
            self.start_button.setText("Start server")
            self.start_button.setEnabled(True)
            self.session_button.setEnabled(True)
            self.quit_button.setText("Quit")
        elif state.name == "LOBBY":
            self.start_button.setText("Start game")
            self.start_button.setEnabled(len(self.players) > 0)
            self.session_button.setEnabled(False)
            self.quit_button.setText("Stop")
        else:
            self.start_button.setText("Start game")
            self.start_button.setEnabled(False)
            self.session_button.setEnabled(False)
            self.quit_button.setText("Stop")

    def _footer_text(self) -> str:
        state = self.state_machine.get_state()
        if state.name == "STOPPED":
            return "Server stopped. Edit the session or click Start server."
        if state.name == "LOBBY":
            if len(self.players) > 0:
                return "Ready. Click Start game to begin, or Stop to close the server."
            return "Server running. Waiting for players…"
        if state.name == "SHOP":
            return "Shop running… Click Stop to return to stopped state."
        if state.name == "GAME":
            return "Game running… Click Stop to return to stopped state."
        if state.name == "END":
            return "Session ending…"
        return ""

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
    # session config (pure logic, shared with the Tk version)
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
            "spawn_type": SpawnType(getattr(self.session, "spawn_type", SpawnType.EDGES)),
            "round_time": int(getattr(self.session, "round_time", 60)),
            "maps": [],
        }

    def _normalize_session_config_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        config = copy.deepcopy(data)
        config.setdefault("starting_money", 500)
        config.setdefault("floating_market", False)
        config.setdefault("damage_multiplier", 1.0)
        config.setdefault("speed_multiplier", 1.0)
        config.setdefault("spawn_type", SpawnType.EDGES)
        config.setdefault("round_time", 60)
        config.setdefault("maps", [])

        config["starting_money"] = int(config["starting_money"])
        config["floating_market"] = bool(config["floating_market"])
        config["damage_multiplier"] = float(config["damage_multiplier"])
        config["speed_multiplier"] = float(config["speed_multiplier"])
        spawn_type = config["spawn_type"]
        if isinstance(spawn_type, str):
            spawn_type = spawn_type.removeprefix("SpawnType.")
            config["spawn_type"] = SpawnType[spawn_type]
        else:
            config["spawn_type"] = SpawnType(spawn_type)
        config["round_time"] = int(config["round_time"])
        if not isinstance(config["maps"], list):
            config["maps"] = []
        return config

    def _discover_map_files_for_editor(self) -> list[str]:
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
        if isinstance(entry, str):
            return {"file": entry}
        if isinstance(entry, dict):
            file_name = str(entry.get("file", "RANDOM"))
            if file_name == "RANDOM":
                return {"file": "RANDOM", "random_params": self._normalize_random_params(entry)}
            return {"file": file_name}
        return {"file": "RANDOM", "random_params": copy.deepcopy(DEFAULT_RANDOM_PARAMS)}

    def _map_entry_to_yaml_value(self, entry: dict[str, Any]) -> Any:
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
            f"{params['width']}×{params['height']}   "
            f"features={feature_text}   "
            f"threshold={params['threshold']:.2f}   "
            f"rooms={params['max_rooms']}"
        )

    def _apply_session_config(self, config: dict[str, Any]) -> bool:
        config = self._normalize_session_config_dict(config)
        try:
            self._write_session_config(self.runtime_session_path, config)
        except OSError as exc:
            QMessageBox.critical(self.win, "Session apply failed", str(exc))
            return False

        new_session = Session.parse_session(str(self.runtime_session_path))
        if not new_session.valid:
            QMessageBox.critical(
                self.win,
                "Session apply failed",
                "The edited session did not parse as a valid session.",
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
            serializable_config = self._normalize_session_config_dict(config)
            serializable_config["spawn_type"] = int(serializable_config["spawn_type"])
            yaml.dump(serializable_config, f, default_flow_style=False, sort_keys=False)

    ##################
    # session editor dialog
    ##################

    def _open_session_editor(self) -> None:
        if self.win is None:
            return
        if self.state_machine.get_state().name != "STOPPED":
            return

        dlg = SessionEditorDialog(self, self.session_config, parent=self.win)
        dlg.setStyleSheet(self._stylesheet(self._last_applied_scale))
        dlg.exec()


##################
# Dialogs
##################


def _make_dialog_button(text: str, primary: bool = False) -> QPushButton:
    btn = QPushButton(text)
    btn.setProperty("kind", "dialog")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary:
        btn.setObjectName("primary")
    return btn


class SessionEditorDialog(QDialog):
    """Edit session parameters and the map rotation."""

    def __init__(self, server: "QtBomberServer", config: dict[str, Any], parent=None) -> None:
        super().__init__(parent)
        self.server = server
        self.setWindowTitle("Session Setup")
        self.setModal(True)
        self.resize(720, 760)

        config = server._normalize_session_config_dict(config)
        self.map_entries: list[dict[str, Any]] = [
            server._normalize_map_entry_for_editor(e) for e in config.get("maps", [])
        ]
        if not self.map_entries:
            files = server._discover_map_files_for_editor()
            self.map_entries.append(server._normalize_map_entry_for_editor(files[0] if files else "RANDOM"))

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 22)
        root.setSpacing(16)

        title = QLabel("Session Setup")
        title.setObjectName("dialogTitle")
        root.addWidget(title)

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.money = QSpinBox()
        self.money.setRange(0, 100_000_000)
        self.money.setValue(int(config["starting_money"]))

        self.floating = QCheckBox("Enabled")
        self.floating.setChecked(bool(config["floating_market"]))

        self.damage = QDoubleSpinBox()
        self.damage.setRange(0.0, 1000.0)
        self.damage.setSingleStep(0.1)
        self.damage.setDecimals(2)
        self.damage.setValue(float(config["damage_multiplier"]))

        self.speed = QDoubleSpinBox()
        self.speed.setRange(0.0, 1000.0)
        self.speed.setSingleStep(0.1)
        self.speed.setDecimals(2)
        self.speed.setValue(float(config["speed_multiplier"]))

        self.spawn = QComboBox()
        for st in SpawnType:
            self.spawn.addItem(st.to_string())
        self.spawn.setCurrentText(config["spawn_type"].to_string())

        self.round_time = QSpinBox()
        self.round_time.setRange(0, 1_000_000)
        self.round_time.setValue(int(config["round_time"]))

        form.addRow("Starting money", self.money)
        form.addRow("Floating market", self.floating)
        form.addRow("Damage multiplier", self.damage)
        form.addRow("Speed multiplier", self.speed)
        form.addRow("Spawn type", self.spawn)
        form.addRow("Round time (s)", self.round_time)
        root.addLayout(form)

        maps_header = QHBoxLayout()
        maps_title = QLabel("MAP ROTATION")
        maps_title.setObjectName("panelTitle")
        maps_header.addWidget(maps_title)
        maps_header.addStretch(1)
        add_btn = _make_dialog_button("+ Add")
        add_btn.clicked.connect(self._add_map)
        maps_header.addWidget(add_btn)
        root.addLayout(maps_header)

        self.maps_list = QListWidget()
        self.maps_list.setObjectName("maps")
        self.maps_list.itemDoubleClicked.connect(lambda _i: self._edit_map())
        root.addWidget(self.maps_list, 1)

        ops = QHBoxLayout()
        ops.setSpacing(8)
        for label, slot in [
            ("Edit", self._edit_map),
            ("Duplicate", self._duplicate_map),
            ("↑", lambda: self._move_map(-1)),
            ("↓", lambda: self._move_map(1)),
            ("Remove", self._remove_map),
        ]:
            b = _make_dialog_button(label)
            b.clicked.connect(slot)
            ops.addWidget(b)
        ops.addStretch(1)
        root.addLayout(ops)

        self.status = QLabel("")
        self.status.setObjectName("dialogHint")
        root.addWidget(self.status)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        apply_btn = _make_dialog_button("Apply", primary=True)
        apply_btn.clicked.connect(self._apply)
        save_btn = _make_dialog_button("Save As…")
        save_btn.clicked.connect(self._save_as)
        load_btn = _make_dialog_button("Load YAML…")
        load_btn.clicked.connect(self._load_yaml)
        cancel_btn = _make_dialog_button("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(apply_btn)
        buttons.addWidget(save_btn)
        buttons.addWidget(load_btn)
        buttons.addStretch(1)
        buttons.addWidget(cancel_btn)
        root.addLayout(buttons)

        self._refresh_maps()

    # --- maps list helpers ---

    def _refresh_maps(self) -> None:
        keep = self.maps_list.currentRow()
        self.maps_list.clear()
        for i, entry in enumerate(self.map_entries, start=1):
            name = self.server._map_display_name(entry.get("file", "RANDOM"))
            summary = self.server._map_entry_summary(entry)
            text = f"{i:>2}.  {name}"
            if summary:
                text += f"      {summary}"
            self.maps_list.addItem(QListWidgetItem(text))
        if 0 <= keep < self.maps_list.count():
            self.maps_list.setCurrentRow(keep)
        elif self.maps_list.count():
            self.maps_list.setCurrentRow(self.maps_list.count() - 1)

    def _current_index(self) -> int:
        idx = self.maps_list.currentRow()
        return idx if 0 <= idx < len(self.map_entries) else -1

    def _add_map(self) -> None:
        if self.map_entries:
            new_entry = copy.deepcopy(self.map_entries[-1])
        else:
            files = self.server._discover_map_files_for_editor()
            new_entry = self.server._normalize_map_entry_for_editor(files[0] if files else "RANDOM")
        self.map_entries.append(new_entry)
        self.maps_list.setCurrentRow(len(self.map_entries) - 1)
        self._refresh_maps()
        self._edit_map()

    def _edit_map(self) -> None:
        idx = self._current_index()
        if idx < 0:
            return
        dlg = MapEditorDialog(self.server, self.map_entries[idx], parent=self)
        dlg.setStyleSheet(self.styleSheet())
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_entry is not None:
            self.map_entries[idx] = dlg.result_entry
            self._refresh_maps()

    def _duplicate_map(self) -> None:
        idx = self._current_index()
        if idx < 0:
            return
        self.map_entries.insert(idx + 1, copy.deepcopy(self.map_entries[idx]))
        self.maps_list.setCurrentRow(idx + 1)
        self._refresh_maps()

    def _remove_map(self) -> None:
        idx = self._current_index()
        if idx < 0:
            return
        self.map_entries.pop(idx)
        if not self.map_entries:
            files = self.server._discover_map_files_for_editor()
            self.map_entries.append(self.server._normalize_map_entry_for_editor(files[0] if files else "RANDOM"))
        self._refresh_maps()

    def _move_map(self, direction: int) -> None:
        idx = self._current_index()
        new_idx = idx + direction
        if idx < 0 or not (0 <= new_idx < len(self.map_entries)):
            return
        self.map_entries[idx], self.map_entries[new_idx] = (
            self.map_entries[new_idx], self.map_entries[idx],
        )
        self.maps_list.setCurrentRow(new_idx)
        self._refresh_maps()

    # --- collect / actions ---

    def _collect(self) -> Optional[dict[str, Any]]:
        try:
            config = {
                "starting_money": int(self.money.value()),
                "floating_market": self.floating.isChecked(),
                "damage_multiplier": float(self.damage.value()),
                "speed_multiplier": float(self.speed.value()),
                "spawn_type": SpawnType.from_string(self.spawn.currentText()),
                "round_time": int(self.round_time.value()),
                "maps": [self.server._map_entry_to_yaml_value(e) for e in self.map_entries],
            }
            return self.server._normalize_session_config_dict(config)
        except Exception:
            self.status.setText("Invalid session setup.")
            return None

    def _apply(self) -> None:
        config = self._collect()
        if config is None:
            return
        if self.server._apply_session_config(config):
            self.accept()

    def _save_as(self) -> None:
        config = self._collect()
        if config is None:
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save session YAML",
            str(self.server.session_path.parent / "session.yaml"),
            "YAML files (*.yaml *.yml)",
        )
        if not filename:
            return
        if "." not in Path(filename).name:
            filename += ".yaml"
        try:
            self.server._write_session_config(Path(filename), config)
        except OSError as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        self.status.setText(f"Saved to {filename}")

    def _load_yaml(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Load session YAML",
            str(self.server.session_path.parent),
            "YAML files (*.yaml *.yml)",
        )
        if not filename:
            return
        config = self.server._load_session_config_dict(Path(filename))
        self.money.setValue(int(config["starting_money"]))
        self.floating.setChecked(bool(config["floating_market"]))
        self.damage.setValue(float(config["damage_multiplier"]))
        self.speed.setValue(float(config["speed_multiplier"]))
        self.spawn.setCurrentText(config["spawn_type"].to_string())
        self.round_time.setValue(int(config["round_time"]))
        self.map_entries = [
            self.server._normalize_map_entry_for_editor(e) for e in config.get("maps", [])
        ]
        if not self.map_entries:
            files = self.server._discover_map_files_for_editor()
            self.map_entries.append(self.server._normalize_map_entry_for_editor(files[0] if files else "RANDOM"))
        self._refresh_maps()
        if self.server._apply_session_config(config):
            self.status.setText(f"Loaded and applied {Path(filename).name}")


class MapEditorDialog(QDialog):
    """Choose a map; for RANDOM, edit generation parameters."""

    def __init__(self, server: "QtBomberServer", entry: dict[str, Any], parent=None) -> None:
        super().__init__(parent)
        self.server = server
        self.result_entry: Optional[dict[str, Any]] = None
        self.setWindowTitle("Edit Map")
        self.setModal(True)
        self.resize(560, 620)

        map_files = server._discover_map_files_for_editor()
        if "RANDOM" not in map_files:
            map_files.append("RANDOM")
        self._files = map_files

        current_file = str(entry.get("file", "RANDOM"))
        if current_file not in map_files:
            current_file = "RANDOM"

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 22)
        root.setSpacing(16)

        title = QLabel("Edit Map")
        title.setObjectName("dialogTitle")
        root.addWidget(title)

        top = QFormLayout()
        top.setHorizontalSpacing(18)
        top.setVerticalSpacing(12)
        self.map_combo = QComboBox()
        for name in map_files:
            self.map_combo.addItem(server._map_display_name(name), userData=name)
        self.map_combo.setCurrentIndex(map_files.index(current_file))
        self.map_combo.currentIndexChanged.connect(self._update_visibility)
        top.addRow("Map", self.map_combo)
        root.addLayout(top)

        params = server._normalize_random_params(entry.get("random_params", {}))
        feature_sizes = params.get("feature_sizes", [20, 5])

        self.random_box = QFrame()
        self.random_box.setObjectName("panel")
        rlay = QVBoxLayout(self.random_box)
        rlay.setContentsMargins(16, 14, 16, 16)
        rlay.setSpacing(10)
        rhead = QLabel("RANDOM MAP OPTIONS")
        rhead.setObjectName("panelTitle")
        rlay.addWidget(rhead)

        rform = QFormLayout()
        rform.setHorizontalSpacing(18)
        rform.setVerticalSpacing(10)

        def spin(lo, hi, val, step=1):
            s = QSpinBox(); s.setRange(lo, hi); s.setValue(int(val))
            if step != 1: s.setSingleStep(step)
            return s

        def dspin(lo, hi, val, step=0.05, dec=2):
            s = QDoubleSpinBox(); s.setRange(lo, hi); s.setDecimals(dec)
            s.setSingleStep(step); s.setValue(float(val))
            return s

        self.width = spin(1, 100000, params["width"])
        self.height = spin(1, 100000, params["height"])
        self.feat1 = spin(0, 100000, feature_sizes[0] if feature_sizes else 20)
        self.feat2 = spin(0, 100000, feature_sizes[1] if len(feature_sizes) > 1 else 0)
        self.threshold = dspin(0.0, 1.0, params["threshold"])
        self.min_treasure = spin(0, 100000, params["min_treasure"])
        self.max_treasure = spin(0, 100000, params["max_treasure"])
        self.min_tools = spin(0, 100000, params["min_tools"])
        self.max_tools = spin(0, 100000, params["max_tools"])
        self.max_rooms = spin(0, 100000, params["max_rooms"])
        self.room_chance = dspin(0.0, 1.0, params["room_chance"])

        rform.addRow("Width", self.width)
        rform.addRow("Height", self.height)
        rform.addRow("Feature size 1", self.feat1)
        rform.addRow("Feature size 2", self.feat2)
        rform.addRow("Threshold", self.threshold)
        rform.addRow("Min treasure", self.min_treasure)
        rform.addRow("Max treasure", self.max_treasure)
        rform.addRow("Min tools", self.min_tools)
        rform.addRow("Max tools", self.max_tools)
        rform.addRow("Max rooms", self.max_rooms)
        rform.addRow("Room chance", self.room_chance)
        rlay.addLayout(rform)
        root.addWidget(self.random_box, 1)

        self.status = QLabel("")
        self.status.setObjectName("dialogHint")
        root.addWidget(self.status)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        save_btn = _make_dialog_button("Save", primary=True)
        save_btn.clicked.connect(self._save)
        cancel_btn = _make_dialog_button("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addStretch(1)
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        root.addLayout(buttons)

        self._update_visibility()

    def _selected_file(self) -> str:
        return self.map_combo.currentData() or "RANDOM"

    def _update_visibility(self) -> None:
        self.random_box.setVisible(self._selected_file() == "RANDOM")

    def _save(self) -> None:
        selected = self._selected_file()
        if selected != "RANDOM":
            self.result_entry = {"file": selected}
            self.accept()
            return
        try:
            feature_sizes = [self.feat1.value()]
            if self.feat2.value() > 0:
                feature_sizes.append(self.feat2.value())
            random_params = {
                "width": self.width.value(),
                "height": self.height.value(),
                "feature_sizes": feature_sizes,
                "threshold": self.threshold.value(),
                "min_treasure": self.min_treasure.value(),
                "max_treasure": self.max_treasure.value(),
                "min_tools": self.min_tools.value(),
                "max_tools": self.max_tools.value(),
                "max_rooms": self.max_rooms.value(),
                "room_chance": self.room_chance.value(),
            }
            self.result_entry = {
                "file": "RANDOM",
                "random_params": self.server._normalize_random_params(random_params),
            }
            self.accept()
        except Exception:
            self.status.setText("Invalid random map values.")
