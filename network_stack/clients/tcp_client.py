# client.py
from __future__ import annotations
import threading
from typing import Callable, Optional, Any

from twisted.internet import protocol, reactor
from twisted.protocols.basic import Int32StringReceiver
from twisted.python.failure import Failure
from twisted.internet import error
from network_stack.shared.alias import (OnMessage, OnConnect, OnDisconnect)
from network_stack.messages.messages import (
    Message,
    encode_message,
    decode_message,
)


class TCPClientProtocol(Int32StringReceiver):
    def __init__(
        self,
        on_message: OnMessage,
        on_connect: Optional[OnConnect],
        on_disconnect: Optional[OnDisconnect],
    ):
        self._on_message = on_message
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect

    def connectionMade(self) -> None:
        if self._on_connect:
            self._on_connect()

    def connectionLost(self, reason: Failure = Failure(error.ConnectionDone())) -> None:
        if self._on_disconnect:
            self._on_disconnect(reason.getErrorMessage())

    def stringReceived(self, string: bytes) -> None:
        try:
            msg = decode_message(string)
        except Exception as e:
            # In real systems: log and maybe drop connection
            print("TCPClientProtocol: Decode error:", e)
            return
        self._on_message(msg)

    def send_message(self, msg: Message) -> None:
        self.sendString(encode_message(msg))  # type: ignore


class TCPClientFactory(protocol.ClientFactory):
    def __init__(self, build_proto: Callable[[], TCPClientProtocol]):
        self._build_proto = build_proto
        self.proto: Optional[TCPClientProtocol] = None

    def buildProtocol(self, addr: str):
        self.proto = self._build_proto()
        return self.proto

    def clientConnectionFailed(
        self, connector: Any, reason: Failure = Failure(error.ConnectionDone())
    ):
        print("TCPClientFactory: Connection failed:", reason.getErrorMessage())
        reactor.stop()  # type: ignore

    def clientConnectionLost(
        self, connector: Any, reason: Failure = Failure(error.ConnectionDone())
    ):
        print("TCPClientFactory: Connection lost:", reason.getErrorMessage())
        reactor.stop()  # type: ignore


class TCPClient:
    """
    Library-style client:
      - start() spins reactor in a background thread
      - send(msg) is safe to call from any thread
      - callbacks deliver received Message objects
    """

    def __init__(
        self,
        ip: str,
        port: int,
        *,
        on_message: OnMessage,
        on_connect: Optional[OnConnect] = None,
        on_disconnect: Optional[OnDisconnect] = None,
    ):
        self._ip = ip
        self._port = port
        self._on_message = on_message
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect

        self._factory = TCPClientFactory(
            build_proto=lambda: TCPClientProtocol(
                on_message=self._on_message,
                on_connect=self._on_connect,
                on_disconnect=self._on_disconnect,
            )
        )

        self._reactor_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        def _run():
            reactor.connectTCP(self._ip, self._port, self._factory)  # type: ignore
            reactor.run(installSignalHandlers=False)  # type: ignore

        self._reactor_thread = threading.Thread(target=_run, daemon=True)
        self._reactor_thread.start()

    def send(self, msg: Message) -> None:
        # thread-safe send
        def _do_send():
            proto = self._factory.proto
            if proto is None or proto.transport is None:  # type: ignore
                print("TCPClient: Not connected yet; dropping message:", msg)
                return
            proto.send_message(msg)

        reactor.callFromThread(_do_send)  # type: ignore
