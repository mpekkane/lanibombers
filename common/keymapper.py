import arcade
import re
from typing import Tuple, Optional
from common.config_reader import ConfigReader
from pynput import keyboard


def map_keys(config: ConfigReader) -> Tuple[
    int,
    int,
    int,
    int,
    int,
    int,
    int,
    int
]:
    up = config.get_config_mandatory("up")
    down = config.get_config_mandatory("down")
    left = config.get_config_mandatory("left")
    right = config.get_config_mandatory("right")
    fire = config.get_config_mandatory("fire")
    stop = config.get_config_mandatory("stop")
    choose = config.get_config_mandatory("choose")
    remote = config.get_config_mandatory("remote")

    keybind_up = parse_arcade_key(up)
    keybind_down = parse_arcade_key(down)
    keybind_left = parse_arcade_key(left)
    keybind_right = parse_arcade_key(right)
    keybind_fire = parse_arcade_key(fire)
    keybind_stop = parse_arcade_key(stop)
    keybind_choose = parse_arcade_key(choose)
    keybind_remote = parse_arcade_key(remote)

    return (
        keybind_up,
        keybind_down,
        keybind_left,
        keybind_right,
        keybind_fire,
        keybind_stop,
        keybind_choose,
        keybind_remote,
    )


def parse_arcade_key(name: str) -> int:
    """
    Convert a human-readable key string like:
        "l shift", "left shift", "up", "space", "a"
    into the corresponding arcade.key constant.
    """

    # Normalize string
    key = name.strip().lower()
    key = re.sub(r"[ \-]+", "_", key)  # replace spaces/hyphens with underscore

    # Manual aliases
    aliases = {}

    for base in ["ctrl", "shift", "alt", "super", "meta"]:
        for side, prefix in [("left", "L"), ("right", "R")]:
            key_const = f"{prefix}{base.upper()}"

            variants = {
                f"{prefix.lower()}{base}",       # lctrl
                f"{base}_{prefix.lower()}",      # ctrl_l
                f"{prefix.lower()}_{base}",      # l_ctrl
                f"{base}_{side}",                # ctrl_left
                f"{side}_{base}",                # left_ctrl
                f"{base}{prefix.lower()}",       # ctrll
                f"{side}{base}",                 # leftctrl
                f"{base}{side}",                 # ctrlleft
            }

            for v in variants:
                aliases[v] = key_const

    # Common extras
    aliases.update({
        "esc": "ESCAPE",
        "return": "ENTER",
    })

    # First try alias
    if key in aliases:
        key_name = aliases[key]
    else:
        key_name = key.upper()

    # Try to fetch from arcade.key
    try:
        return getattr(arcade.key, key_name)
    except AttributeError:
        raise ValueError(f"Unknown arcade key: '{name}'")


def arcade_key_to_string(key_code: int) -> Optional[str]:
    """
    Convert an arcade key integer back into a string
    that parse_arcade_key() can understand.
    """

    # Find matching constant name in arcade.key
    for attr in dir(arcade.key):
        if attr.isupper():
            if getattr(arcade.key, attr) == key_code:
                name = attr.lower()

                # KEY_1 → 1
                if name.startswith("key_"):
                    return name[4:]

                return name

    return None


