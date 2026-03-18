import os
import arcade

_GRAPHICS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "graphics")
_SPRITES_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "sprites")

# Order: Find Server (0), Player Setup (1), Info (2), Exit (3)
MENU_ITEMS = ["Find Server", "Player Setup", "Info", "Exit"]

# Selector geometry in original 640x480 image pixels
_SEL_X = 260       # center x
_SEL_BASE_Y = 148  # center y for item 0
_SEL_STEP_Y = 48   # y increment per item
_SEL_W = 64        # width
_SEL_H = 11        # height


class MainMenuView(arcade.View):
    """Main menu backed by MAIN3.png with a menu_spade selector."""

    def on_show_view(self):
        self.window.background_color = arcade.color.BLACK
        self._selected = 0
        self._zoom = min(self.window.width // 640, self.window.height // 480)
        self._bg_texture = arcade.load_texture(os.path.join(_GRAPHICS_PATH, "MAIN3.png"))
        self._bg_rect = arcade.XYWH(
            self.window.width / 2,
            self.window.height / 2,
            640 * self._zoom,
            480 * self._zoom,
        )
        self._sel_texture = arcade.load_texture(os.path.join(_SPRITES_PATH, "menu_spade.png"))

    def _selector_screen_pos(self, n: int):
        """Return screen (center_x, center_y) for menu item n."""
        z = self._zoom
        img_x = _SEL_X
        img_y = _SEL_BASE_Y + n * _SEL_STEP_Y
        screen_x = self.window.width / 2 + (img_x - 320) * z
        screen_y = self.window.height / 2 + (480 - img_y - 240) * z
        return screen_x, screen_y

    def on_draw(self):
        self.clear()
        arcade.draw_texture_rect(self._bg_texture, self._bg_rect, pixelated=True)
        z = self._zoom
        sx, sy = self._selector_screen_pos(self._selected)
        arcade.draw_texture_rect(self._sel_texture, arcade.XYWH(sx, sy, _SEL_W * z, _SEL_H * z), pixelated=True)

    def on_key_press(self, key, _modifiers):
        if key == arcade.key.UP:
            self._selected = (self._selected - 1) % len(MENU_ITEMS)
        elif key == arcade.key.DOWN:
            self._selected = (self._selected + 1) % len(MENU_ITEMS)
        elif key in (arcade.key.RETURN, arcade.key.ENTER):
            self._confirm()

    def _confirm(self):
        label = MENU_ITEMS[self._selected]
        if label == "Find Server":
            from renderer.views.server_finder_view import ServerFinderView
            self.window.show_view(ServerFinderView())
        elif label == "Player Setup":
            from renderer.views.player_setup_view import PlayerSetupView
            self.window.show_view(PlayerSetupView())
        elif label == "Info":
            from renderer.views.info_view import InfoView
            self.window.show_view(InfoView())
        elif label == "Exit":
            self.window.close()
