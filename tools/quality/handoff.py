"""Create/verify a public worktree snapshot, excluding personal records and experiment outputs.

Not a Git commit, release, secret scanner guarantee or physical acceptance.
Personal records and experiment archives remain local. Snapshot inputs are
reread and their inventory is checked before save.
"""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile

ROOTS = ('adaptive_ecu', 'ivi_platform', 'common', 'security', 'tools', '.github')
EXTRAS = ('README.md', 'Dockerfile.arm64', 'toolchain-aarch64.cmake', '.dockerignore',
          '.gitignore', '.env.example', 'scripts/health_check.sh')
PREFIX = 'Capstone-handoff/'
MAX_FILE = 12*1024*1024
MAX_TOTAL = 96*1024*1024
MAX_FILES = 10000
PRIVATE = (rb'-{5}BEGIN [^\r\n]*PRIVATE KEY-{5}', rb'\bghp_[A-Za-z0-9]{20,}',
           rb'\bgithub_pat_[A-Za-z0-9_]{20,}', rb'(?<![0-9])192\.168\.[0-9]{1,3}\.[0-9]{1,3}(?![0-9])')


def safe_name(name):
    path = PurePosixPath(name)
    if not name or path.is_absolute() or str(path) != name or '..' in path.parts or '\\' in name:
        raise ValueError('unsafe snapshot path')
    return name


def allowed(name):
    path = PurePosixPath(safe_name(name))
    if (name.startswith(('docs/', 'plan/', 'handoff/', '.agents/', '.claude/', '.codex/')) or
            name in ('AGENTS.md', 'CLAUDE.md', 'CODEX.md', 'SKILL.md', '1110할일.md', '질문리스트.md', '프로젝트구조개선.md') or
            name.endswith(('-software-source.tar.gz', '-software-handoff.tar.gz'))):
        return False
    if any(part in ('.git', '__pycache__', '.venv', 'venv', 'models', 'logs') or part.startswith('build') for part in path.parts):
        return False
    if (path.suffix.lower() in ('.key', '.pem', '.bin', '.o', '.so', '.a', '.pyc') or
            path.name.startswith('.env') and name != '.env.example'):
        raise ValueError('private/build input in public inventory: '+name)
    return True


def scan(data, name, nested=True):
    if len(data) > MAX_FILE:raise ValueError('snapshot file exceeds budget: '+name)
    if name.endswith('.tar.gz') and nested:
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
            total = 0;seen = set()
            for member in archive:
                safe_name(member.name)
                if not member.isfile() or member.name in seen or member.size > MAX_FILE:
                    raise ValueError('unsafe nested evidence')
                seen.add(member.name);total += member.size
                if total > MAX_TOTAL or len(seen) > MAX_FILES:raise ValueError('nested evidence exceeds budget')
                scan(archive.extractfile(member).read(), name+'/'+member.name, nested=False)
    elif not name.endswith(('.ttf', '.png', '.gz')) and any(re.search(pattern, data) for pattern in PRIVATE):
        raise ValueError('known private marker: '+name)


def inventory(root):
    result = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard',
                                      *ROOTS, *EXTRAS], cwd=root)
    names = sorted({p.decode() for p in result.split(b'\0') if p})
    return [name for name in names if allowed(name)]


def source_bytes(root, name):
    path = root/name
    if not path.is_file() or path.is_symlink():raise ValueError('regular snapshot input required: '+name)
    if any(p.is_symlink() for p in path.parents if p != root.parent):raise ValueError('snapshot parent symlink')
    if path.stat().st_size > MAX_FILE:raise ValueError('snapshot file exceeds budget: '+name)
    return path.read_bytes()


