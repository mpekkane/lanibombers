"""Generates perlin noise"""

from typing import Tuple
import numpy as np
import random
from tqdm import tqdm


def ed(x1: np.ndarray, x2: np.ndarray) -> float:
    """Euclidean distance"""
    return np.sqrt((x1[0] - x2[0]) ** 2 + (x1[1] - x2[1]) ** 2)


def disp(x1: np.ndarray, x2: np.ndarray) -> np.ndarray:
    """Displacement vector"""
    return (x1 - x2).astype(np.float32)


def gradient(angle: float) -> np.ndarray:
    """Create gradient vector from angle"""
    x = np.cos(angle)
    y = np.sin(angle)
    return np.array((x, y)).astype(np.float32)


def lerp(t: float, x1: float, x2: float) -> float:
    """Linear interpolation"""
    return x1 + t * (x2 - x1)


def fade(t: float):
    """Original smoothing from Perlin"""
    return ((6.0 * t - 15.0) * t + 10.0) * t * t * t


def perlin_noise(x_r: int, y_r: int, g: int) -> np.ndarray:
    """Generate perlin noise

    Args:
        x_r (int): width of the noise
        y_r (int): height of the noise
        g (int): "feature size" of the noise, i.e. the outer grid size

    Returns:
        np.ndarray: noise map
    """
    output = np.zeros((x_r, y_r))
    grid = np.zeros((x_r // g + 2, y_r // g + 2))
    for gx in range(grid.shape[0]):
        for gy in range(grid.shape[1]):
            grid[gx, gy] = random.random() * 2 * np.pi

    for x in tqdm(range(x_r), desc="generating map...", leave=False):
        for y in range(y_r):
            grid_l = x // g
            grid_r = x // g + 1
            grid_u = y // g
            grid_d = y // g + 1

            point = np.array((x, y))
            corner_1 = np.array((grid_l, grid_d)) * g
            corner_2 = np.array((grid_l, grid_u)) * g
            corner_3 = np.array((grid_r, grid_d)) * g
            corner_4 = np.array((grid_r, grid_u)) * g

            displacement_1 = disp(point, corner_1) / g
            displacement_2 = disp(point, corner_2) / g
            displacement_3 = disp(point, corner_3) / g
            displacement_4 = disp(point, corner_4) / g
            gradient_1 = gradient(grid[grid_l, grid_d])
            gradient_2 = gradient(grid[grid_l, grid_u])
            gradient_3 = gradient(grid[grid_r, grid_d])
            gradient_4 = gradient(grid[grid_r, grid_u])
            dot_1 = np.dot(displacement_1, gradient_1)
            dot_2 = np.dot(displacement_2, gradient_2)
            dot_3 = np.dot(displacement_3, gradient_3)
            dot_4 = np.dot(displacement_4, gradient_4)

            fade_x = fade((x - grid_l*g)/g)
            fade_y = fade((y - grid_u*g)/g)
            lerp_1 = lerp(fade_y, dot_2, dot_1)
            lerp_2 = lerp(fade_y, dot_4, dot_3)
            lerp_3 = lerp(fade_x, lerp_1, lerp_2)

            output[x, y] = lerp_3

    return output


def threshold_map(perlin: np.ndarray, th: float) -> np.ndarray:
    """Binary classification for bedrock/dirt"""
    pos = perlin > th
    out = np.zeros_like(perlin)
    out[pos] = 1
    return out


def generate_and_threshold(
    x, y, feature_size, threshold
) -> Tuple[np.ndarray, np.ndarray]:
    """Generate noise and threshold into usable map"""
    perlin = perlin_noise(x, y, feature_size)
    tr = threshold_map(perlin, threshold)
    return perlin, tr


# def test_perlin():
#     import matplotlib.pyplot as plt
#     x = 64
#     y = 45
#     feature_sizes = [2, 3, 5, 10, 20, 50]

#     # thresholds = [0.05, 0.1, 0.15, 0.2]
#     fig, ax = plt.subplots(len(feature_sizes), 2)
#     for i, X in enumerate(feature_sizes):
#         perlin, th = generate_and_threshold(x, y, X, 0.1)
#         ax[i, 0].imshow(perlin)
#         ax[i, 1].imshow(th)
#         print(f"generated {i}: {X}")
#     plt.show()


# if __name__ == "__main__":
#     test_perlin()
