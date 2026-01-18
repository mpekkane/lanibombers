import array
from typing import Any, Optional, List, Dict, Tuple, TYPE_CHECKING, Union

from game_engine.clock import Clock
from game_engine.entities.tile import Tile
from game_engine.entities.dynamic_entity import DynamicEntity, Direction
from game_engine.entities.player import Player
from game_engine.entities.pickup import Pickup, PickupType
from game_engine.entities.bomb import Bomb, BombType
from game_engine.events.event import Event, ResolveFlags, MoveEvent
from game_engine.events.event_resolver import EventResolver
from game_engine.render_state import RenderState
from game_engine.entities import Tool, Treasure
from game_engine.utils import xy_to_tile, clamp
from itertools import chain


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
        self.event_resolver.start()

    def stop(self) -> None:
        """Stop the game engine and event processing."""
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

    def change_entity_direction(self, player: DynamicEntity) -> None:
        """Create and handle player movement events"""
        # When changing dir, all previous movement events are cleared
        self.clear_entity_move_events(player)

        # collision check
        next_tile = self.get_neighbor_tile(player)
        if next_tile.solid and not next_tile.diggable:
            print("change entity direction: blocked")
            return

        # Create new movement
        self.move_entity(player)

    def move_entity(self, entity: DynamicEntity):
        """Main movement generator function from dynamic entities"""

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
        self.clear_entity_move_events(entity)
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
        # FIXME: ?
        current_time = Clock.now()

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
        current_time = Clock.now()
        dt = current_time - event.created_at
        d = dt * target.speed

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

        target.x, target.y = self.clamp_to_map_size(target.x, target.y)

        tolerance = 0.05
        blocked = False
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
                if not next_tile.diggable:
                    target.state = "idle"
                    print("blocked")
                else:
                    self.dig(target)

        if flags.spawn and not blocked:
            self.move_entity(target)

    def resolve_dig(self, target: Player, event: Event, flags: ResolveFlags) -> None:
        target_tile = self.get_neighbor_tile(target)
        dig_power = target.get_dig_power()
        target_tile.take_damage(dig_power)
        print("DIG!")
        print(target_tile)

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
            self.pickups[py][px] = None

        # picked = -1
        # for i, pickup in enumerate(self.pickups):
        #     if pickup.x == px and pickup.y == py:
        #         if pickup.pickup_type == PickupType.TOOL:
        #             assert isinstance(pickup, Tool)
        #             player.pickup_tool(pickup)
        #         else:
        #             assert isinstance(pickup, Treasure)
        #             player.pickup_treasure(pickup)
        #         picked = i
        #         print(f"picked: {pickup.x} {pickup.y}")
        #     else:
        #         print(f"not here {pickup.x} {pickup.y}")
        # if picked >= 0:
        #     del self.pickups[picked]

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
            pickups=list(
                filter(lambda x: x is not None, chain.from_iterable(self.pickups))
            ),
            bombs=self.bombs,
            explosions=explosions_copy,
        )

    def cleanup_render_state(self):
        # clean explosions byte array (0=none)
        for i in range(self.height * self.width):
            self.explosions[i] = 0

    def clamp_to_map_size(
        self, x: Optional[Union[int, float]], y: Optional[Union[int, float]]
    ) -> Tuple[Union[int, float], Union[int, float]]:
        if not x:
            x = 0
        if not y:
            y = 0
        return self.clamp_x(x), self.clamp_y(y)

    def clamp_x(self, x: Union[int, float]):
        return clamp(x, 0, self.height)

    def clamp_y(self, y: Union[int, float]):
        return clamp(y, 0, self.width)
