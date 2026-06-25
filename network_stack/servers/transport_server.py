"""
Transport layer server abstraction interface.
Abstract base class for TCP/UDP servers.
"""

from __future__ import annotations
from typing import Protocol, Optional, Callable, runtime_checkable
from abc import ABC, abstractmethod

from network_stack.messages.messages import Message
from network_stack.shared.types import PeerState
from twisted.python.failure import Failure

OnReceive = Callable[[Message, PeerState, "TransportServerProtocol"], None]
OnDisconnect = Callable[[PeerState, "TransportServerProtocol", Failure], None]


class ServerAddressInUseError(Exception):
    """Raised when the server cannot bind its port because it is already in use.

    Typically means another instance is already serving on this port in the
    subnet, rather than a programming error.
    """

    def __init__(self, port: int) -> None:
        self.port = port
        super().__init__(
            f"Another server is already running in the subnet "
            f"(port {port} is already in use)."
        )

@runtime_checkable
class TransportServerProtocol(Protocol):
    def send_message(self, msg: Message) -> None: ...


class TransportServer(ABC):
    def __init__(self, port: int, on_receive: OnReceive) -> None:
        self.port = port
        self._on_receive = on_receive

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def broadcast(
        self, msg: Message, exclude: Optional[TransportServerProtocol] = None
    ) -> None: ...

    @abstractmethod
    def send_to(self, proto: TransportServerProtocol, msg: Message) -> None: ...

    @abstractmethod
    def disconnect(self, proto: TransportServerProtocol) -> None: ...
