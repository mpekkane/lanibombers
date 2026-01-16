from enum import IntEnum


class Action(IntEnum):
    UP = 1
    DOWN = 2
    LEFT = 3
    RIGHT = 4
    STOP = 5
    FIRE = 6
    CHOOSE = 7
    REMOTE = 8

    def is_move(self) -> bool:
        return (
            self == Action.UP
            or self == Action.DOWN
            or self == Action.RIGHT
            or self == Action.LEFT
            or self == Action.STOP
        )
