
"""
Combined asset extractor for lanibombers.
Extracts all game assets from a ZIP file:
- SPY files -> PNG (sprites)
- PPM files -> PNG (PCX graphics)
- VOC files -> WAV (sounds)
- S3M files -> copy (music)
- MNE/MNL files -> copy (maps)
"""

import os
import sys
import zipfile
import wave
from PIL import Image
from io import BytesIO


# ============================================================================
# SPY Sprite Extractor
# ============================================================================

# Plane offsets for each SPY file: [p1_v, p1_h, p2_v, p2_h, p3_v, p3_h, p4_v, p4_h]
# v = vertical offset (rows), h = horizontal offset (bytes)
# Offsets are CUMULATIVE - each plane's offset is added to all previous
SPY_OFFSETS = {
    'TITLEBE':   [0, 0,  0, 0,  2, 51,  2, 51],
    'CODES':     [0, 0,  0, 5,  0, 5,   0, 57],
    'CONGRATU':  [0, 0,  0, 5,  0, 5,   1, 1],
    'EDITHELP':  [0, 0,  0, 55,  2, 31,   2, 31],
    'FINAL':     [0, 0,  0, 5,  0, 0,   0, 5],
    'GAMEOVER':  [0, 0,  0, 5,  0, 5,   0, 5],
    'HALLOFFA':  [0, 0,  0, 5,  0, 5,   0, 5],
    'IDENTIFW':  [0, 0,  0, 5,  0, 5,   0, 5],
    'INFO1':     [0, 0,  0, 0,  0, 0,   0, 5],
    'INFO2':     [0, 0,  0, 5,  0, 5,   0, 5],
    'INFO3':     [0, 0,  0, 5,  0, 5,   0, 5],
    'KEYS':      [0, 0,  0, 5,  0, 5,   2, 77],
    'LEVSELEC':  [0, 0,  0, 5,  0, 5,   0, 5],
    'MAIN3':     [0, 0,  0, 0,  0, 5,   0, 0],
    'MINEDI33':  [0, 0,  0, 5,  0, 5,   2, 39],
    'MINEDIT2':  [0, 0,  0, 5,  0, 5,   1, 37],
    'OPTIONS5':  [0, 0,  0, 0,  0, 0,   0, 0],
    'PLAYERS':   [0, 0,  0, 5,  0, 5,   0, 5],
    'SHAPET':    [0, 0,  0, 5,  0, 5,   0, 5],
    'SHOPPIC':   [0, 0,  0, 0,  0, 0,   0, 1],
    'SIKA':      [0, 0,  0, 70,  0, 0,   0, 0],
}

SPY_WIDTH = 640
SPY_HEIGHT = 480
SPY_PLANE_SIZE = SPY_WIDTH * SPY_HEIGHT // 8
SPY_ROW_BYTES = SPY_WIDTH // 8


def decode_spy_rle(data):
    """Decode RLE compressed SPY data"""
    output = []
    i = 0
    while i < len(data):
        if i + 2 < len(data) and data[i] == 0x01:
            pattern = data[i+1]
            count = data[i + 2]
            output.extend([pattern] * count)
            i += 3
        else:
            output.append(data[i])
            i += 1
    return output


def extract_spy(data, name):
    """Extract SPY sprite data to PIL Image"""
    palette_data = list(data[:768])
    sprite_data = data[768:]

    decoded = decode_spy_rle(sprite_data)

    if len(decoded) < SPY_PLANE_SIZE * 4:
        print(f"    Warning: Not enough data for {name}")
        return None

    output = [0] * (SPY_WIDTH * SPY_HEIGHT)

    # Get offsets for this file
    offsets = SPY_OFFSETS.get(name, [0, 0, 0, 0, 0, 0, 0, 0])

    # Calculate cumulative byte offsets
    cumulative_offset = 0
    plane_byte_offsets = []
    for plane in range(4):
        v_offset = offsets[plane * 2]
        h_offset = offsets[plane * 2 + 1]
        cumulative_offset += v_offset * SPY_ROW_BYTES + h_offset
        plane_byte_offsets.append(cumulative_offset)

    for plane in range(4):
        plane_start = plane * SPY_PLANE_SIZE + plane_byte_offsets[plane]
        bit_value = 1 << plane

        for byte_idx in range(SPY_PLANE_SIZE):
            src_idx = plane_start + byte_idx
            if src_idx >= len(decoded):
                break
            byte_val = decoded[src_idx]
            pixel_base = byte_idx * 8

            for bit in range(8):
                pixel_idx = pixel_base + bit
                if pixel_idx < SPY_WIDTH * SPY_HEIGHT:
                    if byte_val & (0x80 >> bit):
                        output[pixel_idx] |= bit_value

    img = Image.new('P', (SPY_WIDTH, SPY_HEIGHT))
    img.putpalette(palette_data)
    img.putdata(output)
    return img


