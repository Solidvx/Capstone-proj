from pathlib import Path
import tarfile,json,hashlib,sys,collections,re,datetime
b=Path('docs/development/experiments/physical-ablation-formal-2026-10-04');inv=json.loads((b/'inventory.json').read_text(encoding='utf-8'))
sys.path.insert(0,'docs/development/experiments/ecu-ivi-integration-2026-10-03_04/tools')
from compare_ivi_can import read_can
def rows(p):return [json.loads(x) for x in p.read_text(encoding='utf-8-sig').splitlines() if x.strip()]
for num in ['001']:
 src=next(Path('.').glob('*/20H15M/*'+num+'*.gz'));d=b/('raw/ABLATION-FORMAL-C2-SPOOF-'+num)/'ivi';d.mkdir(parents=True,exist_ok=True)
 def save(p,data):
  if p.exists():assert p.read_bytes()==data
  else:p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
  rel=p.relative_to(b).as_posix();h=hashlib.sha256(data).hexdigest()
  if not any(x['path']==rel for x in inv['files']):inv['files'].append(dict(source=src.as_posix(),path=rel,bytes=len(data),sha256=h,preserved_sha256=h))
 save(d/src.name,src.read_bytes())
 with tarfile.open(src) as t:
  for m in t.getmembers():
   p=Path(m.name);assert not p.is_absolute() and '..' not in p.parts and (m.isdir() or m.isfile())
   if m.isfile():save(d/p,t.extractfile(m).read())
 v=next(d.rglob('candump.log')).parent;e=b/'raw/ABLATION-FORMAL-C2-SPOOF-001/ecu/results'/('ablation-formal-c2-spoof-'+num)
 ecu=sorted([x for p in [e/'warmup.jsonl',*sorted(e.glob('spoofing-*.jsonl'))] for x in rows(p) if 'frame' in x],key=lambda x:x['t'])
 error_lines=[]; data_lines=[]
 for line in (v/'candump.log').read_text().splitlines():
  match=re.search(r'can0 ([0-9A-Fa-f]+)#',line)
  if match and int(match[1],16)&0x20000000:error_lines.append(line)
  else:data_lines.append(line)
 filtered_path=Path('tmp/c2flood-data-only.log');filtered_path.write_text('\n'.join(data_lines)+'\n')
 can=read_can(filtered_path,'absolute');rx=rows(v/'receiver.jsonl');fr=[x for x in rx if x.get('result')=='FRAME'];a=[(x['can_id'],x['data']) for x in ecu];c=[(x[2],x[3]) for x in can]
 z={'ivi_error_frames':error_lines,'ecu_frames':len(a),'ivi_frames':len(c),'prefix_match':a==c[:len(a)],'receiver_frames':len(fr),'filtered_match':[(x['can_id'],x['data']) for x in fr]==[x for x in c if x[0] in [256,257,258,259,512]],'messages':dict(collections.Counter(x.get('message') for x in rx)),'exit_files':{p.name:p.read_text().strip() for p in v.glob('*exit*')},'stats':{p.name:p.read_text() for p in v.glob('can-*.txt')}}
 if z['prefix_match']:
  logs=[]
  for stamp,percent in re.findall(r'canbusload (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)[^\n]*\n[^\n]*? (\d+)%',(v/'canbusload.log').read_text()):
   ts=datetime.datetime.strptime(stamp,'%Y-%m-%d %H:%M:%S').replace(tzinfo=datetime.timezone(datetime.timedelta(hours=9))).timestamp();logs.append((ts,int(percent)))
  z['trials']=[]
  for tr in rows(e/'attempts.jsonl'):
   ix=[i for i,x in enumerate(ecu) if x.get('own') and tr['t_attack_start']<=x['t']<tr['t_attack_end']];lo=can[ix[0]][0]/1e9;hi=can[ix[-1]][0]/1e9
   samples=[p for t,p in logs if lo+1<=t<=hi];z['trials'].append({'trial':tr['trial'],'interior_load_percent':samples,'load_ge50':any(p>=50 for p in samples)})
 out=b/'analysis'/('ABLATION-FORMAL-C2-SPOOF-'+num)/'crosscheck.json';out.write_text(json.dumps(z,indent=2),encoding='utf-8')
 print(num,json.dumps({k:val for k,val in z.items() if k not in ['stats','trials']},ensure_ascii=True));print('load',sum(t['load_ge50'] for t in z.get('trials',[])),'/',len(z.get('trials',[])))
 print('files',[p.name for p in v.iterdir()]);print(z['stats'])
(b/'inventory.json').write_text(json.dumps(inv,ensure_ascii=False,indent=2),encoding='utf-8')
