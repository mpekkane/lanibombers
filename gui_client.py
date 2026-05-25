# main.py  (project root)
import arcade
from renderer.lanibombers_window import LanibombersWindow
from argparse import ArgumentParser


def main():
    parser = ArgumentParser()
    parser.add_argument("--ip", "-i", type=str, default=None)
    parser.add_argument("--cfg", "-c", type=str, default=None)
    args = parser.parse_args()
    ip = args.ip
    cfg = args.cfg
    window = LanibombersWindow(ip, cfg)
    window.render_view()
    arcade.run()


if __name__ == "__main__":
    main()
