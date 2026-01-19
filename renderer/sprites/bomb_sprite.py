import arcade

from game_engine.clock import Clock
from game_engine.entities.bomb import Bomb, BombType

SPRITE_SIZE = 10
NUKE_FRAME_DURATION = 0.1  # seconds per frame for nuke animation


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
        # Track nuke animation state per bomb (by id)
        self.nuke_frames = {}  # bomb_id -> last frame shown (1, 2, or 3)
        self.nuke_last_update = {}  # bomb_id -> last frame change time

    def update_from_bomb(self, bomb: Bomb, current_time: float = None):
        """Update sprite position and texture from bomb entity data"""
        if current_time is None:
            current_time = Clock.now()

        # Update position (grid-aligned, integer coordinates)
        self.center_x = (bomb.x + 0.5) * SPRITE_SIZE * self.zoom
        self.center_y = self.screen_height - (bomb.y + 0.5) * SPRITE_SIZE * self.zoom

        # Get texture based on bomb type and state
        if bomb.bomb_type == BombType.NUKE:
            frame = self._get_nuke_frame(bomb, current_time)
            texture_key = (bomb.bomb_type, 'active', frame)
        elif bomb.state == 'defused':
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

    def _get_nuke_frame(self, bomb: Bomb, current_time: float) -> int:
        """Get the current animation frame for a nuke bomb (cycles 1->2->3->1...)"""
        bomb_id = bomb.id

        # Initialize tracking for new nukes
        if bomb_id not in self.nuke_frames:
            self.nuke_frames[bomb_id] = 1
            self.nuke_last_update[bomb_id] = current_time

        # If defused, return the last frame (frozen)
        if bomb.state == 'defused':
            return self.nuke_frames[bomb_id]

        # Check if it's time to advance the frame
        elapsed = current_time - self.nuke_last_update[bomb_id]
        if elapsed >= NUKE_FRAME_DURATION:
            # Advance frame (1 -> 2 -> 3 -> 1 -> ...)
            current_frame = self.nuke_frames[bomb_id]
            next_frame = (current_frame % 3) + 1
            self.nuke_frames[bomb_id] = next_frame
            self.nuke_last_update[bomb_id] = current_time

        return self.nuke_frames[bomb_id]
