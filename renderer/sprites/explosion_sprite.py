import arcade
from game_engine.clock import Clock
SPRITE_SIZE = 10

# Animation timing (seconds per frame)
FRAME_DURATION = 0.10


class ExplosionSprite(arcade.Sprite):
    """Sprite class for explosion effects with timed animation"""

    def __init__(self, explosion_textures: dict, transparent_texture, zoom: float, screen_height: int):
        super().__init__()
        self.explosion_textures = explosion_textures
        self.transparent_texture = transparent_texture
        self.zoom = zoom
        self.screen_height = screen_height
        self.scale = zoom
        self.texture = transparent_texture

        # Animation state
        self.explosion_type = 0
        self.started_at = 0.0

    def update_from_type(self, explosion_type: int, current_time: float = None):
        """Update sprite based on explosion type from byte array"""
        if current_time is None:
            current_time = Clock.now()

        # New explosion started
        if explosion_type != 0:
            self.explosion_type = explosion_type
            self.started_at = current_time

        # Calculate animation frame based on elapsed time
        elapsed = current_time - self.started_at
        frame_index = int(elapsed / FRAME_DURATION)

        # Animation sequence: explosion -> smoke1 -> smoke2 -> transparent
        if frame_index == 0:
            self.texture = self.explosion_textures[1]
        elif frame_index == 1:
            self.texture = self.explosion_textures[2]
        elif frame_index == 2:
            self.texture = self.explosion_textures[3]
        else:
            self.texture = self.explosion_textures[0]
