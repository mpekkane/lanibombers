import arcade

from game_engine.entities.pickup import Pickup

SPRITE_SIZE = 10


class PickupSprite(arcade.Sprite):
    """Sprite class for pickup entities (treasures, tools)"""

    def __init__(self, pickup_textures: dict, transparent_texture, zoom: float, screen_height: int, y_offset: float = 0):
        super().__init__()
        self.pickup_textures = pickup_textures
        self.transparent_texture = transparent_texture
        self.zoom = zoom
        self.screen_height = screen_height
        self.y_offset = y_offset
        self.scale = zoom
        self.texture = transparent_texture
        self.visual_id = 0

    def update_from_pickup(self, pickup: Pickup):
        """Update sprite position and texture from pickup entity data"""
        # Update position (grid-aligned, integer coordinates)
        self.center_x = (pickup.x + 0.5) * SPRITE_SIZE * self.zoom
        self.center_y = self.screen_height - self.y_offset - (pickup.y + 0.5) * SPRITE_SIZE * self.zoom

        # Update texture based on visual_id
        if pickup.visual_id != self.visual_id:
            self.visual_id = pickup.visual_id
            self.texture = self.pickup_textures.get(pickup.visual_id, self.transparent_texture)
