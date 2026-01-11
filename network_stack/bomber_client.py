import yaml
import time
from typing import Dict, Type, Callable
from network_stack.clients.tcp_client import TCPClient
from network_stack.clients.scan import Scanner
from network_stack.messages.messages import Message, Name


class BomberClient:
    def __init__(self, cfg_path: str) -> None:
        "Init class, read config from YAML"
        # read YAML
        with open(cfg_path, "r") as f:
            config = yaml.load(f, Loader=yaml.SafeLoader)
        try:
            self.subnet = config.get("subnet")
        except Exception:
            self.subnet = None
        try:
            self.port = config.get("port")
        except Exception:
            self.port = None

        try:
            self.host = config.get("host")
        except Exception:
            self.host = None

        self.server_ip = ""
        self.server_port = -1
        self.acquired_server = False
        self.client: TCPClient
        self.connected = False
        self.callbacks: Dict[Type[Message], Callable[[Message], None]] = {}

    def find_host(self) -> bool:
        "Finds servers in the subnet"
        scanner = Scanner(self.subnet, self.port, self.host)
        servers = scanner.scan()

        for i, s in enumerate(servers):
            print(f"{i}: {s}")

        selected = False
        while not selected:
            try:
                inp = input("Select server or q to quit: ")
                if inp == "q" or inp == "Q":
                    selected = True
                num = int(inp)
                self.server_ip, self.server_port = servers[num]
                selected = True
                self.acquired_server = True
            except Exception:
                pass

        return self.acquired_server

    def start(self) -> bool:
        "Starts the client"
        client = TCPClient(
            ip=self.server_ip,
            port=self.server_port,
            on_message=self.on_msg,
            on_connect=lambda: print("connected"),
        )
        client.start()
        time.sleep(1)
        self.client = client
        self.connected = True
        # FIXME: error checking
        return True

    def set_callback(
        self, type: Type[Message], callback: Callable[[Message], None]
    ) -> bool:
        if type in self.callbacks:
            return False

        self.callbacks[type] = callback
        return True

    # messaging
    def set_name(self, name: str) -> bool:
        if self.connected:
            self.client.send(Name(name=name))  # type: ignore
            return True
        else:
            return False

    def send(self, message: Message) -> bool:
        if self.connected:
            self.client.send(message)
            return True
        else:
            return False

    def on_msg(self, msg: Message) -> None:
        msg_type = type(msg)
        callback = self.callbacks[msg_type]
        callback(msg)
