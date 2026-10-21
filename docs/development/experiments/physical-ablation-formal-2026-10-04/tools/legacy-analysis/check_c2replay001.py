from pathlib import Path
import tarfile,json,hashlib,collections
b=Path('docs/development/experiments/physical-ablation-formal-2026-10-04');s=Path('tmp/ABLATION-FORMAL-C2-REPLAY-001-ECU.tar.gz');d=b/'raw/ABLATION-FORMAL-C2-REPLAY-001/ecu';inv=json.loads((b/'inventory.json').read_text(encoding='utf-8'))
def save(p,data):
 if p.exists():assert p.read_bytes()==data
 else:p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 rel=p.relative_to(b).as_posix();h=hashlib.sha256(data).hexdigest()
 if not any(x['path']==rel for x in inv['files']):inv['files'].append(dict(source=s.as_posix(),path=rel,bytes=len(data),sha256=h,preserved_sha256=h))
save(d/s.name,s.read_bytes())
with tarfile.open(s) as t:
 for m in t.getmembers():
  p=Path(m.name);assert not p.is_absolute() and '..' not in p.parts and (m.isdir() or m.isfile())
  if m.isfile():save(d/'results'/p,t.extractfile(m).read())
r=d/'results/ablation-formal-c2-replay-001';meta=r.with_name(r.name+'-meta');rows=[json.loads(x) for x in (r/'attempts.jsonl').read_text().splitlines()];assert [x['trial'] for x in rows]==list(range(1,101))
man=json.loads((r/'manifest.json').read_text())
for n,h in man['files_sha256'].items():assert hashlib.sha256((r/n).read_bytes()).hexdigest()==h
for x in rows:assert hashlib.sha256((r/x['raw_file']).read_bytes()).hexdigest()==x['raw_sha256']
z={'count':len(rows),'status':dict(collections.Counter(x['status'] for x in rows)),'totals':{k:sum(x.get(k,0) or 0 for x in rows) for k in ['attack_sent','attack_seen','attack_tx_errors','tx_syscall_errors','tx_recovered_frames','tx_deadline_skipped','normal_expected','normal_seen','normal_delivered','attack_published','attack_parse_rejected']},'meta':{p.name:p.read_text() for p in meta.glob('*.txt')}}
out=b/'analysis/ABLATION-FORMAL-C2-REPLAY-001';out.mkdir(parents=True,exist_ok=True);(out/'ecu-summary.json').write_text(json.dumps(z,indent=2),encoding='utf-8');(b/'inventory.json').write_text(json.dumps(inv,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(z,indent=2))
