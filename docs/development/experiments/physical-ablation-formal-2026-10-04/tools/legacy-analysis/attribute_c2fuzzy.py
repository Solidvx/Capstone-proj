from pathlib import Path
import json,collections
b=Path('docs/development/experiments/physical-ablation-formal-2026-10-04');v=next((b/'raw/ABLATION-FORMAL-C2-FUZZY-001/ivi').rglob('receiver.jsonl'));hits=json.loads((b/'analysis/ABLATION-FORMAL-C2-FUZZY-001/fuzzy-id-200.json').read_text());rx=[json.loads(s) for s in v.read_text().splitlines()];events=[x for x in rx if x.get('message')=='IDS event published'];out=[]
for x in events:
 matches=[h for h in hits if h['data']==x['data']];assert len(matches)==1
 out.append({'receiver':x,'ecu':matches[0]})
print(json.dumps(out,indent=2));(b/'analysis/ABLATION-FORMAL-C2-FUZZY-001/alert-attribution.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
