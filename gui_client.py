# main.py  (project root)
import arcade
from renderer.lanibombers_window import LanibombersWindow


def main():
    window = LanibombersWindow()
    window.render_view()
    arcade.run()


if __name__ == "__main__":
    main()
