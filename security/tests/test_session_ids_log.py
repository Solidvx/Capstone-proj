"""Owned immutable-generation collection; no device, key or SSH required."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tracemalloc
import uuid

import pytest

from security.experiments.session_ids_log import CHUNK_BYTES, MAX_BYTES, read_generation, stream_generation

GEN=uuid.UUID('00000000-0000-4000-8000-000000000001').hex


def store(tmp_path):
    root=tmp_path/'logs';root.mkdir(mode=0o700)
    folder=root/('ids-'+GEN);folder.mkdir(mode=0o700)
    lock=folder/'owner.lock';lock.write_bytes(b'');lock.chmod(0o600)
    events=folder/'events.jsonl'
    header={'result':'START','run_id':'owned-ids-'+GEN,'protocol':'session-v2','mode':'rules-only'}
    events.write_text(json.dumps(header)+'\n'+json.dumps({'result':'NORMAL','timestamp':1.})+'\n')
    events.chmod(0o600)
    console=folder/'process.log';console.write_text('dummy process output\n');console.chmod(0o600)
    return root,folder,events


def test_exact_bytes_manifest_and_only_fixed_files_are_read(tmp_path):
    root,folder,events=store(tmp_path)
    (folder/'key.bin').write_bytes(b'DO-NOT-COLLECT-THIS')
    data,manifest=read_generation(root,GEN)
    assert data==events.read_bytes() and b'DO-NOT-COLLECT' not in data
    assert manifest['sha256']==hashlib.sha256(data).hexdigest()
    assert manifest['status']=='COMPLETE' and manifest['records']==2
    assert manifest['generation']==GEN and manifest['run_id']=='owned-ids-'+GEN
    console,info=read_generation(root,GEN,'process')
    assert console==b'dummy process output\n' and info['file']=='process.log'
    with pytest.raises(ValueError,match='only events/process'):read_generation(root,GEN,'key.bin')


def test_active_generation_is_refused_then_collectable_after_owner_exit(tmp_path):
    root,folder,_=store(tmp_path)
    child=subprocess.Popen([sys.executable,'-c',
        'import os,fcntl,sys;fd=os.open(sys.argv[1],os.O_RDWR);fcntl.flock(fd,fcntl.LOCK_EX);print("ready",flush=True);sys.stdin.read()',
        str(folder/'owner.lock')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    try:
        assert child.stdout.readline().strip()=='ready'
        with pytest.raises(ValueError,match='still active'):read_generation(root,GEN)
    finally:
        child.stdin.close();child.wait(timeout=3);child.stdout.close()
    assert read_generation(root,GEN)[1]['status']=='COMPLETE'


def test_inherited_child_lock_survives_parent_descriptor_close(tmp_path):
    root,folder,_=store(tmp_path)
    fd=os.open(folder/'owner.lock',os.O_RDWR);fcntl.flock(fd,fcntl.LOCK_EX)
    child=None
    try:
        child=subprocess.Popen([sys.executable,'-c','import sys;print("ready",flush=True);sys.stdin.read()'],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,pass_fds=(fd,))
        assert child.stdout.readline().strip()=='ready'
        os.close(fd);fd=-1
        with pytest.raises(ValueError,match='still active'):read_generation(root,GEN)
    finally:
        if fd>=0:os.close(fd)
        if child is not None:
            child.stdin.close();child.wait(timeout=3);child.stdout.close()
    assert read_generation(root,GEN)[1]['status']=='COMPLETE'


@pytest.mark.parametrize('part',['root','folder','events'])
def test_nonprivate_paths_are_rejected(tmp_path,part):
    root,folder,events=store(tmp_path)
    {'root':root,'folder':folder,'events':events}[part].chmod(0o755)
    with pytest.raises(ValueError,match='private owned'):read_generation(root,GEN)


@pytest.mark.parametrize('kind',['symlink','hardlink','fifo'])
def test_log_cannot_be_replaced_by_another_file_or_special_device(tmp_path,kind):
    root,_,events=store(tmp_path)
    outside=tmp_path/'private.key';outside.write_bytes(b'DO-NOT-READ');outside.chmod(0o600)
    events.unlink()
    if kind=='symlink':events.symlink_to(outside)
    elif kind=='hardlink':os.link(outside,events)
    else:os.mkfifo(events,0o600)
    with pytest.raises((OSError,ValueError)):read_generation(root,GEN)


@pytest.mark.parametrize('generation',['../private','0'*32,'not-an-id',uuid.uuid1().hex])
def test_invalid_generation_cannot_select_a_path(tmp_path,generation):
    root,_,_=store(tmp_path)
    with pytest.raises(ValueError,match='UUIDv4'):read_generation(root,generation)


def test_partial_and_corrupt_logs_are_preserved_but_not_complete(tmp_path):
    root,_,events=store(tmp_path)
    events.write_bytes(events.read_bytes().rstrip(b'\n'))
    raw,manifest=read_generation(root,GEN)
    assert raw==events.read_bytes() and manifest['status']=='INCOMPLETE'
    with events.open('ab') as stream:stream.write(b'\n{partial')
    raw,manifest=read_generation(root,GEN)
    assert raw==events.read_bytes() and manifest['status']=='CORRUPT'


def test_wrong_start_and_oversize_are_rejected(tmp_path):
    root,_,events=store(tmp_path)
    with pytest.raises(ValueError,match='bound'):read_generation(root,GEN,max_bytes=1)
    events.write_text(json.dumps({'result':'START','protocol':'session-v2','mode':'rules-only','run_id':'wrong'})+'\n')
    with pytest.raises(ValueError,match='START'):read_generation(root,GEN)


def test_streams_over_legacy_bound_with_bounded_memory_and_exact_hash(tmp_path):
    root,_,events=store(tmp_path)
    record=json.dumps({'result':'FINDING','timestamp':1.,'observed':'x'*60000}).encode()+b'\n'
    with events.open('ab') as source:
        for _ in range(1120):source.write(record)
    size=events.stat().st_size
    assert size>MAX_BYTES
    with pytest.raises(ValueError,match='bound'):read_generation(root,GEN)
    with (tmp_path/'received.jsonl').open('wb') as sink:
        tracemalloc.start()
        try:
            manifest=stream_generation(root,GEN,max_total_bytes=size,sink=sink)
            _,peak=tracemalloc.get_traced_memory()
        finally:tracemalloc.stop()
    digest=hashlib.sha256()
    with (tmp_path/'received.jsonl').open('rb') as received:
        while True:
            chunk=received.read(CHUNK_BYTES)
            if not chunk:break
            digest.update(chunk)
    assert manifest['schema']=='owned-ids-log-v2' and manifest['status']=='COMPLETE'
    assert manifest['bytes']==size and manifest['sha256']==digest.hexdigest()
    assert manifest['records']==1122 and manifest['max_total_bytes']==size
    assert peak<2*1024*1024  # Source, parsed records and output are never accumulated.


@pytest.mark.parametrize('tail,status',[
    (b'{"result":"NORMAL"}', 'INCOMPLETE'),
    (b'{broken\n','CORRUPT'),
    (b'[]\n','CORRUPT'),
    (b'\xff\n','CORRUPT'),
    (b'{"result":"START"}\n','CORRUPT'),
    (b'x'*(CHUNK_BYTES+1)+b'\n','CORRUPT'),
])
def test_stream_preserves_bad_or_partial_bytes_without_complete_manifest(tmp_path,tail,status):
    import io
    root,_,events=store(tmp_path)
    with events.open('ab') as source:source.write(tail)
    sink=io.BytesIO()
    manifest=stream_generation(root,GEN,max_total_bytes=events.stat().st_size,sink=sink)
    assert sink.getvalue()==events.read_bytes() and manifest['status']==status


@pytest.mark.parametrize('change',['append','truncate','replace','hardlink','permission','flush'])
def test_source_mutations_never_receive_complete_manifest(tmp_path,change):
    root,_,events=store(tmp_path)
    class MutatingSink:
        changed=False
        def write(self,data):
            if not self.changed:
                self.changed=True
                if change=='append':
                    with events.open('ab') as source:source.write(b'{}\n')
                elif change=='truncate':events.write_bytes(b'')
                elif change=='replace':
                    replacement=events.with_suffix('.new');replacement.write_bytes(events.read_bytes())
                    replacement.chmod(0o600);replacement.replace(events)
                elif change=='hardlink':os.link(events,events.with_suffix('.link'))
                elif change=='permission':events.chmod(0o644)
            return len(data)
        def flush(self):
            if change=='flush':
                with events.open('ab') as source:source.write(b'{}\n')
    with pytest.raises((OSError,ValueError)):
        stream_generation(root,GEN,max_total_bytes=MAX_BYTES,sink=MutatingSink())


def test_explicit_bound_and_output_write_failure_are_enforced(tmp_path):
    import io
    root,_,events=store(tmp_path)
    for bound in (True,0,-1,1.5):
        with pytest.raises(ValueError,match='bound'):
            stream_generation(root,GEN,max_total_bytes=bound,sink=io.BytesIO())
    sink=io.BytesIO()
    with pytest.raises(ValueError,match='bound'):
        stream_generation(root,GEN,max_total_bytes=events.stat().st_size-1,sink=sink)
    assert sink.getvalue()==b''
    class ShortSink:
        def write(self,data):return len(data)-1
    with pytest.raises(OSError,match='output write'):
        stream_generation(root,GEN,max_total_bytes=MAX_BYTES,sink=ShortSink())


def test_cli_requires_budget_and_receiver_checks_manifest(tmp_path):
    root,_,events=store(tmp_path)
    command=[sys.executable,'-m','security.experiments.session_ids_log',
        '--log-root',str(root),'--generation',GEN]
    for flags in (['--stream'],['--max-total-bytes','1024']):
        result=subprocess.run(command+flags,capture_output=True)
        assert result.returncode==2 and not result.stdout
    result=subprocess.run(command+['--stream','--max-total-bytes',str(events.stat().st_size)],capture_output=True)
    assert result.returncode==0 and result.stdout==events.read_bytes()
    assert json.loads(result.stderr)['schema']=='owned-ids-log-v2'
    with events.open('ab') as source:source.write(b'{broken')
    result=subprocess.run(command+['--stream','--max-total-bytes',str(events.stat().st_size)],capture_output=True)
    assert result.returncode==2 and result.stdout==events.read_bytes()
    assert json.loads(result.stderr)['status']=='CORRUPT'
