"""Read-only ECU artifact/process identity, paired with IVI authenticated health.

Run locally on Node A. This alone does not prove fresh BMS delivery. No key is
opened; pair its instance with Node B's fresh health over the management path.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.deployment.health import private_file, process_identity


def bind(health, identity):
    for value in (health.get('artifact_sha256'), identity.get('artifact_sha256')):
        if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):raise ValueError('missing paired artifact identity')
    instance = identity.get('instance_id')
    if not isinstance(instance, str) or not re.fullmatch('[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{15}', instance):
        raise ValueError('missing paired ECU instance')
    if (health.get('status') != 'PASS' or identity.get('status') != 'IDENTIFIED' or
            health.get('ecu_instance_id') != identity.get('instance_id') or
            not isinstance(health.get('interface'), str) or not health['interface'] or
            not isinstance(identity.get('interface'), str) or not identity['interface']):
        raise ValueError('ECU executable/process is not the authenticated IVI peer')
    return {'status': 'PASS', 'ecu_instance_id': identity['instance_id'],
            'ecu_artifact_sha256': identity['artifact_sha256'],
            'ivi_artifact_sha256': health['artifact_sha256'],
            'local_interfaces': {'ecu': identity['interface'], 'ivi': health['interface']},
            'scope': 'Explicit ECU process identity matches a fresh IVI authenticated peer check; no cross-host clock subtraction.'}


def check(pid, expected_sha256, stdout, max_bytes):
    if type(pid) is not int or pid <= 0 or not re.fullmatch('[0-9a-f]{64}', expected_sha256):
        raise ValueError('explicit ECU PID/hash required')
    if type(max_bytes) is not int or not 1024 <= max_bytes <= 64*1024*1024:
        raise ValueError('explicit bounded ECU log budget required')
    folder, start, uid = process_identity(pid)
    actual = hashlib.sha256((folder/'exe').read_bytes()).hexdigest()
    if actual != expected_sha256:raise ValueError('running ECU artifact hash mismatch')
    argv = (folder/'cmdline').read_bytes().split(b'\0')
    def argument(name):
        token = name.encode()
        if argv.count(token) != 1 or argv.index(token)+1 >= len(argv):raise ValueError('missing explicit ECU option')
        return os.fsdecode(argv[argv.index(token)+1])
    if argument('--protocol') != 'session-v2' or argument('--secoc') != 'on':
        raise ValueError('protected explicit ECU protocol required')
    interface = argument('--interface')
    fd_info = dict(line.split(':', 1) for line in (folder/'fdinfo/1').read_text().splitlines())
    if int(fd_info['flags'].strip(), 8) & os.O_APPEND:raise ValueError('fresh non-append ECU output required')
    position = int(fd_info['pos'].strip())
    with os.fdopen(private_file(stdout, uid), 'rb') as stream:
        info = os.fstat(stream.fileno());opened = (folder/'fd/1').stat()
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):raise ValueError('output is not this ECU stdout')
        if not 0 < position <= info.st_size <= max_bytes:raise ValueError('ECU stdout exceeds budget or is not ready')
        data = stream.read(position)
    if not data.endswith(b'\n'):raise ValueError('incomplete ECU output; retry')
    records = []
    for line in data.splitlines():
        if not line.startswith(b'{'):continue
        row = json.loads(line)
        if isinstance(row, dict) and row.get('result') == 'ECU_INPUT_LINEAGE':records.append(row)
    if len(records) != 1 or records[0].get('schema') != 'ecu-input-lineage-v1':
        raise ValueError('unique ECU startup identity missing')
    instance = records[0].get('instance_id')
    if not isinstance(instance, str) or not re.fullmatch('[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{15}', instance):
        raise ValueError('invalid ECU process instance')
    if process_identity(pid)[1] != start:raise ValueError('ECU process changed during identity check')
    return {'status': 'IDENTIFIED', 'pid': pid, 'process_start_ticks': start,
            'artifact_sha256': actual, 'instance_id': instance, 'interface': interface,
            'scope': 'Executable and process-owned startup identity only; requires fresh IVI peer binding.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--stdout', type=Path, required=True)
    parser.add_argument('--max-bytes', type=int, required=True)
    args = parser.parse_args()
    try:result = check(args.pid, args.expected_sha256, args.stdout, args.max_bytes)
    except (OSError, ValueError, KeyError) as error:result = {'status': 'FAIL', 'reason': str(error)}
    print(json.dumps(result));return 0 if result['status'] == 'IDENTIFIED' else 1


if __name__ == '__main__':raise SystemExit(main())
