import sys
import threading
from typing import Any
from twisted.python.failure import Failure
from twisted.internet import protocol, reactor, error
from twisted.protocols.basic import LineReceiver


class ChatClient(LineReceiver):
    def connectionMade(self) -> None:
        print("connected")

        t = threading.Thread(target=self._stdin_loop, daemon=True)
        t.start()

    def lineReceived(self, line: bytes) -> None:
        print("Server said:", line.decode("utf-8", errors="replace"))

    def connectionLost(
        self, reason: Failure = Failure(error.ConnectionDone())
    ) -> None:
        print("connection lost:", reason.getErrorMessage())

    def _stdin_loop(self) -> None:
        try:
            for raw in sys.stdin:
                msg = raw.rstrip("\r\n")
                if not msg:
                    continue
                data = msg.encode("utf-8", errors="replace")
                reactor.callFromThread(self.sendLine, data)
        finally:
            reactor.callFromThread(self.transport.loseConnection)
            reactor.callFromThread(reactor.stop)


class ChatFactory(protocol.ClientFactory):
    protocol = ChatClient

    def clientConnectionFailed(self, connector: Any, reason: Failure) -> None:
        print("Connection failed:", reason.getErrorMessage())
        reactor.stop()

    def clientConnectionLost(self, connector: Any, reason: Failure) -> None:
        print("Connection lost:", reason.getErrorMessage())
        reactor.stop()


class Client():
    def __init__(self, ip: str, port: int) -> None:
        reactor.connectTCP(ip, port, ChatFactory())
        reactor.run()
