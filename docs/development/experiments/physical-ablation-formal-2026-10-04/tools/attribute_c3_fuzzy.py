from pathlib import Path
import json,collections,hashlib
b=Path('docs/development/experiments/physical-ablation-formal-2026-10-04');name='ABLATION-FORMAL-C3-FUZZY-001';e=b/'raw'/name/'ecu/results'/name.lower();v=next((b/'raw'/name/'ivi').rglob('receiver.jsonl')).parent

def rows(p):
 with p.open(encoding='utf-8-sig') as f:
  for l in f:
   if l.strip():yield json.loads(l)
ecu=sorted([x for p in [e/'warmup.jsonl',*sorted(e.glob('fuzzy-*.jsonl'))] for x in rows(p) if 'frame' in x],key=lambda x:x['t'])
rx=[x for x in rows(v/'receiver.jsonl') if x.get('result')=='FRAME'];filtered=[x for x in ecu if x['can_id'] in [256,257,258,259,512]]
assert [(x['can_id'],x['data']) for x in filtered]==[(x['can_id'],x['data']) for x in rx[:len(filtered)]]
counts=collections.Counter();injected=[];real=[]
for x,y in zip(filtered,rx):
 if x['can_id']!=512:continue
 origin='injected' if x.get('own') else 'ids'
 counts[(origin,y.get('message'))]+=1
 if origin=='ids':real.append(x['data'])
 if origin=='injected' and y.get('message')=='IDS event published':injected.append({'data':x['data'],'ecu_t':x['t'],'receiver':y})
sent=[x['data'] for x in rows(e/'ids.jsonl') if x.get('result')=='ALERT_SENT'];assert sent==real
stderr=(v/'dashboard.stderr').read_text();z={'counts':{str(k):v for k,v in counts.items()},'ids_exact_sent_match':True,'injected_published':injected,'dashboard_stderr':stderr,'collector_stderr_bytes':{p.name:p.stat().st_size for p in v.glob('*.stderr')}}
(b/'analysis'/name/'alert-attribution.json').write_text(json.dumps(z,indent=2),encoding='utf-8');print(json.dumps(z,ensure_ascii=True))
inv=json.loads((b/'inventory.json').read_text(encoding='utf-8'))
for x in inv['files']:
 if name in x['path']:assert hashlib.sha256((b/x['path']).read_bytes()).hexdigest()==x['preserved_sha256']
print('Run inventory verified')
