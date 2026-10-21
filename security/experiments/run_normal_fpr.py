"""Managed normal-only wire-FPR capture; no attacks, no CAN reconfiguration."""
import argparse
import json
import math
from pathlib import Path
import re
import subprocess
import time

from security.attack_simulator import validate_interface, is_virtual_interface
from security.experiments.run_ablation import Child, render_command, file_hash
from security.experiments.validate_m5_settings import validate
from security.experiments.analyze_normal_fpr import analyze, POLICY


def run(settings,args):
    root=Path(args.output_dir);root.mkdir(parents=True,exist_ok=False)
    (root/'settings.json').write_text(json.dumps(settings,indent=2),encoding='utf-8')
    duration=args.warmup+args.windows+1
    life=duration+30
    values={'run_id':args.run_id,'secoc':'on','lifetime_s':str(life),'lifetime_ms':str(round(life*1000))}
    children=[];manifest={'schema':'normal-wire-fpr-v1','run_id':args.run_id,
        'environment':args.environment,'interface':args.interface,'normal_only':True,
        'source_mode':'controlled-signed-SOC75-fixture','windows':args.windows,
        'warmup_ns':round(args.warmup*1e9),'window_policy':POLICY,
        'managed_alive_until_capture_end':False,'status':'INVALID','reason':None,
        'official_acceptance':False}
    try:
        for role,name,expected in (
                ('receiver_on','receiver',{'secoc_on':True}),
                ('normal_sender','normal',{'secoc_on':True}),
                ('ids','ids-console',{'mode':'rules+if','send_alerts':True})):
            child=Child(render_command(settings[role],values),root,name);children.append(child)
            child.ready(args.run_id)
            ready=[r for r in child.snapshot() if r.get('result')=='READY'][-1]
            if any(type(ready.get(k)) is not type(v) or ready[k]!=v for k,v in expected.items()):
                raise ValueError(name+' readiness mismatch')
        observer_values={**values,'lifetime_s':str(duration),'lifetime_ms':str(round(duration*1000))}
        observer=Child(render_command(settings['observer'],observer_values),root,'bus');children.append(observer)
        observer.ready(args.run_id)
        deadline=time.monotonic()+duration+5
        while observer.process.poll() is None:
            if any(c.process.poll() is not None for c in children[:-1]):
                raise RuntimeError('managed normal/receiver/IDS exited during capture')
            if time.monotonic()>deadline:raise TimeoutError('observer did not terminate after bounded capture')
            time.sleep(.05)
        if observer.process.returncode!=0 or any(c.process.poll() is not None for c in children[:-1]):
            raise RuntimeError('capture or managed child failed at completion')
        observer.stop()  # drain final END before examining evidence
        end=[r for r in observer.snapshot() if r.get('result')=='END']
        if len(end)!=1 or end[0].get('status')!='COMPLETE':raise ValueError('complete observer END required')
        manifest.update(status='COMPLETE',managed_alive_until_capture_end=True)
    except KeyboardInterrupt:
        manifest.update(reason='INTERRUPTED',interrupted=True)
    except (OSError,ValueError,KeyError,TypeError,RuntimeError,TimeoutError,subprocess.SubprocessError) as error:
        manifest.update(reason=str(error))
    finally:
        for child in reversed(children):
            try:child.stop()
            except (OSError,RuntimeError,subprocess.SubprocessError) as error:
                manifest.update(status='INVALID',reason='cleanup: '+str(error))
        manifest['files']={p.name:file_hash(p) for p in root.iterdir() if p.is_file()}
        (root/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    if manifest['status']=='COMPLETE':
        try:result=analyze(root)
        except (OSError,ValueError,TypeError,KeyError,AttributeError) as error:
            result={'status':'INVALID','reason':str(error),'official_acceptance':False}
    else:result={'status':'INVALID','reason':manifest['reason'],'official_acceptance':False}
    (root/'fpr-result.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings',required=True);parser.add_argument('--output-dir',required=True)
    parser.add_argument('--run-id',required=True);parser.add_argument('--interface',required=True)
    parser.add_argument('--environment',choices=('vcan','physical-can'),required=True)
    parser.add_argument('--windows',type=int,default=100);parser.add_argument('--warmup',type=float,default=5)
    parser.add_argument('--confirm-product-ecu-stopped',action='store_true')
    parser.add_argument('--confirm-isolated-test-bus',action='store_true')
    args=parser.parse_args(argv)
    if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}',args.run_id) is None:parser.error('unsafe run-id')
    if not 1<=args.windows<=260 or not math.isfinite(args.warmup) or not 0<=args.warmup<=8:
        parser.error('windows must be 1..260 and warmup 0..8 seconds; all children expire within 300s')
    if not args.confirm_product_ecu_stopped:parser.error('controlled fixture requires product ECU stopped')
    try:
        validate_interface(args.interface)
        virtual=is_virtual_interface(args.interface)
        if virtual!=(args.environment=='vcan'):raise ValueError('actual interface type/environment mismatch')
        if not virtual and not args.confirm_isolated_test_bus:raise ValueError('physical CAN requires isolated test bus')
        settings=json.loads(Path(args.settings).read_text());validate(settings,args.environment)
        result=run(settings,args)
        print(json.dumps({'status':result['status'],'output_dir':args.output_dir,
                          'official_acceptance':False}));return 0 if result['status']=='PASS' else 2
    except (OSError,ValueError,TypeError) as error:
        print(json.dumps({'status':'INVALID','reason':str(error)}));return 2


if __name__=='__main__':raise SystemExit(main())
