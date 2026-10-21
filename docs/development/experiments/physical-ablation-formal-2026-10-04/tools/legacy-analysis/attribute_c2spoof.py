from pathlib import Path
import json,collections
b=Path('docs/development/experiments/physical-ablation-formal-2026-10-04');e=b/'raw/ABLATION-FORMAL-C2-SPOOF-001/ecu/results/ablation-formal-c2-spoof-001';v=next((b/'raw/ABLATION-FORMAL-C2-SPOOF-001/ivi').rglob('receiver.jsonl'))
def rows(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
ecu=sorted([x for p in [e/'warmup.jsonl',*sorted(e.glob('spoofing-*.jsonl'))] for x in rows(p) if 'frame' in x],key=lambda x:x['t']);rx=[x for x in rows(v) if x.get('result')=='FRAME'];assert all((a['can_id'],a['data'])==(z['can_id'],z['data']) for a,z in zip(ecu,rx))
counts=collections.Counter();last=None;details=[]
for a,z in zip(ecu,rx):
 if a['can_id']==256:last=a
 if z.get('message')=='Authenticated BMS data published':
  counts['published_common']+=1
  counts['auth_own']+=bool(a.get('own'));counts['pending_own']+=bool(last and last.get('own'));counts['payload_match']+=bool(last and last['data']==z.get('source_data'))
 if 'MAC_FAIL' in z.get('message',''):
  counts['mac_fail']+=1;counts['mac_fail_pending_own']+=bool(last and last.get('own'));counts['mac_fail_auth_own']+=bool(a.get('own'))
print(dict(counts));print('tail',rx[len(ecu):])
(b/'analysis/ABLATION-FORMAL-C2-SPOOF-001/attribution.json').write_text(json.dumps({'counts':dict(counts),'ivi_tail':rx[len(ecu):]},indent=2),encoding='utf-8')