# ============================================================================
# VOC Sound Converter
# ============================================================================

VOC_SAMPLE_RATE = 11025
VOC_BITS_PER_SAMPLE = 8
VOC_NUM_CHANNELS = 1


def convert_voc_to_wav(pcm_data):
    """Convert raw PCM data to WAV format, returns bytes"""
    output = BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setnchannels(VOC_NUM_CHANNELS)
        wav.setsampwidth(VOC_BITS_PER_SAMPLE // 8)
        wav.setframerate(VOC_SAMPLE_RATE)
        wav.writeframes(pcm_data)
    return output.getvalue()


# ============================================================================
# PCX Graphics Converter (PPM files are actually PCX)
# ============================================================================

def decode_pcx(data):
    """Decode PCX file and return PIL Image"""
    # Parse header
    xmin = data[4] | (data[5] << 8)
    ymin = data[6] | (data[7] << 8)
    xmax = data[8] | (data[9] << 8)
    ymax = data[10] | (data[11] << 8)

    width = xmax - xmin + 1
    height = ymax - ymin + 1

    num_planes = data[65]
    bytes_per_line = data[66] | (data[67] << 8)

    # Decode RLE-compressed image data (starts at byte 128)
    image_data = []
    i = 128
    total_bytes = bytes_per_line * num_planes * height

    while len(image_data) < total_bytes and i < len(data) - 769:
        byte = data[i]
        if byte >= 0xC0:
            count = byte & 0x3F
            i += 1
            if i < len(data):
                value = data[i]
                image_data.extend([value] * count)
        else:
            image_data.append(byte)
        i += 1

    # Get palette (at end of file for version 5)
    palette = None
    if len(data) >= 769 and data[-769] == 0x0C:
        palette = list(data[-768:])

    # Extract pixel data
    pixels = []
    for row in range(height):
        row_start = row * bytes_per_line
        row_data = image_data[row_start:row_start + width]
        pixels.extend(row_data)

    while len(pixels) < width * height:
        pixels.append(0)

    img = Image.new('P', (width, height))
    if palette:
        img.putpalette(palette)
    else:
        img.putpalette([i for i in range(256) for _ in range(3)])
    img.putdata(pixels[:width * height])
    return img


# ============================================================================
# Sprite Splitter
# ============================================================================

# Sprite definitions: (x, y, w, h, ox, oy, name)
# x, y = position in sprite units (1 unit = w x h pixels)
# w, h = size in pixels
# ox, oy = pixel offset for fine adjustment
# name = output filename
SPRITE_DEFS = [
    # (x, y, w, h, ox, oy, name)

    # Row 0 
    (0, 0, 10, 10, 0, 0, 'empty'),
    (1, 0, 10, 10, 0, 0, 'concrete'),
    (2, 0, 10, 10, 0, 0, 'dirt1'),
    (3, 0, 10, 10, 0, 0, 'dirt2'),
    (4, 0, 10, 10, 0, 0, 'dirt3'),
    (5, 0, 10, 10, 0, 0, 'gravel1'),
    (6, 0, 10, 10, 0, 0, 'gravel2'),
    (7, 0, 10, 10, 0, 0, 'bedrock_nw'),
    (8, 0, 10, 10, 0, 0, 'bedrock_ne'),
    (9, 0, 10, 10, 0, 0, 'bedrock_se'),
    (10, 0, 10, 10, 0, 0, 'bedrock_sw'),
    (11, 0, 10, 10, 0, 0, 'boulder'),
    (12, 0, 10, 10, 0, 0, 'bedrock1'),
    (13, 0, 10, 10, 0, 0, 'bedrock2'),
    (14, 0, 10, 10, 0, 0, 'bedrock3'),
    (15, 0, 10, 10, 0, 0, 'bedrock4'),
    (16, 0, 10, 10, 0, 0, 'player1_right_1'),
    (17, 0, 10, 10, 0, 0, 'player1_right_2'),
    (18, 0, 10, 10, 0, 0, 'player1_right_3'),
    (19, 0, 10, 10, 0, 0, 'player1_right_4'),
    (20, 0, 10, 10, 0, 0, 'player1_left_1'),
    (21, 0, 10, 10, 0, 0, 'player1_left_2'),
    (22, 0, 10, 10, 0, 0, 'player1_left_3'),
    (23, 0, 10, 10, 0, 0, 'player1_left_4'),
    (24, 0, 10, 10, 0, 0, 'player1_up_1'),
    (25, 0, 10, 10, 0, 0, 'player1_up_2'),
    (26, 0, 10, 10, 0, 0, 'player1_up_3'),
    (27, 0, 10, 10, 0, 0, 'player1_up_4'),
    (28, 0, 10, 10, 0, 0, 'player1_down_1'),
    (29, 0, 10, 10, 0, 0, 'player1_down_2'),
    (30, 0, 10, 10, 0, 0, 'player1_down_3'),
    (31, 0, 10, 10, 0, 0, 'player1_down_4'),

    # Row 1 
    (0, 1, 10, 10, 0, 0, 'smallbomb1'),
    (1, 1, 10, 10, 0, 0, 'bigbomb1'),
    (2, 1, 10, 10, 0, 0, 'dynamite1'),
    (3, 1, 10, 10, 0, 0, 'smallbarrel1'),
    (4, 1, 10, 10, 0, 0, 'bigbarrel1'),
    (5, 1, 10, 10, 0, 0, 'bigcrucifix'),
    (6, 1, 10, 10, 0, 0, 'urethane'),
    (7, 1, 10, 10, 0, 0, 'smallremote_player1'),
    (8, 1, 10, 10, 0, 0, 'bigremote_player1'),
    (9, 1, 10, 10, 0, 0, 'explosion'),
    (10, 1, 10, 10, 0, 0, 'smoke1'),
    (11, 1, 10, 10, 0, 0, 'smoke2'),
    (12, 1, 10, 10, 0, 0, 'smallremote_player2'),
    (13, 1, 10, 10, 0, 0, 'bigremote_player2'),
    (14, 1, 10, 10, 0, 0, 'landmine'),
    (15, 1, 10, 10, 0, 0, 'blood'),
    (16, 1, 10, 10, 0, 0, 'player2_right_1'),
    (17, 1, 10, 10, 0, 0, 'player2_right_2'),
    (18, 1, 10, 10, 0, 0, 'player2_right_3'),
    (19, 1, 10, 10, 0, 0, 'player2_right_4'),
    (20, 1, 10, 10, 0, 0, 'player2_left_1'),
    (21, 1, 10, 10, 0, 0, 'player2_left_2'),
    (22, 1, 10, 10, 0, 0, 'player2_left_3'),
    (23, 1, 10, 10, 0, 0, 'player2_left_4'),
    (24, 1, 10, 10, 0, 0, 'player2_up_1'),
    (25, 1, 10, 10, 0, 0, 'player2_up_2'),
    (26, 1, 10, 10, 0, 0, 'player2_up_3'),
    (27, 1, 10, 10, 0, 0, 'player2_up_4'),
    (28, 1, 10, 10, 0, 0, 'player2_down_1'),
    (29, 1, 10, 10, 0, 0, 'player2_down_2'),
    (30, 1, 10, 10, 0, 0, 'player2_down_3'),
    (31, 1, 10, 10, 0, 0, 'player2_down_4'),

    # Row 2 
    (0, 2, 10, 10, 0, 0, 'smallbomb2'),
    (1, 2, 10, 10, 0, 0, 'smallbomb3'),
    (2, 2, 10, 10, 0, 0, 'crate'),
    (3, 2, 10, 10, 0, 0, 'smallbarrel2'),
    (4, 2, 10, 10, 0, 0, 'bigbarrel2'),
    (5, 2, 10, 10, 0, 0, 'smallcrucifix'),
    (6, 2, 10, 10, 0, 0, 'bigbomb2'),
    (7, 2, 10, 10, 0, 0, 'bigbomb3'),
    (8, 2, 10, 10, 0, 0, 'dynamite2'),
    (9, 2, 10, 10, 0, 0, 'dynamite3'),
    (10, 2, 10, 10, 0, 0, 'smallpick'),
    (11, 2, 10, 10, 0, 0, 'bigpick'),
    (12, 2, 10, 10, 0, 0, 'drill'),
    (13, 2, 10, 10, 0, 0, 'gold_shield'),
    (14, 2, 10, 10, 0, 0, 'gold_egg'),
    (15, 2, 10, 10, 0, 0, 'gold_coins'),
    (16, 2, 10, 10, 0, 0, 'gold_bracelet'),
    (17, 2, 10, 10, 0, 0, 'gold_bar'),
    (18, 2, 10, 10, 0, 0, 'gold_cross'),
    (19, 2, 10, 10, 0, 0, 'gold_sceptre'),
    (20, 2, 10, 10, 0, 0, 'gold_ruby'),
    (21, 2, 10, 10, 0, 0, 'gold_crown'),
    (22, 2, 10, 10, 0, 0, 'urethane_block'),
    (23, 2, 10, 10, 0, 0, 'tunnel'),
    (24, 2, 10, 10, 0, 0, 'nuke1'),
    (25, 2, 10, 10, 0, 0, 'nuke2'),
    (26, 2, 10, 10, 0, 0, 'nuke3'),
    (27, 2, 10, 10, 0, 0, 'c4'),
    (28, 2, 10, 10, 0, 0, 'urethane_defused'),
    (29, 2, 10, 10, 0, 0, 'diggerbomb'),
    (30, 2, 10, 10, 0, 0, 'crackerbarrel'),
    (31, 2, 10, 10, 0, 0, 'grenade'),


    # Row 3
    (0, 3, 10, 10, 0, 0, 'exit'),
    (1, 3, 10, 10, 0, 0, 'securitydoor'),
    (2, 3, 10, 10, 0, 0, 'smallremote_player3'),
    (3, 3, 10, 10, 0, 0, 'bigremote_player3'),
    (4, 3, 10, 10, 0, 0, 'smallremote_player4'),
    (5, 3, 10, 10, 0, 0, 'bigremote_player4'),
    (6, 3, 10, 10, 0, 0, 'medpack'),
    (7, 3, 10, 10, 0, 0, 'bioslime'),
    (8, 3, 10, 10, 0, 0, '_unknown'),
    (9, 3, 10, 10, 0, 0, 'rock1'),
    (10, 3, 10, 10, 0, 0, 'rock2'),
    (11, 3, 10, 10, 0, 0, '_unknown2'),
    (12, 3, 10, 10, 0, 0, 'smallbomb_defused'),
    (13, 3, 10, 10, 0, 0, 'bigbomb_defused'),
    (14, 3, 10, 10, 0, 0, 'dynamite_defused'),
    (15, 3, 10, 10, 0, 0, 'diamond'),
    (16, 3, 10, 10, 0, 0, 'player3_right_1'),
    (17, 3, 10, 10, 0, 0, 'player3_right_2'),
    (18, 3, 10, 10, 0, 0, 'player3_right_3'),
    (19, 3, 10, 10, 0, 0, 'player3_right_4'),
    (20, 3, 10, 10, 0, 0, 'player3_left_1'),
    (21, 3, 10, 10, 0, 0, 'player3_left_2'),
    (22, 3, 10, 10, 0, 0, 'player3_left_3'),
    (23, 3, 10, 10, 0, 0, 'player3_left_4'),
    (24, 3, 10, 10, 0, 0, 'player3_up_1'),
    (25, 3, 10, 10, 0, 0, 'player3_up_2'),
    (26, 3, 10, 10, 0, 0, 'player3_up_3'),
    (27, 3, 10, 10, 0, 0, 'player3_up_4'),
    (28, 3, 10, 10, 0, 0, 'player3_down_1'),
    (29, 3, 10, 10, 0, 0, 'player3_down_2'),
    (30, 3, 10, 10, 0, 0, 'player3_down_3'),
    (31, 3, 10, 10, 0, 0, 'player3_down_4'),

    # Row 4 
    (14, 4, 10, 10, 0, 0, 'blood_green'),
    (15, 4, 10, 10, 0, 0, 'grasshopper'),
    (16, 4, 10, 10, 0, 0, 'player4_right_1'),
    (17, 4, 10, 10, 0, 0, 'player4_right_2'),
    (18, 4, 10, 10, 0, 0, 'player4_right_3'),
    (19, 4, 10, 10, 0, 0, 'player4_right_4'),
    (20, 4, 10, 10, 0, 0, 'player4_left_1'),
    (21, 4, 10, 10, 0, 0, 'player4_left_2'),
    (22, 4, 10, 10, 0, 0, 'player4_left_3'),
    (23, 4, 10, 10, 0, 0, 'player4_left_4'),
    (24, 4, 10, 10, 0, 0, 'player4_up_1'),
    (25, 4, 10, 10, 0, 0, 'player4_up_2'),
    (26, 4, 10, 10, 0, 0, 'player4_up_3'),
    (27, 4, 10, 10, 0, 0, 'player4_up_4'),
    (28, 4, 10, 10, 0, 0, 'player4_down_1'),
    (29, 4, 10, 10, 0, 0, 'player4_down_2'),
    (30, 4, 10, 10, 0, 0, 'player4_down_3'),
    (31, 4, 10, 10, 0, 0, 'player4_down_4'),

    # Row 5
    (16, 5, 10, 10, 0, 0, 'furryman_right_1'),
    (17, 5, 10, 10, 0, 0, 'furryman_right_2'),
    (18, 5, 10, 10, 0, 0, 'furryman_right_3'),
    (19, 5, 10, 10, 0, 0, 'furryman_right_4'),
    (20, 5, 10, 10, 0, 0, 'furryman_left_1'),
    (21, 5, 10, 10, 0, 0, 'furryman_left_2'),
    (22, 5, 10, 10, 0, 0, 'furryman_left_3'),
    (23, 5, 10, 10, 0, 0, 'furryman_left_4'),
    (24, 5, 10, 10, 0, 0, 'furryman_up_1'),
    (25, 5, 10, 10, 0, 0, 'furryman_up_2'),
    (26, 5, 10, 10, 0, 0, 'furryman_up_3'),
    (27, 5, 10, 10, 0, 0, 'furryman_up_4'),
    (28, 5, 10, 10, 0, 0, 'furryman_down_1'),
    (29, 5, 10, 10, 0, 0, 'furryman_down_2'),
    (30, 5, 10, 10, 0, 0, 'furryman_down_3'),
    (31, 5, 10, 10, 0, 0, 'furryman_down_4'),

    # Row 6
    (16, 6, 10, 10, 0, 0, 'grenademonster_right_1'),
    (17, 6, 10, 10, 0, 0, 'grenademonster_right_2'),
    (18, 6, 10, 10, 0, 0, 'grenademonster_right_3'),
    (19, 6, 10, 10, 0, 0, 'grenademonster_right_4'),
    (20, 6, 10, 10, 0, 0, 'grenademonster_left_1'),
    (21, 6, 10, 10, 0, 0, 'grenademonster_left_2'),
    (22, 6, 10, 10, 0, 0, 'grenademonster_left_3'),
    (23, 6, 10, 10, 0, 0, 'grenademonster_left_4'),
    (24, 6, 10, 10, 0, 0, 'grenademonster_up_1'),
    (25, 6, 10, 10, 0, 0, 'grenademonster_up_2'),
    (26, 6, 10, 10, 0, 0, 'grenademonster_up_3'),
    (27, 6, 10, 10, 0, 0, 'grenademonster_up_4'),
    (28, 6, 10, 10, 0, 0, 'grenademonster_down_1'),
    (29, 6, 10, 10, 0, 0, 'grenademonster_down_2'),
    (30, 6, 10, 10, 0, 0, 'grenademonster_down_3'),
    (31, 6, 10, 10, 0, 0, 'grenademonster_down_4'),

    # Row 7
    (0, 7, 10, 10, 0, 0, 'brics1'),
    (1, 7, 10, 10, 0, 0, 'brics2'),
    (2, 7, 10, 10, 0, 0, 'brics3'),
    (3, 7, 10, 10, 0, 0, 'doorswitch_red'),
    (4, 7, 10, 10, 0, 0, 'doorswitch_green'),
    (5, 7, 10, 10, 0, 0, '_math'),
    (16, 7, 10, 10, 0, 0, 'slime_right_1'),
    (17, 7, 10, 10, 0, 0, 'slime_right_2'),
    (18, 7, 10, 10, 0, 0, 'slime_right_3'),
    (19, 7, 10, 10, 0, 0, 'slime_right_4'),
    (20, 7, 10, 10, 0, 0, 'slime_left_1'),
    (21, 7, 10, 10, 0, 0, 'slime_left_2'),
    (22, 7, 10, 10, 0, 0, 'slime_left_3'),
    (23, 7, 10, 10, 0, 0, 'slime_left_4'),
    (24, 7, 10, 10, 0, 0, 'slime_up_1'),
    (25, 7, 10, 10, 0, 0, 'slime_up_2'),
    (26, 7, 10, 10, 0, 0, 'slime_up_3'),
    (27, 7, 10, 10, 0, 0, 'slime_up_4'),
    (28, 7, 10, 10, 0, 0, 'slime_down_1'),
    (29, 7, 10, 10, 0, 0, 'slime_down_2'),
    (30, 7, 10, 10, 0, 0, 'slime_down_3'),
    (31, 7, 10, 10, 0, 0, 'slime_down_4'),

    # Row 8
    (0, 8, 10, 10, 0, 0, 'alien_right_1'),
    (1, 8, 10, 10, 0, 0, 'alien_right_2'),
    (2, 8, 10, 10, 0, 0, 'alien_right_3'),
    (3, 8, 10, 10, 0, 0, 'alien_right_4'),
    (4, 8, 10, 10, 0, 0, 'alien_left_1'),
    (5, 8, 10, 10, 0, 0, 'alien_left_2'),
    (6, 8, 10, 10, 0, 0, 'alien_left_3'),
    (7, 8, 10, 10, 0, 0, 'alien_left_4'),
    (8, 8, 10, 10, 0, 0, 'alien_up_1'),
    (9, 8, 10, 10, 0, 0, 'alien_up_2'),
    (10, 8, 10, 10, 0, 0, 'alien_up_3'),
    (11, 8, 10, 10, 0, 0, 'alien_up_4'),
    (12, 8, 10, 10, 0, 0, 'alien_down_1'),
    (13, 8, 10, 10, 0, 0, 'alien_down_2'),
    (14, 8, 10, 10, 0, 0, 'alien_down_3'),
    (15, 8, 10, 10, 0, 0, 'alien_down_4'),

    # Row 18
    (0, 18, 10, 10, 0, 0, 'player1_dig_right_1'),
    (1, 18, 10, 10, 0, 0, 'player1_dig_right_2'),
    (2, 18, 10, 10, 0, 0, 'player1_dig_right_3'),
    (3, 18, 10, 10, 0, 0, 'player1_dig_right_4'),
    (4, 18, 10, 10, 0, 0, 'player1_dig_left_1'),
    (5, 18, 10, 10, 0, 0, 'player1_dig_left_2'),
    (6, 18, 10, 10, 0, 0, 'player1_dig_left_3'),
    (7, 18, 10, 10, 0, 0, 'player1_dig_left_4'),
    (8, 18, 10, 10, 0, 0, 'player1_dig_up_1'),
    (9, 18, 10, 10, 0, 0, 'player1_dig_up_2'),
    (10, 18, 10, 10, 0, 0, 'player1_dig_up_3'),
    (11, 18, 10, 10, 0, 0, 'player1_dig_up_4'),
    (12, 18, 10, 10, 0, 0, 'player1_dig_down_1'),
    (13, 18, 10, 10, 0, 0, 'player1_dig_down_2'),
    (14, 18, 10, 10, 0, 0, 'player1_dig_down_3'),
    (15, 18, 10, 10, 0, 0, 'player1_dig_down_4'),
    (16, 18, 10, 10, 0, 0, 'player2_dig_right_1'),
    (17, 18, 10, 10, 0, 0, 'player2_dig_right_2'),
    (18, 18, 10, 10, 0, 0, 'player2_dig_right_3'),
    (19, 18, 10, 10, 0, 0, 'player2_dig_right_4'),
    (20, 18, 10, 10, 0, 0, 'player2_dig_left_1'),
    (21, 18, 10, 10, 0, 0, 'player2_dig_left_2'),
    (22, 18, 10, 10, 0, 0, 'player2_dig_left_3'),
    (23, 18, 10, 10, 0, 0, 'player2_dig_left_4'),
    (24, 18, 10, 10, 0, 0, 'player2_dig_up_1'),
    (25, 18, 10, 10, 0, 0, 'player2_dig_up_2'),
    (26, 18, 10, 10, 0, 0, 'player2_dig_up_3'),
    (27, 18, 10, 10, 0, 0, 'player2_dig_up_4'),
    (28, 18, 10, 10, 0, 0, 'player2_dig_down_1'),
    (29, 18, 10, 10, 0, 0, 'player2_dig_down_2'),
    (30, 18, 10, 10, 0, 0, 'player2_dig_down_3'),
    (31, 18, 10, 10, 0, 0, 'player2_dig_down_4'),

    # Row 19
    (0, 19, 10, 10, 0, 0, 'player3_dig_right_1'),
    (1, 19, 10, 10, 0, 0, 'player3_dig_right_2'),
    (2, 19, 10, 10, 0, 0, 'player3_dig_right_3'),
    (3, 19, 10, 10, 0, 0, 'player3_dig_right_4'),
    (4, 19, 10, 10, 0, 0, 'player3_dig_left_1'),
    (5, 19, 10, 10, 0, 0, 'player3_dig_left_2'),
    (6, 19, 10, 10, 0, 0, 'player3_dig_left_3'),
    (7, 19, 10, 10, 0, 0, 'player3_dig_left_4'),
    (8, 19, 10, 10, 0, 0, 'player3_dig_up_1'),
    (9, 19, 10, 10, 0, 0, 'player3_dig_up_2'),
    (10, 19, 10, 10, 0, 0, 'player3_dig_up_3'),
    (11, 19, 10, 10, 0, 0, 'player3_dig_up_4'),
    (12, 19, 10, 10, 0, 0, 'player3_dig_down_1'),
    (13, 19, 10, 10, 0, 0, 'player3_dig_down_2'),
    (14, 19, 10, 10, 0, 0, 'player3_dig_down_3'),
    (15, 19, 10, 10, 0, 0, 'player3_dig_down_4'),
    (16, 19, 10, 10, 0, 0, 'player4_dig_right_1'),
    (17, 19, 10, 10, 0, 0, 'player4_dig_right_2'),
    (18, 19, 10, 10, 0, 0, 'player4_dig_right_3'),
    (19, 19, 10, 10, 0, 0, 'player4_dig_right_4'),
    (20, 19, 10, 10, 0, 0, 'player4_dig_left_1'),
    (21, 19, 10, 10, 0, 0, 'player4_dig_left_2'),
    (22, 19, 10, 10, 0, 0, 'player4_dig_left_3'),
    (23, 19, 10, 10, 0, 0, 'player4_dig_left_4'),
    (24, 19, 10, 10, 0, 0, 'player4_dig_up_1'),
    (25, 19, 10, 10, 0, 0, 'player4_dig_up_2'),
    (26, 19, 10, 10, 0, 0, 'player4_dig_up_3'),
    (27, 19, 10, 10, 0, 0, 'player4_dig_up_4'),
    (28, 19, 10, 10, 0, 0, 'player4_dig_down_1'),
    (29, 19, 10, 10, 0, 0, 'player4_dig_down_2'),
    (30, 19, 10, 10, 0, 0, 'player4_dig_down_3'),
    (31, 19, 10, 10, 0, 0, 'player4_dig_down_4'),

    # tile transition sprites
    (0 , 0, 4, 10, 148, 60, 'transition_horizontal_empty_bedrock'),
    (0 , 0, 4, 10, 154, 60, 'transition_horizontal_bedrock_empty'),

    (0 , 0, 10, 3, 148, 71, 'transition_vertical_empty_bedrock'),
    (0 , 0, 10, 3, 148, 75, 'transition_vertical_bedrock_empty'),

    (0 , 0, 4, 10, 194, 98, 'transition_horizontal_empty_dirt'),
    (0 , 0, 4, 10, 200, 98, 'transition_horizontal_dirt_empty'),

    (0 , 0, 10, 3, 194, 109, 'transition_vertical_empty_dirt'),
    (0 , 0, 10, 3, 194, 113, 'transition_vertical_dirt_empty'),

]


# Sprite padding definitions: (name, target_w, target_h, pad_side)
# pad_side: 'left', 'right', 'top', 'bottom' - which side gets transparent padding
SPRITE_PADDING_DEFS = [
    # Horizontal transitions: 4x10 -> 8x10 (4 pixels padding)
    ('transition_horizontal_empty_bedrock', 8, 10, 'left'),
    ('transition_horizontal_bedrock_empty', 8, 10, 'right'),
    ('transition_horizontal_empty_dirt', 8, 10, 'left'),
    ('transition_horizontal_dirt_empty', 8, 10, 'right'),

    # Vertical transitions: 10x3 -> 10x6 (3 pixels padding)
    ('transition_vertical_empty_bedrock', 10, 6, 'top'),
    ('transition_vertical_bedrock_empty', 10, 6, 'bottom'),
    ('transition_vertical_empty_dirt', 10, 6, 'top'),
    ('transition_vertical_dirt_empty', 10, 6, 'bottom'),
]


def pad_sprites(output_base):
    """Pad sprite PNG files to target sizes with transparent pixels.

    Reads saved sprite files from disk, pads them according to SPRITE_PADDING_DEFS,
    and overwrites them with the padded versions.
    """
    sprites_dir = os.path.join(output_base, 'sprites')

    if not os.path.exists(sprites_dir):
        return 0

    count = 0
    for name, target_w, target_h, pad_side in SPRITE_PADDING_DEFS:
        sprite_path = os.path.join(sprites_dir, f"{name}.png")

        if not os.path.exists(sprite_path):
            continue

        sprite = Image.open(sprite_path)
        sprite_rgba = sprite.convert('RGBA')
        orig_w, orig_h = sprite_rgba.size

        # Create padded image with transparent background
        padded = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))

        # Calculate paste position based on padding side
        if pad_side == 'left':
            paste_x = target_w - orig_w
            paste_y = 0
        elif pad_side == 'right':
            paste_x = 0
            paste_y = 0
        elif pad_side == 'top':
            paste_x = 0
            paste_y = target_h - orig_h
        elif pad_side == 'bottom':
            paste_x = 0
            paste_y = 0
        else:
            continue

        padded.paste(sprite_rgba, (paste_x, paste_y))
        padded.save(sprite_path)
        count += 1

    if count > 0:
        print(f"  Padded {count} sprites")

    return count


