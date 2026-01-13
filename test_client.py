"""
Test code for client-side
"""

import time
from argparse import ArgumentParser
from network_stack.messages.messages import ChatText, Ping, Pong
from network_stack.bomber_network_client import BomberNetworkClient


class BomberClient:
    def __init__(self, cfg_path: str) -> None:
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
        while True:
            msg = input(": ")
            self.client.send(ChatText(msg))
            time.sleep(0.1)

    def on_chattxt(self, msg: ChatText):
        print(f"{msg.timestamp}: {msg.text}")

    def on_ping(self, msg: Ping):
        received = time.time_ns()
        pong = Pong(ping_UUID=msg.UUID, received=received)
        self.client.send(pong)


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--cfg", "-c", type=str, default="cfg/client_config.yaml")
    args = parser.parse_args()
    cfg_path = args.cfg
    client = BomberClient(cfg_path)
    client.start()


if __name__ == "__main__":
    main()
