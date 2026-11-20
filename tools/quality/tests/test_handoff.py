import hashlib
import io
import json
import tarfile

import pytest

from tools.quality.handoff import PREFIX, allowed, safe_name, scan, verify
from tools.quality import handoff


def archive(tmp_path, mutation):
    data = b'public source\n'
    entries = [{'path': 'code.py', 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'mode': 0o644}]
    if mutation == 'hash':entries[0]['sha256'] = '0'*64
    if mutation == 'missing':entries.append(dict(entries[0], path='absent'))
    contents = [('code.py', data), ('HANDOFF-MANIFEST.json', json.dumps({'schema': 'public-software-handoff-v1', 'entries': entries}).encode())]
    if mutation == 'duplicate':contents.append(contents[0])
    if mutation == 'unlisted':contents.append(('extra', b'unexpected'))
    if mutation == 'traversal':contents.append(('../escape', b'unexpected'))
    path = tmp_path/'source.tar.gz'
    with tarfile.open(path, 'w:gz') as output:
        for name, content in contents:
            member = tarfile.TarInfo(PREFIX+name);member.size = len(content);member.mode = 0o644
            if mutation == 'symlink' and name == 'code.py':member.type = tarfile.SYMTYPE;member.linkname = '/outside';member.size = 0
            output.addfile(member, io.BytesIO(content))
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize('mutation', ['hash', 'missing', 'duplicate', 'unlisted', 'traversal', 'symlink'])
def test_invalid_archive_is_rejected_before_extraction(tmp_path, mutation):
    path, identity = archive(tmp_path, mutation);destination = tmp_path/'output'
    with pytest.raises(ValueError):verify(path, identity, destination)
    assert not destination.exists()


def test_valid_snapshot_extracts_only_to_new_directory_with_hash_check(tmp_path):
    path, identity = archive(tmp_path, None);destination = tmp_path/'output'
    assert len(verify(path, identity, destination)['entries']) == 1
    assert (destination/'code.py').read_bytes() == b'public source\n'
    with pytest.raises(FileExistsError):verify(path, identity, destination)
    with pytest.raises(ValueError, match='hash'):verify(path, '0'*64)


def test_public_inventory_does_not_include_runtime_material_or_recursive_source_archives():
    assert '질문리스트.md' not in handoff.EXTRAS
    assert not allowed('질문리스트.md')
    assert not allowed('AGENTS.md')
    assert not allowed('docs/private-notes.md')
    assert not allowed('common/testdata/artifacts/20261114-software-handoff.tar.gz')
    assert not allowed('plan/_archive/IVI.md')
    assert not allowed('adaptive_ecu/build/adaptive_ecu')
    assert allowed('.env.example')
    for name in ('security/real.key', 'security/.env', 'common/../outside', '/absolute'):
        with pytest.raises(ValueError):allowed(name)
    with pytest.raises(ValueError):scan(b'-'*5+b'BEGIN PRIVATE KEY'+b'-'*5, 'secret.txt')
    assert safe_name('docs/ICD.md') == 'docs/ICD.md'


@pytest.mark.parametrize('change', ['bytes', 'inventory'])
def test_snapshot_drift_is_rejected_before_publishing(tmp_path, monkeypatch, change):
    for name in handoff.EXTRAS:
        path = tmp_path/name;path.parent.mkdir(parents=True, exist_ok=True);path.write_bytes(b'public fixture\n')
    reads = 0
    def inventory(_):
        nonlocal reads
        reads += 1
        if reads == 2:
            if change == 'inventory':return sorted([*handoff.EXTRAS, 'new-file'])
            (tmp_path/'README.md').write_bytes(b'changed source\n')
        return sorted(handoff.EXTRAS)
    monkeypatch.setattr(handoff, 'inventory', inventory)
    monkeypatch.setattr(handoff.subprocess, 'check_output', lambda *a, **kw: 'public-fixture\n')
    output = tmp_path/'not-published.tar.gz'
    with pytest.raises(ValueError, match='changed'):handoff.create(tmp_path, output)
    assert not output.exists()


def test_compressed_size_and_member_count_are_bounded_before_extract(tmp_path, monkeypatch):
    path, identity = archive(tmp_path, None)
    monkeypatch.setattr(handoff, 'MAX_TOTAL', 1);monkeypatch.setattr(handoff, 'MAX_FILE', 1)
    with pytest.raises(ValueError, match='compressed'):verify(path, identity, tmp_path/'oversized')
    monkeypatch.setattr(handoff, 'MAX_TOTAL', 1024*1024);monkeypatch.setattr(handoff, 'MAX_FILE', 1024*1024)
    monkeypatch.setattr(handoff, 'MAX_FILES', 0)
    with pytest.raises(ValueError, match='budget'):verify(path, identity, tmp_path/'too-many')
    assert not (tmp_path/'oversized').exists() and not (tmp_path/'too-many').exists()
