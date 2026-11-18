"""Build a stdlib-only Pi3 worker zipapp; no installation or device access."""
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


# Extract original definitions verbatim, not copied implementations. Fail closed
# if a named definition disappears. Packaged execution is tested independently.
SELECTED = {
    'security/attacks/attack_simulator.py': ('', ('ATTACK_TYPES', 'MAX_RATE_FPS', 'MAX_DURATION_S',
        'SPOOF_BMS', 'REPLAY_BMS', 'is_test_bus', 'validate', 'build_frame')),
    'security/ids/runtime_detector.py': ('from dataclasses import dataclass\n', ('Observation',)),
    'security/experiments/can_capture.py': (
        'import json, socket, select, struct, subprocess, time\n'
        'from security.ids.runtime_detector import Observation\n',
        ('inspect_interface', 'CaptureSocket', 'frame_json')),
    'security/experiments/trial_observer.py': (
        'from security.experiments.can_capture import inspect_interface\n', ('healthy',)),
    'security/ids/startup_identity.py': ('import hashlib, json, os, stat\nfrom pathlib import Path\n',
        ('file_digest', 'source_digest')),
    'security/can_diagnostic.py': ('', ('LENGTHS', '_u', '_zero', '_uuid', '_reference', '_state', 'valid_body')),
}
WHOLE = ('security/physical_transport.py', 'security/experiments/can_attack_worker.py')


def extract(source, header, names):
    tree = ast.parse(source)
    selected = {}
    lines = source.splitlines(keepends=True)
    for node in tree.body:
        name = getattr(node, 'name', None)
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
        if name in names:
            start = min([node.lineno] + [d.lineno for d in getattr(node, 'decorator_list', [])])
            selected[name] = ''.join(lines[start-1:node.end_lineno])
    if set(selected) != set(names):
        raise ValueError('missing package definitions: ' + str(set(names)-set(selected)))
    return ('from __future__ import annotations\n' + header + '\n' +
            '\n\n'.join(selected[name] for name in names)).encode()


def package(repo, output, revision):
    if not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('full source revision required')
    files = {}
    inputs = {}
    for name in (*SELECTED, *WHOLE):
        path = repo / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('regular source required: ' + name)
        data = path.read_bytes()
        inputs[name] = hashlib.sha256(data).hexdigest()
        files[name] = extract(data.decode(), *SELECTED[name]) if name in SELECTED else data
    # Namespace packages are not discovered consistently by zipimport.
    for name in list(files):
        for parent in Path(name).parents:
            if str(parent) != '.':
                files.setdefault(parent.as_posix() + '/__init__.py', b'')
    files['__main__.py'] = b'from security.experiments.can_attack_worker import main\nmain()\n'
    manifest = {'schema': 'capstone-attacker-runtime-v1', 'revision': revision,
        'role': 'keyless-can-worker', 'python_minimum': '3.10', 'platform': 'Linux SocketCAN',
        'dependencies': 'Python standard library only; system ip command',
        'campaign_controller_included': False, 'source_files_sha256': inputs,
        'files_sha256': {n: hashlib.sha256(d).hexdigest() for n, d in sorted(files.items())}}
    # Startup identity hashes the packaged code, not unavailable checkout files.
    identity = files['security/ids/startup_identity.py'].decode()
    pos = identity.index('def source_digest():')
    files['security/ids/startup_identity.py'] = (identity[:pos] +
        "def source_digest():\n    return file_digest(__loader__.archive)['sha256']\n").encode()
    manifest['files_sha256']['security/ids/startup_identity.py'] = hashlib.sha256(files['security/ids/startup_identity.py']).hexdigest()
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(name, data)
    contents = stream.getvalue()
    manifest['archive_sha256'] = hashlib.sha256(contents).hexdigest()
    metadata = output.with_suffix('.json')
    if output.exists() or metadata.exists():
        raise ValueError('new output paths required')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as handle:
        handle.write(contents)
    with metadata.open('x') as handle:
        json.dump(manifest, handle, indent=2)
        handle.write('\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path('.'))
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--revision', required=True)
    args = parser.parse_args()
    result = package(args.repo.resolve(), args.out.resolve(), args.revision)
    print(json.dumps({'out': str(args.out), 'sha256': result['archive_sha256']}))


if __name__ == '__main__':
    main()
