"""
Test code for server-side
"""

import sys
import select
import uuid
from typing import Dict, List, Optional
from argparse import ArgumentParser
from pathlib import Path
import numpy as np
from network_stack.bomber_network_server import BomberNetworkServer, ClientContext
from network_stack.messages.messages import (
    Name,
    ChatText,
    Ping,
    Pong,
    ClientControl,
    ClientSelect,
    GameState,
    ShopState,
    Scoreboard,
    SessionInfo,
    Countdown,
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
from game_engine.session_parser import (
    Session,
    SessionMapType,
    SessionPlayer,
)
from game_engine.map_loader import load_map
from game_engine.random_map_generator import RandomMapGenerator
from game_engine.state_machine import ServerState, ServerStateMachine
from game_engine.shop import Shop
from game_engine.spawn_points import SpawnType


class BomberServer:
    def __init__(
        self, cfg: str, session_setup: str, headless: bool, map_path: Optional[str]
    ) -> None:
        self.state_machine = ServerStateMachine()
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
        self.server.set_disconnect_handler(self.on_disconnect)
        self.server.start()

        self.pings: Dict[str, Ping] = {}
        self.average_ping: int = -1
        self.ping_count = 0
        self.pong_count = 0
        self.MAX_PING_BUFFER = 1
        self.players: List[SessionPlayer] = []

        self.shop: Optional[Shop] = None
        self.shop_complete = False
        self.map_data = None
        self.game_on_countdown = False

        self.max_round_time = 60
        self.engine = None

    def run_state(self) -> None:
        state = self.state_machine.get_state()

        if state == ServerState.STARTING:
            return
        elif state == ServerState.LOBBY:
            self.run_lobby()
        elif state == ServerState.SHOP:
            self.run_shop()
        elif state == ServerState.GAME:
            self.start_game()
        elif state == ServerState.END:
            self.end_game()
        else:
            raise ValueError("Invalid server state")

    def next_state(self) -> None:
        self.state_machine.update(quit=self.session.session_complete())

        if self.session.session_complete():
            info = SessionInfo(
                rounds_left=0,
                width=0,
                height=0,
                tilemap=np.array([]),
                pickups=[],
            )
            self.server.broadcast(info, None)

    @property
    def state(self) -> ServerState:
        return self.get_state()

    def get_state(self) -> ServerState:
        return self.state_machine.get_state()

    def render_callback(self, state: RenderState) -> None:
        self.server.broadcast(GameState.from_render(state), None)  # type: ignore

    def timed_input(self, prompt: str, timeout: float) -> str | None:
        print(prompt, end="", flush=True)

        ready, _, _ = select.select([sys.stdin], [], [], timeout)

        if ready:
            return sys.stdin.readline().strip()

        print("")
        return None

    def run_lobby(self) -> None:
        ready = False

        while not ready:
            print("")
            print("Hosting a LAN server")

            if len(self.players) > 0:
                print("Players in the lobby")
                for i, player in enumerate(self.players):
                    print(f"{i + 1}: {player.name}")

                inp = self.timed_input("start game? y/n ", timeout=1.0)

                if inp == "y":
                    ready = True

            else:
                print("No players in the lobby")
                Clock.sleep(1)

    def generate_next_map(self) -> None:
        next_map = self.session.get_next_map()
        self.rounds_left = self.session.rounds_left()
        if next_map.type == SessionMapType.LOAD:
            self.map_data = load_map(next_map.map_path)
        else:
            random_map_generator = RandomMapGenerator()
            self.map_data = random_map_generator.generate(
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
        info = SessionInfo(
            rounds_left=self.rounds_left,
            width=self.map_data.width,
            height=self.map_data.height,
            tilemap=GameEngine.tilemap_to_numpy(self.map_data.tiles),
            pickups=self.map_data.treasures,
        )
        self.server.broadcast(info, None)

    def run_shop(self) -> None:
        self.generate_next_map()
        self.shop_complete = False
        self._update_shop()
        self._send_shop()
        while not self.shop_complete:
            Clock.sleep(1)

    def start_game(self) -> None:
        assert self.map_data is not None

        # game engine
        self.engine = GameEngine(
            self.map_data.width,
            self.map_data.height,
            spawn_type=self.session.spawn_type,
            max_round_time=self.max_round_time,
        )
        self.engine.set_render_callback(self.render_callback)
        self.engine.load_map(self.map_data)
        self.engine.set_starting_points(num_players=len(self.players))

        # local sound engine for server-side rendering
        self.sound_engine = (
            SoundEngine(music_volume=0.5, fx_volume=1.0) if not self.headless else None
        )

        # create players
        for player in self.players:
            if not player.created:
                self.create_game_player(player)
                player.created = True

        # FIXME: temp to check logic
        # self.state = ServerState.GAME
        # self.engine.start()
        # if self.sound_engine:
        #     self.sound_engine.game()
        self.render_callback(self.engine.get_render_state())
        # update_thread = threading.Thread(target=self.update_state, daemon=True)
        # update_thread.start()

        self.run_game()

    def run_game(self) -> None:
        # round countdown
        self.game_on_countdown = True
        countdown_length = 10
        count = -1
        start = Clock.now()
        elapsed = Clock.now() - start
        while elapsed < countdown_length:
            elapsed = Clock.now() - start
            new_count = countdown_length - int(elapsed)
            if new_count != count:
                count = new_count
                self.server.broadcast(Countdown(count=count))
            Clock.sleep(0.1)

        self.engine.start()
        self.game_on_countdown = False

        # wait while running
        while self.engine.running:
            render_state = self.engine.get_render_state()
            self.server.broadcast(GameState.from_render(render_state), None)

            Clock.sleep(1)

        self.engine.stop()
        # round has ended, clean up player object, award score
        points_by_name = self.score_players()
        for player in self.players:
            player.created = False

            gp = self.engine.get_player_by_name(player.name)
            if gp is not None:
                player.inventory = gp.inventory
                player.money = gp.money
                player.tools = gp.tools
                player.dig_power = gp.dig_power

            player.score += points_by_name[player.name]
        self.engine = None

        self._print_scores()

    def score_players(self):
        # round has ended, clean up player object, award score
        # self.player_death_times: List[Tuple[UUID, str, float]]

        n_players = len(self.players)

        score_data = np.array(self.engine.player_death_times, dtype=object)

        if len(score_data) > 0:
            death_times = score_data[:, 2].astype(dtype=np.float32)
            sort_indices = np.argsort(death_times)

            # Earliest death first
            dead_names_in_order = list(score_data[sort_indices, 1])
        else:
            dead_names_in_order = []

        dead_names = set(dead_names_in_order)

        survivor_names = [
            player.name for player in self.players if player.name not in dead_names
        ]

        points_by_name = {}

        # All survivors get the maximum score
        for name in survivor_names:
            points_by_name[name] = n_players

        # Dead players get increasing points by survival order:
        # earliest death gets 1, latest death gets n_players - n_survivors
        for death_rank, name in enumerate(dead_names_in_order):
            points_by_name[name] = death_rank + 1

        return points_by_name

    def _print_scores(self) -> None:
        datalist = []
        for i, p in enumerate(self.players):
            datalist.append((p.name, p.score))
        data = np.array(datalist)
        points = data[:, 1].astype(dtype=np.int32)
        indices = np.argsort(points)
        indices = indices[::-1]
        scoreboard = data[indices]
        print("Scoreboard")
        print("="*20)
        for i in range(len(self.players)):
            print(f"{scoreboard[i, 0]} - {scoreboard[i, 1]}")

    def end_game(self) -> None:
        print("Game has ended.")
        start = Clock.now()
        dt = Clock.now() - start
        while dt < 10.0:
            self.server.broadcast(Scoreboard(players=self.players), None)
            Clock.sleep(1)
            dt = Clock.now() - start
        self.server.disconnect_all()

    ##################
    # game engine
    ##################

    def get_render_state(self) -> Optional[RenderState]:
        """Returns RenderState with dimensions and sprite indices"""
        if not self.state_machine.get_state().running():
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
    # shop
    ##################

    def _update_shop(self) -> None:
        if self.shop is None:
            self.shop = Shop(
                players=self.players, dynamic_pricing=self.session.floating_market
            )
        else:
            self.shop.players = self.players
            self.shop.reset_shop()

    def _send_shop(self) -> None:
        if self.shop is None:
            return
        self.server.broadcast(ShopState.from_shop(self.shop), None)

    ##################
    # networking
    ##################

    def on_control(self, msg: ClientControl, ctx: ClientContext):
        if self.state_machine.get_state() == ServerState.GAME:
            if not self.game_on_countdown:
                self._on_control_game(msg, ctx)
        elif self.state_machine.get_state() == ServerState.SHOP:
            self._on_control_shop(msg, ctx)
        else:
            pass

    def _on_control_shop(self, msg: ClientControl, ctx: ClientContext):
        if self.shop is None:
            return

        cmd: Action = msg.command  # type: ignore
        assert isinstance(cmd, Action)

        if ctx.state.name is not None:
            player = self.get_player(ctx.state.name)

        if player is None:
            return

        if (
            cmd == Action.RIGHT
            or cmd == Action.LEFT
            or cmd == Action.UP
            or cmd == Action.DOWN
        ):
            self.shop.move_player(player.id, cmd)
        if cmd == Action.FIRE:
            self.shop.purchase_current(player.id)

        self.shop_complete = self.shop.all_done
        self._send_shop()

    def _on_control_game(self, msg: ClientControl, ctx: ClientContext):
        """Handle player control input via the input queue."""
        if not self.state.running():
            return
        if self.engine is None:
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

        if self.engine is None:
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
                player.set_selected(i)
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
        self.players.append(SessionPlayer(name=player_name, color=player_color, appearance=player_appearance, money=self.session.starting_money))  # type: ignore

    def create_game_player(self, session_player: SessionPlayer) -> None:
        self.engine.create_player(session_player)  # type: ignore
        player = self.engine.get_player_by_name(session_player.name)  # type: ignore
        if player is not None:
            player.color = session_player.color  # type: ignore
            player.sprite_id = session_player.appearance  # type: ignore
            player.initialize_player(self.session.starting_money)

    def get_player(self, name: str) -> SessionPlayer:
        for p in self.players:
            if p.name == name:
                return p

        raise ValueError("Unknown player")

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

    def on_disconnect(self, ctx: ClientContext) -> None:
        name = ctx.name

        if self.state == ServerState.GAME and self.engine is not None:
            self.engine.remove_player(name)
        if self.state == ServerState.SHOP and self.shop is not None:
            self.shop.remove_player(name)

        for p in self.players:
            if p.name == name:
                self.players.remove(p)


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
    # assert Path("assets").exists(), "Assets missing"
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
    running = True
    while running:
        server.next_state()
        server.run_state()
    # ready = server.run_lobby()
    # if not ready:
    #     exit(0)

    # # TODO: implement server states
    # running = True
    # while running:
    #     state = server.get_state()
    #     if state == ServerState.GAME:
    #         server.start_game()
    #         if headless:
    #             while True:
    #                 _ = server.get_render_state()
    #                 time.sleep(1)
    #         else:
    #             window = LanibombersWindow()
    #             view = GameView(server.get_render_state_unsafe)
    #             window.show_view(view)
    #             arcade.run()
    #     elif state == ServerState.SHOP:
    #         # TODO: shop logic
    #         pass
    #     elif state == ServerState.END:
    #         # TODO: end logic
    #         running = False
    #     elif state == ServerState.LOBBY:
    #         raise ValueError("Invalid session state")
    #     elif state == ServerState.STARTING:
    #         raise ValueError("Invalid session state")
    #     else:
    #         raise ValueError("Invalid session state")


if __name__ == "__main__":
    main()
