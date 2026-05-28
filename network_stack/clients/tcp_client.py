"""
TCP client.
This client communicates with a TCP server.
"""

from __future__ import annotations

import threading
from typing import Callable, Optional, Any

from twisted.internet import protocol, reactor
from twisted.python.failure import Failure
from twisted.internet import error
from twisted.internet.endpoints import TCP4ClientEndpoint

from network_stack.clients.transport_client import (
    TransportClient,
    TransportClientProtocol,
)
from network_stack.shared.alias import OnMessage, OnConnect, OnDisconnect
from network_stack.messages.messages import (
    Message,
    encode_message,
    decode_message,
)
from common.logger import get_logger


class TCPClientProtocol(TransportClientProtocol):
    """Twisted protocol."""

    def __init__(
        self,
        on_message: OnMessage,
        on_connect: Optional[OnConnect],
        on_disconnect: Optional[OnDisconnect],
    ) -> None:
        self.log = get_logger()
        self._on_message = on_message
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect

    def connectionMade(self) -> None:
        self.log.info("TCPClientProtocol: connection made")

        if self._on_connect:
            try:
                self._on_connect()
            except Exception:
                self.log.exception("TCPClientProtocol: on_connect callback failed")

    def connectionLost(self, reason: Failure = Failure(error.ConnectionDone())) -> None:
        message = reason.getErrorMessage()
        self.log.info("TCPClientProtocol: connection lost: %s", message)

        if self._on_disconnect:
            try:
                self._on_disconnect(message)
            except Exception:
                self.log.exception("TCPClientProtocol: on_disconnect callback failed")

    def stringReceived(self, string: bytes) -> None:
        try:
            msg = decode_message(string)
        except Exception:
            self.log.exception("TCPClientProtocol: decode error")
            return

        try:
            self._on_message(msg)
        except Exception:
            self.log.exception("TCPClientProtocol: on_message callback failed")

    def send_message(self, msg: Message) -> None:
        self.sendString(encode_message(msg))  # type: ignore


class TCPClientFactory(protocol.ClientFactory):
    """Object factory."""

    def __init__(self, build_proto: Callable[[], TCPClientProtocol]) -> None:
        self._build_proto = build_proto
        self.proto: Optional[TCPClientProtocol] = None
        self.connected = False
        self.log = get_logger()

    def buildProtocol(self, addr: Any) -> TCPClientProtocol:
        self.proto = self._build_proto()
        self.connected = True
        self.log.info("TCPClientFactory: connected to %s", addr)
        return self.proto

    def clientConnectionFailed(
        self,
        connector: Any,
        reason: Failure = Failure(error.ConnectionDone()),
    ) -> None:
        self.connected = False
        self.proto = None

        self.log.warning(
            "TCPClientFactory: connection failed: %s",
            reason.getErrorMessage(),
        )

        # Do NOT reactor.stop() here.
        # Keep the reactor alive so this process can reconnect.

    def clientConnectionLost(
        self,
        connector: Any,
        reason: Failure = Failure(error.ConnectionDone()),
    ) -> None:
        self.connected = False
        self.proto = None

        self.log.warning(
            "TCPClientFactory: connection lost: %s",
            reason.getErrorMessage(),
        )

        # Do NOT reactor.stop() here.
        # TCPClientProtocol.connectionLost already calls on_disconnect.


