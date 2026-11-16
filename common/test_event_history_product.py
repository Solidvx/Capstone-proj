"""Restart the actual Qt application and verify its event history survives."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ivi',required=True);parser.add_argument('--out-parent',required=True,type=Path)
    parser.add_argument('--supervisor')
    parser.add_argument('--stall-preload')
    args=parser.parse_args();args.out_parent.mkdir(parents=True,exist_ok=True)
    if args.stall_preload and not args.supervisor:parser.error('stall fixture requires supervisor')
    output=Path(tempfile.mkdtemp(prefix='history-product-',dir=args.out_parent))
    store=output/'store';store.mkdir(mode=0o700)
    policy=output/'policy.json';policy.write_text(json.dumps({'directory':str(store),'segment_bytes':65536,'total_bytes':1048576,
        'warning_bytes':524288,'min_free_bytes':1,'queue_capacity':64}))
    snapshots=[]
    prefix=[sys.executable,args.supervisor,'--'] if args.supervisor else []
    with tempfile.TemporaryDirectory(prefix='history-runtime-') as runtime:
        for index,scenario in enumerate(('warning','normal')):
            observations=output/('run-'+str(index)+'.jsonl')
            result=subprocess.run(prefix+[args.ivi,'--demo',scenario,'--windowed','--event-policy',str(policy),
                '--demo-exit-ms','600','--observation-jsonl',str(observations)],
                env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',XDG_RUNTIME_DIR=runtime),
                capture_output=True,text=True,timeout=8)
            (output/('run-'+str(index)+'.log')).write_text(result.stdout+result.stderr)
            assert result.returncode==0,result.stderr
            if args.supervisor:
                assert 'DASHBOARD_QUIT_NOTIFIED' in result.stderr and 'DASHBOARD_STOP_TIMEOUT' not in result.stderr
            rows=[json.loads(line) for line in observations.read_text().splitlines()]
            snapshots.append(next(row for row in rows if row['result']=='EVENT_HISTORY_SNAPSHOT'))
    assert snapshots[0]['events'],'first run has no event'
    assert all(event in snapshots[1]['events'] for event in snapshots[0]['events']),'previous events did not reach actual ViewModel'
    assert '실패' not in snapshots[1]['storage_status'] and '이번 실행' not in snapshots[1]['storage_status']
    files=list(store.glob('events-*.jsonl'));assert len(files)>=2
    exporter=Path(__file__).resolve().parent.parent/'ivi_platform/scripts/export_event_history.py'
    exported=output/'export'
    result=subprocess.run([sys.executable,str(exporter),'--directory',str(store),'--out',str(exported)],capture_output=True,text=True,timeout=5)
    assert result.returncode==0,result.stderr
    manifest=json.loads((exported/'manifest.json').read_text())
    assert manifest['status']=='COMPLETE' and manifest['records']>=len(snapshots[0]['events'])
    exported_rows=[json.loads(line) for line in (exported/'events.jsonl').read_text().splitlines()]
    assert all(any(row['event']['display']==event for row in exported_rows) for event in snapshots[0]['events'])
    stall_verified=False
    if args.stall_preload:
        stalled=output/'stall-event-store';stalled.mkdir(mode=0o700)
        stalled_policy=output/'stall-policy.json'
        config=json.loads(policy.read_text());config['directory']=str(stalled)
        stalled_policy.write_text(json.dumps(config))
        seen=output/'fsync-stall-seen'
        with tempfile.TemporaryDirectory(prefix='history-stall-runtime-') as runtime:
            result=subprocess.run(prefix+[args.ivi,'--demo','warning','--windowed',
                '--event-policy',str(stalled_policy),'--demo-exit-ms','600'],
                env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',
                         XDG_RUNTIME_DIR=runtime,LD_PRELOAD=args.stall_preload,CAPSTONE_STALL_SEEN_FILE=str(seen)),
                capture_output=True,text=True,timeout=12)
        (output/'stalled-run.log').write_text(result.stdout+result.stderr)
        assert seen.read_text()=='blocked\n','fixture did not block the real journal fsync'
        assert result.returncode==124 and 'DASHBOARD_QUIT_NOTIFIED' in result.stderr
        assert 'DASHBOARD_STOP_TIMEOUT' in result.stderr
        assert (stalled/'writer-active').exists(),'interrupted writer evidence was erased'
        assert not list(stalled.glob('events-*.jsonl')),'marker fsync should block before any event commit'
        with tempfile.TemporaryDirectory(prefix='history-recovered-runtime-') as runtime:
            resumed=subprocess.run(prefix+[args.ivi,'--demo','warning','--windowed',
                '--event-policy',str(stalled_policy),'--demo-exit-ms','600'],
                env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',XDG_RUNTIME_DIR=runtime),
                capture_output=True,text=True,timeout=8)
        (output/'after-stall-run.log').write_text(resumed.stdout+resumed.stderr)
        assert resumed.returncode==0,resumed.stderr
        assert not (stalled/'writer-active').exists(),'clean resumed teardown left writer active'
        recovered_events=[json.loads(json.loads(line)['payload']) for segment in stalled.glob('events-*.jsonl')
                          for line in segment.read_text().splitlines()]
        assert recovered_events and any(row.get('previous_gap_possible') for row in recovered_events)
        stall_verified=True
    summary={'status':'PASS','scope':'actual Qt history restore/export and optional Linux journal-stall injection, offscreen',
        'prior_events_restored':len(snapshots[0]['events']),'second_run_events':len(snapshots[1]['events']),
        'segments':len(files),'no_automatic_deletion':True,'validated_export':True,
        'desktop_quit_notice_verified':bool(args.supervisor),'real_journal_fsync_stall_bounded':stall_verified,
        'interrupted_recording_gap_retained':stall_verified}
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary));return 0


if __name__=='__main__':raise SystemExit(main())
