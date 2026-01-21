"""
Player colorizer for lanibombers.
Handles color swapping for player sprites and cards.
"""

import os
import arcade
from PIL import Image
from typing import Dict, Tuple

from game_engine.entities import Direction


# Player color options (16 colors)
PLAYER_COLORS = [
    (0x00, 0x00, 0x8B),  # #00008B - Dark Blue
    (0xDB, 0x00, 0x00),  # #DB0000 - Red
    (0x00, 0xA3, 0x00),  # #00A300 - Green
    (0xFF, 0xCB, 0x00),  # #FFCB00 - Yellow
    (0x6B, 0x00, 0x91),  # #6B0091 - Purple
    (0xFF, 0xFF, 0xFF),  # #FFFFFF - White
    (0xFF, 0x00, 0x91),  # #FF0091 - Pink
    (0x79, 0xFF, 0xFF),  # #79FFFF - Cyan
    (0xEB, 0x00, 0xEB),  # #EB00EB - Magenta
    (0x80, 0xFF, 0x61),  # #80FF61 - Light Green
    (0x00, 0xAD, 0x85),  # #00AD85 - Teal
    (0xFF, 0x40, 0x40),  # #FF4040 - Light Red
    (0xF5, 0xFF, 0x49),  # #F5FF49 - Light Yellow
    (0xFF, 0x91, 0xFF),  # #FF91FF - Light Pink
    (0x52, 0x52, 0xFF),  # #5252FF - Light Blue
    (0xFF, 0x6C, 0x00),  # #FF6C00 - Orange
]

PLAYER_COLOR_NAMES = [
    "Dark Blue", "Red", "Green", "Yellow", "Purple", "White", "Pink", "Cyan",
    "Magenta", "Light Green", "Teal", "Light Red", "Light Yellow", "Light Pink",
    "Light Blue", "Orange"
]

# Base colors to swap for player cards
CARD_BASE_COLORS = {
    1: (0x00, 0x00, 0x8B),  # #00008B - Dark Blue for appearance 1
    2: (0xDB, 0x00, 0x00),  # #DB0000 - Red for appearance 2
    3: (0x00, 0xA3, 0x00),  # #00A300 - Green for appearance 3
    4: (0xFF, 0xCB, 0x00),  # #FFCB00 - Yellow for appearance 4
}

# Base colors for player sprites (different for appearance 4)
SPRITE_BASE_COLORS = {
    1: (0x00, 0x00, 0x8B),  # #00008B - Dark Blue for appearance 1
    2: (0xDB, 0x00, 0x00),  # #DB0000 - Red for appearance 2
    3: (0x00, 0xA3, 0x00),  # #00A300 - Green for appearance 3
    4: (0xFF, 0x9F, 0x00),  # #FF9F00 - Orange for appearance 4 sprites
}


class PlayerColorizer:
    """Handles color swapping for player sprites and cards.

    Loads player sprite and card images, and provides methods to generate
    recolored textures by swapping the base color with a selected color.
    """

    def __init__(self, sprites_path: str):
        """Initialize the player colorizer.

        Args:
            sprites_path: Path to the sprites directory
        """
        self.sprites_path = sprites_path

        # Store original PIL images for recoloring
        self.player_images: Dict[Tuple, Image.Image] = {}  # (sprite_id, state, direction, frame) -> PIL Image
        self.player_card_images: Dict[int, Image.Image] = {}  # sprite_id -> PIL Image

        # Store current textures
        self.player_textures: Dict[Tuple, arcade.Texture] = {}
        self.player_card_textures: Dict[int, arcade.Texture] = {}

        # Load all images
        self._load_images()

    def _load_images(self):
        """Load all player sprite and card images."""
        # Load player sprites
        for sprite_id in range(1, 5):
            for direction in Direction:
                for frame in range(1, 5):
                    # Walking sprites
                    sprite_name = f"player{sprite_id}_{direction.value}_{frame}"
                    path = os.path.join(self.sprites_path, f"{sprite_name}.png")
                    if os.path.exists(path):
                        img = Image.open(path).convert('RGBA')
                        self.player_images[(sprite_id, "walk", direction, frame)] = img
                        self.player_images[(sprite_id, "idle", direction, frame)] = img
                        self.player_textures[(sprite_id, "walk", direction, frame)] = arcade.Texture(img)
                        self.player_textures[(sprite_id, "idle", direction, frame)] = arcade.Texture(img)

                    # Digging sprites
                    dig_sprite_name = f"player{sprite_id}_dig_{direction.value}_{frame}"
                    dig_path = os.path.join(self.sprites_path, f"{dig_sprite_name}.png")
                    if os.path.exists(dig_path):
                        dig_img = Image.open(dig_path).convert('RGBA')
                        self.player_images[(sprite_id, "dig", direction, frame)] = dig_img
                        self.player_textures[(sprite_id, "dig", direction, frame)] = arcade.Texture(dig_img)

        # Load player card images
        for sprite_id in range(1, 5):
            path = os.path.join(self.sprites_path, f"player_card_{sprite_id}.png")
            if os.path.exists(path):
                img = Image.open(path).convert('RGBA')
                self.player_card_images[sprite_id] = img
                self.player_card_textures[sprite_id] = arcade.Texture(img)

    def _swap_color(self, image: Image.Image, old_color: Tuple[int, int, int],
                    new_color: Tuple[int, int, int]) -> Image.Image:
        """Swap a specific color in an image with a new color.

        Args:
            image: The source PIL image
            old_color: RGB tuple of the color to replace
            new_color: RGB tuple of the replacement color

        Returns:
            A new PIL image with the color swapped
        """
        img = image.copy()
        data = img.load()

        for y in range(img.height):
            for x in range(img.width):
                r, g, b, a = data[x, y]
                if (r, g, b) == old_color:
                    data[x, y] = (new_color[0], new_color[1], new_color[2], a)

        return img

    def update_textures(self, sprite_id: int, color_index: int):
        """Regenerate player textures with the selected color.

        Args:
            sprite_id: The player appearance (1-4)
            color_index: Index into PLAYER_COLORS list
        """
        sprite_base_color = SPRITE_BASE_COLORS[sprite_id]
        card_base_color = CARD_BASE_COLORS[sprite_id]
        new_color = PLAYER_COLORS[color_index]

        # Regenerate player sprite textures (using sprite base color)
        for key, img in self.player_images.items():
            if key[0] == sprite_id:  # Only recolor current appearance
                recolored = self._swap_color(img, sprite_base_color, new_color)
                self.player_textures[key] = arcade.Texture(recolored)

        # Regenerate player card texture (using card base color)
        if sprite_id in self.player_card_images:
            recolored_card = self._swap_color(self.player_card_images[sprite_id], card_base_color, new_color)
            self.player_card_textures[sprite_id] = arcade.Texture(recolored_card)

    def get_player_texture(self, sprite_id: int, state: str, direction: Direction,
                           frame: int) -> arcade.Texture:
        """Get a player sprite texture.

        Args:
            sprite_id: The player appearance (1-4)
            state: Player state ("walk", "idle", "dig")
            direction: Player facing direction
            frame: Animation frame (1-4)

        Returns:
            The arcade Texture for the specified sprite
        """
        key = (sprite_id, state, direction, frame)
        return self.player_textures.get(key)

    def get_card_texture(self, sprite_id: int) -> arcade.Texture:
        """Get a player card texture.

        Args:
            sprite_id: The player appearance (1-4)

        Returns:
            The arcade Texture for the specified card
        """
        return self.player_card_textures.get(sprite_id)
