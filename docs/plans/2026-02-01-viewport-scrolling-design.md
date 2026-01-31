# Viewport Scrolling Design

## Overview

Refactor the renderer to support maps larger than the visible area (up to 256×256 tiles) while displaying a 64×45 tile viewport that scrolls to follow the player.

## Constants

```python
VIEWPORT_WIDTH = 64    # Visible tiles horizontally
VIEWPORT_HEIGHT = 45   # Visible tiles vertically
VIEWPORT_BUFFER = 1    # Extra tile for smooth scrolling
TILE_GRID_WIDTH = 65   # VIEWPORT_WIDTH + VIEWPORT_BUFFER
TILE_GRID_HEIGHT = 46  # VIEWPORT_HEIGHT + VIEWPORT_BUFFER
```

## Sprite List Sizes (Fixed)

Regardless of map size, sprite lists are fixed to viewport dimensions:

| Sprite List | Size | Calculation |
|-------------|------|-------------|
| Background tiles | 65 × 46 = 2,990 | Grid with buffer |
| Horizontal transitions | 64 × 46 = 2,944 | Between columns |
| Vertical transitions | 65 × 45 = 2,925 | Between rows |
| Explosions | 65 × 46 = 2,990 | Matches tile grid |

## Viewport Data Structure

```python
@dataclass
class Viewport:
    x: float = 0.0              # Viewport top-left in tile coords
    y: float = 0.0
    pixel_offset_x: float = 0.0 # Sub-tile pixel offset
    pixel_offset_y: float = 0.0
    tile_start_x: int = 0       # Integer tile index for sampling
    tile_start_y: int = 0
```

## Viewport Calculation

Method on `GameRenderer`:

```python
def calculate_viewport(self, player_x, player_y, map_width, map_height) -> Viewport:
```

### Small Maps (≤64×45)

If map fits within viewport, align to top-left:

```python
if map_width <= VIEWPORT_WIDTH and map_height <= VIEWPORT_HEIGHT:
    return Viewport(x=0, y=0, pixel_offset_x=0, pixel_offset_y=0,
                    tile_start_x=0, tile_start_y=0)
```

### Large Maps

1. Center on player:
   ```python
   x = player_x - VIEWPORT_WIDTH / 2    # 32
   y = player_y - VIEWPORT_HEIGHT / 2   # 22.5
   ```

2. Clamp to map edges:
   ```python
   x = clamp(x, 0, map_width - VIEWPORT_WIDTH)
   y = clamp(y, 0, map_height - VIEWPORT_HEIGHT)
   ```

3. Extract integer and fractional parts:
   ```python
   tile_start_x = floor(x)
   tile_start_y = floor(y)
   pixel_offset_x = (x - tile_start_x) * SPRITE_SIZE * zoom
   pixel_offset_y = (y - tile_start_y) * SPRITE_SIZE * zoom
   ```

## Tile Rendering

### Base Positions

At init, compute base positions for the 65×46 grid (as if viewport at 0,0):

```python
self.base_positions_x = []  # [vy][vx] -> pixel x
self.base_positions_y = []  # [vy][vx] -> pixel y

for vy in range(TILE_GRID_HEIGHT):
    row_x, row_y = [], []
    center_y = self.height - ui_offset - (vy * SPRITE_SIZE + SPRITE_CENTER_OFFSET) * zoom
    for vx in range(TILE_GRID_WIDTH):
        center_x = (vx * SPRITE_SIZE + SPRITE_CENTER_OFFSET) * zoom
        row_x.append(center_x)
        row_y.append(center_y)
    self.base_positions_x.append(row_x)
    self.base_positions_y.append(row_y)
```

### Update Loop

Each frame, sample tilemap and set absolute positions:

