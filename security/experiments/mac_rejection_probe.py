"""Bounded keyless MAC rejection probe; compare its ledger with IVI product logs."""
import argparse
import json
import time
from pathlib import Path
from security.experiments.can_capture import CaptureSocket
from security.experiments.trial_observer import healthy


def forge(raw, auth):
    raw=bytearray(raw);auth=bytearray(auth)
    raw[0]=100 if raw[0]!=100 else 102
    auth[0]^=1
    auth[4:]=((int.from_bytes(auth[4:],'big')+50)&0xffffffff).to_bytes(4,'big')
    return bytes(raw),bytes(auth)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--i-am-on-a-test-bus',action='store_true')
    args=parser.parse_args()
    if not args.i_am_on_a_test_bus:parser.error('isolated test bus required')
    healthy('can0')
    args.out.mkdir(parents=True,exist_ok=False)
    with (args.out/'probe.jsonl').open('x') as log:
        def emit(row):
            log.write(json.dumps(row)+'\n');log.flush()
            print(json.dumps(row),flush=True)
        bus=CaptureSocket('can0',transmit=True)
        try:
            for trial in range(1,31):
                # Drain during spacing, so the next source pair is freshly observed.
                until=time.monotonic()+.5
                while time.monotonic()<until:
                    item=bus.receive(.02)
                    if item and item[0].error:raise RuntimeError('CAN error')
                raw=None;pair=None;deadline=time.monotonic()+3
                while time.monotonic()<deadline:
                    item=bus.receive(.02)
                    if not item:continue
                    frame,own=item
                    if frame.error:raise RuntimeError('CAN error')
                    if own:continue
                    if frame.can_id==0x100:raw=frame
                    elif frame.can_id==0x102 and raw is not None and 0<=frame.t-raw.t<=.1:
                        pair=(raw.data,frame.data);break
                if pair is None:raise RuntimeError('fresh normal raw/auth pair missing')
                payload,auth=forge(*pair)
                emit({'result':'PREPARED','trial':trial,'raw':payload.hex(),'auth':auth.hex(),
                      'source_raw':pair[0].hex(),'source_auth':pair[1].hex()})
                for cid,data in ((0x100,payload),(0x102,auth)):
                    bus.send(cid,data)
                    emit({'result':'TX','trial':trial,'can_id':cid,'data':data.hex()})
            emit({'result':'COMPLETE','trials':30,'rx_dropped':bus.dropped})
        finally:bus.close()


if __name__=='__main__':main()
