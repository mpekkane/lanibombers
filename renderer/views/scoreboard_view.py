import os
import arcade
from dataclasses import dataclass
from typing import List, Tuple
from PIL import Image

from renderer.player_colorizer import (
    PLAYER_COLORS, KEL_LIGHT, KEL_DARK, brighten, darken,
)
from renderer.bitmap_text import BitmapText

GRAPHICS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "assets", "graphics"
)
SPRITES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "assets", "sprites"
)

# Design-space X centers for ranks 1-4 (left to right)
RANK_X = [96, 249, 400, 554]
# Design-space Y centers for name, money, score
NAME_Y = 335
MONEY_Y = 351
SCORE_Y = 367

# Appearance prefixes for player sprites
APPEARANCE_PREFIX = {1: "SIN", 2: "PUN", 3: "VIH", 4: "KEL"}
# Base colors to swap per appearance (matches CARD_BASE_COLORS)
APPEARANCE_BASE_COLORS = {
    1: (0x00, 0x00, 0x8B),  # Blue
    2: (0xDB, 0x00, 0x00),  # Red
    3: (0x00, 0xA3, 0x00),  # Green
    4: (0xFF, 0xCB, 0x00),  # Yellow
}
# Top-left design coords for each rank position
RANK_SPRITE_POS = [(32, 95), (182, 95), (334, 95), (484, 95)]

# The four ranking number colors in FINAL.png (same as CARD_BASE_COLORS)
RANK_BASE_COLORS = [
    (0x00, 0x00, 0x8B),  # 1st - Blue
    (0xDB, 0x00, 0x00),  # 2nd - Red
    (0x00, 0xA3, 0x00),  # 3rd - Green
    (0xFF, 0xCB, 0x00),  # 4th - Yellow
]



@dataclass
class PlayerResult:
    name: str
    appearance: int
    color: int
    score: int
    money: int = 0


