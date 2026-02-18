"""
Entity renderer for lanibombers.
Handles player, monster, pickup, bomb, and explosion rendering.
"""

import os

import arcade

from game_engine.entities import Direction, EntityType
from cfg.bomb_dictionary import BombType
from game_engine.render_state import RenderState

from renderer.sprites import (
    PlayerSprite,
    MonsterSprite,
    PickupSprite,
    BombSprite,
    ExplosionSprite,
)
from cfg.tile_dictionary import (
    TILE_DICTIONARY,
    PLAYER_DEATH_SPRITE,
    MONSTER_DEATH_SPRITE,
    TREASURE_TILES,
    TOOL_TILES,
)

SPRITE_SIZE = 10
SPRITE_CENTER_OFFSET = SPRITE_SIZE // 2


class EntityRenderer:
    """Handles player, monster, pickup, bomb, and explosion rendering."""

    def __init__(
        self, state, transparent_texture, zoom, screen_height, map_height, sprites_path
    ):
        self.zoom = zoom
        self.transparent_texture = transparent_texture
        self.screen_height = screen_height
        self.map_height = map_height
        self.sprites_path = sprites_path

        # Load death textures
        self.blood_texture = arcade.load_texture(
            os.path.join(sprites_path, f"{PLAYER_DEATH_SPRITE}.png")
        )
        self.blood_green_texture = arcade.load_texture(
            os.path.join(sprites_path, f"{MONSTER_DEATH_SPRITE}.png")
        )

        # Load player textures: (sprite_id, state, direction, frame) -> texture
        self.player_textures = {}
        for sprite_id in range(1, 5):
            for direction in Direction:
                for frame in range(1, 5):
                    # Walking sprites
                    sprite_name = f"player{sprite_id}_{direction.value}_{frame}"
                    path = os.path.join(sprites_path, f"{sprite_name}.png")
                    walk_texture = arcade.load_texture(path)
                    self.player_textures[(sprite_id, "walk", direction, frame)] = (
                        walk_texture
                    )

                    # Idle sprites (same as walk, but won't animate)
                    self.player_textures[(sprite_id, "idle", direction, frame)] = (
                        walk_texture
                    )

                    # Digging sprites
                    sprite_name = f"player{sprite_id}_dig_{direction.value}_{frame}"
                    path = os.path.join(sprites_path, f"{sprite_name}.png")
                    self.player_textures[(sprite_id, "dig", direction, frame)] = (
                        arcade.load_texture(path)
                    )

        # Load monster textures: (entity_type, direction, frame) -> texture
        self.monster_textures = {}
        monster_types = [
            (EntityType.SLIME, "slime"),
            (EntityType.FURRYMAN, "furryman"),
            (EntityType.ALIEN, "alien"),
            (EntityType.GRENADEMONSTER, "grenademonster"),
        ]
        for entity_type, sprite_prefix in monster_types:
            for direction in Direction:
                for frame in range(1, 5):
                    sprite_name = f"{sprite_prefix}_{direction.value}_{frame}"
                    path = os.path.join(sprites_path, f"{sprite_name}.png")
                    texture = arcade.load_texture(path)
                    self.monster_textures[(entity_type, direction, frame)] = texture

        # Load grenade projectile texture (single static sprite for all directions/frames)
        grenade_texture = arcade.load_texture(os.path.join(sprites_path, "grenade.png"))
        for direction in Direction:
            for frame in range(1, 5):
                self.monster_textures[(EntityType.GRENADE, direction, frame)] = (
                    grenade_texture
                )

        # Pickup textures: visual_id -> texture (for treasures and tools)
        self.pickup_textures = {}
        pickup_tile_ids = set(TREASURE_TILES.keys()) | set(TOOL_TILES.keys())
        for tile_id in pickup_tile_ids:
            sprite_name = TILE_DICTIONARY.get(tile_id)
            if sprite_name:
                path = os.path.join(sprites_path, f"{sprite_name}.png")
                self.pickup_textures[tile_id] = arcade.load_texture(path)

        # Bomb textures: (bomb_type, state, frame) -> texture
        self.bomb_textures = {}
        self._load_bomb_textures()

        # Explosion textures indexed by frame (0=transparent, 1=explosion, 2=smoke1, 3=smoke2)
        self.explosion_frame_textures = [
            transparent_texture,
            arcade.load_texture(os.path.join(sprites_path, "explosion.png")),
            arcade.load_texture(os.path.join(sprites_path, "smoke1.png")),
            arcade.load_texture(os.path.join(sprites_path, "smoke2.png")),
        ]

        # Player sprite pool
        self.player_sprite_list = arcade.SpriteList()
        self.player_sprite_list.initialize()
        self.player_sprite_list.preload_textures(self.player_textures.values())
        self.player_sprites = []

        for player in state.players:
            sprite = PlayerSprite(
                sprite_id=player.sprite_id,
                color_variant=player.color,
                player_textures=self.player_textures,
                transparent_texture=transparent_texture,
                blood_texture=self.blood_texture,
                zoom=zoom,
                screen_height=screen_height,
                map_height=map_height,
            )
            self.player_sprites.append(sprite)

        self.player_sprite_list.extend(self.player_sprites)

        # Monster sprite pool
        self.monster_sprite_list = arcade.SpriteList()
        self.monster_sprite_list.initialize()
        self.monster_sprite_list.preload_textures(self.monster_textures.values())
        self.monster_sprites = []

        for monster in state.monsters:
            sprite = MonsterSprite(
                entity_type=monster.entity_type,
                monster_textures=self.monster_textures,
                transparent_texture=transparent_texture,
                blood_green_texture=self.blood_green_texture,
                zoom=zoom,
                screen_height=screen_height,
                map_height=map_height,
            )
            self.monster_sprites.append(sprite)

        self.monster_sprite_list.extend(self.monster_sprites)

        # Pickup sprite list (dynamic length)
        self.pickup_sprite_list = arcade.SpriteList()
        self.pickup_sprite_list.initialize()
        self.pickup_sprite_list.preload_textures(self.pickup_textures.values())
        self.pickup_sprites = []

        for pickup in state.pickups:
            sprite = PickupSprite(
                pickup_textures=self.pickup_textures,
                transparent_texture=transparent_texture,
                zoom=zoom,
                screen_height=screen_height,
                map_height=map_height,
            )
            sprite.update_from_pickup(pickup)
            self.pickup_sprites.append(sprite)

        self.pickup_sprite_list.extend(self.pickup_sprites)

        # Bomb sprite list (dynamic length)
        self.bomb_sprite_list = arcade.SpriteList()
        self.bomb_sprite_list.initialize()
        self.bomb_sprite_list.preload_textures(self.bomb_textures.values())
        self.bomb_sprites = []

        for bomb in state.bombs:
            sprite = BombSprite(
                bomb_textures=self.bomb_textures,
                transparent_texture=transparent_texture,
                zoom=zoom,
                screen_height=screen_height,
                map_height=map_height,
            )
            sprite.update_from_bomb(bomb)
            self.bomb_sprites.append(sprite)

        self.bomb_sprite_list.extend(self.bomb_sprites)

        # Explosion sprite list - one per map tile at world positions
        self.explosion_sprite_list = arcade.SpriteList()
        self.explosion_sprite_list.initialize()
        self.explosion_sprite_list.preload_textures(self.explosion_frame_textures)
        self.explosion_sprites = []

        for y in range(state.height):
            world_y = (
                state.height - 1 - y
            ) * SPRITE_SIZE * zoom + SPRITE_CENTER_OFFSET * zoom
            for x in range(state.width):
                world_x = x * SPRITE_SIZE * zoom + SPRITE_CENTER_OFFSET * zoom
                sprite = ExplosionSprite(
                    explosion_textures=self.explosion_frame_textures,
                    transparent_texture=transparent_texture,
                    zoom=zoom,
                    screen_height=screen_height,
                )
                sprite.center_x = world_x
                sprite.center_y = world_y
                sprite.scale = zoom
                sprite.texture = transparent_texture
                self.explosion_sprites.append(sprite)
                self.explosion_sprite_list.append(sprite)

    def on_update(
        self,
        state: RenderState,
        current_time: float,
        delta_time: float,
        view_start_x: int,
        view_end_x: int,
        view_start_y: int,
        view_end_y: int,
    ):
        """Update entity sprites."""
        # Update pickups (dynamic list)
        pickup_count = len(state.pickups)

        while len(self.pickup_sprites) < pickup_count:
            sprite = PickupSprite(
                pickup_textures=self.pickup_textures,
                transparent_texture=self.transparent_texture,
                zoom=self.zoom,
                screen_height=self.screen_height,
                map_height=self.map_height,
            )
            self.pickup_sprites.append(sprite)
            self.pickup_sprite_list.append(sprite)

        while len(self.pickup_sprites) > pickup_count:
            sprite = self.pickup_sprites.pop()
            self.pickup_sprite_list.remove(sprite)

        for i, pickup in enumerate(state.pickups):
            self.pickup_sprites[i].update_from_pickup(pickup)

        # Update bombs (dynamic list)
        bomb_count = len(state.bombs)

        while len(self.bomb_sprites) < bomb_count:
            sprite = BombSprite(
                bomb_textures=self.bomb_textures,
                transparent_texture=self.transparent_texture,
                zoom=self.zoom,
                screen_height=self.screen_height,
                map_height=self.map_height,
            )
            self.bomb_sprites.append(sprite)
            self.bomb_sprite_list.append(sprite)

        while len(self.bomb_sprites) > bomb_count:
            sprite = self.bomb_sprites.pop()
            self.bomb_sprite_list.remove(sprite)

        for i, bomb in enumerate(state.bombs):
            self.bomb_sprites[i].update_from_bomb(bomb, current_time)

        # Update visible explosions
        for y in range(view_start_y, view_end_y):
            for x in range(view_start_x, view_end_x):
                sprite_idx = y * state.width + x
                explosion_type = state.explosions[y, x]
                self.explosion_sprites[sprite_idx].update_from_type(
                    explosion_type, current_time
                )

        # Update monsters (dynamic list)
        monster_count = len(state.monsters)

        while len(self.monster_sprites) < monster_count:
            sprite = MonsterSprite(
                entity_type=EntityType.SLIME,
                monster_textures=self.monster_textures,
                transparent_texture=self.transparent_texture,
                blood_green_texture=self.blood_green_texture,
                zoom=self.zoom,
                screen_height=self.screen_height,
                map_height=self.map_height,
            )
            self.monster_sprites.append(sprite)
            self.monster_sprite_list.append(sprite)

        while len(self.monster_sprites) > monster_count:
            sprite = self.monster_sprites.pop()
            self.monster_sprite_list.remove(sprite)

        for i, monster in enumerate(state.monsters):
            self.monster_sprites[i].entity_type = monster.entity_type
            self.monster_sprites[i].update_from_entity(monster, delta_time)

        # Update players
        for i, player in enumerate(state.players):
            self.player_sprites[i].update_from_entity(player, delta_time)

    def _load_bomb_textures(self):
        """Load all bomb textures into self.bomb_textures dict."""

        # Helper to load animated bomb with 3 frames
        def load_animated(bomb_type, base_name, has_defused=True):
            for frame in range(1, 4):
                path = os.path.join(self.sprites_path, f"{base_name}{frame}.png")
                self.bomb_textures[(bomb_type, "active", frame)] = arcade.load_texture(
                    path
                )
            if has_defused:
                path = os.path.join(self.sprites_path, f"{base_name}_defused.png")
                self.bomb_textures[(bomb_type, "defused", 0)] = arcade.load_texture(
                    path
                )

        # Helper to load single-frame bomb (same texture for all frames)
        def load_static(bomb_type, sprite_name, defused_name=None):
            path = os.path.join(self.sprites_path, f"{sprite_name}.png")
            texture = arcade.load_texture(path)
            for frame in range(1, 4):
                self.bomb_textures[(bomb_type, "active", frame)] = texture
            if defused_name:
                defused_path = os.path.join(self.sprites_path, f"{defused_name}.png")
                self.bomb_textures[(bomb_type, "defused", 0)] = arcade.load_texture(
                    defused_path
                )
            else:
                self.bomb_textures[(bomb_type, "defused", 0)] = texture

        # Animated bombs (3 frames + defused)
        load_animated(BombType.BIG_BOMB, "bigbomb")
        load_animated(BombType.SMALL_BOMB, "smallbomb")
        load_animated(BombType.DYNAMITE, "dynamite")
        load_animated(BombType.NUKE, "nuke", has_defused=False)

        # Static bombs (single frame)
        load_static(BombType.C4, "c4_bomb")
        load_static(BombType.URETHANE, "urethane")
        load_static(BombType.LANDMINE, "landmine")
        load_static(BombType.SMALL_CROSS_BOMB, "smallcrucifix")
        load_static(BombType.BIG_CROSS_BOMB, "bigcrucifix")
        load_static(BombType.GRASSHOPPER, "grasshopper")
        load_static(BombType.SMALL_REMOTE, "smallremote_player1")
        load_static(BombType.BIG_REMOTE, "bigremote_player1")
        # Flame barrel has 2-frame animation like nuke
        for frame in [1, 2]:
            path = os.path.join(self.sprites_path, f"smallbarrel{frame}.png")
            self.bomb_textures[(BombType.FLAME_BARREL, "active", frame)] = (
                arcade.load_texture(path)
            )
        # Defused state
        defused_path = os.path.join(self.sprites_path, "smallbarrel_defused.png")
        self.bomb_textures[(BombType.FLAME_BARREL, "defused", 0)] = arcade.load_texture(
            defused_path
        )

        # Cracker barrel (static, no defused state since it's triggered by damage)
        load_static(BombType.CRACKER_BARREL, "crackerbarrel")

        # Digger bomb (static)
        load_static(BombType.DIGGER_BOMB, "diggerbomb")

        # GRASSHOPPER_HOP uses same texture as GRASSHOPPER
        for frame in range(1, 4):
            self.bomb_textures[(BombType.GRASSHOPPER_HOP, "active", frame)] = (
                self.bomb_textures[(BombType.GRASSHOPPER, "active", frame)]
            )
        self.bomb_textures[(BombType.GRASSHOPPER_HOP, "defused", 0)] = (
            self.bomb_textures[(BombType.GRASSHOPPER, "defused", 0)]
        )
