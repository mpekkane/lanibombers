import random
import arcade
from typing import List


class ScoreboardView(arcade.View):
    """
    End-of-game scoreboard.
    Players listed with random placeholder scores (real scores added later).
    ESC disconnects and returns to main menu.
    """

    def __init__(self, player_names: List[str]):
        super().__init__()
        self._entries = sorted(
            [(name, random.randint(0, 9999)) for name in player_names],
            key=lambda x: x[1],
            reverse=True,
        )

    def on_show_view(self):
        self.window.background_color = arcade.color.BLACK

    def on_draw(self):
        self.clear()
        arcade.draw_text(
            "GAME OVER",
            self.window.width / 2,
            self.window.height * 0.85,
            arcade.color.RED,
            font_size=56,
            anchor_x="center",
            anchor_y="center",
            bold=True,
        )
        arcade.draw_text(
            "SCOREBOARD",
            self.window.width / 2,
            self.window.height * 0.75,
            arcade.color.YELLOW,
            font_size=32,
            anchor_x="center",
            anchor_y="center",
        )
        for rank, (name, score) in enumerate(self._entries):
            if rank < 3:
                prefix = ["1st", "2nd", "3rd"][rank]
            else:
                prefix = f"{rank + 1}th"
            line = f"{prefix}  {name:<20} {score:>6} pts"
            arcade.draw_text(
                line,
                self.window.width / 2,
                self.window.height * 0.62 - rank * 52,
                arcade.color.WHITE,
                font_size=28,
                anchor_x="center",
                anchor_y="center",
            )
        arcade.draw_text(
            "ESC: disconnect and return to menu",
            self.window.width / 2,
            50,
            arcade.color.LIGHT_GRAY,
            font_size=18,
            anchor_x="center",
            anchor_y="center",
        )

    def on_key_press(self, key, _modifiers):
        if key == arcade.key.ESCAPE:
            self._disconnect_and_return()

    def _disconnect_and_return(self):
        self.window.disconnect()
        from renderer.views.main_menu_view import MainMenuView
        self.window.show_view(MainMenuView())
