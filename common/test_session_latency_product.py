"""Actual session-v2 ECU→Qt timing identity and current CSV analysis over vcan.

This is instrumentation acceptance with a small target, not physical TC-PERF-001
acceptance. Preserve coalesced/unknown/pending outcomes rather than require them
to disappear for a green test. No cross-host clock subtraction or real key.
"""
import argparse
from contextlib import ExitStack
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from test_session_ids_products import records,stop,wait_file

ROOT=Path(__file__).resolve().parent.parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('ecu','ivi','policy'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--out-parent',type=Path,required=True)
    parser.add_argument('--samples',type=int,choices=(30,300,1000),default=30)
    args=parser.parse_args();interface=os.environ.get('CAPSTONE_SESSION_TEST_INTERFACE','')
    if not interface:return 77
    if not re.fullmatch('vcan[0-9]+',interface) or not Path('/sys/devices/virtual/net',interface).is_dir():
        raise ValueError('existing explicit virtual CAN required')
    args.out_parent.mkdir(parents=True,exist_ok=True)
    output=Path(tempfile.mkdtemp(prefix='session-latency-',dir=args.out_parent))
    target=args.samples;run_id='VCAN-PERF-SESSION'
    lifetime_s=10+target*.1
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    with tempfile.TemporaryDirectory(prefix='latency-private-') as temporary,ExitStack() as cleanup:
        private=Path(temporary);key=private/'dummy.key';key.write_bytes(bytes(range(32)));key.chmod(0o600)
        runtime=private/'runtime';runtime.mkdir(mode=0o700)
        ready=private/'ready.json';observations=output/'receiver.jsonl';raw=output/'latency.csv'
        ivi_log=cleanup.enter_context((output/'ivi.log').open('w'))
        ivi=subprocess.Popen([args.ivi,'--interface',interface,'--protocol','session-v2','--secoc-key',str(key),
            '--session-policy',args.policy,'--run-id',run_id,'--ready-file',str(ready),
            '--observation-jsonl',str(observations),'--latency-csv',str(raw),'--latency-samples',str(target),
            '--windowed','--demo-exit-ms',str(int(lifetime_s*1000))],
            env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',
                QSG_RENDER_LOOP='basic',XDG_RUNTIME_DIR=str(runtime)),stdout=ivi_log,stderr=subprocess.STDOUT)
        cleanup.callback(stop,ivi);wait_file(ready,[ivi])
        ecu_log=cleanup.enter_context((output/'ecu.log').open('w'))
        ecu=subprocess.Popen([args.ecu,'--interface',interface,'--sensor-mode','constant','--protocol','session-v2',
            '--secoc','on','--key',str(key),'--session-policy',args.policy],stdout=ecu_log,stderr=subprocess.STDOUT)
        cleanup.callback(stop,ecu)
        assert ivi.wait(timeout=lifetime_s+2)==0,'Qt timing target incomplete; raw evidence retained'
        stop(ecu)
    analyzer=ROOT/'ivi_platform/scripts/measure_latency.py'
    measured=subprocess.run([sys.executable,str(analyzer),'--input',str(raw),'--output',str(output/'summary.csv'),
        '--expected-samples',str(target)],capture_output=True,text=True,timeout=5)
    (output/'analysis.stdout').write_text(measured.stdout);(output/'analysis.stderr').write_text(measured.stderr)
    report=json.loads(measured.stdout)
    assert report['run_id']==run_id and report['boot_id']==boot
    assert report['counts']['FRAME_SWAPPED']>=target
    assert measured.returncode==(0 if report['status']=='COMPLETE' else 1)
    service={int(row['measurement_sequence']):row for row in records(observations) if row.get('result')=='SESSION_PUBLICATION'}
    model={int(row['measurement_sequence']):row for row in records(observations) if row.get('result')=='VIEW_MODEL_PUBLICATION'}
    with raw.open() as stream:rows=list(csv.DictReader(stream))
    for row in rows:
        assert row['run_id']==run_id and row['boot_id']==boot
        sample=int(row['sample_id'])
        assert sample in service and sample in model,'recorded sample lacks real service/ViewModel identity'
        if row['stage'] in ('T1','T2'):
            field={'T1':'t1_received_ns','T2':'t2_published_ns'}[row['stage']]
            assert int(row['timestamp_ns'])==int(service[sample][field])==int(model[sample][field])
        elif row['stage']=='T3':assert int(row['timestamp_ns'])==int(model[sample]['t3_view_model_ns'])
    result={'status':'PASS','scope':'Actual same-host session-v2 ECU/Qt over vcan, offscreen software/basic; timing identity and analysis only',
        'target':target,'render_measurement_status':report['status'],'report':report,
        'service_view_model_timestamp_identity_verified':True,'boot_identity_verified':True,
        'physical_performance_acceptance':False,'key_retained':False,
        'files_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir()) if p.is_file()},
        'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            (Path(__file__),analyzer,ROOT/'ivi_platform/ui_qml/main.cpp',ROOT/'ivi_platform/ui_qml/latency_recorder.h')},
        'executables_sha256':{name:hashlib.sha256(Path(getattr(args,name)).read_bytes()).hexdigest() for name in ('ecu','ivi')}}
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(result,output=str(output))))
    return 0


if __name__=='__main__':raise SystemExit(main())
