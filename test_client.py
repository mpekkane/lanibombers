"""
Test code for client-side
"""

import sys
import arcade
from typing import Union, Optional
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
from common.keymapper import map_keys
from renderer.game_renderer import GameRenderer
from game_engine.render_state import RenderState


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

        self.client = BomberNetworkClient(cfg_path)
        self.listener: Optional[keyboard.Listener] = None

        server_found = self.client.find_host()
        if not server_found:
            print("No server found")
            return

        self.client.set_callback(ChatText, self.on_chattxt)
        self.client.set_callback(Ping, self.on_ping)
        self.client.set_callback(GameState, self.on_game_state)
        self.client.set_on_disconnect(self.on_disconnect)
        self.state: Optional[RenderState] = None
        self.renderer = None
        self.running = False

    def start(self) -> None:
        self.client.start()
        name = input("Name: ")
        self.client.set_name(name)

        renderer = GameRenderer(
            self.get_render_state_unsafe, window_name="lanibombers client"
        )
        renderer.bind_input_callback(self.on_press)

        while not self.has_state():
            Clock.sleep(1)

        renderer.initialize()
        renderer.run()

        # renderer_th = threading.Thread(target=self.render)
        # renderer_th.start()

        # Create and start the listener
        # with keyboard.Listener(on_press=self.on_press) as listener:
        #     self.listener = listener
        #     listener.join()

    def on_disconnect(self, reason: str) -> None:
        print(f"Disconnected from server: {reason}")
        if self.listener:
            self.listener.stop()
        # sys.exit(0)

    def on_chattxt(self, msg: ChatText):
        print(f"{msg.timestamp}: {msg.text}")

    def render(self) -> None:
        while True:
            if self.renderer and not self.running:
                self.renderer.run()
            else:
                Clock.sleep(1)

    def on_game_state(self, msg: GameState):
        self.state = msg.to_render()
        # if self.renderer is None:
        #     self.renderer = GameRenderer(self)

    def get_render_state(self) -> Optional[RenderState]:
        """Returns RenderState with dimensions and sprite indices"""
        if self.state is not None:
            return self.state
        return None

    def get_render_state_unsafe(self) -> RenderState:
        """Returns RenderState with dimensions and sprite indices"""
        assert self.state is not None
        return self.state

    def has_state(self) -> bool:
        return self.state is not None

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


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--cfg", "-c", type=str, default="cfg/client_config.yaml")
    parser.add_argument("--key_cfg", "-k", type=str, default="cfg/key_map.yaml")
    parser.add_argument("--headless", "-hl", action="store_true", default=False)
    args = parser.parse_args()
    cfg_path = args.cfg
    key_path = args.key_cfg
    headless = args.headless

    client = BomberClient(cfg_path, key_path, headless)
    client.start()


if __name__ == "__main__":
    main()
