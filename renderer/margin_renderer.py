"""
Margin renderer for lanibombers.
Shows enemy player cards in the right margin during gameplay.
"""

import os
from typing import List

import arcade

from game_engine.entities.player import Player
from renderer.bitmap_text import BitmapText
from renderer.panel_builder import PanelBuilder
from renderer.player_colorizer import PlayerColorizer
from PIL import Image
from common.item_dictionary import ItemType, get_item_icon
from common.bomb_dictionary import BombType

SPRITES_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "sprites")


class MarginRenderer:
    """Renders enemy player cards in the right margin of the game viewport."""

    def __init__(self, zoom: float, screen_height: int, client_player_name: str):
        self.zoom = zoom
        self.screen_height = screen_height
        self.client_player_name = client_player_name

        self.card_x = 640
        self.card_w = 110
        self.card_h = 30
        self.icon_size = 30
        self.max_slots = 16

        # Utilities
        self.panel_builder = PanelBuilder()
        self.bitmap_text = BitmapText(os.path.join(SPRITES_PATH, "font.png"), zoom=zoom)
        self.colorizer = PlayerColorizer(SPRITES_PATH)

        # Sprite lists
        self.panel_sprites = arcade.SpriteList()
        self.card_sprites = arcade.SpriteList()
        self.text_sprites = arcade.SpriteList()
        self.damage_overlay_sprites = arcade.SpriteList()
        self.black_image = Image.new("RGBA", (1, 1), (0, 0, 0, 255))
        self.other_player_info_sprites = arcade.SpriteList()

        # Build static grey panel backgrounds for all 16 slots
        card_panel_texture = self.panel_builder.create_panel_texture(
            self.card_w, self.card_h
        )
        icon_panel_texture = self.panel_builder.create_panel_texture(
            self.icon_size, self.icon_size
        )
        for slot in range(self.max_slots):
            slot_y = (slot + 1) * self.card_h

            panel = arcade.Sprite()
            panel.texture = card_panel_texture
            panel.scale = zoom
            panel.center_x = (self.card_x + self.card_w / 2) * zoom
            panel.center_y = screen_height - (slot_y + self.card_h / 2) * zoom
            self.panel_sprites.append(panel)

            icon_panel = arcade.Sprite()
            icon_panel.texture = icon_panel_texture
            icon_panel.scale = zoom
            icon_panel.center_x = (
                self.card_x + self.card_w + self.icon_size / 2
            ) * zoom
            icon_panel.center_y = screen_height - (slot_y + self.icon_size / 2) * zoom
            self.panel_sprites.append(icon_panel)

        # Change detection cache: list of per-player tuples
        self._cached_player_keys: list = []

        # Load icon textures for all shop items
        self.icon_textures: dict[BombType, arcade.Texture] = {}
        bombs = [btype for btype in BombType]
        for item in bombs:
            icon_name = get_item_icon(item)
            if icon_name:
                path = os.path.join(SPRITES_PATH, f"{icon_name}_icon.png")
                if os.path.exists(path):
                    self.icon_textures[item] = arcade.load_texture(path)

        # time bar
        self.time_bar_sprites = arcade.SpriteList()
        yellow_image = Image.new("RGBA", (1, 1), (255, 255, 0, 255))
        self.time_bar = arcade.Sprite()
        self.time_bar.texture = arcade.Texture(yellow_image, name="time_bar")
        self.time_bar.visible = True
        self.time_bar_sprites.append(self.time_bar)
        self.max_time = None

    def on_update(self, players: List[Player], round_time_left: float):
        """Update enemy cards if player data changed."""
        # time bar
        if self.max_time is None:
            self.max_time = round_time_left

        time_ratio = round_time_left / self.max_time
        self.time_bar.width = 5 * self.zoom
        self.time_bar.height = 450 * time_ratio * self.zoom
        self.time_bar.center_x = (
            (self.card_x + self.card_w + 30) * self.zoom + self.time_bar.width // 2
        )
        self.time_bar.center_y = self.time_bar.height / 2

        others = [p for p in players if p.name != self.client_player_name]

        # Build cache key per player
        player_keys = [
            (
                p.name,
                p.sprite_id,
                p.color,
                p.money,
                p.get_dig_power(),
                p.health,
                p.selected,
            )
            for p in others
        ]
        if player_keys == self._cached_player_keys:
            return
        self._cached_player_keys = player_keys

        self.card_sprites = arcade.SpriteList()
        self.text_sprites = arcade.SpriteList()
        self.damage_overlay_sprites = arcade.SpriteList()
        self.other_player_info_sprites = arcade.SpriteList()

        for i, player in enumerate(others):
            card_top = (i + 1) * self.card_h

            # Recolored card background
            card_texture = self.colorizer.create_recolored_card(
                player.sprite_id, player.color
            )
            if card_texture:
                card_sprite = arcade.Sprite()
                card_sprite.texture = card_texture
                card_sprite.scale = self.zoom
                card_sprite.center_x = (self.card_x + self.card_w / 2) * self.zoom
                card_sprite.center_y = (
                    self.screen_height - (card_top + self.card_h / 2) * self.zoom
                )
                self.card_sprites.append(card_sprite)

            # Player name at card-relative (8, 1) — white
            name_x = (self.card_x + 8) * self.zoom
            name_y = self.screen_height - (card_top + 1) * self.zoom
            name_sprites = self.bitmap_text.create_text_sprites(
                player.name, name_x, name_y
            )
            for sprite in name_sprites:
                self.text_sprites.append(sprite)

            # Dig power at card-relative (26, 11) — red
            dp_x = (self.card_x + 26) * self.zoom
            dp_y = self.screen_height - (card_top + 11) * self.zoom
            dp_sprites = self.bitmap_text.create_text_sprites(
                str(player.get_dig_power()), dp_x, dp_y, color=(255, 0, 0, 255)
            )
            for sprite in dp_sprites:
                self.text_sprites.append(sprite)

            # Money at card-relative (26, 21) — yellow
            money_x = (self.card_x + 26) * self.zoom
            money_y = self.screen_height - (card_top + 21) * self.zoom
            money_sprites = self.bitmap_text.create_text_sprites(
                str(player.money), money_x, money_y, color=(255, 255, 0, 255)
            )
            for sprite in money_sprites:
                self.text_sprites.append(sprite)

            # Update damage overlay on health bar (right edge of card)
            damage_ratio = (100 - player.health) / 100
            if damage_ratio > 0:
                damage_overlay = arcade.Sprite()
                damage_overlay.texture = arcade.Texture(
                    self.black_image, name="damage_overlay"
                )
                damage_overlay.visible = True
                overlay_height = 26 * damage_ratio
                damage_overlay.width = 8 * self.zoom
                damage_overlay.height = overlay_height * self.zoom
                damage_overlay.center_x = (self.card_x + 104) * self.zoom
                damage_overlay.center_y = (
                    self.screen_height - (card_top + 2 + overlay_height / 2) * self.zoom
                )
                self.damage_overlay_sprites.append(damage_overlay)

            # Selected weapon
            icon_texture = self.icon_textures.get(player.selected_type)
            if icon_texture:
                icon_left = self.card_x + self.card_w
                icon_top = card_top
                icon_sprite = arcade.Sprite()
                icon_sprite.texture = icon_texture
                icon_sprite.scale = self.zoom
                icon_sprite.center_x = (icon_left + 15) * self.zoom
                icon_sprite.center_y = self.screen_height - (card_top + 15) * self.zoom
                self.other_player_info_sprites.append(icon_sprite)

    def on_draw(self):
        """Draw all margin sprite lists."""
        self.panel_sprites.draw(pixelated=True)
        self.card_sprites.draw(pixelated=True)
        self.text_sprites.draw(pixelated=True)
        self.damage_overlay_sprites.draw(pixelated=True)
        self.other_player_info_sprites.draw(pixelated=True)
        self.time_bar_sprites.draw(pixelated=True)
