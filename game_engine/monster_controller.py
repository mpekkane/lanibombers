from __future__ import annotations

import threading
from typing import Optional, TYPE_CHECKING

from game_engine.agent_state import Action
from game_engine.clock import Clock
from game_engine.entities.dynamic_entity import Direction, EntityType
from game_engine.entities.bomb import Bomb, BombType
from game_engine.input_queue import InputCommand
from game_engine.monster_ai import MonsterAI, MONSTER_AI_MAP
from game_engine.render_state import RenderState
from game_engine.utils import xy_to_tile

if TYPE_CHECKING:
    from game_engine.entities.dynamic_entity import DynamicEntity
    from game_engine.game_engine import GameEngine

THINK_INTERVAL = 0.2  # seconds between AI ticks

# Map Action enum values to Direction enum values
_ACTION_TO_DIRECTION = {
    Action.UP: Direction.UP,
    Action.DOWN: Direction.DOWN,
    Action.LEFT: Direction.LEFT,
    Action.RIGHT: Direction.RIGHT,
}


class MonsterController:
    """Thread wrapper that drives a single monster's AI."""

    def __init__(self, monster: DynamicEntity, engine: GameEngine) -> None:
        self.monster = monster
        self.engine = engine
        self.ai: MonsterAI = MONSTER_AI_MAP[monster.entity_type]()
        self._state: Optional[RenderState] = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def push_state(self, state: RenderState) -> None:
        """Store the latest render state (drops old states)."""
        with self._lock:
            self._state = state

    def _pop_state(self) -> Optional[RenderState]:
        """Retrieve and clear the latest render state."""
        with self._lock:
            state = self._state
            self._state = None
            return state

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(
            target=self._run,
            name=f"monster-{self.monster.entity_type.value}-{self.monster.id}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _run(self) -> None:
        while self._running:
            Clock.sleep(THINK_INTERVAL)
            if not self._running:
                break
            if self.monster.state == "dead":
                continue

            state = self._pop_state()
            if state is None:
                continue

            action = self.ai.think(state)
            if action is not None:
                self._execute_action(action)

    def _execute_action(self, action: Action) -> None:
        """Execute an AI action via the input queue."""
        if self.monster.state == "dead":
            return

        now = Clock.now()

        if action.is_move():
            if action == Action.STOP:
                self.monster.state = "idle"
            else:
                direction = _ACTION_TO_DIRECTION[action]
                # Redundant direction guard (same as on_control)
                if (
                    self.monster.direction == direction
                    and self.monster.state == "walk"
                ):
                    return
                self.monster.direction = direction
                self.monster.state = "walk"
            self.engine.input_queue.submit(
                InputCommand(entity=self.monster, action=action, timestamp=now)
            )
        elif action == Action.FIRE:
            # Only grenade monsters can fire
            if self.monster.entity_type != EntityType.GRENADEMONSTER:
                return
            vx, vy = xy_to_tile(self.monster.x, self.monster.y)
            bomb = Bomb(
                x=vx,
                y=vy,
                bomb_type=BombType.GRENADE,
                placed_at=now,
                owner_id=self.monster.id,
                direction=self.monster.direction,
            )
            self.engine.input_queue.submit(
                InputCommand(entity=self.monster, action=action, timestamp=now, bomb=bomb)
            )
