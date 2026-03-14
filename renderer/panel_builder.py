"""
Panel builder utility for lanibombers.
Creates grey beveled panel textures from SHOPPIC.png border pieces.
"""

import os

import arcade
from PIL import Image

GRAPHICS_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "graphics")


class PanelBuilder:
    """Creates grey beveled panel textures using corner/edge pieces from SHOPPIC.png."""

    def __init__(self):
        shoppic = Image.open(os.path.join(GRAPHICS_PATH, "SHOPPIC.png")).convert("RGBA")
        self._corners = {
            'tl': shoppic.crop((0, 0, 3, 3)),
            'tr': shoppic.crop((637, 0, 640, 3)),
            'bl': shoppic.crop((0, 477, 3, 480)),
            'br': shoppic.crop((637, 477, 640, 480)),
        }
        self._edges = {
            'top': shoppic.crop((320, 0, 321, 3)),       # 1x3
            'bottom': shoppic.crop((320, 477, 321, 480)), # 1x3
            'left': shoppic.crop((0, 240, 3, 241)),       # 3x1
            'right': shoppic.crop((637, 240, 640, 241)),   # 3x1
        }

    def create_panel_texture(self, width: int, height: int) -> arcade.Texture:
        """Create a grey beveled panel texture of the given size (min 6x6).

        Uses 3x3 corner pieces and 1px edge strips sampled from SHOPPIC.png,
        with #676767 fill for the interior.
        """
        w = max(width, 6)
        h = max(height, 6)

        panel = Image.new("RGBA", (w, h), (0x67, 0x67, 0x67, 0xFF))

        # Paste corners
        panel.paste(self._corners['tl'], (0, 0))
        panel.paste(self._corners['tr'], (w - 3, 0))
        panel.paste(self._corners['bl'], (0, h - 3))
        panel.paste(self._corners['br'], (w - 3, h - 3))

        # Tile edges
        top_strip = self._edges['top']
        bottom_strip = self._edges['bottom']
        left_strip = self._edges['left']
        right_strip = self._edges['right']

        for x in range(3, w - 3):
            panel.paste(top_strip, (x, 0))
            panel.paste(bottom_strip, (x, h - 3))

        for y in range(3, h - 3):
            panel.paste(left_strip, (0, y))
            panel.paste(right_strip, (w - 3, y))

        return arcade.Texture(panel)
