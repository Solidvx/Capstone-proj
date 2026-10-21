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
    bus = Mock(start_time=0.0, clock_offset_ns=0)
    bus.receive.side_effect = [Observation(0.01, 0x555, bytes(8), 8),
                               Observation(0.2, 0x555, bytes(8), 8)]
    bus.send.side_effect = [OSError(errno.ENOBUFS, 'test pressure'), None]
    log = tmp_path / 'ids.jsonl'
    with patch('security.ids.runtime.SocketCan', return_value=bus), \
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
