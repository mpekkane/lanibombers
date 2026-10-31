from itertools import groupby
import numpy as np


def encode(input: np.ndarray, big: bool = False):
    return _RLE_encode(input, big).tobytes()


def decode(input: bytes, big: bool = False):
    if big:
        dtype = np.uint16
    else:
        dtype = np.uint8

    return _RLE_decode(np.frombuffer(input, dtype=dtype))


def _RLE_encode(input: np.ndarray, big: bool):
    if input.ndim > 1:
        input = input.flatten()
    output = []

    if big:
        dtype = np.uint16
    else:
        dtype = np.uint8

    for char, group in groupby(input):
        count = len(list(group))
        output.append(dtype(char))
        output.append(dtype(count))

    return np.array(output)


def _RLE_decode(input: np.ndarray):
    assert input.ndim == 1
    assert len(input) % 2 == 0
    vals = input[::2]
    counts = input[1::2]
    tot_len = counts.sum()
    output = np.zeros(tot_len, dtype=np.uint8)

    place = 0
    for val, count in zip(vals, counts):
        i_count = int(count)
        output[place:place + i_count] = val
        place += i_count

    return output


def main():
    files = [
        ("/home/matti/code/lanibombers/dbg_tilemap.npy", False),
        ("/home/matti/code/lanibombers/dbg_explosions.npy", True)
    ]

    for file, big in files:
        print("-" * 80)
        arr = np.load(file)
        en = encode(arr, big)
        de = decode(en, big).reshape(arr.shape)

        print(len(en))
        print(len(arr.tobytes()))

        print(np.all(arr == de))


if __name__ == "__main__":

    main()
