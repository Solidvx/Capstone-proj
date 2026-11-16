#!/usr/bin/env python3
"""Bound desktop dashboard teardown after a signal or its private quit notice."""
import argparse
import json
import math
import os
import selectors
import signal
import socket
import subprocess
import sys
import time


def supervise(command, grace_seconds=5.0, poll_control=None, on_stdout=None):
    if not math.isfinite(grace_seconds) or not .05 <= grace_seconds <= 60:
        raise ValueError('shutdown grace must be 0.05..60 seconds')
    requested = None

    def request(signum, _frame):
        nonlocal requested
        if requested is None:
            requested = signum

    # This command owns signal handling until process exit. Restoring default
    # handlers just before returning lets a repeated stop overwrite exit124.
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, request)
    child = None
    forced = False

    def send(signum):
        if child is not None and child.poll() is None:
            try:
                os.killpg(child.pid, signum)
            except ProcessLookupError:
                pass

    def report(result, **details):
        print(json.dumps({'result': result, **details}), file=sys.stderr, flush=True)

    def terminal(code):
        # The child is reaped (or explicitly reported unreapable). CPython
        # finalization resets Python signal callbacks to SIG_DFL; SIG_IGN
        # survives it and protects the already-decided exit status.
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(sig, signal.SIG_IGN)
        return code

    try:
        reader, writer = socket.socketpair()
        with reader, writer, selectors.DefaultSelector() as selector:
            reader.setblocking(False)
            writer.setblocking(False)
            child = subprocess.Popen(command, start_new_session=True,
                env=dict(os.environ, IVI_SHUTDOWN_NOTIFY_FD=str(writer.fileno())),
                pass_fds=(writer.fileno(),), stdout=subprocess.PIPE if on_stdout is not None else None)
            writer.close()
            selector.register(reader, selectors.EVENT_READ)
            pending = b''
            if child.stdout is not None:
                os.set_blocking(child.stdout.fileno(), False)
                selector.register(child.stdout, selectors.EVENT_READ)
            deadline = None
            forwarded = False
            while child.poll() is None:
                if poll_control is not None and poll_control() and requested is None:
                    requested = signal.SIGTERM
                now = time.monotonic()
                if requested is not None and not forwarded:
                    forwarded = True
                    send(requested)
                    if deadline is None:
                        deadline = now + grace_seconds
                    report('DASHBOARD_STOP_REQUESTED', signal=requested)
                if deadline is not None and now >= deadline:
                    forced = True
                    send(signal.SIGKILL)
                    report('DASHBOARD_STOP_TIMEOUT', grace_seconds=grace_seconds,
                           pending_event_records='unconfirmed')
                    try:
                        child.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        report('DASHBOARD_CHILD_UNREAPED', pending_event_records='unconfirmed')
                        return terminal(125)
                    return terminal(124)
                wait = min(.05, max(0, deadline-now)) if deadline is not None else .05
                for key, _ in selector.select(wait):
                    if key.fileobj is not reader:
                        chunk = os.read(key.fileobj.fileno(), 4096)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        pending += chunk
                        if len(pending)>65536: raise ValueError('dashboard stdout row too large')
                        while b'\n' in pending:
                            line, pending = pending.split(b'\n',1)
                            on_stdout(line)
                        continue
                    notice = reader.recv(64)
                    # A notice is sent before Qt/worker teardown. EOF also
                    # bounds teardown on an early return or unexpected close.
                    if deadline is None:
                        deadline = time.monotonic() + grace_seconds
                        report('DASHBOARD_QUIT_NOTIFIED', valid_notice=notice == b'Q')
                    if not notice:
                        selector.unregister(reader)
            code = child.wait()
            report('DASHBOARD_STOPPED', returncode=code)
            return terminal(code if code >= 0 else 128-code)
    finally:
        if child is not None and child.poll() is None and not forced:
            send(signal.SIGTERM)
            try:
                child.wait(timeout=grace_seconds)
            except subprocess.TimeoutExpired:
                send(signal.SIGKILL)
                try:
                    child.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    report('DASHBOARD_CHILD_UNREAPED', pending_event_records='unconfirmed')
        if child is not None and child.stdout is not None: child.stdout.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--grace-seconds', type=float, default=5.0)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        parser.error('dashboard command required after --')
    return supervise(command, args.grace_seconds)


if __name__ == '__main__':
    raise SystemExit(main())
