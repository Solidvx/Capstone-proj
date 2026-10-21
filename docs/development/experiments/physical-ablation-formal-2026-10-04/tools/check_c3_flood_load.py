from pathlib import Path
import json,re,datetime,sys,bisect,hashlib
sys.path.insert(0,'docs/development/experiments/ecu-ivi-integration-2026-10-03_04/tools')
from compare_ivi_can import read_can
b=Path('docs/development/experiments/physical-ablation-formal-2026-10-04');root=b/'raw/ABLATION-FORMAL-C3-FLOOD-001-003'
def rows(p):
 with p.open(encoding='utf-8-sig') as f:
  for l in f:
   if l.strip():yield json.loads(l)
for n in range(1,4):
 name=f'ablation-formal-c3-flood-{n:03d}';e=root/'ecu/results'/name;v=root/'ivi'/name;can=read_can(v/'candump.log','absolute')
 cursor=sum('frame' in x for x in rows(e/'warmup.jsonl'));ranges={}
 for p in sorted(e.glob('flooding-*.jsonl')):
  first=last=None
  for x in rows(p):
   if 'frame' not in x:continue
   if x.get('own'):first=cursor if first is None else first;last=cursor
   cursor+=1
  if first is not None:ranges[int(p.stem.split('-')[1])]=(can[first][0]/1e9,can[last][0]/1e9)
 loads=[]
 for stamp,percent in re.findall(r'canbusload (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)[^\n]*\n[^\n]*? (\d+)%',(v/'canbusload.log').read_text()):
  ts=datetime.datetime.strptime(stamp,'%Y-%m-%d %H:%M:%S').replace(tzinfo=datetime.timezone(datetime.timedelta(hours=9))).timestamp();loads.append((ts,int(percent)))
 out=[]
 for r in rows(e/'attempts.jsonl'):
  if r['status']!='VALID':continue
  lo,hi=ranges[r['trial']];samples=[p for t,p in loads if lo+1<=t<=hi]
  out.append({'trial':r['trial'],'interior_load_percent':samples,'any_interior_ge50':any(p>=50 for p in samples)})
 z={'method':'Exact sequence aligned first/last injected own frames; interior one-second canbusload samples only, not full-window mean','trials':out}
 (b/'analysis'/name.upper()/'load-check.json').write_text(json.dumps(z,indent=2),encoding='utf-8')
 print(n,len(out),sum(x['any_interior_ge50'] for x in out), 'range',min((p for x in out for p in x['interior_load_percent']),default=None),max((p for x in out for p in x['interior_load_percent']),default=None))
inv=json.loads((b/'inventory.json').read_text(encoding='utf-8'))
for x in inv['files']:
 p=b/x['path'];assert p.stat().st_size==x['bytes'];assert hashlib.sha256(p.read_bytes()).hexdigest()==x['preserved_sha256']
print('Inventory verified',len(inv['files']))
