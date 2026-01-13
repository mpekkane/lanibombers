"""
Test code for server-side
"""

import os
import time
import uuid
import array
import threading
from typing import Dict
from argparse import ArgumentParser
from pathlib import Path
from network_stack.bomber_network_server import BomberNetworkServer, ClientContext
from network_stack.messages.messages import Name, ChatText, Ping, Pong, ClientControl

from cfg.tile_dictionary import EMPTY_TILE_ID, MONSTER_SPAWN_TILES
from game_engine.entities import Direction, EntityType, DynamicEntity
from game_engine.render_state import RenderState
from game_engine.agent_state import Action
from renderer.game_renderer import GameRenderer, RendererConfig
from cfg.tile_dictionary import (
    TILE_DICTIONARY,
    EMPTY_TILE_NAMES,
    BEDROCK_TILE_NAMES,
    DIRT_TILE_NAMES,
    PLAYER_DEATH_SPRITE,
    MONSTER_DEATH_SPRITE,
)


class BomberServer:
    def __init__(self, cfg: str, map_path: str) -> None:
        # game engine
        self.init_game(map_path)

        # networking
        self.server = BomberNetworkServer(cfg)

        self.server.set_callback(Name, self.on_name)
        self.server.set_callback(ChatText, self.on_chat)
        self.server.set_callback(Pong, self.on_pong)
        self.server.set_callback(ClientControl, self.on_control)
        self.server.start()

        self.pings: Dict[str, Ping] = {}
        self.average_ping: int = -1
        self.ping_count = 0
        self.pong_count = 0
        self.MAX_PING_BUFFER = 100

        # FIXME: temp to check logic
        update_thread = threading.Thread(target=self.update_state, daemon=True)
        update_thread.start()

    ##################
    # game engine
    ##################
    def init_game(self, map_path: str):
        self._load_map(map_path)
        self._init_players()
        self._init_monsters()

    def _load_map(self, path):
        """Load map from ASCII file, sprite indices are ASCII values"""
        self.grid = array.array("B")
        with open(path, "rb") as f:
            for line in f:
                line = line.rstrip(b"\r\n")
                for char in line:
                    self.grid.append(char)
        self.height = 45
        self.width = 64

    def _init_players(self):
        """Initialize mock players"""
        self.players = [
            DynamicEntity(
                x=9,
                y=9,
                direction=Direction.RIGHT,
                entity_type=EntityType.PLAYER,
                name="Player1",
                colour=(255, 0, 0),
                sprite_id=1,
                state="dig",
            ),
            DynamicEntity(
                x=8,
                y=18,
                direction=Direction.RIGHT,
                entity_type=EntityType.PLAYER,
                name="Player2",
                colour=(0, 255, 0),
                sprite_id=2,
                state="idle",
            ),
        ]
        self.start_time = time.time()
        self.last_damage_time = self.start_time
        # Player 2 movement pattern: start position
        self.player2_start_x = 8
        self.player2_start_y = 18

    def _init_monsters(self):
        """Initialize monsters from spawn tiles in the map"""
        self.monsters = []

        for i, tile_id in enumerate(self.grid):
            if tile_id in MONSTER_SPAWN_TILES:
                entity_type, direction = MONSTER_SPAWN_TILES[tile_id]
                x = i % self.width
                y = i // self.width

                monster = DynamicEntity(
                    x=x, y=y, direction=direction, entity_type=entity_type, state="walk"
                )
                self.monsters.append(monster)

                # Replace spawn tile with empty
                self.grid[i] = EMPTY_TILE_ID

    def get_render_state(self):
        """Returns RenderState with dimensions and sprite indices"""
        return RenderState(
            width=self.width,
            height=self.height,
            tilemap=self.grid,
            players=self.players,
            monsters=self.monsters,
        )

    def update_state(self):
        while(True):
            time.sleep(0.1)
            elapsed = time.time() - self.start_time
            # Pattern: 4s right, 1s stop, 4s down, 1s stop, 4s left, 1s stop, 4s up, 1s stop = 20s cycle
            # Speed: 1.5 blocks/second (6 blocks in 4 seconds)
            cycle_time = elapsed % 20.0
            player = self.players[1]
            speed = 0.015  # blocks per second
            dt = cycle_time * speed

            for player in self.players:
                dx = 0
                dy = 0
                if player.state == "walk":
                    if player.direction == Direction.RIGHT:
                        dx = dt
                    elif player.direction == Direction.LEFT:
                        dx = -dt
                    elif player.direction == Direction.UP:
                        dy = -dt
                    elif player.direction == Direction.DOWN:
                        dy = dt

                player.x += dx
                player.y += dy

    ##################
    # networking
    ##################

    def on_control(self, msg: Name, ctx: ClientContext):
        """test contolling"""
        player = self.players[1]
        cmd = msg.commands[0]
        if cmd == Action.RIGHT:
            # Moving right
            player.direction = Direction.RIGHT
            player.state = "walk"
        elif cmd == Action.LEFT:
            # Moving right
            player.direction = Direction.LEFT
            player.state = "walk"
        elif cmd == Action.UP:
            # Moving right
            player.direction = Direction.UP
            player.state = "walk"
        elif cmd == Action.DOWN:
            player.direction = Direction.DOWN
            player.state = "walk"
        elif cmd == Action.STOP:
            # Stopped after right
            player.state = "idle"

    def _ensure_timestamp(self, msg: Ping) -> None:
        if getattr(msg, "timestamp", None) is None:
            object.__setattr__(msg, "timestamp", time.time_ns())

    def ping(self) -> None:
        uid = str(uuid.uuid4())
        ping = Ping(uid)
        self._ensure_timestamp(ping)
        self.server.broadcast(ping)
        self.ping_count += 1
        self.pings[ping.UUID] = ping

        if len(self.pings) > self.MAX_PING_BUFFER:
            drop_n = self.MAX_PING_BUFFER // 2  # e.g. 50 when MAX=100
            oldest_keys = sorted(self.pings, key=lambda k: self.pings[k].timestamp)[
                :drop_n
            ]
            for k in oldest_keys:
                self.pings.pop(k, None)

    def on_name(self, msg: Name, ctx: ClientContext) -> None:
        ctx.name = msg.name
        print("set name:", msg.name)

    def on_chat(self, msg: ChatText, ctx: ClientContext) -> None:
        sender = ctx.name or "?"
        ctx.broadcast(ChatText(text=f"<{sender}> {msg.text}"), exclude_self=True)

    def on_pong(self, msg: Pong, ctx: ClientContext) -> None:
        ping = self.pings[msg.ping_UUID]
        dt = msg.received - ping.timestamp

        self.pong_count += 1

        if self.average_ping < 0:
            self.average_ping = dt
        else:
            self.average_ping = (self.average_ping * (self.ping_count - 1) + dt) / (
                self.ping_count
            )
        avg_s = self.average_ping / 1e9

        if self.ping_count % 100 == 0:
            # print(f"sent        : {ping.timestamp}")
            # print(f"received    : {msg.received}")
            # print(f"dt      (ns): {dt} ns")
            # print(f"dt      (s) : {dt/1e9} s")
            print(f"average (ns): {self.average_ping} ns")
            print(f"average (s) : {avg_s} s")
            print(f"over pings  : {self.ping_count}")
            print(f"   & pongs  : {self.pong_count}")


