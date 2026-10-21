from pathlib import Path
import json,collections,hashlib
b=Path('docs/development/experiments/physical-ablation-formal-2026-10-04');name='ABLATION-FORMAL-C3-SPOOF-001';e=b/'raw'/name/'ecu/results'/name.lower();v=next((b/'raw'/name/'ivi').rglob('receiver.jsonl')).parent
def rows(p):
 with p.open() as f:
  for l in f:
   if l.strip():yield json.loads(l)
a=sorted([x for p in [e/'warmup.jsonl',*sorted(e.glob('spoofing-*.jsonl'))] for x in rows(p) if 'frame' in x],key=lambda x:x['t']);c=[x for x in rows(v/'receiver.jsonl') if x.get('result')=='FRAME'];key=lambda x:(x['can_id'],x['data'])
i=j=0;missing=[];pairs=[]
while i<len(a) and j<len(c):
 if key(a[i])==key(c[j]):pairs.append((i,j));i+=1;j+=1;continue
 skip=next((k for k in range(1,10) if [key(x) for x in a[i+k:i+k+30]]==[key(x) for x in c[j:j+30]]),None)
 if skip is None:raise ValueError((i,j))
 missing.extend({'index':q,'record':a[q]} for q in range(i,i+skip));i+=skip
sent=[x['data'] for x in rows(e/'ids.jsonl') if x.get('result')=='ALERT_SENT'];received=[x['data'] for x in c if x['can_id']==512];assert sent==received
pending=None;pub=collections.Counter();mac=collections.Counter()
for ai,cj in pairs:
 x=a[ai];y=c[cj]
 if x['can_id']==256:pending=x
 if y.get('message')=='Authenticated BMS data published':pub[(bool(pending and pending['own']),bool(x['own']),bool(pending and pending['data']==y.get('source_data')))]+=1
 if 'MAC_FAIL' in y.get('message',''):mac[(bool(pending and pending['own']),bool(x['own']))]+=1
z={'missing_alignment':missing,'matched':len(pairs),'ivi_tail':len(c)-j,'ids_exact_match':len(sent),'published_origins':{str(k):v for k,v in pub.items()},'mac_fail_origins':{str(k):v for k,v in mac.items()},'qt_warning_count':(v/'dashboard.stderr').read_text().count('QUnifiedTimer::stopAnimationDriver: driver is not running'),'stderr_bytes':{p.name:p.stat().st_size for p in v.glob('*.stderr')}}
(b/'analysis'/name/'attribution.json').write_text(json.dumps(z,indent=2),encoding='utf-8');print(json.dumps(z))
for x in json.loads((b/'inventory.json').read_text(encoding='utf-8'))['files']:
 if name in x['path']:assert hashlib.sha256((b/x['path']).read_bytes()).hexdigest()==x['preserved_sha256']
