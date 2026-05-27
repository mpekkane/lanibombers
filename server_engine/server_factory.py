from typing import Optional
from server_engine.server_base import BomberServerBase
from server_engine.cli_server import CursesBomberServer
from server_engine.console_server import ConsoleBomberServer
from server_engine.gui_server import TkBomberServer


def build_server(
    *,
    ui: str,
    cfg: str,
    session: str,
    headless: bool,
    map_path: Optional[str],
    font_size: int = 12,
) -> BomberServerBase:
    if ui == "console":
        return ConsoleBomberServer(cfg, session, headless, map_path)

    if ui == "curses":
        return CursesBomberServer(cfg, session, headless, map_path)

    if ui == "gui":
        return TkBomberServer(
            cfg=cfg,
            session_setup=session,
            headless=headless,
            map_path=map_path,
            log_path="logs/server.log",
            font_size=font_size,
        )

    raise ValueError(f"Unknown UI mode: {ui}")