def create(root, output):
    names = inventory(root)
    if not set(EXTRAS) <= set(names) or len(names) > MAX_FILES:raise ValueError('required snapshot source missing or inventory exceeds budget')
    contents = {};entries = []
    for name in names:
        data = source_bytes(root, name);scan(data, name);contents[name] = data
        entries.append({'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                        'mode': 0o755 if (root/name).stat().st_mode & 0o111 else 0o644})
    if sum(len(data) for data in contents.values()) > MAX_TOTAL:raise ValueError('snapshot exceeds total budget')
    manifest = {'schema': 'public-software-handoff-v1', 'working_tree_overlay_included': True,
        'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        'branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=root, text=True).strip(),
        'entries': entries, 'scope': 'Current source, tests and build configuration; no personal records or experiment outputs; not a deployment.',
        'excluded': ['Git internals and ignored files', 'runtime keys/state/builds/virtual environments/models',
            'personal and AI records, plans and experiment outputs',
            'prior source archives and this generated source archive'],
        'checks': ['regular files', 'known private markers', 'nested evidence members', 'source reread and inventory equality']}
    contents['HANDOFF-MANIFEST.json'] = (json.dumps(manifest, ensure_ascii=False, indent=2)+'\n').encode()
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w') as archive:
        modes = {entry['path']: entry['mode'] for entry in entries}
        for name, data in sorted(contents.items()):
            member = tarfile.TarInfo(PREFIX+name);member.size = len(data);member.mode = modes.get(name, 0o644)
            archive.addfile(member, io.BytesIO(data))
    if inventory(root) != names or any(source_bytes(root, name) != contents[name] for name in names):
        raise ValueError('snapshot source or inventory changed')
    data = gzip.compress(buffer.getvalue(), mtime=0)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream:stream.write(data)
    identity = hashlib.sha256(data).hexdigest()
    verified = verify(output, identity)
    return {'archive': str(output), 'sha256': identity, 'bytes': len(data), 'files': len(entries),
            'source_reread_unchanged': True, 'readback_verified': bool(verified)}


def verify(archive_path, expected_sha256, destination=None):
    if archive_path.stat().st_size > MAX_TOTAL+MAX_FILE:raise ValueError('compressed handoff exceeds budget')
    data = archive_path.read_bytes()
    if not re.fullmatch('[0-9a-f]{64}', expected_sha256) or hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError('handoff archive hash differs')
    contents = {};total = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        for member in archive:
            if not member.name.startswith(PREFIX):raise ValueError('invalid handoff prefix')
            name = safe_name(member.name[len(PREFIX):])
            if name in contents or not member.isfile() or not 0 <= member.size <= MAX_FILE or member.mode not in (0o644, 0o755):
                raise ValueError('unsafe handoff member')
            total += member.size
            if total > MAX_TOTAL+MAX_FILE or len(contents) >= MAX_FILES+1:raise ValueError('handoff total budget exceeded')
            contents[name] = (archive.extractfile(member).read(), member.mode)
    manifest = json.loads(contents['HANDOFF-MANIFEST.json'][0])
    if manifest.get('schema') != 'public-software-handoff-v1':raise ValueError('invalid handoff manifest')
    names = set()
    for row in manifest['entries']:
        name = safe_name(row['path'])
        if name in names or name not in contents:raise ValueError('missing/duplicate handoff entry')
        names.add(name);content, mode = contents[name]
        if len(content) != row['bytes'] or hashlib.sha256(content).hexdigest() != row['sha256'] or mode != row['mode']:
            raise ValueError('handoff content mismatch')
        scan(content, name)
    if set(contents) != names | {'HANDOFF-MANIFEST.json'}:raise ValueError('unlisted handoff member')
    if destination is not None:
        destination.mkdir(mode=0o700, parents=False, exist_ok=False)
        for name, (content, mode) in contents.items():
            path = destination/name;path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as stream:stream.write(content)
            path.chmod(mode)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action', required=True)
    build = actions.add_parser('create');build.add_argument('--repo', type=Path, required=True);build.add_argument('--out', type=Path, required=True)
    read = actions.add_parser('verify');read.add_argument('--archive', type=Path, required=True)
    read.add_argument('--sha256', required=True);read.add_argument('--extract-to', type=Path)
    args = parser.parse_args()
    if args.action == 'create':result = create(args.repo.resolve(), args.out.absolute())
    else:
        manifest = verify(args.archive, args.sha256, args.extract_to)
        result = {'status': 'PASS', 'files': len(manifest['entries']), 'extracted': bool(args.extract_to)}
    print(json.dumps(result));return 0


if __name__ == '__main__':raise SystemExit(main())
