DynamicEntity:
  id: 16 bytes
  x: Float32
  y: Float32
  speed: Float32
  health: 0 - 1023
  direction: 0 - 3
  entity_type: 0 - 7
  state: 0 - 3

Player:
  id: 16 bytes
  x: Float32
  y: Float32
  speed: Float32
  health: 0 - 1023
  direction: 0 - 3
  entity_type: 0 - 7
  state: 0 - 3
  sprite_id: 0 - 255
  color.r: 0 - 255
  color.g: 0 - 255
  color.b: 0 - 255
  money: 0 - 16383
  dig_power: 0 - 127
  selected: 0 - 31
  selected_type: 0 - 31
  name bytes: 0 - 255
  inventory entries: 0 - 255
  inventory bomb_type: 0 - 255
  inventory count: 0 - 255
  tool entries: 0 - 255
  tool_type: 0 - 7
  tool count: 0 - 31

Bomb:
  id: 16 bytes
  owner_id: 16 bytes
  x: 0 - 255
  y: 0 - 255
  bomb_type: 0 - 31
  state: 0 - 1
  direction: 0 - 7
  fuse_pct: Float32

Pickup:
  x: 0 - 255
  y: 0 - 255
  visual_id: 0 - 255
  pickup_type: 0 - 3
  value: 0 - 127

GameState:
  width: 0 - 255
  height: 0 - 255
  server_time: Float64
  round_time_left: Float64
  running: 0 - 255
  tilemap values: 0 - 255
  tilemap payload bytes: 0 - 4294967295
  explosions payload bytes: 0 - 4294967295
  players payload bytes: 0 - 65535
  monsters payload bytes: 0 - 65535
  pickups payload bytes: 0 - 65535
  bombs payload bytes: 0 - 65535
  sounds payload bytes: 0 - 65535
  player record bytes: 0 - 65535
  sound code: 0 - 255

SessionInfo:
  rounds_left: 0 - 255
  width: 0 - 255
  height: 0 - 255
  tilemap values: 0 - 255
  tilemap payload bytes: 0 - 4294967295
  pickups payload bytes: 0 - 65535

RLE:
  normal value: 0 - 255
  normal run length: 0 - 255
  big value: 0 - 65535
  big run length: 0 - 65535