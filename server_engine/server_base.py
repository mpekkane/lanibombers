"""
Server-side test runner with pluggable UI.

Modes:
    --ui console   original print/input style
    --ui curses    simple ncurses dashboard for lobby and score display
"""

from __future__ import annotations

import uuid
from typing import Dict, List, Optional, Callable

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
    ClientConnectionStateMessage,
    ClientConnectionState,
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
from common.player_constants import BASE_DIGGING_POWER


class BomberServerBase:
    """
    Base server.

    Contains networking, game state, shop logic, scoring, and callbacks.

    Subclasses should override UI-facing methods such as:
        - run_lobby()
        - show_scores()
        - show_end_message()
        - show_ping_stats()
    """

    def __init__(
        self,
        cfg: str,
        session_setup: str,
        headless: bool,
        map_path: Optional[str],
        log: Optional[LogFn] = None,
    ) -> None:
        self.log: LogFn = log or print
        self.state_machine = ServerStateMachine()
        self.headless = headless

        self.session = Session.parse_session(session_setup)
        if not self.session.valid:
            self.session = Session.get_single_map_session(map_path)

        assert self.session.valid

        # Networking
        self.server = BomberNetworkServer(cfg)

        self.server.set_callback(Name, self.on_name)
        self.server.set_callback(ChatText, self.on_chat)
        self.server.set_callback(Pong, self.on_pong)
        self.server.set_callback(ClientControl, self.on_control)
        self.server.set_callback(ClientSelect, self.on_select)
        self.server.set_disconnect_handler(self.on_disconnect)

        # Network listener is opened only when entering LOBBY from STOPPED.
        self._networking_started = False

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

        self.engine: Optional[GameEngine] = None
        self.sound_engine: Optional[SoundEngine] = None

        self.rounds_left: int = self.session.rounds_left()

        # Keep False for curses UI, otherwise prints corrupt the screen.
        self.debug_prints = False
        self.end_screen_wait_time = 5

    ##################
    # Networking lifecycle
    ##################

    def _start_networking(self) -> None:
        """
        Start accepting client connections.

        Called when progressing from STOPPED -> LOBBY.
        """
        if self._networking_started:
            return

        self.server.start()
        self._networking_started = True
        self.log("Server networking started.")

    def _stop_networking(self) -> None:
        """
        Stop accepting client connections.

        Called when entering STOPPED / after session END.
        """
        if not self._networking_started:
            return

        # First disconnect existing clients.
        self.server.disconnect_all()

        # Then close the listener if the transport implementation supports it.
        stop_fn = getattr(self.server, "stop", None)

        if callable(stop_fn):
            stop_fn()
            self._networking_started = False
            self.log("Server networking stopped.")
        else:
            # Fallback: clients are disconnected, but the listening socket may remain open.
            # Add BomberNetworkServer.stop() for true STOPPED behavior.
            self._networking_started = False
            self.log(
                "Server networking marked stopped, but BomberNetworkServer has no stop()."
            )

    def stop_server(self) -> None:
        """
        Force the server back to STOPPED from any state.

        This is not app quit. It closes the current game/session runtime,
        disconnects clients, stops networking, clears transient state, and
        moves the state machine to STOPPED.
        """
        if self.engine is not None:
            try:
                self.engine.stop()
            except Exception:
                pass

        self.engine = None
        self.sound_engine = None
        self.shop = None
        self.shop_complete = False
        self.map_data = None
        self.game_on_countdown = False

        for player in self.players:
            player.created = False

        self.players.clear()
        self.pings.clear()
        self.average_ping = -1
        self.ping_count = 0
        self.pong_count = 0

        self.server.disconnect_all()
        self._stop_networking()

        self.session.reset()
        self.state_machine.stop()

    def _handle_stop_server_request(self) -> bool:
        if self.state == ServerState.STOPPED:
            return False

        if not self.ui_stop_server_requested():
            return False

        self.stop_server()
        return True

    ##################
    # Main loop
    ##################

    def run_forever(self) -> None:
        self.ui_start()
        try:
            while not self.ui_should_quit():
                self.ui_tick()

                if self._handle_stop_server_request():
                    continue

                self.run_state()
        finally:
            self.ui_stop()

    def run_state(self) -> None:
        state = self.state_machine.get_state()

        if state == ServerState.STARTING:
            self.state_machine.update()

        elif state == ServerState.STOPPED:
            self.run_stopped()

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

    @property
    def state(self) -> ServerState:
        return self.get_state()

    def get_state(self) -> ServerState:
        return self.state_machine.get_state()

    ##################
    # UI hooks
    ##################

    def ui_start(self) -> None:
        pass

    def ui_stop(self) -> None:
        pass

    def ui_tick(self) -> None:
        pass

    def ui_should_quit(self) -> bool:
        return False

    def ui_start_requested(self) -> bool:
        return False

    def ui_show_scores(self) -> None:
        pass

    def ui_show_end_message(self) -> None:
        pass

    def ui_stop_server_requested(self) -> bool:
        return False

    ##################
    # Rendering
    ##################

    def render_callback(self, state: RenderState) -> None:
        self.server.broadcast(GameState.from_render(state), None)  # type: ignore

    def get_render_state(self) -> Optional[RenderState]:
        """Returns RenderState with dimensions and sprite indices."""
        if not self.state_machine.get_state().running():
            return None
        if self.engine is None:
            return None
        return self.engine.get_render_state()

    def get_render_state_unsafe(self) -> RenderState:
        """Returns RenderState and plays local server-side sounds."""
        assert self.engine is not None

        state = self.engine.get_render_state()

        if self.sound_engine and state.sounds:
            for sound in state.sounds:
                self._play_sound(sound)

        return state

    def _play_sound(self, sound_type: int) -> None:
        se = self.sound_engine
        if se is None:
            return

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

    ##################
    # Stopped
    ##################

    def run_stopped(self) -> None:
        self._stop_networking()

        while self.state == ServerState.STOPPED and not self.ui_should_quit():
            self.ui_tick()

            if self.ui_start_requested():
                self.players.clear()
                self.shop = None
                self.shop_complete = False
                self.map_data = None
                self.game_on_countdown = False
                self.engine = None
                self.sound_engine = None

                self._start_networking()
                self.state_machine.update()
                return

            Clock.sleep(0.1)

    ##################
    # Lobby
    ##################

    def run_lobby(self) -> None:
        ready = False

        while not ready and not self.ui_should_quit():
            self.ui_tick()

            if self._handle_stop_server_request():
                return

            if len(self.players) > 0:
                if self.ui_start_requested():
                    ready = True
            else:
                Clock.sleep(0.1)

        if ready:
            self.state_machine.update()

    ##################
    # Map/session
    ##################

    def generate_next_map(self) -> None:
        self.rounds_left = self.session.rounds_left()
        next_map = self.session.get_next_map()

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

    ##################
    # Shop
    ##################

    def run_shop(self) -> None:
        self.generate_next_map()
        self.shop_complete = False
        self._update_shop()
        self._send_shop()

        while not self.shop_complete and not self.ui_should_quit():
            self.ui_tick()

            if self._handle_stop_server_request():
                return

            Clock.sleep(1)

        if self.shop_complete:
            self.state_machine.update()

    def _update_shop(self) -> None:
        if self.shop is None:
            self.shop = Shop(
                players=self.players,
                dynamic_pricing=self.session.floating_market,
            )
        else:
            self.shop.players = self.players
            self.shop.reset_shop()

    def _send_shop(self) -> None:
        if self.shop is None:
            return
        self.server.broadcast(ShopState.from_shop(self.shop), None)

    ##################
    # Game
    ##################

    def start_game(self) -> None:
        assert self.map_data is not None

        self.engine = GameEngine(
            self.map_data.width,
            self.map_data.height,
            spawn_type=self.session.spawn_type,
            max_round_time=self.session.round_time,
        )
        self.engine.set_render_callback(self.render_callback)
        self.engine.load_map(self.map_data)
        self.engine.set_starting_points(num_players=len(self.players))

        self.sound_engine = (
            SoundEngine(music_volume=0.5, fx_volume=1.0) if not self.headless else None
        )

        for player in self.players:
            if not player.created:
                self.create_game_player(player)
                player.created = True

        self.render_callback(self.engine.get_render_state())
        self.run_game()

    def run_game(self) -> None:
        assert self.engine is not None

        self.game_on_countdown = True
        countdown_length = 5
        count = -1
        start = Clock.now()
        elapsed = Clock.now() - start

        while elapsed < countdown_length and not self.ui_should_quit():
            self.ui_tick()

            if self._handle_stop_server_request():
                return

            elapsed = Clock.now() - start
            new_count = countdown_length - int(elapsed)

            if new_count != count:
                count = new_count
                self.server.broadcast(Countdown(count=count))

            # Broadcast render state every tick so inventory selections
            # made via on_select during the countdown become visible to
            # all clients in real time (the engine isn't running yet, so
            # nothing else triggers state broadcasts here).
            self.render_callback(self.engine.get_render_state())

            Clock.sleep(0.1)

        self.engine.start()
        self.game_on_countdown = False

        while self.engine.running and not self.ui_should_quit():
            self.ui_tick()

            if self._handle_stop_server_request():
                return

            render_state = self.engine.get_render_state()
            self.server.broadcast(GameState.from_render(render_state), None)

            Clock.sleep(1)

        self.engine.stop()

        points_by_name = self.score_players()

        for player in self.players:
            player.created = False

            gp = self.engine.get_player_by_name(player.name)
            if gp is not None:
                player.inventory = gp.inventory
                player.money = gp.money
                player.tools = {}
                player.dig_power = BASE_DIGGING_POWER
                player.max_health = 100

            player.score += points_by_name[player.name]

        self.engine = None
        self.ui_show_scores()

        quit_session = self.session.session_complete()
        self.state_machine.update(quit=quit_session)

        if quit_session:
            info = SessionInfo(
                rounds_left=0,
                width=0,
                height=0,
                tilemap=np.array([]),
                pickups=[],
            )
            self.server.broadcast(info, None)

    def score_players(self) -> Dict[str, int]:
        """
        Survivors get max points.

        Dead players get points by death order:
            earliest death -> 1
            latest death   -> n_players - n_survivors
        """
        assert self.engine is not None

        n_players = len(self.players)
        score_data = np.array(self.engine.player_death_times, dtype=object)

        if len(score_data) > 0:
            death_times = score_data[:, 2].astype(dtype=np.float32)
            sort_indices = np.argsort(death_times)
            dead_names_in_order = list(score_data[sort_indices, 1])
        else:
            dead_names_in_order = []

        dead_names = set(dead_names_in_order)

        survivor_names = [
            player.name for player in self.players if player.name not in dead_names
        ]

        points_by_name: Dict[str, int] = {}

        for name in survivor_names:
            points_by_name[name] = n_players

        for death_rank, name in enumerate(dead_names_in_order):
            points_by_name[name] = death_rank + 1

        return points_by_name

    def get_scoreboard_rows(self) -> List[tuple[str, int]]:
        rows = [(p.name, int(p.score)) for p in self.players]
        rows.sort(key=lambda row: row[1], reverse=True)
        return rows

    def end_game(self) -> None:
        self.ui_show_end_message()

        start = Clock.now()
        dt = Clock.now() - start

        while dt < self.end_screen_wait_time and not self.ui_should_quit():
            self.ui_tick()

            if self._handle_stop_server_request():
                return

            self.server.broadcast(Scoreboard(players=self.players), None)

            Clock.sleep(1)
            dt = Clock.now() - start

        self.server.disconnect_all()
        self._stop_networking()
        self.session.reset()
        self.state_machine.update()

    def update_state(self) -> None:
        if not self.state.running():
            return
        if self.engine is None:
            return

        while True:
            self.engine.update_player_state()
            Clock.sleep(0.1)

    ##################
    # Networking callbacks
    ##################

    def on_control(self, msg: ClientControl, ctx: ClientContext) -> None:
        current_state = self.state_machine.get_state()

        if current_state == ServerState.GAME:
            if not self.game_on_countdown:
                self._on_control_game(msg, ctx)
        elif current_state == ServerState.SHOP:
            self._on_control_shop(msg, ctx)

    def _on_control_shop(self, msg: ClientControl, ctx: ClientContext) -> None:
        if self.shop is None:
            return

        cmd: Action = msg.command  # type: ignore
        assert isinstance(cmd, Action)

        player = None
        if ctx.state.name is not None:
            player = self.get_player(ctx.state.name)

        if player is None:
            return

        if cmd in (Action.RIGHT, Action.LEFT, Action.UP, Action.DOWN):
            self.shop.move_player(player.id, cmd)

        if cmd == Action.FIRE:
            self.shop.purchase_current(player.id)

        self.shop_complete = self.shop.all_done
        self._send_shop()

    def _on_control_game(self, msg: ClientControl, ctx: ClientContext) -> None:
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
                            entity=player,
                            action=cmd,
                            timestamp=now,
                            bomb=bomb,
                        )
                    )

            elif cmd == Action.REMOTE:
                self.engine.input_queue.submit(
                    InputCommand(entity=player, action=cmd, timestamp=now)
                )

    def on_select(self, msg: ClientSelect, ctx: ClientContext) -> None:
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

        player.select(target_type)

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
                drop_n = self.MAX_PING_BUFFER // 2
            else:
                drop_n = len(self.pings)

            oldest_keys = sorted(
                self.pings,
                key=lambda k: self.pings[k].timestamp,
            )[:drop_n]

            for key in oldest_keys:
                self.pings.pop(key, None)

    def on_name(self, msg: Name, ctx: ClientContext) -> None:
        ctx.name = msg.name  # type: ignore

        player_name = msg.name
        player_color = msg.color
        player_appearance = msg.appearance_id

        self.players.append(
            SessionPlayer(
                name=player_name,
                color=player_color,
                appearance=player_appearance,
                money=self.session.starting_money,
            )
        )  # type: ignore

        self.server.send_to_client(
            ctx, ClientConnectionStateMessage(ClientConnectionState.CONNECTED)
        )

    def create_game_player(self, session_player: SessionPlayer) -> None:
        assert self.engine is not None

        self.engine.create_player(session_player)  # type: ignore
        player = self.engine.get_player_by_name(session_player.name)  # type: ignore

        if player is not None:
            player.color = session_player.color  # type: ignore
            player.sprite_id = session_player.appearance  # type: ignore
            player.initialize_player(self.session.starting_money)

    def get_player(self, name: str) -> SessionPlayer:
        for player in self.players:
            if player.name == name:
                return player

        raise ValueError("Unknown player")

    def on_chat(self, msg: ChatText, ctx: ClientContext) -> None:
        sender = ctx.name or "?"
        ctx.broadcast(
            ChatText(text=f"<{sender}> {msg.text}"),
            exclude_self=False,
        )  # type: ignore

    def on_pong(self, msg: Pong, ctx: ClientContext) -> None:
        received = Clock.now_ns()

        ping = self.pings.get(msg.ping_UUID)  # type: ignore
        if ping is None:
            return

        dt = received - ping.timestamp

        if self.MAX_PING_BUFFER == 1:
            self.pings.pop(msg.ping_UUID, None)  # type: ignore

        self.pong_count += 1

        if self.average_ping < 0:
            self.average_ping = dt
        else:
            self.average_ping = (
                self.average_ping * (self.ping_count - 1) + dt
            ) // self.ping_count

        avg_s = self.average_ping / 1e9

        if self.debug_prints and self.ping_count % 100 == 0:
            self.show_ping_stats(avg_s)

    def on_disconnect(self, ctx: ClientContext) -> None:
        name = ctx.name

        if name is None:
            return

        if self.state == ServerState.GAME and self.engine is not None:
            self.engine.remove_player(name)

        if self.state == ServerState.SHOP and self.shop is not None:
            self.shop.remove_player(name)

        for player in list(self.players):
            if player.name == name:
                self.players.remove(player)


def ping_thread(server: BomberServerBase) -> None:
    last_ping = Clock.now()
    tick = 0.1

    while True:
        if Clock.now() - last_ping > tick:
            server.ping()
            last_ping = Clock.now()

        Clock.sleep(tick / 2)
