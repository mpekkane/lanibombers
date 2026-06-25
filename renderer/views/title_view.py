import os
import random
import arcade

FADE_DURATION = 1.0        # seconds to fade in the TITLEBE backdrop
INTRO_DURATION = 0.5       # version-text fade-in + lani-text zoom duration
LANI_START_SCALE = 10.0    # lani text starts at 1000% and shrinks to 100%
LANI_START_ANGLE = -90.0   # lani text starts rotated 90 degrees CCW, ends at 0

# Nuke explosion effect (mirrors game_renderer.py)
NUKE_SHAKE_DURATION = 2.0  # seconds of screen shake
NUKE_FLASH_DURATION = 1.0  # seconds of white flash
NUKE_SHAKE_MAX_AMP = 50    # base shake amplitude (tiles), scaled by zoom

_GRAPHICS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "graphics")


class TitleView(arcade.View):
    """Title screen.

    Fades in TITLEBE; the first key/button press then plays an intro sequence
    (version text fades in, lani text zooms in from 1000% to 100% over 0.5s),
    followed by the in-game nuke explosion effect (screen shake + white flash
    + explosion sound) before advancing to the main menu.
    """

    def on_show_view(self):
        self.window.background_color = arcade.color.BLACK
        self._alpha = 0.0
        self._elapsed = 0.0
        self._ready = False

        self._zoom = min(self.window.width // 640, self.window.height // 480)
        self._cx = self.window.width / 2
        self._cy = self.window.height / 2
        self._base_w = 640 * self._zoom
        self._base_h = 480 * self._zoom

        self._title_texture = arcade.load_texture(os.path.join(_GRAPHICS_PATH, "TITLEBE.png"))
        self._version_texture = arcade.load_texture(os.path.join(_GRAPHICS_PATH, "version_pamaus_text.png"))
        self._lani_texture = arcade.load_texture(os.path.join(_GRAPHICS_PATH, "lani_text.png"))

        # Intro / nuke sequence state
        self._intro_started = False
        self._intro_elapsed = 0.0
        self._nuke_started = False
        self._nuke_elapsed = 0.0
        self._nuke_done = False
        self._shake_amp = NUKE_SHAKE_MAX_AMP * self._zoom

    def on_update(self, delta_time: float):
        # Phase 1: fade in the backdrop.
        if self._elapsed < FADE_DURATION:
            self._elapsed += delta_time
            self._alpha = min(255, int(255 * self._elapsed / FADE_DURATION))
        else:
            self._alpha = 255
            self._ready = True

        # Auto mode skips straight through once the backdrop has faded in.
        if self._ready and self.window.auto:
            self.window.view_complete()
            return

        # Phase 2: intro (version text fade-in + lani text zoom-in).
        if self._intro_started and not self._nuke_started:
            self._intro_elapsed += delta_time
            if self._intro_elapsed >= INTRO_DURATION:
                self._intro_elapsed = INTRO_DURATION
                self._start_nuke()

        # Phase 3: nuke effect. Once it finishes we wait for another press.
        if self._nuke_started and not self._nuke_done:
            self._nuke_elapsed += delta_time
            if self._nuke_elapsed >= NUKE_SHAKE_DURATION:
                self._nuke_elapsed = NUKE_SHAKE_DURATION
                self._nuke_done = True

    def _start_nuke(self):
        self._nuke_started = True
        self._nuke_elapsed = 0.0
        self.window.sound_engine.explosion()

    def on_draw(self):
        self.clear()

        # Nuke screen-shake offset (amplitude decays over the shake duration).
        if self._nuke_started and self._nuke_elapsed < NUKE_SHAKE_DURATION:
            amp = self._shake_amp * (1.0 - self._nuke_elapsed / NUKE_SHAKE_DURATION)
            ox = random.uniform(-amp, amp)
            oy = random.uniform(-amp, amp)
        else:
            ox = oy = 0.0
        cx = self._cx + ox
        cy = self._cy + oy

        title_rect = arcade.XYWH(cx, cy, self._base_w, self._base_h)
        arcade.draw_texture_rect(self._title_texture, title_rect, pixelated=True)

        # Fade-in overlay for the backdrop (phase 1).
        overlay_alpha = 255 - int(self._alpha)
        if overlay_alpha > 0:
            arcade.draw_rect_filled(title_rect, (0, 0, 0, overlay_alpha))

        # Intro overlays: version text (fading in) and lani text (zooming in).
        if self._intro_started:
            t = min(self._intro_elapsed / INTRO_DURATION, 1.0)
            version_alpha = int(255 * t)
            arcade.draw_texture_rect(
                self._version_texture, title_rect, alpha=version_alpha, pixelated=True
            )
            scale = LANI_START_SCALE + (1.0 - LANI_START_SCALE) * t
            lani_rect = arcade.XYWH(cx, cy, self._base_w * scale, self._base_h * scale)
            lani_angle = LANI_START_ANGLE * (1.0 - t)
            arcade.draw_texture_rect(
                self._lani_texture, lani_rect, angle=lani_angle, pixelated=True
            )

        # Nuke white flash, fading out over its duration.
        if self._nuke_started and self._nuke_elapsed < NUKE_FLASH_DURATION:
            flash_alpha = int(255 * (1.0 - self._nuke_elapsed / NUKE_FLASH_DURATION))
            flash_margin = self._shake_amp * 2
            flash_rect = arcade.XYWH(
                cx, cy,
                self.window.width + flash_margin,
                self.window.height + flash_margin,
            )
            arcade.draw_rect_filled(flash_rect, (255, 255, 255, flash_alpha))

    def _advance(self):
        """First press after fade-in starts the intro/nuke sequence; the next
        press after the nuke effect has finished advances to the main menu."""
        if self._nuke_done:
            self.window.view_complete()
        elif self._ready and not self._intro_started:
            self._intro_started = True

    def on_key_press(self, symbol, modifiers):
        self._advance()

    def on_mouse_press(self, x, y, button, modifiers):
        self._advance()
