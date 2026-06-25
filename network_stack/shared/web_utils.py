"""
Network utilities.
"""

import socket


def get_local_ip() -> str:
    """Best-effort local LAN IP address (the egress interface).

    Opens a UDP socket and "connects" it to a public address so the OS picks
    the outbound interface; no packets are actually sent. Falls back to
    hostname resolution and finally loopback.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        pass

    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return "127.0.0.1"