```python
for vy in range(TILE_GRID_HEIGHT):
    for vx in range(TILE_GRID_WIDTH):
        sprite = self.sprites[vy * TILE_GRID_WIDTH + vx]

        # Sample from tilemap
        tx = viewport.tile_start_x + vx
        ty = viewport.tile_start_y + vy
        if 0 <= tx < state.width and 0 <= ty < state.height:
            sprite.texture = self.tile_id_to_texture_dictionary[state.tilemap[ty, tx]]
        else:
            sprite.texture = self.transparent_texture

        # Absolute position (no creep)
        sprite.center_x = self.base_positions_x[vy][vx] - viewport.pixel_offset_x
        sprite.center_y = self.base_positions_y[vy][vx] + viewport.pixel_offset_y
```

### Transitions

Same pattern - sample from tilemap based on viewport, set absolute positions.

Horizontal transitions (64×46):
- Sample pairs at `(ty, tx)` and `(ty, tx+1)`
- Position between columns

Vertical transitions (65×45):
- Sample pairs at `(ty, tx)` and `(ty+1, tx)`
- Position between rows

### Explosions

Same as tiles - 65×46 grid, sample `state.explosions[ty, tx]`, set absolute positions.

## Entity Rendering

### Position Calculation

Entity sprites compute position relative to viewport:

```python
def update_from_entity(self, entity, delta_time, viewport):
    world_x = entity.x - viewport.x
    world_y = entity.y - viewport.y
    self.center_x = round(world_x * SPRITE_SIZE) * self.zoom
    self.center_y = self.screen_height - self.y_offset - round(world_y * SPRITE_SIZE) * self.zoom
```

### Affected Sprites

- PlayerSprite
- MonsterSprite
- BombSprite
- PickupSprite

All receive `viewport` parameter in their update methods.

## Draw Order

Draw header/UI last so it covers any entities that scroll underneath:

```python
def on_draw(self):
    self.clear()
    # Game world (affected by viewport)
    self.background_tile_sprite_list.draw(pixelated=True)
    self.vertical_transition_sprite_list.draw(pixelated=True)
    self.horizontal_transition_sprite_list.draw(pixelated=True)
    self.pickup_sprite_list.draw(pixelated=True)
    self.bomb_sprite_list.draw(pixelated=True)
    self.monster_sprite_list.draw(pixelated=True)
    self.player_sprite_list.draw(pixelated=True)
    self.explosion_sprite_list.draw(pixelated=True)
    # UI (drawn last, covers overflow)
    self.header_sprite_list.draw(pixelated=True)
    self.player_name_sprites.draw(pixelated=True)
    self.dig_power_sprites.draw(pixelated=True)
    self.money_sprites.draw(pixelated=True)
    self.inventory_sprites.draw(pixelated=True)
    self.inventory_hatch_sprites.draw(pixelated=True)
    self.inventory_count_sprites.draw(pixelated=True)
```

## Files to Modify

1. **renderer/game_renderer.py**
   - Add Viewport dataclass
   - Add VIEWPORT_* constants
   - Change sprite list initialization to fixed sizes
   - Add base_positions arrays
   - Add calculate_viewport() method
   - Add find_client_player() helper
   - Update on_update() to use viewport
   - Reorder on_draw() if needed

2. **renderer/sprites/player_sprite.py**
   - Add viewport parameter to update_from_entity()

3. **renderer/sprites/monster_sprite.py**
   - Add viewport parameter to update_from_entity()

4. **renderer/sprites/bomb_sprite.py**
   - Add viewport parameter to update_from_bomb()

5. **renderer/sprites/pickup_sprite.py**
   - Add viewport parameter to update_from_pickup()

6. **renderer/sprites/explosion_sprite.py**
   - Add viewport parameter to update_from_type() or create new method

## Edge Cases

1. **No client player found**: Default viewport to (0, 0)
2. **Map smaller than viewport**: Tiles beyond map edge get transparent texture
3. **Player at map edge**: Viewport clamps, player moves toward screen edge
4. **Entities outside viewport**: Still rendered, but will be off-screen or covered by header
