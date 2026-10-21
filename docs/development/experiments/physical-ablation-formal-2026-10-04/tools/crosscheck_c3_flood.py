from pathlib import Path
import json,collections,re,sys
sys.path.insert(0,'docs/development/experiments/ecu-ivi-integration-2026-10-03_04/tools')
from compare_ivi_can import read_can
b=Path('docs/development/experiments/physical-ablation-formal-2026-10-04');root=b/'raw/ABLATION-FORMAL-C3-FLOOD-001-003'
def rows(p):
 with p.open(encoding='utf-8-sig') as f:
  for line in f:
   if line.strip():yield json.loads(line)
for n in range(1,4):
 name=f'ablation-formal-c3-flood-{n:03d}';e=root/'ecu/results'/name;v=root/'ivi'/name
 ecu=[]
 for p in [e/'warmup.jsonl',*sorted(e.glob('flooding-*.jsonl'))]:
  ecu.extend((x['t'],x['can_id'],x['data'],x.get('own',False)) for x in rows(p) if 'frame' in x)
 ecu.sort(key=lambda x:x[0]);a=[(x[1],x[2]) for x in ecu]
 errors=[];lines=[]
 for l in (v/'candump.log').read_text().splitlines():
  m=re.search(r'can0\s+([0-9A-Fa-f]+)#',l)
  if m and int(m[1],16)&0x20000000:errors.append(l)
  else:lines.append(l)
 temp=Path('tmp/c3-can-filtered.log');temp.write_text('\n'.join(lines)+'\n');can=read_can(temp,'absolute');c=[(x[2],x[3]) for x in can]
 rx=list(rows(v/'receiver.jsonl'));fr=[x for x in rx if x.get('result')=='FRAME'];filtered=[x for x in c if x[0] in [256,257,258,259,512]]
 sent=[(512,x['data']) for x in rows(e/'ids.jsonl') if x.get('result')=='ALERT_SENT'];alerts=[x for x in c if x[0]==512]
 meta={p.name:p.read_text() for p in v.glob('*.txt') if p.name.startswith('can-') or 'exit' in p.name}
 z={'ecu_frames':len(a),'ivi_frames':len(c),'ecu_exact_prefix':a==c[:len(a)],'ivi_extra_tail':len(c)-len(a),'receiver_frames':len(fr),'receiver_exact_filtered_can':[(x['can_id'],x['data']) for x in fr]==filtered,'error_frames':errors,'messages':dict(collections.Counter(x.get('message') for x in rx)),'ids_sent':len(sent),'ivi_alert_frames':len(alerts),'ids_sent_exact_ivi_alerts':sent==alerts,'alert_types':dict(collections.Counter(int(x[1][:2],16) for x in alerts)), 'stats_exit':meta,'stderr_bytes':{p.name:p.stat().st_size for p in v.glob('*.stderr')}}
 if a!=c[:len(a)]:z['first_difference']=next((i for i,(x,y) in enumerate(zip(a,c)) if x!=y),min(len(a),len(c)))
 out=b/'analysis'/name.upper()/'crosscheck.json';out.write_text(json.dumps(z,indent=2),encoding='utf-8');print(name,json.dumps(z,ensure_ascii=True))
