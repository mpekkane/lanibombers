from game_engine.entities import Direction, EntityType


# Tile names grouped by type
EMPTY_TILE_NAMES = {
    'empty',
    'boulder',
    'landmine',
    'crate',
    'smallpick',
    'bigpick',
    'drill',
    'gold_shield',
    'gold_egg',
    'gold_coins',
    'gold_bracelet',
    'gold_bar',
    'gold_cross',
    'gold_sceptre',
    'gold_ruby',
    'gold_crown',
    'tunnel',
    'crackerbarrel',
}

BEDROCK_TILE_NAMES = {'bedrock1', 'bedrock2', 'bedrock3', 'bedrock4'}
DIRT_TILE_NAMES = {'dirt1', 'dirt2', 'dirt3'}

# Death sprites
PLAYER_DEATH_SPRITE = 'blood'
MONSTER_DEATH_SPRITE = 'blood_green'


# Map tile IDs to sprite names
TILE_DICTIONARY = {
    # Basic terrain
    48: 'empty',
    49: 'concrete',
    50: 'dirt1',
    51: 'dirt2',
    52: 'dirt3',
    53: 'gravel1',
    54: 'gravel2',
    55: 'bedrock_nw',
    56: 'bedrock_ne',
    57: 'bedrock_se',
    #
    #
    65: 'bedrock_sw',
    66: 'boulder',
    67: 'bedrock1',
    68: 'bedrock2',
    69: 'bedrock3',
    70: 'bedrock4',
    #
    101: 'landmine',
    #
    #
    108: 'securitydoor',
    109: 'medpack',
    #
    111: 'bioslime',
    112: 'rock2',
    113: 'rock1',
    #
    #
    121: 'crate',
    #
    #
    143: 'smallpick',
    144: 'bigpick',
    145: 'drill',
    146: 'gold_shield',
    147: 'gold_egg',
    148: 'gold_coins',
    149: 'gold_bracelet',
    150: 'gold_bar',
    151: 'gold_cross',
    152: 'gold_sceptre',
    153: 'gold_ruby',
    154: 'gold_crown',
    155: 'urethane_block',
    156: 'tunnel',
    #
    #
    164: 'crackerbarrel',
    #
    #
    172: 'brics1',
    #
    #
    180: 'doorswitch_red',
}

# Get the tile ID for 'empty' from the dictionary
EMPTY_TILE_ID = next(tile_id for tile_id, name in TILE_DICTIONARY.items() if name == 'empty')

# Monster spawn tile definitions
# Each monster type has 4 consecutive tile IDs for directions: right, left, up, down
MONSTER_SPAWN_TILES = {
    71: (EntityType.FURRYMAN, Direction.RIGHT),
    72: (EntityType.FURRYMAN, Direction.LEFT),
    73: (EntityType.FURRYMAN, Direction.UP),
    74: (EntityType.FURRYMAN, Direction.DOWN),
    75: (EntityType.GRENADEMONSTER, Direction.RIGHT),
    76: (EntityType.GRENADEMONSTER, Direction.LEFT),
    77: (EntityType.GRENADEMONSTER, Direction.UP),
    78: (EntityType.GRENADEMONSTER, Direction.DOWN),
    79: (EntityType.SLIME, Direction.RIGHT),
    80: (EntityType.SLIME, Direction.LEFT),
    81: (EntityType.SLIME, Direction.UP),
    82: (EntityType.SLIME, Direction.DOWN),
    83: (EntityType.ALIEN, Direction.RIGHT),
    84: (EntityType.ALIEN, Direction.LEFT),
    85: (EntityType.ALIEN, Direction.UP),
    86: (EntityType.ALIEN, Direction.DOWN),
}
