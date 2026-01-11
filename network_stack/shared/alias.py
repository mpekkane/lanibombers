from typing import Callable
from network_stack.messages.messages import (
    Message,
)

OnMessage = Callable[[Message], None]
OnConnect = Callable[[], None]
OnDisconnect = Callable[[str], None]
