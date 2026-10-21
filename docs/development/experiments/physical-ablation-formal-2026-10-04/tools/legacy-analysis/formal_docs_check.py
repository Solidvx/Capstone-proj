from pathlib import Path
import json,hashlib,re
b=Path('docs/development/experiments/physical-ablation-formal-2026-10-04');p=b/'reports/ABLATION-FORMAL-C1-FLOOD-001.md';s=p.read_text(encoding='utf-8-sig').replace('7회차エラーは errno105 ENOBUFS、monotonic2363.056326690。qdisc drop36→37増加1、requeue237→341増加104、終了backlog0。8~100回は未実行。','7회차 오류는 errno105 ENOBUFS, monotonic2363.056326690. qdisc drop36→37 증가1, requeue237→341 증가104, 종료backlog0. 8~100회는 미실행.');p.write_text(s,encoding='utf-8')
p=b/'README.md';s=p.read_text(encoding='utf-8-sig').replace('상태: 기록 공간 준비 완료. 공식 시행은 아직 미실행.','상태: 첫 공식 실행7회 시도, 실행기VALID6회·INVALID1회. IVI대조 및 공식인정횟수 미확정.').replace('아직 수령 파일 없음.','수령 파일은 아래 실행별 등록과 보고서에서 확인한다.').replace('| 예정·미실행 |','| 7회 시도·VALID6/INVALID1·IVI 대조 대기 |');s+='\n[첫 실행 ECU 검토](reports/ABLATION-FORMAL-C1-FLOOD-001.md)\n';p.write_text(s,encoding='utf-8')
i=json.loads((b/'inventory.json').read_text());assert all(hashlib.sha256((b/x['path']).read_bytes()).hexdigest()==x['preserved_sha256'] for x in i['files'])
for p in b.rglob('*.md'):
 for t in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8-sig')):assert (p.parent/t).exists(),t
print('Formal archive verified:',len(i['files']),'files; links OK')
