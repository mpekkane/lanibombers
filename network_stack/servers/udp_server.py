"""
UDP server.
Handles server-side UPD traffic.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import threading
from twisted.internet import reactor
from twisted.internet.protocol import DatagramProtocol

from network_stack.messages.messages import (
    Message,
    encode_message,
    decode_message,
    Discover,
    Announce,
)
from network_stack.shared.types import PeerState
from network_stack.servers.transport_server import (
    TransportServer,
    TransportServerProtocol,
    OnReceive,
)


Addr = Tuple[str, int]


@dataclass(frozen=True)
class UDPPeer(TransportServerProtocol):
    """
    Wraps a UDP (ip, port) tuple so higher layers can treat it like a "protocol".
    """

    addr: Addr
    _server: "UDPServer"

    def send_message(self, msg: Message) -> None:
        self._server._send_to_addr(self.addr, msg)


class _UDPWire(DatagramProtocol):
    """
    Twisted DatagramProtocol doing the actual UDP IO.
    Delegates behavior to UDPServer.
    """

    def __init__(self, server: "UDPServer") -> None:
        self._server = server

    def startProtocol(self) -> None:
        # Enable UDP broadcast
        self.transport.setBroadcastAllowed(True)

        # Optional multicast join
        if self._server.multicast_group is not None:
            # joinGroup works for listenMulticast transports
            try:
                self.transport.joinGroup(
                    self._server.multicast_group, interface=self._server.interface
                )
            except Exception as e:
                print("UDP multicast join failed:", e)

    def datagramReceived(self, data: bytes, addr: Addr) -> None:
        self._server._datagram_received(data, addr)


class UDPServer(TransportServer):
    """
    UDP transport server.

    Two ways to "broadcast":
    - If exclude is None: send ONE datagram to broadcast/multicast address (true broadcast).
    - If exclude is provided: cannot exclude with true broadcast, so we unicast to known peers
      except the excluded peer.
    """

    def __init__(
        self,
        port: int,
        on_receive: OnReceive,
        *,
        interface: str = "0.0.0.0",
        broadcast_addr: str = "255.255.255.255",
        multicast_group: Optional[str] = None,  # e.g. "239.255.0.1"
        listen_multiple: bool = True,
    ) -> None:
        super().__init__(port, on_receive)
        self.interface = interface
        self.broadcast_addr = broadcast_addr
        self.multicast_group = multicast_group

        self._wire = _UDPWire(self)
        self._listening_port = None

        # Peer tracking
        self._peers_by_addr: Dict[Addr, UDPPeer] = {}
        self._state_by_peer: Dict[UDPPeer, PeerState] = {}

        # multicast params
        self._listen_multiple = listen_multiple

    def start(self) -> None:
        """Start the server"""
        def _listen():
            if self.multicast_group is not None:
                self._listening_port = reactor.listenMulticast(
                    self.port,
                    self._wire,
                    interface=self.interface,
                    listenMultiple=self._listen_multiple,
                )
            else:
                self._listening_port = reactor.listenUDP(
                    self.port,
                    self._wire,
                    interface=self.interface,
                )

        # If reactor is already running (likely, if TCP is running), schedule on reactor thread
        if reactor.running:
            reactor.callFromThread(_listen)
            return

        # Otherwise start reactor in background and bind inside it
        def _run():
            _listen()
            reactor.run(installSignalHandlers=False)

        self._reactor_thread = threading.Thread(target=_run, daemon=True)
        self._reactor_thread.start()

    def stop(self) -> None:
        """Stop the server"""
        if self._listening_port is not None:
            self._listening_port.stopListening()
            self._listening_port = None

    def _get_peer(self, addr: Addr) -> UDPPeer:
        """Get status of connected client"""
        peer = self._peers_by_addr.get(addr)
        if peer is None:
            peer = UDPPeer(addr=addr, _server=self)
            self._peers_by_addr[addr] = peer
            self._state_by_peer[peer] = PeerState()
        return peer

    def _datagram_received(self, data: bytes, addr: Addr) -> None:
        """Receive and marshall data"""
        try:
            msg = decode_message(data)
        except Exception as e:
            print("UDPServer decode error:", e)
            return

        if isinstance(msg, Discover):
            # reply unicast to sender addr
            reply = Announce(name="BomberLAN", port=self.port)
            self._wire.transport.write(encode_message(reply), addr)
            return

        peer = self._get_peer(addr)
        state = self._state_by_peer[peer]
        self._on_receive(msg, state, peer)

    def _send_to_addr(self, addr: Addr, msg: Message) -> None:
        """Send datagram"""
        payload = encode_message(msg)
        # DatagramProtocol transport is stored on wire
        self._wire.transport.write(payload, addr)

    def broadcast(
        self, msg: Message, exclude: Optional[TransportServerProtocol] = None
    ) -> None:
        """UDP Broadcasting"""
        payload = encode_message(msg)

        # If we can do true broadcast (no exclude), send ONE datagram to broadcast address.
        if exclude is None:
            # UDP broadcast
            self._wire.transport.write(payload, (self.broadcast_addr, self.port))

            # Optional multicast send too (if configured)
            if self.multicast_group is not None:
                self._wire.transport.write(payload, (self.multicast_group, self.port))
            return

        # If exclude is requested, true broadcast can't exclude.
        # Fall back to per-peer unicast to known peers.
        for peer in list(self._state_by_peer.keys()):
            if peer is exclude:
                continue
            self._wire.transport.write(payload, peer.addr)

    def send_to(self, proto: TransportServerProtocol, msg: Message) -> None:
        """Works for UDPPeer and any other TransportServerProtocol"""
        proto.send_message(msg)

    def disconnect(self, proto: TransportServerProtocol) -> None:
        """UDP has no connection to close. We can forget the peer state"""
        if isinstance(proto, UDPPeer):
            self._state_by_peer.pop(proto, None)
            self._peers_by_addr.pop(proto.addr, None)
