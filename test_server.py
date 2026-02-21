"""
Test code for server-side
"""

import uuid
import time
from enum import IntEnum
from typing import Dict, List, Optional
from argparse import ArgumentParser
from pathlib import Path
from network_stack.bomber_network_server import BomberNetworkServer, ClientContext
from network_stack.messages.messages import (
    Name,
    ChatText,
    Ping,
    Pong,
    ClientControl,
    GameState,
)
from game_engine.clock import Clock
from game_engine.entities import Direction
from game_engine.render_state import RenderState
from game_engine.agent_state import Action
from game_engine.map_loader import load_map
from game_engine import GameEngine
from game_engine.random_map_generator import RandomMapGenerator
from renderer.game_renderer import GameRenderer


class ServerState(IntEnum):
    STARTING = 1
    LOBBY = 2
    SHOP = 3
    GAME = 4
    END = 5

    def running(self) -> bool:
        return int(self) > 2


class BomberServer:
    def __init__(self, cfg: str, map_path: str, headless: bool) -> None:
        self.state = ServerState.STARTING

        if map_path:
            map_data = load_map(map_path)
        else:
            random_map_generator = RandomMapGenerator()
            map_data = random_map_generator.generate()

        # game engine
        self.engine = GameEngine(map_data.width, map_data.height, headless)
        self.engine.set_render_callback(self.render_callback)
        self.engine.load_map(map_data)

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
        self.players: List[str] = []

    def render_callback(self, state: RenderState) -> None:
        self.server.broadcast(GameState.from_render(state), None)  # type: ignore

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
                Clock.sleep(1)
        return self.state == ServerState.GAME

    def start_game(self) -> None:
        # FIXME: temp to check logic
        self.state = ServerState.GAME
        self.engine.start()
        self.render_callback(self.engine.get_render_state())
        # update_thread = threading.Thread(target=self.update_state, daemon=True)
        # update_thread.start()

    ##################
    # game engine
    ##################

    def get_render_state(self) -> Optional[RenderState]:
        """Returns RenderState with dimensions and sprite indices"""
        if not self.state.running():
            return
        return self.engine.get_render_state()

    def get_render_state_unsafe(self) -> RenderState:
        """Returns RenderState with dimensions and sprite indices"""
        return self.engine.get_render_state()

    def update_state(self):
        if not self.state.running():
            return
        while True:
            self.engine.update_player_state()
            Clock.sleep(0.1)

    ##################
    # networking
    ##################

    def on_control(self, msg: ClientControl, ctx: ClientContext):
        """test contolling"""
        if not self.state.running():
            return

        if ctx.state.name is not None:
            player = self.engine.get_player_by_name(ctx.state.name)
        else:
            player = self.engine.get_player_by_name("unnamed")

        if player is None:
            return

        if player.state == "dead":
            return

        cmd: Action = msg.command  # type: ignore
        assert isinstance(cmd, Action)
        if cmd.is_move():
            if cmd == Action.RIGHT:
                if player.direction == Direction.RIGHT and player.state == "walk":
                    return
                player.direction = Direction.RIGHT
                player.state = "walk"
            elif cmd == Action.LEFT:
                if player.direction == Direction.LEFT and player.state == "walk":
                    return
                player.direction = Direction.LEFT
                player.state = "walk"
            elif cmd == Action.UP:
                if player.direction == Direction.UP and player.state == "walk":
                    return
                player.direction = Direction.UP
                player.state = "walk"
            elif cmd == Action.DOWN:
                if player.direction == Direction.DOWN and player.state == "walk":
                    return
                player.direction = Direction.DOWN
                player.state = "walk"
            elif cmd == Action.STOP:
                player.state = "idle"

            self.engine.change_entity_direction(player)
        else:
            if cmd == Action.FIRE:
                bomb = player.plant_bomb()
                if bomb is not None:
                    self.engine.plant_bomb(bomb)
            elif cmd == Action.CHOOSE:
                bomb = player.choose()
            elif cmd == Action.REMOTE:
                # TODO: trigger remote bomb
                self.engine.detonate_remotes(player)

    def _ensure_timestamp(self, msg: Ping) -> None:
        if getattr(msg, "timestamp", None) is None:
            object.__setattr__(msg, "timestamp", Clock.now_ns())

    def ping(self) -> None:
        uid = str(uuid.uuid4())
        ping = Ping(uid)  # type: ignore
        self._ensure_timestamp(ping)
        self.server.broadcast(ping)
        self.ping_count += 1
        self.pings[ping.UUID] = ping  # type: ignore

        if self.MAX_PING_BUFFER > 1:
            if len(self.pings) > self.MAX_PING_BUFFER:
                drop_n = self.MAX_PING_BUFFER // 2  # e.g. 50 when MAX=100
            else:
                drop_n = len(self.pings)
            oldest_keys = sorted(self.pings, key=lambda k: self.pings[k].timestamp)[
                :drop_n
            ]
            for k in oldest_keys:
                self.pings.pop(k, None)

    def on_name(self, msg: Name, ctx: ClientContext) -> None:
        print(f"got {msg.name}")
        ctx.name = msg.name  # type: ignore
        self.players.append(msg.name)  # type: ignore
        self.engine.create_player(msg.name)  # type: ignore
        # FIXME: debug testing
        player = self.engine.get_player_by_name(msg.name)  # type: ignore
        if player is not None:
            player.test_inventory()

    def on_chat(self, msg: ChatText, ctx: ClientContext) -> None:
        sender = ctx.name or "?"
        ctx.broadcast(ChatText(text=f"<{sender}> {msg.text}"), exclude_self=True)  # type: ignore

    def on_pong(self, msg: Pong, ctx: ClientContext) -> None:
        received = Clock.now_ns()
        ping = self.pings[msg.ping_UUID]  # type: ignore
        dt = received - ping.timestamp

        if self.MAX_PING_BUFFER == 1:
            self.pings.pop(msg.ping_UUID, None)  # type: ignore

        self.pong_count += 1

        if self.average_ping < 0:
            self.average_ping = dt
        else:
            self.average_ping = (self.average_ping * (self.ping_count - 1) + dt) // (
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
    last_ping = Clock.now()
    tick = 0.1
    while True:
        if Clock.now() - last_ping > tick:
            server.ping()
            last_ping = Clock.now()
        Clock.sleep(tick / 2)


def main() -> None:
    assert Path("assets").exists(), "Assets missing"
    parser = ArgumentParser()
    parser.add_argument("--cfg", "-c", type=str, default="cfg/server_config.yaml")
    parser.add_argument("--map", "-m", type=str, default="")
    # FIXME: might wanna flip this in final version
    parser.add_argument("--headless", "-hl", action="store_true", default=False)
    args = parser.parse_args()
    cfg = args.cfg
    map_path = args.map
    headless = args.headless
    server = BomberServer(cfg, map_path, headless)
    ready = server.run_lobby()
    if not ready:
        exit(0)
    # ping_thread = threading.Thread(
    #     target=ping, daemon=True, kwargs={"server": server}
    # )
    # ping_thread.start()

    # state = server.get_render_state()
    server.start_game()
    if headless:
        while True:
            # FIXME: debug
            state = server.get_render_state()
            if state is not None:
                print(state.players[0].x, state.players[0].y)
            time.sleep(1)
    else:
        renderer = GameRenderer(
            server.get_render_state_unsafe, window_name="lanibombers server"
        )
        renderer.initialize()
        renderer.run()


if __name__ == "__main__":
    main()
