"""Collect one closed, owned IDS generation file; never select arbitrary paths.

Run on ECU through PC-owned SSH after remote cleanup acknowledgement. stdout is
the exact selected file; stderr carries a length/hash/generation manifest. An
active generation is refused. No key, model or caller-selected filename is read.
"""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import uuid

FILES={'events':'events.jsonl','process':'process.log'}
MAX_BYTES=64*1024*1024
CHUNK_BYTES=65536


def private(fd,directory=False):
    info=os.fstat(fd)
    expected=stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if not expected or info.st_uid!=os.getuid() or info.st_mode&0o077 or (not directory and info.st_nlink!=1):
        raise ValueError('private owned directory/regular single-link file required')
    return info


@contextmanager
def owned_file(root,generation,kind):
    if (not isinstance(generation,str) or not re.fullmatch('[0-9a-f]{32}',generation)
            or uuid.UUID(hex=generation).version!=4):
        raise ValueError('owned UUIDv4 generation required')
    if kind not in FILES:raise ValueError('only events/process logs may be collected')
    if not Path(root).is_absolute():raise ValueError('absolute owned log root required')
    descriptors=[]
    try:
        flags=os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW|os.O_NONBLOCK
        parent=os.open(root,flags|os.O_DIRECTORY);descriptors.append(parent);private(parent,True)
        folder=os.open('ids-'+generation,flags|os.O_DIRECTORY,dir_fd=parent)
        descriptors.append(folder);private(folder,True)
        lock=os.open('owner.lock',flags,dir_fd=folder);descriptors.append(lock);private(lock)
        try:fcntl.flock(lock,fcntl.LOCK_SH|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('IDS generation is still active') from None
        fd=os.open(FILES[kind],flags,dir_fd=folder);descriptors.append(fd);initial=private(fd)
        yield fd
        final=private(fd)
        if ((initial.st_size,initial.st_mtime_ns,initial.st_ctime_ns)!=
            (final.st_size,final.st_mtime_ns,final.st_ctime_ns)):
            raise ValueError('IDS log changed during collection')
        # An unlinked/replaced file must not attest the selected closed generation.
        for descriptor,name,dir_fd in ((parent,root,None),(folder,'ids-'+generation,parent),
                                       (lock,'owner.lock',folder),(fd,FILES[kind],folder)):
            info=private(descriptor,directory=descriptor in (parent,folder))
            named=os.stat(name,dir_fd=dir_fd,follow_symlinks=False)
            if (info.st_dev,info.st_ino)!=(named.st_dev,named.st_ino):
                raise ValueError('IDS generation path changed during collection')
    finally:
        for fd in reversed(descriptors):os.close(fd)


class EventValidator:
    """Validate NDJSON with at most one bounded record retained in memory."""
    def __init__(self,generation):
        self.generation=generation;self.pending=bytearray();self.first=None
        self.records=0;self.status='COMPLETE';self.last_newline=False

    def record(self,line):
        try:
            if len(line)>CHUNK_BYTES:raise ValueError('oversized event')
            row=json.loads(line)
            if not isinstance(row,dict):raise ValueError('object required')
        except (ValueError,UnicodeDecodeError):
            self.status='CORRUPT';return
        if self.first is None:self.first=row
        elif row.get('result')=='START':self.status='CORRUPT'
        self.records+=1

    def feed(self,chunk):
        self.last_newline=chunk.endswith(b'\n')
        if self.status=='CORRUPT':return
        pieces=chunk.split(b'\n')
        for index,piece in enumerate(pieces):
            self.pending.extend(piece)
            if len(self.pending)>CHUNK_BYTES:
                self.status='CORRUPT';self.pending.clear();return
            if index<len(pieces)-1:
                self.record(self.pending);self.pending.clear()
                if self.status=='CORRUPT':return

    def finish(self):
        if self.pending and self.status!='CORRUPT':self.record(self.pending)
        first=self.first
        if (first is None or first.get('result')!='START' or
            first.get('run_id')!='owned-ids-'+self.generation or
            first.get('protocol')!='session-v2' or first.get('mode') not in ('rules-only','rules+if')):
            raise ValueError('IDS START does not attest the selected generation')
        if self.status=='COMPLETE' and not self.last_newline:self.status='INCOMPLETE'
        return {'status':self.status,'mode':first['mode'],'records':self.records,'run_id':first['run_id']}


def stream_generation(root,generation,kind='events',*,max_total_bytes,sink):
    """Copy exactly one closed log in bounded chunks; caller must choose a budget.

    Bytes already sent are preserved on failure, but never receive a COMPLETE
    manifest. The receiver must check the final manifest and process exit status.
    """
    if type(max_total_bytes) is not int or not 1<=max_total_bytes<=sys.maxsize:
        raise ValueError('invalid stream bound')
    validator=EventValidator(generation) if kind=='events' else None
    with owned_file(root,generation,kind) as fd:
        before=private(fd)
        if before.st_size>max_total_bytes:raise ValueError('IDS log exceeds collection bound')
        digest=hashlib.sha256();count=0
        while True:
            chunk=os.read(fd,min(CHUNK_BYTES,max_total_bytes+1-count))
            if not chunk:break
            count+=len(chunk)
            if count>max_total_bytes:raise ValueError('IDS log changed during collection')
            if validator:validator.feed(chunk)
            written=sink.write(chunk)
            if written!=len(chunk):raise OSError('incomplete IDS log output write')
            digest.update(chunk)
        after=private(fd)
        if (count!=before.st_size or
            (before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_size,after.st_mtime_ns,after.st_ctime_ns)):
            raise ValueError('IDS log changed during collection')
        manifest={'schema':'owned-ids-log-v2','generation':generation,'file':FILES[kind],
            'bytes':count,'sha256':digest.hexdigest(),'status':'COMPLETE',
            'max_total_bytes':max_total_bytes,'stream':True}
        if validator:manifest.update(validator.finish())
        sink.flush()
    return manifest


def read_generation(root,generation,kind='events',max_bytes=MAX_BYTES):
    # Preserve the legacy byte-returning API and its original 64 MiB ceiling.
    import io
    if type(max_bytes) is not int or not 1<=max_bytes<=MAX_BYTES:raise ValueError('invalid read bound')
    sink=io.BytesIO()
    manifest=stream_generation(root,generation,kind,max_total_bytes=max_bytes,sink=sink)
    manifest['schema']='owned-ids-log-v1';manifest.pop('max_total_bytes');manifest.pop('stream')
    return sink.getvalue(),manifest


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log-root',type=Path,required=True)
    parser.add_argument('--generation',required=True)
    parser.add_argument('--kind',choices=FILES,default='events')
    parser.add_argument('--stream',action='store_true',help='bounded streaming; requires an explicit total byte budget')
    parser.add_argument('--max-total-bytes',type=int,help='explicit selected-file budget, required with --stream')
    args=parser.parse_args(argv)
    if args.stream!=(args.max_total_bytes is not None):parser.error('--stream and --max-total-bytes must be supplied together')
    try:
        if args.stream:
            manifest=stream_generation(args.log_root,args.generation,args.kind,
                max_total_bytes=args.max_total_bytes,sink=sys.stdout.buffer)
        else:
            data,manifest=read_generation(args.log_root,args.generation,args.kind)
            sys.stdout.buffer.write(data);sys.stdout.buffer.flush()
    except (OSError,ValueError) as error:
        print(json.dumps({'status':'ERROR','error':str(error)}),file=sys.stderr);return 2
    print(json.dumps(manifest),file=sys.stderr)
    return 0 if manifest['status']=='COMPLETE' else 2


if __name__=='__main__':raise SystemExit(main())
