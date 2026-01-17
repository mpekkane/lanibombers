import array
import time
from typing import Any, Optional, List, Dict, Tuple, TYPE_CHECKING

from game_engine.entities.tile import Tile
from game_engine.entities.dynamic_entity import DynamicEntity, Direction
from game_engine.entities.player import Player
from game_engine.entities.pickup import Pickup
from game_engine.entities.bomb import Bomb, BombType
from game_engine.events.event import Event, ResolveFlags, MoveEvent
from game_engine.events.event_resolver import EventResolver
from game_engine.render_state import RenderState
from game_engine.utils import xy_to_tile

if TYPE_CHECKING:
    from game_engine.map_loader import MapData


class GameEngine:
    """Main game engine containing the tile grid and event system."""

    explosions = array.array("B")

    def __init__(self, width: int = 64, height: int = 45):
        self.width = width
        self.height = height
        self.tiles: list[list[Tile]] = [
            [Tile() for _ in range(width)] for _ in range(height)
        ]
        self.explosions = array.array("B", [0]) * self.width * self.height
        self.players: List[Player] = []
        self.player_map: Dict[str, int] = {}
        self.monsters: List[DynamicEntity] = []
        self.pickups: List[Pickup] = []
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

    def load_map(self, map_data: "MapData") -> None:
        """Load map data into the engine."""
        self.width = map_data.width
        self.height = map_data.height
        self.tiles = map_data.tiles
        self.monsters = map_data.monsters
        self.pickups = list(map_data.treasures) + list(map_data.tools)

    def start(self) -> None:
        """Start the game engine and event processing."""
        self.event_resolver.start()

    def stop(self) -> None:
        """Stop the game engine and event processing."""
        self.event_resolver.stop()

    def create_player(self, name: str) -> None:
        num_players = len(self.players)
        start_pose = self.starting_poses[num_players]
        player = Player(
            x=start_pose[0],
            y=start_pose[1],
            direction=Direction.RIGHT,
            name=name,
            sprite_id=num_players + 1,
            state="idle",
            speed=1,
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
            print("plant timed bomb")
            explosion_event = Event(
                trigger_at=bomb.placed_at + bomb.fuse_duration,
                target=bomb,
                event_type="explode",
            )
            self.event_resolver.schedule_event(explosion_event)
        else:
            print(f"plant untimed bomb ({bomb.x}, {bomb.y})")

    def detonate_remotes(self, player: Player) -> None:
        for bomb in self.bombs:
            if bomb.bomb_type == BombType.REMOTE and bomb.owner_id == player.id:
                explosion_event = Event(
                    trigger_at=time.time() + 0,
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

    def change_entity_direction(self, player: DynamicEntity) -> None:
        """Create and handle player movement events"""
        # When changing dir, all previous movement events are cleared
        self.clear_entity_move_events(player)
        # Create new movement
        self.move_entity(player)

    def move_entity(self, entity: DynamicEntity):
        """Main movement generator function from dynamic entities"""

        # When walking, calculate distance
        if entity.state == "walk":
            if entity.direction == Direction.RIGHT:
                decimal = (entity.x - (int)(entity.x))
                if decimal > 0.5:
                    d = 1 - decimal
                else:
                    d = 0.5 - decimal
            elif entity.direction == Direction.LEFT:
                decimal = (entity.x - (int)(entity.x))
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

            # this is the boundary condition
            if d == 0:
                d = 0.5

            # this is the required time to cross the thershold
            dt = d / entity.speed
            movement_event = MoveEvent(
                trigger_at=time.time() + dt,
                target=entity,
                event_type="move",
                created_at=time.time(),
                created_by=entity.id,
                direction=str(entity.direction.value)
            )
            self.event_resolver.schedule_event(movement_event)

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

    def resolve_bomb(self, target: Bomb, event: Event, flags: ResolveFlags) -> None:
        """Resolve explosion events"""
        # FIXME: ?
        current_time = time.time()

        # Damage tiles and create explosions within blast radius
        for dy in range(-target.blast_radius, target.blast_radius + 1):
            for dx in range(-target.blast_radius, target.blast_radius + 1):
                tx, ty = target.x + dx, target.y + dy
                tile = self.get_tile(tx, ty)
                if tile:
                    tile.take_damage(target.damage)
                    # Record explosion start time and type at this tile (type 1 = big bomb)
                    self.explosions[tx + ty * self.width] = 1  # for normal big bomb

        # Remove bomb from list
        if target in self.bombs:
            self.bombs.remove(target)

    def resolve_movement(
        self, target: DynamicEntity, event: MoveEvent, flags: ResolveFlags
    ) -> None:
        """Resolve move events"""
        # because events might have been cleared, i.e., triggered at times
        # other than planned, calculate actual traveled distance
        current_time = time.time()
        dt = current_time - event.created_at
        d = dt * target.speed
        prev_vx, prev_vy = xy_to_tile(target.x, target.y)

        # move target to the stored direction, not the current one!
        # this is due to the fact that when changing direction, the target (pointer)
        # has different direction than in the move command
        dir = Direction(event.direction)
        moved: float
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

        tolerance = 0.01
        # print("-" * 20)
        # print(target.x, target.y)
        # print("1:", abs(moved - int(moved)))
        # print("2:", abs(moved - int(moved) - 1))
        # enter tile
        px, py = xy_to_tile(target.x, target.y)
        if abs(moved - int(moved)) < tolerance or abs(moved - int(moved) - 1) < tolerance:
            print(f"enter tile   {px} {py}")
            self.entity_enter_tile(target)
        # middle
        if abs(moved - int(moved) - 0.5) < tolerance:
            print(f"enter center {px} {py}")
            self.entity_reach_tile_center(target)

        # spawn in by default true, but when clearing, do not spawn new ones
        if flags.spawn:
            self.move_entity(target)

    # TODO: tile entering logic
    def entity_enter_tile(self, target: DynamicEntity) -> None:
        """Events that happen when entity enters a tile"""
        # check for mines
        px, py = xy_to_tile(target.x, target.y)
        for bomb in self.bombs:
            if bomb.bomb_type == BombType.LANDMINE:
                if bomb.x == px and bomb.y == py:
                    explosion_event = Event(
                        trigger_at=time.time() + 0,
                        target=bomb,
                        event_type="explode",
                    )
                    self.event_resolver.schedule_event(explosion_event)

    # TODO: tile center reached logic
    def entity_reach_tile_center(self, target: DynamicEntity) -> None:
        """Events that happen when entity enters a tile center"""
        pass

    def update_player_state(self):
        """OBSOLETE: used for tick-rendering"""
        if self.prev_time < 0:
            self.prev_time = time.time()
        elapsed = time.time() - self.prev_time

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
        self.prev_time = time.time()

    def get_render_state(self) -> RenderState:
        """Build and return a RenderState for the renderer."""

        # Build tilemap
        tilemap = array.array("B")
        for row in self.tiles:
            for tile in row:
                tilemap.append(tile.visual_id)

        explosions_copy = self.explosions[:]

        self.cleanup_render_state()

        return RenderState(
            width=self.width,
            height=self.height,
            tilemap=tilemap,
            players=self.players,
            monsters=self.monsters,
            pickups=self.pickups,
            bombs=self.bombs,
            explosions=explosions_copy,
        )

    def cleanup_render_state(self):
        # clean explosions byte array (0=none)
        for i in range(self.height * self.width):
            self.explosions[i] = 0
