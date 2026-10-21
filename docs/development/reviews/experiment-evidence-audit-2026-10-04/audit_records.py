from pathlib import Path
import json,hashlib,re,collections
root=Path('.');bases=list(Path('docs/development/experiments').glob('*2026*'));result={}
for b in bases:
 inv=json.loads((b/'inventory.json').read_text(encoding='utf-8')); bad=[];changed=[];paths=[];hashes=set()
 for x in inv['files']:
  p=b/x['path'];paths.append(x['path'])
  if not p.exists():bad.append([x['path'],'missing']);continue
  h=hashlib.sha256(p.read_bytes()).hexdigest();hashes.add(h)
  if h!=x.get('preserved_sha256',x['sha256']):bad.append([x['path'],'hash'])
  if h!=x['sha256']:changed.append(x['path'])
 raw={p.relative_to(b).as_posix() for p in (b/'raw').rglob('*') if p.is_file()}
 result[b.name]={'inventory_count':len(paths),'duplicates':[x for x,c in collections.Counter(paths).items() if c>1],'bad':bad,'modified_preserved':changed,'unindexed_raw':sorted(raw-set(paths)),'reports':[p.name for p in (b/'reports').glob('*.md')]}
 print(b.name,len(paths),'bad',len(bad),'modified',len(changed),'unindexed',len(raw-set(paths)))
f=next(b for b in bases if b.name.startswith('physical'));cases=[]
for p in (f/'raw').rglob('attempts.jsonl'):
 rows=[json.loads(l) for l in p.read_text().splitlines() if l.strip()];man=p.parent/'manifest.json'
 if not rows:continue
 m=json.loads(man.read_text());issues=[]
 for n,h in m.get('files_sha256',{}).items():
  q=p.parent/n
  if not q.exists() or hashlib.sha256(q.read_bytes()).hexdigest()!=h:issues.append(n)
 cases.append({'run_id':m.get('run_id'),'config':m.get('config'),'attack':rows[0].get('attack_type'),'n':len(rows),'trials':[r['trial'] for r in rows],'status':dict(collections.Counter(r['status'] for r in rows)),'path':p.as_posix(),'manifest_bad':issues,'source_files':len(m.get('source_sha256',{}))})
result['formal_cases']=cases
print('cases',len(cases),'rows',sum(x['n'] for x in cases),'badmanifest',sum(len(x['manifest_bad']) for x in cases))
links=[]
for p in [*Path('docs/development/experiments').rglob('*.md'),*Path('docs/aidlc/changes/CHG-014').glob('*.md')]:
 if 'raw' in p.parts:continue
 for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8-sig')):
  target=target.split('#')[0].strip('<>')
  if not target or '://' in target or target.startswith('mailto:'):continue
  if not (p.parent/target).exists():links.append([p.as_posix(),target])
result['broken_local_links']=links
Path('tmp/record-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('brokenlinks',len(links));print(json.dumps(links[:15],ensure_ascii=True))
