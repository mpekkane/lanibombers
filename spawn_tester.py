from game_engine.map_loader import load_map
from game_engine.random_map_generator import RandomMapGenerator
from game_engine.spawn_points import get_spawn_points, SpawnType


def main():
    type = 1
    num_players = 7

    if type == 1:
        map_data = load_map("/home/matti/code/lanibombers/assets/maps/ANZULABY.MNE")
    else:
        random_map_generator = RandomMapGenerator()
        map_data = random_map_generator.generate()

    pts = get_spawn_points(num_players, map_data, SpawnType.TRUE_RANDOM)
    print(pts)


if __name__ == "__main__":
    main()
