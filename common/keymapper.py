from typing import Union
from pynput import keyboard

_KEY_MAP = {
    "up": keyboard.Key.up,
    "down": keyboard.Key.down,
    "left": keyboard.Key.left,
    "right": keyboard.Key.right,
    "enter": keyboard.Key.enter,
    "space": keyboard.Key.space,
    "esc": keyboard.Key.esc,
    "tab": keyboard.Key.tab,
    "shift_r": keyboard.Key.shift_r,
    "shift_l": keyboard.Key.shift_l,
    "ctrl_r": keyboard.Key.ctrl_r,
    "ctrl_l": keyboard.Key.ctrl_l,
    "alt": keyboard.Key.alt,
}


def get_key(key: str) -> keyboard.Key:
    try:
        return _KEY_MAP[key]
    except KeyError:
        return key


def check_input(pressed: Union[keyboard.Key, keyboard.KeyCode], mapped: str):
    if isinstance(pressed, keyboard.Key):
        return pressed == get_key(mapped)
    else:
        return pressed.char == mapped
