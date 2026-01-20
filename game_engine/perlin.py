import matplotlib.pyplot as plt
import numpy as np
import random
from tqdm import tqdm

def ed(x1: np.ndarray, x2: np.ndarray) -> float:
    return np.sqrt((x1[0] - x2[0]) ** 2 + (x1[1] - x2[1]) ** 2)


def disp(x1: np.ndarray, x2: np.ndarray) -> np.ndarray:
    return (x1 - x2).astype(np.float32)


def gradient(angle: float) -> np.ndarray:
    x = np.cos(angle)
    y = np.sin(angle)
    return np.array((x, y)).astype(np.float32)


def lerp(t: float, x1: float, x2: float) -> float:
    return x1 + t * (x2 - x1)


def fade(t: float):
    return ((6.0 * t - 15.0) * t + 10.0) * t * t * t


def perlin_noise(x_r: int, y_r: int, g: int) -> np.ndarray:
    output = np.zeros((x_r * g, y_r * g))
    grid = np.zeros((x_r + 1, y_r + 1))
    for gx in range(grid.shape[0]):
        for gy in range(grid.shape[1]):
            grid[gx, gy] = random.random() * 2 * np.pi

    for x in tqdm(range(x_r), desc="generating map...", leave=False):
        for y in range(y_r):
            for xf in range(g):
                for yf in range(g):
                    grid_l = x
                    grid_r = x + 1
                    grid_u = y
                    grid_d = y + 1

                    point = np.array((x + xf / g, y + yf / g))
                    corner_1 = np.array((grid_l, grid_d))
                    corner_2 = np.array((grid_l, grid_u))
                    corner_3 = np.array((grid_r, grid_d))
                    corner_4 = np.array((grid_r, grid_u))

                    displacement_1 = disp(point, corner_1)
                    displacement_2 = disp(point, corner_2)
                    displacement_3 = disp(point, corner_3)
                    displacement_4 = disp(point, corner_4)
                    gradient_1 = gradient(grid[corner_1[0], corner_1[1]])
                    gradient_2 = gradient(grid[corner_2[0], corner_2[1]])
                    gradient_3 = gradient(grid[corner_3[0], corner_3[1]])
                    gradient_4 = gradient(grid[corner_4[0], corner_4[1]])
                    dot_1 = np.dot(displacement_1, gradient_1)
                    dot_2 = np.dot(displacement_2, gradient_2)
                    dot_3 = np.dot(displacement_3, gradient_3)
                    dot_4 = np.dot(displacement_4, gradient_4)

                    fade_x = fade(xf / g)
                    fade_y = fade(yf / g)
                    lerp_1 = lerp(fade_y, dot_2, dot_1)
                    lerp_2 = lerp(fade_y, dot_4, dot_3)
                    lerp_3 = lerp(fade_x, lerp_1, lerp_2)

                    output[x * g + xf, y * g + yf] = lerp_3

    return output


def threshold_map(perlin: np.ndarray, th: float) -> np.ndarray:
    pos = perlin > th
    out = np.zeros_like(perlin)
    out[pos] = 1
    return out


def generate_and_threshold(feature_resolution, aspect, fidelity, threshold):
    x = feature_resolution
    y = int(feature_resolution * aspect)
    perlin = perlin_noise(x, y, fidelity)
    tr = threshold_map(perlin, threshold)
    return perlin, tr


def test_perlin():
    feature_resolution = 3
    aspect = 1.5
    fidelity = 20
    thresholds = [0.05, 0.1, 0.15, 0.2]
    fig, ax = plt.subplots(len(thresholds), 2)
    for i, tr in enumerate(thresholds):
        perlin, th = generate_and_threshold(feature_resolution, aspect, fidelity, tr)
        ax[i, 0].imshow(perlin)
        ax[i, 1].imshow(th)
        print(f"generated {i}: {tr}")
    plt.show()


if __name__ == "__main__":
    test_perlin()
