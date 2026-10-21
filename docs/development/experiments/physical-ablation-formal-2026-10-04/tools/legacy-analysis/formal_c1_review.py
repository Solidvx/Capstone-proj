from pathlib import Path
import tarfile,json,hashlib,shutil,collections
b=Path('docs/development/experiments/physical-ablation-formal-2026-10-04');s=Path('tmp/ABLATION-FORMAL-C1-FLOOD-001-ECU.tar.gz');d=b/'raw/ABLATION-FORMAL-C1-FLOOD-001/ecu';d.mkdir(parents=True,exist_ok=True)
with tarfile.open(s) as t:t.extractall(d,filter='data')
shutil.copy2(s,d/s.name)
r=d/'results/ablation-formal-c1-flood-001';m=json.loads((r/'manifest.json').read_text());a=[json.loads(x) for x in (r/'attempts.jsonl').read_text().splitlines()]
for n,h in m['files_sha256'].items():assert hashlib.sha256((r/n).read_bytes()).hexdigest()==h
print('manifest',m['status'],m.get('error'),'hashes',len(m['files_sha256']))
for x in a:print(x['trial'],x['status'],x['attack_sent'],x['attack_tx_errors'],x['normal_seen'],x['normal_delivered'])
raw=[json.loads(x) for x in (r/'flooding-007.jsonl').read_text().splitlines()];print('errors',[x for x in raw if 'tx_error' in x])
meta=r.parent/'ablation-formal-c1-flood-001-meta'
for n in ['start.txt','end.txt','qdisc-before.txt','qdisc-after.txt']:print(n,(meta/n).read_text())
p=b/'inventory.json';i=json.loads(p.read_text(encoding='utf-8-sig'));known={x['path'] for x in i['files']}
for f in d.rglob('*'):
 if f.is_file() and f.relative_to(b).as_posix() not in known:
  h=hashlib.sha256(f.read_bytes()).hexdigest();i['files'].append(dict(source=s.as_posix(),path=f.relative_to(b).as_posix(),bytes=f.stat().st_size,sha256=h,preserved_sha256=h))
i['policy']='Preserve received originals and failed attempts; raw is local-only and Git-ignored.';p.write_text(json.dumps(i,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
out=b/'analysis/ABLATION-FORMAL-C1-FLOOD-001';out.mkdir(exist_ok=True);(out/'ecu-summary.json').write_text(json.dumps({'status':m['status'],'verified_hashes':len(m['files_sha256']),'attempts':a,'ivi_review':'PENDING','formal_accepted_count':None},indent=2)+'\n')
