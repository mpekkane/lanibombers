from __future__ import annotations

from typing import Optional

from game_engine.agent_state import Action
from game_engine.monster_ai.base import MonsterAI
from game_engine.render_state import RenderState


class FurrymanAI(MonsterAI):
    def think(self, state: RenderState, state_updated: bool) -> Optional[Action]:
        return None
