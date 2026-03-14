from __future__ import annotations
import sys
import numpy as np
from typing import Any, Optional, List, Dict, Tuple, TYPE_CHECKING, Union, Callable
from itertools import chain
import random
from enum import Enum
from copy import deepcopy
from game_engine.agent_state import Action
from game_engine.clock import Clock
from game_engine.entities.tile import Tile, TileType
from game_engine.entities.dynamic_entity import DynamicEntity, Direction, EntityType
from game_engine.engine_utils import flood_fill, get_solid_map, get_bioslime_map
from cfg.tile_dictionary import (
    C4_TILE_ID,
    URETHANE_TILE_ID,
    EMPTY_TILE_ID,
    SECURITY_DOOR_ID,
)
from game_engine.entities.player import Player
from game_engine.entities.pickup import Pickup, PickupType
from game_engine.entities.bomb import Bomb, BombType
from cfg.bomb_dictionary import (
    GRASSHOPPER_CONFIG,
    FLAME_BARREL_CONFIG,
    CRACKER_BARREL_CONFIG,
    FLAMETHROWER_CONFIG,
    FIRE_EXTINGUISHER_CONFIG,
    GRENADE_CONFIG,
)
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
from game_engine.input_queue import InputCommand, InputQueue
from game_engine.monster_controller import MonsterController
from game_engine.render_state import ExplosionVisual, RenderState, SoundType
from game_engine.entities import Tool, Treasure
from game_engine.utils import xy_to_tile, clamp

if TYPE_CHECKING:
    from game_engine.map_loader import MapData


