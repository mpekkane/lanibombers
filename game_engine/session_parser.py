from __future__ import annotations
from enum import IntEnum
from typing import List
from common.config_reader import ConfigReader


class SessionMapType(IntEnum):
    RANDOM = 0
    LOAD = 1


class SessionMap:
    def __init__(
        self,
        maptype: SessionMapType,
        map_path: str = "",
        width: int = 64,
        height: int = 45,
        feature_sizes: List[int] = [20, 5],
        threshold: float = 0.3,
        min_treasure: int = 10,
        max_treasure: int = 40,
        min_tools: int = 5,
        max_tools: int = 20,
        max_rooms: int = 5,
        room_chance: float = 0.1,
    ) -> None:
        self.type = maptype
        self.map_path = map_path
        self.width = width
        self.height = height
        self.feature_sizes = feature_sizes
        self.threshold = threshold
        self.min_treasure = min_treasure
        self.max_treasure = max_treasure
        self.min_tools = min_tools
        self.max_tools = max_tools
        self.max_rooms = max_rooms
        self.room_chance = room_chance


class Session:
    def __init__(
        self,
        starting_money: int,
        floating_market: bool,
        damage_multiplier: float,
        speed_multiplier: float,
        maps: List[SessionMap],
    ) -> None:
        self.valid = True
        self.starting_money = starting_money
        self.floating_market = floating_market
        self.damage_multiplier = damage_multiplier
        self.speed_multiplier = speed_multiplier
        self.maps = maps
        self._current_map = 0

    def get_next_map(self) -> SessionMap:
        next_map = self.maps[self._current_map]
        self._current_map += 1
        return next_map

    @staticmethod
    def get_dummy() -> Session:
        session = Session(0, False, 0, 0, [])
        session.valid = False
        return session

    @staticmethod
    def parse_session(config_path: str) -> Session:
        config = ConfigReader(config_path)
        if not config.config:
            return Session.get_dummy()
        starting_money = config.get_config_mandatory("starting_money", int)
        floating_market = config.get_config_mandatory("floating_market", bool)
        damage_multiplier = config.get_config_mandatory("damage_multiplier", float)
        speed_multiplier = config.get_config_mandatory("speed_multiplier", float)

        maps = []
        raw_maps = config.get_config_mandatory("maps", list)
        for raw in raw_maps:
            if isinstance(raw, str):
                if "assets/maps" not in raw:
                    map_path = f"assets/maps/{raw}"
                else:
                    map_path = raw
                maps.append(SessionMap(SessionMapType.LOAD, map_path=map_path))
            else:
                width = raw["width"]
                height = raw["height"]
                feature_sizes = raw["feature_sizes"]
                threshold = raw["threshold"]
                min_treasure = raw["min_treasure"]
                max_treasure = raw["max_treasure"]
                min_tools = raw["min_tools"]
                max_tools = raw["max_tools"]
                max_rooms = raw["max_rooms"]
                room_chance = raw["room_chance"]
                maps.append(
                    SessionMap(
                        SessionMapType.RANDOM,
                        width=width,
                        height=height,
                        feature_sizes=feature_sizes,
                        threshold=threshold,
                        min_treasure=min_treasure,
                        max_treasure=max_treasure,
                        min_tools=min_tools,
                        max_tools=max_tools,
                        max_rooms=max_rooms,
                        room_chance=room_chance,
                    )
                )

        return Session(
            starting_money, floating_market, damage_multiplier, speed_multiplier, maps
        )

    @staticmethod
    def get_single_map_session(map_path: str) -> Session:
        maps = []
        if map_path:
            maps.append(SessionMap(SessionMapType.LOAD, map_path=map_path))
        else:
            maps.append(SessionMap(SessionMapType.RANDOM))
        session = Session(
            starting_money=500,
            floating_market=False,
            damage_multiplier=1.0,
            speed_multiplier=1.0,
            maps=maps,
        )
        return session
