"""
Test code for client-side
"""

from typing import Dict, List, Optional, Union
from argparse import ArgumentParser
from network_stack.messages.messages import (
    ChatText,
    Ping,
    Pong,
    ClientControl,
    ClientSelect,
    GameState,
)
from game_engine.clock import Clock
from game_engine.agent_state import Action
from network_stack.bomber_network_client import BomberNetworkClient
from pynput import keyboard
from common.config_reader import ConfigReader
from common.keymapper import map_keys, parse_arcade_key, pynput_to_arcade_key
from renderer.game_renderer import GameRenderer
from game_engine.render_state import RenderState
from game_engine.client_simulation import ClientSimulation
from cfg.bomb_dictionary import BombType, BOMB_NAME_TO_TYPE


class BomberClient:
    def __init__(self, cfg_path: str, key_path: str, headless: bool) -> None:
        # TODO: how to map
        config = ConfigReader(key_path)
        (
            self.up,
            self.down,
            self.left,
            self.right,
            self.fire,
            self.stop,
            self.choose,
            self.remote,
        ) = map_keys(config)
        self.headless = headless
        self.client = BomberNetworkClient(cfg_path)
        self.listener: Optional[keyboard.Listener] = None
        self.name = config.get_config("player_name")
        self.color = self._parse_color(config.get_config("color"))
        self.appearance_id = int(config.get_config("appearance_id") or 1)

        # Load item ordering and hotkeys from config
        self.weapon_order: List[BombType] = []
        self.item_hotkeys: Dict[BombType, str] = {}
        self.hotkey_keys: Dict[int, BombType] = {}  # arcade key code -> BombType
        items_cfg = config.get_config_untyped("items")
        if items_cfg:
            sorted_items = sorted(items_cfg, key=lambda item: item.get("menu_order", 999))
            for item in sorted_items:
                name = item.get("name", "")
                bomb_type = BOMB_NAME_TO_TYPE.get(name)
                if bomb_type is None:
                    continue
                self.weapon_order.append(bomb_type)
                hotkey = str(item.get("hotkey", ""))
                if hotkey:
                    self.item_hotkeys[bomb_type] = hotkey
                    try:
                        key_code = parse_arcade_key(hotkey)
                        self.hotkey_keys[key_code] = bomb_type
                    except ValueError:
                        pass

        server_found = self.client.find_host()
        if not server_found:
            print("No server found")
            return

        self.client.set_callback(ChatText, self.on_chattxt)
        self.client.set_callback(Ping, self.on_ping)
        self.client.set_callback(GameState, self.on_game_state)
        self.client.set_on_disconnect(self.on_disconnect)
        self.simulation = ClientSimulation()
        self.renderer = None
        self.running = False

    @staticmethod
    def _parse_color(color_str) -> tuple:
        """Convert hex color string '#FF0091' to RGB tuple (255, 0, 145)."""
        if not color_str or not isinstance(color_str, str):
            return (255, 255, 255)
        color_str = color_str.lstrip("#")
        if len(color_str) != 6:
            return (255, 255, 255)
        return (int(color_str[0:2], 16), int(color_str[2:4], 16), int(color_str[4:6], 16))

    def start(self) -> None:
        self.client.start()

        if not self.name:
            name = input("Name: ")
        else:
            name = self.name
            print(f"Connecting with {name}")
            Clock.sleep(1)

        self.client.set_name(name, self.color, self.appearance_id)

        if not self.headless:
            renderer = GameRenderer(
                self.get_render_state_unsafe,
                client_player_name=name,
                window_name="lanibombers client",
                item_hotkeys=self.item_hotkeys,
            )
            renderer.bind_input_callback(self.on_press)

            while not self.has_state():
                Clock.sleep(1)

            renderer.initialize()
            renderer.run()
        else:
            # Create and start the listener
            with keyboard.Listener(on_press=self.on_press_local) as listener:
                self.listener = listener
                listener.join()

    def on_disconnect(self, reason: str) -> None:
        print(f"Disconnected from server: {reason}")
        if self.listener:
            self.listener.stop()
        # sys.exit(0)

    def on_chattxt(self, msg: ChatText) -> None:
        print(f"{msg.timestamp}: {msg.text}")

    def render(self) -> None:
        while True:
            if self.renderer and not self.running:
                self.renderer.run()
            else:
                Clock.sleep(1)

    def on_game_state(self, msg: GameState):
        self.simulation.receive_state(msg.to_render())

    def get_render_state_unsafe(self) -> RenderState:
        """Returns extrapolated RenderState with client-side inventory reordering."""
        state = self.simulation.get_render_state_unsafe()
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
        # Remember the currently selected BombType
        selected_type = player.inventory[player.selected][0]
        # Build reordered list: items in weapon_order first, rest appended
        inv_dict = {bt: count for bt, count in player.inventory}
        reordered = []
        for bt in self.weapon_order:
            if bt in inv_dict:
                reordered.append((bt, inv_dict.pop(bt)))
        # Append any remaining items not in weapon_order
        for bt, count in player.inventory:
            if bt in inv_dict:
                reordered.append((bt, count))
                del inv_dict[bt]
        player.inventory = reordered
        # Adjust selected index to point to the same BombType
        for i, (bt, _c) in enumerate(player.inventory):
            if bt == selected_type:
                player.selected = i
                break

    def has_state(self) -> bool:
        return self.simulation.has_state()

    def on_ping(self, msg: Ping):
        received = Clock.now_ns()
        pong = Pong(ping_UUID=msg.UUID, received=received)
        self.client.send(pong)

    def _send_select(self, bomb_type: BombType) -> None:
        """Send a ClientSelect message for the given BombType."""
        all_types = list(BombType)
        idx = all_types.index(bomb_type)
        self.client.send(ClientSelect(bomb_type=idx))

    def on_press(self, symbol: int, modifiers: int) -> None:
        # Check weapon hotkeys first
        if symbol in self.hotkey_keys:
            self._send_select(self.hotkey_keys[symbol])
            return

        if symbol == self.fire:
            action = Action.FIRE
        elif symbol == self.stop:
            action = Action.STOP
        elif symbol == self.up:
            action = Action.UP
        elif symbol == self.down:
            action = Action.DOWN
        elif symbol == self.left:
            action = Action.LEFT
        elif symbol == self.right:
            action = Action.RIGHT
        elif symbol == self.choose:
            # Cycle to next weapon in weapon_order that exists in inventory
            if self.weapon_order and self.simulation.has_state():
                state = self.simulation.get_render_state_unsafe()
                player = None
                for p in state.players:
                    if p.name == self.name:
                        player = p
                        break
                if player and player.inventory:
                    # Get current selected BombType
                    current_type = player.inventory[player.selected][0]
                    # Find types present in inventory
                    inv_types = [bt for bt, _c in player.inventory]
                    # Find next in weapon_order that's in inventory
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
        elif symbol == self.remote:
            action = Action.REMOTE
        else:
            action = None
        if action is not None:
            self.client.send(ClientControl(int(action)))

    def on_press_local(self, key: Union[keyboard.Key, keyboard.KeyCode, None]) -> None:
        if key is None:
            return
        symbol = pynput_to_arcade_key(key)
        if symbol is not None:
            self.on_press(symbol, 0)


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--cfg", "-c", type=str, default="cfg/client_config.yaml")
    parser.add_argument("--key_cfg", "-k", type=str, default="cfg/player.yaml")
    parser.add_argument("--headless", "-hl", action="store_true", default=False)
    args = parser.parse_args()
    cfg_path = args.cfg
    key_path = args.key_cfg
    headless = args.headless

    client = BomberClient(cfg_path, key_path, headless)
    client.start()


if __name__ == "__main__":
    main()
