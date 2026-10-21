"""Conservative IVI payload correlation, not cryptographic sender attribution."""
import argparse
from collections import Counter
import json
from pathlib import Path


def score(probe, ivi):
    prepared=[r for r in probe if r.get('result')=='PREPARED']
    complete=[r for r in probe if r.get('result')=='COMPLETE']
    if len(prepared)!=30 or not complete or complete[-1].get('rx_dropped')!=0:
        raise ValueError('incomplete or dropped probe evidence')
    auths=[r['auth'] for r in prepared]
    if len(set(auths))!=len(auths):raise ValueError('ambiguous duplicate auth payload')
    outcomes=[]
    for row in prepared:
        tx=[r for r in probe if r.get('result')=='TX' and r.get('trial')==row['trial']]
        if [(r['can_id'],r['data']) for r in tx]!=[(256,row['raw']),(258,row['auth'])]:
            raise ValueError('missing transmit evidence')
        matches=[r for r in ivi if r.get('result')=='FRAME' and r.get('can_id')==258 and r.get('data')==row['auth']]
        result='UNOBSERVED' if not matches else 'AMBIGUOUS'
        if len(matches)==1:
            r=matches[0]
            if r.get('source_data')==row['raw']:
                if r.get('process_result')==3:
                    result='MAC_REJECTED' if r.get('message','').split(' ',1)[0]=='reason=MAC_FAIL' else 'OTHER_REJECTION'
                elif r.get('process_result')==2:result='PUBLISHED'
        outcomes.append({'trial':row['trial'],'outcome':result,'matches':len(matches)})
    counts=Counter(r['outcome'] for r in outcomes)
    eligible=sum(counts[k] for k in ('MAC_REJECTED','OTHER_REJECTION','PUBLISHED'))
    return {'planned':30,'counts':dict(counts),'attributable_candidates':eligible,
            'mac_rejection_fraction_among_attributable_candidates':counts['MAC_REJECTED']/eligible if eligible else None,
            'complete_coverage':eligible==30,'trials':outcomes,
            'note':'Payload and source_data correlation only. Missing/ambiguous evidence is not rejection; do not generalize this sample rate.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe',type=Path,required=True)
    parser.add_argument('--ivi',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    read=lambda p:[json.loads(x) for x in p.read_text().splitlines() if x.strip()]
    result=score(read(args.probe),read(args.ivi))
    with args.out.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='trials'},ensure_ascii=False))


if __name__=='__main__':main()
