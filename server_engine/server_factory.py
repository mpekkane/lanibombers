from typing import Optional
from server_engine.server_base import BomberServerBase


def build_server(
    *,
    ui: str,
    cfg: str,
    session: str,
    headless: bool,
    map_path: Optional[str],
    font_size: int = 12,
) -> BomberServerBase:
    if ui == "legacy":
        from server_engine.console_server import ConsoleBomberServer
        return ConsoleBomberServer(cfg, session, headless, map_path)

    if ui == "cli":
        from server_engine.cli_server import CursesBomberServer
        return CursesBomberServer(cfg, session, headless, map_path)

    if ui == "gui":
        from server_engine.qt_server import QtBomberServer
        return QtBomberServer(
            cfg=cfg,
            session_setup=session,
            headless=headless,
            map_path=map_path,
            log_path="logs/server.log",
            font_size=font_size,
        )

    if ui == "tk":
        from server_engine.gui_server import TkBomberServer
        return TkBomberServer(
            cfg=cfg,
            session_setup=session,
            headless=headless,
            map_path=map_path,
            log_path="logs/server.log",
            font_size=font_size,
        )

    raise ValueError(f"Unknown UI mode: {ui}")
