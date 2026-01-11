"""
Transport layer server abstraction interface.
Abstract base class for TCP/UDP servers.
"""

from __future__ import annotations
from typing import Protocol, Optional, Callable, runtime_checkable
from abc import ABC, abstractmethod

from network_stack.messages.messages import Message
from network_stack.shared.types import PeerState

OnReceive = Callable[[Message, PeerState, "TransportServerProtocol"], None]


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
