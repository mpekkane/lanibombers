from game_engine.map_loader import load_map
from game_engine.random_map_generator import RandomMapGenerator
from game_engine.spawn_points import get_spawn_points, SpawnType
import random
from pathlib import Path
from tqdm import tqdm


def main():
    trials = 10
    successes = 0
    success_map = 0
    success_rnd = 0
    # spawntype = SpawnType.TRUE_RANDOM
    # spawntype = SpawnType.UNIFORM_DIST_RANDOM
    spawntype = SpawnType.EDGES

    for _ in tqdm(range(trials)):
        # print("-"*80)
        num_players = random.randint(4, 16)
        r = random.random()
        map = False
        if r > 0.5:
            maps_dir = Path("assets/maps")

            map_files = [p for p in maps_dir.iterdir() if p.is_file()]
            random_map = random.choice(map_files)
            # print(f"random map: {random_map}")
            map_data = load_map(str(random_map))
            map = True
        else:
            random_map_generator = RandomMapGenerator()
            map_data = random_map_generator.generate()

        pts = get_spawn_points(num_players, map_data, spawntype)

        # print(f"h: {map_data.height} w: {map_data.width}")
        # print(pts)

        success = len(pts) == num_players
        for p in pts:
            if not (
                p[0] >= 0
                and p[0] < map_data.height
                and p[1] >= 0
                and p[1] < map_data.width
            ):
                success = False
        if success:
            # print(success)
            successes += 1
            if map:
                success_map += 1
            else:
                success_rnd += 1

    print(f"Trial N={trials} SpawnType={spawntype}")
    print(f"Random map successes: {success_rnd}")
    print(f"Predef map successes: {success_map}")
    print(f"Total successes: {successes}/{trials}")


if __name__ == "__main__":
    main()
