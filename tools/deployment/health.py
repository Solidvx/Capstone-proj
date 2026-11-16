"""Read-only IVI deployment health: exact live executable and fresh verified CAN.

Uses the receiver's private, open observation file; never opens a SecOC key.
Battery WARNING/CRITICAL/SHUTDOWN are reported, not reset or treated as crashes.
All freshness and read budgets are explicit deployment inputs, not defaults.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from security.can_diagnostic import valid_body


def number(value):
    if not isinstance(value, str) or not re.fullmatch('0|[1-9][0-9]*', value) or int(value) >= 2**64:
        raise ValueError('noncanonical health counter')
    return int(value)


def evaluate(rows, run_id, now_ns, max_age_ms):
    if type(now_ns) is not int or now_ns < 0 or type(max_age_ms) is not int or not 0 < max_age_ms < 2**31:
        raise ValueError('explicit positive health freshness required')
    publications = [r for r in rows if r.get('result') == 'SESSION_PUBLICATION']
    if not publications:raise ValueError('no authenticated publication')
    p = publications[-1]
    if p.get('run_id') != run_id or any(p.get(k) is not True for k in
            ('valid', 'secoc_verified', 'state_confirmed', 'protection_confirmed')) or p.get('stale') is not False:
        raise ValueError('receiver publication is not current authenticated state')
    t1, t2 = number(p.get('t1_received_ns')), number(p.get('t2_published_ns'))
    if not 0 < t1 <= t2 <= now_ns or now_ns-t1 > max_age_ms*1_000_000:
        raise ValueError('stale, future or unordered publication')
    session = p.get('session_id')
    if not isinstance(session, str) or not re.fullmatch('[0-9a-f]{32}', session):
        raise ValueError('current session identity missing')
    messages = {}
    for row in rows:
        if row.get('result') != 'AUTHENTICATED_DIAGNOSTIC' or row.get('kind') not in (1, 8):continue
        kind = row['kind']
        if type(kind) is not int:raise ValueError('invalid diagnostic kind')
        if row.get('session_id') != session:continue
        sequence = number(row.get('sequence'))
        if sequence > 0xFFFFFFFF:raise ValueError('invalid diagnostic sequence')
        # A late lower-sequence message must not replace the current report.
        if kind in messages and sequence <= number(messages[kind]['sequence']):continue
        messages[kind] = row
    bodies = {}
    for kind in (1, 8):
        row = messages.get(kind)
        if row is None:raise ValueError('missing current process/protection diagnostic')
        raw = row.get('body_hex')
        if not isinstance(raw, str) or not re.fullmatch('[0-9a-f]{112}', raw):
            raise ValueError('invalid health diagnostic body')
        body = bytes.fromhex(raw)
        if not valid_body(0x302, kind, body):raise ValueError('unreviewed diagnostic state')
        received, verified = number(row.get('received_monotonic_ms')), number(row.get('verified_monotonic_ms'))
        if not 0 < received <= verified <= now_ns//1_000_000 or now_ns//1_000_000-received > max_age_ms:
            raise ValueError('stale or future process/protection report')
        bodies[kind] = body
    node, protection = bodies[1], bodies[8]
    if any(type(p.get(k)) is not int for k in ('battery_state', 'battery_reason')):
        raise ValueError('invalid current battery state type')
    if node[32] != 2 or node[34] != 2 or node[53] != 1:
        raise ValueError('ECU is not running with ready input')
    if (node[:16] != protection[:16] or node[35] != protection[48] or
            node[37] != protection[49] or p.get('battery_state') != node[35] or p.get('battery_reason') != node[37]):
        raise ValueError('process/protection/current state mismatch')
    if protection[51] & 1 and (node[33] != 2 or not node[52] or not node[54]):
        raise ValueError('unverified restored process state')
    return {'status': 'PASS', 'run_id': run_id, 'session_id': session,
            'ecu_instance_id': node[:16].hex(), 'battery_state': node[35], 'battery_reason': node[37],
            'measurement_sequence': number(p.get('measurement_sequence')),
            'publication_age_ms': (now_ns-t1)/1_000_000,
            'scope': 'Verified receiver process and fresh authenticated data; battery protection is preserved, not reset.'}


def private_file(path, uid):
    parent = path.parent.stat()
    if parent.st_uid != uid or parent.st_mode & 0o077:
        raise ValueError('private process-owned evidence directory required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != uid or info.st_mode & 0o022:
        os.close(fd);raise ValueError('evidence ownership/type rejected')
    return fd


def process_identity(pid):
    folder = Path('/proc')/str(pid)
    data = (folder/'stat').read_text()
    fields = data.rpartition(') ')[2].split()
    if len(fields) < 20 or fields[0] in ('Z', 'X'):
        raise ValueError('process is not live')
    return folder, fields[19], folder.stat().st_uid


def check(pid, expected_sha256, ready, observations, run_id, max_age_ms, max_bytes):
    if type(pid) is not int or pid <= 0 or not re.fullmatch('[0-9a-f]{64}', expected_sha256):
        raise ValueError('explicit live PID and expected artifact hash required')
    if type(max_bytes) is not int or not 1024 <= max_bytes <= 64*1024*1024:
        raise ValueError('explicit bounded health read budget required')
    folder, start, uid = process_identity(pid)
    actual = hashlib.sha256((folder/'exe').read_bytes()).hexdigest()
    if actual != expected_sha256:raise ValueError('running artifact hash mismatch')
    argv = (folder/'cmdline').read_bytes().split(b'\0')
    def argument(name):
        token = name.encode()
        if argv.count(token) != 1 or argv.index(token)+1 >= len(argv):raise ValueError('missing process evidence option')
        return os.fsdecode(argv[argv.index(token)+1])
    if (argument('--protocol') != 'session-v2' or argument('--run-id') != run_id or
        Path(argument('--ready-file')).resolve() != ready.resolve() or
        Path(argument('--observation-jsonl')).resolve() != observations.resolve() or
        b'--experiment-secoc-off' in argv):
        raise ValueError('process protocol or evidence binding differs')
    with os.fdopen(private_file(ready, uid), 'rb') as stream:
        data = stream.read(4097)
    if len(data) > 4096:raise ValueError('ready evidence too large')
    ready_record = json.loads(data)
    if ready_record != {'result': 'READY', 'run_id': run_id, 'secoc_on': True}:
        raise ValueError('protected receiver readiness unavailable')
    with os.fdopen(private_file(observations, uid), 'rb') as stream:
        info = os.fstat(stream.fileno())
        descriptors = list((folder/'fd').iterdir())
        if len(descriptors) > 4096:raise ValueError('process descriptor limit exceeded')
        bound = False
        for descriptor in descriptors:
            try:opened = descriptor.stat()
            except OSError:continue
            if (opened.st_dev, opened.st_ino) == (info.st_dev, info.st_ino):bound = True
        if not bound:raise ValueError('observation file is not open in this receiver')
        offset = max(0, info.st_size-max_bytes);stream.seek(offset)
        data = stream.read(min(max_bytes, info.st_size-offset))
    if offset:
        cut = data.find(b'\n')
        if cut < 0:raise ValueError('health evidence line exceeds budget')
        data = data[cut+1:]
    if data and not data.endswith(b'\n'):raise ValueError('incomplete live observation tail; retry')
    rows = []
    for line in data.splitlines():
        if len(line) > 65536:raise ValueError('oversized observation row')
        row = json.loads(line)
        if not isinstance(row, dict):raise ValueError('invalid observation row')
        rows.append(row)
    result = evaluate(rows, run_id, time.monotonic_ns(), max_age_ms)
    if process_identity(pid)[1] != start:raise ValueError('receiver changed during health check')
    result.update(pid=pid, process_start_ticks=start, artifact_sha256=actual,
                  bytes_read=len(data), truncated_prefix=bool(offset), interface=argument('--interface'))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument('--pid', type=int);target.add_argument('--service')
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--ready', required=True, type=Path)
    parser.add_argument('--observations', required=True, type=Path)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--max-age-ms', required=True, type=int)
    parser.add_argument('--max-bytes', required=True, type=int)
    args = parser.parse_args()
    try:
        pid = args.pid
        if args.service:
            if not re.fullmatch(r'[A-Za-z0-9_.@:-]+\.service', args.service):raise ValueError('explicit service name required')
            text = subprocess.check_output(['systemctl', 'show', '--no-pager', '-p', 'MainPID', '-p', 'ActiveState', '-p', 'SubState', '--', args.service], text=True, timeout=5)
            properties = dict(line.split('=', 1) for line in text.splitlines())
            if properties.get('ActiveState') != 'active' or properties.get('SubState') != 'running':
                raise ValueError('service is not active/running')
            pid = int(properties['MainPID'])
        result = check(pid, args.expected_sha256, args.ready, args.observations,
                       args.run_id, args.max_age_ms, args.max_bytes)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        result = {'status': 'FAIL', 'reason': str(error)}
    print(json.dumps(result))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
