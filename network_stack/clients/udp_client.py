"""
UDP client.
This client communicates with a UDP server.
"""

from __future__ import annotations
import threading
from typing import Optional

from twisted.internet import reactor
from twisted.internet.protocol import DatagramProtocol
from twisted.python.failure import Failure
from twisted.internet import error

from network_stack.messages.messages import Message, encode_message, decode_message
from network_stack.shared.alias import OnMessage, OnConnect, OnDisconnect
from network_stack.clients.transport_client import TransportClient


class _UDPClientWire(DatagramProtocol):
    def __init__(
        self,
        ip: str,
        port: int,
        on_message: OnMessage,
        on_connect: Optional[OnConnect],
        on_disconnect: Optional[OnDisconnect],
    ) -> None:
        self._ip = ip
        self._port = port
        self._on_message = on_message
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect

    def startProtocol(self) -> None:
        # Connect sets the default destination for write()
        self.transport.connect(self._ip, self._port)
        # If you want the client to receive broadcast replies, also allow broadcast:
        self.transport.setBroadcastAllowed(True)

        if self._on_connect:
            self._on_connect()

    def datagramReceived(self, data: bytes, addr) -> None:
        try:
            msg = decode_message(data)
        except Exception as e:
            print("UDPClient decode error:", e)
            return
        self._on_message(msg)

    def stopProtocol(self) -> None:
        if self._on_disconnect:
            self._on_disconnect("udp stopped")  # type: ignore[arg-type]

    def send_message(self, msg: Message) -> None:
        self.transport.write(encode_message(msg))


class UDPClient(TransportClient):
    """Twisted wrapper"""
    def __init__(
        self,
        ip: str,
        port: int,
        *,
        on_message: OnMessage,
        on_connect: Optional[OnConnect] = None,
        on_disconnect: Optional[OnDisconnect] = None,
    ) -> None:
        self._ip = ip
        self._port = port
        self._on_message = on_message
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect

        self._wire = _UDPClientWire(ip, port, on_message, on_connect, on_disconnect)
        self._reactor_thread: Optional[threading.Thread] = None
        self._listening_port = None

    def start(self) -> None:
        def _run():
            # bind to an ephemeral local port
            self._listening_port = reactor.listenUDP(0, self._wire)
            reactor.run(installSignalHandlers=False)

        self._reactor_thread = threading.Thread(target=_run, daemon=True)
        self._reactor_thread.start()

    def send(self, msg: Message) -> None:
        # thread-safe send
        reactor.callFromThread(self._wire.send_message, msg)

    def stop(self) -> None:
        def _do():
            try:
                if self._listening_port is not None:
                    self._listening_port.stopListening()
            finally:
                if reactor.running:
                    reactor.stop()

        reactor.callFromThread(_do)
