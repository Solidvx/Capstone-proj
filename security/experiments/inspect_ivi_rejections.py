"""Descriptive product rejection evidence; payload matches are not sender attribution."""
import argparse
from collections import Counter
import json
from pathlib import Path
from security.experiments.live_three_node import read_run


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def inspect(root):
    output=[]
    for attempt in sorted(root.glob('C*/attempt-*')):
        manifest, ledger=read_run(attempt)  # Verify sealed original evidence.
        if not manifest.get('cleanup_confirmed'):raise ValueError('unconfirmed cleanup')
        worker=rows(attempt/'attacker.jsonl'); obs=rows(attempt/'observer_b.jsonl')
        ivi=rows(attempt/'ivi.jsonl')
        starts=[r['t'] for r in obs if r.get('result')=='PHASE' and r.get('phase')=='attack']
        ends=[r['t'] for r in obs if r.get('result')=='PHASE' and r.get('phase')=='idle']
        if len(starts)!=len(ends):raise ValueError('incomplete phase boundaries')
        completed=[r for r in ledger if r.get('trial_completed')]
        if len(completed)!=len(starts):raise ValueError('trial/window mismatch')
        for trial,start,end in zip(completed,starts,ends):
            signatures={(r['can_id'],r['data']) for r in worker if r.get('result')=='TX' and r.get('trial')==trial['trial']}
            # Replay raw payload also occurs in genuine traffic: inspect auth candidates only.
            if trial['attack_type']=='replay':signatures={s for s in signatures if s[0]==0x102}
            matched=[r for r in ivi if r.get('result')=='FRAME' and start<=int(r['timestamp_ns'])/1e9<=end
                     and (r['can_id'],r['data']) in signatures]
            outcomes=Counter(r['process_result'] for r in matched)
            reasons=Counter(r.get('message','') for r in matched if r['process_result']==3)
            output.append({'config':trial['config'],'attack':trial['attack_type'],'trial':trial['trial'],
                           'candidate_frames':len(matched),'ignored':outcomes[0],'pending':outcomes[1],
                           'published':outcomes[2],'rejected':outcomes[3],'rejection_messages':dict(reasons),
                           'blocking_rate':None})
    return {'note':'Candidate payload matches, not authenticated sender attribution. Replay capture occurs within the attack phase, so genuine source auth can match. No causal blocking rate inferred. Invalid BMS payload rejection is not SecOC rejection.', 'trials':output}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();report=inspect(args.root)
    with args.out.open('x') as f:json.dump(report,f,indent=2)
    groups={}
    for row in report['trials']:
        key=f"C{row['config']}-{row['attack']}"
        group=groups.setdefault(key,Counter())
        group.update({k:row[k] for k in ('candidate_frames','ignored','pending','published','rejected')})
    print(json.dumps(groups,indent=2))


if __name__=='__main__':main()
