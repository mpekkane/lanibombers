import yaml
from typing import Dict, Type, Callable, TypeVar, cast, Tuple, List
from network_stack.clients.transport_client import TransportClient
from network_stack.shared.factory import get_client
# FIXME: factory
from network_stack.clients.tcp_scanner import TCPScanner
from network_stack.clients.udp_scanner import UDPScanner
from network_stack.messages.messages import Message, Name

MsgType = TypeVar("MsgType", bound=Message)
ClientHandler = Callable[[Message], None]


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

        self.protocol = config.get("protocol")
        self.server_ip = ""
        self.server_port = -1
        self.acquired_server = False
        self.client: TransportClient
        self.connected = False
        self.callbacks: Dict[Type[Message], Callable[[Message], None]] = {}

    def find_host(self) -> bool:
        if self.protocol == "tcp":
            servers = self.find_tcp_host()
        else:
            servers = self.find_udp_host()

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

    def find_udp_host(self) -> List[Tuple[str, int]]:
        #FIXME
        scanner = UDPScanner(self.subnet, self.port, 5)
        return scanner.scan()

    def find_tcp_host(self) -> List[Tuple[str, int]]:
        "Finds servers in the subnet"
        scanner = TCPScanner(self.subnet, self.port, self.host)
        return scanner.scan()

    def start(self) -> bool:
        "Starts the client"
        def _on_connect():
            self.connected = True
        client = get_client(
            protocol=self.protocol,
            ip=self.server_ip,
            port=self.server_port,
            on_message=self.on_msg,
            on_connect=_on_connect,
        )
        client.start()
        self.client = client
        # FIXME: error checking
        return True

    def set_callback(
        self, msg_type: Type[MsgType], callback: Callable[[MsgType], None]
    ) -> bool:
        if msg_type in self.callbacks:
            return False
        self.callbacks[msg_type] = cast(ClientHandler, callback)
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
        callback = self.callbacks.get(type(msg))
        if callback is None:
            return
        callback(msg)
