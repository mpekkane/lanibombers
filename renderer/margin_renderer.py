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
        self.bitmap_text = BitmapText(
            os.path.join(SPRITES_PATH, "font.png"), zoom=zoom
        )
        self.colorizer = PlayerColorizer(SPRITES_PATH)

        # Sprite lists
        self.panel_sprites = arcade.SpriteList()
        self.card_sprites = arcade.SpriteList()
        self.text_sprites = arcade.SpriteList()

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
            icon_panel.center_x = (self.card_x + self.card_w + self.icon_size / 2) * zoom
            icon_panel.center_y = screen_height - (slot_y + self.icon_size / 2) * zoom
            self.panel_sprites.append(icon_panel)

        # Change detection cache: list of per-player tuples
        self._cached_player_keys: list = []

    def on_update(self, players: List[Player]):
        """Update enemy cards if player data changed."""
        others = [p for p in players if p.name != self.client_player_name]

        # Build cache key per player
        player_keys = [
            (p.name, p.sprite_id, p.color, p.money, p.get_dig_power())
            for p in others
        ]
        if player_keys == self._cached_player_keys:
            return
        self._cached_player_keys = player_keys

        self.card_sprites = arcade.SpriteList()
        self.text_sprites = arcade.SpriteList()

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
                card_sprite.center_y = self.screen_height - (card_top + self.card_h / 2) * self.zoom
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

    def on_draw(self):
        """Draw all margin sprite lists."""
        self.panel_sprites.draw(pixelated=True)
        self.card_sprites.draw(pixelated=True)
        self.text_sprites.draw(pixelated=True)
