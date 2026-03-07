from typing import List


def room1():
    name = "room1"
    rows = [
        [49, 49,  49,  49,  49],
        [49, 154, 48,  154, 49],
        [49, 48,  145, 48,  49],
        [49, 154, 48,  154, 49],
        [49, 49,  48,  49,  49],
    ]
    return rows, name


def create_room(path: str, tiles: List[List[int]], name: str):
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


def main():
    path = "common/room_templates"
    rows, name = room1()
    create_room(path, rows, name)


if __name__ == "__main__":
    main()
