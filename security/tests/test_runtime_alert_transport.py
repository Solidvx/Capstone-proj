import errno
import io
import json
from unittest.mock import Mock, patch

import pytest

from security.ids.runtime import main, send_alert
from security.ids.runtime_detector import Observation


@pytest.mark.parametrize('code', [errno.ENOBUFS, errno.EAGAIN])
def test_backpressure_is_logged_cooldown_applies_and_next_alert_recovers(code):
    bus = Mock()
    bus.send.side_effect = [OSError(code, 'test pressure'), None]
    output = io.StringIO()
    state = {}
    for t in (1.0, 1.01, 1.05, 1.11):
        send_alert(bus, bytes(8), t, state, output)
    rows = [json.loads(line) for line in output.getvalue().splitlines()]
    assert bus.send.call_count == 2
    assert [r['result'] for r in rows] == ['ALERT_TX_FAILED', 'ALERT_SENT']
    assert rows[0]['errno'] == code and rows[0]['retry'] is False


@pytest.mark.parametrize('code', [errno.ENETDOWN, errno.EBADF, errno.EIO])
def test_non_transient_errors_still_stop(code):
    bus = Mock()
    bus.send.side_effect = OSError(code, 'fatal')
    with pytest.raises(OSError):
        send_alert(bus, bytes(8), 1.0, {}, io.StringIO())


def test_live_detector_continues_receiving_after_alert_send_failure(tmp_path):
    bus = Mock(start_time=0.0, clock_offset_ns=0, rx_dropped=0)
    # Out-of-range BMS is a typed (alertable) event; a lone unknown ID is not.
    spoofed = bytes([201, 190, 0x10, 0x68, 0xFF, 0xEC, 65, 0])
    bus.receive.side_effect = [Observation(0.01, 0x100, spoofed, 8),
                               Observation(0.2, 0x100, spoofed, 8)]
    bus.send.side_effect = [OSError(errno.ENOBUFS, 'test pressure'), None]
    log = tmp_path / 'ids.jsonl'
    with patch('security.ids.runtime.OrderedSocketCan', return_value=bus), \
         patch('security.ids.runtime.time.monotonic', side_effect=[0, 0, .01, .2, 2]):
        result = main(['--interface', 'test-only', '--rules-only', '--send-alerts',
                       '--duration', '1', '--log', str(log)])
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert result == 0 and bus.receive.call_count == 2
    assert sum(r['result'] == 'ANOMALY' for r in rows) == 2
    assert sum(r['result'] == 'ALERT_TX_FAILED' for r in rows) == 1
    assert sum(r['result'] == 'ALERT_SENT' for r in rows) == 1
    assert rows[-1]['result'] == 'END'
    bus.close.assert_called_once()


def test_live_observation_records_actual_drop_health(tmp_path):
    bus = Mock(start_time=0.0, clock_offset_ns=0, rx_dropped=4)
    bus.receive.side_effect = [Observation(1.01, 0x200, bytes(8), 8)]
    log = tmp_path / 'observation.jsonl'
    with patch('security.ids.runtime.OrderedSocketCan', return_value=bus), \
         patch('security.ids.runtime.time.monotonic', side_effect=[0, 0, 0, 2]), \
         patch('security.ids.runtime.time.monotonic_ns', return_value=1_010_000_000):
        result = main(['--interface', 'test-only', '--rules-only',
                       '--duration', '1', '--log', str(log)])
    assert result == 0
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    record = next(row for row in rows if row.get('result') == 'OBSERVATION_STATUS')
    body = bytes.fromhex(record['body_hex'])
    assert record['delivery'] == 'local-log-only'
    assert body[16:18] == bytes((2, 1))
    assert int.from_bytes(body[40:44], 'big') == 4
    assert int.from_bytes(body[44:48], 'big') == 0


def test_diagnostic_send_failure_does_not_stop_live_observation(tmp_path):
    bus=Mock(start_time=0.0,clock_offset_ns=0,rx_dropped=0)
    bus.receive.side_effect=[Observation(1.01,0x200,bytes(8),8),
                             Observation(2.02,0x200,bytes(8),8)]
    sender=Mock()
    sender.send.side_effect=[{'accepted':False,'errno':errno.ENOBUFS},
                            {'accepted':True,'errno':None}]
    log=tmp_path/'ipc.jsonl'
    with patch('security.ids.runtime.OrderedSocketCan',return_value=bus), \
         patch('security.ids.runtime.DiagnosticSender',return_value=sender), \
         patch('security.ids.runtime.time.monotonic',side_effect=[0,0,0,0,4]):
        result=main(['--interface','test-only','--rules-only','--duration','3',
                     '--log',str(log),'--diagnostic-socket','/test-only/ids.sock'])
    assert result==0 and bus.receive.call_count==2
    assert [call.kwargs["observed_at_ms"] for call in sender.send.call_args_list]==[1010,2020]
    rows=[json.loads(line) for line in log.read_text().splitlines()]
    records=[row for row in rows if row.get('result')=='DIAGNOSTIC_IPC']
    assert [row['local_accepted'] for row in records]==[False,True]
    assert [row['timestamp'] for row in records]==[1.01,2.02]
    assert [row['body_hex'] for row in records]==[call.args[1].hex() for call in sender.send.call_args_list]
    assert all(row['can_delivery']=='unconfirmed' for row in records)
    sender.close.assert_called_once()


def test_clock_epoch_reopens_socket_and_records_unknown_coverage_without_exiting(tmp_path):
    from security.ids.runtime import ReceiveClockChanged
    first=Mock(start_time=0.0,clock_offset_ns=0,rx_dropped=4)
    first.receive.side_effect=ReceiveClockChanged('test clock step')
    replacement=Mock(start_time=1.01,idle_time=1.01,clock_offset_ns=1,rx_dropped=0)
    log=tmp_path/'epoch.jsonl'
    with patch('security.ids.runtime.OrderedSocketCan',side_effect=[first,replacement]), \
         patch('security.ids.runtime.time.monotonic',side_effect=[0,0,0,2]), \
         patch('security.ids.runtime.time.monotonic_ns',return_value=1_010_000_000):
        result=main(['--interface','test-only','--rules-only','--duration','1','--log',str(log)])
    assert result==0
    rows=[json.loads(line) for line in log.read_text().splitlines()]
    assert any(row.get('result')=='RECEIVE_EPOCH_RESET' for row in rows)
    body=bytes.fromhex(next(row['body_hex'] for row in rows if row.get('result')=='OBSERVATION_STATUS'))
    assert body[16:18]==bytes((2,3)) and body[40:44]==bytes.fromhex('ffffffff')
    assert not any(row.get('attack_type') for row in rows)
    first.close.assert_called_once();replacement.close.assert_called_once()
