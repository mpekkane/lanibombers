"""
Client-side simulation for state extrapolation.
Receives RenderState from server and extrapolates between updates.
"""

from dataclasses import replace
from typing import Any, Optional

import numpy as np

from game_engine.clock import Clock
from game_engine.render_state import RenderState, SoundType
from game_engine.entities.dynamic_entity import Direction


# Direction to velocity mapping (dx, dy per unit speed)
DIRECTION_VELOCITY = {
    Direction.UP: (0, -1),
    Direction.DOWN: (0, 1),
    Direction.LEFT: (-1, 0),
    Direction.RIGHT: (1, 0),
}

MAX_EXTRAPOLATION_TIME = 0.5  # Don't extrapolate beyond this


class ClientSimulation:
    """
    Client-side simulator that extrapolates game state between server updates.

    Receives RenderState objects from the server and provides extrapolated
    state for smooth rendering. Currently extrapolates DynamicEntity movement.
    """

    def __init__(self, sound_engine=None):
        self._server_state: Optional[RenderState] = None
        self._server_state_time: float = 0.0
        self._prev_server_time: float = 0.0  # Previous state's server_time
        self._accumulated_explosions: Optional[np.ndarray] = None
        self._sound_engine = sound_engine

    def receive_state(self, state: RenderState) -> None:
        """
        Receive a new RenderState from the server.

        Re-times state arrival using server clock deltas so that
        client-side extrapolation is immune to variable network/processing delays.
        """
        if self._accumulated_explosions is not None:
            # Merge: new explosions take priority, keep old where new is zero
            self._accumulated_explosions = np.where(
                state.explosions > 0, state.explosions, self._accumulated_explosions
            )
        else:
            self._accumulated_explosions = state.explosions.copy()

        # Re-time: advance client state time by the server's own time delta
        # instead of using raw Clock.now() which includes variable network delay
        if self._prev_server_time > 0 and state.server_time > 0:
            server_delta = state.server_time - self._prev_server_time
            self._server_state_time += server_delta
        else:
            # First state — bootstrap with client clock
            self._server_state_time = Clock.now()

        self._prev_server_time = state.server_time
        self._server_state = state

        if self._sound_engine and state.sounds:
            for sound in state.sounds:
                self._play_sound(sound)

    def _play_sound(self, sound_type: int) -> None:
        """Play a sound effect via the sound engine."""
        se = self._sound_engine
        if sound_type == SoundType.EXPLOSION:
            se.explosion()
        elif sound_type == SoundType.SMALL_EXPLOSION:
            se.small_explosion()
        elif sound_type == SoundType.URETHANE:
            se.urethane()
        elif sound_type == SoundType.DIG:
            se.dig()
        elif sound_type == SoundType.TREASURE:
            se.treasure()
        elif sound_type == SoundType.DIE:
            se.die()

    def has_state(self) -> bool:
        """Whether at least one server state has been received."""
        return self._server_state is not None

    def get_render_state(self) -> Optional[RenderState]:
        """
        Get the extrapolated RenderState for rendering.

        Returns:
            Extrapolated RenderState, or None if no state has been received
        """
        if self._server_state is None:
            return None

        current_time = Clock.now()
        delta_time = min(current_time - self._server_state_time, MAX_EXTRAPOLATION_TIME)

        # Create extrapolated copies of dynamic entities
        extrapolated_players = [
            self._extrapolate_entity(player, delta_time)
            for player in self._server_state.players
        ]
        extrapolated_monsters = [
            self._extrapolate_entity(monster, delta_time)
            for monster in self._server_state.monsters
        ]

        # Use accumulated explosions and clear for next frame
        explosions = self._accumulated_explosions
        self._accumulated_explosions = np.zeros_like(explosions)

        return RenderState(
            width=self._server_state.width,
            height=self._server_state.height,
            tilemap=self._server_state.tilemap,
            players=extrapolated_players,
            monsters=extrapolated_monsters,
            pickups=self._server_state.pickups,
            bombs=self._server_state.bombs,
            explosions=explosions,
            running=self._server_state.running
        )

    def get_render_state_unsafe(self) -> RenderState:
        """Get extrapolated RenderState, asserting that state exists."""
        assert self._server_state is not None
        state = self.get_render_state()
        assert state is not None
        return state

    def apply_input(self, action: Any) -> None:
        """Placeholder for future client-side input prediction."""
        pass

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

        width = self._server_state.width
        height = self._server_state.height

        min_allowed = 0.5
        if new_y < min_allowed:
            new_y = min_allowed
        if new_x < min_allowed:
            new_x = min_allowed
        if new_y > height - min_allowed:
            new_y = height - min_allowed
        if new_x > width - min_allowed:
            new_x = width - min_allowed

        # Return new entity with extrapolated position
        return replace(entity, x=new_x, y=new_y)
