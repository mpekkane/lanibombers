"""
Server-side test runner with pluggable UI.

Modes:
    --ui console   original print/input style
    --ui curses    simple ncurses dashboard for lobby and score display
"""

from __future__ import annotations

from dataclasses import replace
from threading import RLock
import uuid
from copy import deepcopy
from typing import Dict, List, Optional, Callable

import numpy as np

from network_stack.bomber_network_server import BomberNetworkServer, ClientContext
from network_stack.servers.transport_server import ServerAddressInUseError
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
    LobbyPlayers,
    JoinMode,
    JoinReply,
)
from game_engine.clock import Clock
from game_engine.entities import Direction, EntityState
from game_engine.render_state import RenderState
from game_engine.agent_state import Action
from game_engine.input_queue import InputCommand

# Action → Direction mapping for movement commands. STOP and non-move
# actions deliberately omitted (look-up returns None for them).
_ACTION_TO_DIRECTION = {
    Action.UP: Direction.UP,
    Action.DOWN: Direction.DOWN,
    Action.LEFT: Direction.LEFT,
    Action.RIGHT: Direction.RIGHT,
}
from common.bomb_dictionary import BombType
from game_engine import GameEngine
from game_engine.sound_engine import SoundEngine
from game_engine.render_state import SoundType
from game_engine.session_parser import (
    ScoringType,
    Session,
    SessionMapType,
    SessionPlayer,
)
from game_engine.map_loader import load_map
from game_engine.random_map_generator import RandomMapGenerator
from game_engine.state_machine import ServerState, ServerStateMachine
from game_engine.shop import Shop
from common.player_constants import BASE_DIGGING_POWER
from game_engine.lighting_effects import LightingEffects


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
        use_lights: bool = False,
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
        self.pending_players: dict[str, SessionPlayer] = {}
        self._disconnected_players: dict[str, SessionPlayer] = {}
        self._admission_lock = RLock()
        self._shop_info: SessionInfo | None = None
        self._latest_game_state: GameState | None = None
        self._countdown: int | None = None

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

        # If DMX enabled lights are connected:
        self.lobby_alert = False
        self.nuke_warning = False
        self.use_lights = use_lights
        if self.use_lights:
            self.lighting_fx = LightingEffects()
            self.lighting_fx.start()
        else:
            self.lighting_fx = None

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

        from network_stack.shared.web_utils import get_local_ip
        from common.logger import get_logger

        ip = get_local_ip()
        get_logger().info(f"Server listening on {ip}:{self.server.port}")
        self.log(f"Server networking started ({ip}:{self.server.port}).")

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
        with self._admission_lock:
            self.state_machine.stop()

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

        with self._admission_lock:
            self.players.clear()
            self.pending_players.clear()
            self._disconnected_players.clear()
            self._shop_info = None
            self._latest_game_state = None
            self._countdown = None
        self.pings.clear()
        self.average_ping = -1
        self.ping_count = 0
        self.pong_count = 0

        self.server.disconnect_all()
        self._stop_networking()

        self.session.reset()
        self.rounds_left = self.session.rounds_left()

        if self.use_lights:
            self.lighting_fx.stop_fx()

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
        try:
            self.ui_start()
            while not self.ui_should_quit():
                self.ui_tick()

                if self._handle_stop_server_request():
                    continue

                self.run_state()
        except ServerAddressInUseError as exc:
            # Port already taken (another server is up on this subnet). Report it
            # clearly and shut down instead of leaving a dead reactor thread.
            self.ui_fatal_error(str(exc))
        finally:
            try:
                self._shutdown_app()
            finally:
                self.ui_stop()

    def _shutdown_app(self) -> None:
        """Release long-lived workers when the server application exits."""
        try:
            if self.engine is not None:
                self.engine.stop()
                self.engine = None
        finally:
            try:
                if self.sound_engine is not None:
                    self.sound_engine.stop_all()
                    self.sound_engine = None
            finally:
                try:
                    self._stop_networking()
                finally:
                    if self.use_lights:
                        # Unlike stop_server(), application shutdown is final.
                        # The DMX worker is non-daemon and must be joined or
                        # Python cannot exit.
                        self.lighting_fx.stop()

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

    def ui_fatal_error(self, message: str) -> None:
        """Surface a fatal error to the user before shutdown.

        Default logs it; GUI UIs override to show a blocking dialog so the
        message is seen even though the window closes immediately afterwards.
        """
        self.log(message)

    ##################
    # Rendering
    ##################

    def render_callback(self, state: RenderState) -> None:
        snapshot = GameState.from_render(state)
        self._latest_game_state = snapshot
        self.server.broadcast(snapshot)

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

                with self._admission_lock:
                    self._start_networking()
                    self.state_machine.update()
                return

            Clock.sleep(0.1)

    ##################
    # Lobby
    ##################

    def run_lobby(self) -> None:
        ready = False
        player_msg_time = 1.0
        prev = -1
        if self.use_lights:
            self.lighting_fx.server()

        while not ready and not self.ui_should_quit():
            self.ui_tick()

            if prev < 0:
                prev = Clock.now()
            else:
                if Clock.now() - prev > player_msg_time:
                    self.server.broadcast(LobbyPlayers(players=self.players))

            if self._handle_stop_server_request():
                return

            if len(self.players) > 0:
                if self.ui_start_requested():
                    ready = True
            else:
                Clock.sleep(0.1)

        if ready:
            self.state_machine.update()

    def toggle_lobby_alert(self) -> None:
        if self.lobby_alert:
            self.unset_lobby_alert()
        else:
            self.set_lobby_alert()

    def set_lobby_alert(self) -> None:
        self.lobby_alert = True
        if self.use_lights:
            self.lighting_fx.server_alert()

    def unset_lobby_alert(self) -> None:
        self.lobby_alert = False
        if self.use_lights:
            self.lighting_fx.server()

    ##################
    # Map/session
    ##################

    def generate_next_map(self) -> SessionInfo:
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

        return SessionInfo(
            rounds_left=self.rounds_left,
            width=self.map_data.width,
            height=self.map_data.height,
            tilemap=GameEngine.tilemap_to_numpy(self.map_data.tiles),
            pickups=self.map_data.treasures,
        )

    ##################
    # Shop
    ##################

    def run_shop(self) -> None:
        info = self.generate_next_map()
        with self._admission_lock:
            self.players.extend(self._take_pending_players())
            self.shop_complete = False
            self._update_shop()
            self._shop_info = info
            self.server.broadcast(info)
            self._send_shop()

        if self.use_lights:
            self.lighting_fx.shop()

        while not self.ui_should_quit():
            self.ui_tick()

            if self._handle_stop_server_request():
                return

            with self._admission_lock:
                if self.shop_complete:
                    self._shop_info = None
                    self.state_machine.update()
                    return

            Clock.sleep(1)

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
        self.server.broadcast(deepcopy(ShopState.from_shop(self.shop)))

    ##################
    # Game
    ##################

    def start_game(self) -> None:
        with self._admission_lock:
            assert self.map_data is not None

            self.engine = GameEngine(
                self.map_data.width,
                self.map_data.height,
                spawn_type=self.session.spawn_type,
                max_round_time=self.session.round_time,
                lighting_fx=self.lighting_fx,
            )
            self.engine.set_render_callback(self.render_callback)
            self.engine.load_map(self.map_data)
            if self.players:
                self.engine.set_starting_points(num_players=len(self.players))
            else:
                self.engine.running = False

            self.sound_engine = (
                SoundEngine(music_volume=0.5, fx_volume=1.0)
                if not self.headless
                else None
            )

            for player in self.players:
                if not player.created:
                    self.create_game_player(player)
                    player.created = True

            self.render_callback(self.engine.get_render_state())
        self.run_game()

    def run_game(self) -> None:
        assert self.engine is not None
        if self.engine.running:
            self._at_round_start()

        if self.use_lights:
            self.lighting_fx.game()

        while self.engine.running and not self.ui_should_quit():
            self.ui_tick()

            if self._handle_stop_server_request():
                return

            render_state = self.engine.get_render_state()
            self.render_callback(render_state)

            if self.use_lights:
                nuke_found = False
                for bomb in render_state.bombs:
                    if bomb.bomb_type == BombType.NUKE:
                        nuke_found = True
                        break
                if nuke_found:
                    if not self.nuke_warning:
                        self.lighting_fx.nuke_warning()
                        self.nuke_warning = True
                else:
                    if self.nuke_warning:
                        self.lighting_fx.game()
                        self.nuke_warning = False

            Clock.sleep(1)

        self.engine.stop()

        self._at_round_end()

    def _at_round_start(self) -> None:
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
                self._countdown = count
                self.server.broadcast(Countdown(count=count))
                if self.use_lights:
                    self.lighting_fx.countdown()

            # Broadcast render state every tick so inventory selections
            # made via on_select during the countdown become visible to
            # all clients in real time (the engine isn't running yet, so
            # nothing else triggers state broadcasts here).
            self.render_callback(self.engine.get_render_state())

            Clock.sleep(0.1)

        self.engine.start()
        self._countdown = None
        self.game_on_countdown = False

    def _at_round_end(self) -> None:
        with self._admission_lock:
            assert self.engine is not None
            quit_session = self.session.session_complete()

            for player in self.players:
                player.created = False

                gp = self.engine.get_player_by_name(player.name)
                if gp is not None:
                    player.inventory = gp.inventory
                    player.money = gp.money
                    player.tools = {}
                    player.dig_power = BASE_DIGGING_POWER
                    player.max_health = 100

            points_by_name = self.score_players()
            for player in self.players:
                if not quit_session:
                    player.money += self.session.money_inject
                player.score += points_by_name[player.name]

            self.engine = None
            self._latest_game_state = None
            self._countdown = None

            self.state_machine.update(quit=quit_session)
        self.ui_show_scores()
        if self.use_lights:
            self.lighting_fx.stop_fx()

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
        match self.session.scoring_type:
            case ScoringType.SURVIVAL:
                return self._score_survival()
            case ScoringType.DEATHMATCH:
                return self._score_deathmatch()
            case ScoringType.TREASURE_HUNT:
                return self._score_treasure_hunt()
            case ScoringType.COMBO:
                return self._score_combo()
        raise ValueError(f"Unsupported scoring type: {self.session.scoring_type}")

    def _score_survival(self) -> Dict[str, int]:
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

    def _score_deathmatch(self) -> Dict[str, int]:
        assert self.engine is not None
        points_by_name: Dict[str, int] = {}

        for player in self.players:
            kills = self.engine.player_kills.get(player.id, 0)
            if self.session.count_monster_kills:
                kills += self.engine.monster_kills.get(player.id, 0)
            points_by_name[player.name] = kills

        return points_by_name

    def _score_treasure_hunt(self) -> Dict[str, int]:
        points_by_name: Dict[str, int] = {}

        for player in self.players:
            points_by_name[player.name] = player.money // 100

        return points_by_name

    def _score_combo(self) -> Dict[str, int]:
        survivor_points = self._score_survival()
        kill_points = self._score_deathmatch()
        money_points = self._score_treasure_hunt()

        points_by_name: Dict[str, int] = {}

        for player in self.players:
            survive = survivor_points[player.name]
            kills = kill_points[player.name]
            money = money_points[player.name]
            points_by_name[player.name] = int(
                self.session.weight_survival * survive
                + self.session.weight_kill * kills
                + self.session.weight_money * money
            )

        return points_by_name

    def get_scoreboard_rows(self) -> List[tuple[str, int]]:
        rows = [(p.name, int(p.score)) for p in self.players]
        rows.sort(key=lambda row: row[1], reverse=True)
        return rows

    def kick_player(self, player: SessionPlayer) -> bool:
        with self._admission_lock:
            connected = (
                player in self.players
                or self.pending_players.get(player.name) is player
            )
            return connected and self.server.disconnect_player(player.name)

    def end_game(self) -> None:
        self.ui_show_end_message()

        start = Clock.now()
        dt = Clock.now() - start

        if self.use_lights:
            max_points = -1
            winner = None
            for p in self.players:
                if p.score > max_points:
                    max_points = p.score
                    winner = p

            self.lighting_fx.stop_fx()
            if winner is not None:
                self.lighting_fx.win(winner.color[0], winner.color[1], winner.color[2])

        while dt < self.end_screen_wait_time and not self.ui_should_quit():
            self.ui_tick()

            if self._handle_stop_server_request():
                return

            self.server.broadcast(Scoreboard(players=self.players), None)

            Clock.sleep(1)
            dt = Clock.now() - start

        self.server.disconnect_all()
        self._stop_networking()
        with self._admission_lock:
            self.pending_players.clear()
            self._disconnected_players.clear()
            self.session.reset()
            self.rounds_left = self.session.rounds_left()
            self.state_machine.update()
        if self.use_lights:
            self.lighting_fx.stop_fx()

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
        with self._admission_lock:
            if ctx.name is None or ctx.name in self.pending_players:
                return

            if self.state == ServerState.SHOP:
                if self._shop_info is not None and not self.shop_complete:
                    self._on_control_shop(msg, ctx)
                return

            if self.state != ServerState.GAME or self.game_on_countdown:
                return

        self._on_control_game(msg, ctx)

    def _on_control_shop(self, msg: ClientControl, ctx: ClientContext) -> None:
        if self.shop is None or ctx.name is None:
            return

        cmd: Action = msg.command  # type: ignore
        assert isinstance(cmd, Action)

        player = self.shop.get_player(ctx.name)
        if player is None:
            return

        if cmd in (Action.RIGHT, Action.LEFT, Action.UP, Action.DOWN):
            self.shop.move_player(player.id, cmd)

        if cmd == Action.FIRE:
            self.shop.purchase_current(player.id)

        if cmd == Action.STOP:
            self.shop.sell_current(player.id)

        self.shop_complete = self.shop.all_done
        self._send_shop()

    def _on_control_game(self, msg: ClientControl, ctx: ClientContext) -> None:
        engine = self.engine
        if self.state != ServerState.GAME or ctx.name is None or engine is None:
            return

        player = engine.get_player_by_name(ctx.name)

        if player is None:
            return

        if player.state == EntityState.DEAD:
            return

        cmd: Action = msg.command  # type: ignore
        assert isinstance(cmd, Action)
        now = Clock.now()

        if cmd.is_move():
            # Best-effort dedup of no-op repeats. Reading entity.direction /
            # state here is a benign cross-thread read — worst case is a
            # spurious command that the engine processes idempotently.
            # Direction / state mutations now happen exclusively on the
            # engine thread via change_entity_direction.
            intended_direction = _ACTION_TO_DIRECTION.get(cmd)
            if cmd == Action.STOP:
                if player.state == EntityState.IDLE:
                    return
            elif (
                intended_direction is not None
                and player.direction == intended_direction
                and player.state == EntityState.WALK
            ):
                return

            engine.input_queue.submit(
                InputCommand(
                    entity=player,
                    action=cmd,
                    timestamp=now,
                    direction=intended_direction,
                )
            )

        else:
            if cmd == Action.FIRE:
                bomb = player.plant_bomb()
                if bomb is not None:
                    engine.input_queue.submit(
                        InputCommand(
                            entity=player,
                            action=cmd,
                            timestamp=now,
                            bomb=bomb,
                        )
                    )

            elif cmd == Action.REMOTE:
                engine.input_queue.submit(
                    InputCommand(entity=player, action=cmd, timestamp=now)
                )

    def on_select(self, msg: ClientSelect, ctx: ClientContext) -> None:
        engine = self.engine
        if self.state != ServerState.GAME or ctx.name is None or engine is None:
            return

        player = engine.get_player_by_name(ctx.name)
        if player is None:
            return

        try:
            target_type = BombType(msg.bomb_type)
        except ValueError:
            return

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

    def _join_starting_values(self) -> tuple[int, int]:
        if not self.players or self.rounds_left == len(self.session.maps):
            return self.session.starting_money, 0
        money = sum(player.money for player in self.players) // len(self.players)
        score = min(player.score for player in self.players) - 1
        return money, score

    def _take_pending_players(self) -> list[SessionPlayer]:
        players = list(self.pending_players.values())
        if players:
            money, score = self._join_starting_values()
            for player in players:
                if self._disconnected_players.pop(player.name, None) is not None:
                    self.server.log.info(
                        "Restored %s in the shop (score=%d, money=%d, inventory=%s)",
                        player.name, player.score, player.money, player.inventory,
                    )
                else:
                    player.money = money
                    player.score = score
        self.pending_players.clear()
        return players

    def on_name(self, msg: Name, ctx: ClientContext) -> None:
        with self._admission_lock:
            if ctx.name is not None:
                return

            name = msg.name
            if not self.state.running():
                rejection = "Session is unavailable"
            elif name in self.pending_players or any(
                player.name == name for player in self.players
            ):
                rejection = "name taken"
            else:
                rejection = None

            if rejection is not None:
                ctx.send(
                    ClientConnectionStateMessage(
                        ClientConnectionState.DISCONNECTED, msg=rejection
                    )
                )
                return

            player = self._disconnected_players.get(name)
            returning = player is not None
            if player is None:
                player = SessionPlayer(
                    name=name,
                    color=msg.color,
                    appearance=msg.appearance_id,
                    money=self.session.starting_money,
                    base_dig_power=self.session.base_dig_power,
                )
            else:
                player.color = msg.color
                player.appearance = msg.appearance_id
            ctx.name = name
            if self.state == ServerState.GAME or (
                self.state == ServerState.SHOP
                and self._shop_info is not None
                and self.shop_complete
            ):
                mode = JoinMode.SPECTATE
                self.pending_players[name] = player
            elif self.state == ServerState.SHOP:
                mode = JoinMode.SHOP
                if self._shop_info is not None and self.shop is not None:
                    if returning:
                        self._disconnected_players.pop(name)
                    else:
                        player.money, player.score = self._join_starting_values()
                    self.shop.add_player(player)
                else:
                    self.pending_players[name] = player
            else:
                mode = JoinMode.LOBBY
                self._disconnected_players.pop(name, None)
                self.players.append(player)

            ctx.send(ClientConnectionStateMessage(ClientConnectionState.CONNECTED))
            ctx.send(JoinReply(mode))
            if returning:
                self.server.log.info(
                    "Recognized reconnect for %s (mode=%s, score=%d, money=%d, inventory=%s)",
                    name, mode.name, player.score, player.money, player.inventory,
                )
            if mode == JoinMode.SHOP and self._shop_info is not None:
                ctx.send(self._shop_info)
                self._send_shop()
            elif mode == JoinMode.SPECTATE and self._latest_game_state is not None:
                if self._countdown is not None:
                    ctx.send(Countdown(count=self._countdown))
                ctx.send(replace(self._latest_game_state, sounds=()))

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
        with self._admission_lock:
            name = ctx.name
            if name is None or self.pending_players.pop(name, None) is not None:
                return

            player = next((player for player in self.players if player.name == name), None)
            if player is None:
                return

            if self.state == ServerState.GAME and self.engine is not None:
                game_player = self.engine.get_player_by_name(name)
                if game_player is not None:
                    player.money = game_player.money
                    player.inventory = list(game_player.inventory)
                    player.tools = {}
                    player.dig_power = BASE_DIGGING_POWER
                    player.max_health = 100
                self.engine.remove_player(name)

            player.created = False
            if self.state.running():
                self._disconnected_players[name] = player
                self.server.log.info(
                    "Saved state for %s (score=%d, money=%d, inventory=%s)",
                    name, player.score, player.money, player.inventory,
                )

            if (
                self.state == ServerState.SHOP
                and self._shop_info is not None
                and self.shop is not None
            ):
                self.shop.remove_player(name)
                if not self.players and self.pending_players:
                    for pending_player in self._take_pending_players():
                        self.shop.add_player(pending_player)
                    self.server.broadcast(self._shop_info)
                self.shop_complete = bool(self.players) and self.shop.all_done
                self._send_shop()
            else:
                self.players.remove(player)


def ping_thread(server: BomberServerBase) -> None:
    last_ping = Clock.now()
    tick = 0.1

    while True:
        if Clock.now() - last_ping > tick:
            server.ping()
            last_ping = Clock.now()

        Clock.sleep(tick / 2)
