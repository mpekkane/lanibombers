"""
Container for the game messaging.
This file contains all the network message definitions (subclasses of Message),
and handles registry of the message types, encoding and decoding.
"""

from __future__ import annotations
import struct
from dataclasses import dataclass
from game_engine.clock import Clock
from typing import ClassVar, Dict, Type, Iterable, List
from game_engine.agent_state import Action


class Message:
    """Abstract class for message objects"""

    def __init__(self) -> None:
        self.timestamp = Clock.now_ns()

    TYPE: ClassVar[int] = -1  # override
    timestamp: int

    def to_bytes(self) -> bytes: ...
    @classmethod
    def from_bytes(cls, payload: bytes) -> Message: ...


# This is intentionally global
_REGISTRY: Dict[int, Type[Message]] = {}


def get_registered_message_types() -> Iterable[type[Message]]:
    """This returns all the message types"""
    return _REGISTRY.values()


def register_message(cls: Type[Message]) -> Type[Message]:
    """This lists a new message type to the registry"""
    if cls.TYPE in _REGISTRY:
        raise ValueError(f"Duplicate message TYPE={cls.TYPE}")
    _REGISTRY[cls.TYPE] = cls
    return cls


def encode_message(msg: Message) -> bytes:
    """
    Wire format inside a single frame:
      1 byte: type id (0-255)
      N bytes: payload
    """
    t = msg.TYPE
    stamp = getattr(msg, "timestamp", None)
    if stamp is None:
        stamp = Clock.now_ns()
        object.__setattr__(msg, "timestamp", stamp)
    stamp = msg.timestamp.to_bytes(8, "big")  # 64 bits, 8 bytes
    if not (0 <= t <= 255):
        raise ValueError(f"TYPE must be 0..255, got {t}")
    return bytes([t]) + stamp + msg.to_bytes()


def decode_message(frame: bytes) -> Message:
    """Gets the message type and passes to the correct class to parse"""
    if len(frame) < 1:
        raise ValueError("Empty frame")
    t = frame[0]
    stamp = int.from_bytes(frame[1:9], "big")
    payload = frame[9:]
    cls = _REGISTRY.get(t)
    if cls is None:
        raise ValueError(f"Unknown message TYPE={t}")
    msg = cls.from_bytes(payload)
    object.__setattr__(msg, "timestamp", stamp)
    return msg


@register_message
@dataclass(frozen=True)
class Name(Message):
    """This is demo message, TO BE REMOVED"""

    TYPE: ClassVar[int] = 1
    name: str

    def to_bytes(self) -> bytes:
        return self.name.encode("utf-8")

    @classmethod
    def from_bytes(cls, payload: bytes) -> Name:
        return cls(name=payload.decode("utf-8", errors="replace"))


@register_message
@dataclass(frozen=True)
class ChatText(Message):
    """This is demo message, TO BE REMOVED"""

    TYPE: ClassVar[int] = 2
    text: str

    def to_bytes(self) -> bytes:
        return self.text.encode("utf-8")

    @classmethod
    def from_bytes(cls, payload: bytes) -> ChatText:
        obj = cls(payload.decode("utf-8", errors="replace"))
        return obj


@register_message
@dataclass(frozen=True)
class RawBytes(Message):
    """This is test type message, TO BE REMOVED"""

    TYPE: ClassVar[int] = 3
    data: bytes

    def to_bytes(self) -> bytes:
        return self.data

    @classmethod
    def from_bytes(cls, payload: bytes) -> RawBytes:
        obj = cls(payload)
        return obj


@register_message
@dataclass(frozen=True)
class Discover(Message):
    """
    This is UDP discovery signal from client to look for servers.
    UDP scanner sends this and waits Announce reply from the server.
    """

    TYPE: ClassVar[int] = 4

    def to_bytes(self) -> bytes:
        return bytes()

    @classmethod
    def from_bytes(cls, payload: bytes) -> RawBytes:
        obj = cls()
        return obj


_MAGIC = b"BMBR"
_VERSION = 1


@register_message
@dataclass(frozen=True)
class Announce(Message):
    """
    This is UDP server reply signal to the client
    UDP scanner sends this as the reply to Discovery query.
    """

    TYPE: ClassVar[int] = 5
    port: int
    name: str

    def to_bytes(self) -> bytes:
        name_b = self.name.encode("utf-8", errors="strict")
        if len(name_b) > 255:
            raise ValueError("Announce.name too long (max 255 bytes UTF-8)")

        if not (0 <= self.port <= 65535):
            raise ValueError("Announce.port out of range")

        # ! = network byte order (big endian)
        header = struct.pack("!4sBH", _MAGIC, _VERSION, self.port)
        return header + struct.pack("!B", len(name_b)) + name_b

    @classmethod
    def from_bytes(cls, payload: bytes) -> Announce:
        # Need at least magic(4) + ver(1) + port(2) + name_len(1)
        if len(payload) < 8:
            raise ValueError("Announce payload too short")

        magic, ver, port = struct.unpack("!4sBH", payload[:7])
        if magic != _MAGIC:
            raise ValueError("Bad Announce magic")
        if ver != _VERSION:
            raise ValueError(f"Unsupported Announce version: {ver}")

        (name_len,) = struct.unpack("!B", payload[7:8])
        if len(payload) != 8 + name_len:
            raise ValueError("Announce name length mismatch")

        name_b = payload[8:8 + name_len]
        name = name_b.decode("utf-8", errors="strict")
        return cls(port=port, name=name)


@register_message
@dataclass(frozen=True)
class Ping(Message):
    """
    Network Ping test
    """

    TYPE: ClassVar[int] = 6
    UUID: str

    def to_bytes(self) -> bytes:
        return self.UUID.encode("utf-8")

    @classmethod
    def from_bytes(cls, payload: bytes) -> Ping:
        obj = cls(UUID=payload.decode("utf-8", errors="replace"))
        return obj


@register_message
@dataclass(frozen=True)
class Pong(Message):
    """
    Network Pong test
    """

    TYPE: ClassVar[int] = 7
    ping_UUID: str
    received: int

    def to_bytes(self) -> bytes:
        return self.received.to_bytes(8, "big") + self.ping_UUID.encode("utf-8")

    @classmethod
    def from_bytes(cls, payload: bytes) -> Pong:
        received = int.from_bytes(payload[0:8], "big")
        ping_UUID = payload[8:].decode("utf-8", errors="replace")
        obj = cls(ping_UUID=ping_UUID, received=received)
        return obj


@register_message
@dataclass(frozen=True)
class ClientControl(Message):
    """
    Client control msg
    """

    TYPE: ClassVar[int] = 8
    command: Action

    def to_bytes(self) -> bytes:
        return int(self.command).to_bytes(1, "big")

    @classmethod
    def from_bytes(cls, payload: bytes) -> ClientControl:
        return cls(Action(int.from_bytes(payload, "big")))
