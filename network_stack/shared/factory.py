from network_stack.servers.transport_server import TransportServer
from network_stack.servers.tcp_server import TCPServer, OnReceive
from network_stack.clients.transport_client import TransportClient
from network_stack.clients.tcp_client import TCPClient
from network_stack.shared.alias import OnMessage, OnConnect


def get_server(protocol: str, port: int, on_receive: OnReceive) -> TransportServer:
    if protocol == "tcp":
        return TCPServer(port, on_receive)
    else:
        raise ValueError("Undefined protocol")


def get_client(
    protocol: str, ip: str, port: int, on_message: OnMessage, on_connect: OnConnect
) -> TransportClient:
    if protocol == "tcp":
        return TCPClient(
            ip=ip,
            port=port,
            on_message=on_message,
            on_connect=on_connect,
        )
    else:
        raise ValueError("Undefined protocol")
