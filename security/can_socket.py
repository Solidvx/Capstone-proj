"""Small Classical SocketCAN adapter shared by security test tools.

The adapter never creates or reconfigures an interface.  Interface bitrate,
bus state and recovery policy remain an operator responsibility.
"""

from __future__ import annotations

from dataclasses import dataclass
import socket
import struct


CAN_EFF_FLAG = 0x80000000
CAN_RTR_FLAG = 0x40000000
CAN_ERR_FLAG = 0x20000000
CAN_EFF_MASK = 0x1FFFFFFF
CAN_SFF_MASK = 0x000007FF
_CAN_FRAME = struct.Struct("=IB3x8s")


@dataclass(frozen=True)
class CanFrame:
    can_id: int
    data: bytes
    extended: bool = False
    remote: bool = False
    error: bool = False

    @property
    def dlc(self) -> int:
        return len(self.data)


class SocketCanTransport:
    """Blocking Classical CAN transport with bounded receive timeouts."""

    def __init__(self, interface: str, timeout_s: float = 0.05,
                 track_rx_overflow: bool = False) -> None:
        if not hasattr(socket, "AF_CAN"):
            raise RuntimeError("SocketCAN requires Linux")
        self._socket = socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
        self.track_rx_overflow = track_rx_overflow
        self.rx_overflow = 0
        self._overflow_option = getattr(socket, "SO_RXQ_OVFL", 40)  # Linux UAPI
        try:
            if track_rx_overflow:
                self._socket.setsockopt(socket.SOL_SOCKET, self._overflow_option, 1)
            self._socket.bind((interface,))
            self._socket.settimeout(timeout_s)
        except Exception:
            self._socket.close()
            raise

    def send(self, can_id: int, data: bytes) -> None:
        if not 0 <= can_id <= CAN_SFF_MASK:
            raise ValueError("standard CAN ID must be in 0x000..0x7FF")
        if not 0 <= len(data) <= 8:
            raise ValueError("Classical CAN payload must contain at most 8 bytes")
        packed = _CAN_FRAME.pack(can_id, len(data), data.ljust(8, b"\x00"))
        if self._socket.send(packed) != len(packed):
            raise OSError("short CAN write")

    def receive(self) -> CanFrame | None:
        try:
            if self.track_rx_overflow:
                raw, ancillary, flags, _address = self._socket.recvmsg(
                    _CAN_FRAME.size, socket.CMSG_SPACE(4))
                if flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC):
                    raise OSError("truncated CAN frame/overflow metadata")
                for level, kind, data in ancillary:
                    if level == socket.SOL_SOCKET and kind == self._overflow_option:
                        if len(data) != 4:
                            raise OSError("invalid CAN overflow metadata")
                        self.rx_overflow = struct.unpack("=I", data)[0]
            else:
                raw = self._socket.recv(_CAN_FRAME.size)
        except socket.timeout:
            return None
        if len(raw) != _CAN_FRAME.size:
            raise OSError("short CAN read")
        raw_id, dlc, payload = _CAN_FRAME.unpack(raw)
        if dlc > 8:
            raise ValueError("invalid Classical CAN DLC")
        extended = bool(raw_id & CAN_EFF_FLAG)
        mask = CAN_EFF_MASK if extended else CAN_SFF_MASK
        return CanFrame(
            raw_id & mask,
            payload[:dlc],
            extended=extended,
            remote=bool(raw_id & CAN_RTR_FLAG),
            error=bool(raw_id & CAN_ERR_FLAG),
        )

    def close(self) -> None:
        self._socket.close()

    def __enter__(self) -> "SocketCanTransport":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