def split_sprites(output_base):
    """Split SIKA.png into individual sprite files based on SPRITE_DEFS"""
    sika_path = os.path.join(output_base, 'graphics', 'SIKA.png')
    sprites_dir = os.path.join(output_base, 'sprites')
    os.makedirs(sprites_dir, exist_ok=True)

    if not os.path.exists(sika_path):
        print(f"  SIKA.png not found, skipping sprite split")
        return 0

    img = Image.open(sika_path)

    if not SPRITE_DEFS:
        print(f"  No sprite definitions, skipping sprite split")
        return 0

    print(f"  Extracting {len(SPRITE_DEFS)} named sprites...")
    count = 0

    for x, y, w, h, ox, oy, name in SPRITE_DEFS:
        px = x * w + ox
        py = y * h + oy
        sprite = img.crop((px, py, px + w, py + h))
        sprite.save(os.path.join(sprites_dir, f"{name}.png"))
        count += 1

    print(f"  Extracted {count} sprites")
    return count


# ============================================================================
# Main Extractor
# ============================================================================

def extract_assets(zip_path, output_base):
    """Extract all assets from ZIP file to output directory"""

    # Create output directories
    dirs = {
        'graphics': os.path.join(output_base, 'graphics'),
        'sounds': os.path.join(output_base, 'sounds'),
        'music': os.path.join(output_base, 'music'),
        'maps': os.path.join(output_base, 'maps'),
    }
    for d in dirs.values():
        os.makedirs(d, exist_ok=True)

    stats = {'graphics': 0, 'sounds': 0, 'music': 0, 'maps': 0}

    with zipfile.ZipFile(zip_path, 'r') as zf:
        for file_info in zf.infolist():
            filename = os.path.basename(file_info.filename)
            name, ext = os.path.splitext(filename)
            ext = ext.upper()

            if not filename or file_info.is_dir():
                continue

            data = zf.read(file_info.filename)

            try:
                # SPY sprites -> PNG (to graphics folder)
                if ext == '.SPY':
                    print(f"  Extracting sprite: {filename}")
                    img = extract_spy(data, name)
                    if img:
                        img.save(os.path.join(dirs['graphics'], f"{name}.png"))
                        stats['graphics'] += 1

                # PPM (PCX) graphics -> PNG (to graphics folder)
                elif ext == '.PPM':
                    print(f"  Converting graphic: {filename}")
                    img = decode_pcx(data)
                    img.save(os.path.join(dirs['graphics'], f"{name}.png"))
                    stats['graphics'] += 1

                # VOC sounds -> WAV
                elif ext == '.VOC':
                    print(f"  Converting sound: {filename}")
                    wav_data = convert_voc_to_wav(data)
                    with open(os.path.join(dirs['sounds'], f"{name}.wav"), 'wb') as f:
                        f.write(wav_data)
                    stats['sounds'] += 1

                # S3M music -> copy
                elif ext == '.S3M':
                    print(f"  Copying music: {filename}")
                    with open(os.path.join(dirs['music'], filename), 'wb') as f:
                        f.write(data)
                    stats['music'] += 1

                # MNE/MNL maps -> copy
                elif ext in ('.MNE', '.MNL'):
                    print(f"  Copying map: {filename}")
                    with open(os.path.join(dirs['maps'], filename), 'wb') as f:
                        f.write(data)
                    stats['maps'] += 1

            except Exception as e:
                print(f"    Error processing {filename}: {e}")

    return stats


def main():
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))

    if len(sys.argv) < 2:
        # Default paths (relative to script location)
        zip_path = os.path.join(script_dir, 'minebomb.zip')
        output_base = os.path.join(script_dir, 'assets')
    else:
        zip_path = sys.argv[1]
        output_base = sys.argv[2] if len(sys.argv) > 2 else './assets'

    print(f"Extracting assets from: {zip_path}")
    print(f"Output directory: {output_base}\n")

    if not os.path.exists(zip_path):
        print(f"Error: ZIP file not found: {zip_path}")
        return

    stats = extract_assets(zip_path, output_base)
    sprite_count = split_sprites(output_base)
    padded_count = pad_sprites(output_base)

    print(f"\nExtraction complete!")
    print(f"  Graphics: {stats['graphics']}")
    print(f"  Sounds:   {stats['sounds']}")
    print(f"  Music:    {stats['music']}")
    print(f"  Maps:     {stats['maps']}")
    print(f"  Sprites:  {sprite_count}")


if __name__ == '__main__':
    main()
