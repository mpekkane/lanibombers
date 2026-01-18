"""
LaniBombers network client.
This is the main client-side class that abstracts all of the networking stuff away.
The idea is that a instance of this class is created by the game client,
and this class handles all of the network communication.

The usage is:
1. Create instance, and pass the configuration file as parameter
2. Register the callbacks that are needed
3. Start client

After this, the responsibility of receiving and sending logic is to the owning class.
"""

from typing import Dict, Type, Callable, TypeVar, cast, Optional
from network_stack.clients.transport_client import TransportClient
from network_stack.shared.factory import get_client, get_scanner
from network_stack.messages.messages import Message, Name
from common.config_reader import ConfigReader

MsgType = TypeVar("MsgType", bound=Message)
ClientHandler = Callable[[Message], None]
DisconnectHandler = Callable[[str], None]


class BomberNetworkClient:
    def __init__(self, cfg_path: str) -> None:
        "Init class, read config from YAML"
        self.config = ConfigReader(cfg_path)
        self.base_addr = self.config.get_config_mandatory("base_addr", str)
        self.subnet = self.config.get_config("subnet", int)
        self.port = self.config.get_config("port", int)
        self.host = self.config.get_config("host", int)
        self.protocol = self.config.get_config_mandatory("protocol", str)
        self.timeout = self.config.get_config("timeout", float)
        self.server_ip = ""
        self.server_port = -1
        self.acquired_server = False
        self.client: TransportClient
        self.connected = False
        self.callbacks: Dict[Type[Message], Callable[[Message], None]] = {}
        self.on_disconnect_handler: Optional[DisconnectHandler] = None

    def find_host(self) -> bool:
        scanner = get_scanner(
            self.protocol, self.base_addr, self.subnet, self.port, self.host, self.timeout
        )
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

        def _on_connect():
            self.connected = True

        def _on_disconnect(reason: str):
            self.connected = False
            if self.on_disconnect_handler:
                self.on_disconnect_handler(reason)

        client = get_client(
            protocol=self.protocol,
            ip=self.server_ip,
            port=self.server_port,
            on_message=self.on_msg,
            on_connect=_on_connect,
            on_disconnect=_on_disconnect,
        )
        client.start()
        self.client = client
        # FIXME: error checking
        return True

    def set_on_disconnect(self, handler: DisconnectHandler) -> None:
        """Set callback for when connection is lost."""
        self.on_disconnect_handler = handler

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
