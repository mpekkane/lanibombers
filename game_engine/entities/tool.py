from dataclasses import dataclass
from enum import Enum

from game_engine.entities.pickup import Pickup, PickupType


class ToolType(Enum):
    SMALL_PICK = 'smallpick'
    BIG_PICK = 'bigpick'
    DRILL = 'drill'
    MEDPACK = 'medpack'


# Dig power bonus for each tool type
TOOL_DIG_POWER = {
    ToolType.SMALL_PICK: 1,
    ToolType.BIG_PICK: 3,
    ToolType.DRILL: 5,
    ToolType.MEDPACK: 0,
}


@dataclass(kw_only=True)
class Tool(Pickup):
    """Tool item that can be picked up to increase dig power."""
    tool_type: ToolType

    def __post_init__(self):
        self.pickup_type = PickupType.TOOL
        self.dig_power = TOOL_DIG_POWER[self.tool_type]
