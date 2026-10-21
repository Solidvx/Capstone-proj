"""Regressions for the two experiment pipelines sharing the IDS runtime."""
import errno
import hashlib
import io
import json
from unittest.mock import Mock

import pytest

from security.ids.runtime import AlertThrottle, main, send_alert, train_model
from security.ids.runtime_detector import Event


def local_capture(root):
    root.mkdir()
    frames = root / 'frames.jsonl'
    frames.write_text(''.join(json.dumps({'t': i / 10, 'can_id': 0x100,
        'data': '96be1068ffec4100'}) + '\n' for i in range(41)), encoding='utf-8')
    manifest = {'status': 'COMPLETE', 'normal_attested': True, 'rx_dropped': 0,
                'error_frames': 0, 'duration_s': 4, 'sha256': hashlib.sha256(frames.read_bytes()).hexdigest()}
    (root / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    return frames


def test_cli_accepts_attested_capture_directory_and_keeps_run_id(tmp_path):
    frames = local_capture(tmp_path / 'training')
    replay = tmp_path / 'attack.jsonl'
    replay.write_text(json.dumps({'t': 0, 'can_id': 0x555, 'data': '00' * 8}) + '\n')
    log = tmp_path / 'events.jsonl'
    assert main(['--replay', str(replay), '--train-normal', str(frames),
                 '--run-id', 'integration-test', '--log', str(log)]) == 0
    records = [json.loads(line) for line in log.read_text().splitlines()]
    assert records[0]['run_id'] == 'integration-test'
    assert records[0]['mode'] == 'rules+if'
    assert any(row.get('reason') == 'UNKNOWN_ID' for row in records)


def test_cli_rejects_changed_capture_before_creating_log(tmp_path):
    frames = local_capture(tmp_path / 'training')
    frames.write_text(frames.read_text() + '\n')
    log = tmp_path / 'events.jsonl'
    assert main(['--replay', str(frames), '--train-normal', str(frames), '--log', str(log)]) == 2
    assert not log.exists()


def test_explicit_manifest_is_validated_before_fitting(tmp_path):
    frames = local_capture(tmp_path / 'training')
    bad = tmp_path / 'normal.manifest.json'
    bad.write_text(json.dumps({'schema': 'ids-normal-v2', 'status': 'COMPLETE',
                              'rejected_frames': 0, 'capture_sha256': 'invalid'}))
    with pytest.raises(ValueError, match='hash differs'):
        train_model(frames, manifest_path=bad)


def test_fair_queue_keeps_other_types_after_backpressure_without_retry():
    queue = AlertThrottle()
    output, attempts, bus = io.StringIO(), {}, Mock()
    bus.send.side_effect = [OSError(errno.ENOBUFS, 'test pressure'), None]
    queue.offer(Event(0, 0x555, 'UNKNOWN_ID', 1))
    queue.offer(Event(.01, 0x100, 'FRAME_RATE', 4))
    for now in (0, .11):
        event = queue.pop_ready(now)
        send_alert(bus, event.alert_payload(1), now, attempts, output,
                   run_id='integration-test', event=event)
    rows = [json.loads(line) for line in output.getvalue().splitlines()]
    assert [row['result'] for row in rows] == ['ALERT_TX_FAILED', 'ALERT_SENT']
    assert [row['attack_type'] for row in rows] == [1, 4]
    assert all(row['run_id'] == 'integration-test' for row in rows)
    assert rows[0]['retry'] is False
    assert queue.pop_ready(.22) is None
