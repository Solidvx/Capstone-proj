"""Opt-in Linux vcan integration smoke; never selects a physical interface."""
import argparse
import json
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from security.attack_simulator import is_virtual_interface, validate_interface
from security.experiments.run_ablation import Child, main as run_matrix
from security.experiments.summarize_ablation import summarize
from security.can_socket import SocketCanTransport
from security.secoc_tamper_fixture import TAMPERED


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--interface',required=True)
    parser.add_argument('--receiver-bin',required=True)
    args=parser.parse_args()
    validate_interface(args.interface)
    if not is_virtual_interface(args.interface):parser.error('vcan only')
    root=Path(tempfile.mkdtemp(prefix='capstone-review-vcan-'))
    key=root/'dummy-key.bin';key.write_bytes(bytes(range(32)))
    python=sys.executable
    sender=[python,'-m','security.experiments.normal_sender','--interface',args.interface,
            '--secoc','on','--key',str(key),'--run-id','training','--duration','8']
    with (root/'training-sender.jsonl').open('x') as stream:
        process=subprocess.Popen(sender,stdout=stream)
        try:
            time.sleep(.2)
            subprocess.run([python,'-m','security.capture_normal','--interface',args.interface,
                '--duration','4','--output',str(root/'normal.jsonl'),
                '--manifest',str(root/'normal.manifest.json')],check=True)
        finally:
            process.terminate();process.wait(timeout=3)
    receiver=['env','QT_QPA_PLATFORM=offscreen','QT_QUICK_BACKEND=software',args.receiver_bin,
        '--interface',args.interface,'--secoc-key',str(key),'--run-id','{run_id}',
        '--observation-jsonl','-','--demo-exit-ms','{lifetime_ms}']
    tamper_dir=root/'tamper';tamper_dir.mkdir()
    tamper_receiver=Child([v.replace('{run_id}','tamper-review').replace('{lifetime_ms}','10000')
                          for v in receiver],tamper_dir,'receiver')
    try:
        tamper_receiver.ready('tamper-review')
        subprocess.run([python,'-m','security.secoc_tamper_fixture','--interface',args.interface,
            '--key',str(key),'--counter-start','0','--inter-pair-delay','.2',
            '--confirm-ecu-stopped','--confirm-receiver-reset',
            '--log',str(tamper_dir/'fixture.json')],check=True)
        time.sleep(.1)
        with SocketCanTransport(args.interface) as bus:bus.send(0x100,TAMPERED)
        time.sleep(.25)
    finally:
        tamper_receiver.stop()
    rows=tamper_receiver.snapshot()
    auth=[r for r in rows if r.get('result')=='FRAME' and r.get('can_id')==0x102]
    if [r['process_result'] for r in auth]!=[2,3,2] or [auth[0]['soc'],auth[2]['soc']]!=[75,70] \
            or 'reason=MAC_FAIL' not in auth[1]['message']:
        raise RuntimeError('live MAC tamper/recovery acceptance failed')
    if not any(r.get('result')=='TIMEOUT' and r.get('source_data')==TAMPERED.hex() for r in rows):
        raise RuntimeError('timer-only pending rejection observation missing')
    settings={
        'receiver_binary_sha256':hashlib.sha256(Path(args.receiver_bin).read_bytes()).hexdigest(),
        'python_version':sys.version,
        'observer':[python,'-m','security.experiments.bus_observer','--interface',args.interface,
                    '--run-id','{run_id}','--duration','{lifetime_s}'],
        'receiver_on':receiver,
        'receiver_off':receiver+['--experiment-secoc-off','--confirm-isolated-test-bus'],
        'normal_sender':sender[:-3]+['{run_id}','--duration','{lifetime_s}'],
        'ids':[python,'-m','security.ids.runtime','--interface',args.interface,
               '--train-normal',str(root/'normal.jsonl'),'--normal-manifest',str(root/'normal.manifest.json'),
               '--secoc-key',str(key),'--run-id','{run_id}',
               '--log',str(root/'ids-{run_id}.jsonl'),'--duration','{lifetime_s}','--send-alerts']}
    config=root/'settings.json';config.write_text(json.dumps(settings,indent=2))
    code=run_matrix(['--settings',str(config),'--output-dir',str(root/'matrix'),
        '--run-id','review-vcan','--environment','vcan','--interface',args.interface,
        '--trials','1','--baseline','.5','--warmup','1.2','--drain','.5',
        '--cooldown','.5','--attack-duration','.3','--flood-rate','1000','--confirm-product-ecu-stopped'])
    result=summarize(root/'matrix')
    (root/'summary.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({'artifact_dir':str(root),'matrix_complete':result['matrix_complete'],
                      'official_1200_complete':result['official_1200_complete']}),flush=True)
    return code or (0 if result['matrix_complete'] else 2)


if __name__=='__main__':raise SystemExit(main())
