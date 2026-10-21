from pathlib import Path
import tarfile,sys,json,collections,hashlib,shutil
b=Path('docs/development/experiments/physical-ablation-formal-2026-10-04');d=b/'raw/ABLATION-FORMAL-C1-FLOOD-001/ivi';d.mkdir(exist_ok=True);s=next(Path('IVI측에서받아온파일들/09H15M').glob('*.gz'))
with tarfile.open(s) as t:t.extractall(d,filter='data')
shutil.copy2(s,d/s.name)
sys.path.insert(0,'docs/development/experiments/ecu-ivi-integration-2026-10-03_04/tools');from compare_ivi_can import read_can
v=next(d.rglob('candump.log')).parent;e=d.parent/'ecu/results/ablation-formal-c1-flood-001'
def rows(p):return [json.loads(x) for x in p.read_text(encoding='utf-8-sig').splitlines() if x.strip()]
ecu=sorted([x for p in [e/'warmup.jsonl',*sorted(e.glob('flooding-*.jsonl'))] for x in rows(p) if 'frame' in x],key=lambda x:x['t']);can=read_can(v/'candump.log','absolute');rx=rows(v/'receiver.jsonl');fr=[x for x in rx if x.get('result')=='FRAME'];a=[(x['can_id'],x['data']) for x in ecu];c=[(x[2],x[3]) for x in can]
z={'ecu_frames':len(a),'ivi_frames':len(c),'prefix_match':a==c[:len(a)],'receiver_frames':len(fr),'filtered_match':[(x['can_id'],x['data']) for x in fr]==[x for x in c if x[0] in [256,257,258,259,512]],'messages':dict(collections.Counter(x.get('message') for x in rx)),'exit_codes':{p.name:p.read_text().strip() for p in v.glob('*exit*')}}
print(json.dumps(z,indent=2));assert z['prefix_match'] and z['filtered_match']
for tr in rows(e/'attempts.jsonl'):
 ix=[i for i,x in enumerate(ecu) if x.get('own') and tr['t_attack_start']<=x['t']<tr['t_attack_end']];print('trial',tr['trial'],'epoch first last',can[ix[0]][0]/1e9,can[ix[-1]][0]/1e9)
print((v/'canbusload.log').read_text());print((v/'can-before.txt').read_text());print((v/'can-after.txt').read_text())
(b/'analysis/ABLATION-FORMAL-C1-FLOOD-001/crosscheck.json').write_text(json.dumps(z,indent=2)+'\n')
p=b/'inventory.json';inv=json.loads(p.read_text());known={x['path'] for x in inv['files']}
for f in d.rglob('*'):
 if f.is_file() and f.relative_to(b).as_posix() not in known:
  h=hashlib.sha256(f.read_bytes()).hexdigest();inv['files'].append(dict(source=s.as_posix(),path=f.relative_to(b).as_posix(),bytes=f.stat().st_size,sha256=h,preserved_sha256=h))
p.write_text(json.dumps(inv,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
