# main.py  (project root)
import arcade
from renderer.lanibombers_window import LanibombersWindow
from argparse import ArgumentParser
from common.logger import setup_logger


def main():
    logger = setup_logger("logs/client.log")
    logger.info("Client started")

    parser = ArgumentParser()
    parser.add_argument("--ip", "-i", type=str, default=None)
    parser.add_argument("--cfg", "-c", type=str, default=None)
    parser.add_argument("--auto", "-a", action="store_true")
    parser.add_argument("--stats", "-s", action="store_true")
    args = parser.parse_args()
    ip = args.ip
    cfg = args.cfg
    auto = args.auto
    stats = args.stats
    window = LanibombersWindow(ip, cfg, auto, stats)
    window.render_view()
    arcade.run()


if __name__ == "__main__":
    main()
