"""
Bitmap text renderer for lanibombers.
Renders text using an 8x8 bitmap font spritesheet.
"""

import os
import arcade
from PIL import Image

# Font properties (must match asset_extractor.py)
FONT_CHAR_WIDTH = 8
FONT_CHAR_HEIGHT = 8
FONT_CHARS_PER_ROW = 16


class BitmapText:
    """Renders text using an 8x8 bitmap font spritesheet.

    The font spritesheet is a 128x128 PNG with 256 characters arranged
    in a 16x16 grid. Characters are indexed by ASCII code.
    """

    def __init__(self, font_path: str, zoom: float = 1.0, color: tuple = (255, 255, 255, 255)):
        """Initialize the bitmap text renderer.

        Args:
            font_path: Path to the font.png spritesheet
            zoom: Scale factor for the text
            color: RGBA color tuple for the text (default white)
        """
        self.zoom = zoom
        self.color = color
        self.char_width = FONT_CHAR_WIDTH * zoom
        self.char_height = FONT_CHAR_HEIGHT * zoom

        # Load the font image with PIL to extract character textures
        font_image = Image.open(font_path).convert('RGBA')

        # Pre-create textures for each character (0-255)
        self.char_textures = {}
        for char_code in range(256):
            grid_x = char_code % FONT_CHARS_PER_ROW
            grid_y = char_code // FONT_CHARS_PER_ROW

            # Calculate pixel coordinates in the spritesheet
            x = grid_x * FONT_CHAR_WIDTH
            y = grid_y * FONT_CHAR_HEIGHT

            # Extract the character from the spritesheet
            char_image = font_image.crop((x, y, x + FONT_CHAR_WIDTH, y + FONT_CHAR_HEIGHT))

            # Create an arcade texture from the PIL image
            texture = arcade.Texture(char_image, name=f"font_char_{char_code}")
            self.char_textures[char_code] = texture

        # Sprite list for rendering text
        self.sprite_list = arcade.SpriteList()

    def create_text_sprites(self, text: str, x: float, y: float,
                            color: tuple = None) -> arcade.SpriteList:
        """Create a sprite list for the given text.

        Args:
            text: The text string to render
            x: X position of the text (left edge)
            y: Y position of the text (top edge)
            color: Optional RGBA color override

        Returns:
            A SpriteList containing sprites for each character
        """
        sprite_list = arcade.SpriteList()
        current_x = x

        for char in text:
            char_code = ord(char)
            if char_code > 255:
                char_code = ord('?')  # Fallback for non-ASCII

            texture = self.char_textures.get(char_code)
            if texture is None:
                current_x += self.char_width
                continue

            sprite = arcade.Sprite()
            sprite.texture = texture
            sprite.scale = self.zoom
            # Position sprite center
            sprite.center_x = current_x + self.char_width / 2
            sprite.center_y = y - self.char_height / 2

            # Apply color tint if specified
            if color:
                sprite.color = color[:3]  # RGB only
                if len(color) > 3:
                    sprite.alpha = color[3]
            elif self.color:
                sprite.color = self.color[:3]
                if len(self.color) > 3:
                    sprite.alpha = self.color[3]

            sprite_list.append(sprite)
            current_x += self.char_width

        return sprite_list

    def draw_text(self, text: str, x: float, y: float, color: tuple = None):
        """Draw text at the specified position.

        Args:
            text: The text string to render
            x: X position of the text (left edge)
            y: Y position of the text (top edge)
            color: Optional RGBA color override
        """
        sprite_list = self.create_text_sprites(text, x, y, color)
        sprite_list.draw(pixelated=True)

    def get_text_width(self, text: str) -> float:
        """Get the width of the given text in pixels.

        Args:
            text: The text string to measure

        Returns:
            Width in pixels (scaled by zoom)
        """
        return len(text) * self.char_width

    def get_text_height(self) -> float:
        """Get the height of a line of text in pixels.

        Returns:
            Height in pixels (scaled by zoom)
        """
        return self.char_height