class TCPClient(TransportClient):
    """
    Library-style client:
      - start() spins reactor in a background thread, only once
      - send(msg) is safe to call from any thread
      - callbacks deliver received Message objects
      - disconnect() closes TCP connection but keeps reactor alive
      - reconnect_to(...) reconnects using the same running reactor
      - stop() stops reactor only for final app shutdown
    """

    def __init__(
        self,
        ip: str,
        port: int,
        *,
        on_message: OnMessage,
        on_connect: Optional[OnConnect] = None,
        on_disconnect: Optional[OnDisconnect] = None,
        local_ip: Optional[str] = None,
    ) -> None:
        self._ip = ip
        self._port = port
        self._local_ip = local_ip

        self._on_message = on_message
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect

        self.log = get_logger()
        self.log.info("TCP client, local ip: %s", local_ip)

        self._factory = TCPClientFactory(
            build_proto=lambda: TCPClientProtocol(
                on_message=self._on_message,
                on_connect=self._on_connect,
                on_disconnect=self._on_disconnect,
            )
        )

        self._reactor_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """
        Connect to the configured server.

        If reactor already runs, only schedules the connection.
        If reactor is not running yet, starts it in a background thread.
        """

        def _connect() -> None:
            self.log.info(
                "TCPClient: connecting to %s:%s from local_ip=%s",
                self._ip,
                self._port,
                self._local_ip,
            )

            endpoint = TCP4ClientEndpoint(
                reactor,
                self._ip,
                self._port,
                bindAddress=(self._local_ip, 0) if self._local_ip else None,
            )
            endpoint.connect(self._factory)

        if reactor.running:  # type: ignore
            reactor.callFromThread(_connect)  # type: ignore
            return

        def _run() -> None:
            _connect()
            reactor.run(installSignalHandlers=False)  # type: ignore

        self._reactor_thread = threading.Thread(
            target=_run,
            daemon=True,
            name="TCPClientReactorThread",
        )
        self._reactor_thread.start()

    def reconnect_to(
        self,
        ip: str,
        port: int,
        *,
        local_ip: Optional[str] = None,
    ) -> None:
        """
        Disconnect current TCP connection and connect to another server.

        Keeps the Twisted reactor alive.
        """
        self._ip = ip
        self._port = port
        self._local_ip = local_ip

        def _do_reconnect() -> None:
            proto = self._factory.proto

            if proto is not None and proto.transport is not None:  # type: ignore
                self.log.info("TCPClient: closing old connection before reconnect")
                proto.transport.loseConnection()  # type: ignore

            self._factory.proto = None
            self._factory.connected = False

            self.log.info(
                "TCPClient: reconnecting to %s:%s from local_ip=%s",
                self._ip,
                self._port,
                self._local_ip,
            )

            endpoint = TCP4ClientEndpoint(
                reactor,
                self._ip,
                self._port,
                bindAddress=(self._local_ip, 0) if self._local_ip else None,
            )
            endpoint.connect(self._factory)

        if reactor.running:  # type: ignore
            reactor.callFromThread(_do_reconnect)  # type: ignore
        else:
            self.start()

    def disconnect(self) -> None:
        """
        Close current TCP connection but keep reactor alive.

        Use this when returning to menu or before reconnecting.
        """

        def _do_disconnect() -> None:
            proto = self._factory.proto

            if proto is not None and proto.transport is not None:  # type: ignore
                self.log.info("TCPClient: disconnecting")
                proto.transport.loseConnection()  # type: ignore

            self._factory.proto = None
            self._factory.connected = False

        if reactor.running:  # type: ignore
            reactor.callFromThread(_do_disconnect)  # type: ignore

    def stop(self) -> None:
        """
        Final app shutdown.

        Warning:
            Twisted's default reactor cannot be restarted after stop().
            Do not use this for reconnecting.
        """

        def _do_stop() -> None:
            proto = self._factory.proto

            if proto is not None and proto.transport is not None:  # type: ignore
                self.log.info("TCPClient: closing connection before reactor stop")
                proto.transport.loseConnection()  # type: ignore

            self._factory.proto = None
            self._factory.connected = False

            if reactor.running:  # type: ignore
                self.log.info("TCPClient: stopping reactor")
                reactor.stop()  # type: ignore

        if reactor.running:  # type: ignore
            reactor.callFromThread(_do_stop)  # type: ignore

        if self._reactor_thread is not None:
            self._reactor_thread.join(timeout=2.0)
            self._reactor_thread = None

    def send(self, msg: Message) -> None:
        """
        Thread-safe send.

        Drops message gracefully if not connected.
        """

        def _do_send() -> None:
            proto = self._factory.proto

            if (
                proto is None
                or proto.transport is None  # type: ignore
                or not getattr(proto.transport, "connected", False)  # type: ignore
            ):
                self.log.warning("TCPClient: not connected; dropping message: %s", msg)
                return

            try:
                proto.send_message(msg)
            except Exception:
                self.log.exception("TCPClient: failed to send message")

        if reactor.running:  # type: ignore
            reactor.callFromThread(_do_send)  # type: ignore
        else:
            self.log.warning(
                "TCPClient: reactor not running; dropping message: %s", msg
            )
