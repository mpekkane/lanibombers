import arcade

from game_engine.entities import Direction, DynamicEntity

SPRITE_SIZE = 10


class PlayerSprite(arcade.Sprite):
    """Extended sprite class for player entities with animation support"""

    def __init__(self, sprite_id: int, colour: tuple, player_textures: dict, transparent_texture, zoom: float, screen_height: int):
        super().__init__()
        self.sprite_id = sprite_id
        self.colour = colour
        self.player_textures = player_textures
        self.transparent_texture = transparent_texture
        self.zoom = zoom
        self.screen_height = screen_height

        # Animation state
        self.current_frame = 1
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
        self.center_x = round((player.x + 0.5) * SPRITE_SIZE) * self.zoom
        self.center_y = self.screen_height - round((player.y + 0.5) * SPRITE_SIZE) * self.zoom

        # Update animation frame if walking or digging
        if player.state in ('walk', 'dig'):
            self.frame_timer += delta_time
            frame_duration = 1.0 / self.frames_per_second
            if self.frame_timer >= frame_duration:
                self.frame_timer -= frame_duration
                self.current_frame = (self.current_frame % 4) + 1
            self.last_direction = player.direction
            self.last_frame = self.current_frame
        else:
            # Idle: keep last frame from walk/dig animation
            self.frame_timer = 0.0

        # Get texture based on state
        frame_to_use = self.current_frame if player.state in ('walk', 'dig') else self.last_frame
        texture = self.player_textures.get(
            (self.sprite_id, player.state, player.direction, frame_to_use),
            self.transparent_texture
        )
        self.texture = texture
