from __future__ import annotations
from typing import Dict, Optional, Callable
from abc import ABC
from twisted.internet import error
from twisted.protocols.basic import Int32StringReceiver
from twisted.python.failure import Failure

from network_stack.messages.messages import Message
from network_stack.shared.types import PeerState


OnReceive = Callable[[Message, PeerState, "TransportServerProtocol"], None]


class TransportServerProtocol(ABC, Int32StringReceiver):
    def __init__(
        self, peers: Dict["TransportServerProtocol", PeerState], on_receive: OnReceive
    ) -> None:
        pass

    def connectionMade(self) -> None:
        pass

    def connectionLost(self, reason: Failure = Failure(error.ConnectionDone())) -> None:
        pass

    def stringReceived(self, string: bytes) -> None:
        pass

    def send_message(self, msg: Message) -> None:
        pass


class TransportServer(ABC):
    def __init__(self, port: int, on_receive: OnReceive) -> None:
        pass

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def broadcast(
        self, msg: Message, exclude: Optional[TransportServerProtocol] = None
    ) -> None:
        pass

    def send_to(self, proto: TransportServerProtocol, msg: Message) -> None:
        pass

    def disconnect(self, proto: TransportServerProtocol) -> None:
        pass
