# main.py  (project root)
import arcade
from renderer.lanibombers_window import LanibombersWindow
from argparse import ArgumentParser


def main():
    parser = ArgumentParser()
    parser.add_argument("--ip", "-i", type=str, default=None)
    parser.add_argument("--cfg", "-c", type=str, default=None)
    parser.add_argument("--auto", "-a", action="store_true")
    args = parser.parse_args()
    ip = args.ip
    cfg = args.cfg
    auto = args.auto
    window = LanibombersWindow(ip, cfg, auto)
    window.render_view()
    arcade.run()


if __name__ == "__main__":
    main()
