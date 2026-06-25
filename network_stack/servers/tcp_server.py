"""
TCP server.
Handles server-side TCP traffic.
"""

from __future__ import annotations
from typing import Dict, Optional
import threading

from twisted.internet.protocol import Factory
from twisted.internet import reactor, error
from twisted.python.failure import Failure
from twisted.protocols.basic import Int32StringReceiver
from network_stack.servers.transport_server import (
    TransportServer,
    TransportServerProtocol,
    ServerAddressInUseError,
    OnReceive,
    OnDisconnect,
)
from network_stack.messages.messages import Message, encode_message, decode_message
from network_stack.shared.types import PeerState
from common.logger import get_logger


class TCPServerProtocol(TransportServerProtocol, Int32StringReceiver):
    """This is the twisted per-connection protocol handler"""

    def __init__(
        self,
        peers: Dict["TCPServerProtocol", PeerState],
        on_receive: OnReceive,
        on_disconnect: OnDisconnect,
    ) -> None:
        self._peers = peers
        self._state = PeerState()
        self._on_receive = on_receive
        self._on_disconnect = on_disconnect
        self.log = get_logger()

    def connectionMade(self) -> None:
        self._peers[self] = self._state

    def connectionLost(self, reason: Failure = Failure(error.ConnectionDone())) -> None:
        self._peers.pop(self, None)
        self._on_disconnect(self._state, self, reason)

    def stringReceived(self, string: bytes) -> None:
        try:
            msg = decode_message(string)
        except Exception as e:
            self.log.error("TCPServerProto: Decode error:", e)
            return
        self._on_receive(msg, self._state, self)

    def send_message(self, msg: Message) -> None:
        self.sendString(encode_message(msg))  # type: ignore


class TCPServerFactory(Factory):
    """Creates protocol instance for each connection"""

    def __init__(self, on_receive: OnReceive, on_disconnect: OnDisconnect) -> None:
        self._peers: Dict[TCPServerProtocol, PeerState] = {}
        self._on_receive = on_receive
        self._on_disconnect = on_disconnect

    def buildProtocol(self, addr: str):
        return TCPServerProtocol(self._peers, self._on_receive, self._on_disconnect)

    @property
    def peers(self) -> Dict[TCPServerProtocol, PeerState]:
        return self._peers


class TCPServer(TransportServer):
    """Wrapper for twisted"""

    def __init__(
        self, port: int, on_receive: OnReceive, on_disconnect: OnDisconnect
    ) -> None:
        self.port = port
        self._factory = TCPServerFactory(
            on_receive=on_receive, on_disconnect=on_disconnect
        )
        self._reactor_thread: Optional[threading.Thread] = None
        self._listening_port = None  # Twisted IListeningPort
        self._started = False

    def start(self) -> None:
        """Start accepting TCP connections without restarting the reactor.

        Binding happens synchronously: start() blocks until the port is either
        bound or known to have failed, so a port-already-in-use error surfaces
        to the caller as ServerAddressInUseError instead of silently killing the
        reactor thread with an unhandled traceback.
        """
        self._listen_error: Optional[BaseException] = None
        listen_done = threading.Event()

        def _listen() -> None:
            try:
                if self._listening_port is not None:
                    return
                self._listening_port = reactor.listenTCP(  # type: ignore
                    self.port,
                    self._factory,
                    interface="0.0.0.0",
                )
                self._started = True
            except error.CannotListenError as exc:
                self._listen_error = exc
            finally:
                listen_done.set()

        if reactor.running:  # type: ignore
            reactor.callFromThread(_listen)  # type: ignore
            listen_done.wait()
            self._raise_if_listen_failed()
            return

        def _run() -> None:
            _listen()
            # Only drive the reactor if the bind succeeded. Otherwise the thread
            # would crash inside reactor.run() on the failed listener.
            if self._listen_error is None:
                reactor.run(installSignalHandlers=False)  # type: ignore

        self._reactor_thread = threading.Thread(
            target=_run,
            daemon=True,
            name="TCPServerReactorThread",
        )
        self._reactor_thread.start()
        listen_done.wait()
        self._raise_if_listen_failed()

    def _raise_if_listen_failed(self) -> None:
        """Translate a captured bind failure into ServerAddressInUseError."""
        if self._listen_error is not None:
            err = self._listen_error
            self._listen_error = None
            # The reactor thread exits on its own when the bind fails (it never
            # calls reactor.run()), but join it so we don't leave a half-started
            # thread dangling behind the error.
            self._join_reactor_thread()
            raise ServerAddressInUseError(self.port) from err

    def _join_reactor_thread(self, timeout: float = 2.0) -> None:
        """Join and drop the reactor thread if it is no longer needed."""
        thread = self._reactor_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout)
        self._reactor_thread = None

    def stop(self) -> None:
        """
        Stop accepting connections and disconnect clients.

        Important:
            This does NOT stop the Twisted reactor.
            The reactor must stay alive if the server may be started again.
        """

        def _do() -> None:
            # Stop accepting new connections.
            if self._listening_port is not None:
                try:
                    self._listening_port.stopListening()
                finally:
                    self._listening_port = None

            # Disconnect existing clients.
            for proto in list(self._factory.peers.keys()):
                if proto.transport is not None:  # type: ignore
                    proto.transport.loseConnection()  # type: ignore

            self._factory.peers.clear()
            self._started = False

        if reactor.running:  # type: ignore
            reactor.callFromThread(_do)  # type: ignore

    def shutdown_reactor(self) -> None:
        """
        Final application shutdown only.

        Warning:
            Twisted's default reactor cannot be restarted after this.
        """

        def _do() -> None:
            if self._listening_port is not None:
                try:
                    self._listening_port.stopListening()
                finally:
                    self._listening_port = None

            for proto in list(self._factory.peers.keys()):
                if proto.transport is not None:  # type: ignore
                    proto.transport.loseConnection()  # type: ignore

            self._factory.peers.clear()
            self._started = False

            if reactor.running:  # type: ignore
                reactor.stop()  # type: ignore

        if reactor.running:  # type: ignore
            reactor.callFromThread(_do)  # type: ignore

    def broadcast(
        self, msg: Message, exclude: Optional[TransportServerProtocol] = None
    ) -> None:
        """To fulfill the interface, this is TCP 'broadcast'"""

        def _do() -> None:
            payload = encode_message(msg)
            for proto in list(self._factory.peers.keys()):
                if proto is exclude:
                    continue
                proto.sendString(payload)  # type: ignore

        if reactor.running:  # type: ignore
            reactor.callFromThread(_do)  # type: ignore

    def send_to(self, proto: TransportServerProtocol, msg: Message) -> None:
        """Send message"""

        def _do() -> None:
            if proto.transport is not None:  # type: ignore
                proto.send_message(msg)

        if reactor.running:  # type: ignore
            reactor.callFromThread(_do)  # type: ignore

    def disconnect(self, proto: TransportServerProtocol) -> None:
        """Disconnect"""

        def _do() -> None:
            if proto.transport is not None:  # type: ignore
                proto.transport.loseConnection()  # type: ignore

        if reactor.running:  # type: ignore
            reactor.callFromThread(_do)  # type: ignore
