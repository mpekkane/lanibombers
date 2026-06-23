# renderer/lanibombers_window.py
from typing import List, Dict, Optional
import threading
import time

import arcade

from game_engine.agent_state import Action
from game_engine.client_simulation import ClientSimulation
from game_engine.render_state import RenderState
from game_engine.sound_engine import SoundEngine
from network_stack.bomber_network_client import BomberNetworkClient
from network_stack.messages.messages import (
    GameState,
    ClientControl,
    ClientSelect,
    ShopState,
    Scoreboard,
    SessionInfo,
    Countdown,
    ClientConnectionStateMessage,
    ClientConnectionState,
    ChatText,
)
from common.bomb_dictionary import BombType, BOMB_NAME_TO_TYPE
from common.keymapper import map_keys, parse_arcade_key
from common.config_reader import ConfigReader
from game_engine.state_machine import ClientStateMachine, ClientState, ClientStateAction
from renderer.views.title_view import TitleView
from renderer.views.main_menu_view import MainMenuView
from renderer.views.info_view import InfoView
from renderer.views.player_setup_view import PlayerSetupView
from renderer.views.scoreboard_view import ScoreboardView, PlayerResult
from renderer.views.server_finder_view import ServerFinderView
from renderer.game_renderer import GameView
from renderer.shop_renderer import ShopView
from game_engine.shop import Shop
from game_engine.clock import Clock
from renderer.player_colorizer import PLAYER_COLORS
import random
from game_engine.auto_client import ShopAI
from common.logger import get_logger

WINDOW_WIDTH = 1708
WINDOW_HEIGHT = 960
WINDOW_TITLE = "lanibombers"

_CLIENT_CFG_PATH = "cfg/client_config.yaml"


def _parse_color(color_str) -> tuple:
    """Convert hex color string '#FF0091' to RGB tuple (255, 0, 145)."""
    if not color_str or not isinstance(color_str, str):
        return (255, 255, 255)
    color_str = color_str.lstrip("#")
    if len(color_str) != 6:
        return (255, 255, 255)
    return (int(color_str[0:2], 16), int(color_str[2:4], 16), int(color_str[4:6], 16))


