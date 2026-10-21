from pathlib import Path
import json,collections
b=Path('docs/development/experiments/physical-ablation-formal-2026-10-04');e=b/'raw/ABLATION-FORMAL-C3-REPLAY-001/ecu/results/ablation-formal-c3-replay-001';v=next((b/'raw/ABLATION-FORMAL-C3-REPLAY-001/ivi').rglob('receiver.jsonl'))
def rows(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
ecu=sorted([x for p in [e/'warmup.jsonl',*sorted(e.glob('replay-*.jsonl'))] for x in rows(p) if 'frame' in x],key=lambda x:x['t']);rx=[x for x in rows(v) if x.get('result')=='FRAME'];assert all((x['can_id'],x['data'])==(y['can_id'],y['data']) for x,y in zip(ecu,rx))
records=[];last_normal=None
for x,y in zip(ecu,rx):
 if x['can_id']==256 and not x.get('own'):last_normal=x['data']
 for o in x.get('outcomes',[]):
  if o['kind']=='PUBLISHED' and (o.get('own') or o.get('auth_own')):
   records.append({'t':x['t'],'auth_own':x['own'],'pending_own':o['own'],'payload':o['payload'],'matches_latest_normal':o['payload']==last_normal,'ivi_message':y.get('message'),'ivi_source_data':y.get('source_data'),'ivi_matches_payload':y.get('source_data')==o['payload'],'auth_data':x['data']})
z={'count':len(records),'auth_own':sum(x['auth_own'] for x in records),'matches_latest_normal':sum(x['matches_latest_normal'] for x in records),'ivi_published':sum(x['ivi_message']=='Authenticated BMS data published' for x in records),'ivi_matches_payload':sum(x['ivi_matches_payload'] for x in records),'records':records}
(b/'analysis/ABLATION-FORMAL-C3-REPLAY-001/attribution.json').write_text(json.dumps(z,indent=2),encoding='utf-8');print({k:v for k,v in z.items() if k!='records'})

