"""
TCP protocol server scanner.
This is used with TCP clients to discover TCP servers via Discovery/Announce.
Not so neat, as it goes through a lot if the config if wrong, but guarantees
that the communication port is open, since the discovery and communication are
from the same port. Efficiently-minded could use UDP server as a discovery server
that actually replies with the TCP server address, if needed, since UDP discovery
is A LOT faster, due to the UDP broadcast.
"""

from typing import Optional, List, Tuple
import socket
from itertools import product
from concurrent.futures import ThreadPoolExecutor
from network_stack.clients.transport_scanner import TransportScanner


class TCPScanner(TransportScanner):
    def __init__(self, base_addr: str, subnet: Optional[int], port: Optional[int], host: Optional[int]) -> None:
        self.base_addr = base_addr
        self.scan_subnets = False
        self.scan_ports = False
        if subnet is not None:
            self.subnet = subnet
        else:
            self.subnet = -1
            self.scan_subnets = True
            print("WARNING: missing subnet config")
        if port is not None:
            self.port = port
        else:
            self.port = -1
            self.scan_ports = True
            print("WARNING: missing port config")
        if host:
            self.host = host
        else:
            self.host = -1

    def _scan_port(self, ip: int, port: int) -> Tuple[bool, str, int]:
        tgt = f"{self.base_addr}.{self.subnet}.{ip}"
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((tgt, port))
            sock.close()
            return result == 0, tgt, port
        except Exception:
            return False, "", -1

    def _scan_ports(self, ip_start: int, ip_end: int) -> List[Tuple[bool, str, int]]:
        open_ports: List[Tuple[bool, str, int]] = []
        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [
                executor.submit(self._scan_port, ip, self.port)
                for ip in range(ip_start, ip_end + 1)
            ]
            for future in futures:
                result = future.result()
                if result:
                    open_ports.append(result)
        return open_ports

    def scan(self) -> List[Tuple[str, int]]:
        if self.scan_subnets:
            subnets = range(0, 256)
        else:
            subnets = [self.subnet]

        if self.scan_ports:
            ports = range(8000, 9000)
        else:
            ports = [self.port]

        all_found: List[Tuple[str, int]] = []
        first = True
        for subnet, port in product(subnets, ports):
            found = self._scan_one(subnet, port, self.host)
            if first:
                all_found = found
                first = False
            else:
                all_found += found
        return all_found

    def _scan_one(self, subnet: int, port: int, host: int) -> List[Tuple[str, int]]:
        print(f"Subnet: {subnet}")
        print(f"Port: {port}")
        print("Looking for servers...")

        if host > 0 and host < 256:
            ip_from = host
            ip_to = host
        else:
            ip_from = 0
            ip_to = 256

        results = self._scan_ports(ip_from, ip_to)
        found: List[Tuple[str, int]] = []
        for res, tgt, port in results:
            if res:
                found.append((tgt, port))
        return found
