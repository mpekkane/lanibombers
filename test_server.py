"""
Test code for server-side
"""

import time
from typing import Dict
from argparse import ArgumentParser
import uuid
from network_stack.bomber_network_server import BomberNetworkServer, ClientContext
from network_stack.messages.messages import Name, ChatText, Ping, Pong


class BomberServer:
    def __init__(self, cfg: str) -> None:
        self.server = BomberNetworkServer(cfg)

        self.server.set_callback(Name, self.on_name)
        self.server.set_callback(ChatText, self.on_chat)
        self.server.set_callback(Pong, self.on_pong)
        self.server.start()

        self.pings: Dict[str, Ping] = {}
        self.average_ping: int = -1
        self.ping_count = 0
        self.pong_count = 0
        self.MAX_PING_BUFFER = 100

    def _ensure_timestamp(self, msg: Ping) -> None:
        if getattr(msg, "timestamp", None) is None:
            object.__setattr__(msg, "timestamp", time.time_ns())

    def ping(self) -> None:
        uid = str(uuid.uuid4())
        ping = Ping(uid)
        self._ensure_timestamp(ping)
        self.server.broadcast(ping)
        self.ping_count += 1
        self.pings[ping.UUID] = ping

        if len(self.pings) > self.MAX_PING_BUFFER:
            drop_n = self.MAX_PING_BUFFER // 2  # e.g. 50 when MAX=100
            oldest_keys = sorted(self.pings, key=lambda k: self.pings[k].timestamp)[:drop_n]
            for k in oldest_keys:
                self.pings.pop(k, None)

    def on_name(self, msg: Name, ctx: ClientContext) -> None:
        ctx.name = msg.name
        print("set name:", msg.name)

    def on_chat(self, msg: ChatText, ctx: ClientContext) -> None:
        sender = ctx.name or "?"
        ctx.broadcast(ChatText(text=f"<{sender}> {msg.text}"), exclude_self=True)

    def on_pong(self, msg: Pong, ctx: ClientContext) -> None:
        ping = self.pings[msg.ping_UUID]
        dt = msg.received - ping.timestamp

        self.pong_count += 1

        if self.average_ping < 0:
            self.average_ping = dt
        else:
            self.average_ping = (self.average_ping * (self.ping_count - 1) + dt) / (
                self.ping_count
            )
        avg_s = self.average_ping / 1e9

        if self.ping_count % 100 == 0:
            # print(f"sent        : {ping.timestamp}")
            # print(f"received    : {msg.received}")
            # print(f"dt      (ns): {dt} ns")
            # print(f"dt      (s) : {dt/1e9} s")
            print(f"average (ns): {self.average_ping} ns")
            print(f"average (s) : {avg_s} s")
            print(f"over pings  : {self.ping_count}")
            print(f"   & pongs  : {self.pong_count}")


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--cfg", "-c", type=str, default="cfg/server_config.yaml")
    args = parser.parse_args()
    cfg = args.cfg
    server = BomberServer(cfg)

    last_ping = time.time()
    tick = 0.01
    while True:
        if time.time() - last_ping > tick:
            server.ping()
            last_ping = time.time()
        time.sleep(tick/2)


if __name__ == "__main__":
    main()
