import socket
import tempfile
import pytest
from security.ids.diagnostic_ipc import DiagnosticSender, encode, decode
from security.ids.observation_status import ObservationStatus


def body():
    return ObservationStatus().update(start_ms=0,end_ms=1000,frames=10,
                                     dropped=0,condition_mask=0)[0]


def test_local_socket_roundtrip_and_missing_receiver(tmp_path):
    directory=tempfile.TemporaryDirectory(prefix='cid-', dir='/tmp')
    path=directory.name+'/ids.sock'
    sender=DiagnosticSender(path)
    try:
        assert not sender.send(7,body())['accepted']
        with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as receiver:
            receiver.bind(path);receiver.settimeout(1)
            payload=body()
            assert sender.send(7,payload)['accepted']
            assert decode(receiver.recv(119))==(7,payload)
    finally:
        sender.close()
        directory.cleanup()


def test_other_diagnostic_roles_and_truncation_are_rejected():
    packet=encode(7,body())
    for invalid in (packet[:-1],packet+b'x',b'WRNG'+packet[4:],b'CID1'+bytes((1,52))+packet[6:]):
        with pytest.raises(ValueError):decode(invalid)
    with pytest.raises(ValueError):encode(3,bytes(40))


def test_submission_stamp_is_producer_observation_time_not_late_send_time():
    payload=body();packet=encode(7,payload,1234)
    assert packet[:4]==b'CID2' and int.from_bytes(packet[6:14],'big')==1234
    assert decode(packet)==(7,payload)
    for stamp in (-1,2**64,True,1.5):
        with pytest.raises(ValueError):encode(7,payload,stamp)
    with pytest.raises(ValueError):decode(b'CID1'+packet[4:6]+packet[14:])
