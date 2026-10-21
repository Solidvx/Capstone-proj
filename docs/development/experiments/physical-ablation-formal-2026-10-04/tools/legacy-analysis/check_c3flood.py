from pathlib import Path
import tarfile,json,hashlib,collections
b=Path('docs/development/experiments/physical-ablation-formal-2026-10-04');s=Path('tmp/ABLATION-FORMAL-C3-FLOOD-001-003-ECU.tar.gz');d=b/'raw/ABLATION-FORMAL-C3-FLOOD-001-003/ecu';inv=json.loads((b/'inventory.json').read_text(encoding='utf-8'));known={x['path']:x for x in inv['files']}
def save(p,data):
 if p.exists():assert p.read_bytes()==data
 else:p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 rel=p.relative_to(b).as_posix();h=hashlib.sha256(data).hexdigest()
 if rel not in known:inv['files'].append(dict(source=s.as_posix(),path=rel,bytes=len(data),sha256=h,preserved_sha256=h));known[rel]=inv['files'][-1]
save(d/s.name,s.read_bytes())
with tarfile.open(s) as t:
 for m in t.getmembers():
  p=Path(m.name);assert not p.is_absolute() and '..' not in p.parts and ':' not in m.name and (m.isdir() or m.isfile())
  if m.isfile():save(d/'results'/p,t.extractfile(m).read())
allrows=[]
for i in range(1,4):
 name=f'ABLATION-FORMAL-C3-FLOOD-{i:03d}';r=d/'results'/name.lower();meta=r.with_name(r.name+'-meta')
 rows=[json.loads(x) for x in (r/'attempts.jsonl').read_text().splitlines()];allrows+=rows
 man=json.loads((r/'manifest.json').read_text())
 for n,h in man['files_sha256'].items():
  assert Path(n).name==n
  assert hashlib.sha256((r/n).read_bytes()).hexdigest()==h,(name,n)
 for x in rows:
  if 'raw_file' in x:assert hashlib.sha256((r/x['raw_file']).read_bytes()).hexdigest()==x['raw_sha256']
 counter=collections.Counter();errnos=collections.Counter();reasons=collections.Counter()
 with (r/'ids.jsonl').open() as stream:
  for line in stream:
   x=json.loads(line);counter[x['result']]+=1
   if x['result']=='ALERT_TX_FAILED':errnos[x.get('errno')]+=1
   if x['result']=='ANOMALY':reasons[x.get('reason')]+=1
 z={'count':len(rows),'trials':[x['trial'] for x in rows],'status':dict(collections.Counter(x['status'] for x in rows)),'totals':{k:sum(x.get(k,0) or 0 for x in rows) for k in ['attack_sent','attack_seen','attack_tx_errors','tx_syscall_errors','tx_recovered_frames','tx_deadline_skipped','normal_expected','normal_seen','normal_delivered','attack_published']},'ratios_over_one':[x['trial'] for x in rows if (x.get('delivery_ratio') or 0)>1], 'ids_results':dict(counter),'ids_tx_failure_errnos':dict(errnos),'ids_reasons':dict(reasons),'meta':{p.name:p.read_text() for p in meta.glob('*.txt')},'ids_process_log':(r/'ids-process.log').read_text(),'clock':man.get('clock')}
 out=b/'analysis'/name;out.mkdir(parents=True,exist_ok=True);(out/'ecu-summary.json').write_text(json.dumps(z,indent=2),encoding='utf-8');print(json.dumps(z,indent=2))
assert [x['trial'] for x in allrows]==list(range(1,101))
(b/'inventory.json').write_text(json.dumps(inv,ensure_ascii=False,indent=2),encoding='utf-8')
print('Verified all manifest/raw hashes; inventory files',len(inv['files']))
