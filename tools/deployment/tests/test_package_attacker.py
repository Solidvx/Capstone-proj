import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from tools.deployment.package_attacker import package

ROOT = Path(__file__).resolve().parents[3]


def test_isolated_archive_has_only_worker_dependencies(tmp_path):
    output = tmp_path / 'attacker.pyz'
    manifest = package(ROOT, output, 'a'*40)
    result = subprocess.run([sys.executable, '-I', str(output), '--help'], cwd=tmp_path,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert '--i-am-on-a-test-bus' in result.stdout
    with zipfile.ZipFile(output) as archive:
        assert set(archive.namelist()) == set(manifest['files_sha256'])
        for name, digest in manifest['files_sha256'].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest
        assert b'class RuntimeDetector' not in archive.read('security/ids/runtime_detector.py')
        assert b'def encode(' not in archive.read('security/can_diagnostic.py')
        assert not any('can_session' in n or 'test' in n or n.endswith('.md') for n in archive.namelist())
    # Import only from the generated archive, with site packages disabled.
    program = '''
import sys, json, random
sys.path.insert(0, sys.argv[1])
from security.experiments.can_attack_worker import injection_frames, physical_source
from security.ids.runtime_detector import Observation
from security.ids.startup_identity import source_digest
rows = json.loads(sys.argv[2])
frames = [(cid, bytes.fromhex(data)) for cid, data in rows]
source = physical_source([Observation(i*.001, cid, data) for i,(cid,data) in enumerate(frames)], True)
assert source == frames
assert injection_frames('replay', random.Random(1), 0, source, 'isolated-physical-v1') == source
assert injection_frames('spoofing', random.Random(1), 0, source, 'isolated-physical-v1') != source
assert injection_frames('flooding', random.Random(1), 0, None, 'isolated-physical-v1')[0][0] == 0
print(source_digest())
'''
    from security.tests.test_physical_diagnostic import body
    from security.tests.diagnostic_fixtures import fixtures
    from security.can_diagnostic import encode
    ctx, keys, _ = fixtures()
    frames = encode(keys, ctx, 0x302, 1, 9, bytes(body()))
    result = subprocess.run([sys.executable, '-I', '-S', '-c', program, str(output),
                             json.dumps([(cid, data.hex()) for cid, data in frames])],
                            cwd=tmp_path, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == manifest['archive_sha256']
    assert manifest['campaign_controller_included'] is False


def test_existing_archive_is_preserved(tmp_path):
    output = tmp_path / 'attacker.pyz'
    package(ROOT, output, 'a'*40)
    before = output.read_bytes()
    with pytest.raises(ValueError, match='new output'):
        package(ROOT, output, 'a'*40)
    assert output.read_bytes() == before


@pytest.mark.skipif(os.environ.get('ATTACKER_VCAN_TEST') != '1', reason='explicit local vcan test only')
def test_packaged_worker_sends_and_records_vcan(tmp_path):
    import select
    import time
    output = tmp_path / 'attacker.pyz'
    package(ROOT, output, 'a'*40)
    process = subprocess.Popen([sys.executable, '-I', str(output), '--interface', 'vcan0',
        '--environment', 'vcan', '--duration', '5', '--run-id', 'PACKAGE-VCAN',
        '--i-am-on-a-test-bus'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    rows = []
    pending = b''
    try:
        deadline = time.monotonic()+7
        while time.monotonic() < deadline:
            if not select.select([process.stdout], [], [], .1)[0]:
                continue
            chunk = os.read(process.stdout.fileno(), 65536)
            if not chunk:
                break
            pending += chunk
            while b'\n' in pending:
                line, pending = pending.split(b'\n', 1)
                row = json.loads(line)
                rows.append(row)
                if row['result'] == 'READY':
                    request = {'trial': 1, 'attack': 'flooding', 'rate': 10, 'duration': .2,
                        'seed': 1, 'interface': 'vcan0', 'secoc': True, 'profile': 'isolated-physical-v1'}
                    process.stdin.write((json.dumps(request)+'\n').encode())
                    process.stdin.flush()
                if row['result'] == 'ATTACK_DONE':
                    process.stdin.close()
            if any(r['result'] == 'ATTACK_DONE' for r in rows):
                break
        process.wait(timeout=5)
        assert process.returncode == 0, process.stderr.read().decode()
        done = [r for r in rows if r['result'] == 'ATTACK_DONE']
        assert len(done) == 1 and done[0]['sent'] > 0 and done[0]['tx_errors'] == 0
        assert any(r['result'] == 'ATTACK_RX' for r in rows)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
