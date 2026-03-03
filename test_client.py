"""
Test code for client-side
"""

from typing import Optional, Union
from argparse import ArgumentParser
from network_stack.messages.messages import (
    ChatText,
    Ping,
    Pong,
    ClientControl,
    GameState,
)
from game_engine.clock import Clock
from game_engine.agent_state import Action
from network_stack.bomber_network_client import BomberNetworkClient
from pynput import keyboard
from common.config_reader import ConfigReader
from common.keymapper import map_keys, pynput_to_arcade_key
from renderer.game_renderer import GameRenderer
from game_engine.render_state import RenderState
from game_engine.client_simulation import ClientSimulation


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
        """Returns extrapolated RenderState for smooth rendering."""
        return self.simulation.get_render_state_unsafe()

    def has_state(self) -> bool:
        return self.simulation.has_state()

    def on_ping(self, msg: Ping):
        received = Clock.now_ns()
        pong = Pong(ping_UUID=msg.UUID, received=received)
        self.client.send(pong)

    def on_press(self, symbol: int, modifiers: int) -> None:
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
