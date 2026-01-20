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
    157: 'c4_tile',
    #
    #
    164: 'crackerbarrel',
    #
    #
    172: 'brics1',
    173: 'brics2',
    174: 'brics3',
    #
    #
    180: 'doorswitch_red',
}

# Tile ID groupings by type
BEDROCK_TILES = {55, 56, 57, 65, 67, 68, 69, 70}
BEDROCK_CORNER_TILES = {55, 56, 57, 65}
DIRT_TILES = {50, 51, 52, 53, 54}  # Includes gravel
CONCRETE_TILES = {49}
URETHANE_TILES = {155}
BIOSLIME_TILES = {111}
BOULDER_TILES = {66, 112, 113}
BRICKS_TILES = {172}
SWITCH_TILES = {180}
SECURITY_DOOR_TILES = {108}
TUNNEL_TILES = {156}
C4_TILES = {157}

# Get tile IDs from the dictionary
EMPTY_TILE_ID = next(tile_id for tile_id, name in TILE_DICTIONARY.items() if name == 'empty')
ROCK1_TILE_ID = next(tile_id for tile_id, name in TILE_DICTIONARY.items() if name == 'rock1')
ROCK2_TILE_ID = next(tile_id for tile_id, name in TILE_DICTIONARY.items() if name == 'rock2')
BRICS2_TILE_ID = next(tile_id for tile_id, name in TILE_DICTIONARY.items() if name == 'brics2')
BRICS3_TILE_ID = next(tile_id for tile_id, name in TILE_DICTIONARY.items() if name == 'brics3')
C4_TILE_ID = next(tile_id for tile_id, name in TILE_DICTIONARY.items() if name == 'c4_tile')
URETHANE_TILE_ID = next(tile_id for tile_id, name in TILE_DICTIONARY.items() if name == 'urethane_block')
DIRT_TILE_ID = next(tile_id for tile_id in DIRT_TILES)
BOULDER_TILE_ID = next(tile_id for tile_id in BOULDER_TILES)

CONCRETE_TILE_ID = 49
BIOSLIME_TILE_ID = 111
BRICKS_TILE_ID = 172
SWITCH_TILE_ID = 180
SECURITY_DOOR_ID = 108
TUNNEL_TILE_ID = 156

# Monster spawn tile definitions (tile_id -> (entity_type, direction))
MONSTER_SPAWN_TILES = {
    71: ('furryman', 'right'),
    72: ('furryman', 'left'),
    73: ('furryman', 'up'),
    74: ('furryman', 'down'),
    75: ('grenademonster', 'right'),
    76: ('grenademonster', 'left'),
    77: ('grenademonster', 'up'),
    78: ('grenademonster', 'down'),
    79: ('slime', 'right'),
    80: ('slime', 'left'),
    81: ('slime', 'up'),
    82: ('slime', 'down'),
    83: ('alien', 'right'),
    84: ('alien', 'left'),
    85: ('alien', 'up'),
    86: ('alien', 'down'),
}

# Treasure tile definitions (tile_id -> treasure_type)
TREASURE_TILES = {
    146: 'gold_shield',
    147: 'gold_egg',
    148: 'gold_coins',
    149: 'gold_bracelet',
    150: 'gold_bar',
    151: 'gold_cross',
    152: 'gold_sceptre',
    153: 'gold_ruby',
    154: 'gold_crown',
}

# Tool tile definitions (tile_id -> tool_type)
TOOL_TILES = {
    143: 'smallpick',
    144: 'bigpick',
    145: 'drill',
    109: 'medpack',
}
