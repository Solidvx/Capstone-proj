"""Build a latency-only overlay of the immutable 003 source handoff."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

OVERLAYS = (
    'ivi_platform/CMakeLists.txt', 'ivi_platform/ui_qml/main.cpp',
    'ivi_platform/ui_qml/latency_recorder.h', 'ivi_platform/test/test_latency_recorder.cpp',
)


def bundle(root, base, output):
    with tarfile.open(base, 'r:gz') as archive:
        old_manifest = json.load(archive.extractfile('Capstone-handoff/HANDOFF-MANIFEST.json'))
        data = {}
        modes = {}
        for name, digest in old_manifest['files'].items():
            member = archive.getmember('Capstone-handoff/' + name)
            if not member.isfile() or Path(name).is_absolute() or '..' in Path(name).parts:
                raise ValueError('unsafe source member')
            content = archive.extractfile(member).read()
            if hashlib.sha256(content).hexdigest() != digest:
                raise ValueError('003 source hash mismatch: ' + name)
            data[name], modes[name] = content, member.mode
    for name in OVERLAYS:
        data[name], modes[name] = (root / name).read_bytes(), 0o644
    manifest = {'schema': 'pi-source-handoff-v1', 'kind': 'WORKTREE-SNAPSHOT-NOT-COMMIT',
                'handoff_id': 'pi-handoff-20261004-004', 'base_commit': old_manifest.get('base_commit'),
                'base_archive_sha256': hashlib.sha256(base.read_bytes()).hexdigest(),
                'overlay_source_base_commit': subprocess.check_output(
                    ['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                'overlay_files': list(OVERLAYS),
                'scope': '003 source bytes preserved except explicit IVI latency overlays. ECU unchanged.',
                'excluded': old_manifest['excluded'],
                'files': {name: hashlib.sha256(content).hexdigest() for name, content in sorted(data.items())}}
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode()
    sums = ''.join(f'{digest}  {name}\n' for name, digest in manifest['files'].items()).encode()
    output.mkdir(parents=True, exist_ok=False)
    path = output / 'capstone-pi-handoff.tar.gz'
    with tarfile.open(path, 'x:gz') as archive:
        for name, content in sorted({**data, 'HANDOFF-MANIFEST.json': manifest_bytes,
                                     'HANDOFF-FILES.sha256': sums}.items()):
            member = tarfile.TarInfo('Capstone-handoff/' + name)
            member.size, member.mode = len(content), modes.get(name, 0o644)
            archive.addfile(member, io.BytesIO(content))
    (output / 'HANDOFF-MANIFEST.json').write_bytes(manifest_bytes)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    (output / 'capstone-pi-handoff.tar.gz.sha256').write_text(digest + '  ' + path.name + '\n')
    print(json.dumps({'archive': str(path), 'sha256': digest, 'files': len(data)}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    args = p.parse_args()
    bundle(Path(__file__).resolve().parents[1], args.base, args.output_dir)
