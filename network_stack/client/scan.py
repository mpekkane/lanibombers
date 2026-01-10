from typing import Optional, List
import socket
from itertools import product
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor


class Scanner:
    def __init__(self, subnet: Optional[int], port: Optional[int]):
        self.subnet = subnet
        self.port = port

    def _scan_port(self, ip, port) -> bool:
        tgt = f"192.168.{self.subnet}.{ip}"
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((tgt, port))
            sock.close()
            return result == 0, tgt
        except:
            return False

    def _scan_ports(self, ip_start, ip_end):
        open_ports = []
        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(self._scan_port, ip, self.port) for ip in range(ip_start, ip_end + 1)]
            for future in futures:
                result = future.result()
                if result:
                    open_ports.append(result)
        return open_ports

    def scan(self) -> List[str]:
        print(f"Subnet: {self.subnet}")
        print(f"Port: {self.port}")
        print("Looking for servers...")
        results = self._scan_ports(0, 200)
        found = []
        for res, tgt in results:
            if res:
                found.append(tgt)
        return found