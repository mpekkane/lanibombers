"""
Container for the game messaging.
This file contains all the network message definitions (subclasses of Message),
and handles registry of the message types, encoding and decoding.
"""

from __future__ import annotations
import struct
from dataclasses import dataclass
import pickle
import numpy as np
from game_engine.clock import Clock
from typing import ClassVar, Dict, Type, Iterable, List
from game_engine.agent_state import Action
from game_engine.entities import Pickup, Bomb, DynamicEntity, Player
from game_engine.render_state import RenderState


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
    """Client sends name, color and appearance when joining."""

    TYPE: ClassVar[int] = 1
    name: str
    color: tuple = (255, 255, 255)  # (r, g, b)
    appearance_id: int = 1  # 1-4

    def to_bytes(self) -> bytes:
        name_bytes = self.name.encode("utf-8")
        return (
            bytes([len(name_bytes)])
            + name_bytes
            + bytes([self.color[0], self.color[1], self.color[2]])
            + bytes([self.appearance_id])
        )

    @classmethod
    def from_bytes(cls, payload: bytes) -> Name:
        name_len = payload[0]
        name = payload[1 : 1 + name_len].decode("utf-8", errors="replace")
        off = 1 + name_len
        color = (payload[off], payload[off + 1], payload[off + 2])
        appearance_id = payload[off + 3]
        return cls(name=name, color=color, appearance_id=appearance_id)


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

        name_b = payload[8 : 8 + name_len]
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


@register_message
@dataclass(frozen=True)
class ClientSelect(Message):
    """Client sends specific weapon selection by BombType enum value."""

    TYPE: ClassVar[int] = 10
    bomb_type: int

    def to_bytes(self) -> bytes:
        return self.bomb_type.to_bytes(1, "big")

    @classmethod
    def from_bytes(cls, payload: bytes) -> ClientSelect:
        return cls(bomb_type=int.from_bytes(payload, "big"))


@register_message
@dataclass(frozen=True)
class GameState(Message):

    TYPE: ClassVar[int] = 9
    width: int
    height: int
    tilemap: np.ndarray
    explosions: np.ndarray
    players: List[Player]
    monsters: List[DynamicEntity]
    pickups: List[Pickup]
    bombs: List[Bomb]
    server_time: float
    sounds: tuple = ()

    @staticmethod
    def from_render(state: RenderState) -> GameState:
        return GameState(
            width=state.width,
            height=state.height,
            tilemap=state.tilemap,
            explosions=state.explosions,
            players=state.players,
            monsters=state.monsters,
            pickups=state.pickups,
            bombs=state.bombs,
            server_time=state.server_time,
            sounds=tuple(state.sounds),
        )

    def to_render(self) -> RenderState:
        return RenderState(
            width=self.width,
            height=self.height,
            tilemap=self.tilemap,
            explosions=self.explosions,
            players=self.players,
            monsters=self.monsters,
            pickups=self.pickups,
            bombs=self.bombs,
            server_time=self.server_time,
            sounds=list(self.sounds),
        )

    def to_bytes(self) -> bytes:
        # main data
        b_width = self.width.to_bytes(1, "big")
        b_height = self.height.to_bytes(1, "big")
        b_server_time = struct.pack("!d", self.server_time)  # 8 bytes double
        b_tilemap = self.tilemap.tobytes()
        b_explosions = self.explosions.tobytes()
        b_players = pickle.dumps(self.players)
        b_monsters = pickle.dumps(self.monsters)
        b_pickups = pickle.dumps(self.pickups)
        b_bombs = pickle.dumps(self.bombs)
        b_sounds = bytes(self.sounds)
        # auxiliary data
        b_num_players = len(self.players).to_bytes(1, "big")
        b_num_monsters = len(self.monsters).to_bytes(1, "big")
        b_num_pickups = len(self.pickups).to_bytes(1, "big")
        b_num_bombs = len(self.bombs).to_bytes(1, "big")
        b_tilemap_size = self.tilemap.size.to_bytes(4, "big")
        b_explosions_size = self.explosions.size.to_bytes(4, "big")
        b_players_size = len(b_players).to_bytes(2, "big")
        b_monsters_size = len(b_monsters).to_bytes(2, "big")
        b_pickups_size = len(b_pickups).to_bytes(2, "big")
        b_bombs_size = len(b_bombs).to_bytes(2, "big")
        b_sounds_size = len(b_sounds).to_bytes(2, "big")

        return (
            b_width
            + b_height
            + b_server_time
            + b_num_players
            + b_num_monsters
            + b_num_pickups
            + b_num_bombs
            + b_tilemap_size
            + b_explosions_size
            + b_players_size
            + b_monsters_size
            + b_pickups_size
            + b_bombs_size
            + b_sounds_size
            + b_tilemap
            + b_explosions
            + b_players
            + b_monsters
            + b_pickups
            + b_bombs
            + b_sounds
        )

    @classmethod
    def from_bytes(cls, payload: bytes) -> GameState:
        width = int(payload[0])
        height = int(payload[1])
        (server_time,) = struct.unpack("!d", payload[2:10])
        num_players = int(payload[10])
        num_monsters = int(payload[11])
        num_pickups = int(payload[12])
        num_bombs = int(payload[13])
        tilemap_size = int.from_bytes(payload[14:18], "big")
        explosions_size = int.from_bytes(payload[18:22], "big")
        players_size = int.from_bytes(payload[22:24], "big")
        monsters_size = int.from_bytes(payload[24:26], "big")
        pickups_size = int.from_bytes(payload[26:28], "big")
        bombs_size = int.from_bytes(payload[28:30], "big")
        sounds_size = int.from_bytes(payload[30:32], "big")
        start = 32
        stop = start + tilemap_size
        tilemap = np.frombuffer(payload[start:stop], dtype=np.uint8).reshape(
            (height, width)
        )
        start = stop
        stop = start + explosions_size
        explosions = np.frombuffer(payload[start:stop], dtype=np.uint8).reshape(
            (height, width)
        )
        start = stop
        stop = start + players_size
        players = pickle.loads(payload[start:stop])
        start = stop
        stop = start + monsters_size
        if monsters_size == 5:
            monsters = []
        else:
            monsters = pickle.loads(payload[start:stop])
        start = stop
        stop = start + pickups_size
        if pickups_size == 5:
            pickups = []
        else:
            pickups = pickle.loads(payload[start:stop])
        start = stop
        stop = start + bombs_size
        if bombs_size == 5:
            bombs = []
        else:
            bombs = pickle.loads(payload[start:stop])
        start = stop
        stop = start + sounds_size
        sounds = tuple(payload[start:stop])

        return cls(
            width=width,
            height=height,
            tilemap=tilemap,
            explosions=explosions,
            players=players,
            monsters=monsters,
            pickups=pickups,
            bombs=bombs,
            server_time=server_time,
            sounds=sounds,
        )