class ScoreboardView(arcade.View):
    """
    End-of-game scoreboard showing the final standings with FINAL.png background.
    """

    def __init__(self, players: List[PlayerResult]):
        super().__init__()
        self.players = players
        self.bg_sprite_list: arcade.SpriteList | None = None

    def on_show_view(self):
        self.window.background_color = arcade.color.BLACK
        self._init_sprite_lists()

    def _recolor_background(self, img: Image.Image) -> Image.Image:
        """Swap ranking number colors in the top half to match top 4 player colors."""
        img = img.copy()
        data = img.load()
        assert data is not None

        # Sort players by score descending, take top 4
        ranked = sorted(self.players, key=lambda p: p.score, reverse=True)[:4]

        # Build swap map: base rank color -> player color
        swap: dict[Tuple[int, int, int], Tuple[int, int, int]] = {}
        for i, player in enumerate(ranked):
            swap[RANK_BASE_COLORS[i]] = PLAYER_COLORS[player.color]

        half_h = img.height // 2
        for y in range(half_h):
            for x in range(img.width):
                r, g, b, a = data[x, y]
                new_color = swap.get((r, g, b))
                if new_color is not None:
                    data[x, y] = (new_color[0], new_color[1], new_color[2], a)

        return img

    def _init_sprite_lists(self):
        z = 2
        self.zoom = z
        font_path = os.path.join(SPRITES_PATH, "font.png")
        self.bitmap_text = BitmapText(font_path, zoom=z)

        bg_path = os.path.join(GRAPHICS_PATH, "FINAL.png")
        bg_image = Image.open(bg_path).convert("RGBA")
        bg_image = self._recolor_background(bg_image)
        bg_texture = arcade.Texture(bg_image)

        bg_sprite = arcade.Sprite()
        bg_sprite.texture = bg_texture
        bg_sprite.scale = z
        bg_sprite.center_x = self.window.width / 2
        bg_sprite.center_y = self.window.height / 2
        self.bg_sprite_list = arcade.SpriteList()
        self.bg_sprite_list.append(bg_sprite)

        # Background image offset: left edge and top edge in screen coords
        self.bg_left = (self.window.width - 640 * z) / 2
        self.bg_top = (self.window.height + 480 * z) / 2

        self._build_player_sprites()
        self._build_text_sprites()

    @staticmethod
    def _recolor_sprite(img: Image.Image, appearance: int,
                        target_color: Tuple[int, int, int]) -> Image.Image:
        """Swap the base color (and light/dark variants) of a player sprite."""
        base = APPEARANCE_BASE_COLORS[appearance]
        swap: dict[Tuple[int, int, int], Tuple[int, int, int]] = {
            base: target_color,
        }
        if appearance == 4:
            swap[KEL_LIGHT] = brighten(target_color)
            swap[KEL_DARK] = darken(target_color)

        img = img.copy()
        data = img.load()
        assert data is not None
        for y in range(img.height):
            for x in range(img.width):
                r, g, b, a = data[x, y]
                new = swap.get((r, g, b))
                if new is not None:
                    data[x, y] = (new[0], new[1], new[2], a)
        return img

    def _build_player_sprites(self):
        """Build recolored player sprites for top 4 ranked players."""
        z = self.zoom
        ranked = sorted(self.players, key=lambda p: p.score, reverse=True)[:4]
        top_score = ranked[0].score
        draw_count = sum(1 for p in ranked if p.score == top_score)
        is_draw = draw_count > 1

        self.player_sprite_list = arcade.SpriteList()
        for i, player in enumerate(ranked):
            prefix = APPEARANCE_PREFIX[player.appearance]
            if is_draw and player.score == top_score:
                suffix = "DRAW"
            elif i == 0:
                suffix = "VOIT"
            else:
                suffix = "LOSE"

            img_path = os.path.join(GRAPHICS_PATH, f"{prefix}{suffix}.png")
            img = Image.open(img_path).convert("RGBA")
            img = self._recolor_sprite(img, player.appearance, PLAYER_COLORS[player.color])
            texture = arcade.Texture(img)

            sprite = arcade.Sprite()
            sprite.texture = texture
            sprite.scale = z
            # Position from top-left design coords
            tl_x, tl_y = RANK_SPRITE_POS[i]
            sx, sy = self._design_to_screen(tl_x, tl_y)
            sprite.left = sx
            sprite.top = sy
            self.player_sprite_list.append(sprite)

    def _design_to_screen(self, dx: float, dy: float) -> Tuple[float, float]:
        """Convert design-space coords (relative to bg image) to screen coords."""
        z = self.zoom
        sx = self.bg_left + dx * z
        sy = self.bg_top - dy * z
        return sx, sy

    def _build_text_sprites(self):
        """Build text sprites for top 4 player names, money and scores."""
        cw = self.bitmap_text.char_width
        ch = self.bitmap_text.char_height
        ranked = sorted(self.players, key=lambda p: p.score, reverse=True)[:4]

        self.text_sprites = arcade.SpriteList()
        for i, player in enumerate(ranked):
            center_x_design = RANK_X[i]

            for text, y_design in [
                (player.name, NAME_Y),
                (str(player.money), MONEY_Y),
                (str(player.score), SCORE_Y),
            ]:
                sx, sy = self._design_to_screen(center_x_design, y_design)
                # Center text: sx is the center, offset left by half text width
                # sy is the center, offset up by half char height (bitmap_text y = top edge)
                x = sx - len(text) * cw / 2
                y = sy + ch / 2
                sprites = self.bitmap_text.create_text_sprites(text, x, y)
                for s in sprites:
                    self.text_sprites.append(s)

    def on_draw(self):
        self.clear()
        if self.bg_sprite_list:
            self.bg_sprite_list.draw(pixelated=True)
        if self.player_sprite_list:
            self.player_sprite_list.draw(pixelated=True)
        if self.text_sprites:
            self.text_sprites.draw(pixelated=True)

    def on_key_press(self, key, _modifiers):
        if key == arcade.key.ESCAPE:
            self._disconnect_and_return()

    def _disconnect_and_return(self):
        self.window.disconnect()
        self.window.view_complete()
