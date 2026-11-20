"""Real local owner processes/Unix sockets; synthetic app, not a panel test."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time

import pytest

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/dashboard_handoff.py'


def query(root, **value):
    with socket.socket(socket.AF_UNIX) as channel:
        channel.settimeout(.3);channel.connect(str(root/'ivi-owner/control.sock'))
        channel.sendall(json.dumps(value or {'operation':'query'}).encode()+b'\n')
        return json.loads(channel.recv(65536))


def until(predicate, timeout=4):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        try:
            result=predicate()
            if result:return result
        except (OSError,ValueError):pass
        time.sleep(.02)
    raise AssertionError('owner did not reach expected state')


def stop(proc):
    if proc.poll() is None:
        proc.terminate()
        try:proc.wait(timeout=3)
        except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=2)
    if proc.stdin and not proc.stdin.closed:proc.stdin.close()


@contextmanager
def desktop(tmp_path, extra=''):
    # Deliberately short: Linux Unix-domain socket names have a small limit.
    with tempfile.TemporaryDirectory(prefix='ivio-',dir=os.environ.get('TMPDIR')) as name:
        root=Path(name);pidfile=root/'app.pid';launcher=root/'launch.py'
        app=('import os,signal,time,json\nfrom pathlib import Path\n'
             'signal.signal(signal.SIGTERM,lambda *_:exit(0))\n'
             f'Path({str(pidfile)!r}).write_text(str(os.getpid()))\n'
             'print(json.dumps({"result":"WINDOW_PRESENTED","display_platform":"wayland"}),flush=True)\n'
             +extra+'\nwhile True:time.sleep(.02)\n')
        command=[sys.executable,str(SCRIPT),'--mode','desktop','--runtime-dir',str(root),
                 '--launcher',str(launcher),'--grace-seconds','.2','--',sys.executable,'-c',app]
        launcher.write_text('#!'+sys.executable+'\nimport os\nos.execv('+repr(sys.executable)+','+repr(command)+')\n')
        launcher.chmod(0o700)
        with (root/'normal.log').open('w') as log:
            normal=subprocess.Popen(command,stdout=log,stderr=log)
            leases=[]
            try:
                until(lambda:query(root).get('display_ready'))
                yield root,normal,leases,pidfile,launcher
            finally:
                for child in leases:stop(child)
                stop(normal)
                try:
                    answer=query(root)
                    if answer.get('mode')=='desktop':
                        os.kill(answer['pid'],signal.SIGTERM)
                        until(lambda:not (root/'ivi-owner/control.sock').exists())
                except OSError:pass


def start_lease(root, leases):
    proc=subprocess.Popen([sys.executable,str(SCRIPT),'--mode','lease','--runtime-dir',str(root),
        '--run-id','DUMMY','--duration','10','--handoff-timeout','2'],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    leases.append(proc)
    until(lambda:query(root).get('mode')=='lease')
    return proc


def test_takeover_reaps_normal_and_EOF_restores_one_new_desktop(tmp_path):
    with desktop(tmp_path) as (root,normal,leases,pidfile,launcher):
        first=int(pidfile.read_text());lease=start_lease(root,leases)
        assert normal.wait(timeout=2)==0
        with pytest.raises(ProcessLookupError):os.kill(first,0)
        duplicate=subprocess.run([str(launcher)],capture_output=True,text=True,timeout=2)
        assert duplicate.returncode==0 and 'DESKTOP_ALREADY_OWNED' in duplicate.stdout
        lease.stdin.close();lease.wait(timeout=4)
        rows=[json.loads(line) for line in lease.stdout.read().splitlines()]
        assert lease.returncode==0 and rows[-1]['restored'] is True
        assert query(root)['display_ready'] and int(pidfile.read_text())!=first


def test_restore_failure_is_not_reported_as_success(tmp_path):
    with desktop(tmp_path) as (root,normal,leases,pidfile,launcher):
        lease=start_lease(root,leases);launcher.unlink()
        lease.stdin.close();lease.wait(timeout=4)
        rows=[json.loads(line) for line in lease.stdout.read().splitlines()]
        assert lease.returncode==2 and rows[-1]['restored'] is False


def test_second_lease_refused_without_disturbing_current_owner(tmp_path):
    with desktop(tmp_path) as (root,normal,leases,pidfile,launcher):
        lease=start_lease(root,leases)
        second=subprocess.run([sys.executable,str(SCRIPT),'--mode','lease','--runtime-dir',str(root)],
                              input='',capture_output=True,text=True,timeout=2)
        assert second.returncode==2 and 'another experiment' in second.stdout
        assert query(root)['mode']=='lease' and lease.poll() is None


def test_launch_needs_owned_run_and_actual_Wayland_socket(tmp_path):
    with desktop(tmp_path) as (root,normal,leases,pidfile,launcher):
        lease=start_lease(root,leases)
        prefix=[sys.executable,str(SCRIPT),'--mode','launch','--runtime-dir',str(root),'--run-id']
        command=[sys.executable,'-c','import os;print(os.environ["QT_QPA_PLATFORM"])']
        missing=subprocess.run(prefix+['DUMMY','--']+command,capture_output=True,text=True,timeout=2)
        assert missing.returncode==2 and 'Wayland socket' in missing.stdout
        with socket.socket(socket.AF_UNIX) as wayland:
            wayland.bind(str(root/'wayland-0'))
            wrong=subprocess.run(prefix+['WRONG','--']+command,capture_output=True,text=True,timeout=2)
            assert wrong.returncode==2
            good=subprocess.run(prefix+['DUMMY','--']+command,capture_output=True,text=True,timeout=2,
                                env={k:v for k,v in os.environ.items() if k!='WAYLAND_DISPLAY'})
            assert good.returncode==0 and good.stdout.strip()=='wayland'


def test_uncertain_cleanup_prevents_new_lease(tmp_path):
    with tempfile.TemporaryDirectory(prefix='ivio-',dir=os.environ.get('TMPDIR')) as name:
        root=Path(name);directory=root/'ivi-owner';directory.mkdir(mode=0o700)
        (directory/'uncertain.json').write_text('{}')
        result=subprocess.run([sys.executable,str(SCRIPT),'--mode','lease','--runtime-dir',name],
            input='',capture_output=True,text=True,timeout=2)
        assert result.returncode==2 and 'uncertain' in result.stdout


@pytest.mark.skipif(not Path('/proc/self/comm').exists(),reason='Linux process ownership check')
def test_unmanaged_dashboard_is_never_killed_or_overlapped(tmp_path):
    with tempfile.TemporaryDirectory(prefix='ivio-',dir=os.environ.get('TMPDIR')) as name:
        ready=Path(name)/'ready'
        code=('import ctypes,time\nfrom pathlib import Path\n'
              'ctypes.CDLL(None).prctl(15,b"ivi_dashboard",0,0,0)\n'
              f'Path({str(ready)!r}).write_text("ready")\n'
              'time.sleep(10)\n')
        child=subprocess.Popen([sys.executable,'-c',code])
        try:
            until(ready.exists)
            attempt=subprocess.run([sys.executable,str(SCRIPT),'--mode','lease','--runtime-dir',name],
                input='',capture_output=True,text=True,timeout=2)
            assert attempt.returncode==2 and 'unowned dashboard' in attempt.stdout
            assert child.poll() is None
        finally:stop(child)
