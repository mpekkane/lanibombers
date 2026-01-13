"""
Server and client factory.
This enables the BomberClient/Server to create transport layer client/servers
"""

from typing import Optional
from network_stack.servers.transport_server import TransportServer, OnReceive
from network_stack.servers.tcp_server import TCPServer
from network_stack.servers.udp_server import UDPServer
from network_stack.clients.transport_client import TransportClient
from network_stack.clients.tcp_client import TCPClient
from network_stack.clients.udp_client import UDPClient
from network_stack.shared.alias import OnMessage, OnConnect, OnDisconnect
from network_stack.clients.transport_scanner import TransportScanner
from network_stack.clients.tcp_scanner import TCPScanner
from network_stack.clients.udp_scanner import UDPScanner


def get_server(protocol: str, port: int, on_receive: OnReceive) -> TransportServer:
    if protocol == "udp":
        return UDPServer(port, on_receive)
    if protocol == "tcp":
        return TCPServer(port, on_receive)
    raise ValueError(protocol)


def get_client(
    protocol: str,
    ip: str,
    port: int,
    on_message: OnMessage,
    on_connect: Optional[OnConnect] = None,
    on_disconnect: Optional[OnDisconnect] = None,
) -> TransportClient:
    if protocol == "udp":
        return UDPClient(
            ip,
            port,
            on_message=on_message,
            on_connect=on_connect,
            on_disconnect=on_disconnect,
        )
    if protocol == "tcp":
        return TCPClient(
            ip,
            port,
            on_message=on_message,
            on_connect=on_connect,
            on_disconnect=on_disconnect,
        )
    raise ValueError(protocol)


def get_scanner(
    protocol: str,
    base_addr: str,
    subnet: Optional[int],
    port: Optional[int],
    host: Optional[int],
    timeout: Optional[float],
) -> TransportScanner:
    if protocol == "udp":
        assert port, "UDP scanning required a known port"
        return UDPScanner(base_addr, subnet, port, timeout)
    if protocol == "tcp":
        return TCPScanner(base_addr, subnet, port, host)
    raise ValueError(protocol)
