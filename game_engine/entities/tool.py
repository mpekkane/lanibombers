from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

from game_engine.entities.pickup import Pickup, PickupType
from cfg.tile_dictionary import (
    MEDPACK_ID,
    CRATE_ID,
    SMALLPICK_ID,
    BIGPICK_ID,
    DRILL_ID,
)


class ToolType(Enum):
    SMALL_PICK = 'smallpick'
    BIG_PICK = 'bigpick'
    DRILL = 'drill'
    MEDPACK = 'medpack'
    CRATE = 'crate'


# Dig power bonus for each tool type
TOOL_DIG_POWER = {
    ToolType.SMALL_PICK: 1,
    ToolType.BIG_PICK: 3,
    ToolType.DRILL: 5,
    ToolType.MEDPACK: 0,
    ToolType.CRATE: 0,
}


@dataclass(kw_only=True)
class Tool(Pickup):
    """Tool item that can be picked up to increase dig power."""
    tool_type: ToolType

    @staticmethod
    def create(x: int, y: int, tool_type: ToolType) -> Tool:
        if tool_type == ToolType.MEDPACK:
            return Tool(x=x, y=y, tool_type=ToolType.MEDPACK, visual_id=MEDPACK_ID)
        elif tool_type == ToolType.SMALL_PICK:
            return Tool(x=x, y=y, tool_type=ToolType.SMALL_PICK, visual_id=SMALLPICK_ID)
        elif tool_type == ToolType.BIG_PICK:
            return Tool(x=x, y=y, tool_type=ToolType.BIG_PICK, visual_id=BIGPICK_ID)
        elif tool_type == ToolType.DRILL:
            return Tool(x=x, y=y, tool_type=ToolType.DRILL, visual_id=DRILL_ID)
        elif tool_type == ToolType.CRATE:
            return Tool(x=x, y=y, tool_type=ToolType.CRATE, visual_id=CRATE_ID)

    def __post_init__(self):
        self.pickup_type = PickupType.TOOL
        self.dig_power = TOOL_DIG_POWER[self.tool_type]
