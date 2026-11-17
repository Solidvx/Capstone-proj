"""Build node-specific physical-display archives, never a repository snapshot.

Run inside a Debian13 ARM64 Release build environment. Does not install,
activate services, copy keys or change an existing checkout on a Raspberry Pi.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import platform
import re
import struct
import tarfile


def host_target():
    release = platform.freedesktop_os_release()
    if release.get('ID') != 'debian' or release.get('VERSION_ID') != '13' or platform.machine() != 'aarch64':
        raise ValueError('runtime packaging requires native Debian13 ARM64; do not ship Ubuntu/macOS build binaries')
    return {'os': 'debian', 'version': '13', 'architecture': 'aarch64'}


def package(repo, build, role, revision, output, target):
    if role not in ('ecu', 'ivi') or not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('explicit node and full source revision required')
    if target != {'os': 'debian', 'version': '13', 'architecture': 'aarch64'}:
        raise ValueError('unsupported runtime target')
    cache = (build / 'CMakeCache.txt').read_text()
    for required in ('CMAKE_BUILD_TYPE:STRING=Release', 'ENABLE_COVERAGE:BOOL=OFF'):
        if required not in cache.splitlines():
            raise ValueError('runtime archive requires Release without coverage')
    selected = {'bin/adaptive_ecu': build / 'adaptive_ecu',
                'bin/physical_battery_worker': build / 'physical_battery_worker',
                'config/physical-battery.conf.example': repo / 'adaptive_ecu/data/physical-battery.conf.example'} if role == 'ecu' else {
                    'bin/ivi_dashboard': build / 'ivi_dashboard',
                    'licenses/NanumGothic-OFL.txt': repo / 'ivi_platform/ui_qml/fonts/OFL.txt'}
    selected['config/session-v2-development.conf'] = repo / 'adaptive_ecu/data/session-v2-development.conf'
    contents = {}
    for name, path in selected.items():
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 64 * 1024 * 1024:
            raise ValueError('missing/unsafe runtime input: ' + name)
        data = path.read_bytes()
        if name.startswith('bin/'):
            if len(data) < 20 or data[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', data, 18)[0] != 183:
                raise ValueError('ARM64 ELF required: ' + name)
        contents[name] = (data, 0o755 if name.startswith('bin/') else 0o644)
    manifest = {'schema': 'capstone-node-runtime-v1', 'node': role, 'purpose': 'physical-display',
                'revision': revision, 'target': target, 'system_libraries_bundled': False,
                'files': {name: {'sha256': hashlib.sha256(data).hexdigest(), 'mode': mode}
                          for name, (data, mode) in contents.items()}}
    contents['runtime.json'] = ((json.dumps(manifest, indent=2) + '\n').encode(), 0o644)
    prefix = 'capstone-' + role + '-runtime/'
    # Build in memory before creating the output; never overwrite old packages.
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as archive:
        for name, (data, mode) in sorted(contents.items()):
            item = tarfile.TarInfo(prefix + name)
            item.size = len(data);item.mode = mode;item.mtime = 0
            archive.addfile(item, io.BytesIO(data))
    if len(stream.getvalue()) > 128 * 1024 * 1024:
        raise ValueError('runtime archive exceeds budget')
    checksum = output.with_name(output.name + '.sha256')
    if output.exists() or checksum.exists():
        raise ValueError('new runtime output paths required')
    with output.open('xb') as destination:
        destination.write(stream.getvalue())
    with checksum.open('x') as destination:
        destination.write(hashlib.sha256(stream.getvalue()).hexdigest() + '  ' + output.name + '\n')
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, default=Path('.'))
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--node', choices=('ecu', 'ivi'), required=True)
    p.add_argument('--revision', required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    try:
        manifest = package(args.repo.resolve(), args.build.resolve(), args.node, args.revision,
                           args.out.resolve(), host_target())
        print(json.dumps({'status': 'PASS', 'node': args.node, 'files': len(manifest['files']) + 1, 'out': str(args.out)}))
        return 0
    except (OSError, ValueError) as error:
        print(json.dumps({'status': 'ERROR', 'error': str(error)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
