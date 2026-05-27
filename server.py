from argparse import ArgumentParser
from server_engine.server_factory import build_server
from common.logger import setup_logger


def main() -> None:
    setup_logger("logs/server.log")

    parser = ArgumentParser()

    parser.add_argument("--cfg", "-c", type=str, default="cfg/server_config.yaml")
    parser.add_argument("--map", "-m", type=str, default="")
    parser.add_argument("--session", "-s", type=str, default="cfg/session.yaml")
    parser.add_argument("--display", "-d", action="store_true", default=False)
    parser.add_argument(
        "--ui",
        choices=("console", "curses", "gui"),
        default="curses",
    )
    parser.add_argument(
        "--font-size",
        type=int,
        default=24,
        help="GUI font size",
    )
    args = parser.parse_args()

    cfg = args.cfg
    map_path = args.map
    headless = not args.display
    session = args.session
    font_size = args.font_size

    server = build_server(
        ui=args.ui,
        cfg=cfg,
        session=session,
        headless=headless,
        map_path=map_path,
        font_size=font_size
    )

    server.run_forever()


if __name__ == "__main__":
    main()
