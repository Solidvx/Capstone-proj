import socket
import struct
from unittest.mock import Mock, patch

import pytest

from security.ids.runtime import SocketCan
from security.ids.runtime_detector import RuntimeDetector


def packet(seconds, nanos=0, flags=0, ancillary=True):
    return (struct.pack('=IB3x8s',0x102,8,bytes(8)),
            [(socket.SOL_SOCKET,64,struct.pack('=qq',seconds,nanos))] if ancillary else [], flags, None)


def transport(fake):
    with patch('security.ids.runtime.socket.socket',return_value=fake), \
         patch('security.ids.runtime.socket.AF_CAN',29,create=True), \
         patch('security.ids.runtime.socket.CAN_RAW',1,create=True), \
         patch('security.ids.runtime.time.monotonic',return_value=10), \
         patch('security.ids.runtime.time.monotonic_ns',return_value=10_000_000_000), \
         patch('security.ids.runtime.time.time_ns',return_value=1000_000_000_000):
        return SocketCan('test-only')


def test_delayed_processing_preserves_period_and_detects_real_short_period():
    fake=Mock(); bus=transport(fake)
    fake.recvmsg.side_effect=[packet(1000),packet(1000,100_000_000),packet(1000,110_000_000)]
    detector=RuntimeDetector(start_time=10)
    with patch.object(bus,'_check_clock'), patch('security.ids.runtime.time.monotonic',side_effect=[10.054,10.100,10.110]):
        frames=[bus.receive(),bus.receive(),bus.receive()]
    assert frames[1].t-frames[0].t == pytest.approx(.1)
    assert not any(e.reason=='PERIOD_TOO_SHORT' for f in frames[:2] for e in detector.observe(f))
    assert any(e.reason=='PERIOD_TOO_SHORT' for e in detector.observe(frames[2]))


def test_timeout_watermark_does_not_overtake_queued_frame():
    fake=Mock();bus=transport(fake)
    fake.recvmsg.side_effect=[socket.timeout(),packet(1000,51_000_000)]
    detector=RuntimeDetector(start_time=10)
    with patch.object(bus,'_check_clock'), patch('security.ids.runtime.time.monotonic',side_effect=[10,10.080]):
        assert bus.receive() is None
        detector.tick(bus.idle_time)
        detector.observe(bus.receive())
    assert detector.now==pytest.approx(10.051)


@pytest.mark.parametrize('value',[packet(1000,ancillary=False),packet(1000,flags=socket.MSG_CTRUNC),packet(1000,1_000_000_000)])
def test_bad_timestamp_fails_closed(value):
    fake=Mock();bus=transport(fake);fake.recvmsg.return_value=value
    with patch.object(bus,'_check_clock'),pytest.raises(ValueError):
        bus.receive()


def test_clock_step_fails_closed():
    bus=transport(Mock())
    with patch('security.ids.runtime.time.monotonic_ns',return_value=10_000_000_000), \
         patch('security.ids.runtime.time.time_ns',return_value=1001_000_000_000),pytest.raises(RuntimeError):
        bus._check_clock()


@pytest.mark.skipif(not hasattr(socket,'AF_CAN'),reason='Linux timestamp ABI')
def test_real_linux_timestamp_ancillary_abi_on_loopback_udp():
    # Actual kernel cmsg ABI check; this is not a SocketCAN hardware test.
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as receiver, socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sender:
        receiver.setsockopt(socket.SOL_SOCKET,64,1)
        receiver.bind(('127.0.0.1',0));receiver.settimeout(1)
        sender.sendto(b'timestamp-test',receiver.getsockname())
        data,ancillary,flags,_=receiver.recvmsg(64,socket.CMSG_SPACE(16))
        assert data==b'timestamp-test' and flags==0
        stamp=next(data for level,kind,data in ancillary if level==socket.SOL_SOCKET and kind==64)
        seconds,nanos=struct.unpack('=qq',stamp)
        assert seconds>0 and 0<=nanos<1_000_000_000


def test_clock_mapping_retries_preempted_sample_without_relaxing_step_guard():
    bus=transport(Mock())
    with patch('security.ids.runtime.time.monotonic_ns',side_effect=[10_000_000_000,10_020_000_000,10_030_000_000,10_030_000_000]), \
         patch('security.ids.runtime.time.time_ns',side_effect=[1000_000_000_000,1000_030_000_000]):
        bus._check_clock()
    with patch('security.ids.runtime.time.monotonic_ns',side_effect=[0,2_000_000,3_000_000,5_000_000,6_000_000,8_000_000]), \
         patch('security.ids.runtime.time.time_ns',return_value=0),pytest.raises(RuntimeError,match='uncertainty'):
        bus._check_clock()
