"""Test script for the scoreboard view with 16 random players."""

import random
import arcade
from renderer.views.scoreboard_view import ScoreboardView, PlayerResult

WINDOW_WIDTH = 1708
WINDOW_HEIGHT = 960

NAMES = [
    "Bomber", "Blaster", "Pyro", "Napalm", "Detonator", "Igniter",
    "Sparky", "Fuse", "Kaboom", "Dynamite", "Firefly", "Flashbang",
    "Mortar", "Rocket", "Nitro", "Inferno",
]


def main():
    players = [
        PlayerResult(
            name=NAMES[i],
            appearance=random.randint(1, 4),
            color=random.randint(0, 15),
            score=random.randint(1, 8),
            money=random.randint(0, 999),
        )
        for i in range(16)
    ]

    window = arcade.Window(WINDOW_WIDTH, WINDOW_HEIGHT, "Scoreboard Test", vsync=True)
    view = ScoreboardView(players)
    window.show_view(view)
    arcade.run()


if __name__ == "__main__":
    main()
