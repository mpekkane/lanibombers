import os
import arcade

_GRAPHICS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "graphics")
_SLIDE_FILES = ["INFO1.png", "INFO3.png", "INFO2.png"]


class InfoView(arcade.View):
    """Info slideshow — INFO1/3/2 images, any key advances, exits after third."""

    def on_show_view(self):
        self.window.background_color = arcade.color.BLACK
        self._slide = 0
        zoom = min(self.window.width // 640, self.window.height // 480)
        rect = arcade.XYWH(self.window.width / 2, self.window.height / 2, 640 * zoom, 480 * zoom)
        self._textures = [
            arcade.load_texture(os.path.join(_GRAPHICS_PATH, f))
            for f in _SLIDE_FILES
        ]
        self._rect = rect

    def on_draw(self):
        self.clear()
        arcade.draw_texture_rect(self._textures[self._slide], self._rect, pixelated=True)

    def on_key_press(self, _key, _modifiers):
        if self._slide < len(_SLIDE_FILES) - 1:
            self._slide += 1
        else:
            from renderer.views.main_menu_view import MainMenuView
            self.window.show_view(MainMenuView())
