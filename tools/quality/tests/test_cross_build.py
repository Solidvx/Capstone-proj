from pathlib import Path
import struct
import xml.etree.ElementTree as ET

import pytest

from tools.quality.cross_build import EXCLUDED, elf_machine, input_hashes, validate_results
from tools.quality.ctest_gate import EXPECTED


def test_arm64_and_host_elf_are_distinct_and_malformed_files_rejected(tmp_path):
    path = tmp_path/'public-dummy-elf'
    for machine in (62, 183):
        data = bytearray(20);data[:6] = b'\x7fELF\x02\x01'
        struct.pack_into('<H', data, 18, machine);path.write_bytes(data)
        assert elf_machine(path) == machine
    for data in (b'', b'not an ELF file', b'\x7fELF\x01\x01'+bytes(14)):
        path.write_bytes(data)
        with pytest.raises(ValueError):elf_machine(path)


def test_cross_profile_preserves_native_inventory_and_declares_all_nonemulated_tests():
    assert len(EXPECTED['ecu']) == 35 and len(EXPECTED['ivi']) == 21
    assert len(EXPECTED['ivi-integrated']) == 44
    assert len(EXPECTED['ecu']-EXCLUDED['ecu'].keys()) == 27
    assert len(EXPECTED['ivi']-EXCLUDED['ivi'].keys()) == 18
    for component in EXCLUDED:
        assert EXCLUDED[component].keys() <= EXPECTED[component]
        assert all(EXCLUDED[component].values())


@pytest.mark.parametrize('bad', ['skip', 'failure', 'error', 'missing', 'duplicate'])
def test_qemu_gate_rejects_incomplete_or_failed_results(bad):
    tree = ET.fromstring('<testsuite><testcase name="test_one"/></testsuite>')
    assert validate_results(tree, {'test_one'}) == 1
    if bad in ('skip', 'failure', 'error'):
        ET.SubElement(tree[0], 'skipped' if bad == 'skip' else bad)
    elif bad == 'missing':tree.remove(tree[0])
    else:ET.SubElement(tree, 'testcase', name='test_one')
    with pytest.raises(ValueError):validate_results(tree, {'test_one'})


def test_docker_context_excludes_source_credentials_and_logs():
    root = Path(__file__).resolve().parents[3]
    assert (root/'.dockerignore').read_text().splitlines() == ['**', '!Dockerfile.arm64']
    text = (root/'Dockerfile.arm64').read_text()
    assert not any(line.lstrip().startswith(('COPY ', 'ADD ')) for line in text.splitlines())
    assert 'qt6-base-dev-tools:amd64' in text and 'libssl-dev:arm64' in text


def test_cross_input_snapshot_detects_added_removed_and_changed_source(tmp_path):
    for name in ('Dockerfile.arm64', 'toolchain-aarch64.cmake', 'tools/quality/cross_build.py',
                 'tools/quality/ctest_gate.py', 'adaptive_ecu/CMakeLists.txt', 'ivi_platform/CMakeLists.txt'):
        path = tmp_path/name;path.parent.mkdir(parents=True, exist_ok=True);path.write_text('public fixture')
    before = input_hashes(tmp_path)
    new = tmp_path/'adaptive_ecu/new.cpp';new.write_text('new source')
    after = input_hashes(tmp_path);assert after != before
    new.write_text('changed source');assert input_hashes(tmp_path) != after
    new.unlink();assert input_hashes(tmp_path) == before
    vector=tmp_path/'common/testdata/physical-v1-vectors.tsv'
    vector.parent.mkdir(parents=True);vector.write_text('public physical contract vector')
    assert input_hashes(tmp_path) != before
