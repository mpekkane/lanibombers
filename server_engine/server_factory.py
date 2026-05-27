from typing import Optional
from server_engine.server_base import BomberServerBase
from server_engine.cli_server import CursesBomberServer
from server_engine.console_server import ConsoleBomberServer


def build_server(
    *,
    ui: str,
    cfg: str,
    session: str,
    headless: bool,
    map_path: Optional[str],
) -> BomberServerBase:
    if ui == "console":
        return ConsoleBomberServer(cfg, session, headless, map_path)

    if ui == "curses":
        return CursesBomberServer(cfg, session, headless, map_path)

    raise ValueError(f"Unknown UI mode: {ui}")
