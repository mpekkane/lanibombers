import contextlib
import io
import unittest
from uuid import uuid4

import numpy as np

from game_engine.entities import (
    BombState,
    EntityState,
    Bomb, BombType, Direction, DynamicEntity, EntityType, Pickup, Player, ToolType,
)
from network_stack.messages.messages import GameState


class EntityEncodingTests(unittest.TestCase):
    def test_monster_states_and_health(self):
        for entity_type in EntityType:
            for direction in Direction:
                for state in EntityState:
                    monster = DynamicEntity(
                        x=12.25, y=34.5, speed=2.5, health=1023,
                        entity_type=entity_type, direction=direction, state=state,
                    )
                    encoded = monster.to_bytes()
                    decoded = DynamicEntity.from_bytes(encoded)
                    self.assertIsInstance(decoded.state, EntityState)
                    self.assertIsInstance(decoded.direction, Direction)
                    self.assertIsInstance(decoded.entity_type, EntityType)
                    flags = int.from_bytes(encoded[-3:], "big")
                    self.assertEqual((flags >> 10) & 7, int(entity_type))
                    self.assertEqual((flags >> 13) & 3, int(direction))
                    self.assertEqual((int.from_bytes(encoded[-3:], "big") >> 15) & 3, int(state))
                    self.assertEqual(len(encoded), 31)
                    for name in ("id", "x", "y", "speed", "health", "entity_type", "direction", "state"):
                        self.assertEqual(getattr(decoded, name), getattr(monster, name))

    def test_player_stats_and_inventory(self):
        player = Player(
            x=12.25, y=34.5, speed=3.5, health=1023, name="ä" * 20,
            sprite_id=4, color=(0, 127, 255), money=16383, dig_power=127,
            selected=31, selected_type=BombType.GRENADE,
            inventory=[(BombType.GRENADE, 255)] * 32,
            tools={tool: 31 for tool in ToolType}, state=EntityState.DIG, direction=Direction.LEFT,
        )
        decoded = Player.from_bytes(player.to_bytes())
        self.assertIsInstance(decoded.selected_type, BombType)
        self.assertTrue(all(isinstance(kind, BombType) for kind, _ in decoded.inventory))
        self.assertTrue(all(isinstance(kind, ToolType) for kind in decoded.tools))
        for name in (
            "id", "x", "y", "speed", "health", "name", "sprite_id", "color",
            "money", "dig_power", "selected", "selected_type", "inventory", "tools",
            "state", "direction",
        ):
            self.assertEqual(getattr(decoded, name), getattr(player, name))
        decoded = Player.from_bytes(Player().to_bytes())
        self.assertEqual(decoded.inventory, [])
        self.assertEqual(decoded.tools, {})

    def test_player_rejects_overflow(self):
        for changes in (
            {"health": 1024}, {"health": -1}, {"money": 16384}, {"money": -1},
            {"dig_power": 128}, {"selected": 32}, {"name": "a" * 21},
            {"inventory": [(BombType.SMALL_BOMB, 1)] * 33},
            {"inventory": [(BombType.SMALL_BOMB, 256)]},
            {"tools": {ToolType.DRILL: 32}},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                Player(**changes).to_bytes()

    def test_bomb_identity_animation_and_direction(self):
        for bomb_type in BombType:
            for direction in (None, *Direction):
                for state in BombState:
                    bomb = Bomb(x=255, y=0, owner_id=uuid4(), placed_at=100.0,
                                bomb_type=bomb_type, direction=direction)
                    bomb.fuse_pct = 0.25
                    bomb.state = state
                    encoded = bomb.to_bytes()
                    decoded = Bomb.from_bytes(encoded)
                    self.assertIsInstance(decoded.bomb_type, BombType)
                    self.assertIsInstance(decoded.state, BombState)
                    flags = int.from_bytes(encoded[34:36], "big")
                    self.assertEqual(flags & 31, int(bomb_type))
                    self.assertEqual((flags >> 5) & 1, int(state))
                    self.assertEqual(len(encoded), 40)
                    for name in ("id", "owner_id", "x", "y", "bomb_type", "direction", "state", "fuse_pct"):
                        self.assertEqual(getattr(decoded, name), getattr(bomb, name))

    def test_game_state_sections(self):
        player = Player(name="Matti", inventory=[(BombType.SMALL_BOMB, 255)])
        monster = DynamicEntity.create_monster(EntityType.ALIEN, 2.25, 1.5, Direction.UP)
        pickup = Pickup(x=1, y=1, visual_id=42)
        bomb = Bomb(x=1, y=0, owner_id=player.id, placed_at=100.0, bomb_type=BombType.NUKE)
        tilemap = np.arange(8, dtype=np.uint8).reshape(2, 4)
        for counts in ((0, 0, 0, 0), (1, 1, 1, 1), (2, 3, 2, 4), (0, 1, 0, 1)):
            with self.subTest(counts=counts):
                msg = GameState(
                    width=4, height=2, tilemap=tilemap, explosions=np.zeros_like(tilemap),
                    players=[player, Player(name="ä", inventory=[])][:counts[0]],
                    monsters=[monster] * counts[1],
                    pickups=[pickup] * counts[2], bombs=[bomb] * counts[3],
                    server_time=123.5, running=True, round_time_left=67.25, sounds=(1, 2, 3),
                )
                with contextlib.redirect_stdout(io.StringIO()):
                    decoded = GameState.from_bytes(msg.to_bytes())
                for name in ("players", "monsters", "pickups", "bombs"):
                    self.assertEqual(
                        [entity.to_bytes() for entity in getattr(decoded, name)],
                        [entity.to_bytes() for entity in getattr(msg, name)],
                    )
                for name in ("server_time", "running", "round_time_left", "sounds"):
                    self.assertEqual(getattr(decoded, name), getattr(msg, name))
                np.testing.assert_array_equal(decoded.tilemap, tilemap)
                np.testing.assert_array_equal(decoded.explosions, msg.explosions)


if __name__ == "__main__":
    unittest.main()
