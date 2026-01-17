"""
Test code for client-side
"""

from typing import Union
from argparse import ArgumentParser
from network_stack.messages.messages import ChatText, Ping, Pong, ClientControl
from game_engine.clock import Clock
from game_engine.agent_state import Action
from network_stack.bomber_network_client import BomberNetworkClient
from pynput import keyboard
from common.config_reader import ConfigReader
from common.keymapper import check_input


class BomberClient:
    def __init__(self, cfg_path: str, key_path: str) -> None:
        # TODO: how to map
        config = ConfigReader(key_path)
        self.up = config.get_config_mandatory("up")
        self.down = config.get_config_mandatory("down")
        self.left = config.get_config_mandatory("left")
        self.right = config.get_config_mandatory("right")
        self.fire = config.get_config_mandatory("fire")
        self.stop = config.get_config_mandatory("stop")
        self.choose = config.get_config_mandatory("choose")
        self.remote = config.get_config_mandatory("remote")

        self.client = BomberNetworkClient(cfg_path)
        server_found = self.client.find_host()
        if not server_found:
            print("No server found")
            return

        self.client.set_callback(ChatText, self.on_chattxt)
        self.client.set_callback(Ping, self.on_ping)

    def start(self) -> None:
        self.client.start()
        name = input("Name: ")
        self.client.set_name(name)

        # Create and start the listener
        with keyboard.Listener(on_press=self.on_press) as listener:
            listener.join()

    def on_chattxt(self, msg: ChatText):
        print(f"{msg.timestamp}: {msg.text}")

    def on_ping(self, msg: Ping):
        received = Clock.now_ns()
        pong = Pong(ping_UUID=msg.UUID, received=received)
        self.client.send(pong)

    def on_press(self, key: Union[keyboard.Key, keyboard.KeyCode]):
        # FIXME: test with static keys, fix to key_config.yaml
        if check_input(key, self.fire):
            action = Action.FIRE
        elif check_input(key, self.stop):
            action = Action.STOP
        elif check_input(key, self.up):
            action = Action.UP
        elif check_input(key, self.down):
            action = Action.DOWN
        elif check_input(key, self.left):
            action = Action.LEFT
        elif check_input(key, self.right):
            action = Action.RIGHT
        elif check_input(key, self.choose):
            action = Action.CHOOSE
        elif check_input(key, self.remote):
            action = Action.REMOTE
        else:
            action = None
        if action:
            self.client.send(ClientControl(int(action)))


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--cfg", "-c", type=str, default="cfg/client_config.yaml")
    parser.add_argument("--key_cfg", "-k", type=str, default="cfg/key_map.yaml")
    args = parser.parse_args()
    cfg_path = args.cfg
    key_path = args.key_cfg

    client = BomberClient(cfg_path, key_path)
    client.start()


if __name__ == "__main__":
    main()