def pynput_to_arcade_key(key: keyboard.Key | keyboard.KeyCode) -> int | None:
    """
    Convert a pynput key event key into an arcade key code (int).

    Returns:
        int  -> arcade key code (e.g. arcade.key.UP)
        None -> if the key can't be mapped (unknown / platform-specific)
    """

    # 1) Character keys (letters, digits, punctuation) come as KeyCode
    if isinstance(key, keyboard.KeyCode):
        ch = key.char
        if not ch:
            return None

        # Arcade's key constants for letters are uppercase: arcade.key.A, etc.
        # Digits are arcade.key.KEY_0..KEY_9
        # Common punctuation often exists too (e.g. SPACE, COMMA) but varies.
        if "a" <= ch.lower() <= "z":
            return getattr(arcade.key, ch.upper())

        if "0" <= ch <= "9":
            return getattr(arcade.key, f"KEY_{ch}")

        # Space sometimes comes as KeyCode(' ') depending on OS/app focus
        if ch == " ":
            return arcade.key.SPACE

        # Basic punctuation you might care about (add more if you need)
        punct_map = {
            ",": arcade.key.COMMA,
            ".": arcade.key.PERIOD,
            "/": arcade.key.SLASH,
            "\\": arcade.key.BACKSLASH,
            ";": arcade.key.SEMICOLON,
            "'": arcade.key.APOSTROPHE,
            "[": arcade.key.BRACKETLEFT,
            "]": arcade.key.BRACKETRIGHT,
            "-": arcade.key.MINUS,
            "=": arcade.key.EQUAL,
            "`": arcade.key.GRAVE,
        }
        return punct_map.get(ch, None)

    # 2) Special keys come as keyboard.Key
    if isinstance(key, keyboard.Key):
        special_map = {
            keyboard.Key.up: arcade.key.UP,
            keyboard.Key.down: arcade.key.DOWN,
            keyboard.Key.left: arcade.key.LEFT,
            keyboard.Key.right: arcade.key.RIGHT,
            keyboard.Key.space: arcade.key.SPACE,
            keyboard.Key.enter: arcade.key.ENTER,
            keyboard.Key.tab: arcade.key.TAB,
            keyboard.Key.backspace: arcade.key.BACKSPACE,
            keyboard.Key.esc: arcade.key.ESCAPE,
            keyboard.Key.delete: arcade.key.DELETE,
            keyboard.Key.insert: arcade.key.INSERT,
            keyboard.Key.home: arcade.key.HOME,
            keyboard.Key.end: arcade.key.END,
            keyboard.Key.page_up: arcade.key.PAGEUP,
            keyboard.Key.page_down: arcade.key.PAGEDOWN,
            keyboard.Key.shift: arcade.key.LSHIFT,  # generic -> pick left
            keyboard.Key.shift_l: arcade.key.LSHIFT,
            keyboard.Key.shift_r: arcade.key.RSHIFT,
            keyboard.Key.ctrl: arcade.key.LCTRL,  # generic -> pick left
            keyboard.Key.ctrl_l: arcade.key.LCTRL,
            keyboard.Key.ctrl_r: arcade.key.RCTRL,
            keyboard.Key.alt: arcade.key.LALT,  # generic -> pick left
            keyboard.Key.alt_l: arcade.key.LALT,
            keyboard.Key.alt_r: arcade.key.RALT,
            keyboard.Key.caps_lock: arcade.key.CAPSLOCK,
            # Media keys / cmd / menu can be platform-specific; map if you need them
            # keyboard.Key.cmd: arcade.key.LSUPER,
            # keyboard.Key.cmd_l: arcade.key.LSUPER,
            # keyboard.Key.cmd_r: arcade.key.RSUPER,
            # keyboard.Key.menu: arcade.key.MENU,
        }

        # Function keys
        if hasattr(keyboard.Key, "f1"):
            fkeys = {
                keyboard.Key.f1: arcade.key.F1,
                keyboard.Key.f2: arcade.key.F2,
                keyboard.Key.f3: arcade.key.F3,
                keyboard.Key.f4: arcade.key.F4,
                keyboard.Key.f5: arcade.key.F5,
                keyboard.Key.f6: arcade.key.F6,
                keyboard.Key.f7: arcade.key.F7,
                keyboard.Key.f8: arcade.key.F8,
                keyboard.Key.f9: arcade.key.F9,
                keyboard.Key.f10: arcade.key.F10,
                keyboard.Key.f11: arcade.key.F11,
                keyboard.Key.f12: arcade.key.F12,
            }
            if key in fkeys:
                return fkeys[key]

        return special_map.get(key, None)

    return None
