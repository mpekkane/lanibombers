from __future__ import annotations
from dataclasses import dataclass
from typing import ClassVar, Dict, Type, Iterable


class Message:
    TYPE: ClassVar[int] = -1  # override

    def to_bytes(self) -> bytes: ...
    @classmethod
    def from_bytes(cls, payload: bytes) -> "Message": ...


_REGISTRY: Dict[int, Type[Message]] = {}


def get_registered_message_types() -> Iterable[type[Message]]:
    return _REGISTRY.values()


def register_message(cls: Type[Message]) -> Type[Message]:
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
    if not (0 <= t <= 255):
        raise ValueError(f"TYPE must be 0..255, got {t}")
    return bytes([t]) + msg.to_bytes()


def decode_message(frame: bytes) -> Message:
    if len(frame) < 1:
        raise ValueError("Empty frame")
    t = frame[0]
    payload = frame[1:]
    cls = _REGISTRY.get(t)
    if cls is None:
        raise ValueError(f"Unknown message TYPE={t}")
    return cls.from_bytes(payload)


@register_message
@dataclass(frozen=True)
class Name(Message):
    TYPE: ClassVar[int] = 1
    name: str

    def to_bytes(self) -> bytes:
        return self.name.encode("utf-8")

    @classmethod
    def from_bytes(cls, payload: bytes) -> Name:
        return cls(payload.decode("utf-8", errors="replace"))


@register_message
@dataclass(frozen=True)
class ChatText(Message):
    TYPE: ClassVar[int] = 2
    text: str

    def to_bytes(self) -> bytes:
        return self.text.encode("utf-8")

    @classmethod
    def from_bytes(cls, payload: bytes) -> ChatText:
        return cls(payload.decode("utf-8", errors="replace"))


@register_message
@dataclass(frozen=True)
class RawBytes(Message):
    TYPE: ClassVar[int] = 3
    data: bytes

    def to_bytes(self) -> bytes:
        return self.data

    @classmethod
    def from_bytes(cls, payload: bytes) -> RawBytes:
        return cls(payload)
