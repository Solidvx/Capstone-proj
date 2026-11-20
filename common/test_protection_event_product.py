"""Real ECU -> authenticated virtual CAN -> Qt -> durable protection records.

One controlled sender, temporary public dummy key, no physical CAN or services.
Tests explicit fresh/resume and supervisor recovery with a live dashboard.
Does not install or exercise systemd services.
"""
import argparse
from contextlib import ExitStack
import hashlib
import json
import os
import signal
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from test_protection_checkpoint_product import state, stop
from test_ecu_supervisor_recovery import child_pid, wait_for


def journal_events(directory):
    events=[]
    for path in sorted(directory.glob('events-*.jsonl')):
        for line in path.read_bytes().splitlines(keepends=True):
            if not line.endswith(b'\n'):break
            row=json.loads(line)
            assert hashlib.sha256((row['sequence']+'\n'+row['payload']).encode()).hexdigest()==row['sha256']
            events.append(json.loads(row['payload']))
    return events


def main():
    def interrupted(_signum,_frame):
        raise KeyboardInterrupt('protection product interrupted')
    signal.signal(signal.SIGTERM,interrupted)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ecu',required=True)
    parser.add_argument('--ivi',required=True)
    parser.add_argument('--policy',required=True)
    parser.add_argument('--out-parent',type=Path,required=True)
    args=parser.parse_args()
    interface=os.environ.get('CAPSTONE_SESSION_TEST_INTERFACE','')
    if not interface:return 77
    if not interface.startswith('vcan') or not Path('/sys/devices/virtual/net',interface).is_dir():
        raise ValueError('existing virtual CAN only')
    root=Path(__file__).resolve().parents[1]
    args.out_parent.mkdir(parents=True,exist_ok=True)
    output=Path(tempfile.mkdtemp(prefix='protection-event-',dir=args.out_parent))
    store=output/'event-store';store.mkdir(mode=0o700)
    event_policy=output/'event-policy.json'
    event_policy.write_text(json.dumps({'directory':str(store),'segment_bytes':1048576,
        'total_bytes':16777216,'warning_bytes':8388608,'min_free_bytes':1,'queue_capacity':128}))
    result={'status':'RUNNING','root':str(output),'cases':[]}
    children=[];observation_paths=[]
    def save():
        (output/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    save()
    with tempfile.TemporaryDirectory(prefix='protection-event-private-') as directory, ExitStack() as stack:
        private=Path(directory);private.chmod(0o700)
        key=private/'public-dummy.key';key.write_bytes(bytes(range(32)));key.chmod(0o600)
        runtime=private/'runtime';runtime.mkdir(mode=0o700)
        profile=private/'profile.csv'
        profile.write_text('voltage,current,temperature\n'+'42,-2,56\n'*3+'42,-2,61\n'*70+
                           '42,-2,25\n'*70+'42,-2,56\n'*70)
        (output/'public-synthetic-profile.csv').write_bytes(profile.read_bytes())
        checkpoint=private/'state'
        env=dict(os.environ,TMPDIR='/var/tmp',QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',
                 XDG_RUNTIME_DIR=str(runtime),XDG_CONFIG_HOME=str(private/'settings'))
        ecu_base=[args.ecu,'--interface',interface,'--key',str(key),'--secoc','on',
            '--protocol','session-v2','--session-policy',args.policy,'--sensor-mode','profile_csv','--profile',str(profile),
            '--checkpoint',str(checkpoint),'--checkpoint-period-ms','100','--checkpoint-flush-ms','2000',
            '--checkpoint-max-age-ms','60000','--restart-wait-ms','200','--restart-retry-ms','50','--restart-notice-attempts','3']

        def launch(name,intent,managed=False):
            ready=output/(name+'-ready.json');observations=output/(name+'-observations.jsonl')
            observation_paths.append(observations)
            log=stack.enter_context((output/(name+'-ivi.log')).open('w'))
            ivi=subprocess.Popen([args.ivi,'--interface',interface,'--secoc-key',str(key),
                '--protocol','session-v2','--session-policy',args.policy,'--event-policy',str(event_policy),
                '--ready-file',str(ready),'--observation-jsonl',str(observations),'--run-id',name,
                '--windowed','--demo-exit-ms','45000'],env=env,stdout=log,stderr=subprocess.STDOUT)
            children.append(ivi)
            deadline=time.monotonic()+6
            while not ready.exists():
                if ivi.poll() is not None or time.monotonic()>deadline:raise AssertionError('IVI READY failed')
                time.sleep(.02)
            log=stack.enter_context((output/(name+'-ecu.log')).open('w'))
            command=ecu_base+['--start-intent',intent]
            if managed:
                tail=ecu_base[1:]
                checkpoint_option=tail.index('--checkpoint')
                del tail[checkpoint_option:checkpoint_option+2]
                # Existing supervisor product-test bounds, not operating policy.
                command=[sys.executable,str(root/'adaptive_ecu/scripts/supervise_ecu.py'),
                    '--ecu',args.ecu,'--checkpoint',str(checkpoint),'--initial-intent',intent,
                    '--stop-timeout','.3','--startup-timeout','3','--heartbeat-timeout','.4',
                    '--max-crash-restarts','1','--',*tail]
            ecu=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT)
            children.append(ecu)
            return ecu,ivi

        def wait_record(ecu,ivi,predicate,timeout=10):
            deadline=time.monotonic()+timeout
            while time.monotonic()<deadline:
                assert ecu.poll() is None and ivi.poll() is None,'product actor stopped early'
                for event in reversed(journal_events(store)):
                    if event.get('category')=='protection-status' and predicate(event):return event
                time.sleep(.04)
            raise AssertionError('durable protection record did not satisfy predicate')

        def close(ecu,ivi,kill=False):
            stop(ivi);assert ivi.returncode==0,'IVI did not close cleanly'
            if kill:ecu.kill();ecu.wait(timeout=3)
            else:stop(ecu);assert ecu.returncode==0,'ECU did not close cleanly'

        try:
            ecu,ivi=launch('PROTECTION-FRESH','fresh')
            a=wait_record(ecu,ivi,lambda e:e['ecu_protection']['state']==3)
            saved=state(checkpoint);p=a['ecu_protection']
            assert (saved['lineage'],saved['incident'],saved['revision'])==(p['lineage_id'],p['incident_id'],int(p['revision']))
            close(ecu,ivi,kill=True)
            (output/'before-resume.checkpoint').write_bytes(checkpoint.read_bytes())
            result['cases'].append({'case':'fresh-shutdown','event_id':a['event_id'],'metadata':p})
            save()

            ecu,ivi=launch('PROTECTION-RESUME','resume')
            b=wait_record(ecu,ivi,lambda e:e.get('protection_link',{}).get('previous_event_id')==a['event_id'])
            q=b['ecu_protection'];link=b['protection_link']
            assert q['lineage_id']==p['lineage_id'] and q['incident_id']==p['incident_id']
            assert q['instance_id']!=p['instance_id'] and q['session_id']!=p['session_id']
            assert q['checkpoint_resumed'] and q['state']==3 and link['status']=='resumed'
            close(ecu,ivi)
            result['cases'].append({'case':'same-event-new-instance-and-session','event_id':b['event_id'],
                'previous_event_id':link['previous_event_id'],'metadata':q})
            save()

            ecu,ivi=launch('PROTECTION-NEW-DEMO','fresh')
            lineage_record=wait_record(ecu,ivi,lambda e:e['ecu_protection']['lineage_id']!=q['lineage_id'] and
                e.get('protection_link',{}).get('status')=='new-lineage')
            c=wait_record(ecu,ivi,lambda e:e['ecu_protection']['state']==3 and
                e['ecu_protection']['lineage_id']==lineage_record['ecu_protection']['lineage_id'])
            r=c['ecu_protection'];fresh_link=lineage_record['protection_link']
            assert r['incident_id']!=q['incident_id'] and not r['checkpoint_resumed']
            assert fresh_link['status']=='new-lineage' and fresh_link['prior_event_end_unconfirmed']
            assert 'previous_event_id' not in fresh_link
            result['cases'].append({'case':'fresh-does-not-close-old-event','event_id':c['event_id'],
                'lineage_record_id':lineage_record['event_id'],'metadata':r})
            save()
            closed=wait_record(ecu,ivi,lambda e:e['ecu_protection'].get('incident_id')==r['incident_id'] and
                e['ecu_protection']['phase']==2,timeout=20)
            recurrence=wait_record(ecu,ivi,lambda e:e['ecu_protection']['lineage_id']==r['lineage_id'] and
                e['ecu_protection']['phase']==1 and e['ecu_protection'].get('incident_id')!=r['incident_id'],timeout=12)
            assert int(closed['ecu_protection']['revision'])>int(r['revision'])
            assert recurrence['ecu_protection']['revision']=='1'
            assert recurrence['protection_link']['status']=='new-incident'
            close(ecu,ivi)
            result['cases'].extend([{'case':'cooling-closes-same-event','event_id':closed['event_id'],
                'metadata':closed['ecu_protection']},{'case':'recurrence-starts-new-event','event_id':recurrence['event_id'],
                'metadata':recurrence['ecu_protection']}])

            earlier_events={event['event_id'] for event in journal_events(store)}
            manager,ivi=launch('PROTECTION-AUTOMATIC','fresh',managed=True)
            supervisor_log=output/'PROTECTION-AUTOMATIC-ecu.log'
            before=wait_record(manager,ivi,lambda e:e['event_id'] not in earlier_events and e['ecu_protection']['state']==3 and
                e['ecu_protection']['lineage_id']!=r['lineage_id'])
            prior=before['ecu_protection']
            wait_for(manager,lambda:state(checkpoint).get('incident')==prior['incident_id'] and
                state(checkpoint).get('revision')==int(prior['revision']))
            old_pid=wait_for(manager,lambda:child_pid(supervisor_log,manager.pid))
            live_ivi_pid=ivi.pid
            os.kill(old_pid,signal.SIGKILL)
            new_pid=wait_for(manager,lambda:(pid if (pid:=child_pid(supervisor_log,manager.pid)) and pid!=old_pid else None))
            resumed=wait_record(manager,ivi,lambda e:e.get('protection_link',{}).get('previous_event_id')==before['event_id'] and
                e.get('protection_link',{}).get('status')=='resumed')
            current=resumed['ecu_protection']
            assert current['lineage_id']==prior['lineage_id'] and current['incident_id']==prior['incident_id']
            assert current['revision']==prior['revision'] and current['state']==3 and current['checkpoint_resumed']
            assert current['instance_id']!=prior['instance_id'] and current['session_id']!=prior['session_id']
            assert ivi.pid==live_ivi_pid and ivi.poll() is None,'dashboard was restarted during ECU recovery'
            assert not Path('/proc',str(old_pid)).exists(),'old ECU not reaped before replacement'
            close(manager,ivi)
            assert not Path('/proc',str(new_pid)).exists(),'manual manager stop left ECU alive'
            manager_text=supervisor_log.read_text()
            assert manager_text.count('crash recovery attempt=')==1 and manager_text.count('intent=resume')==1
            result['cases'].extend([
                {'case':'supervised-fresh-shutdown','event_id':before['event_id'],'metadata':prior},
                {'case':'automatic-resume-with-live-dashboard','event_id':resumed['event_id'],
                 'previous_event_id':before['event_id'],'metadata':current,
                 'same_dashboard_process':True,'old_ecu_reaped':True,'manual_stop_reaped_without_retry':True}])
            save()

            exported=output/'export'
            subprocess.run([sys.executable,str(root/'ivi_platform/scripts/export_event_history.py'),
                '--directory',str(store),'--out',str(exported)],check=True,capture_output=True,timeout=5)
            manifest=json.loads((exported/'manifest.json').read_text())
            rows=[json.loads(line)['event'] for line in (exported/'events.jsonl').read_text().splitlines()]
            assert hashlib.sha256((exported/'events.jsonl').read_bytes()).hexdigest()==manifest['sha256']
            assert not manifest['writer_marker_present']
            observed={}
            for path in observation_paths:
                for line in path.read_text().splitlines():
                    item=json.loads(line)
                    if item.get('result')=='AUTHENTICATED_DIAGNOSTIC' and item.get('kind')==8:
                        observed[(item['session_id'],item['sequence'],item['body_hex'])]=item
            protection=[row for row in rows if row.get('category')=='protection-status']
            semantic_keys=[(row['ecu_protection']['session_id'],row['ecu_protection']['body_hex']) for row in protection]
            assert len(semantic_keys)==len(set(semantic_keys)),'unchanged heartbeat generated duplicate event history'
            for event in protection:
                meta=event['ecu_protection']
                assert (meta['session_id'],meta['sequence'],meta['body_hex']) in observed
            assert all(any(row['event_id']==case['event_id'] for row in rows) for case in result['cases'])
            assert any(row['event_id']==lineage_record['event_id'] for row in rows)
            result.update(status='PASS',protection_records=len(protection),export_records=manifest['records'],
                authenticated_kind8_observations=len(observed),all_primary_records_matched_authenticated_body=True,
                unchanged_heartbeat_records_deduplicated=True,
                old_records_preserved=True,actors_reaped=True,dummy_key_retained=False)
        except BaseException as error:
            result.update(status='FAIL',error=str(error));save();raise
        finally:
            for child in reversed(children):stop(child)
    save();print(json.dumps(result,ensure_ascii=False));return 0


if __name__=='__main__':raise SystemExit(main())
