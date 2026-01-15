"""
Test code for server-side
"""

import os
import time
import uuid
import threading
from enum import IntEnum
from typing import Dict, Union
from argparse import ArgumentParser
from pathlib import Path
from network_stack.bomber_network_server import BomberNetworkServer, ClientContext
from network_stack.messages.messages import Name, ChatText, Ping, Pong, ClientControl
from game_engine.entities import Direction
from game_engine.render_state import RenderState
from game_engine.agent_state import Action
from game_engine.game_state import Game
from renderer.game_renderer import GameRenderer, RendererConfig
from common.keymapper import check_input
from cfg.tile_dictionary import (
    TILE_DICTIONARY,
    EMPTY_TILE_NAMES,
    BEDROCK_TILE_NAMES,
    DIRT_TILE_NAMES,
    PLAYER_DEATH_SPRITE,
    MONSTER_DEATH_SPRITE,
)


class ServerState(IntEnum):
    STARTING = 1
    LOBBY = 2
    SHOP = 3
    GAME = 4
    END = 5

    def running(self) -> bool:
        return int(self) > 2


class BomberServer:
    def __init__(self, cfg: str, map_path: str) -> None:
        self.state = ServerState.STARTING
        # game engine
        self.game = Game(map_path)

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
        self.MAX_PING_BUFFER = 1
        self.players = []

    def run_lobby(self) -> bool:
        self.state = ServerState.LOBBY
        while self.state == ServerState.LOBBY:
            print("")
            print("Hosting a LAN server")
            if len(self.players) > 0:
                print("Players in the lobby")
                for i, player in enumerate(self.players):
                    print(f"{i+1}: {player}")
                inp = input("start game? y/n")
                if inp == "y":
                    self.state = ServerState.GAME
            else:
                print("No players in the lobby")
                time.sleep(1)
        return self.state == ServerState.GAME

    def start_game(self) -> None:
        # FIXME: temp to check logic
        self.state = ServerState.GAME
        update_thread = threading.Thread(target=self.update_state, daemon=True)
        update_thread.start()

    ##################
    # game engine
    ##################

    def get_render_state(self):
        """Returns RenderState with dimensions and sprite indices"""
        if not self.state.running():
            return
        players = self.game.get_player_list()
        monsters = self.game.get_monsters()
        grid = self.game.get_grid()
        width, height = self.game.get_size()
        return RenderState(
            width=width,
            height=height,
            tilemap=grid,
            players=players,
            monsters=monsters,
        )

    def update_state(self):
        if not self.state.running():
            return
        while True:
            self.game.update_state()
            time.sleep(0.1)

    ##################
    # networking
    ##################

    def on_control(self, msg: ClientControl, ctx: ClientContext):
        """test contolling"""
        if not self.state.running():
            return

        player = self.game.get_player(ctx.state.name)
        cmd = msg.command
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

        if self.MAX_PING_BUFFER > 1:
            if len(self.pings) > self.MAX_PING_BUFFER:
                drop_n = self.MAX_PING_BUFFER // 2  # e.g. 50 when MAX=100
            oldest_keys = sorted(self.pings, key=lambda k: self.pings[k].timestamp)[
                :drop_n
            ]
            for k in oldest_keys:
                self.pings.pop(k, None)

    def on_name(self, msg: Name, ctx: ClientContext) -> None:
        ctx.name = msg.name
        self.players.append(msg.name)
        self.game.create_player(msg.name)

    def on_chat(self, msg: ChatText, ctx: ClientContext) -> None:
        sender = ctx.name or "?"
        ctx.broadcast(ChatText(text=f"<{sender}> {msg.text}"), exclude_self=True)

    def on_pong(self, msg: Pong, ctx: ClientContext) -> None:
        received = time.time_ns()
        version = 3
        ping = self.pings[msg.ping_UUID]
        # send time
        if version == 1:
            dt = msg.received - ping.timestamp
        # receive time
        elif version == 2:
            dt = received - msg.timestamp
        # roundtrip
        elif version == 3:
            dt = received - ping.timestamp
        else:
            dt = 0

        if self.MAX_PING_BUFFER == 1:
            self.pings.pop(msg.ping_UUID, None)

        self.pong_count += 1

        if self.average_ping < 0:
            self.average_ping = dt
        else:
            self.average_ping = (self.average_ping * (self.ping_count - 1) + dt) / (
                self.ping_count
            )
        avg_s: float = self.average_ping / 1e9

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
    ready = server.run_lobby()
    if not ready:
        exit(0)
    # ping_thread = threading.Thread(
    #     target=ping, daemon=True, kwargs={"server": server}
    # )
    # ping_thread.start()

    # state = server.get_render_state()
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

    server.start_game()
    renderer = GameRenderer(server, renderer_config)
    renderer.run()


if __name__ == "__main__":
    main()
