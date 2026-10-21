from pathlib import Path
import json,collections
b=Path('docs/development/experiments/physical-ablation-formal-2026-10-04');e=b/'raw/ABLATION-FORMAL-C2-FLOOD-001/ecu/results/ablation-formal-c2-flood-001';v=next((b/'raw/ABLATION-FORMAL-C2-FLOOD-001/ivi').rglob('receiver.jsonl'))
def rows(p):return [json.loads(s) for s in p.read_text().splitlines() if s.strip()]
ecu=sorted([x for p in [e/'warmup.jsonl',*sorted(e.glob('flooding-*.jsonl'))] for x in rows(p) if 'frame' in x],key=lambda x:x['t']);f=[x for x in ecu if x['can_id'] in [256,257,258,259,512]];rx=[x for x in rows(v) if x.get('result')=='FRAME'];paired=list(zip(f,rx));out=[]
for tr in rows(e/'attempts.jsonl'):
 sub=[(a,z) for a,z in paired if tr['t_attack_start']<=a['t']<tr['t_attack_end']]
 out.append({'trial':tr['trial'],'ivi_messages_in_ecu_attack_window':dict(collections.Counter(z['message'] for a,z in sub))})
p=b/'analysis/ABLATION-FORMAL-C2-FLOOD-001/ivi-attack-windows.json';p.write_text(json.dumps(out,indent=2),encoding='utf-8')
print(collections.Counter({k:sum(t['ivi_messages_in_ecu_attack_window'].get(k,0) for t in out) for k in set(k for t in out for k in t['ivi_messages_in_ecu_attack_window'])}))
