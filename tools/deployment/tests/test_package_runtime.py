"""Public dummy ARM64 ELF; no hardware, services or actual private keys."""
import hashlib
import json
from pathlib import Path
import tarfile

import pytest

from tools.deployment.package_runtime import host_target, package

TARGET = {'os': 'debian', 'version': '13', 'architecture': 'aarch64'}


def test_host_target_rejects_wrong_runtime_environment(monkeypatch):
    monkeypatch.setattr('platform.machine', lambda: 'aarch64')
    monkeypatch.setattr('platform.freedesktop_os_release', lambda: {'ID': 'ubuntu', 'VERSION_ID': '26.04'})
    with pytest.raises(ValueError, match='Debian13'):
        host_target()
    monkeypatch.setattr('platform.freedesktop_os_release', lambda: {'ID': 'debian', 'VERSION_ID': '13'})
    assert host_target() == TARGET
    monkeypatch.setattr('platform.machine', lambda: 'x86_64')
    with pytest.raises(ValueError, match='Debian13'):
        host_target()


def source(tmp_path):
    repo = tmp_path / 'repo';build = tmp_path / 'build';build.mkdir()
    for name in ('adaptive_ecu/data/session-v2-development.conf', 'adaptive_ecu/data/physical-battery.conf.example',
                 'ivi_platform/ui_qml/fonts/OFL.txt', 'docs/unneeded.md', 'tests/unneeded.py', 'logs/unneeded.log'):
        path = repo / name;path.parent.mkdir(parents=True, exist_ok=True);path.write_text('public fixture\n')
    for name in ('adaptive_ecu', 'physical_battery_worker', 'ivi_dashboard', 'test_fake'):
        data = bytearray(64);data[:6] = b'\x7fELF\x02\x01';data[18:20] = b'\xb7\x00'
        (build / name).write_bytes(data)
    (build / 'CMakeCache.txt').write_text('CMAKE_BUILD_TYPE:STRING=Release\nENABLE_COVERAGE:BOOL=OFF\n')
    return repo, build


@pytest.mark.parametrize('node,count', [('ecu', 5), ('ivi', 4)])
def test_exact_runtime_inventory_and_hashes(tmp_path, node, count):
    repo, build = source(tmp_path);out = tmp_path / (node + '.tar.gz')
    m = package(repo, build, node, 'a' * 40, out, TARGET)
    with tarfile.open(out) as t:
        assert len(t.getmembers()) == count
        assert all(p.isfile() for p in t.getmembers())
        names = [p.name for p in t.getmembers()]
        assert not any(n.endswith(('.md', '.py', '.log', '.key', '.png')) or '/test' in n for n in names)
        for name, meta in m['files'].items():
            data = t.extractfile('capstone-' + node + '-runtime/' + name).read()
            assert hashlib.sha256(data).hexdigest() == meta['sha256']
        assert json.load(t.extractfile('capstone-' + node + '-runtime/runtime.json')) == m
    assert hashlib.sha256(out.read_bytes()).hexdigest() in out.with_name(out.name + '.sha256').read_text()
    with pytest.raises(ValueError, match='new runtime'):
        package(repo, build, node, 'a' * 40, out, TARGET)


@pytest.mark.parametrize('problem', ['architecture', 'coverage', 'symlink', 'target'])
def test_bad_build_inputs_are_not_packaged(tmp_path, problem):
    repo, build = source(tmp_path)
    target = TARGET
    if problem == 'architecture':
        path = build / 'adaptive_ecu';data = bytearray(path.read_bytes());data[18:20] = b'\x3e\x00';path.write_bytes(data)
    elif problem == 'coverage':
        (build / 'CMakeCache.txt').write_text('CMAKE_BUILD_TYPE:STRING=Release\nENABLE_COVERAGE:BOOL=ON\n')
    elif problem == 'symlink':
        path = build / 'physical_battery_worker';path.unlink();path.symlink_to(build / 'adaptive_ecu')
    else:
        target = dict(TARGET, os='ubuntu')
    with pytest.raises(ValueError):
        package(repo, build, 'ecu', 'a' * 40, tmp_path / 'out.tar.gz', target)
    assert not (tmp_path / 'out.tar.gz').exists()
