"""Independent whole-bus observer, run on the same Node B clock as IVI."""
import argparse
import json
import time
from pathlib import Path

from security.can_socket import SocketCanTransport
from security.attack_simulator import validate_interface


def interface_stats(interface):
    result={}
    for name in ('rx_dropped','rx_errors','tx_errors'):
        try:result[name]=int((Path('/sys/class/net')/interface/'statistics'/name).read_text())
        except (OSError,ValueError):result[name]=None
    return result


def collect(transport,run_id,interface,duration,emit):
    before=interface_stats(interface)
    started=time.monotonic_ns()
    emit({'result':'READY','run_id':run_id,'interface':interface,
          'timestamp_ns':str(started),'requested_duration_s':duration,
          'stats_before':before,'rx_overflow_tracking':True})
    status='COMPLETE';reason=None;frames=0;code=0
    try:
        deadline=started+round(duration*1e9)
        while time.monotonic_ns()<deadline:
            frame=transport.receive()
            if frame:
                frames+=1
                emit({'result':'BUS_FRAME','run_id':run_id,
                    'timestamp_ns':str(time.monotonic_ns()),'can_id':frame.can_id,
                    'dlc':frame.dlc,'data':frame.data.hex(),'extended':frame.extended,
                    'remote':frame.remote,'error':frame.error})
    except KeyboardInterrupt:
        status='INTERRUPTED';reason='operator interrupt';code=130
    except (OSError,ValueError,RuntimeError) as error:
        status='INVALID';reason=str(error);code=2
    ended=time.monotonic_ns()
    emit({'result':'END','run_id':run_id,'interface':interface,
          'timestamp_ns':str(ended),'status':status,'reason':reason,'frames':frames,
          'stats_after':interface_stats(interface),'rx_overflow':transport.rx_overflow})
    return code


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--interface', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--duration', type=float, default=60)
    args = parser.parse_args()
    if not 0 < args.duration <= 86400: parser.error('invalid duration')
    validate_interface(args.interface)
    try:
        with SocketCanTransport(args.interface,track_rx_overflow=True) as transport:
            return collect(transport,args.run_id,args.interface,args.duration,
                           lambda row:print(json.dumps(row),flush=True))
    except KeyboardInterrupt:
        return 130
    except (OSError,ValueError,RuntimeError) as error:
        print(json.dumps({'result':'ERROR','run_id':args.run_id,'reason':str(error)}),flush=True)
        return 2


if __name__=='__main__':raise SystemExit(main())
