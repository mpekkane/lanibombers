# main.py  (project root)
import faulthandler
import os
import sys

# In a PyInstaller --windowed build there is no console, so sys.stderr is None
# and the default faulthandler.enable() raises "RuntimeError: sys.stderr is
# None". Fall back to a log file so we still capture crash tracebacks.
try:
    faulthandler.enable()
except (RuntimeError, ValueError):
    os.makedirs("logs", exist_ok=True)
    _fault_log = open("logs/faulthandler.log", "w")
    faulthandler.enable(_fault_log)
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
