from __future__ import annotations
import numpy as np
from typing import Any, Optional, List, Dict, Tuple, TYPE_CHECKING, Union, Callable
from itertools import chain
import random
from enum import Enum
from copy import deepcopy
from game_engine.clock import Clock
from game_engine.entities.tile import Tile, TileType
from game_engine.entities.dynamic_entity import DynamicEntity, Direction, EntityType
from game_engine.engine_utils import flood_fill, get_solid_map
from cfg.tile_dictionary import (
    C4_TILE_ID,
    URETHANE_TILE_ID,
    EMPTY_TILE_ID,
    SECURITY_DOOR_ID,
)
from game_engine.entities.player import Player
from game_engine.entities.pickup import Pickup, PickupType
from game_engine.entities.bomb import Bomb, BombType
from cfg.bomb_dictionary import GRASSHOPPER_CONFIG, FLAME_BARREL_CONFIG, CRACKER_BARREL_CONFIG, FLAMETHROWER_CONFIG, FIRE_EXTINGUISHER_CONFIG, GRENADE_CONFIG
from game_engine.entities.explosion import (
    ExplosionType,
    SmallExplosion,
    MediumExplosion,
    LargeExplosion,
    NukeExplosion,
    SmallCrossExplosion,
    BigCrossExplosion,
    DirectedFlameExplosion,
)
from game_engine.events.event import Event, ResolveFlags, MoveEvent

# Map ExplosionType to explosion instances
EXPLOSION_MAP = {
    ExplosionType.SMALL: SmallExplosion(),
    ExplosionType.MEDIUM: MediumExplosion(),
    ExplosionType.LARGE: LargeExplosion(),
    ExplosionType.NUKE: NukeExplosion(),
    ExplosionType.SMALL_CROSS: SmallCrossExplosion(),
    ExplosionType.BIG_CROSS: BigCrossExplosion(),
}
from game_engine.events.event_resolver import EventResolver
from game_engine.render_state import RenderState
from game_engine.entities import Tool, Treasure
from game_engine.utils import xy_to_tile, clamp
from game_engine.sound_engine import SoundEngine

if TYPE_CHECKING:
    from game_engine.map_loader import MapData


class SwitchState(Enum):
    ON = "on"
    OFF = "off"

    def switch(self) -> SwitchState:
        if self == SwitchState.OFF:
            return SwitchState.ON
        else:
            return SwitchState.OFF


