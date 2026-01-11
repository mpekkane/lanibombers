from __future__ import annotations
from dataclasses import dataclass
import yaml
from typing import Optional, Callable, Dict, Type, TypeVar, cast
from network_stack.messages.messages import Message
from network_stack.shared.factory import get_server
from network_stack.servers.transport_server import (
    TransportServer,
    TransportServerProtocol,
)
from network_stack.shared.types import PeerState


@dataclass
class ClientContext:
    """
    What handlers get: game-level view of the client.
    No Twisted imports needed in user code if you keep this in bomber_server.py.
    """

    server: BomberServer
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


class BomberServer:
    def __init__(self, cfg_path: str) -> None:
        with open(cfg_path, "r") as f:
            cfg = yaml.safe_load(f)
        self.port = cfg.get("port")
        self.protocol = cfg.get("protocol")
        self._running = False
        self._server: TransportServer = get_server(
            self.protocol, self.port, self._on_receive
        )  # private
        self._handlers: Dict[Type[Message], Handler] = {}

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

    def _send_to_proto(self, proto: TransportServerProtocol, msg: Message) -> None:
        self._server.send_to(proto, msg)

    def disconnect(self, proto: TransportServerProtocol) -> None:
        self._server.disconnect(proto)

    def _on_receive(
        self, msg: Message, state: PeerState, proto: TransportServerProtocol
    ) -> None:
        if not self._running:
            return

        ctx = ClientContext(server=self, state=state, _proto=proto)
        handler = self._handlers.get(type(msg))
        if handler is None:
            # unknown message type: ignore or log
            return
        handler(msg, ctx)
