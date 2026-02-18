import arcade
import re
from typing import Tuple
from common.config_reader import ConfigReader


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
