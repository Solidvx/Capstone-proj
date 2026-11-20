#!/usr/bin/env python3
"""Cooperative desktop ownership and PC-stdin-bounded experiment leases.

Run as the existing desktop user. Never signal a PID discovered by name.
Only a desktop started through this owner can be taken over automatically.
"""
import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import select
import signal
import socket
import stat
import subprocess
import sys
import time
import uuid

from supervise_dashboard import supervise


def emit(result, run_id, **details):
    print(json.dumps(dict(result=result, run_id=run_id, **details)), flush=True)


def private_directory(runtime):
    runtime = Path(runtime)
    if runtime.is_symlink() or not runtime.is_dir() or runtime.stat().st_uid != os.getuid():
        raise ValueError('existing desktop-owned runtime directory required')
    directory = runtime / 'ivi-owner'
    directory.mkdir(mode=0o700, exist_ok=True)
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('private owner directory required')
    if len(os.fsencode(directory/'control.sock')) >= 104:
        raise ValueError('owner socket path too long')
    return directory


def lock(directory, name):
    fd = os.open(directory/name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    stream = os.fdopen(fd, 'r+')
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        stream.close(); raise ValueError('private regular owner lock required')
    return stream


def acquire(stream):
    try: fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB); return True
    except BlockingIOError: return False


def request(directory, operation, **details):
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(1.)
        client.connect(str(directory/'control.sock'))
        client.sendall(json.dumps(dict(operation=operation, **details)).encode()+b'\n')
        data = b''
        while not data.endswith(b'\n'):
            chunk = client.recv(4096)
            if not chunk or len(data)+len(chunk) > 65536: raise ValueError('incomplete owner response')
            data += chunk
    value = json.loads(data)
    if not isinstance(value, dict): raise ValueError('owner response object required')
    return value


def server(directory):
    path = directory/'control.sock'
    # Called only while holding the owner lock; no live owner's socket is removed.
    path.unlink(missing_ok=True)
    channel = socket.socket(socket.AF_UNIX)
    channel.bind(str(path)); path.chmod(0o600); channel.listen(4); channel.setblocking(False)
    return channel


def receive(channel, response):
    if not select.select([channel], [], [], 0)[0]: return None
    with channel.accept()[0] as client:
        client.settimeout(.2)
        try:
            data = b''
            while not data.endswith(b'\n'):
                chunk = client.recv(4096)
                if not chunk or len(data)+len(chunk)>4096: return None
                data += chunk
            value = json.loads(data)
            reply = response(value)
            client.sendall(json.dumps(reply).encode()+b'\n')
            return value if reply.get('accepted') else None
        except (OSError, ValueError, TypeError, KeyError): return None


def dashboard_pids():
    """Detect unowned/leftover apps, without killing them."""
    found = []
    for path in Path('/proc').glob('[0-9]*'):
        try:
            if (path/'comm').read_text().strip() in (
                    'ivi_dashboard', 'ivi_dashboard_e'):
                found.append(int(path.name))
        except (OSError, ValueError): pass
    return found


def write_status(directory, name, value):
    temporary = directory/(name+'.pending')
    with temporary.open('w') as stream:
        os.fchmod(stream.fileno(),0o600)
        json.dump(value,stream);stream.flush();os.fsync(stream.fileno())
    temporary.replace(directory/name)


def desktop(args, command, directory):
    if not command or not Path(args.launcher).is_absolute() or not os.access(args.launcher, os.X_OK):
        raise ValueError('desktop command and executable absolute restore launcher required')
    with lock(directory,'lease.lock') as gate, lock(directory,'owner.lock') as owner:
        if not acquire(gate) or not acquire(owner):
            emit('DESKTOP_ALREADY_OWNED',args.run_id); return 0
        if (directory/'uncertain.json').exists() or dashboard_pids():
            raise ValueError('unowned dashboard or uncertain prior cleanup; operator inspection required')
        channel = server(directory)
        fcntl.flock(gate,fcntl.LOCK_UN)
        stop_id = None
        display_ready = False
        environment = {name:value for name,value in os.environ.items() if name in (
            'XDG_RUNTIME_DIR','WAYLAND_DISPLAY','DISPLAY','DBUS_SESSION_BUS_ADDRESS','XDG_CONFIG_HOME',
            'IVI_SECOC_KEY','IVI_CAN_INTERFACE','IVI_SESSION_POLICY','IVI_EVENT_POLICY')}
        def respond(value):
            nonlocal stop_id
            if value.get('operation') == 'query':
                return dict(mode='desktop', pid=os.getpid(), run_id=args.run_id, display_ready=display_ready)
            if value.get('operation') == 'takeover' and stop_id is None:
                stop_id = str(uuid.UUID(value['handoff_id']))
                return dict(accepted=True, mode='desktop', handoff_id=stop_id,
                            restore_argv=[args.launcher], restore_env=environment)
            return dict(accepted=False, mode='desktop')
        def control():
            receive(channel,respond)
            return stop_id is not None
        def output(line):
            nonlocal display_ready
            print(line.decode('utf-8',errors='replace'),flush=True)
            try:
                row=json.loads(line)
                if row.get('result')=='WINDOW_PRESENTED' and row.get('display_platform')=='wayland':display_ready=True
            except (ValueError,TypeError,AttributeError):pass
        try:
            emit('DESKTOP_OWNER_READY',args.run_id,pid=os.getpid())
            code = supervise(command,args.grace_seconds,poll_control=control,on_stdout=output)
            write_status(directory,'desktop-stop.json',dict(handoff_id=stop_id,returncode=code))
            if code == 125:
                write_status(directory,'uncertain.json',dict(reason='DESKTOP_CHILD_UNREAPED'))
            return code
        finally:
            channel.close();(directory/'control.sock').unlink(missing_ok=True)


