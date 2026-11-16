"""Bounded ECU-local IDS diagnostic packet. Contains no keys or CAN MACs.

The receiving process must enforce peer credentials and source/tick freshness
before signing. A successful send means local socket acceptance only.
"""
import socket
import time
from security.can_diagnostic import valid_body

MAGIC = b'CID2'


def encode(kind, body, observed_at_ms=None):
    if kind not in (4, 7) or not isinstance(body, bytes) or not valid_body(0x302, kind, body):
        raise ValueError('only valid IDS incident/observation bodies may be submitted')
    if observed_at_ms is None:
        observed_at_ms = time.monotonic_ns() // 1_000_000
    if type(observed_at_ms) is not int or not 0 <= observed_at_ms < 2**64:
        raise ValueError('local monotonic observation time required')
    return MAGIC + bytes((kind, len(body))) + observed_at_ms.to_bytes(8, 'big') + body


def decode(packet):
    if not isinstance(packet, bytes) or len(packet) < 14 or len(packet) > 118:
        raise ValueError('invalid local diagnostic packet length')
    kind, length = packet[4:6]
    if packet[:4] != MAGIC or len(packet) != 14+length:
        raise ValueError('invalid local diagnostic packet header')
    body = packet[14:]
    encode(kind, body, int.from_bytes(packet[6:14], "big"))
    return kind, body


class DiagnosticSender:
    def __init__(self, path):
        if not isinstance(path, str) or not path.startswith('/') or '\0' in path:
            raise ValueError('absolute filesystem Unix socket path required')
        self.path = path
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.socket.setblocking(False)

    def send(self, kind, body, observed_at_ms=None):
        packet = encode(kind, body, observed_at_ms)
        try:
            count = self.socket.sendto(packet, self.path)
        except OSError as error:
            return {'accepted': False, 'errno': error.errno}
        return {'accepted': count == len(packet), 'errno': None}

    def close(self):
        self.socket.close()
