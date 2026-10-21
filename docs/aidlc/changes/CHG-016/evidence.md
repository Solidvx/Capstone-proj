# CHG-016 검증 기록 — 독립 가능한 선행 준비

2026-10-03, develop dirty worktree. 사용자 Pi 실행/로그 없이 시험 준비 범위의 코드를 보완했다. 관련 사용자 변경·001/002 패키지를 보존했으며 stage/commit/push/원격 Pi 접근을 하지 않았다. 프로젝트 SKILL의 계약 유지·작은 파일럿·분리 데이터·정직한 분모/환경 원칙을 적용했다.

## 반영

- `run_normal_fpr.py`, `analyze_normal_fpr.py`: 소유한 receiver/normal/IDS READY·수명 검증, Node B bounded observer natural END, 고정 정상 윈도우 100개, wire 경보 FP/TN, 원본 해시·전후 driver counters·socket overflow·정상 입력 공백/프레임 형식 검증. 중단/미실시/손실/분모 미달을 0% PASS로 바꾸지 않는다.
- `bus_observer.py`: READY/END에 단조 timestamp·구간·프레임 수·상태·전후 interface 통계. `SocketCanTransport`는 observer의 opt-in overflow tracking에서만 recvmsg/SO_RXQ_OVFL을 사용하며 기존 기본 입출력 경로는 유지한다. Linux UAPI `/usr/include/asm-generic/socket.h`의 상수 40을 실제 확인했다.
- IDS READY에 send_alerts를 명시. IF_ANOMALY는 미분류 로컬 진단으로 유지하고 임의 AttackType/새 wire 코드를 넣지 않았다.
- headless ROC SVG·JSON 혼동 원수/N06 보조 지표·summary CSV·REP-1=A 원장 비교. 분모 0 null, 비율/percentage point 구분, 설정/코드/실제 입력/seed·독립 run 검증.
- sklearn/NumPy/Python/학습·특징·IF 소스 hash를 모델 정의에 기록. 윈도우 ID 검사에서 반복 전체 스캔 대신 run별 인덱스를 집계한다.
- Popen 실패 시 양쪽 로그 핸들 닫기와 회귀시험. `how_to_train.md`·README manifest 인자·M5/M7 “미구현” drift·ASan 성공 문자열 오해 정정.
- ECU/IVI `ENABLE_ASAN` 기본 OFF, GCC/Clang 전용, ECU coverage 동시 ON 거절. 제품 빌드·ICD/HAL·SecOC 인증·CRITICAL latch는 변경하지 않았다.

## 실제 결과

| 실행 | 결과·인정 범위 |
|---|---|
| Linux 전체 Python | **71 passed, 9 subtests passed**. 실제 sklearn, 새 실패/중단/분모/그림/CSV/재현/핸들 회귀 포함 |
| wire FPR 작은 파일럿 | 정상 수집 3윈도우·INSUFFICIENT_WINDOWS 종료코드 2. 고정 분모 부족을 기대대로 표시 |
| wire FPR vcan91 | **FP 0 / 정상 100윈도우**, TN100/FPR0.0·관측 목표 PASS. official_acceptance=false, 물리 결과 아님 |
| wire FPR 재집계 | 최종 분석기로 hash/설정/전체 원본 재검사 후 PASS |
| M5 반복 파일럿 | 같은 설정으로 12회 행렬 두 번, 두 run 각 12 VALID, matrix_complete=true |
| REP-1 비교 | 12개 조합 최대 성공률 차이 **0.0%p**, PASS. 각 cell 1회 파일럿이며 공식 100회 반복/통계 신뢰성 아님 |
| 실제 summary CSV CLI | 검증 원장에서 12행 JSON/CSV 생성. 공식 1,200회 상태 false |
| 실제 sklearn→ROC SVG CLI | 합성으로 표시한 별도 fixture에서 **NO_FEASIBLE_THRESHOLD**, SVG 생성 성공. 불충족 후보를 PASS로 바꾸지 않음 |
| ASan + LeakSanitizer ECU | Debug **16/16 CTest 통과**, ASAN_OPTIONS=detect_leaks=1 |
| ASan + LeakSanitizer IVI | Qt/product/experiment 빌드와 **12/12 CTest 통과**, detect_leaks=1 |
| 003 실제 archive 추출 | 144개 source checksum OK, Python71/9 subtests, Release ECU16/IVI12 통과. ASan 기본 OFF 제품 빌드도 검증 |
| 정적 점검 | Python compileall·git diff --check·새 문서 로컬 링크 확인 |

