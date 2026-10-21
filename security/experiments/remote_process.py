"""Bound a remote trial process by both SSH stdin lifetime and a deadline."""
import argparse
import hashlib
import json
import os
import select
import signal
import subprocess
import time
from pathlib import Path


def supervise(command, duration, control_fd=0):
    stopping = False
    def stop(signum, frame):
        nonlocal stopping
        stopping = True
    signals = (signal.SIGHUP, signal.SIGINT, signal.SIGTERM)
    previous = {sig: signal.signal(sig, stop) for sig in signals}
    child = None
    try:
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, start_new_session=True)
        deadline = time.monotonic() + duration
        while not stopping and child.poll() is None and time.monotonic() < deadline:
            readable, _, _ = select.select([control_fd], [], [], .1)
            if readable and not os.read(control_fd, 1024):
                break
    finally:
        try:
            if child is not None:
                # Reap the owned group even if its leader exited first.
                try:os.killpg(child.pid, signal.SIGTERM)
                except ProcessLookupError:pass
                try:child.wait(timeout=2)
                except subprocess.TimeoutExpired:pass
                try:os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:pass
                child.wait()
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
    return child.returncode if child.returncode >= 0 else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration', type=float, required=True)
    parser.add_argument('--run-id', default='remote')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not 0 < args.duration <= 86400 or not command:
        parser.error('a command and duration in (0,86400] are required')
    executable = Path(command[0])
    print(json.dumps({'result':'REMOTE_START','run_id':args.run_id,
                      'executable_sha256':hashlib.sha256(executable.read_bytes()).hexdigest()
                      if executable.is_file() else None}),flush=True)
    code = supervise(command, args.duration)
    print(json.dumps({"result": "REMOTE_STOPPED", "run_id": args.run_id, "exit_code": code}), flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
