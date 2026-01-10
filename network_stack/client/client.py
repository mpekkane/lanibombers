from twisted.internet import protocol, reactor
from twisted.protocols.basic import LineReceiver

import sys
import threading


class ChatClient(LineReceiver):
    # IMPORTANT: don't override delimiter; default is b"\r\n"
    # delimiter = b"\r\n"

    def connectionMade(self):
        print("connected")

        t = threading.Thread(target=self._stdin_loop, daemon=True)
        t.start()

    def lineReceived(self, line: bytes):
        print("Server said:", line.decode("utf-8", errors="replace"))

    def connectionLost(self, reason):
        print("connection lost:", reason.getErrorMessage())

    def _stdin_loop(self):
        try:
            for raw in sys.stdin:
                msg = raw.rstrip("\r\n")
                if not msg:
                    continue
                data = msg.encode("utf-8", errors="replace")
                reactor.callFromThread(self.sendLine, data)  # adds \r\n
        finally:
            reactor.callFromThread(self.transport.loseConnection)
            reactor.callFromThread(reactor.stop)


class ChatFactory(protocol.ClientFactory):
    protocol = ChatClient

    def clientConnectionFailed(self, connector, reason):
        print("Connection failed:", reason.getErrorMessage())
        reactor.stop()

    def clientConnectionLost(self, connector, reason):
        print("Connection lost:", reason.getErrorMessage())
        reactor.stop()


class Client():
    def __init__(self) -> None:
        reactor.connectTCP("localhost", 8123, ChatFactory())
        reactor.run()

