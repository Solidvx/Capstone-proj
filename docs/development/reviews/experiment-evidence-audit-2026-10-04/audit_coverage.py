from pathlib import Path
import json,hashlib,collections
z=json.loads(Path('tmp/record-audit.json').read_text(encoding='utf-8'))
for k,v in z.items():
 if isinstance(v,dict) and 'modified_preserved' in v:print(k,'modified',json.dumps(v['modified_preserved'],ensure_ascii=True))
print('matrix')
groups=collections.defaultdict(list)
for x in z['formal_cases']:groups[(x['config'],x['attack'])].append(x)
for k,r in sorted(groups.items()):print(k,[(x['run_id'],x['status']) for x in r])
# Coverage of incoming files by source hash, independently of stored paths.
hashes=set()
for b in Path('docs/development/experiments').glob('*2026*'):
 for x in json.loads((b/'inventory.json').read_text(encoding='utf-8'))['files']:hashes.add(x['sha256'])
incoming=next(p for p in Path('.').iterdir() if p.is_dir() and p.name.startswith('IVI'))
uncovered=[];total=0
for p in incoming.rglob('*'):
 if p.is_file():
  total+=1
  if hashlib.sha256(p.read_bytes()).hexdigest() not in hashes:uncovered.append(p.as_posix())
print('incoming',total,'uncovered',len(uncovered));print(json.dumps(uncovered[:25],ensure_ascii=True))
z['incoming_uncovered']=uncovered;z['incoming_count']=total
formal=Path('docs/development/experiments/physical-ablation-formal-2026-10-04')
z['tools']=[p.name for p in (formal/'tools').glob('*')]
print('tools',z['tools'])
print('tmp scripts', [p.name for p in Path('tmp').glob('*.py') if any(t in p.name for t in ['cross','attribute','finish','check_c'])])
Path('tmp/record-audit.json').write_text(json.dumps(z,ensure_ascii=False,indent=2),encoding='utf-8')
