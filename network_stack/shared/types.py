"""
Commonly used types to avoid circular imports.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class PeerState:
    name: Optional[str] = None
