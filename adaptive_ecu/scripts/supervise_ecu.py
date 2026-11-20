#!/usr/bin/env python3
"""Own ECU lifetime and preserve state across bounded automatic recovery.

Exit75 is a planned resume. Signals or a health timeout may consume the explicit
crash retry budget. Exit2/configuration, storage health errors and manual stop
never silently fresh-start. All timing values are explicit local policy.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import stat
import subprocess
import sys
import time
from owned_ids import OwnedIds, load_settings


class TxTraceCapture:
    """Owned bounded pipe; malformed/partial trace never changes ECU health."""
    def __init__(self, output):
        self.reader,self.writer=os.pipe()
        try:
            for fd in (self.reader,self.writer):os.set_blocking(fd,False)
        except BaseException:
            os.close(self.reader);os.close(self.writer);raise
        self.output=output;self.pending=b'';self.error=None;self.final=None
        self.records=0;self.tx_records=0;self.last_drops=0;self.bytes=0;self.pid=None;self.instance=None

    def validate(self,row):
        prefix={'result','schema','instance_id'}
        def number(key,limit=2**64-1):
            value=row.get(key)
            if type(value) is not int or not 0<=value<=limit:raise ValueError('invalid trace number: '+key)
            return value
        if number('records_dropped')<self.last_drops:raise ValueError('trace drops regressed')
        if row['result']=='ECU_CAN_TX_END':
            if set(row)!=prefix|{'attempts','records_written','records_dropped','ended_ns'}:
                raise ValueError('invalid trace end fields')
            if (number('records_written')!=self.tx_records or
                number('attempts')!=number('records_written')+number('records_dropped')):
                raise ValueError('trace end counters differ')
            number('ended_ns')
        else:
            if set(row)!=prefix|{'sequence','started_ns','ended_ns','can_id','dlc','data','counter',
                                 'syscall_attempted','returned_bytes','error_number','kernel_accepted','records_dropped'}:
                raise ValueError('invalid trace attempt fields')
            if number('sequence')!=self.tx_records+1+number('records_dropped'):
                raise ValueError('trace sequence/drop counters differ')
            if number('ended_ns')<number('started_ns'):raise ValueError('trace clock regressed')
            cid=number('can_id',2**32-1);dlc=number('dlc',255);data=row['data']
            if (not isinstance(data,str) or len(data)!=min(dlc,8)*2 or
                any(c not in '0123456789abcdef' for c in data)):
                raise ValueError('invalid trace wire bytes')
            counter=int(data[8:],16) if dlc==8 and cid in (0x102,0x103,0x105) else None
            if row['counter']!=counter or (counter is not None and type(row['counter']) is not int):
                raise ValueError('trace auth counter differs from wire')
            if (type(row['syscall_attempted']) is not bool or type(row['kernel_accepted']) is not bool or
                type(row['returned_bytes']) is not int or not -1<=row['returned_bytes']<=16):
                raise ValueError('invalid trace syscall outcome')
            error=number('error_number',2**31-1)
            if ((not row['syscall_attempted'] and row['returned_bytes']!=-1) or
                (row['syscall_attempted'] and row['returned_bytes']==-1 and not error)):
                raise ValueError('trace precheck/syscall errno missing')
            accepted=row['syscall_attempted'] and row['returned_bytes']==16
            if row['kernel_accepted']!=accepted or (accepted and (error or dlc>8)):
                raise ValueError('trace acceptance differs from syscall')

    def handed_off(self):
        os.close(self.writer);self.writer=-1

    def poll(self):
        if self.reader<0:return False
        try:data=os.read(self.reader,4096)
        except (BlockingIOError,InterruptedError):return False
        except OSError as error:
            self.error='trace read failed: errno='+str(error.errno)
            try:os.close(self.reader)
            except OSError:pass  # EBADF means the descriptor is already closed.
            self.reader=-1;self.pending=b''
            return False
        if not data:
            os.close(self.reader);self.reader=-1
            if self.pending:self.error='partial trace record'
            return False
        self.bytes+=len(data)
        try:
            parts=(self.pending+data).split(b'\n');self.pending=parts.pop()
            if len(self.pending)>=512:raise ValueError('oversized trace tail')
            for line in parts:
                if len(line)>=512:raise ValueError('oversized trace record')
                row=json.loads(line)
                if (not isinstance(row,dict) or row.get('schema')!='ecu-can-tx-v1' or
                    row.get('result') not in ('ECU_CAN_TX','ECU_CAN_TX_END') or self.final):
                    raise ValueError('invalid trace schema/order')
                instance=row.get('instance_id')
                if (not isinstance(instance,str) or len(instance)!=32 or
                    any(c not in '0123456789abcdef' for c in instance) or
                    self.instance not in (None,instance)):
                    raise ValueError('mixed trace instance')
                self.instance=instance
                self.validate(row)
                self.last_drops=row['records_dropped']
                if row['result']=='ECU_CAN_TX_END':self.final=row.copy()
                else:self.tx_records+=1
                self.records+=1
                self.output(dict(row,ecu_pid=self.pid))
        except (ValueError,UnicodeError,TypeError,KeyError) as error:
            self.error=str(error);os.close(self.reader);self.reader=-1;self.pending=b''
        return True

    def close(self):
        if self.writer>=0:os.close(self.writer);self.writer=-1
        # Called only after reaping the child. Bound even an unexpected holder.
        for _ in range(64):
            if not self.poll():break
        complete=self.reader<0 and not self.error and not self.pending and self.final is not None
        if self.reader>=0:os.close(self.reader);self.reader=-1
        self.output({'result':'ECU_CAN_TX_CAPTURE_END','ecu_pid':self.pid,'instance_id':self.instance,
                     'status':'COMPLETE' if complete else 'INCOMPLETE','records':self.records,
                     'bytes':self.bytes,'error':self.error,'final_record_available':self.final is not None})


def executable_identity(path):
    with Path(path).open('rb') as stream:
        before=os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):raise ValueError('ECU executable must be a regular file')
        digest=hashlib.sha256()
        for block in iter(lambda:stream.read(65536),b''):digest.update(block)
        after=os.fstat(stream.fileno())
        if (before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_size,after.st_mtime_ns,after.st_ctime_ns):
            raise ValueError('ECU executable changed during fingerprint')
    return digest.hexdigest()


def reclaim(child, timeout):
    if child is None or child.poll() is not None:
        return
    child.terminate()
    try:
        child.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ecu', required=True)
    parser.add_argument('--ids-settings', type=Path)
    parser.add_argument('--trace-can-tx',action='store_true',help='opt-in private nonblocking ECU CAN syscall trace in manager output')
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--initial-intent', choices=('fresh', 'resume'), required=True)
    parser.add_argument('--stop-timeout', type=float, required=True)
    parser.add_argument('--startup-timeout', type=float, required=True)
    parser.add_argument('--heartbeat-timeout', type=float, required=True)
    parser.add_argument('--max-crash-restarts', type=int, required=True)
    parser.add_argument('ecu_args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if any(not 0 < value <= 60 for value in (args.stop_timeout,args.startup_timeout,args.heartbeat_timeout)):
        parser.error('timeouts must be in (0,60] seconds')
    if not 0 <= args.max_crash_restarts <= 3:
        parser.error('max-crash-restarts must be in [0,3]')
    tail = args.ecu_args[1:] if args.ecu_args[:1] == ['--'] else args.ecu_args
    if any(x.split('=', 1)[0] in ('--checkpoint', '--start-intent', '--supervisor-fd','--tx-trace-fd') for x in tail):
        parser.error('checkpoint, intent, health and TX trace pipes are owned by this supervisor')
    ids_settings=load_settings(args.ids_settings) if args.ids_settings else None
    if ids_settings:
        owned_flags={'--ids-context-fd','--ids-peer-fd','--ids-socket','--ids-pid','--ids-frame-budget','--ids-expiry-ms'}
        if any(x.split('=',1)[0] in owned_flags for x in tail):parser.error('IDS options are supervisor-owned')
        def selected(flag):
            if tail.count(flag)!=1 or tail.index(flag)+1==len(tail):parser.error('managed IDS requires explicit '+flag)
            return tail[tail.index(flag)+1]
        ids_interface=selected('--interface');ids_key=selected('--key')
    directory = args.checkpoint.absolute().parent
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        parser.error('checkpoint parent must be private and owned')
    lock_fd = os.open(str(args.checkpoint) + '.supervisor.lock',
                      os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(lock_fd, 'rb') as lock:
        info = os.fstat(lock.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            parser.error('supervisor lock rejected')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        child = None
        stopping = False

        def stop(signum, frame):
            nonlocal stopping
            stopping = True
            if child is not None and child.poll() is None:
                child.terminate()

        signal.signal(signal.SIGINT, stop)
        signal.signal(signal.SIGTERM, stop)
        intent = args.initial_intent
        crash_restarts = 0
        try:
            while not stopping:
                reader, writer = os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)
                fault = None
                ids=None;ids_extra=[];tx_trace=None
                try:
                    if ids_settings:
                        ids=OwnedIds(ids_settings,directory,ids_interface,ids_key)
                        try:
                            ids.start(args.startup_timeout,lambda:stopping)
                            ids_extra=ids.ecu_args()
                        except (OSError,ValueError,RuntimeError) as error:
                            print('ECU_SUPERVISOR: IDS unavailable: '+str(error),flush=True)
                            print(json.dumps({'result':'OWNED_IDS_UNAVAILABLE','error':str(error)}),flush=True)
                            ids.close(args.stop_timeout);ids=None
                    if stopping:return 0
                    if args.trace_can_tx:
                        tx_trace=TxTraceCapture(lambda row:print(json.dumps(row,sort_keys=True),flush=True))
                    executable_sha256=executable_identity(args.ecu)
                    inherited=(writer,)+( (ids.writer,ids.peer_writer) if ids else ())
                    trace_args=[]
                    if tx_trace:
                        inherited+=(tx_trace.writer,);trace_args=['--tx-trace-fd',str(tx_trace.writer)]
                    child = subprocess.Popen([args.ecu, '--checkpoint', str(args.checkpoint),
                        '--start-intent', intent, '--supervisor-fd', str(writer)] + tail + ids_extra + trace_args,
                        pass_fds=inherited)
                    if tx_trace:tx_trace.pid=child.pid;tx_trace.handed_off()
                    if ids:ids.handed_off()
                    os.close(writer); writer = -1
                    print('ECU_SUPERVISOR: started pid=' + str(child.pid) + ' intent=' + intent, flush=True)
                    if executable_identity(args.ecu)!=executable_sha256:
                        reclaim(child,args.stop_timeout)
                        raise RuntimeError('ECU executable changed during launch')
                    print(json.dumps({'result':'ECU_PROCESS_STARTED','pid':child.pid,'intent':intent,
                        'trace_can_tx':args.trace_can_tx,
                        'executable_sha256':executable_sha256,
                        'supervisor_sha256':executable_identity(__file__),
                        'owned_ids_sha256':executable_identity(Path(__file__).with_name('owned_ids.py'))}),flush=True)
                    started = last_work = time.monotonic()
                    saw_work = False
                    while child.poll() is None and not stopping:
                        if ids:ids.check()
                        watched=[reader]+([tx_trace.reader] if tx_trace and tx_trace.reader>=0 else [])
                        ready, _, _ = select.select(watched, [], [], .1)
                        if tx_trace and tx_trace.reader in ready:tx_trace.poll()
                        if reader in ready:
                            data = os.read(reader, 4096)
                            if data:
                                if any(not byte & 1 or byte > 15 for byte in data):
                                    fault = 'invalid-health'; break
                                if any(byte & 6 for byte in data):
                                    fault = 'storage-unavailable'; break
                                last_work = time.monotonic(); saw_work = True
                            else:
                                # Pipe EOF can precede waitpid by a scheduling turn.
                                try:child.wait(timeout=.1)
                                except subprocess.TimeoutExpired:fault = 'health-pipe-closed'
                                break
                        now = time.monotonic()
                        if now-last_work >= (args.heartbeat_timeout if saw_work else args.startup_timeout):
                            fault = 'heartbeat-timeout' if saw_work else 'startup-timeout'; break
                    if fault or stopping:
                        reclaim(child,args.stop_timeout)
                    code = child.wait()  # fully reaped before replacement
                finally:
                    if ids:
                        reclaim(child,args.stop_timeout)
                        ids.close(args.stop_timeout)
                    if tx_trace:
                        reclaim(child,args.stop_timeout)
                        tx_trace.close()
                    os.close(reader)
                    if writer >= 0:os.close(writer)
                if stopping:
                    return 0
                if fault in ('storage-unavailable','invalid-health','health-pipe-closed'):
                    print('ECU_SUPERVISOR: stopped ' + fault, flush=True)
                    return 2
                if code == 75 and fault is None:
                    intent = 'resume'
                    print('ECU_SUPERVISOR: planned restart, restoring protected state', flush=True)
                    continue
                if fault is None and code >= 0:
                    return code
                if crash_restarts >= args.max_crash_restarts:
                    print('ECU_SUPERVISOR: recovery budget exhausted', flush=True)
                    return 1
                # ECU validates integrity, age, configuration and protection on
                # resume. A rejected snapshot returns2 and ends recovery.
                crash_restarts += 1
                intent = 'resume'
                print('ECU_SUPERVISOR: crash recovery attempt=' + str(crash_restarts) +
                      ' reason=' + (fault or 'signal'), flush=True)
            return 0
        finally:
            reclaim(child,args.stop_timeout)


if __name__ == '__main__':
    sys.exit(main())
