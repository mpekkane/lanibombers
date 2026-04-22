from typing import List

from common.tile_dictionary import TILE_DICTIONARY

TILE_NAME_TO_ID = {name: tile_id for tile_id, name in TILE_DICTIONARY.items()}


def t(name: str) -> int:
    return TILE_NAME_TO_ID[name]


C = t("concrete")
E = t("empty")
D = t("drill")
G = t("gold_crown")
B = t("bedrock1")
S = t("bioslime")
T = t("tunnel")
R = t("gold_ruby")


def room1():
    name = "room1"
    rows = [
        [C, C, C, C, C],
        [C, G, E, G, C],
        [C, E, D, E, C],
        [C, G, E, G, C],
        [C, C, E, C, C],
    ]
    return rows, name


def slime_room():
    name = "slime_room"
    rows = [
        [B, B, B, B, B, B],
        [B, S, E, E, E, B],
        [B, B, B, B, E, B],
        [B, E, E, E, E, B],
        [B, E, B, B, B, B],
        [B, E, E, E, E, E],
    ]
    return rows, name


def ruby_teleport_room():
    name = "ruby_teleport_room"
    rows = [
        [B, C, C, C, B],
        [C, C, R, C, C],
        [C, R, T, R, C],
        [C, C, R, C, C],
        [B, C, C, C, B],
    ]
    return rows, name


def _rotate_90_cw(tiles: List[List[int]]) -> List[List[int]]:
    """Rotate a 2D tile grid 90 degrees clockwise."""
    height = len(tiles)
    width = len(tiles[0])
    return [[tiles[height - 1 - r][c] for r in range(height)] for c in range(width)]


def _write_room_file(path: str, tiles: List[List[int]], name: str):
    height = len(tiles)
    widths: List[int] = []
    for h in range(height):
        widths.append(len(tiles[h]))
    assert all(x == widths[0] for x in widths)
    width = widths[0]

    with open(f"{path}/{name}.MNE", "wb") as f:
        f.write(str(width).encode("utf-8"))
        f.write(b"\r\n")
        f.write(str(height).encode("utf-8"))
        f.write(b"\r\n")
        for i, row in enumerate(tiles):
            for tile in row:
                f.write(tile.to_bytes(1, "big"))
            if i < height - 1:
                f.write(b"\r\n")


def create_room(path: str, tiles: List[List[int]], name: str):
    """Write the room file along with 90, 180, and 270 degree rotated copies."""
    rotated = tiles
    for suffix, _ in [("", 0), ("_90", 90), ("_180", 180), ("_270", 270)]:
        _write_room_file(path, rotated, name + suffix)
        rotated = _rotate_90_cw(rotated)


def main():
    path = "common/room_templates"
    for room_func in (room1, slime_room, ruby_teleport_room):
        rows, name = room_func()
        create_room(path, rows, name)


if __name__ == "__main__":
    main()
