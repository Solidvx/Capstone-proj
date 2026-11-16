import socket
import struct
import pytest
from security.ids.runtime import SocketCan


def receiver():
    result = SocketCan.__new__(SocketCan)
    result.rx_dropped = 0
    result._drop_counter = 0
    return result


def ancillary(value):
    return [(socket.SOL_SOCKET, SocketCan.RXQ_OVFL, struct.pack('=I', value))]


def test_cumulative_counter_is_not_double_counted_and_wraps():
    rx = receiver()
    rx._record_drops(ancillary(5))
    rx._record_drops(ancillary(5))
    rx._record_drops([])
    assert rx.rx_dropped == 5
    rx._drop_counter = 0xFFFFFFFE
    rx._record_drops(ancillary(2))
    assert rx.rx_dropped == 9


def test_invalid_counter_does_not_mutate_measurement():
    rx = receiver()
    for bad in [ancillary(2)*2, [(socket.SOL_SOCKET, SocketCan.RXQ_OVFL, b'x')]]:
        with pytest.raises(ValueError):
            rx._record_drops(bad)
    assert rx.rx_dropped == 0
