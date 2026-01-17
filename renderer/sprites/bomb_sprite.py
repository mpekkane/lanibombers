import arcade

from game_engine.clock import Clock
from game_engine.entities.bomb import Bomb, BombType

SPRITE_SIZE = 10


class BombSprite(arcade.Sprite):
    """Sprite class for bomb entities with fuse-based animation"""

    def __init__(self, bomb_textures: dict, transparent_texture, zoom: float, screen_height: int):
        super().__init__()
        self.bomb_textures = bomb_textures
        self.transparent_texture = transparent_texture
        self.zoom = zoom
        self.screen_height = screen_height
        self.scale = zoom
        self.texture = transparent_texture

    def update_from_bomb(self, bomb: Bomb, current_time: float = None):
        """Update sprite position and texture from bomb entity data"""
        if current_time is None:
            current_time = Clock.now()

        # Update position (grid-aligned, integer coordinates)
        self.center_x = (bomb.x + 0.5) * SPRITE_SIZE * self.zoom
        self.center_y = self.screen_height - (bomb.y + 0.5) * SPRITE_SIZE * self.zoom

        # Get texture based on bomb type and state
        if bomb.state == 'defused':
            texture_key = (bomb.bomb_type, 'defused', 0)
        else:
            # Active bomb - select frame based on fuse percentage
            fuse_pct = bomb.get_fuse_percentage(current_time)
            # First 33% (100%-67%) = frame 1, next 33% (67%-33%) = frame 2, last 33% (33%-0%) = frame 3
            if fuse_pct > 0.67:
                frame = 1
            elif fuse_pct > 0.33:
                frame = 2
            else:
                frame = 3
            texture_key = (bomb.bomb_type, 'active', frame)

        self.texture = self.bomb_textures.get(texture_key, self.transparent_texture)
