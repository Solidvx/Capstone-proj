from unittest.mock import patch

import pytest

from security.ids.runtime import OrderedSocketCan, SocketCan, ReceiveClockChanged
from security.ids.runtime_detector import Observation


def bus():
    def initialize(self, interface):
        self.start_time = self.idle_time = 0.
    with patch.object(SocketCan, '__init__', initialize):
        return OrderedSocketCan('test-only')


def frame(stamp, value=0):
    return Observation(stamp, 0x100, bytes([value])*8, 8)


def test_small_receive_inversion_is_ordered_without_changing_any_timestamp_or_bytes():
    transport = bus()
    later, earlier, boundary = frame(1.001, 1), frame(1.0009, 2), frame(1.004, 3)
    with patch.object(SocketCan, 'receive', side_effect=[later, earlier, boundary]):
        assert transport.receive() is earlier
        assert transport.receive() is later
    assert earlier.t == 1.0009 and later.t == 1.001
    assert transport.reordered_frames == 1
    assert len(transport._ordered) == 1


def test_equal_timestamps_keep_capture_order_and_pending_frames_drain_before_reading():
    transport = bus()
    first, second = frame(1., 1), frame(1., 2)
    with patch.object(SocketCan, 'receive', side_effect=[first, second, frame(1.002)]) as receive:
        assert transport.receive() is first
        assert transport.receive() is second
    assert receive.call_count == 3


def test_timeout_watermark_cannot_overtake_buffered_data():
    transport = bus()
    pending = frame(1.)
    def receive():
        transport.idle_time = 1.0005
        return None
    with patch.object(SocketCan, 'receive', side_effect=[pending, None]):
        transport.idle_time = 1.0005
        assert transport.receive() is None
    assert transport.idle_time < pending.t
    with patch.object(SocketCan, 'receive', side_effect=receive):
        assert transport.receive() is None
    assert transport.idle_time < pending.t
    with patch.object(SocketCan, 'receive', side_effect=lambda: setattr(transport, 'idle_time', 1.01)):
        assert transport.receive() is pending


def test_late_frame_outside_released_window_remains_an_epoch_fault_with_details():
    transport = bus()
    with patch.object(SocketCan, 'receive', side_effect=[frame(1.), frame(1.01), frame(.99)]):
        transport.receive()
        with pytest.raises(ReceiveClockChanged, match=r'received=.*watermark=.*can_id=256'):
            transport.receive()


def test_buffer_overflow_and_real_clock_step_are_not_hidden():
    transport = bus(); transport.ORDER_CAPACITY = 2
    with patch.object(SocketCan, 'receive', side_effect=[frame(1.), frame(1.), frame(1.)]):
        with pytest.raises(ReceiveClockChanged, match='capacity exhausted'):
            transport.receive()
    with patch.object(SocketCan, 'receive', side_effect=ReceiveClockChanged('mapping changed by more than 10ms')):
        with pytest.raises(ReceiveClockChanged, match='10ms'):
            transport.receive()
