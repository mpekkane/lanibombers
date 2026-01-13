import array
from typing import Any, Optional, List

from game_engine.entities.tile import Tile
from game_engine.entities.dynamic_entity import DynamicEntity
from game_engine.entities.pickup import Pickup
from game_engine.entities.bomb import Bomb
from game_engine.events.event import Event
from game_engine.events.event_resolver import EventResolver
from game_engine.render_state import RenderState


class GameEngine:
    """Main game engine containing the tile grid and event system."""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.tiles: list[list[Tile]] = [
            [Tile() for _ in range(width)]
            for _ in range(height)
        ]
        self.players: List[DynamicEntity] = []
        self.monsters: List[DynamicEntity] = []
        self.pickups: List[Pickup] = []
        self.bombs: List[Bomb] = []
        self.event_resolver = EventResolver(resolve=self.resolve)

    def start(self) -> None:
        """Start the game engine and event processing."""
        self.event_resolver.start()

    def stop(self) -> None:
        """Stop the game engine and event processing."""
        self.event_resolver.stop()

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

    def schedule_event(self, event: Event) -> None:
        """Schedule an event for later execution."""
        self.event_resolver.schedule_event(event)

    def cancel_event(self, event_id) -> bool:
        """Cancel a scheduled event."""
        return self.event_resolver.cancel_event(event_id)

    def resolve(self, target: Any, event: Event) -> None:
        """
        Called when an event fires. Override to handle event resolution.

        Args:
            target: The object associated with the event (e.g., Bomb, Pickup)
            event: The event that triggered
        """
        pass

    def get_render_state(self) -> RenderState:
        """Build and return a RenderState for the renderer."""
        tilemap = array.array('B')
        for row in self.tiles:
            for tile in row:
                tilemap.append(tile.tile_id)

        return RenderState(
            width=self.width,
            height=self.height,
            tilemap=tilemap,
            players=self.players,
            monsters=self.monsters,
            pickups=self.pickups,
            bombs=self.bombs
        )
