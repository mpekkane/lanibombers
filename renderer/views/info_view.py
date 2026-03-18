import arcade

SLIDES = [
    ("How to Play", "Move with arrow keys.\nPlant bombs with fire.\nSurvive!"),
    ("Bomb Types", "Choose your bomb before the round.\nBuy upgrades in the shop."),
    ("Shop", "Between rounds you buy weapons.\nSelect 'Ready' when done."),
    ("Credits", "lanibombers\n\nPress ESC to return."),
]


class InfoView(arcade.View):
    """Info/help slideshow — placeholder text slides, Esc exits."""

    def on_show_view(self):
        self.window.background_color = arcade.color.DARK_BLUE
        self._slide = 0

    def on_draw(self):
        self.clear()
        title, body = SLIDES[self._slide]
        arcade.draw_text(
            title,
            self.window.width / 2,
            self.window.height * 0.7,
            arcade.color.YELLOW,
            font_size=40,
            anchor_x="center",
            anchor_y="center",
            bold=True,
        )
        arcade.draw_text(
            body,
            self.window.width / 2,
            self.window.height / 2,
            arcade.color.WHITE,
            font_size=24,
            anchor_x="center",
            anchor_y="center",
            multiline=True,
            width=800,
        )
        arcade.draw_text(
            f"Slide {self._slide + 1}/{len(SLIDES)}  |  LEFT/RIGHT: navigate  |  ESC: back",
            self.window.width / 2,
            60,
            arcade.color.LIGHT_GRAY,
            font_size=18,
            anchor_x="center",
            anchor_y="center",
        )

    def on_key_press(self, key, _modifiers):
        if key == arcade.key.ESCAPE:
            from renderer.views.main_menu_view import MainMenuView
            self.window.show_view(MainMenuView())
        elif key == arcade.key.RIGHT:
            self._slide = min(self._slide + 1, len(SLIDES) - 1)
        elif key == arcade.key.LEFT:
            self._slide = max(self._slide - 1, 0)
