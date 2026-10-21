from pathlib import Path
import json,hashlib,re
b=Path('docs/development/experiments/physical-ablation-formal-2026-10-04');p=b/'README.md';s=p.read_text(encoding='utf-8');s=s.replace('IVI대조 및 공식인정횟수 미확정.','IVI대조 완료, 유효6/100 인정·무효1 보존.').replace('7회 시도·VALID6/INVALID1·IVI 대조 대기','7회 시도·공식유효6/100·무효1, 후속대기');p.write_text(s,encoding='utf-8')
p=b/'analysis/ABLATION-FORMAL-C1-FLOOD-001/ecu-summary.json';a=json.loads(p.read_text(encoding='utf-8'));a['ivi_review']='COMPLETE';a['formal_accepted_count']=6;p.write_text(json.dumps(a,indent=2)+'\n')
i=json.loads((b/'inventory.json').read_text(encoding='utf-8'));assert all(hashlib.sha256((b/x['path']).read_bytes()).hexdigest()==x['preserved_sha256'] for x in i['files']);print('Verified formal files',len(i['files']))
for p in b.rglob('*.md'):
 for t in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8-sig')):assert (p.parent/t).exists()

