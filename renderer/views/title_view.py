import os
import arcade

FADE_DURATION = 2.0   # seconds to fade in

_GRAPHICS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "graphics")


class TitleView(arcade.View):
    """Title screen: fades in TITLEBE graphic, any key advances."""

    def on_show_view(self):
        self.window.background_color = arcade.color.BLACK
        self._alpha = 0.0
        self._elapsed = 0.0
        self._ready = False
        zoom = min(self.window.width // 640, self.window.height // 480)
        self._texture = arcade.load_texture(os.path.join(_GRAPHICS_PATH, "TITLEBE.png"))
        self._rect = arcade.XYWH(
            self.window.width / 2,
            self.window.height / 2,
            640 * zoom,
            480 * zoom,
        )

    def on_update(self, delta_time: float):
        if self._elapsed < FADE_DURATION:
            self._elapsed += delta_time
            self._alpha = min(255, int(255 * self._elapsed / FADE_DURATION))
        else:
            self._alpha = 255
            self._ready = True

    def on_draw(self):
        self.clear()
        arcade.draw_texture_rect(self._texture, self._rect, pixelated=True)
        overlay_alpha = 255 - int(self._alpha)
        if overlay_alpha > 0:
            arcade.draw_rect_filled(self._rect, (0, 0, 0, overlay_alpha))

    def on_key_press(self, symbol, modifiers):
        if self._ready:
            self.window.view_complete()
