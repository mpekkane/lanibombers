import arcade

FADE_DURATION = 2.0   # seconds to fade in


class TitleView(arcade.View):
    """Title screen: fades in placeholder graphic, any key advances."""

    def on_show_view(self):
        self.window.background_color = arcade.color.BLACK
        self._alpha = 0.0
        self._elapsed = 0.0
        self._ready = False

    def on_update(self, delta_time: float):
        if self._elapsed < FADE_DURATION:
            self._elapsed += delta_time
            self._alpha = min(255, int(255 * self._elapsed / FADE_DURATION))
        else:
            self._alpha = 255
            self._ready = True

    def on_draw(self):
        self.clear()
        arcade.draw_text(
            "LANIBOMBERS",
            self.window.width / 2,
            self.window.height / 2,
            (255, 255, 255, int(self._alpha)),
            font_size=72,
            anchor_x="center",
            anchor_y="center",
            bold=True,
        )
        if self._ready:
            arcade.draw_text(
                "press any key",
                self.window.width / 2,
                self.window.height / 2 - 100,
                (211, 211, 211, int(self._alpha)),
                font_size=24,
                anchor_x="center",
                anchor_y="center",
            )

    def on_key_press(self, _key, _modifiers):
        if self._ready:
            from renderer.views.main_menu_view import MainMenuView
            self.window.show_view(MainMenuView())
