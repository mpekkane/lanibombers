import arcade

from game_engine.entities import Direction, DynamicEntity

SPRITE_SIZE = 10


class PlayerSprite(arcade.Sprite):
    """Extended sprite class for player entities with animation support"""

    def __init__(self, sprite_id: int, color_variant: tuple, player_textures: dict, transparent_texture, blood_texture, zoom: float, screen_height: int):
        super().__init__()
        self.sprite_id = sprite_id
        self.color_variant = color_variant
        self.player_textures = player_textures
        self.transparent_texture = transparent_texture
        self.blood_texture = blood_texture
        self.zoom = zoom
        self.screen_height = screen_height

        # Animation state - ping-pong pattern: 1,2,3,4,3,2,1,2,3,4...
        self.frame_sequence = [1, 2, 3, 4, 3, 2]
        self.frame_index = 0
        self.frame_timer = 0.0
        self.frames_per_second = 4  # Animation speed

        # Previous state for idle frame persistence
        self.last_direction = Direction.DOWN
        self.last_frame = 1

        self.scale = zoom
        self.texture = transparent_texture

    def update_from_entity(self, player: DynamicEntity, delta_time: float):
        """Update sprite position, texture and animation from player entity data"""
        # Update position (rounded to pixel grid before zoom)
        self.center_x = round((player.x) * SPRITE_SIZE) * self.zoom
        self.center_y = self.screen_height - round((player.y) * SPRITE_SIZE) * self.zoom

        # Handle dead state
        if player.state == 'dead':
            self.texture = self.blood_texture
            return

        # Update animation frame if walking or digging (ping-pong: 1,2,3,4,3,2...)
        if player.state in ('walk', 'dig'):
            self.frame_timer += delta_time
            frame_duration = 1.0 / self.frames_per_second
            if self.frame_timer >= frame_duration:
                self.frame_timer -= frame_duration
                self.frame_index = (self.frame_index + 1) % len(self.frame_sequence)
            self.last_direction = player.direction
            self.last_frame = self.frame_sequence[self.frame_index]
        else:
            # Idle: keep last frame from walk/dig animation
            self.frame_timer = 0.0

        # Get texture based on state
        current_frame = self.frame_sequence[self.frame_index]
        frame_to_use = current_frame if player.state in ('walk', 'dig') else self.last_frame
        texture = self.player_textures.get(
            (self.sprite_id, player.state, player.direction, frame_to_use),
            self.transparent_texture
        )
        self.texture = texture
