from enum import IntEnum


class ServerState(IntEnum):
    STARTING = 1
    LOBBY = 2
    SHOP = 3
    GAME = 4
    END = 5

    def running(self) -> bool:
        return int(self) > 3


class ServerStateMachine:
    def __init__(self) -> None:
        self.state = ServerState.STARTING

    # TODO: ending condition, now just test control flow
    def update(self, quit: bool = False) -> ServerState:
        if self.state == ServerState.STARTING:
            self.state = ServerState.LOBBY
        elif self.state == ServerState.LOBBY:
            self.state = ServerState.GAME  # FIXME:
        elif self.state == ServerState.SHOP:
            self.state = ServerState.GAME
        elif self.state == ServerState.GAME:
            if quit:
                self.state = ServerState.END
            else:
                self.state = ServerState.SHOP
        return self.state

    def get_state(self) -> ServerState:
        return self.state


class ClientStateAction(IntEnum):
    NONE = -1
    INFO = 1
    SETUP = 2
    CONNECT = 3
    END = 4
    QUIT = 100


class ClientState(IntEnum):
    STARTING = 10
    MENU = 20
    SETUP = 21
    INFO = 22
    CONNECT = 23
    LOBBY = 30
    SHOP = 40
    GAME = 50
    ENDING = 60
    QUIT = 70

    def running(self) -> bool:
        return int(self) > 3


class ClientStateMachine:
    def __init__(self) -> None:
        self.state = ClientState.STARTING

    # TODO: ending condition, now just test control flow
    def update(self, action: ClientStateAction = ClientStateAction.NONE) -> ClientState:
        if self.state == ClientState.STARTING:
            self.state = ClientState.MENU
        elif self.state == ClientState.MENU:
            if action == ClientStateAction.INFO:
                self.state = ClientState.INFO
            elif action == ClientStateAction.SETUP:
                self.state = ClientState.SETUP
            elif action == ClientStateAction.CONNECT:
                self.state = ClientState.CONNECT
            else:
                self.state = ClientState.MENU
        elif self.state == ClientState.INFO:
            self.state = ClientState.MENU
        elif self.state == ClientState.SETUP:
            self.state = ClientState.MENU
        elif self.state == ClientState.CONNECT:
            self.state = ClientState.GAME  # FIXME:
        elif self.state == ClientState.GAME:
            if action == ClientStateAction.END:
                self.state = ClientState.ENDING
            else:
                self.state = ClientState.SHOP
        elif self.state == ClientState.ENDING:
            self.state = ClientState.QUIT
        elif self.state == ClientState.QUIT:
            self.state = ClientState.QUIT
        return self.state

    def get_state(self) -> ClientState:
        return self.state
