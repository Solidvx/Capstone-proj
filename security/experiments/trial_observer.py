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


def healthy(channel):
    info = inspect_interface(channel, 'physical')
    if info['bitrate'] != 500000 or info['state'] != 'ERROR-ACTIVE':
        raise RuntimeError('CAN must be ERROR-ACTIVE at 500000 bit/s')
    return info


def emit(row):
    print(json.dumps(row), flush=True)


def observe(channel, duration, run_id, control_fd=0):
    healthy(channel)
    bus = CaptureSocket(channel)
    stopping = False
    def stop(signum, frame):
        nonlocal stopping
        stopping = True
    old = {sig: signal.signal(sig, stop) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    phase, pending = 'idle', b''
    deadline = time.monotonic() + duration
    try:
        emit({'result': 'READY', 'run_id': run_id})
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
                    emit({'result': 'PHASE', 'run_id': run_id, 'phase': phase,
                          'drained_at_boundary': discarded, 'rx_dropped': bus.dropped})
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
    args = parser.parse_args()
    if not 0 < args.duration <= 86400:
        parser.error('duration must be in (0, 86400]')
    observe(args.interface, args.duration, args.run_id)


if __name__ == '__main__':
    main()