class LanibombersWindow(arcade.Window):
    """Single window for the entire client. Views handle all screens."""

    def __init__(
        self,
        local_ip: Optional[str] = None,
        player_config_path: Optional[str] = None,
        auto: bool = False,
        show_stats: bool = False
    ):
        super().__init__(WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_TITLE, vsync=True)
        # FIXME: for debugging multiple processes as once
        self.atlas = arcade.DefaultTextureAtlas(
            size=(4096, 4096),
            ctx=self.ctx,
        )
        self.show_stats = show_stats
        # this is the default behavior
        # self.atlas = self.ctx.default_atlas

        self.sound_engine: SoundEngine = SoundEngine(music_volume=0.5, fx_volume=1.0)
        self.player_config: dict | None = None
        self.client_config: dict | None = None
        self.network_client: BomberNetworkClient | None = None
        self.client_simulation: ClientSimulation | None = None
        self.name: str = ""
        self.color: tuple = (255, 255, 255)
        self.appearance_id: int = 1
        self._up = self._down = self._left = self._right = -1
        self._fire = self._stop = self._choose = self._remote = -1
        self._hotkey_keys: Dict[int, BombType] = {}
        self.weapon_order: List[BombType] = []
        self.item_hotkeys: Dict[BombType, str] = {}
        # This is the main state machine that handles the program control flow
        self.state_machine = ClientStateMachine()
        self.shop: Optional[Shop] = None
        self.got_shop = False
        self.session_end = False
        self.standings: Optional[List[PlayerResult]] = None
        self.got_session = False
        self.countdown = None
        # perf_counter() time at which `self.countdown` last changed value.
        # Used by the renderer to interpolate within the final second for the
        # radial map-reveal animation.
        self.countdown_value_started_at: Optional[float] = None
        self.local_ip = local_ip
        self.player_config_path = player_config_path
        self.next_rounds_left: Optional[int] = None
        self.auto = auto
        self.log = get_logger()
        self.connection_state = ClientConnectionState.NONE
        self.chat_log = []

        if self.auto:
            self._auto_running = True
            self.autothread = threading.Thread(target=self._run_auto)
            self.autothread.start()

    def render_view(self) -> None:
        """Render the next view on screen"""
        view = self.get_view_for_state()
        if view is not None:
            self.show_view(view)
        else:
            self.close()

    def view_complete(self, action: ClientStateAction = ClientStateAction.NONE) -> None:
        """
        This is the main callback all views should call when their internal logic
        is finished. Then, the window's state machine will deal with setting up the next
        view.

        Args:
            action (ClientStateAction, optional): In some states there are choices into
            which state we will go to. This variable tells that choice.
            Defaults to ClientStateAction.NONE.
        """
        self.clean_view()
        if action == ClientStateAction.QUIT:
            self.close()
        else:
            self.state_machine.update(action, self.next_rounds_left)
            self.render_view()

    def get_view_for_state(self) -> Optional[arcade.View]:
        """This is the mapping from the state machine to the view

        Returns:
            arcade.View: Returns the view to be rendered
        """
        state = self.state_machine.get_state()
        self.sound_engine.stop_music()
        if state == ClientState.STARTING:
            return TitleView()
        elif state == ClientState.MENU:
            return MainMenuView()
        elif state == ClientState.INFO:
            return InfoView()
        elif state == ClientState.SETUP:
            return PlayerSetupView()
        elif state == ClientState.CONNECT:
            return ServerFinderView()
        # TODO: separate lobby view
        elif state == ClientState.LOBBY:
            return ServerFinderView()
        # TODO: shop view
        elif state == ClientState.SHOP:
            while not (self.got_shop and self.got_session):
                Clock.sleep(1)
                if self.session_end:
                    self.sound_engine.scoreboard()
                    assert self.standings is not None
                    return ScoreboardView(self.standings)
            assert self.shop is not None
            view = ShopView(
                self.shop.get_state,
                client_player_name=self.name,
                shop_items=self.shop.items,
                cursor_positions=self.shop.cursor_positions,
                next_map_tiles=self.next_tilemap,
                next_map_pickups=self.next_pickups,
                rounds_left=self.next_rounds_left,
            )  # FIXME: rounds left
            view.bind_input_callback(self.on_press)
            self.sound_engine.shop()
            return view
        elif state == ClientState.GAME:
            self.create_game_simulation()
            ok = False
            while not ok:
                ok = (
                    self.client_simulation is not None
                    and self.client_simulation.has_state()
                )
                Clock.sleep(0.1)
            view = GameView(
                self.get_render_state,
                client_player_name=self.name,
                item_hotkeys=self.item_hotkeys,
                show_stats=self.show_stats,
            )
            view.bind_input_callback(self.on_press)
            self.sound_engine.game()
            return view
        # TODO: ending view
        elif state == ClientState.ENDING:
            self.sound_engine.scoreboard()
            assert self.standings is not None
            return ScoreboardView(self.standings)
        elif state == ClientState.QUIT:
            return None

    def clean_view(self) -> None:
        """This performs needed cleanup after view is done"""
        state = self.state_machine.get_state()
        if state == ClientState.STARTING:
            return
        elif state == ClientState.MENU:
            return
        elif state == ClientState.INFO:
            return
        elif state == ClientState.SETUP:
            return
        elif state == ClientState.CONNECT:
            return
        elif state == ClientState.LOBBY:
            return
        elif state == ClientState.SHOP:
            self.shop = None
            self.got_shop = False
            self.got_session = False
        elif state == ClientState.GAME:
            self.client_simulation = None
            self.countdown = None
            self.countdown_value_started_at = None
        elif state == ClientState.ENDING:
            return
        elif state == ClientState.QUIT:
            return

    def _on_game_state(self, msg: GameState) -> None:
        if self.client_simulation is not None:
            self.client_simulation.receive_state(msg.to_render())

    def connect(self, host: str, port: int, player_config: dict) -> None:
        """Create and start a BomberNetworkClient for the given server."""
        client = BomberNetworkClient(_CLIENT_CFG_PATH, self.local_ip)
        client.server_ip = host
        client.server_port = port
        client.acquired_server = True

        self.sound_engine.stop_music()
        # self.sound_engine.game()

        # type: ignore[attr-defined]

        client.set_callback(GameState, self._on_game_state)
        client.set_callback(ShopState, self._on_shop_state)
        client.set_callback(Scoreboard, self._on_scoreboard)
        client.set_callback(SessionInfo, self._on_session_info)
        client.set_callback(Countdown, self._on_countdown)
        client.set_callback(ClientConnectionStateMessage, self._on_client_state)
        client.set_callback(ChatText, self._on_chat)
        client.set_on_disconnect(self._on_disconnect)
        client.start()

        self.network_client = client
        self.player_config = player_config
        if self.player_config_path is not None:
            self.setup_input(self.player_config_path)
        else:
            self.setup_input()

    def _on_client_state(self, msg: ClientConnectionStateMessage) -> None:
        self.connection_state = msg.state

    def _on_chat(self, msg: ChatText) -> None:
        self.chat_log.append(f"{msg.text}")

    def send_chat(self, msg: str) -> None:
        if self.network_client is not None:
            self.network_client.send(ChatText(text=msg))

    def create_game_simulation(self) -> None:
        self.client_simulation = ClientSimulation(sound_engine=self.sound_engine)

    def _on_disconnect(self, reason: str) -> None:
        self.log.info(f"Disconnected from server: {reason}")
        self.connection_state = ClientConnectionState.DISCONNECTED

    def _on_shop_state(self, msg: ShopState) -> None:
        shop = ShopState.to_shop(msg)
        if not self.got_shop:
            self.shop = shop
            self.got_shop = True
        else:
            self.shop.cursor_positions = shop.cursor_positions
            self.shop.state = shop.state
            self.shop.items = shop.items
            self.shop.players = shop.players

    def _on_session_info(self, msg: SessionInfo) -> None:
        self.next_rounds_left = msg.rounds_left
        self.next_width = msg.width
        self.next_height = msg.height
        self.next_tilemap = msg.tilemap
        self.next_pickups = msg.pickups
        self.got_session = True

    def _on_countdown(self, msg: Countdown) -> None:
        if msg.count != self.countdown:
            self.countdown_value_started_at = time.perf_counter()
        self.countdown = msg.count

    def _on_scoreboard(self, msg: Scoreboard) -> None:
        results = []

        for player in msg.players:
            color_idx = None
            for i, col in enumerate(PLAYER_COLORS):
                if col == player.color:
                    color_idx = i
            assert color_idx is not None
            result = PlayerResult(
                name=player.name,
                appearance=player.appearance,
                color=color_idx,
                score=player.score,
                money=player.money,
            )
            results.append(result)
        self.standings = results
        self.session_end = True

    def setup_input(self, key_cfg_path: str = "cfg/player.yaml") -> None:
        """Parse key bindings, weapon order, and hotkeys from player config."""
        config = ConfigReader(key_cfg_path)
        (
            self._up,
            self._down,
            self._left,
            self._right,
            self._fire,
            self._stop,
            self._choose,
            self._remote,
        ) = map_keys(config)
        self.name = config.get_config("player_name") or ""
        self.color = _parse_color(config.get_config("color"))
        self.appearance_id = int(config.get_config("appearance_id") or 1)
        self._hotkey_keys = {}
        self.weapon_order = []
        self.item_hotkeys = {}
        items_cfg = config.get_config_untyped("items")
        if items_cfg:
            sorted_items = sorted(
                items_cfg, key=lambda item: item.get("menu_order", 999)
            )
            for item in sorted_items:
                bomb_type = BOMB_NAME_TO_TYPE.get(item.get("name", ""))
                if bomb_type is None:
                    continue
                self.weapon_order.append(bomb_type)
                hotkey = str(item.get("hotkey", ""))
                if hotkey:
                    self.item_hotkeys[bomb_type] = hotkey
                    try:
                        self._hotkey_keys[parse_arcade_key(hotkey)] = bomb_type
                    except ValueError:
                        pass

    # ------------------------------------------------------------------
    # Render state
    # ------------------------------------------------------------------

    def get_render_state(self) -> Optional[RenderState]:
        """Returns extrapolated RenderState with client-side inventory reordering."""
        if self.client_simulation is None:
            return None
        state = self.client_simulation.get_render_state_unsafe()
        if self.weapon_order:
            for player in state.players:
                if player.name == self.name:
                    self._reorder_inventory(player)
                    break
        return state

    def _reorder_inventory(self, player) -> None:
        """Reorder player inventory to match weapon_order from config."""
        if not player.inventory:
            return
        selected_type = player.inventory[player.selected][0]
        inv_dict = {bt: count for bt, count in player.inventory}
        reordered = []
        for bt in self.weapon_order:
            if bt in inv_dict:
                reordered.append((bt, inv_dict.pop(bt)))
        for bt, count in player.inventory:
            if bt in inv_dict:
                reordered.append((bt, count))
                del inv_dict[bt]
        player.inventory = reordered
        for i, (bt, _c) in enumerate(player.inventory):
            if bt == selected_type:
                player.set_selected(i)
                break

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def _send_select(self, bomb_type: BombType) -> None:
        """Send a ClientSelect message for the given BombType."""
        assert self.network_client is not None
        idx = list(BombType).index(bomb_type)
        self.network_client.send(ClientSelect(bomb_type=idx))  # type: ignore[call-arg]

    def on_press(self, symbol: int, modifiers: int) -> None:
        """Translate arcade key press to a network message and send to server."""
        if self.network_client is None:
            return
        if symbol in self._hotkey_keys:
            self._send_select(self._hotkey_keys[symbol])
            return
        if symbol == self._fire:
            action = Action.FIRE
        elif symbol == self._stop:
            action = Action.STOP
        elif symbol == self._up:
            action = Action.UP
        elif symbol == self._down:
            action = Action.DOWN
        elif symbol == self._left:
            action = Action.LEFT
        elif symbol == self._right:
            action = Action.RIGHT
        elif symbol == self._choose:
            if (
                self.weapon_order
                and self.client_simulation is not None
                and self.client_simulation.has_state()
            ):
                state = self.client_simulation.get_render_state_unsafe()
                player = None
                for p in state.players:
                    if p.name == self.name:
                        player = p
                        break
                if player and player.inventory:
                    current_type = player.inventory[player.selected][0]
                    inv_types = [bt for bt, _c in player.inventory]
                    ordered_in_inv = [bt for bt in self.weapon_order if bt in inv_types]
                    if ordered_in_inv:
                        try:
                            cur_idx = ordered_in_inv.index(current_type)
                            next_idx = (cur_idx + 1) % len(ordered_in_inv)
                        except ValueError:
                            next_idx = 0
                        self._send_select(ordered_in_inv[next_idx])
                        return
            action = Action.CHOOSE
        elif symbol == self._remote:
            action = Action.REMOTE
        else:
            action = None
        if action is not None:
            self.network_client.send(ClientControl(command=action))  # type: ignore[call-arg]

    # ------------------------------------------------------------------
    # Disconnect
    # ------------------------------------------------------------------

    def disconnect(self) -> None:
        """Stop the network client and clear connection state."""
        if self.network_client is not None:
            client = self.network_client
            transport = getattr(client, "client", None)
            if transport is not None and hasattr(transport, "stop"):
                transport.stop()
            self.network_client = None
        self.client_simulation = None
        if self.auto:
            self._auto_running = False
            self.autothread.join()
        self.view_complete(ClientStateAction.RESTART)

    # ------------------------------------------------------------------
    # Debugging auto client (very stupid ai)
    # ------------------------------------------------------------------
    def _run_auto(self):
        shop_ai = None
        got_shop = False
        while self._auto_running:
            state = self.state_machine.get_state()
            if state == ClientState.STARTING:
                pass
            elif state == ClientState.MENU:
                pass
            elif state == ClientState.INFO:
                pass
            elif state == ClientState.SETUP:
                pass
            elif state == ClientState.CONNECT:
                pass
            elif state == ClientState.LOBBY:
                pass
            elif state == ClientState.SHOP:
                if not got_shop:
                    Clock.sleep(0.5)
                if self.shop is not None:
                    got_shop = True
                    player_obj = self.shop.get_player(self.name)
                    id, item = self.shop.get_player_cursor(player_obj.id)
                    if shop_ai is None:
                        shop_ai = ShopAI(
                            id=id,
                            name=self.name,
                            shop=self.shop,
                            cols=4,
                            callback=self.on_press,
                            left=self._left,
                            right=self._right,
                            up=self._up,
                            down=self._down,
                            fire=self._fire
                        )

                    if shop_ai is not None:
                        shop_ai.tick(item)
                Clock.sleep(0.1)
            elif state == ClientState.GAME:
                shop_ai = None
                got_shop = False
                actions = [
                    self._fire,
                    self._stop,
                    self._up,
                    self._down,
                    self._left,
                    self._right,
                    self._choose,
                ]
                action = random.choice(actions)
                self.on_press(action, 0)
                Clock.sleep(random.random())
            elif state == ClientState.ENDING:
                pass
            elif state == ClientState.QUIT:
                pass
