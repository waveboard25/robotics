"""UDP broadcast transport layer."""

from __future__ import annotations

import socket
from typing import Optional

from communication.protocol import Message
from meshfleet.constants import BROADCAST_PORT


class UDPTransport:
    def __init__(self, port: int = BROADCAST_PORT, bind_port: Optional[int] = None):
        self.port = port
        self.bind_port = bind_port or port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.bind(("", self.bind_port))
        self.sock.setblocking(False)

    def send(self, message: Message, redundant: int = 1) -> None:
        data = message.to_json().encode("utf-8")
        for _ in range(redundant):
            self.sock.sendto(data, ("<broadcast>", self.port))

    def recv_all(self) -> list[Message]:
        messages: list[Message] = []
        while True:
            try:
                data, _ = self.sock.recvfrom(65535)
                messages.append(Message.from_json(data.decode("utf-8")))
            except BlockingIOError:
                break
            except (OSError, ValueError, KeyError):
                break
        return messages

    def close(self) -> None:
        self.sock.close()
