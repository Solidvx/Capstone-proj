"""Receive-only remote observer with stdin phase barriers and a bounded lifetime.

Run through non-PTY SSH directly (not remote_process, which consumes stdin).
Phase boundaries are acknowledged on this host; clocks across hosts are not subtracted.
"""
import argparse
import json
import os
import select
import signal
import time

from security.experiments.can_capture import CaptureSocket, frame_json, inspect_interface
from security.ids.startup_identity import source_digest, file_digest
import platform
import sys
from pathlib import Path


def healthy(channel,environment='physical'):
    if environment not in ('physical','vcan'):raise ValueError('explicit bus environment required')
    info = inspect_interface(channel, environment)
    if environment=='vcan':return info
    if info['bitrate'] != 500000 or info['state'] != 'ERROR-ACTIVE':
        raise RuntimeError('CAN must be ERROR-ACTIVE at 500000 bit/s')
    return info


def emit(row):
    print(json.dumps(row), flush=True)


def observe(channel, duration, run_id, control_fd=0,environment='physical'):
    healthy(channel,environment)
    bus = CaptureSocket(channel)
    try: clock_id = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    except OSError: clock_id = None
    stopping = False
    def stop(signum, frame):
        nonlocal stopping
        stopping = True
    old = {sig: signal.signal(sig, stop) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    phase, pending = 'idle', b''
    deadline = time.monotonic() + duration
    try:
        emit({'result': 'READY', 'run_id': run_id,'execution_identity':{
            'schema':'python-actor-startup-v1','source_sha256':source_digest(),
            'interpreter':file_digest(sys.executable),'python':platform.python_version()}})
        while not stopping and time.monotonic() < deadline:
            if select.select([control_fd], [], [], 0)[0]:
                data = os.read(control_fd, 4096)
                if not data:
                    break
                pending += data
                if len(pending) > 8192:
                    raise ValueError('observer command too long')
                while b'\n' in pending:
                    line, pending = pending.split(b'\n', 1)
                    request = json.loads(line)
                    next_phase = request['phase']
                    if next_phase not in ('baseline', 'attack', 'post', 'idle'):
                        raise ValueError('invalid phase')
                    # Log queued frames in the old phase before acknowledging the barrier.
                    discarded = 0
                    for _ in range(4096):
                        received = bus.receive(0)
                        if received is None:
                            break
                        frame, _ = received
                        emit({"result": "OBS_FRAME", "phase": phase, **frame_json(frame),
                              "rx_dropped": bus.dropped})
                        discarded += 1
                    else:
                        raise RuntimeError("observer backlog did not drain")
                    phase = next_phase
                    emit({'result': 'PHASE', 'run_id': run_id, 'phase': phase, 't': time.monotonic(),
                          'drained_at_boundary': discarded, 'rx_dropped': bus.dropped, 'clock_id': clock_id})
            received = bus.receive(.01)
            if received:
                frame, _ = received
                emit({'result': 'OBS_FRAME', 'phase': phase, **frame_json(frame),
                      'rx_dropped': bus.dropped})
    finally:
        bus.close()
        for sig, handler in old.items():
            signal.signal(sig, handler)
        emit({'result': 'OBSERVER_STOPPED', 'run_id': run_id, 'rx_dropped': bus.dropped})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--interface', default='can0')
    parser.add_argument('--duration', type=float, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--environment',choices=('physical','vcan'),default='physical')
    args = parser.parse_args()
    if not 0 < args.duration <= 86400:
        parser.error('duration must be in (0, 86400]')
    observe(args.interface, args.duration, args.run_id,environment=args.environment)


if __name__ == '__main__':
    main()