class GameEngine:
    """Main game engine containing the tile grid and event system."""

    def __init__(self, width: int = 64, height: int = 45, headless: bool = False):
        self.width = width
        self.height = height
        self.tiles: list[list[Tile]] = [
            [Tile() for _ in range(width)] for _ in range(height)
        ]
        self.explosions = np.zeros((self.height, self.width), dtype=np.uint8)
        self.players: List[Player] = []
        self.player_map: Dict[str, int] = {}
        self.monsters: List[DynamicEntity] = []
        self.pickups: List[List[Optional[Pickup]]] = [
            [None for _ in range(width)] for _ in range(height)
        ]
        self.bombs: List[Bomb] = []
        self.explosion_times: Dict[Tuple[int, int], Tuple[float, int]] = (
            {}
        )  # (x, y) -> (start_time, type)
        self.event_resolver = EventResolver(resolve=self.resolve)
        # FIXME: placeholder
        self.starting_poses = [
            (1, 1),
            # (60, 5),  # debug: close to teleport
            # (10, 20),  # debug: close to boulder
            (1, width - 1),
            (height - 1, 1),
            (height - 1, width - 1),
        ]
        self.prev_time = -1
        self.sounds_enabled = not headless
        if self.sounds_enabled:
            self.sounds = SoundEngine(music_volume=0.5, fx_volume=1.0)
        self.teleports: List[Tuple[int, int]] = []
        self.switch_state = SwitchState.OFF
        self.security_doors: List[Tuple[int, int, Tile]] = []
        self.state_callback: Optional[Callable[[RenderState], None]] = None

    def set_render_callback(
        self, callback: Callable[[RenderState], None]
    ) -> None:
        self.state_callback = callback

    def load_map(self, map_data: MapData) -> None:
        """Load map data into the engine."""
        self.width = map_data.width
        self.height = map_data.height
        self.tiles = map_data.tiles
        self.monsters = map_data.monsters
        for pickup in list(map_data.tools):
            self.pickups[pickup.y][pickup.x] = pickup
        for pickup in list(map_data.treasures):
            self.pickups[pickup.y][pickup.x] = pickup

        # list teleports, here we add also weapon teleports
        for y, tiles in enumerate(self.tiles):
            for x, tile in enumerate(tiles):
                if tile.is_teleport():
                    self.teleports.append((x, y))

        # list security tiles
        for y, tiles in enumerate(self.tiles):
            for x, tile in enumerate(tiles):
                if tile.is_security_door():
                    self.security_doors.append((x, y, tile))

    def start(self) -> None:
        """Start the game engine and event processing."""
        if self.sounds_enabled:
            self.sounds.game()
        self.event_resolver.start()

    def stop(self) -> None:
        """Stop the game engine and event processing."""
        if self.sounds_enabled:
            self.sounds.stop_all()
        self.event_resolver.stop()

    def create_player(self, name: str) -> None:
        num_players = len(self.players)
        start_pose = self.starting_poses[num_players]
        player = Player(
            x=start_pose[0] + 0.5,
            y=start_pose[1] + 0.5,
            direction=Direction.RIGHT,
            name=name,
            sprite_id=num_players + 1,
            state="idle",
            speed=3,
            fight_power=20,
        )
        return self._create_player(player)

    def _create_players(self, players: List[Player]) -> None:
        """Create players"""
        for player in players:
            self._create_player(player)

    def _create_player(self, player: Player) -> None:
        """Create players"""
        self.players.append(player)
        idx = len(self.players) - 1
        self.player_map[player.name] = idx

    def get_player_by_name(self, name: str) -> Optional[Player]:
        idx = self.player_map.get(name)
        if idx is not None:
            return self.get_player_by_id(idx)
        else:
            return None

    def get_player_by_id(self, idx: int) -> Optional[Player]:
        if idx >= 0 and idx < len(self.players):
            return self.players[idx]
        else:
            return None

    def get_tile(self, x: int, y: int) -> Optional[Tile]:
        """Get tile at grid position."""
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.tiles[y][x]
        return None

    def set_tile(self, x: int, y: int, tile: Tile) -> bool:
        """Set tile at grid position. Returns True if successful."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.tiles[y][x] = tile
            return True
        return False

    def plant_bomb(self, bomb: Bomb) -> None:
        """Plant a bomb in the game and schedule its explosion event."""
        self.bombs.append(bomb)

        if bomb.bomb_type.is_timed():
            explosion_event = Event(
                trigger_at=bomb.placed_at + bomb.fuse_duration,
                target=bomb,
                event_type="explode",
            )
            self.event_resolver.schedule_event(explosion_event)
        elif bomb.bomb_type == BombType.FLAMETHROWER:
            # Flamethrower fires immediately
            explosion_event = Event(
                trigger_at=Clock.now(),
                target=bomb,
                event_type="explode",
            )
            self.event_resolver.schedule_event(explosion_event)
        elif bomb.bomb_type == BombType.FIRE_EXTINGUISHER:
            # Fire extinguisher fires immediately
            explosion_event = Event(
                trigger_at=Clock.now(),
                target=bomb,
                event_type="explode",
            )
            self.event_resolver.schedule_event(explosion_event)
        elif bomb.bomb_type == BombType.CLONE:
            # Clone fires immediately
            explosion_event = Event(
                trigger_at=Clock.now(),
                target=bomb,
                event_type="explode",
            )
            self.event_resolver.schedule_event(explosion_event)
        elif bomb.bomb_type == BombType.GRENADE:
            # Grenade fires immediately
            explosion_event = Event(
                trigger_at=Clock.now(),
                target=bomb,
                event_type="explode",
            )
            self.event_resolver.schedule_event(explosion_event)

    def detonate_remotes(self, player: Player) -> None:
        for bomb in self.bombs:
            if bomb.bomb_type in (BombType.SMALL_REMOTE, BombType.BIG_REMOTE) and bomb.owner_id == player.id:
                explosion_event = Event(
                    trigger_at=Clock.now() + 0,
                    target=bomb,
                    event_type="explode",
                )
                self.event_resolver.schedule_event(explosion_event)

    def _trigger_bombs_in_area(self, source_bomb: Bomb, affected_area: np.ndarray, delay: float = 1.0 / 60.0) -> None:
        """
        Trigger all bombs in the affected area to explode after a delay.

        Args:
            source_bomb: The bomb causing the explosion (will be skipped)
            affected_area: Boolean or numeric numpy array where truthy values indicate affected tiles
            delay: Time delay before triggered bombs explode (default 1/60s)
        """
        for other_bomb in self.bombs:
            if other_bomb is source_bomb:
                continue
            if affected_area[other_bomb.y, other_bomb.x]:
                self.event_resolver.reschedule_events_by_target(other_bomb, "explode", delay)

    def clear_entity_move_events(self, player: DynamicEntity) -> None:
        """Clear all move actions by the player"""
        # Note: We assume that this is not needed. However, in the original game,
        # the move is sometimes rounded up, i.e., you gain speed by turning.
        # Up for discussion.
        # First resolve undergoing events, i.e., stop to the place the entity
        # has already made progress to
        # self.event_resolver.resolve_object_events(
        #     player.id, "move", ResolveFlags(spawn=False)
        # )
        # Safety: clear all movement events from the queue
        self.event_resolver.cancel_object_events(player.id, "move")
        self.event_resolver.cancel_object_events(player.id, "push")

    def clear_entity_dig_events(self, player: DynamicEntity) -> None:
        """Clear all dig actions by the player"""
        # First resolve undergoing events, i.e., apply the dig damage
        # already done
        self.event_resolver.resolve_object_events(
            player.id, "dig", ResolveFlags(spawn=False)
        )
        # Safety: clear all dig events from the queue
        self.event_resolver.cancel_object_events(player.id, "dig")

    def change_entity_direction(self, player: DynamicEntity) -> None:
        """Create and handle player movement events"""
        if player.state == "dead":
            return

        # Cancel dig events, this needs to be done first as the resolve
        # init a move event
        self.clear_entity_dig_events(player)
        # When changing dir, all previous movement events are cleared
        self.clear_entity_move_events(player)

        # print("Centralize")
        # print(player.x, player.y)
        self.centralize_position(player)
        # print(player.x, player.y)

        # collision check
        next_tile = self.get_neighbor_tile(player)
        if next_tile.solid:
            self.collision_check(player, next_tile)
        else:
            # Create new movement
            self.move_entity(player)

    def collision_check(self, entity: DynamicEntity, next_tile: Tile):
        # dig
        if next_tile.diggable:
            self.dig(entity)
        # interact
        elif next_tile.interactable:
            if next_tile.is_switch():
                self.use_switch()
            elif next_tile.is_boulder():
                # TODO: can you push boulders on top of items?
                tile_behind_push = self.get_neighbor_tile(entity, range=2)
                if not tile_behind_push.solid:
                    self.move_entity(entity, push=True)
        # if nothing can be done: stop
        else:
            entity.state = "idle"

    def move_entity(self, entity: DynamicEntity, push: bool = False):
        """Main movement generator function from dynamic entities"""
        if entity.state == "dead":
            return

        # When walking, calculate distance
        if entity.state == "walk":
            if entity.direction == Direction.RIGHT:
                decimal = entity.x - (int)(entity.x)
                if decimal > 0.5:
                    d = 1 - decimal
                else:
                    d = 0.5 - decimal
            elif entity.direction == Direction.LEFT:
                decimal = entity.x - (int)(entity.x)
                if decimal < 0.5:
                    d = decimal
                else:
                    d = decimal - 0.5
            elif entity.direction == Direction.UP:
                decimal = entity.y - (int)(entity.y)
                if decimal < 0.5:
                    d = decimal
                else:
                    d = decimal - 0.5
            elif entity.direction == Direction.DOWN:
                decimal = entity.y - (int)(entity.y)
                if decimal > 0.5:
                    d = 1 - decimal
                else:
                    d = 0.5 - decimal
            else:
                return

            # print(f"d {d}")

            # this is the boundary condition
            if d == 0:
                d = 0.5

            # this is the required time to cross the thershold
            speed_modifier = 1
            if push:
                speed_modifier = entity.push_power()
            dt = d / (entity.speed * speed_modifier)
            # HACK: since the movement is calculated with actual time, add some bonus
            # time to cross the threshold properly, to make tile transition logic
            # nicee
            dt += 0.01

            event = "move" if not push else "push"

            movement_event = MoveEvent(
                trigger_at=Clock.now() + dt,
                target=entity,
                event_type=event,
                created_at=Clock.now(),
                created_by=entity.id,
                direction=str(entity.direction.value),
            )
            self.event_resolver.schedule_event(movement_event)

    def dig(self, entity: DynamicEntity) -> None:
        self.event_resolver.cancel_object_events(entity.id, "move")
        dig_event = Event(
            trigger_at=Clock.now() + 0.1,
            target=entity,
            event_type="dig",
            created_at=Clock.now(),
            created_by=entity.id,
        )
        self.event_resolver.schedule_event(dig_event)

    def schedule_event(self, event: Event) -> None:
        """Schedule an event for later execution."""
        self.event_resolver.schedule_event(event)

    def cancel_event(self, event_id) -> bool:
        """Cancel a scheduled event."""
        return self.event_resolver.cancel_event(event_id)

    def resolve(self, target: Any, event: Event, flags: ResolveFlags) -> None:
        """
        Called when an event fires. Handles event resolution.

        Args:
            target: The object associated with the event (e.g., Bomb, Pickup)
            event: The event that triggered
        """
        # Handle bomb explosion
        if isinstance(target, Bomb) and event.event_type == "explode":
            self.resolve_bomb(target, event, flags)
        elif isinstance(target, Player) and event.event_type == "move":
            self.resolve_movement(target, event, flags)
        elif isinstance(target, Player) and event.event_type == "push":
            self.resolve_push(target, event, flags)
        elif isinstance(target, Player) and event.event_type == "dig":
            self.resolve_dig(target, event, flags)
        elif isinstance(target, DynamicEntity) and target.entity_type == EntityType.GRENADE and event.event_type == "move":
            self.resolve_grenade_movement(target, event, flags)

        # send renderstate
        if self.state_callback:
            self.state_callback(self.get_render_state())

    def resolve_bomb(self, target: Bomb, event: Event, flags: ResolveFlags) -> None:
        """Resolve explosion events"""
        # C4 has special behavior - flood fill with c4 tiles instead of exploding
        if target.bomb_type == BombType.C4:
            self._resolve_c4(target)
            return

        # URETHANE has special behavior - flood fill with urethane tiles (no chain reaction)
        if target.bomb_type == BombType.URETHANE:
            self._resolve_urethane(target)
            return

        # FLAME_BARREL flood fills and damages all non-solid tiles in range
        if target.bomb_type == BombType.FLAME_BARREL:
            self._resolve_flame_barrel(target)
            return

        # CRACKER_BARREL does flood fill damage + scattered medium explosions
        if target.bomb_type == BombType.CRACKER_BARREL:
            self._resolve_cracker_barrel(target)
            return

        # DIGGER_BOMB only damages bedrock tiles using large explosion radius
        if target.bomb_type == BombType.DIGGER_BOMB:
            self._resolve_digger_bomb(target)
            return

        # BIOSLIME places a bioslime tile at bomb location
        if target.bomb_type == BombType.BIOSLIME:
            self._resolve_bioslime(target)
            return

        # METAL_PLATE places a concrete tile at bomb location
        if target.bomb_type == BombType.METAL_PLATE:
            self._resolve_metal_plate(target)
            return

        # FLAMETHROWER does a 90-degree cone flame in player's facing direction
        if target.bomb_type == BombType.FLAMETHROWER:
            self._resolve_flamethrower(target)
            return

        # FIRE_EXTINGUISHER defuses bombs in a 90-degree cone
        if target.bomb_type == BombType.FIRE_EXTINGUISHER:
            self._resolve_fire_extinguisher(target)
            return

        # CLONE spawns a decoy entity
        if target.bomb_type == BombType.CLONE:
            self._resolve_clone(target)
            return

        # TELEPORT places a tunnel tile at bomb location
        if target.bomb_type == BombType.TELEPORT:
            self._resolve_teleport(target)
            return

        # GRENADE is a thrown projectile
        if target.bomb_type == BombType.GRENADE:
            self._resolve_grenade(target)
            return

        # Grasshopper bombs have special spawning behavior after explosion
        is_grasshopper = target.bomb_type in (BombType.GRASSHOPPER, BombType.GRASSHOPPER_HOP)

        # Get explosion instance and calculate damage pattern
        explosion = EXPLOSION_MAP[target.explosion_type]
        solids = np.zeros((self.height, self.width), dtype=bool)
        damage_array = explosion.calculate_damage(target.x, target.y, solids)

        # Track C4 tiles that will be hit for chain reaction
        c4_tiles_hit = []

        # Apply damage to tiles
        for y in range(self.height):
            for x in range(self.width):
                dmg = damage_array[y, x]
                if dmg > 0:
                    tile = self.get_tile(x, y)
                    if tile:
                        # Check if this is a C4 tile before damaging
                        if tile.tile_type == TileType.C4:
                            c4_tiles_hit.append((x, y))
                        tile.take_damage(dmg, target.explosion_type)
                        if not tile.solid:
                            self.explosions[y, x] = 1

        # Schedule chain explosions for C4 tiles that were hit (1/60s delay)
        chain_delay = 1.0 / 60.0
        current_time = Clock.now()
        for cx, cy in c4_tiles_hit:
            c4_bomb = Bomb(
                x=cx,
                y=cy,
                bomb_type=BombType.C4_TILE,
                placed_at=current_time,
                owner_id=target.owner_id,
            )
            explosion_event = Event(
                trigger_at=current_time + chain_delay,
                target=c4_bomb,
                event_type="explode",
            )
            self.event_resolver.schedule_event(explosion_event)

        # Trigger any bombs in the damage area
        self._trigger_bombs_in_area(target, damage_array)

        # Grasshopper: spawn next hop if we haven't reached 13 explosions
        if is_grasshopper:
            self._spawn_grasshopper_hop(target, current_time)

        if target.bomb_type == BombType.C4_TILE:
            pass  # No sound for C4 tile chain explosions
        elif target.bomb_type == BombType.SMALL_BOMB:
            if self.sounds_enabled:
                self.sounds.small_explosion()
        elif target.explosion_type == ExplosionType.SMALL:
            if self.sounds_enabled:
                self.sounds.small_explosion()
        else:
            if self.sounds_enabled:
                self.sounds.explosion()

        # Remove bomb from list
        if target in self.bombs:
            self.bombs.remove(target)

    def _resolve_c4(self, bomb: Bomb) -> None:
        """Resolve C4 bomb - flood fill empty tiles with c4_tiles."""
        # Get solid map (True = solid, we need inverse for flood fill which expects True = walkable)
        solid_map = get_solid_map(self.tiles, self.height, self.width)
        walkable_map = ~solid_map  # Invert: True = empty/walkable

        # Flood fill from bomb position, max 8 tiles away
        fill_mask = flood_fill(walkable_map, (bomb.y, bomb.x), max_dist=8)

        # Convert all filled empty tiles to c4_tiles
        for y in range(self.height):
            for x in range(self.width):
                if fill_mask[y, x]:
                    tile = self.get_tile(x, y)
                    if tile and tile.tile_type == TileType.EMPTY:
                        self.set_tile(x, y, Tile.create_c4())
        if self.sounds_enabled:
            self.sounds.urethane()

        # Remove bomb from list
        if bomb in self.bombs:
            self.bombs.remove(bomb)

    def _resolve_urethane(self, bomb: Bomb) -> None:
        """Resolve URETHANE bomb - flood fill empty tiles with urethane tiles (no chain reaction)."""
        # Get solid map (True = solid, we need inverse for flood fill which expects True = walkable)
        solid_map = get_solid_map(self.tiles, self.height, self.width)
        walkable_map = ~solid_map  # Invert: True = empty/walkable

        # Flood fill from bomb position, max 8 tiles away
        fill_mask = flood_fill(walkable_map, (bomb.y, bomb.x), max_dist=8)

        # Convert all filled empty tiles to urethane tiles
        for y in range(self.height):
            for x in range(self.width):
                if fill_mask[y, x]:
                    tile = self.get_tile(x, y)
                    if tile and tile.tile_type == TileType.EMPTY:
                        self.set_tile(x, y, Tile.create_urethane())

        if self.sounds_enabled:
            self.sounds.urethane()

        # Remove bomb from list
        if bomb in self.bombs:
            self.bombs.remove(bomb)

    def _resolve_bioslime(self, bomb: Bomb) -> None:
        """Resolve BIOSLIME bomb - place a bioslime tile at bomb location."""
        tile = self.get_tile(bomb.x, bomb.y)
        if tile and tile.tile_type == TileType.EMPTY:
            self.set_tile(bomb.x, bomb.y, Tile.create_bioslime())

        if self.sounds_enabled:
            self.sounds.urethane()  # FIXME: Use urethane sound for now

        # Remove bomb from list
        if bomb in self.bombs:
            self.bombs.remove(bomb)

    def _resolve_metal_plate(self, bomb: Bomb) -> None:
        """Resolve METAL_PLATE bomb - place a concrete tile at bomb location."""
        tile = self.get_tile(bomb.x, bomb.y)
        if tile and tile.tile_type == TileType.EMPTY:
            self.set_tile(bomb.x, bomb.y, Tile.create_concrete())

        if self.sounds_enabled:
            self.sounds.urethane()  # FIXME: Use urethane sound for now

        # Remove bomb from list
        if bomb in self.bombs:
            self.bombs.remove(bomb)

    def _resolve_flamethrower(self, bomb: Bomb) -> None:
        """Resolve FLAMETHROWER - 90-degree cone flame in player's facing direction."""
        cfg = FLAMETHROWER_CONFIG
        direction = bomb.direction if bomb.direction else Direction.DOWN

        # Create directed flame explosion
        directed_flame = DirectedFlameExplosion(
            direction=direction,
            max_distance=cfg['max_distance'],
            base_damage=cfg['damage']
        )

        # Get walkable map
        solid_map = get_solid_map(self.tiles, self.height, self.width)
        walkable_map = ~solid_map

        # Calculate affected area
        final_mask = directed_flame.calculate_area(bomb.x, bomb.y, walkable_map, flood_fill)

        # Apply damage to tiles in the final mask
        for y in range(self.height):
            for x in range(self.width):
                if final_mask[y, x]:
                    tile = self.get_tile(x, y)
                    if tile:
                        tile.take_damage(cfg['damage'])
                        # Mark explosion visual
                        if not tile.solid:
                            self.explosions[y, x] = 1

        # Trigger any bombs in the affected area
        self._trigger_bombs_in_area(bomb, final_mask)

        if self.sounds_enabled:
            self.sounds.explosion()

        # Remove bomb from list
        if bomb in self.bombs:
            self.bombs.remove(bomb)

    def _resolve_fire_extinguisher(self, bomb: Bomb) -> None:
        """Resolve FIRE_EXTINGUISHER - 90-degree cone that defuses bombs."""
        cfg = FIRE_EXTINGUISHER_CONFIG
        direction = bomb.direction if bomb.direction else Direction.DOWN

        # Create directed flame explosion (reuse the cone calculation)
        directed_flame = DirectedFlameExplosion(
            direction=direction,
            max_distance=cfg['max_distance']
        )

        # Get walkable map
        solid_map = get_solid_map(self.tiles, self.height, self.width)
        walkable_map = ~solid_map

        # Calculate affected area
        final_mask = directed_flame.calculate_area(bomb.x, bomb.y, walkable_map, flood_fill)

        # Defuse any bombs in the final mask area
        defuse_delay = 24 * 60 * 60  # 24 hours in seconds
        for other_bomb in self.bombs:
            if other_bomb is bomb:
                continue  # Skip the fire extinguisher itself
            if final_mask[other_bomb.y, other_bomb.x]:
                other_bomb.state = 'defused'
                # Reschedule explosion to 24 hours from now
                self.event_resolver.reschedule_events_by_target(other_bomb, "explode", defuse_delay)

        # Remove fire extinguisher from list
        if bomb in self.bombs:
            self.bombs.remove(bomb)

    def _resolve_clone(self, bomb: Bomb) -> None:
        """Resolve CLONE bomb - spawns a decoy entity."""
        # TODO: Implement decoy entity spawning
        pass

        # Remove bomb from list
        if bomb in self.bombs:
            self.bombs.remove(bomb)

    def _resolve_teleport(self, bomb: Bomb) -> None:
        """Resolve TELEPORT bomb - places a tunnel tile at bomb location."""
        tile = self.get_tile(bomb.x, bomb.y)
        if tile and tile.tile_type == TileType.EMPTY:
            self.set_tile(bomb.x, bomb.y, Tile.create_tunnel())
            # Add to teleport list
            self.teleports.append((bomb.x, bomb.y))

        if self.sounds_enabled:
            self.sounds.urethane()  # FIXME: Use urethane sound for now

        # Remove bomb from list
        if bomb in self.bombs:
            self.bombs.remove(bomb)

    def _resolve_grenade(self, bomb: Bomb) -> None:
        """Resolve GRENADE - create a grenade projectile entity."""
        cfg = GRENADE_CONFIG
        direction = bomb.direction if bomb.direction else Direction.DOWN

        # Create grenade entity at bomb position
        grenade = DynamicEntity.create_grenade(
            x=bomb.x + 0.5,  # Center in tile
            y=bomb.y + 0.5,
            direction=direction,
            owner_id=bomb.owner_id,
            speed=cfg['speed'],
        )

        # Add grenade to monsters list (for rendering and movement)
        self.monsters.append(grenade)

        # Start the grenade moving
        self.move_entity(grenade)

        # Remove bomb from list
        if bomb in self.bombs:
            self.bombs.remove(bomb)

    def resolve_grenade_movement(self, grenade: DynamicEntity, event: MoveEvent, flags: ResolveFlags) -> None:
        """Resolve grenade movement - moves until hitting wall or player."""
        # Calculate actual distance based on elapsed time
        current_time = Clock.now()
        dt = current_time - event.created_at
        d = dt * grenade.speed

        # Move in stored direction
        dir = Direction(event.direction)
        if dir == Direction.RIGHT:
            grenade.x += d
        elif dir == Direction.LEFT:
            grenade.x -= d
        elif dir == Direction.UP:
            grenade.y -= d
        elif dir == Direction.DOWN:
            grenade.y += d

        self.round_position(grenade)

        # Get current and next tile positions
        gx, gy = xy_to_tile(grenade.x, grenade.y)

        # Check for teleport at current position
        current_tile = self.get_tile(gx, gy)
        if current_tile and current_tile.is_teleport():
            # Find available teleports (excluding current)
            available = [(tx, ty) for tx, ty in self.teleports if tx != gx or ty != gy]
            if available:
                dest = random.choice(available)
                grenade.x = dest[0] + 0.5
                grenade.y = dest[1] + 0.5
                gx, gy = dest[0], dest[1]

        # Calculate next tile based on direction
        nx, ny = gx, gy
        if dir == Direction.RIGHT:
            nx += 1
        elif dir == Direction.LEFT:
            nx -= 1
        elif dir == Direction.UP:
            ny -= 1
        elif dir == Direction.DOWN:
            ny += 1

        # Check for player in next tile
        for player in self.players:
            px, py = xy_to_tile(player.x, player.y)
            if px == nx and py == ny and player.state != "dead":
                # Explode in the tile with the player
                self._explode_grenade(grenade, nx, ny)
                return

        # Check if next tile is solid
        next_tile = self.get_tile(nx, ny)
        if next_tile and next_tile.solid:
            # Explode in current (non-solid) tile
            self._explode_grenade(grenade, gx, gy)
            return

        # Continue moving
        if flags.spawn:
            self.move_entity(grenade)

    def _explode_grenade(self, grenade: DynamicEntity, x: int, y: int) -> None:
        """Trigger a small explosion at the given position and remove grenade."""
        # Create a small bomb at explosion location
        explosion_bomb = Bomb(
            x=x,
            y=y,
            bomb_type=BombType.SMALL_BOMB,
            placed_at=Clock.now(),
            owner_id=grenade.owner_id,
            fuse_override=0.0,  # Instant
        )

        # Schedule immediate explosion
        explosion_event = Event(
            trigger_at=Clock.now(),
            target=explosion_bomb,
            event_type="explode",
        )
        self.event_resolver.schedule_event(explosion_event)

        # Remove grenade from monsters list
        if grenade in self.monsters:
            self.monsters.remove(grenade)

    def _resolve_flame_barrel(self, bomb: Bomb) -> None:
        """Resolve FLAME_BARREL bomb - flood fill and damage all non-solid tiles in range."""
        cfg = FLAME_BARREL_CONFIG

        # Get solid map (True = solid, we need inverse for flood fill which expects True = walkable)
        solid_map = get_solid_map(self.tiles, self.height, self.width)
        walkable_map = ~solid_map  # Invert: True = empty/walkable

        # Flood fill from bomb position
        fill_mask = flood_fill(walkable_map, (bomb.y, bomb.x), max_dist=cfg['max_distance'])

        # Apply damage to all tiles in the flood fill area
        damage = cfg['damage']
        for y in range(self.height):
            for x in range(self.width):
                if fill_mask[y, x]:
                    tile = self.get_tile(x, y)
                    if tile:
                        tile.take_damage(damage)
                        # Mark explosion visual
                        if not tile.solid:
                            self.explosions[y, x] = 1

        # Trigger any bombs in the affected area
        self._trigger_bombs_in_area(bomb, fill_mask)

        if self.sounds_enabled:
            self.sounds.explosion()

        # Remove bomb from list
        if bomb in self.bombs:
            self.bombs.remove(bomb)

    def _resolve_cracker_barrel(self, bomb: Bomb) -> None:
        """Resolve CRACKER_BARREL bomb - flood fill damage + scattered medium explosions."""
        cfg = CRACKER_BARREL_CONFIG
        current_time = Clock.now()

        # Get solid map for flood fill
        solid_map = get_solid_map(self.tiles, self.height, self.width)
        walkable_map = ~solid_map

        # Flood fill from bomb position (like flame barrel but shorter range)
        fill_mask = flood_fill(walkable_map, (bomb.y, bomb.x), max_dist=cfg['flood_fill_distance'])

        # Apply damage to all tiles in the flood fill area
        damage = cfg['flood_fill_damage']
        for y in range(self.height):
            for x in range(self.width):
                if fill_mask[y, x]:
                    tile = self.get_tile(x, y)
                    if tile:
                        tile.take_damage(damage)
                        if not tile.solid:
                            self.explosions[y, x] = 1

        # Trigger any bombs in the flood fill area
        self._trigger_bombs_in_area(bomb, fill_mask)

        # Schedule scattered medium explosions
        scatter_count = cfg['scatter_explosions']
        scatter_dist = cfg['scatter_distance']
        interval = cfg['scatter_interval']

        for i in range(scatter_count):
            # Random position up to scatter_dist away
            offset_x = random.randint(-scatter_dist, scatter_dist)
            offset_y = random.randint(-scatter_dist, scatter_dist)
            new_x = bomb.x + offset_x
            new_y = bomb.y + offset_y

            # Clamp to game area with 1-tile border
            new_x = max(1, min(self.width - 2, new_x))
            new_y = max(1, min(self.height - 2, new_y))

            # Create a medium explosion bomb (using C4_TILE type for instant explosion)
            scatter_bomb = Bomb(
                x=new_x,
                y=new_y,
                bomb_type=BombType.C4_TILE,  # Reuse C4_TILE for medium instant explosion
                placed_at=current_time,
                owner_id=bomb.owner_id,
            )

            # Schedule at 1/60 second intervals
            trigger_time = current_time + (i * interval)
            explosion_event = Event(
                trigger_at=trigger_time,
                target=scatter_bomb,
                event_type="explode",
            )
            self.event_resolver.schedule_event(explosion_event)

        if self.sounds_enabled:
            self.sounds.explosion()

        # Remove bomb from list
        if bomb in self.bombs:
            self.bombs.remove(bomb)

    def _resolve_digger_bomb(self, bomb: Bomb) -> None:
        """Resolve DIGGER_BOMB - only damages bedrock tiles using large explosion radius."""
        # Use LARGE explosion pattern
        explosion = EXPLOSION_MAP[ExplosionType.LARGE]
        solids = np.zeros((self.height, self.width), dtype=bool)
        damage_array = explosion.calculate_damage(bomb.x, bomb.y, solids)

        # Apply damage only to bedrock tiles
        for y in range(self.height):
            for x in range(self.width):
                dmg = damage_array[y, x]
                if dmg > 0:
                    tile = self.get_tile(x, y)
                    if tile and tile.tile_type == TileType.BEDROCK:
                        tile.take_damage(dmg)
                        # Show explosion visual on the tile
                        self.explosions[y, x] = 1

        if self.sounds_enabled:
            self.sounds.explosion()

        # Remove bomb from list
        if bomb in self.bombs:
            self.bombs.remove(bomb)

    def _spawn_grasshopper_hop(self, source_bomb: Bomb, current_time: float) -> None:
        """
        Spawn the next grasshopper hop bomb after an explosion.
        Configuration is loaded from GRASSHOPPER_CONFIG in bomb_dictionary.py.
        """
        cfg = GRASSHOPPER_CONFIG

        # Count this explosion
        new_hop_count = source_bomb.hop_count + 1

        # Stop after max hops
        if new_hop_count >= cfg['max_hops']:
            return

        # Calculate new position: random offset up to max_hop_distance in each direction
        max_dist = cfg['max_hop_distance']
        offset_x = random.randint(-max_dist, max_dist)
        offset_y = random.randint(-max_dist, max_dist)
        new_x = source_bomb.x + offset_x
        new_y = source_bomb.y + offset_y

        # Clamp to game area with 1-tile border
        new_x = max(1, min(self.width - 2, new_x))
        new_y = max(1, min(self.height - 2, new_y))

        # Determine explosion type for next hop
        if source_bomb.bomb_type == BombType.GRASSHOPPER:
            # First hop after initial bomb: random from first_hop_explosions
            next_explosion = random.choice(cfg['first_hop_explosions'])
        else:
            # Subsequent hops: shrink/stay/grow based on configured chances
            current_explosion = source_bomb.explosion_type
            explosion_order = cfg['explosion_order']
            roll = random.random()

            if roll < cfg['shrink_chance']:
                # Shrink: move down in explosion_order, stay at minimum
                try:
                    idx = explosion_order.index(current_explosion)
                    next_explosion = explosion_order[max(0, idx - 1)]
                except ValueError:
                    next_explosion = explosion_order[0]
            elif roll < cfg['shrink_chance'] + cfg['stay_chance']:
                # Stay same
                next_explosion = current_explosion
            else:
                # Grow: move up in explosion_order, stay at maximum
                try:
                    idx = explosion_order.index(current_explosion)
                    next_explosion = explosion_order[min(len(explosion_order) - 1, idx + 1)]
                except ValueError:
                    next_explosion = explosion_order[-1]

        # Random fuse between configured min and max
        fuse_time = random.uniform(cfg['fuse_min'], cfg['fuse_max'])

        # Create the hop bomb
        hop_bomb = Bomb(
            x=new_x,
            y=new_y,
            bomb_type=BombType.GRASSHOPPER_HOP,
            placed_at=current_time,
            owner_id=source_bomb.owner_id,
            fuse_override=fuse_time,
            explosion_override=next_explosion,
            hop_count=new_hop_count,
        )

        # Add to bombs list and schedule explosion
        self.bombs.append(hop_bomb)
        explosion_event = Event(
            trigger_at=current_time + fuse_time,
            target=hop_bomb,
            event_type="explode",
        )
        self.event_resolver.schedule_event(explosion_event)

    def resolve_push(
        self, target: DynamicEntity, event: MoveEvent, flags: ResolveFlags
    ) -> None:
        player_x, player_y = xy_to_tile(target.x, target.y)
        target_x, target_y = player_x, player_y
        new_x, new_y = target_x, target_y
        if target.direction == Direction.RIGHT:
            target_x = player_x + 1
            new_x = target_x + 1
        elif target.direction == Direction.LEFT:
            target_x = player_x - 1
            new_x = target_x - 1
        elif target.direction == Direction.UP:
            target_y = player_y - 1
            new_y = target_y - 1
        elif target.direction == Direction.DOWN:
            target_y = player_y + 1
            new_y = target_y + 1
        else:
            raise ValueError("Invalid move direction")

        # TODO: do boulders crush items?
        self.tiles[new_y][new_x] = deepcopy(self.tiles[target_y][target_x])
        self.set_tile(target_x, target_y, Tile.create_empty())
        self.resolve_movement(target, event, flags)

    def resolve_movement(
        self, target: DynamicEntity, event: MoveEvent, flags: ResolveFlags
    ) -> None:
        """
        Resolve move events.

        There's a lot of printing, as there's a lot to debug, also in future
        """
        if target.state == "dead":
            return

        # because events might have been cleared, i.e., triggered at times
        # other than planned, calculate actual traveled distance
        current_time = Clock.now()
        dt = current_time - event.created_at
        speedmod = 1
        if event.event_type == "push":
            speedmod = target.push_power()
        d = dt * target.speed * speedmod

        # move target to the stored direction, not the current one!
        # this is due to the fact that when changing direction, the target (pointer)
        # has different direction than in the move command
        dir = Direction(event.direction)
        moved: float

        # print("-" * 20)
        # print(f"from: {target.x}, {target.y}")
        if dir == Direction.RIGHT:
            target.x += d
            moved = target.x
        elif dir == Direction.LEFT:
            target.x -= d
            moved = target.x
        elif dir == Direction.UP:
            target.y -= d
            moved = target.y
        elif dir == Direction.DOWN:
            target.y += d
            moved = target.y
        else:
            raise ValueError("Invalid move direction")
        # print(f"to  : {target.x}, {target.y}")
        self.round_position(target)
        # print(f"cntr: {target.x}, {target.y}")
        # print(f"ms: {self.width} {self.height}")

        # target.x, target.y = self.clamp_to_map_size(target.x, target.y)
        # print(target.x, target.y)

        tolerance = 0.05
        blocked = False
        px, py = xy_to_tile(target.x, target.y)
        # enter tile
        if (
            abs(moved - int(moved)) < tolerance
            or abs(moved - int(moved) - 1) < tolerance
        ):
            # print(f"enter tile   {px} {py}")
            self.entity_enter_tile(target)
        # middle
        if abs(moved - int(moved) - 0.5) < tolerance:
            # print(f"enter center {px} {py}")
            self.entity_reach_tile_center(target)

            # check the neighboring tiles
            # wall
            # interact
            next_tile = self.get_neighbor_tile(target)
            # print(next_tile)
            if next_tile.solid:
                blocked = True
                px, py = xy_to_tile(target.x, target.y)
                self.collision_check(target, next_tile)

        if flags.spawn and not blocked:
            self.move_entity(target)

        # fight monsters
        self.fight(target)

    def centralize_position(self, entity: DynamicEntity) -> None:
        if entity.direction in (Direction.UP, Direction.DOWN):
            entity.x = round(entity.x - 0.5) + 0.5
        if entity.direction in (Direction.RIGHT, Direction.LEFT):
            entity.y = round(entity.y - 0.5) + 0.5

    def round_position(self, entity: DynamicEntity) -> None:
        entity.x = int(round(entity.x * 2)) / 2
        entity.y = int(round(entity.y * 2)) / 2

    def resolve_dig(self, target: Player, event: Event, flags: ResolveFlags) -> None:
        if target.state == "dead":
            return

        target_tile = self.get_neighbor_tile(target)
        dig_power = target.get_dig_power()
        target_tile.take_damage(dig_power)
        if self.sounds_enabled:
            self.sounds.dig()
        # print("DIG!")
        # print(target_tile)

        if target_tile.health > 0:
            self.dig(target)
        else:
            self.move_entity(target)

    def get_neighbor_tile(self, entity: DynamicEntity, range: int = 1) -> Tile:
        px, py = xy_to_tile(entity.x, entity.y)
        nx, ny = px, py
        dir = Direction(entity.direction)
        if dir == Direction.RIGHT:
            nx += range
        elif dir == Direction.LEFT:
            nx -= range
        elif dir == Direction.UP:
            ny -= range
        elif dir == Direction.DOWN:
            ny += range
        else:
            print(entity)
            raise ValueError("Invalid move direction")

        nx, ny = self.clamp_to_map_size(nx, ny)
        next_tile: Tile = self.tiles[ny][nx]

        # print("-" * 20)
        # print("pp:", entity.x, entity.y)
        # print("px:", px, py)
        # print("nx:", nx, ny)
        # print(next_tile)

        return next_tile

    # TODO: tile entering logic
    def entity_enter_tile(self, target: DynamicEntity) -> None:
        """Events that happen when entity enters a tile"""
        # check for mines
        px, py = xy_to_tile(target.x, target.y)
        for bomb in self.bombs:
            if bomb.bomb_type == BombType.LANDMINE:
                if bomb.x == px and bomb.y == py:
                    explosion_event = Event(
                        trigger_at=Clock.now() + 0,
                        target=bomb,
                        event_type="explode",
                    )
                    self.event_resolver.schedule_event(explosion_event)

    # TODO: tile center reached logic
    def entity_reach_tile_center(self, player: Player) -> None:
        """Events that happen when entity enters a tile center"""
        # pickup items
        px, py = xy_to_tile(player.x, player.y)
        pickup = self.pickups[py][px]
        if pickup:
            if pickup.pickup_type == PickupType.TOOL:
                assert isinstance(pickup, Tool)
                player.pickup_tool(pickup)
            else:
                assert isinstance(pickup, Treasure)
                player.pickup_treasure(pickup)
                # TODO:
                if self.sounds_enabled:
                    self.sounds.treasure()
            self.pickups[py][px] = None

        # teleport
        tile = self.tiles[py][px]
        if tile.is_teleport():
            available: List[Tuple[int, int]] = []
            for teleport in self.teleports:
                if teleport[0] == px and teleport[1] == py:
                    continue
                else:
                    available.append(teleport)
            if available:
                val = random.choice(available)
                player.x = val[0] + 0.5
                player.y = val[1] + 0.5

    def use_switch(self) -> None:
        if self.switch_state == SwitchState.OFF:
            for x, y, _ in self.security_doors:
                self.set_tile(x, y, Tile.create_empty())
        else:
            for x, y, tile in self.security_doors:
                self.set_tile(x, y, tile)

        self.switch_state = self.switch_state.switch()

    def fight(self, agent: DynamicEntity) -> None:
        entities = self.players + self.monsters
        px, py = xy_to_tile(agent.x, agent.y)
        for other in entities:
            ox, oy = (int)(other.x), (int)(other.y)
            if ox == px and oy == py and other.state != "dead" and other.id != agent.id:
                pass
                # other.take_damage(agent.fight_power)
                # agent.take_damage(other.fight_power)
                # print("FIGHT!")
                # print(f"Agent deals {agent.fight_power} damage")
                # print(f"Enemy deals {other.fight_power} damage")
                # print(f"Agent health {agent.health}")
                # print(f"Enemy health {other.health}")
        if agent.state == "dead":
            if self.sounds_enabled:
                self.sounds.die()

    def update_player_state(self):
        """OBSOLETE: used for tick-rendering"""
        if self.prev_time < 0:
            self.prev_time = Clock.now()
        elapsed = Clock.now() - self.prev_time

        for player in self.players:
            dt = elapsed * player.speed  # blocks per second
            dx = 0
            dy = 0
            if player.state == "walk":
                if player.direction == Direction.RIGHT:
                    dx = dt
                elif player.direction == Direction.LEFT:
                    dx = -dt
                elif player.direction == Direction.UP:
                    dy = -dt
                elif player.direction == Direction.DOWN:
                    dy = dt

            player.x += dx
            player.y += dy
        self.prev_time = Clock.now()

    def get_render_state(self) -> RenderState:
        """Build and return a RenderState for the renderer."""

        # Build tilemap as 2D numpy array
        tilemap = np.array(
            [[tile.visual_id for tile in row] for row in self.tiles], dtype=np.uint8
        )

        explosions_copy = self.explosions.copy()

        self.cleanup_render_state()

        return RenderState(
            width=self.width,
            height=self.height,
            tilemap=tilemap,
            explosions=explosions_copy,
            players=self.players,
            monsters=self.monsters,
            pickups=list(
                filter(lambda x: x is not None, chain.from_iterable(self.pickups))
            ),
            bombs=self.bombs,
        )

    def cleanup_render_state(self):
        # clean explosions array (0=none)
        self.explosions.fill(0)

    def clamp_to_map_size(
        self, x: Optional[Union[int, float]], y: Optional[Union[int, float]]
    ) -> Tuple[Union[int, float], Union[int, float]]:
        if not x:
            x = 0
        if not y:
            y = 0
        return self.clamp_x(x), self.clamp_y(y)

    def clamp_x(self, x: Union[int, float]):
        return clamp(x, 0, self.width)

    def clamp_y(self, y: Union[int, float]):
        return clamp(y, 0, self.height)
