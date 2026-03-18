# renderer/lanibombers_window.py
import arcade

from game_engine.client_simulation import ClientSimulation
from network_stack.bomber_network_client import BomberNetworkClient
from network_stack.messages.messages import GameState

WINDOW_WIDTH = 1708
WINDOW_HEIGHT = 960
WINDOW_TITLE = "lanibombers"

# Path to the client network config (provides protocol, timeout, etc.)
_CLIENT_CFG_PATH = "cfg/client_config.yaml"


def _parse_color(color_str) -> tuple:
    """Convert hex color string '#FF0091' to RGB tuple (255, 0, 145)."""
    if not color_str or not isinstance(color_str, str):
        return (255, 255, 255)
    color_str = color_str.lstrip("#")
    if len(color_str) != 6:
        return (255, 255, 255)
    return (int(color_str[0:2], 16), int(color_str[2:4], 16), int(color_str[4:6], 16))


class LanibombersWindow(arcade.Window):
    """Single window for the entire client. Views handle all screens."""

    def __init__(self):
        super().__init__(WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_TITLE, vsync=True)
        self.player_config: dict | None = None
        self.client_config: dict | None = None
        self.network_client: BomberNetworkClient | None = None
        self.client_simulation: ClientSimulation | None = None

    def connect(self, host: str, port: int, player_config: dict) -> None:
        """Create and start a BomberNetworkClient for the given server.

        Args:
            host: Server IP address returned by UDPScanner.scan().
            port: Server port returned by UDPScanner.scan().
            player_config: Raw dict loaded from player.yaml (keys: player_name,
                           color, appearance_id, …).
        """
        # 1. Create client from the network config file (provides protocol, etc.),
        #    then override server address with the one found by the scanner.
        client = BomberNetworkClient(_CLIENT_CFG_PATH)
        client.server_ip = host
        client.server_port = port
        client.acquired_server = True

        # 2. Create simulation early so the callback can be registered before
        #    start() opens the socket.
        simulation = ClientSimulation(sound_engine=None)

        # 3. Register the GameState callback.
        def _on_game_state(msg: GameState) -> None:
            simulation.receive_state(msg.to_render())

        client.set_callback(GameState, _on_game_state)

        # 4. Open the connection.
        client.start()

        # set_name() is called by the view once client.connected becomes True
        # (the TCP handshake completes asynchronously after start() returns).

        self.network_client = client
        self.client_simulation = simulation
        self.player_config = player_config

    def disconnect(self) -> None:
        """Stop the network client and clear connection state."""
        if self.network_client is not None:
            # BomberNetworkClient has no stop(); try the underlying transport.
            client = self.network_client
            transport = getattr(client, "client", None)
            if transport is not None and hasattr(transport, "stop"):
                transport.stop()
            self.network_client = None
        self.client_simulation = None
