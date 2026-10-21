# 팀원 전달 자료 — 여기부터 읽기

이 브랜치에는 문서와 로그 압축본이 모두 포함되어 있다. GitHub Release에서 별도로 다운로드할 필요가 없다.

## 1. 문서

1. [이번 세션 전체 총정리](../../docs/development/reviews/2026-10-22-session-summary.md): 수행 작업·코드 변경·결과·남은 일.
2. [오늘 실험 총정리](../../docs/development/experiments/2026-10-22-experiments-summary.md): 시험 방법·분모·실측값·증거 한계. **11절에 마지막 flooding 관찰 결과가 있다.**
3. [실행 및 인수인계 안내](../../docs/development/playbooks/three-node-handoff.md): 노드별 역할·실행·종료·오류·재개 방법.

문서 원본은 위 경로에 유지한다. 압축본에도 같은 문서의 전달 시점 사본이 포함되어 있다.

## 2. 브랜치 가져오기

기존 작업 폴더가 수정 중이면 pull/reset하지 말고 별도 디렉터리에 복제한다.

```bash
git clone --branch docs/three-node-results --single-branch https://github.com/Solidvx/Capstone-proj.git Capstone-handoff
cd Capstone-handoff
```

비공개 저장소 접근 권한과 본인의 GitHub 인증이 필요하다. 팀원의 인증정보나 실험 키를 커밋하지 않는다.

## 3. 로그 압축본 확인·해제

[capstone-handoff-20261022-v3.tar.gz](capstone-handoff-20261022-v3.tar.gz)는 약12.9MB이며 MD 문서, 실험 로그, 당시 소스 스냅샷을 포함한다.

macOS:

```bash
cd handoff/2026-10-22
shasum -a 256 -c capstone-handoff-20261022-v3.tar.gz.sha256
mkdir -p ../../tmp/handoff-review
tar -xzf capstone-handoff-20261022-v3.tar.gz -C ../../tmp/handoff-review
cd ../../tmp/handoff-review/capstone-handoff-20261022
shasum -a 256 -c SHA256SUMS
```

Linux에서는 shasum 대신 `sha256sum -c`를 사용할 수 있다.
압축본 내부 README.txt와 FILES.json에서 자료 목록과 원본 대비 비식별 처리 여부를 확인한다.
해제한 로그는 tmp에 유지하고 다시 Git에 추가하지 않는다.

## 4. 마지막까지 포함된 결과

| 시험 | 결과 |
|---|---|
| 유형 실험360회 | 360 유효, C3 ECU/IVI MATCH120/120 |
| 실제 화면 | 가변저항 반영·네 공격 경보 사용자 확인 |
| 고정 정상 FPR | 규칙0/298, 규칙+IF2/298(약0.67%) |
| 조작 정상 FPR | 두 방식0/298 |
| replay 단일 시험 | auth16송신·동일 payload거부16(counter11/orphan5) |
| MAC 반복 | 일치 후보30/30 MAC_REJECTED |
| flooding 마지막 관찰 | 9981송신, 노출 구간 BMS119게시, 평균100.085ms·최대100.564ms |

**flooding 결과는 해당 부하에서 갱신 유지 관찰이며 전체 드롭·BUS-OFF·일반 가용성 보장이 아니다.**
공식1200회·재부팅 자동실행 확인은 오늘 제외한 후속 항목이다. 일반 반복 replay/차단율 확대 검증도 별도다.

## 5. 공유 범위와 재현 주의

- SecOC 키·SSH 개인키·실제 PC 접속 설정은 포함하지 않는다. 실행용 설정은 인수자가 별도로 구성한다.
- 주소·계정 등 일부 문자열은 공유 사본에서 치환했다. 원본 manifest와 공유 사본 해시가 다른 파일은 FILES.json에서 확인한다.
- 공유 사본은 기존 실험의 --resume 입력으로 사용하지 않는다.
- source/manual은 당시 실행 스크립트의 증거 사본으로 경로 치환이 있어 그대로 실행하지 않는다.
- 당시 장비의 직접 수정본과 PC campaign 소스 해시를 보존했다. 현재 Git HEAD만으로 과거 실행 환경을 단정하지 않는다.
- 원본은 기존 PC·장비에 보존했다. 저장소에는 사용자 요청에 따라 이 전달용 압축본 한 개만 예외적으로 포함한다.
