"""
Client-side simulation for state extrapolation.
Receives RenderState from server and extrapolates between updates.
"""

from dataclasses import replace
from typing import Optional

from game_engine.clock import Clock
from game_engine.render_state import RenderState
from game_engine.entities.dynamic_entity import Direction


# Direction to velocity mapping (dx, dy per unit speed)
DIRECTION_VELOCITY = {
    Direction.UP: (0, -1),
    Direction.DOWN: (0, 1),
    Direction.LEFT: (-1, 0),
    Direction.RIGHT: (1, 0),
}


class ClientSimulation:
    """
    Client-side simulator that extrapolates game state between server updates.

    Receives RenderState objects from the server and provides extrapolated
    state for smooth rendering. Currently extrapolates DynamicEntity movement.
    """

    def __init__(self):
        self._server_state: Optional[RenderState] = None
        self._server_state_time: float = 0.0

    def receive_state(self, state: RenderState) -> None:
        """
        Receive a new RenderState from the server.

        Args:
            state: The authoritative state from the game server
        """
        self._server_state = state
        self._server_state_time = Clock.now()

    def get_render_state(self) -> Optional[RenderState]:
        """
        Get the extrapolated RenderState for rendering.

        Returns:
            Extrapolated RenderState, or None if no state has been received
        """
        if self._server_state is None:
            return None

        current_time = Clock.now()
        delta_time = current_time - self._server_state_time

        # Create extrapolated copies of dynamic entities
        extrapolated_players = [
            self._extrapolate_entity(player, delta_time)
            for player in self._server_state.players
        ]
        extrapolated_monsters = [
            self._extrapolate_entity(monster, delta_time)
            for monster in self._server_state.monsters
        ]

        return RenderState(
            width=self._server_state.width,
            height=self._server_state.height,
            tilemap=self._server_state.tilemap,
            players=extrapolated_players,
            monsters=extrapolated_monsters,
            pickups=self._server_state.pickups,
            bombs=self._server_state.bombs,
            explosions=self._server_state.explosions,
        )

    def _extrapolate_entity(self, entity, delta_time: float):
        """
        Extrapolate an entity's position based on its movement state.

        Args:
            entity: DynamicEntity to extrapolate
            delta_time: Time elapsed since last server update

        Returns:
            New DynamicEntity with extrapolated position
        """
        # Only extrapolate if entity is walking
        if entity.state != 'walk' or entity.speed <= 0:
            return entity

        # Get velocity from direction
        dx, dy = DIRECTION_VELOCITY.get(entity.direction, (0, 0))

        # Calculate new position
        new_x = entity.x + dx * entity.speed * delta_time
        new_y = entity.y + dy * entity.speed * delta_time

        # Return new entity with extrapolated position
        return replace(entity, x=new_x, y=new_y)
