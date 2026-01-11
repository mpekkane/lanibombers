"""
Abstract base class for TCP/UDP server discovery.
"""


from abc import ABC, abstractmethod
from typing import List, Tuple


class TransportScanner(ABC):
    @abstractmethod
    def scan(self) -> List[Tuple[str, int]]:
        """Find servers"""
