"""
UDP protocol server scanner.
This is used with UDP clients to discover UDP servers via Discovery/Announce.
"""

from __future__ import annotations
from typing import List, Tuple, Optional
import socket

from game_engine.clock import Clock
from network_stack.messages.messages import encode_message, decode_message
from network_stack.messages.messages import Message, Discover, Announce
from network_stack.clients.transport_scanner import TransportScanner


def _local_broadcast_addr(base_addr: str, subnet: int) -> str:
    return f"{base_addr}.{subnet}.255"


class UDPScanner(TransportScanner):

    def __init__(
        self,
        base_addr: str,
        subnet: Optional[int],
        port: int,
        timeout_s: Optional[float] = 1.0,
    ) -> None:
        self.base_addr = base_addr
        self.subnet = subnet
        self.port = port
        self.timeout_s = timeout_s

    def scan(self) -> List[Tuple[str, int]]:
        """
        Broadcast DISCOVER once, collect ANNOUNCE replies for timeout_s.
        """
        if self.subnet is None:
            # fallback: global broadcast; may be blocked on some LANs
            bcast = "255.255.255.255"
        else:
            bcast = _local_broadcast_addr(self.base_addr, self.subnet)

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(0.1)

            # bind so we can receive replies
            sock.bind(("0.0.0.0", 0))
            local_port = sock.getsockname()[1]

            # send discovery
            discover_msg: Message = Discover()
            payload = encode_message(discover_msg)
            print(f"send to {bcast}")
            sock.sendto(payload, (bcast, self.port))

            found: dict[Tuple[str, int], None] = {}

            deadline = Clock.now() + self.timeout_s
            while Clock.now() < deadline:
                try:
                    data, (ip, port) = sock.recvfrom(65535)
                except socket.timeout:
                    continue
                try:
                    msg = decode_message(data)
                except Exception:
                    continue

                if isinstance(msg, Announce):
                    found[(ip, msg.port)] = None
                    break

            return list(found.keys())
        finally:
            sock.close()
