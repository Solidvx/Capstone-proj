"""Controlled M5 normal fixture. Never run alongside the product ECU."""
import argparse
import json
import time
import signal

from security.can_socket import SocketCanTransport
from security.attack_simulator import validate_interface, is_virtual_interface
from security.secoc_module import SecOcModule

BMS=bytes.fromhex('96BE1068FFEC4100')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--interface',required=True)
    parser.add_argument('--secoc',choices=('on','off'),required=True)
    parser.add_argument('--key',required=True)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--duration',type=float,default=60)
    parser.add_argument('--confirm-isolated-test-bus',action='store_true')
    args=parser.parse_args()
    validate_interface(args.interface)
    if not is_virtual_interface(args.interface) and not args.confirm_isolated_test_bus:
        parser.error('physical CAN requires isolated test bus confirmation')
    if not 0<args.duration<=300:parser.error('duration must be in (0,300]')
    signer=SecOcModule.from_key_file(args.key)
    running=True
    def stop(signum,frame):
        nonlocal running
        running=False
    signal.signal(signal.SIGINT,stop)
    signal.signal(signal.SIGTERM,stop)
    try:
        with SocketCanTransport(args.interface) as transport:
            print(json.dumps({'result':'READY','run_id':args.run_id,'secoc_on':args.secoc=='on'}),flush=True)
            deadline=time.monotonic()+args.duration
            next_send=time.monotonic()
            while running and time.monotonic()<deadline:
                if time.monotonic()<next_send:time.sleep(max(0,min(next_send,deadline)-time.monotonic()))
                if not running or time.monotonic()>=deadline:break
                pair=[(0x100,BMS)]
                if args.secoc=='on':pair.append((0x102,signer.sign(0x102,0x100,BMS).data))
                for index,(cid,data) in enumerate(pair):
                    if index:time.sleep(.002)
                    transport.send(cid,data)
                    print(json.dumps({'result':'NORMAL_TX','run_id':args.run_id,
                        'can_id':cid,'data':data.hex(),'timestamp_ns':str(time.monotonic_ns())}),flush=True)
                next_send+=.1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__=='__main__':raise SystemExit(main())
