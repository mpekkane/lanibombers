# network_stack/servers/tcp_server.py
from __future__ import annotations
from typing import Dict, Optional, Callable
import threading

from twisted.internet.protocol import Factory
from twisted.internet import reactor, error
from twisted.protocols.basic import Int32StringReceiver
from twisted.python.failure import Failure

from network_stack.messages.messages import Message, encode_message, decode_message
from network_stack.shared.types import PeerState

OnReceive = Callable[[Message, PeerState, "TCPServerProtocol"], None]


class TCPServerProtocol(Int32StringReceiver):
    def __init__(
        self, peers: Dict["TCPServerProtocol", PeerState], on_receive: OnReceive
    ) -> None:
        self._peers = peers
        self._state = PeerState()
        self._on_receive = on_receive

    def connectionMade(self) -> None:
        self._peers[self] = self._state

    def connectionLost(self, reason: Failure = Failure(error.ConnectionDone())) -> None:
        self._peers.pop(self, None)

    def stringReceived(self, string: bytes) -> None:
        try:
            msg = decode_message(string)
        except Exception as e:
            print("TCPServerProto: Decode error:", e)
            return
        self._on_receive(msg, self._state, self)

    def send_message(self, msg: Message) -> None:
        self.sendString(encode_message(msg))  # type: ignore


class TCPServerFactory(Factory):
    def __init__(self, on_receive: OnReceive) -> None:
        self._peers: Dict[TCPServerProtocol, PeerState] = {}
        self._on_receive = on_receive

    def buildProtocol(self, addr: str):
        return TCPServerProtocol(self._peers, self._on_receive)

    @property
    def peers(self) -> Dict[TCPServerProtocol, PeerState]:
        return self._peers


class TCPServer:
    def __init__(self, port: int, on_receive: OnReceive) -> None:
        self.port = port
        self._factory = TCPServerFactory(on_receive=on_receive)
        self._reactor_thread: Optional[threading.Thread] = None
        self._listening_port = None  # Twisted IListeningPort

    def start(self) -> None:
        def _run():
            self._listening_port = reactor.listenTCP(  # type: ignore
                self.port, self._factory, interface="0.0.0.0"
            )
            reactor.run(installSignalHandlers=False)  # type: ignore

        self._reactor_thread = threading.Thread(target=_run, daemon=True)
        self._reactor_thread.start()

    def stop(self) -> None:
        # thread-safe stop
        def _do():
            try:
                if self._listening_port is not None:
                    self._listening_port.stopListening()
            finally:
                if reactor.running:  # type: ignore
                    reactor.stop()  # type: ignore

        reactor.callFromThread(_do)  # type: ignore

    def broadcast(
        self, msg: Message, exclude: Optional[TCPServerProtocol] = None
    ) -> None:
        def _do():
            payload = encode_message(msg)
            for proto in list(self._factory.peers.keys()):
                if proto is exclude:
                    continue
                proto.sendString(payload)  # type: ignore

        reactor.callFromThread(_do)  # type: ignore

    def send_to(self, proto: TCPServerProtocol, msg: Message) -> None:
        def _do():
            if proto.transport is not None:  # type: ignore
                proto.send_message(msg)

        reactor.callFromThread(_do)  # type: ignore

    def disconnect(self, proto: TCPServerProtocol) -> None:
        def _do():
            if proto.transport is not None:  # type: ignore
                proto.transport.loseConnection()  # type: ignore

        reactor.callFromThread(_do)  # type: ignore
