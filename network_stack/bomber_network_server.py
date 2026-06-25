"""
LaniBombers network server.
This is the main server-side class that abstracts all of the networking stuff away.
The idea is that a instance of this class is created by the game server,
and this class handles all of the network communication.

The usage is:
1. Create instance, and pass the configuration file as parameter
2. Register the callbacks that are needed
3. Start client

After this, the responsibility of receiving and sending logic is to the owning class.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Callable, Dict, Type, TypeVar, cast, List
from network_stack.messages.messages import Message
from network_stack.shared.factory import get_server
from network_stack.servers.transport_server import (
    TransportServer,
    TransportServerProtocol,
)
from network_stack.shared.types import PeerState
from common.config_reader import ConfigReader
from common.logger import get_logger


@dataclass
class ClientContext:
    """
    What handlers get: game-level view of the client.
    No Twisted imports needed in user code if you keep this in bomber_server.py.
    """

    server: BomberNetworkServer
    state: PeerState
    _proto: TransportServerProtocol

    @property
    def name(self) -> Optional[str]:
        return self.state.name

    @name.setter
    def name(self, value: str) -> None:
        self.state.name = value

    def send(self, msg: Message) -> None:
        self.server._send_to_proto(self._proto, msg)  # type: ignore

    def broadcast(self, msg: Message, *, exclude_self: bool = True) -> None:
        self.server.broadcast(msg, exclude=self._proto if exclude_self else None)

    def disconnect(self) -> None:
        self.server.disconnect(self._proto)


MsgType = TypeVar("MsgType", bound=Message)
Handler = Callable[[Message, ClientContext], None]


class BomberNetworkServer:

    def __init__(self, cfg_path: str) -> None:
        self.config = ConfigReader(cfg_path)
        self.port = self.config.get_config_mandatory("port", int)
        self.protocol = self.config.get_config_mandatory("protocol", str)
        self._running = False
        self._server: TransportServer = get_server(
            self.protocol, self.port, self._on_receive, self._on_disconnect
        )  # private
        self._handlers: Dict[Type[Message], Handler] = {}
        self._clients: List[ClientContext] = []
        self._diconnect_handler: Callable[[ClientContext], None]
        self.log = get_logger()

    def start(self) -> None:
        self._server.start()
        self._running = True

    def stop(self) -> None:
        self._running = False
        self._server.stop()

    def set_callback(
        self, msg_type: Type[MsgType], handler: Callable[[MsgType, ClientContext], None]
    ) -> bool:
        if msg_type in self._handlers:
            return False
        # erase type for storage; safe because dispatch uses msg_type key
        self._handlers[msg_type] = cast(Handler, handler)
        return True

    def set_disconnect_handler(self, handler: Callable[[ClientContext], None]) -> bool:
        self._diconnect_handler = handler
        return True

    # ---- game-level send APIs ----
    def broadcast(
        self, msg: Message, exclude: Optional[TransportServerProtocol] = None
    ) -> None:
        self._server.broadcast(msg, exclude=exclude)

    # Optional: you can expose a send-to-name API, etc.
    def broadcast_chat(
        self,
        text: str,
        sender: Optional[str] = None,
        exclude: Optional[TransportServerProtocol] = None,
    ) -> None:
        from network_stack.messages.messages import ChatText

        prefix = sender if sender else "?"
        self.broadcast(ChatText(text=f"<{prefix}> {text}"), exclude=exclude)

    def send_to_client(self, context: ClientContext, msg: Message) -> None:
        self._send_to_proto(context._proto, msg)

    def _send_to_proto(self, proto: TransportServerProtocol, msg: Message) -> None:
        self._server.send_to(proto, msg)

    def disconnect(self, proto: TransportServerProtocol) -> None:
        self._server.disconnect(proto)

    def disconnect_all(self) -> None:
        for client in self._clients:
            self.disconnect(client._proto)

    def _peer_ip(self, proto: TransportServerProtocol) -> str:
        """Best-effort remote IP from the transport (name isn't known yet)."""
        try:
            return proto.transport.getPeer().host  # type: ignore[attr-defined]
        except Exception:
            return "?"

    def _on_receive(
        self, msg: Message, state: PeerState, proto: TransportServerProtocol
    ) -> None:
        if not self._running:
            return

        ctx = ClientContext(server=self, state=state, _proto=proto)
        if ctx not in self._clients:
            self._clients.append(ctx)
            self.log.info(f"Client connected from {self._peer_ip(proto)}")
        handler = self._handlers.get(type(msg))
        if handler is None:
            # Unknown/unhandled type. Log only the type name: msg is remote input
            # and some messages (GameState, RawBytes) have huge reprs.
            self.log.warning(f"Unknown message type received: {type(msg).__name__}")
            return
        handler(msg, ctx)

    def _on_disconnect(
        self,
        state: PeerState,
        proto: TransportServerProtocol,
        reason: Failure,
    ) -> None:
        was_client = any(client._proto is proto for client in self._clients)

        self._clients = [
            client for client in self._clients if client._proto is not proto
        ]

        ctx = ClientContext(server=self, state=state, _proto=proto)
        self._diconnect_handler(ctx)

        if was_client:
            self.log.info(f"Client {state.name} disconnected: {reason.getErrorMessage()}")
        else:
            # Bare TCP connect with no handshake = LAN discovery scan probe.
            self.log.info("Server scan request received")
