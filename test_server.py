"""
Test code for server-side
"""

import uuid
import time
from enum import IntEnum
from typing import Dict, List, Optional, Tuple
from argparse import ArgumentParser
from pathlib import Path
from network_stack.bomber_network_server import BomberNetworkServer, ClientContext
from network_stack.messages.messages import (
    Name,
    ChatText,
    Ping,
    Pong,
    ClientControl,
    ClientSelect,
    GameState,
)
from game_engine.clock import Clock
from game_engine.entities import Direction
from game_engine.render_state import RenderState
from game_engine.agent_state import Action
from game_engine.input_queue import InputCommand
from common.bomb_dictionary import BombType
from game_engine import GameEngine
from game_engine.sound_engine import SoundEngine
from game_engine.render_state import SoundType
import arcade
from renderer.game_renderer import GameView
from renderer.lanibombers_window import LanibombersWindow
from game_engine.entities import Player
from game_engine.session_parser import Session, SessionMap, SessionMapType
from game_engine.map_loader import load_map
from game_engine.random_map_generator import RandomMapGenerator
from game_engine.state_machine import ServerState


class SessionPlayer:

    def __init__(
        self,
        name: str,
        data: Optional[Player],
        color: Tuple[int, int, int],
        appearance: int,
    ) -> None:
        self.name = name
        self.player = data
        self.color = color
        self.appearance = appearance
        self.created = False

    def set_player(self, player: Player) -> None:
        self.player = player

    def get_player(self) -> Optional[Player]:
        return self.player


class BomberServer:
    def __init__(
        self, cfg: str, session_setup: str, headless: bool, map_path: Optional[str]
    ) -> None:
        self.state = ServerState.STARTING
        self.headless = headless
        self.session = Session.parse_session(session_setup)
        if not self.session.valid:
            self.session = Session.get_single_map_session(map_path)

        assert self.session.valid
        # networking
        self.server = BomberNetworkServer(cfg)

        self.server.set_callback(Name, self.on_name)
        self.server.set_callback(ChatText, self.on_chat)
        self.server.set_callback(Pong, self.on_pong)
        self.server.set_callback(ClientControl, self.on_control)
        self.server.set_callback(ClientSelect, self.on_select)
        self.server.start()

        self.pings: Dict[str, Ping] = {}
        self.average_ping: int = -1
        self.ping_count = 0
        self.pong_count = 0
        self.MAX_PING_BUFFER = 1
        self.players: List[SessionPlayer] = []

    def get_state(self) -> ServerState:
        return self.state

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
                    print(f"{i+1}: {player.name}")
                inp = input("start game? y/n")
                if inp == "y":
                    self.state = ServerState.GAME
            else:
                print("No players in the lobby")
                Clock.sleep(1)
        return self.state == ServerState.GAME

    def start_game(self) -> None:
        next_map = self.session.get_next_map()
        if next_map.type == SessionMapType.LOAD:
            map_data = load_map(next_map.map_path)
        else:
            random_map_generator = RandomMapGenerator()
            map_data = random_map_generator.generate(
                next_map.width,
                next_map.height,
                next_map.feature_sizes,
                next_map.threshold,
                next_map.min_treasure,
                next_map.max_treasure,
                next_map.min_tools,
                next_map.max_tools,
                next_map.max_rooms,
                next_map.room_chance,
            )
        # game engine
        self.engine = GameEngine(map_data.width, map_data.height)
        self.engine.set_render_callback(self.render_callback)
        self.engine.load_map(map_data)

        # local sound engine for server-side rendering
        self.sound_engine = (
            SoundEngine(music_volume=0.5, fx_volume=1.0) if not self.headless else None
        )

        # create players
        for player in self.players:
            if not player.created:
                self.create_player(player)
                player.created = True

        # FIXME: temp to check logic
        self.state = ServerState.GAME
        self.engine.start()
        if self.sound_engine:
            self.sound_engine.game()
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
        state = self.engine.get_render_state()
        if self.sound_engine and state.sounds:
            for sound in state.sounds:
                self._play_sound(sound)
        return state

    def _play_sound(self, sound_type: int) -> None:
        """Play a sound effect locally via the server's sound engine."""
        se = self.sound_engine
        if sound_type == SoundType.EXPLOSION:
            se.explosion()
        elif sound_type == SoundType.SMALL_EXPLOSION:
            se.small_explosion()
        elif sound_type == SoundType.URETHANE:
            se.urethane()
        elif sound_type == SoundType.DIG:
            se.dig()
        elif sound_type == SoundType.TREASURE:
            se.treasure()
        elif sound_type == SoundType.DIE:
            se.die()

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
        """Handle player control input via the input queue."""
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
        now = Clock.now()

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

            self.engine.input_queue.submit(
                InputCommand(entity=player, action=cmd, timestamp=now)
            )
        else:
            if cmd == Action.FIRE:
                bomb = player.plant_bomb()
                if bomb is not None:
                    self.engine.input_queue.submit(
                        InputCommand(
                            entity=player, action=cmd, timestamp=now, bomb=bomb
                        )
                    )
            elif cmd == Action.CHOOSE:
                player.choose()
            elif cmd == Action.REMOTE:
                self.engine.input_queue.submit(
                    InputCommand(entity=player, action=cmd, timestamp=now)
                )

    def on_select(self, msg: ClientSelect, ctx: ClientContext):
        """Handle weapon selection by bomb type."""
        if not self.state.running():
            return

        if ctx.state.name is not None:
            player = self.engine.get_player_by_name(ctx.state.name)
        else:
            player = self.engine.get_player_by_name("unnamed")

        if player is None:
            return

        all_types = list(BombType)
        if msg.bomb_type < 0 or msg.bomb_type >= len(all_types):
            return
        target_type = all_types[msg.bomb_type]
        for i, (bomb_type, _count) in enumerate(player.inventory):
            if bomb_type == target_type:
                player.selected = i
                return

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
        ctx.name = msg.name  # type: ignore
        player_name = msg.name
        player_color = msg.color
        player_appearance = msg.appearance_id
        self.players.append(SessionPlayer(player_name, None, player_color, player_appearance))  # type: ignore

    def create_player(self, session_player: SessionPlayer) -> None:
        self.engine.create_player(session_player.name)  # type: ignore
        player = self.engine.get_player_by_name(session_player.name)  # type: ignore
        if player is not None:
            player.color = session_player.color  # type: ignore
            player.sprite_id = session_player.appearance  # type: ignore
            player.initialize_player(self.session.starting_money)

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
    parser.add_argument("--session", "-s", type=str, default="cfg/session.yaml")
    parser.add_argument("--display", "-d", action="store_true", default=False)
    args = parser.parse_args()
    cfg = args.cfg
    map_path = args.map
    headless = not args.display
    session = args.session
    server = BomberServer(cfg, session, headless, map_path)
    ready = server.run_lobby()
    if not ready:
        exit(0)

    # TODO: implement server states
    state = server.get_state()
    if state == ServerState.GAME:
        server.start_game()
        if headless:
            while True:
                _ = server.get_render_state()
                time.sleep(1)
        else:
            window = LanibombersWindow()
            view = GameView(server.get_render_state_unsafe)
            window.show_view(view)
            arcade.run()
    elif state == ServerState.SHOP:
        # TODO: shop logic
        pass
    elif state == ServerState.END:
        # TODO: end logic
        pass
    elif state == ServerState.LOBBY:
        raise ValueError("Invalid session state")
    elif state == ServerState.STARTING:
        raise ValueError("Invalid session state")
    else:
        raise ValueError("Invalid session state")


if __name__ == "__main__":
    main()