def lease(args, directory):
    stopping = False
    def stop(_sig,_frame):
        nonlocal stopping
        stopping = True
    for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):signal.signal(sig,stop)
    restore = None; channel = None; owned = False; restore_ok = True; leased = False
    with lock(directory,'lease.lock') as gate, lock(directory,'owner.lock') as owner:
        if not acquire(gate): raise ValueError('another experiment owns the desktop lease')
        try:
            owned = acquire(owner)
            if not owned:
                identity = str(uuid.uuid4())
                restore = request(directory,'takeover',handoff_id=identity)
                if restore.get('accepted') is not True or restore.get('mode') != 'desktop':
                    raise ValueError('desktop is not available for cooperative takeover')
                deadline = time.monotonic()+args.handoff_timeout
                while not owned and time.monotonic()<deadline and not stopping:
                    time.sleep(.02);owned = acquire(owner)
                if not owned:
                    write_status(directory,'uncertain.json',dict(reason='DESKTOP_STOP_UNCONFIRMED'))
                    raise ValueError('desktop stop not confirmed')
                status=json.loads((directory/'desktop-stop.json').read_text())
                if status.get('handoff_id')!=identity or status.get('returncode')!=0:
                    raise ValueError('desktop teardown was not clean')
            if (directory/'uncertain.json').exists() or dashboard_pids():
                raise ValueError('unowned dashboard or uncertain cleanup; no experiment started')
            channel=server(directory)
            leased=True
            emit('READY',args.run_id,role='desktop-lease',source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
            deadline=time.monotonic()+args.duration
            while not stopping and time.monotonic()<deadline:
                if select.select([sys.stdin],[],[],.05)[0] and not os.read(sys.stdin.fileno(),4096):break
                receive(channel,lambda value:dict(mode='lease',run_id=args.run_id,pid=os.getpid(),accepted=False))
        finally:
            if channel is not None:channel.close();(directory/'control.sock').unlink(missing_ok=True)
            # Remote receiver cleanup may lag an abrupt PC/SSH disconnect.
            if owned:
                if leased:
                    deadline=time.monotonic()+args.handoff_timeout
                    while dashboard_pids() and time.monotonic()<deadline:time.sleep(.05)
                    if dashboard_pids():
                        write_status(directory,'uncertain.json',dict(reason='EXPERIMENT_APP_STILL_RUNNING'))
                fcntl.flock(owner,fcntl.LOCK_UN)
            fcntl.flock(gate,fcntl.LOCK_UN)
            if restore is not None:
                restore_ok = False
                if owned and not (directory/'uncertain.json').exists() and not dashboard_pids():
                    try:
                        with (directory/'restore.log').open('ab') as log:
                            os.fchmod(log.fileno(),0o600)
                            child=subprocess.Popen(restore['restore_argv'],stdin=subprocess.DEVNULL,
                                stdout=log,stderr=log,start_new_session=True,
                                env=dict(os.environ,**restore['restore_env']))
                        deadline=time.monotonic()+args.handoff_timeout
                        while time.monotonic()<deadline:
                            try:
                                answer=request(directory,'query')
                                if (answer.get('mode')=='desktop' and answer.get('pid')==child.pid
                                        and answer.get('display_ready') is True):
                                    restore_ok=True;break
                            except (OSError,ValueError):pass
                            if child.poll() is not None:break
                            time.sleep(.02)
                    except (OSError,ValueError,KeyError):pass
            emit('DISPLAY_LEASE_STOPPED',args.run_id,restored=restore_ok,
                 restoration_required=restore is not None)
    return 0 if restore_ok else 2


def launch(args, command, directory):
    owner=request(directory,'query')
    if owner.get('mode')!='lease' or owner.get('run_id')!=args.run_id or not command:
        raise ValueError('matching active experiment lease required')
    runtime=Path(args.runtime_dir)
    candidates=sorted(path for path in runtime.glob('wayland-*') if stat.S_ISSOCK(path.stat().st_mode))
    selected=os.environ.get('WAYLAND_DISPLAY')
    if selected:
        candidates=[p for p in candidates if p.name==selected]
    if len(candidates)!=1:raise ValueError('one explicit desktop Wayland socket required')
    env=dict(os.environ,XDG_RUNTIME_DIR=str(runtime),WAYLAND_DISPLAY=candidates[0].name,QT_QPA_PLATFORM='wayland')
    env.pop('QT_QUICK_BACKEND',None)
    os.execvpe(command[0],command,env)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('desktop','lease','launch'),required=True)
    parser.add_argument('--runtime-dir',default=os.environ.get('XDG_RUNTIME_DIR',f'/run/user/{os.getuid()}'))
    parser.add_argument('--run-id',default='desktop')
    parser.add_argument('--duration',type=float,default=120)
    parser.add_argument('--handoff-timeout',type=float,default=10)
    parser.add_argument('--grace-seconds',type=float,default=5)
    parser.add_argument('--launcher')
    parser.add_argument('command',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    try:
        if not math.isfinite(args.duration) or not 0<args.duration<=86400:raise ValueError('bounded duration required')
        if not math.isfinite(args.handoff_timeout) or not 1<=args.handoff_timeout<=10:raise ValueError('handoff timeout must be1..10s')
        directory=private_directory(args.runtime_dir)
        command=args.command[1:] if args.command[:1]==['--'] else args.command
        if args.mode=='desktop':return desktop(args,command,directory)
        if args.mode=='lease':return lease(args,directory)
        return launch(args,command,directory)
    except (OSError,ValueError,KeyError,TypeError) as error:
        emit('DISPLAY_HANDOFF_ERROR',args.run_id,error=str(error));return 2


if __name__=='__main__':raise SystemExit(main())
