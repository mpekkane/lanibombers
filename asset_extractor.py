
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

    print(f"\nExtraction complete!")
    print(f"  Graphics: {stats['graphics']}")
    print(f"  Sounds:   {stats['sounds']}")
    print(f"  Music:    {stats['music']}")
    print(f"  Maps:     {stats['maps']}")


if __name__ == '__main__':
    main()
