import numpy as np
from typing import Any, Optional, List, Dict, Tuple, TYPE_CHECKING, Union
from itertools import chain

from game_engine.clock import Clock
from game_engine.entities.tile import Tile, TileType
from game_engine.entities.dynamic_entity import DynamicEntity, Direction, EntityType
from game_engine.engine_utils import flood_fill, get_solid_map
from cfg.tile_dictionary import C4_TILE_ID, URETHANE_TILE_ID
from game_engine.entities.player import Player
from game_engine.entities.pickup import Pickup, PickupType
from game_engine.entities.bomb import Bomb, BombType
from game_engine.entities.explosion import (
    ExplosionType, SmallExplosion, MediumExplosion, LargeExplosion, NukeExplosion,
    SmallCrossExplosion, BigCrossExplosion
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
        # FIXME: placeholder
        self.starting_poses = [
            (1, 1),
            (1, width - 1),
            (height - 1, 1),
            (height - 1, width - 1),
        ]
        self.prev_time = -1
        self.sounds = SoundEngine(music_volume=0.5, fx_volume=1.0)

    def load_map(self, map_data: "MapData") -> None:
        """Load map data into the engine."""
        self.width = map_data.width
        self.height = map_data.height
        self.tiles = map_data.tiles
        self.monsters = map_data.monsters
        for pickup in list(map_data.tools):
            self.pickups[pickup.y][pickup.x] = pickup
        for pickup in list(map_data.treasures):
            self.pickups[pickup.y][pickup.x] = pickup

    def start(self) -> None:
        """Start the game engine and event processing."""
        self.sounds.game()
        self.event_resolver.start()

    def stop(self) -> None:
        """Stop the game engine and event processing."""
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

    def detonate_remotes(self, player: Player) -> None:
        for bomb in self.bombs:
            if bomb.bomb_type == BombType.REMOTE and bomb.owner_id == player.id:
                explosion_event = Event(
                    trigger_at=Clock.now() + 0,
                    target=bomb,
                    event_type="explode",
                )
                self.event_resolver.schedule_event(explosion_event)

    def clear_entity_move_events(self, player: DynamicEntity) -> None:
        """Clear all move actions by the player"""
        # First resolve undergoing events, i.e., stop to the place the entity
        # has already made progress to
        self.event_resolver.resolve_object_events(
            player.id, "move", ResolveFlags(spawn=False)
        )
        # Safety: clear all movement events from the queue
        self.event_resolver.cancel_object_events(player.id, "move")

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
            if not next_tile.diggable:
                # print("change entity direction: blocked")
                # print(player.x, player.y)
                # print(next_tile)
                return
            else:
                self.dig(player)
        else:
            # Create new movement
            self.move_entity(player)

    def move_entity(self, entity: DynamicEntity):
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
            dt = d / entity.speed
            # HACK: since the movement is calculated with actual time, add some bonus
            # time to cross the threshold properly, to make tile transition logic
            # nicee
            dt += 0.01
            movement_event = MoveEvent(
                trigger_at=Clock.now() + dt,
                target=entity,
                event_type="move",
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
        elif isinstance(target, Player) and event.event_type == "dig":
            self.resolve_dig(target, event, flags)

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

        if target.bomb_type == BombType.C4_TILE:
            pass  # No sound for C4 tile chain explosions
        elif target.bomb_type == BombType.SMALL_BOMB:
            self.sounds.small_explosion()
        elif target.bomb_type == BombType.URETHANE:
            self.sounds.urethane()
        else:
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
                        tile.tile_type = TileType.C4
                        tile.visual_id = C4_TILE_ID
                        tile.solid = True
                        tile.diggable = True
                        tile.health = 100

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
                        tile.tile_type = TileType.URETHANE
                        tile.visual_id = URETHANE_TILE_ID
                        tile.solid = True
                        tile.diggable = True
                        tile.health = 200

        self.sounds.urethane()

        # Remove bomb from list
        if bomb in self.bombs:
            self.bombs.remove(bomb)

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
        d = dt * target.speed

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
            if next_tile.solid:
                blocked = True
                px, py = xy_to_tile(target.x, target.y)
                if not next_tile.diggable:
                    target.state = "idle"
                    # print("resolve move blocked")
                    # print(target.x, target.y)
                    # print(next_tile)
                else:
                    # print("dig")
                    self.dig(target)

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
        self.sounds.dig()
        # print("DIG!")
        # print(target_tile)

        if target_tile.health > 0:
            self.dig(target)
        else:
            self.move_entity(target)

    def get_neighbor_tile(self, entity: DynamicEntity) -> Tile:
        px, py = xy_to_tile(entity.x, entity.y)
        nx, ny = px, py
        dir = Direction(entity.direction)
        if dir == Direction.RIGHT:
            nx += 1
        elif dir == Direction.LEFT:
            nx -= 1
        elif dir == Direction.UP:
            ny -= 1
        elif dir == Direction.DOWN:
            ny += 1
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
                self.sounds.treasure()
            self.pickups[py][px] = None

    def fight(self, agent: DynamicEntity) -> None:
        entities = self.players + self.monsters
        px, py = xy_to_tile(agent.x, agent.y)
        for other in entities:
            ox, oy = (int)(other.x), (int)(other.y)
            if ox == px and oy == py and other.state != "dead" and other.id != agent.id:
                other.take_damage(agent.fight_power)
                agent.take_damage(other.fight_power)
                # print("FIGHT!")
                # print(f"Agent deals {agent.fight_power} damage")
                # print(f"Enemy deals {other.fight_power} damage")
                # print(f"Agent health {agent.health}")
                # print(f"Enemy health {other.health}")
        if agent.state == "dead":
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
            [[tile.visual_id for tile in row] for row in self.tiles],
            dtype=np.uint8
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