def ping(server: BomberServer) -> None:
    print("ping thread")
    last_ping = time.time()
    tick = 0.1
    while True:
        if time.time() - last_ping > tick:
            server.ping()
            last_ping = time.time()
        time.sleep(tick / 2)


def main() -> None:
    assert Path("assets").exists(), "Assets missing"
    parser = ArgumentParser()
    parser.add_argument("--cfg", "-c", type=str, default="cfg/server_config.yaml")
    parser.add_argument("--map", "-m", type=str, default="assets/maps/ANZULABY.MNE")
    args = parser.parse_args()
    cfg = args.cfg
    map_path = args.map
    server = BomberServer(cfg, map_path)

    # ping_thread = threading.Thread(
    #     target=ping, daemon=True, kwargs={"server": server}
    # )
    # ping_thread.start()

    state = server.get_render_state()
    # FIXME: refactor
    SPRITES_PATH = os.path.join(os.path.dirname(__file__), "assets", "sprites")
    renderer_config = RendererConfig(
        TILE_DICTIONARY,
        EMPTY_TILE_NAMES,
        BEDROCK_TILE_NAMES,
        DIRT_TILE_NAMES,
        PLAYER_DEATH_SPRITE,
        MONSTER_DEATH_SPRITE,
        SPRITES_PATH,
    )
    renderer = GameRenderer(server, renderer_config)
    renderer.run()


if __name__ == "__main__":
    main()
