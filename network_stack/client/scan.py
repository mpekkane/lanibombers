from typing import Optional, List, Tuple
import socket
from itertools import product
from concurrent.futures import ThreadPoolExecutor


class Scanner:
    def __init__(self, subnet: Optional[int], port: Optional[int]) -> None:
        self.scan_subnets = False
        self.scan_ports = False
        if subnet:
            self.subnet = subnet
        else:
            self.subnet = -1
            self.scan_subnets = True
            print("WARNING: missing subnet config")
        if port:
            self.port = port
        else:
            self.port = -1
            self.scan_ports = True
            print("WARNING: missing port config")

    def _scan_port(self, ip: int, port: int) -> Tuple[bool, str]:
        tgt = f"192.168.{self.subnet}.{ip}"
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((tgt, port))
            sock.close()
            return result == 0, tgt
        except Exception:
            return False, ""

    def _scan_ports(self, ip_start: int, ip_end: int) -> List[Tuple[bool, str]]:
        open_ports: List[Tuple[bool, str]] = []
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

    def scan(self) -> List[str]:
        if self.scan_subnets:
            subnets = range(0, 256)
        else:
            subnets = [self.subnet]

        if self.scan_ports:
            ports = range(8000, 9000)
        else:
            ports = [self.port]

        all_found: List[str] = []
        first = True
        for subnet, port in product(subnets, ports):
            found = self._scan_one(subnet, port)
            if first:
                all_found = found
                first = False
            else:
                all_found += found
        return all_found

    def _scan_one(self, subnet: int, port: int) -> List[str]:
        print(f"Subnet: {subnet}")
        print(f"Port: {port}")
        print("Looking for servers...")
        results = self._scan_ports(0, 200)
        found: List[str] = []
        for res, tgt in results:
            if res:
                found.append(tgt)
        return found
