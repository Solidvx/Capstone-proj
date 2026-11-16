"""Local staged release transaction; no SSH, service identity or policy defaults.

Activation/health/deactivation are explicit executable argument lists. Runtime
keys, counters, checkpoints and event stores must live outside this release root.
An interrupted transaction blocks new activation until explicit recovery.
"""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import subprocess
import tempfile
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def durable(path, value):
    fd, name = tempfile.mkstemp(prefix='.'+path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
        os.replace(name, path);sync_dir(path.parent)
    finally:
        if os.path.exists(name):os.unlink(name)


def inspect_release(directory, immutable=False):
    if directory.is_symlink() or not directory.is_dir():raise ValueError('regular release directory required')
    manifest = directory/'release.json'
    if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size > 1024*1024:
        raise ValueError('bounded regular release manifest required')
    raw = manifest.read_bytes();value = json.loads(raw)
    if set(value) != {'schema', 'revision', 'files'} or value['schema'] != 'capstone-release-v1':
        raise ValueError('unsupported release manifest')
    if not isinstance(value['revision'], str) or not re.fullmatch('[A-Za-z0-9._-]{1,96}', value['revision']):
        raise ValueError('explicit public revision required')
    if not isinstance(value['files'], dict) or not 2 <= len(value['files']) <= 10000:
        raise ValueError('invalid release inventory')
    if not {'bin/adaptive_ecu', 'bin/ivi_dashboard'} <= value['files'].keys():
        raise ValueError('both products required')
    expected = {'release.json'}
    for name, metadata in value['files'].items():
        if not isinstance(name, str):raise ValueError('unsafe release path')
        path = PurePosixPath(name)
        if (path.is_absolute() or str(path) != name or
                any(part in ('', '.', '..') or part.startswith('.') for part in path.parts)):
            raise ValueError('unsafe release path')
        if (not isinstance(metadata, dict) or set(metadata) != {'sha256', 'mode'} or
                not isinstance(metadata['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', metadata['sha256']) or
                type(metadata['mode']) is not int or metadata['mode'] not in (0o444, 0o555)):
            raise ValueError('invalid immutable release metadata')
        source = directory/name
        if any(parent.is_symlink() for parent in [source, *source.parents] if parent != directory.parent):
            raise ValueError('release symlink rejected')
        if not source.is_file() or digest(source) != metadata['sha256']:
            raise ValueError('release content mismatch')
        if immutable and source.stat().st_mode & 0o7777 != metadata['mode']:
            raise ValueError('staged release permissions changed')
        expected.add(name)
    actual = set()
    for current, folders, files in os.walk(directory, followlinks=False):
        if any((Path(current)/p).is_symlink() for p in folders+files):raise ValueError('release symlink rejected')
        actual.update(str((Path(current)/p).relative_to(directory)) for p in files)
    if actual != expected:raise ValueError('unlisted release content')
    for name in ('bin/adaptive_ecu', 'bin/ivi_dashboard'):
        with (directory/name).open('rb') as stream:header = stream.read(20)
        if len(header) != 20 or header[:6] != b'\x7fELF\x02\x01' or header[18:20] != b'\xb7\x00':
            raise ValueError('ARM64 product ELF required')
        if value['files'][name]['mode'] != 0o555:raise ValueError('executable product required')
    return hashlib.sha256(raw).hexdigest(), value


@contextlib.contextmanager
def locked(root):
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = root.stat()
    if root.is_symlink() or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('private operator-owned release root required')
    with (root/'lock').open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def stage(root, source):
    identity, manifest = inspect_release(source)
    releases = root/'releases';releases.mkdir(mode=0o700, exist_ok=True)
    target = releases/identity
    if target.exists():
        if inspect_release(target, immutable=True)[0] != identity:raise ValueError('staged release changed')
        return target
    temporary = Path(tempfile.mkdtemp(prefix='.stage-', dir=releases))
    try:
        for name, metadata in manifest['files'].items():
            destination = temporary/name;destination.parent.mkdir(parents=True, exist_ok=True)
            with (source/name).open('rb') as incoming, destination.open('xb') as outgoing:
                shutil.copyfileobj(incoming, outgoing);outgoing.flush();os.fsync(outgoing.fileno())
            destination.chmod(metadata['mode'])
        shutil.copyfile(source/'release.json', temporary/'release.json')
        (temporary/'release.json').chmod(0o444)
        with (temporary/'release.json').open('rb') as stream:os.fsync(stream.fileno())
        if inspect_release(temporary, immutable=True)[0] != identity or inspect_release(source)[0] != identity:
            raise ValueError('release changed during staging')
        for current, _, _ in os.walk(temporary, topdown=False):sync_dir(current)
        os.rename(temporary, target);sync_dir(releases)
        return target
    finally:
        if temporary.exists():shutil.rmtree(temporary)


def current(root):
    link = root/'current'
    if not link.is_symlink():
        if link.exists():raise ValueError('current must be a managed symlink')
        return None
    target = link.resolve(strict=True)
    if target.parent != (root/'releases').resolve() or inspect_release(target, immutable=True)[0] != target.name:
        raise ValueError('unmanaged or modified current release')
    return target


def switch(root, target):
    temporary = root/'.current-next'
    if temporary.exists() or temporary.is_symlink():temporary.unlink()
    if target is None:
        (root/'current').unlink(missing_ok=True);sync_dir(root);return
    temporary.symlink_to('releases/'+target.name)
    os.replace(temporary, root/'current');sync_dir(root)


def policy(value):
    if not isinstance(value, dict) or set(value) != {'activate', 'health', 'deactivate', 'timeout_s'}:
        raise ValueError('explicit activation, health, deactivation and timeout policy required')
    if type(value['timeout_s']) is not int or not 1 <= value['timeout_s'] <= 3600:
        raise ValueError('bounded explicit hook timeout required')
    for name in ('activate', 'health', 'deactivate'):
        argv = value[name]
        if not isinstance(argv, list) or not argv or any(not isinstance(a, str) or not a or '\0' in a for a in argv):
            raise ValueError('hook must be a nonempty argument list')
        if not Path(argv[0]).is_absolute():raise ValueError('absolute hook executable required')
    return value


def hook(settings, name, target):
    argv = [a.replace('{release}', str(target) if target else '') for a in settings[name]]
    # Hook stdout may contain operational secrets; do not echo or persist it.
    process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, start_new_session=True)
    try:code = process.wait(timeout=settings['timeout_s'])
    except subprocess.TimeoutExpired as error:
        try:os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:pass
        process.wait(timeout=5)
        raise RuntimeError(name+' hook timed out') from error
    if code:raise RuntimeError(name+' hook failed with code '+str(code))


def restore(root, row, settings):
    old = root/'releases'/row['previous'] if row['previous'] else None
    if old and inspect_release(old, immutable=True)[0] != old.name:raise ValueError('previous release changed; rollback refused')
    switch(root, old)
    if old:
        hook(settings, 'activate', old);hook(settings, 'health', old)
    else:hook(settings, 'deactivate', None)
    row.update(status='ROLLED_BACK', finished_ns=time.time_ns());durable(root/'transaction.json', row)
    return row


def deploy(root, source, settings, recover=False):
    settings = policy(settings)
    with locked(root):
        journal = root/'transaction.json'
        prior = json.loads(journal.read_text()) if journal.exists() else None
        if prior is not None:
            if (not isinstance(prior, dict) or prior.get('schema') != 'release-transaction-v1' or
                    prior.get('status') not in ('PENDING', 'ROLLBACK_FAILED', 'COMMITTED', 'ROLLED_BACK') or
                    not isinstance(prior.get('release'), str) or not re.fullmatch('[0-9a-f]{64}', prior['release']) or
                    prior.get('previous') is not None and (not isinstance(prior['previous'], str) or
                        not re.fullmatch('[0-9a-f]{64}', prior['previous']))):
                raise ValueError('invalid transaction journal; automatic recovery refused')
        pending = prior and prior.get('status') in ('PENDING', 'ROLLBACK_FAILED')
        if recover:
            if not pending:raise ValueError('no interrupted transaction to recover')
            row = prior
        else:
            if pending:raise ValueError('pending transaction requires explicit recovery')
            previous = current(root);target = stage(root, source)
            if previous == target:
                hook(settings, 'health', target)
                return {'status': 'UNCHANGED', 'release': target.name}
            row = {'schema': 'release-transaction-v1', 'status': 'PENDING', 'release': target.name,
                   'previous': previous.name if previous else None, 'started_ns': time.time_ns()}
            durable(journal, row)
            try:
                switch(root, target);hook(settings, 'activate', target);hook(settings, 'health', target)
                row.update(status='COMMITTED', finished_ns=time.time_ns());durable(journal, row);return row
            except (OSError, RuntimeError) as error:
                row.update(status='PENDING', activation_error=str(error));durable(journal, row)
        try:return restore(root, row, settings)
        except (OSError, ValueError, RuntimeError) as error:
            row.update(status='ROLLBACK_FAILED', rollback_error=str(error));durable(journal, row)
            return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--hooks', type=Path, required=True)
    parser.add_argument('--recover', action='store_true')
    args = parser.parse_args()
    if not args.recover and args.source is None:parser.error('--source required for deployment')
    try:
        result = deploy(args.root.absolute(), args.source.absolute() if args.source else None,
                        json.loads(args.hooks.read_text()), args.recover)
    except (OSError, ValueError, RuntimeError) as error:
        result = {'status': 'ERROR', 'error': str(error)}
    print(json.dumps(result))
    return 0 if result['status'] in ('COMMITTED', 'UNCHANGED') or args.recover and result['status'] == 'ROLLED_BACK' else 1


if __name__ == '__main__':raise SystemExit(main())
