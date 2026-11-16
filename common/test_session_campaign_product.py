"""Real local actors over existing vcan; no SSH/Pi or IF performance claim."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from collections import Counter

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from security.experiments.session_campaign import run_case


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('ecu','ivi','policy'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--out-parent',type=Path,required=True)
    parser.add_argument('--trials',type=int,choices=(1,2,3),default=2)
    parser.add_argument('--attack',choices=('fuzzy','flooding','spoofing','replay'),default='fuzzy')
    args=parser.parse_args()
    interface=os.environ.get('CAPSTONE_SESSION_TEST_INTERFACE','')
    if not interface:return 77
    if not interface.startswith('vcan') or not Path('/sys/devices/virtual/net',interface).is_dir():
        raise ValueError('explicit existing vcan only')
    args.ecu=str(Path(args.ecu).resolve());args.ivi=str(Path(args.ivi).resolve());args.policy=str(Path(args.policy).resolve())
    args.out_parent=args.out_parent.resolve();args.out_parent.mkdir(parents=True,exist_ok=True)
    output=Path(tempfile.mkdtemp(prefix='session-campaign-',dir=args.out_parent))
    os.chdir(ROOT)
    with tempfile.TemporaryDirectory(prefix='sc-private-') as temporary:
        private=Path(temporary);key=private/'dummy.key';key.write_bytes(bytes(range(32)));key.chmod(0o600)
        runtime=private/'runtime';runtime.mkdir(mode=0o700)
        logs=output/'ids';logs.mkdir(mode=0o700)
        config=private/'ids.json';config.write_text(json.dumps({'python':sys.executable,'repository':str(ROOT),
            'log_directory':str(logs),'mode':'rules-only','frame_budget':2,'expiry_ms':1000}))
        def wrapped(command):
            return [sys.executable,'-m','security.experiments.remote_process','--run-id','{run_id}',
                    '--duration','{lifetime_s}','--']+command
        receiver=['env','QT_QPA_PLATFORM=offscreen','QT_QUICK_BACKEND=software',
            'XDG_RUNTIME_DIR='+str(runtime)]+wrapped([args.ivi,'--interface','{interface}','--protocol','session-v2',
            '--session-policy',args.policy,'--secoc-key',str(key),'--run-id','{run_id}','--observation-jsonl','-'])
        manager=wrapped([sys.executable,str(ROOT/'adaptive_ecu/scripts/supervise_ecu.py'),'--ecu',args.ecu,
            '--checkpoint',str(private/'state'),'--initial-intent','fresh','--stop-timeout','1','--startup-timeout','10',
            '--heartbeat-timeout','1','--max-crash-restarts','0','--ids-settings',str(config),'--',
            '--interface','{interface}','--sensor-mode','constant','--protocol','session-v2','--secoc','on',
            '--key',str(key),'--session-policy',args.policy,'--checkpoint-period-ms','100','--checkpoint-flush-ms','1000',
            '--checkpoint-max-age-ms','60000','--restart-wait-ms','200','--restart-retry-ms','50','--restart-notice-attempts','2'])
        commands={'receiver_on':receiver,'ecu_ids':manager}
        for role in ('observer_a','observer_b'):
            commands[role]=[sys.executable,'-m','security.experiments.trial_observer','--interface','{interface}',
                '--environment','vcan','--duration','{lifetime_s}','--run-id','{run_id}']
        commands['attacker']=[sys.executable,'-m','security.experiments.can_attack_worker','--interface','{interface}',
            '--environment','vcan','--duration','{lifetime_s}','--run-id','{run_id}','--i-am-on-a-test-bus']
        commands['ids_fetch']=[sys.executable,'-m','security.experiments.session_ids_log','--log-root',str(logs),
            '--generation','{ids_generation}','--kind','{log_kind}']
        for role in ('health_a','health_b','health_c'):
            commands[role]=[sys.executable,'-m','security.experiments.can_health','--interface','{interface}','--environment','vcan']
        settings={'commands':commands,'environment':'vcan','ids_mode':'rules-only'}
        group=output/('C3-'+args.attack);group.mkdir(mode=0o700)
        args.run_id='VCAN-SC';args.per_case=args.trials;args.interface=interface;args.sensor_mode='constant'
        args.baseline=2.;args.duration=2.;args.post=2.;args.quiet_timeout=20.;args.rate=1000.
        manifest,rows=run_case(settings,args,3,args.attack,1,group/'session-001')
        expected_response='PASS'
        summary={'status':'PASS' if manifest['status']=='COMPLETE' and manifest['cleanup_confirmed'] and
                    len(rows)==args.trials and all(row['status']=='VALID' and row['ecu_ids_type_result']=='MATCH' and
                    row['ivi_diagnostic_type_result']=='MATCH' and row['ivi_view_model_type_result']=='MATCH' and
                    row.get('attack_response',{}).get('status')==expected_response for row in rows) else 'FAIL',
            'scope':'actual local ECU/owned IDS/Qt/observer/worker actors; vcan; rules-only development; no SSH/Pi/IF performance',
            'process_sessions':1,'planned_trials':args.trials,'attempt_rows':len(rows),
            'completed_trials':sum(bool(row.get('trial_completed')) for row in rows),
            'valid_trials':sum(bool(row.get('trial_completed')) and row['status']=='VALID' for row in rows),
            'case_status':manifest['status'],'cleanup_confirmed':manifest['cleanup_confirmed']}
        summary.update(attack=args.attack,expected_response=expected_response,
            response_target_met=summary['status']=='PASS',
            response_note='Replay starts at the first repeated IVI auth with a verified rejection witness; not raw or physical TX.'
                if args.attack=='replay' else 'Two development trials are not a performance population.')
        summary['response_results']=dict(Counter(row.get('attack_response',{}).get('status','NOT_RECORDED') for row in rows))
        (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        print(json.dumps(dict(summary,output=str(output))))
        return 0 if summary['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
