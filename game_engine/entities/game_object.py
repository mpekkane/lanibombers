from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass
class GameObject:
    """Base class for all game objects."""
    id: UUID = field(default_factory=uuid4)
    health: int = 100
    visual_id: int = 0
    color: tuple = (255, 255, 255)
