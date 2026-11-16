"""Run the actual ECU executable against an authenticated vcan test peer.

Explicit public dummy key only. Does not install services or use physical CAN.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ecu", required=True)
    parser.add_argument("--peer", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--out-parent",required=True,type=Path)
    args = parser.parse_args()
    name = os.environ.get("CAPSTONE_SESSION_TEST_INTERFACE", "")
    if not name:
        print("SKIP: CAPSTONE_SESSION_TEST_INTERFACE not selected")
        return 77
    if not name.startswith("vcan") or "/" in name or not Path("/sys/devices/virtual/net", name).is_dir():
        raise ValueError("actual ECU smoke requires an existing virtual vcan")
    args.out_parent.mkdir(parents=True,exist_ok=True)
    output=Path(tempfile.mkdtemp(prefix='input-lineage-',dir=args.out_parent))
    results=[]
    with tempfile.TemporaryDirectory(prefix="ecu-input-") as directory:
        private=Path(directory);private.chmod(0o700)
        key = Path(directory) / "public-dummy-key.bin"
        key.write_bytes(bytes(range(32)))
        key.chmod(0o600)
        profile=private/'profile.csv'
        raw=b'# public synthetic test data\r\nvoltage,current,temperature\r\n'+b'42,-2,25.5\r\n'*40
        profile.write_bytes(raw)
        soh=private/'soh.csv';soh_raw=b'elapsed_s,estimated_capacity_ah\r\n0,50\r\n10,45\r\n';soh.write_bytes(soh_raw)
        for mode,intent in (('constant','standalone'),('profile_csv','standalone'),
                            ('profile_csv','fresh'),('profile_csv','resume'),
                            ('random_walk','fresh'),('random_walk','resume')):
            label=mode+'-'+intent;log=output/(label+'.log')
            tail=['--sensor-mode',mode]
            if mode=='profile_csv':tail+=['--profile',str(profile),'--soh-profile',str(soh)]
            checkpoint=private/(mode+'.state')
            if intent!='standalone':
                tail+=['--checkpoint',str(checkpoint),'--start-intent',intent,
                    '--checkpoint-period-ms','100','--checkpoint-flush-ms','1000','--checkpoint-max-age-ms','60000',
                    '--restart-wait-ms','200','--restart-retry-ms','50','--restart-notice-attempts','2']
            with log.open('w+') as stream:
                child=subprocess.Popen([args.ecu,'--interface',name,'--secoc','on','--protocol','session-v2',
                    '--session-policy',args.policy,'--key',str(key)]+tail,stdout=stream,stderr=subprocess.STDOUT)
                try:
                    peer=subprocess.run([args.peer,'--ivi-only'],capture_output=True,text=True,timeout=12)
                    (output/(label+'-peer.log')).write_text(peer.stdout+peer.stderr)
                    if peer.returncode or child.poll() is not None:raise RuntimeError('actual ECU authenticated input/session failed')
                finally:
                    if child.poll() is None:
                        child.terminate()
                        try:child.wait(timeout=3)
                        except subprocess.TimeoutExpired:child.kill();child.wait(timeout=3)
                    stream.flush()
                stream.seek(0);text=stream.read()
                if child.returncode or 'security protocol=session-v2' not in text:
                    raise RuntimeError('actual ECU input failed: '+text[:4000])
            rows=[json.loads(line) for line in text.splitlines() if line.startswith('{')]
            lineage=[row for row in rows if row.get('result')=='ECU_INPUT_LINEAGE']
            assert len(lineage)==1
            row=lineage[0];configuration=row['configuration'];state=row['state']
            assert row['schema']=='ecu-input-lineage-v1' and row['start_intent']==intent
            assert configuration['source_mode']==mode and configuration['ground_truth_label']=='unattested'
            assert configuration['sensor_units']=={'voltage':'V','current':'A','temperature':'degC'}
            assert str(private) not in json.dumps(row) and 'public-dummy-key' not in json.dumps(row)
            if mode=='profile_csv':
                assert configuration['sensor']['input']=={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
                assert configuration['sensor']['rows']==40
                assert configuration['soh']['input']=={'bytes':len(soh_raw),'sha256':hashlib.sha256(soh_raw).hexdigest()}
            if intent=='resume':
                prior=next(r['lineage'] for r in results if r['case']==mode+'-fresh')
                assert row['configuration']==prior['configuration'] and row['instance_id']!=prior['instance_id']
                assert state['soh_elapsed_s']>0
                if mode=='profile_csv':assert state['profile_index']>0
                else:assert state['rng_state_sha256']!=prior['state']['rng_state_sha256']
            else:assert state['soh_elapsed_s']==0 and state['profile_index']==0
            results.append({'case':label,'lineage':row,'authenticated_bms_verified':10,'exit_code':child.returncode})
        # Changed CSV bytes must not restore an old snapshot under the old identity.
        profile.write_bytes(raw+b'41,-2,25\n')
        changed=subprocess.run([args.ecu,'--interface',name,'--secoc','on','--protocol','session-v2',
            '--session-policy',args.policy,'--key',str(key),'--sensor-mode','profile_csv','--profile',str(profile),
            '--soh-profile',str(soh),'--checkpoint',str(private/'profile_csv.state'),'--start-intent','resume',
            '--checkpoint-period-ms','100','--checkpoint-flush-ms','1000','--checkpoint-max-age-ms','60000',
            '--restart-wait-ms','200','--restart-retry-ms','50','--restart-notice-attempts','2'],
            capture_output=True,text=True,timeout=5)
        (output/'changed-profile.log').write_text(changed.stdout+changed.stderr)
        assert changed.returncode==2 and 'checkpoint restore rejected' in changed.stderr
        assert 'ECU_INPUT_LINEAGE' not in changed.stdout
        # Bad CSV must fail before attempting to open even a deliberately absent CAN.
        profile.write_text('voltage,current,temperature\n42,-2,nan\n')
        invalid=subprocess.run([args.ecu,'--interface','vcan-missing-input-test','--protocol','legacy-v1','--secoc','off',
            '--sensor-mode','profile_csv','--profile',str(profile)],capture_output=True,text=True,timeout=5)
        (output/'invalid-profile.log').write_text(invalid.stdout+invalid.stderr)
        assert invalid.returncode==2 and 'nonfinite profile temperature' in invalid.stderr and 'CAN open failed' not in invalid.stderr
    result={'status':'PASS','scope':'actual ECU/session-v2/vcan; public synthetic inputs; no physical ADC test',
        'cases':results,'changed_profile_resume_refused':True,'nonfinite_rejected_before_CAN':True,'key_retained':False}
    (output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':'PASS','source_cases':len(results),'output':str(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
