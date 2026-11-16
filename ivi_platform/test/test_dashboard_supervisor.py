"""Real desktop-supervisor process tests, without CAN or production keys."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/supervise_dashboard.py'
pytestmark=pytest.mark.skipif(os.name!='posix',reason='POSIX desktop process ownership')


def start(tmp_path, body, grace=.2, finalizer_race=False):
    ready=tmp_path/'child-pid'
    code=('import os,signal,socket,time,sys\n'
          'from pathlib import Path\n'
          'signal.signal(signal.SIGTERM,signal.SIG_IGN)\n'
          'channel=socket.socket(fileno=int(os.environ["IVI_SHUTDOWN_NOTIFY_FD"]))\n'
          f'Path({str(ready)!r}).write_text(str(os.getpid()))\n'+body)
    prefix=[sys.executable]
    if finalizer_race:
        # Widen CPython's callable-handler reset window without changing the
        # product. SIG_IGN must survive; Python callbacks may be reset to DFL.
        bootstrap=('import atexit,runpy,signal,sys,time\nfrom pathlib import Path\n'
            'def cleanup():\n'
            ' for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):\n'
            '  if callable(signal.getsignal(sig)):signal.signal(sig,signal.SIG_DFL)\n'
            f' Path({str(tmp_path/"finalizing")!r}).write_text("ready")\n'
            ' deadline=time.monotonic()+2\n'
            f' while not Path({str(tmp_path/"release-finalizer")!r}).exists() and time.monotonic()<deadline:time.sleep(.005)\n'
            'atexit.register(cleanup)\nsys.argv=sys.argv[1:]\nrunpy.run_path(sys.argv[0],run_name="__main__")\n')
        prefix+=['-c',bootstrap]
    proc=subprocess.Popen(prefix+[str(SCRIPT),'--grace-seconds',str(grace),'--',
                           sys.executable,'-c',code],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    return proc,ready


def wait_ready(proc, ready):
    until=time.monotonic()+3
    while True:
        try:
            value=ready.read_text()
            if value:return int(value)
        except FileNotFoundError:
            pass
        if proc.poll() is not None or time.monotonic()>=until:
            raise AssertionError('child did not start')
        time.sleep(.01)


def finish(proc):
    if proc.poll() is None:
        proc.terminate()
        try:proc.wait(timeout=3)
        except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=2)


def test_normal_quit_notice_preserves_exit_code(tmp_path):
    proc,_=start(tmp_path,'channel.send(b"Q")\ntime.sleep(.05)\nsys.exit(7)\n')
    try:
        _,err=proc.communicate(timeout=3)
        assert proc.returncode==7
        assert 'DASHBOARD_STOP_TIMEOUT' not in err
        assert 'DASHBOARD_STOPPED' in err
    finally:finish(proc)


def test_quit_notice_kills_and_reaps_stuck_cleanup(tmp_path):
    proc,ready=start(tmp_path,'channel.send(b"Q")\nwhile True:time.sleep(1)\n')
    try:
        child=wait_ready(proc,ready)
        _,err=proc.communicate(timeout=3)
        assert proc.returncode==124
        rows=[json.loads(line) for line in err.splitlines()]
        assert any(row.get('valid_notice') is True for row in rows)
        assert rows[-1]['result']=='DASHBOARD_STOP_TIMEOUT'
        assert rows[-1]['pending_event_records']=='unconfirmed'
        with pytest.raises(ProcessLookupError):os.kill(child,0)
    finally:finish(proc)


def test_repeated_stop_signals_do_not_extend_deadline(tmp_path):
    proc,ready=start(tmp_path,'while True:time.sleep(1)\n')
    try:
        child=wait_ready(proc,ready)
        until=time.monotonic()+1.5
        while proc.poll() is None and time.monotonic()<until:
            proc.send_signal(signal.SIGTERM)
            time.sleep(.02)
        assert proc.poll() is not None,'repeated signals postponed the original deadline'
        _,err=proc.communicate(timeout=1)
        assert proc.returncode==124 and err.count('DASHBOARD_STOP_REQUESTED')==1
        with pytest.raises(ProcessLookupError):os.kill(child,0)
    finally:finish(proc)


def test_terminal_exit_code_survives_interpreter_signal_cleanup(tmp_path):
    proc,ready=start(tmp_path,'while True:time.sleep(1)\n',finalizer_race=True)
    try:
        child=wait_ready(proc,ready);proc.send_signal(signal.SIGTERM)
        deadline=time.monotonic()+2
        while not (tmp_path/'finalizing').exists() and proc.poll() is None and time.monotonic()<deadline:time.sleep(.005)
        assert (tmp_path/'finalizing').exists(),'final interpreter teardown not reached'
        proc.send_signal(signal.SIGTERM)
        (tmp_path/'release-finalizer').write_text('done')
        _,err=proc.communicate(timeout=2)
        assert proc.returncode==124 and err.count('DASHBOARD_STOP_REQUESTED')==1
        with pytest.raises(ProcessLookupError):os.kill(child,0)
    finally:finish(proc)


@pytest.mark.parametrize('grace',['0','nan','inf'])
def test_invalid_deadline_does_not_start_child(tmp_path, grace):
    marker=tmp_path/'must-not-exist'
    result=subprocess.run([sys.executable,str(SCRIPT),'--grace-seconds',grace,'--',
        sys.executable,'-c',f'open({str(marker)!r},"w").close()'],capture_output=True,text=True,timeout=3)
    assert result.returncode!=0 and not marker.exists()
