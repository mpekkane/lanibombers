from __future__ import annotations
from typing import Dict
from twisted.internet.protocol import Factory
from twisted.internet import reactor, error
from twisted.internet.interfaces import IAddress
from twisted.protocols.basic import LineReceiver
from twisted.python.failure import Failure


class Chat(LineReceiver):
    def __init__(self, users: Dict[bytes, Chat]):
        self.users = users
        self.name: bytes = bytes()
        self.state = "GETNAME"

    def connectionMade(self) -> None:
        print("new user connected")
        self.sendLine(b"What's your name XD?")

    def connectionLost(self, reason: Failure = Failure(error.ConnectionDone())) -> None:
        if self.name in self.users:
            print(f"{self.name.decode('utf-8')} disconnected")
            del self.users[self.name]
        else:
            print("unknown disconnected")
        self.print_users()

    def lineReceived(self, line: bytes) -> None:
        if self.state == "GETNAME":
            self.handle_GETNAME(line)
        else:
            self.handle_CHAT(line)

    def handle_GETNAME(self, name: bytes) -> None:
        if name in self.users:
            self.sendLine(b"Name taken, please choose another.")
            return
        self.sendLine(f"Welcome, {name.decode('utf-8')}!".encode("utf-8"))
        self.name = name
        self.users[name] = self
        self.state = "CHAT"
        self.print_users()

    def handle_CHAT(self, message: bytes) -> None:
        message = b"<" + self.name + b"> " + message
        for _, protocol in self.users.items():
            if protocol != self:
                protocol.sendLine(message)

    def print_users(self) -> None:
        if len(self.users) > 0:
            print("users:")
            i = 1
            for name, _ in self.users.items():
                print(f"{i}: {name.decode('utf-8')}")
                i += 1
        else:
            print("no users")


class ChatFactory(Factory):
    def __init__(self) -> None:
        self.users: Dict[bytes, Chat] = {}

    def buildProtocol(self, addr: IAddress) -> Chat:
        return Chat(self.users)


class Server():
    def __init__(self, port: int) -> None:
        print(f"Starting server on port {port}")
        reactor.listenTCP(port, ChatFactory())
        reactor.run()
