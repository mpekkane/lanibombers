from abc import ABC
from typing import Optional
from twisted.protocols.basic import Int32StringReceiver
from twisted.python.failure import Failure
from twisted.internet import error
from network_stack.shared.alias import OnMessage, OnConnect, OnDisconnect
from network_stack.messages.messages import Message


class TransportClientProtocol(Int32StringReceiver):
    def __init__(
        self,
        on_message: OnMessage,
        on_connect: Optional[OnConnect],
        on_disconnect: Optional[OnDisconnect],
    ):
        pass

    def connectionMade(self) -> None:
        pass

    def connectionLost(self, reason: Failure = Failure(error.ConnectionDone())) -> None:
        pass

    def stringReceived(self, string: bytes) -> None:
        pass


class TransportClient(ABC):
    """
    Library-style client:
      - start() spins reactor in a background thread
      - send(msg) is safe to call from any thread
      - callbacks deliver received Message objects
    """

    def __init__(
        self,
        ip: str,
        port: int,
        *,
        on_message: OnMessage,
        on_connect: Optional[OnConnect] = None,
        on_disconnect: Optional[OnDisconnect] = None,
    ):
        pass

    def start(self) -> None:
        pass

    def send(self, msg: Message) -> None:
        pass