class _BioslimeTick:
    """Sentinel target for bioslime tick events."""

    pass


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

    def __init__(self, width: int = 64, height: int = 45):
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
        self.input_queue = InputQueue()
        # FIXME this has to be set by the map so you don't start in illegal position
        offset = 0
        self.starting_poses = [
            (offset, offset),
            (offset, width - offset),
            (height - offset, offset),
            (height - offset, width - offset),
        ]
        self.prev_time = -1
        self.pending_sounds: List[int] = []
        self.teleports: List[Tuple[int, int]] = []
        self.switch_state = SwitchState.OFF
        self.security_doors: List[Tuple[int, int, Tile]] = []
        self.state_callback: Optional[Callable[[RenderState], None]] = None
        self._external_state_callback: Optional[Callable[[RenderState], None]] = None
        self.monster_controllers: List[MonsterController] = []
        self._bioslime_tick_active = False
        self._bioslime_sentinel = _BioslimeTick()

    def set_render_callback(self, callback: Callable[[RenderState], None]) -> None:
        self._external_state_callback = callback
        self.state_callback = self._dispatch_render_state

    def _dispatch_render_state(self, state: RenderState) -> None:
        if self._external_state_callback:
            self._external_state_callback(state)
        for controller in self.monster_controllers:
            controller.push_state(state)

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
        self.input_queue.set_notify(self.event_resolver.notify)
        self.event_resolver.pre_process = self.process_inputs
        self.event_resolver.start()
        self._start_monster_controllers()

    def process_inputs(self) -> None:
        """Drain the input queue and apply commands. Called from the resolver thread."""
        for cmd in self.input_queue.drain():
            if cmd.entity.state == "dead":
                continue
            if cmd.action.is_move():
                self.change_entity_direction(cmd.entity)
            elif cmd.action == Action.FIRE:
                if cmd.bomb is not None:
                    self.plant_bomb(cmd.bomb)
            elif cmd.action == Action.REMOTE:
                if isinstance(cmd.entity, Player):
                    self.detonate_remotes(cmd.entity)

    def _start_monster_controllers(self) -> None:
        for monster in self.monsters:
            if monster.entity_type == EntityType.GRENADE:
                continue  # projectiles, not AI
            controller = MonsterController(monster, self)
            self.monster_controllers.append(controller)
            controller.start()
        # Ensure dispatch is wired up even if no external callback was set
        if self.monster_controllers and self.state_callback is None:
            self.state_callback = self._dispatch_render_state

    def stop(self) -> None:
        """Stop the game engine and event processing."""
        for controller in self.monster_controllers:
            controller.stop()
        self.monster_controllers.clear()
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
                trigger_at=bomb.placed_at,
                target=bomb,
                event_type="explode",
            )
            self.event_resolver.schedule_event(explosion_event)
        elif bomb.bomb_type == BombType.FIRE_EXTINGUISHER:
            # Fire extinguisher fires immediately
            explosion_event = Event(
                trigger_at=bomb.placed_at,
                target=bomb,
                event_type="explode",
            )
            self.event_resolver.schedule_event(explosion_event)
        elif bomb.bomb_type == BombType.CLONE:
            # Clone fires immediately
            explosion_event = Event(
                trigger_at=bomb.placed_at,
                target=bomb,
                event_type="explode",
            )
            self.event_resolver.schedule_event(explosion_event)
        elif bomb.bomb_type == BombType.GRENADE:
            # Grenade fires immediately
            explosion_event = Event(
                trigger_at=bomb.placed_at,
                target=bomb,
                event_type="explode",
            )
            self.event_resolver.schedule_event(explosion_event)

        # send renderstate
        if self.state_callback:
            self.state_callback(self.get_render_state(bomb.placed_at))

    def detonate_remotes(self, player: Player) -> None:
        now = Clock.now()
        for bomb in self.bombs:
            if (
                bomb.bomb_type in (BombType.SMALL_REMOTE, BombType.BIG_REMOTE)
                and bomb.owner_id == player.id
            ):
                explosion_event = Event(
                    trigger_at=now,
                    target=bomb,
                    event_type="explode",
                )
                self.event_resolver.schedule_event(explosion_event)

    def _trigger_bombs_in_area(
        self,
        source_bomb: Bomb,
        affected_area: np.ndarray,
        delay: float = 1.0 / 60.0,
        now: float = 0.0,
    ) -> None:
        """
        Trigger all bombs in the affected area to explode after a delay.

        Args:
            source_bomb: The bomb causing the explosion (will be skipped)
            affected_area: Boolean or numeric numpy array where truthy values indicate affected tiles
            delay: Time delay before triggered bombs explode (default 1/60s)
            now: Base timestamp for scheduling (0 = use Clock.now())
        """
        for other_bomb in self.bombs:
            if other_bomb is source_bomb:
                continue
            if affected_area[other_bomb.y, other_bomb.x]:
                self.event_resolver.reschedule_events_by_target(
                    other_bomb, "explode", delay, now
                )

    def _damage_entities_in_area(self, damage_array: np.ndarray) -> None:
        """Damage players, monsters, and pickups in the affected area.

        Args:
            damage_array: Numeric numpy array where values indicate damage per tile.
        """
        for player in self.players:
            if player.state == "dead":
                continue
            px, py = xy_to_tile(player.x, player.y)
            dmg = damage_array[py, px]
            if dmg > 0:
                player.take_damage(int(dmg))

        for monster in self.monsters:
            if monster.state == "dead":
                continue
            mx, my = xy_to_tile(monster.x, monster.y)
            if 0 <= mx < self.width and 0 <= my < self.height:
                dmg = damage_array[my, mx]
                if dmg > 0:
                    monster.take_damage(int(dmg))

        for y in range(len(self.pickups)):
            for x in range(len(self.pickups[y])):
                if self.pickups[y][x] is not None and damage_array[y, x] > 0:
                    self.pickups[y][x] = None

    def clear_entity_move_events(
        self, player: DynamicEntity, resolve_time: float = 0.0
    ) -> None:
        """Clear all move actions by the player"""
        # Note: We assume that this is not needed. However, in the original game,
        # the move is sometimes rounded up, i.e., you gain speed by turning.
        # Up for discussion.
        # First resolve undergoing events, i.e., stop to the place the entity
        # has already made progress to
        self.event_resolver.resolve_object_events(
            player.id, "move", ResolveFlags(spawn=False, resolve_time=resolve_time)
        )
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

        # Capture wall-clock time once for premature event resolution.
        # This is the single place where Clock.now() is used for movement
        # resolution, making future lag compensation straightforward.
        now = Clock.now()

        # Cancel dig events, this needs to be done first as the resolve
        # init a move event
        self.clear_entity_dig_events(player)
        # When changing dir, all previous movement events are cleared
        self.clear_entity_move_events(player, now)

        # print("Centralize")
        # print(player.x, player.y)
        self.centralize_position(player)
        # print(player.x, player.y)

        # collision check
        in_bounds, next_tile = self.get_neighbor_tile(player)
        if in_bounds:
            if next_tile.solid:
                self.collision_check(player, next_tile, now)
            elif not self.try_push_bomb(player):
                # Create new movement (no bomb blocked us)
                self.move_entity(player, now=now)

        # send renderstate
        if self.state_callback:
            self.state_callback(self.get_render_state(now))

    def collision_check(self, entity: DynamicEntity, next_tile: Tile, now: float = 0.0):
        # dig
        if next_tile.diggable:
            entity.state = "dig"
            self.dig(entity, now)
        # interact
        elif next_tile.interactable:
            if next_tile.is_switch():
                self.use_switch()
            elif next_tile.is_boulder():
                # TODO: can you push boulders on top of items?
                in_bounds, tile_behind_push = self.get_neighbor_tile(entity, range=2)
                if in_bounds and not tile_behind_push.solid:
                    # Check no bomb blocking the destination
                    _, _, nx, ny = self.get_entity_movement_vector(entity)
                    bomb_blocked = any(b.x == nx and b.y == ny for b in self.bombs)
                    if not bomb_blocked:
                        self.move_entity(entity, push=True, now=now)
                    else:
                        entity.state = "idle"
                else:
                    entity.state = "idle"
        # if nothing can be done: stop
        else:
            entity.state = "idle"

    def try_push_bomb(self, entity: DynamicEntity) -> bool:
        """Try to push a bomb in the next tile ahead of entity.
        Returns True if movement is blocked (bomb couldn't be pushed)."""
        target_x, target_y, _, _ = self.get_entity_movement_vector(entity)
        for bomb in self.bombs:
            if (
                bomb.x == target_x
                and bomb.y == target_y
                and not (
                    bomb.bomb_type == BombType.LANDMINE
                    or bomb.bomb_type == BombType.CRACKER_BARREL
                )
            ):
                # Check destination tile for the bomb
                _, _, new_x, new_y = self.get_entity_movement_vector(entity)
                dest_tile = self.get_tile(new_x, new_y)
                if dest_tile is not None and not dest_tile.solid:
                    # Check no other bomb at destination
                    bomb_blocked = any(
                        b.x == new_x and b.y == new_y for b in self.bombs
                    )
                    if not bomb_blocked:
                        bomb.x = new_x
                        bomb.y = new_y
                        cx, cy = self.clamp_to_map_size(bomb.x, bomb.y)
                        bomb.x, bomb.y = int(cx), int(cy)
                        return False  # pushed successfully, entity can continue
                # Can't push — block movement
                entity.state = "idle"
                return True
        return False  # no bomb ahead, entity can continue

    def move_entity(self, entity: DynamicEntity, push: bool = False, now: float = 0.0):
        """Main movement generator function from dynamic entities"""
        if entity.state == "dead":
            return

        # When walking, calculate distance to the next half-tile boundary
        # (0.0 or 0.5 fractional) in the movement direction.
        # d is always positive; direction is stored separately in the event.
        if entity.state == "walk":
            if entity.direction in (Direction.RIGHT, Direction.LEFT):
                frac = entity.x % 1.0
            elif entity.direction in (Direction.DOWN, Direction.UP):
                frac = entity.y % 1.0
            else:
                return

            if entity.direction in (Direction.RIGHT, Direction.DOWN):
                # Moving toward higher values: next stop is 0.5 or 1.0
                if frac < 0.5:
                    d = 0.5 - frac
                else:
                    d = 1.0 - frac
            else:
                # Moving toward lower values: next stop is 0.0 or 0.5
                if frac > 0.5:
                    d = frac - 0.5
                else:
                    d = frac

            if d < 1e-9:
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

            caller = sys._getframe(1).f_code.co_name
            movement_event = MoveEvent(
                trigger_at=now + dt,
                target=entity,
                event_type=event,
                created_at=now,
                created_by=entity.id,
                direction=str(entity.direction.value),
                source=f"move_entity<-{caller}",
            )
            self.event_resolver.schedule_event(movement_event)

    def dig(self, entity: DynamicEntity, now: float = 0.0) -> None:
        self.event_resolver.cancel_object_events(entity.id, "move")
        dig_event = Event(
            trigger_at=now + 0.1,
            target=entity,
            event_type="dig",
            created_at=now,
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
        elif isinstance(target, DynamicEntity) and event.event_type == "move":
            if target.entity_type == EntityType.GRENADE:
                self.resolve_grenade_movement(target, event, flags)
            else:
                self.resolve_movement(target, event, flags)
        elif isinstance(target, DynamicEntity) and event.event_type == "push":
            self.resolve_push(target, event, flags)
        elif isinstance(target, DynamicEntity) and event.event_type == "dig":
            self.resolve_dig(target, event, flags)
        elif isinstance(target, _BioslimeTick) and event.event_type == "bioslime_tick":
            self._bioslime_tick(event.trigger_at)

        # send renderstate — use event's logical time for consistent interpolation
        if self.state_callback:
            self.state_callback(self.get_render_state(event.trigger_at))

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
            self._resolve_flame_barrel(target, now=event.trigger_at)
            return

        # CRACKER_BARREL does flood fill damage + scattered medium explosions
        if target.bomb_type == BombType.CRACKER_BARREL:
            self._resolve_cracker_barrel(target, event.trigger_at)
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
            self._resolve_flamethrower(target, now=event.trigger_at)
            return

        # FIRE_EXTINGUISHER defuses bombs in a 90-degree cone
        if target.bomb_type == BombType.FIRE_EXTINGUISHER:
            self._resolve_fire_extinguisher(target, now=event.trigger_at)
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
            self._resolve_grenade(target, now=event.trigger_at)
            return

        # Grasshopper bombs have special spawning behavior after explosion
        is_grasshopper = target.bomb_type in (
            BombType.GRASSHOPPER,
            BombType.GRASSHOPPER_HOP,
        )

        # Get explosion instance and calculate damage pattern
        explosion = EXPLOSION_MAP[target.explosion_type]
        solids = np.zeros((self.height, self.width), dtype=bool)
        damage_array = explosion.calculate_damage(target.x, target.y, solids)

        # Choose visual code for the explosion array
        visual = (
            ExplosionVisual.NUKE
            if target.explosion_type == ExplosionType.NUKE
            else ExplosionVisual.EXPLOSION
        )

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
                            self.explosions[y, x] = visual

        # Schedule chain explosions for C4 tiles that were hit (1/60s delay)
        chain_delay = 1.0 / 60.0
        current_time = event.trigger_at
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
        self._trigger_bombs_in_area(target, damage_array, now=event.trigger_at)

        # Damage players, monsters, and pickups
        self._damage_entities_in_area(damage_array)

        # Grasshopper: spawn next hop if we haven't reached 13 explosions
        if is_grasshopper:
            self._spawn_grasshopper_hop(target, current_time)

        if target.bomb_type == BombType.C4_TILE:
            pass  # No sound for C4 tile chain explosions
        elif target.bomb_type == BombType.SMALL_BOMB:
            self.pending_sounds.append(SoundType.SMALL_EXPLOSION)
        elif target.explosion_type == ExplosionType.SMALL:
            self.pending_sounds.append(SoundType.SMALL_EXPLOSION)
        else:
            self.pending_sounds.append(SoundType.EXPLOSION)

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
        self.pending_sounds.append(SoundType.URETHANE)

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

        self.pending_sounds.append(SoundType.URETHANE)

        # Remove bomb from list
        if bomb in self.bombs:
            self.bombs.remove(bomb)

    def _resolve_bioslime(self, bomb: Bomb) -> None:
        """Resolve BIOSLIME bomb - place a bioslime tile at bomb location."""
        tile = self.get_tile(bomb.x, bomb.y)
        if tile and tile.tile_type == TileType.EMPTY:
            self.set_tile(bomb.x, bomb.y, Tile.create_bioslime())
            self._schedule_bioslime_tick(bomb.placed_at)

        self.pending_sounds.append(
            SoundType.URETHANE
        )  # FIXME: Use urethane sound for now

        # Remove bomb from list
        if bomb in self.bombs:
            self.bombs.remove(bomb)

    def _schedule_bioslime_tick(self, now: float) -> None:
        """Schedule the next bioslime tick if not already active."""
        if self._bioslime_tick_active:
            return
        self._bioslime_tick_active = True
        event = Event(
            trigger_at=now + 0.25,
            target=self._bioslime_sentinel,
            event_type="bioslime_tick",
        )
        self.event_resolver.schedule_event(event)

    def _bioslime_tick(self, now: float) -> None:
        """Process one bioslime spreading tick."""
        self._bioslime_tick_active = False

        bioslime = get_bioslime_map(self.tiles, self.height, self.width)

        # Stop if all bioslime is gone
        if not bioslime.any():
            return

        walkable = ~get_solid_map(self.tiles, self.height, self.width)

        # Frontier: bioslime tiles with at least one walkable cardinal neighbor
        # Pad walkable with False border, then slice to check all 4 neighbors
        padded = np.pad(walkable, 1, constant_values=False)
        has_walkable_neighbor = (
            padded[:-2, 1:-1]  # up
            | padded[2:, 1:-1]  # down
            | padded[1:-1, :-2]  # left
            | padded[1:-1, 2:]  # right
        )
        frontier = bioslime & has_walkable_neighbor

        # Process frontier tiles
        ys, xs = np.where(frontier)
        for y, x in zip(ys, xs):
            tile = self.tiles[y][x]
            tile.spread_ticks -= 1
            if tile.spread_ticks <= 0:
                # Find walkable cardinal neighbors
                neighbors = []
                if y > 0 and walkable[y - 1, x]:
                    neighbors.append((x, y - 1))
                if y < self.height - 1 and walkable[y + 1, x]:
                    neighbors.append((x, y + 1))
                if x > 0 and walkable[y, x - 1]:
                    neighbors.append((x - 1, y))
                if x < self.width - 1 and walkable[y, x + 1]:
                    neighbors.append((x + 1, y))

                if neighbors:
                    nx, ny = random.choice(neighbors)
                    self.set_tile(nx, ny, Tile.create_bioslime())

                # Reset timer so it can spread again
                tile.spread_ticks = random.randint(4, 8)

        # Always reschedule as long as bioslime exists
        self._schedule_bioslime_tick(now)

    def _resolve_metal_plate(self, bomb: Bomb) -> None:
        """Resolve METAL_PLATE bomb - place a concrete tile at bomb location."""
        tile = self.get_tile(bomb.x, bomb.y)
        if tile and tile.tile_type == TileType.EMPTY:
            self.set_tile(bomb.x, bomb.y, Tile.create_concrete())

        self.pending_sounds.append(
            SoundType.URETHANE
        )  # FIXME: Use urethane sound for now

        # Remove bomb from list
        if bomb in self.bombs:
            self.bombs.remove(bomb)

    def _resolve_flamethrower(self, bomb: Bomb, now: float = 0.0) -> None:
        """Resolve FLAMETHROWER - 90-degree cone flame in player's facing direction."""
        cfg = FLAMETHROWER_CONFIG
        direction = bomb.direction if bomb.direction else Direction.DOWN

        # Create directed flame explosion
        directed_flame = DirectedFlameExplosion(
            direction=direction,
            max_distance=cfg["max_distance"],
            base_damage=cfg["damage"],
        )

        # Get walkable map
        solid_map = get_solid_map(self.tiles, self.height, self.width)
        walkable_map = ~solid_map

        # Calculate affected area
        final_mask = directed_flame.calculate_area(
            bomb.x, bomb.y, walkable_map, flood_fill
        )

        # Apply damage to tiles in the final mask
        for y in range(self.height):
            for x in range(self.width):
                if final_mask[y, x]:
                    tile = self.get_tile(x, y)
                    if tile:
                        tile.take_damage(cfg["damage"])
                        # Mark explosion visual
                        if not tile.solid:
                            self.explosions[y, x] = 1

        # Trigger any bombs in the affected area
        self._trigger_bombs_in_area(bomb, final_mask, now=now)

        # Damage players, monsters, and pickups
        self._damage_entities_in_area(final_mask * cfg["damage"])

        self.pending_sounds.append(SoundType.EXPLOSION)

        # Remove bomb from list
        if bomb in self.bombs:
            self.bombs.remove(bomb)

    def _resolve_fire_extinguisher(self, bomb: Bomb, now: float = 0.0) -> None:
        """Resolve FIRE_EXTINGUISHER - 90-degree cone that defuses bombs."""
        cfg = FIRE_EXTINGUISHER_CONFIG
        direction = bomb.direction if bomb.direction else Direction.DOWN

        # Create directed flame explosion (reuse the cone calculation)
        directed_flame = DirectedFlameExplosion(
            direction=direction, max_distance=cfg["max_distance"]
        )

        # Get walkable map
        solid_map = get_solid_map(self.tiles, self.height, self.width)
        walkable_map = ~solid_map

        # Calculate affected area
        final_mask = directed_flame.calculate_area(
            bomb.x, bomb.y, walkable_map, flood_fill
        )

        # Defuse any bombs in the final mask area
        defuse_delay = 24 * 60 * 60  # 24 hours in seconds
        for other_bomb in self.bombs:
            if other_bomb is bomb:
                continue  # Skip the fire extinguisher itself
            if final_mask[other_bomb.y, other_bomb.x]:
                other_bomb.state = "defused"
                # Reschedule explosion to 24 hours from now
                self.event_resolver.reschedule_events_by_target(
                    other_bomb, "explode", defuse_delay, now
                )

        # Show smoke effect in affected area
        for y in range(self.height):
            for x in range(self.width):
                if final_mask[y, x]:
                    tile = self.get_tile(x, y)
                    if tile and not tile.solid:
                        self.explosions[y, x] = 4

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

        self.pending_sounds.append(
            SoundType.URETHANE
        )  # FIXME: Use urethane sound for now

        # Remove bomb from list
        if bomb in self.bombs:
            self.bombs.remove(bomb)

    def _resolve_grenade(self, bomb: Bomb, now: float = 0.0) -> None:
        """Resolve GRENADE - create a grenade projectile entity."""
        cfg = GRENADE_CONFIG
        direction = bomb.direction if bomb.direction else Direction.DOWN

        # Create grenade entity at bomb position
        grenade = DynamicEntity.create_grenade(
            x=bomb.x + 0.5,  # Center in tile
            y=bomb.y + 0.5,
            direction=direction,
            owner_id=bomb.owner_id,
            speed=cfg["speed"],
        )

        # Add grenade to monsters list (for rendering and movement)
        self.monsters.append(grenade)

        # Start the grenade moving
        self.move_entity(grenade, now=now)

        # Remove bomb from list
        if bomb in self.bombs:
            self.bombs.remove(bomb)

    def resolve_grenade_movement(
        self, grenade: DynamicEntity, event: MoveEvent, flags: ResolveFlags
    ) -> None:
        """Resolve grenade movement - moves until hitting wall or player."""
        # Calculate actual distance based on elapsed time
        current_time = event.trigger_at
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

        # self.round_position(grenade)

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
                self._explode_grenade(grenade, nx, ny, now=current_time)
                return

        # Check if next tile is solid or out of bounds
        next_tile = self.get_tile(nx, ny)
        if next_tile is None or next_tile.solid:
            # Explode in current tile (clamped to map)
            gx = max(0, min(self.width - 1, gx))
            gy = max(0, min(self.height - 1, gy))
            self._explode_grenade(grenade, gx, gy, now=current_time)
            return

        # Continue moving
        if flags.spawn:
            self.move_entity(grenade, now=current_time)

    def _explode_grenade(
        self, grenade: DynamicEntity, x: int, y: int, now: float = 0.0
    ) -> None:
        """Trigger a small explosion at the given position and remove grenade."""
        # Create a small bomb at explosion location
        explosion_bomb = Bomb(
            x=x,
            y=y,
            bomb_type=BombType.SMALL_BOMB,
            placed_at=now,
            owner_id=grenade.owner_id,
            fuse_override=0.0,  # Instant
        )

        # Schedule immediate explosion
        explosion_event = Event(
            trigger_at=now,
            target=explosion_bomb,
            event_type="explode",
        )
        self.event_resolver.schedule_event(explosion_event)

        # Remove grenade from monsters list
        if grenade in self.monsters:
            self.monsters.remove(grenade)

    def _resolve_flame_barrel(self, bomb: Bomb, now: float = 0.0) -> None:
        """Resolve FLAME_BARREL bomb - flood fill and damage all non-solid tiles in range."""
        cfg = FLAME_BARREL_CONFIG

        # Get solid map (True = solid, we need inverse for flood fill which expects True = walkable)
        solid_map = get_solid_map(self.tiles, self.height, self.width)
        walkable_map = ~solid_map  # Invert: True = empty/walkable

        # Flood fill from bomb position
        fill_mask = flood_fill(
            walkable_map, (bomb.y, bomb.x), max_dist=cfg["max_distance"]
        )

        # Apply damage to all tiles in the flood fill area
        damage = cfg["damage"]
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
        self._trigger_bombs_in_area(bomb, fill_mask, now=now)

        # Damage players, monsters, and pickups
        self._damage_entities_in_area(fill_mask * cfg["damage"])

        self.pending_sounds.append(SoundType.EXPLOSION)

        # Remove bomb from list
        if bomb in self.bombs:
            self.bombs.remove(bomb)

    def _resolve_cracker_barrel(self, bomb: Bomb, now: float = 0.0) -> None:
        """Resolve CRACKER_BARREL bomb - flood fill damage + scattered medium explosions."""
        cfg = CRACKER_BARREL_CONFIG
        current_time = now

        # Get solid map for flood fill
        solid_map = get_solid_map(self.tiles, self.height, self.width)
        walkable_map = ~solid_map

        # Flood fill from bomb position (like flame barrel but shorter range)
        fill_mask = flood_fill(
            walkable_map, (bomb.y, bomb.x), max_dist=cfg["flood_fill_distance"]
        )

        # Apply damage to all tiles in the flood fill area
        damage = cfg["flood_fill_damage"]
        for y in range(self.height):
            for x in range(self.width):
                if fill_mask[y, x]:
                    tile = self.get_tile(x, y)
                    if tile:
                        tile.take_damage(damage)
                        if not tile.solid:
                            self.explosions[y, x] = 1

        # Trigger any bombs in the flood fill area
        self._trigger_bombs_in_area(bomb, fill_mask, now=now)

        # Damage players, monsters, and pickups
        self._damage_entities_in_area(fill_mask * cfg["flood_fill_damage"])

        # Schedule scattered medium explosions
        scatter_count = cfg["scatter_explosions"]
        scatter_dist = cfg["scatter_distance"]
        interval = cfg["scatter_interval"]

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

        self.pending_sounds.append(SoundType.EXPLOSION)

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

        self.pending_sounds.append(SoundType.EXPLOSION)

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
        if new_hop_count >= cfg["max_hops"]:
            return

        # Calculate new position: random offset up to max_hop_distance in each direction
        max_dist = cfg["max_hop_distance"]
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
            next_explosion = random.choice(cfg["first_hop_explosions"])
        else:
            # Subsequent hops: shrink/stay/grow based on configured chances
            current_explosion = source_bomb.explosion_type
            explosion_order = cfg["explosion_order"]
            roll = random.random()

            if roll < cfg["shrink_chance"]:
                # Shrink: move down in explosion_order, stay at minimum
                try:
                    idx = explosion_order.index(current_explosion)
                    next_explosion = explosion_order[max(0, idx - 1)]
                except ValueError:
                    next_explosion = explosion_order[0]
            elif roll < cfg["shrink_chance"] + cfg["stay_chance"]:
                # Stay same
                next_explosion = current_explosion
            else:
                # Grow: move up in explosion_order, stay at maximum
                try:
                    idx = explosion_order.index(current_explosion)
                    next_explosion = explosion_order[
                        min(len(explosion_order) - 1, idx + 1)
                    ]
                except ValueError:
                    next_explosion = explosion_order[-1]

        # Random fuse between configured min and max
        fuse_time = random.uniform(cfg["fuse_min"], cfg["fuse_max"])

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
        target_x, target_y, new_x, new_y = self.get_entity_movement_vector(target)

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

        # Use event's scheduled time for normal resolution (timer-fired).
        # For premature resolution (direction change), use the resolve_time
        # captured in change_entity_direction.
        if flags.resolve_time > 0:
            current_time = flags.resolve_time
        else:
            current_time = event.trigger_at
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

        # check map bounds
        min_allowed = 0.5
        if target.y < min_allowed:
            target.y = min_allowed
        if target.x < min_allowed:
            target.x = min_allowed
        if target.y > self.height - min_allowed:
            target.y = self.height - min_allowed
        if target.x > self.width - min_allowed:
            target.x = self.width - min_allowed

        # print(f"to  : {target.x}, {target.y}")
        # self.round_position(target)
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
            self.entity_enter_tile(target, now=current_time)
        # middle
        if abs(moved - int(moved) - 0.5) < tolerance:
            # print(f"enter center {px} {py}")
            self.entity_reach_tile_center(target)

            # check the neighboring tiles
            # wall
            # interact
            in_bounds, next_tile = self.get_neighbor_tile(target)
            # print(next_tile)
            if not in_bounds:
                blocked = True
                target.state = "idle"
            elif next_tile.solid:
                blocked = True
                self.collision_check(target, next_tile, current_time)
            elif self.try_push_bomb(target):
                blocked = True

        if flags.spawn and not blocked:
            self.move_entity(target, now=current_time)

        # fight monsters
        self.fight(target)

    def centralize_position(self, entity: DynamicEntity) -> None:
        if entity.direction in (Direction.UP, Direction.DOWN):
            entity.x = round(entity.x - 0.5) + 0.5
        if entity.direction in (Direction.RIGHT, Direction.LEFT):
            entity.y = round(entity.y - 0.5) + 0.5

    def resolve_dig(self, target: DynamicEntity, event: Event, flags: ResolveFlags) -> None:
        if target.state == "dead":
            return

        in_bounds, target_tile = self.get_neighbor_tile(target)
        if not in_bounds:
            return
        dig_power = target.get_dig_power() if isinstance(target, Player) else 1
        target_tile.take_damage(dig_power)
        self.pending_sounds.append(SoundType.DIG)
        # print("DIG!")
        # print(target_tile)

        if target_tile.health > 0:
            self.dig(target, event.trigger_at)
        else:
            target.state = "walk"
            self.move_entity(target, now=event.trigger_at)

    def get_neighbor_tile(
        self, entity: DynamicEntity, range: int = 1
    ) -> Tuple[bool, Tile]:
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

        tile = self.get_tile(nx, ny)
        if tile is None:
            return False, Tile()
        else:
            return True, tile

    # TODO: tile entering logic
    def entity_enter_tile(self, target: DynamicEntity, now: float = 0.0) -> None:
        """Events that happen when entity enters a tile"""
        # check for mines
        px, py = xy_to_tile(target.x, target.y)
        for bomb in self.bombs:
            if bomb.bomb_type == BombType.LANDMINE:
                if bomb.x == px and bomb.y == py:
                    explosion_event = Event(
                        trigger_at=now,
                        target=bomb,
                        event_type="explode",
                    )
                    self.event_resolver.schedule_event(explosion_event)

    # TODO: tile center reached logic
    def entity_reach_tile_center(self, entity: DynamicEntity) -> None:
        """Events that happen when entity enters a tile center"""
        px, py = xy_to_tile(entity.x, entity.y)

        # pickup items (only players pick up items)
        if isinstance(entity, Player):
            pickup = self.pickups[py][px]
            if pickup:
                if pickup.pickup_type == PickupType.TOOL:
                    assert isinstance(pickup, Tool)
                    entity.pickup_tool(pickup)
                else:
                    assert isinstance(pickup, Treasure)
                    entity.pickup_treasure(pickup)
                    # TODO:
                    self.pending_sounds.append(SoundType.TREASURE)
                self.pickups[py][px] = None

        # teleport (applies to all entities)
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
                entity.x = val[0] + 0.5
                entity.y = val[1] + 0.5


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
            self.pending_sounds.append(SoundType.DIE)

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

    def _interpolate_entity_position(
        self, entity: DynamicEntity, render_entity: DynamicEntity, now: float
    ) -> None:
        """Update render_entity position based on pending move event progress.

        Uses progress fraction (elapsed / total_duration) to interpolate exactly
        0.5 tiles per move segment. This naturally handles push speed modifiers
        (baked into trigger_at) and caps at the tile boundary.

        Looks up events by target identity on `entity` (the authoritative object)
        and writes the interpolated position to `render_entity` (the deep copy).
        """
        move_events = self.event_resolver.get_events_by_target(entity, "move")
        if not move_events:
            move_events = self.event_resolver.get_events_by_target(entity, "push")
        if not move_events:
            return

        assert (
            len(move_events) <= 1
        ), f"Expected at most 1 move event, got {len(move_events)}"
        event: MoveEvent = move_events[0]  # type: ignore[assignment]
        total_duration = event.trigger_at - event.created_at
        if total_duration <= 0:
            return
        progress = min((now - event.created_at) / total_duration, 1.0)
        d = progress * 0.5

        direction = Direction(event.direction)
        if direction == Direction.RIGHT:
            render_entity.x = entity.x + d
        elif direction == Direction.LEFT:
            render_entity.x = entity.x - d
        elif direction == Direction.UP:
            render_entity.y = entity.y - d
        elif direction == Direction.DOWN:
            render_entity.y = entity.y + d

    def get_render_state(self, now: Optional[float] = None) -> RenderState:
        """Build and return a RenderState for the renderer."""

        # Build tilemap as 2D numpy array
        tilemap = np.array(
            [[tile.visual_id for tile in row] for row in self.tiles], dtype=np.uint8
        )

        explosions_copy = self.explosions.copy()

        self.cleanup_render_state()

        # Deep copy entities and interpolate positions for rendering
        render_players = [deepcopy(p) for p in self.players]
        render_monsters = [deepcopy(m) for m in self.monsters]

        if now is None:
            now = Clock.now()
        for player, render_player in zip(self.players, render_players):
            self._interpolate_entity_position(player, render_player, now)

        for monster, render_monster in zip(self.monsters, render_monsters):
            self._interpolate_entity_position(monster, render_monster, now)

        sounds = self.pending_sounds.copy()
        self.pending_sounds.clear()

        return RenderState(
            width=self.width,
            height=self.height,
            tilemap=tilemap,
            explosions=explosions_copy,
            players=render_players,
            monsters=render_monsters,
            pickups=list(
                filter(lambda x: x is not None, chain.from_iterable(self.pickups))
            ),
            bombs=self.bombs,
            server_time=now,
            sounds=sounds,
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

    def get_entity_movement_vector(
        self, target: DynamicEntity
    ) -> Tuple[int, int, int, int]:
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

        return target_x, target_y, new_x, new_y
