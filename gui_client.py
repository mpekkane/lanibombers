# main.py  (project root)
import arcade
from renderer.lanibombers_window import LanibombersWindow
from renderer.views.title_view import TitleView


def main():
    window = LanibombersWindow()
    title_view = TitleView()
    window.show_view(title_view)
    arcade.run()


if __name__ == "__main__":
    main()