로컬 VM 환경은 Linux ARM64/GCC15.2/Qt6.10.2/GTest1.17/sklearn1.7.2/Python3.14이며 실제 Pi의 Debian13/Qt6.8 검증으로 대신하지 않는다. Qt QML plugin target 경고가 있었으나 제품/experiment와 Qt 시험은 통과했다. 이 시험은 짧은 소프트웨어 회귀이며 장시간 운용·CPU/RSS 목표·실제 물리 부하 인수는 아니다.

## 증거 위치·재현

모두 로컬 Linux VM 임시 경로다. 더미 키만 사용했고 raw·키·대형 산출물은 Git에 넣지 않는다.

- `/tmp/capstone-normal-fpr-pilot-20261003-001/`
- `/tmp/capstone-normal-fpr-100-20261003-001/` (`final-recheck.json` 포함)
- `/tmp/capstone-rep-a-20261003-001/`, `/tmp/capstone-rep-b-20261003-001/`
- `/tmp/capstone-rep-comparison-20261003-001.json`, `...rep-b...summary.json/csv`
- `/tmp/capstone-roc-cli-20261003-001/analysis/`
- `/tmp/capstone-ecu-asan-20261003-001/`, `/tmp/capstone-ivi-asan-20261003-001/`
- `/tmp/pi-handoff-verify-20261003-003/`: archive checksum log·추출 소스·독립 Release builds.

```bash
python3 -m pytest -p no:cacheprovider security/tests \
  ivi_platform/test/test_period_analysis.py ivi_platform/test/test_pi_handoff.py -q
python3 -m security.experiments.run_normal_fpr \
  --settings /tmp/capstone-review-vcan-mgba0met/settings.json \
  --output-dir /tmp/NEW-fpr-run --run-id NEW-fpr-run \
  --interface vcan91 --environment vcan --windows 100 --warmup 2 \
  --confirm-product-ecu-stopped
python3 -m security.experiments.verify_reproducibility \
  --previous /tmp/capstone-rep-a-20261003-001 \
  --current /tmp/capstone-rep-b-20261003-001 --output /tmp/NEW-repro.json
```

실행된 두 matrix는 당시 동일 tool hash를 보존한다. 이후 소스 수정본과 과거 matrix의 tool hash를 섞어 새 동일 버전 반복으로 주장하지 않는다. 현재 도구는 과거 두 원장을 그대로 재판정할 수 있다.

새 사용자 전달 package는 제외 경로 `tmp/pi-handoff-20261003-003/`에 있으며 archive SHA256은 `a9d8bbf85b27e6aaefb1e4b467d908c255a2ec67aa466751190d48fde66fdb16`이다. archive에는 실제 키/장비 주소/바이너리/모델/원시 logs가 없다. 내부 HANDOFF-FILES.sha256을 검증하고 Pi에서 다시 빌드한다.

## 완료와 남은 일의 경계

[독립 준비 완료표](../../../development/playbooks/pre-hardware-readiness.md)의 코드/도구/로컬 검증을 완료했다. 사용자의 다음 행동은 루트 임시_할일.md의 기존 1~4번으로 유지한다. 물리 IT/TC·대표 정상/독립 공격 자료·최종 threshold 적용·공식 1,200회·장시간 Pi 안정성·픽셀 표시 지연·CPU/RSS/실제 부하·계약 확정 전 IF/새 세션 정책은 인수 대기다. 미측정 숫자나 외부 변경으로 이 경계를 메우지 않는다.
