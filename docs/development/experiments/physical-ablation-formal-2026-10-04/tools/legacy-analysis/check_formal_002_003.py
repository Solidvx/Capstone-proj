import tarfile,json,hashlib,shutil
from pathlib import Path
b=Path('docs/development/experiments/physical-ablation-formal-2026-10-04');src=Path('tmp/ABLATION-FORMAL-C1-FLOOD-002-003-ECU.tar.gz'); dst=b/'raw/ABLATION-FORMAL-C1-FLOOD-002-003/ecu'
dst.mkdir(parents=True,exist_ok=True)
inv=json.loads((b/'inventory.json').read_text(encoding='utf-8-sig'))
def save(path,data):
 if path.exists(): assert path.read_bytes()==data
 else: path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
 rel=path.relative_to(b).as_posix();h=hashlib.sha256(data).hexdigest()
 if not any(x['path']==rel for x in inv['files']):inv['files'].append(dict(source=src.as_posix(),path=rel,bytes=len(data),sha256=h,preserved_sha256=h))
save(dst/src.name,src.read_bytes())
with tarfile.open(src) as t:
 for m in t.getmembers():
  p=Path(m.name)
  assert not p.is_absolute() and '..' not in p.parts
  assert m.isfile() or m.isdir()
  if m.isfile():save(dst/'results'/p,t.extractfile(m).read())
(b/'inventory.json').write_text(json.dumps(inv,ensure_ascii=False,indent=2),encoding='utf-8')
for num in ['002','003']:
 root=dst/'results'/('ablation-formal-c1-flood-'+num);meta=root.with_name(root.name+'-meta')
 rows=[json.loads(x) for x in (root/'attempts.jsonl').read_text().splitlines()]
 print(num,'rows',len(rows),'range',rows[0]['trial'],rows[-1]['trial'])
 for k in ['attack_tx_errors','tx_syscall_errors','tx_recovered_frames','tx_retry_planned_count','tx_deadline_skipped','attack_sent','attack_seen','normal_expected','normal_delivered']:print(k,sum(r.get(k,0) for r in rows))
 print('invalid',[(r['trial'],r['invalid_reason']) for r in rows if r['status']!='VALID'])
 for n in ['start.txt','end.txt','exit.txt','qdisc-before.txt','qdisc-after.txt','can-before.txt','can-after.txt']:print(n,(meta/n).read_text())
 manifest=json.loads((root/'manifest.json').read_text())
 for n,h in manifest['files_sha256'].items():assert hashlib.sha256((root/n).read_bytes()).hexdigest()==h,n
 for r in rows:assert hashlib.sha256((root/r['raw_file']).read_bytes()).hexdigest()==r['raw_sha256']
 print('HASHES OK')
