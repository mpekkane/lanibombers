import arcade

MENU_ITEMS = ["Player Setup", "Server Finder", "Info", "Exit"]
SELECTED_COLOR = arcade.color.YELLOW
NORMAL_COLOR = arcade.color.WHITE


class MainMenuView(arcade.View):
    """Main menu: four options navigated with arrow keys, confirmed with Enter."""

    def on_show_view(self):
        self.window.background_color = arcade.color.BLACK
        self._selected = 0

    def on_draw(self):
        self.clear()
        arcade.draw_text(
            "LANIBOMBERS",
            self.window.width / 2,
            self.window.height * 0.75,
            arcade.color.WHITE,
            font_size=48,
            anchor_x="center",
            anchor_y="center",
            bold=True,
        )
        for i, label in enumerate(MENU_ITEMS):
            color = SELECTED_COLOR if i == self._selected else NORMAL_COLOR
            prefix = "> " if i == self._selected else "  "
            arcade.draw_text(
                f"{prefix}{label}",
                self.window.width / 2,
                self.window.height * 0.5 - i * 60,
                color,
                font_size=32,
                anchor_x="center",
                anchor_y="center",
            )

    def on_key_press(self, key, _modifiers):
        if key == arcade.key.UP:
            self._selected = (self._selected - 1) % len(MENU_ITEMS)
        elif key == arcade.key.DOWN:
            self._selected = (self._selected + 1) % len(MENU_ITEMS)
        elif key in (arcade.key.RETURN, arcade.key.ENTER):
            self._confirm()

    def _confirm(self):
        label = MENU_ITEMS[self._selected]
        if label == "Player Setup":
            from renderer.views.player_setup_view import PlayerSetupView
            self.window.show_view(PlayerSetupView())
        elif label == "Server Finder":
            from renderer.views.server_finder_view import ServerFinderView
            self.window.show_view(ServerFinderView())
        elif label == "Info":
            from renderer.views.info_view import InfoView
            self.window.show_view(InfoView())
        elif label == "Exit":
            self.window.close()
