# CHG-015 검증 기록

2026-10-03, develop dirty worktree. 사용자 변경과 001 패키지를 보존하고, stage/commit/push 없이 로컬 준비만 수행했다. Pi 접근·실제 키 열람·CAN 재설정·기존 서비스 종료는 하지 않았다. 프로젝트 SKILL의 작은 파일럿 우선, 데이터 분리, 목표/실측 구분 원칙을 적용했다.

## 구현과 경계

| 항목 | 구현/회귀 확인 |
|---|---|
| 사용자 행동 순서 | 루트 `임시_할일.md`: 먼저 복사·checksum·환경 수집·빌드만, 실패 시 중단, 결과 반환 후 다음 실행 |
| M5 설정 | argv/REPLACE/format/run ID/원격 제한 시간/동일 Node B 검사. 하네스 실행 전에도 적용. 실제 SSH 준비 판정은 아님 |
| IF 점수·ROC | 기존 sklearn train_model, normal manifest, distinct run/source SHA, 완전 1초 비중첩 윈도우, calibration에서만 후보 선택, evaluation 고정 적용 |
| 분석 회귀 | 완전 분리·동점 AUC·실패 후보·각 공격 목표·최종 평가 재조정 금지·손상/누락/중복/NaN/bool·실제 sklearn 경로 |
| 반환 자료 판정 | seal 이후 원본 hash 검사, dump+수신기 source_data/auth 순서 상관, long-gap Fail-safe 독립 counter, MAC_FAIL 미게시/동일 counter 복구 |
| 안전 경계 | 증거 환경/interface 불일치 시 seal 생성 전 거절. 새 보고 폴더/파일만 허용. 불완전 자료를 합격으로 바꾸지 않음 |

오프라인 IF 윈도우 FPR/AUC는 live 전체 IDS 0x200 FPR/공식 trial 탐지율이 아니다. 모델 후보를 제품 임계나 IF 송신 정책에 자동 적용하지 않는다. 사용자 ground truth와 완료/수집 시간 메타데이터의 사실성은 실제 원본·장비 로그와 함께 인수해야 한다.

## 실제 검증

- Linux ARM64 VM Python pytest **59 passed**, 실제 sklearn 점수 생성 포함. macOS 기본 Python의 좁은 시험은 실제 sklearn 의존성 부재로 해당 1개를 skip했으며, Linux 전체 실행에서는 skip 없이 통과했다.
- 이번 vcan91 M5 재실행 **12/12 VALID**, matrix_complete=true, official_1200_complete=false. 실제 MAC 변조 차단/75→70 복구, silent pending TIMEOUT도 smoke 내부에서 확인.
- vcan 원본 산출물: 로컬 VM `/tmp/capstone-review-vcan-mgba0met/`. 더미 키만 사용했으며 raw journal/키/모델은 저장소에 넣지 않았다. 1,000fps 연결 smoke이지 물리 버스 부하 ≥50% 인수가 아니다.
- 새 002 archive의 **실제 추출 소스**: 135개 파일 checksum OK, Python **59 passed**, Release ECU/IVI 빌드 성공, ECU **16/16**, IVI **12/12** CTest 통과.
- 새 archive 위치: `tmp/pi-handoff-20261003-002/capstone-pi-handoff.tar.gz`.
- archive SHA256: `d7c2cdef1bde5d34c8324e4b9b1e3304d320f776579a15b3e97cc904fa41e07a`.
- 추출/빌드 검증 위치: 로컬 VM `/tmp/pi-handoff-verify-20261003-002/Capstone-handoff/`.
- GCC15.2/Qt6.10.2/GTest1.17/sklearn1.7.2 환경이며 Debian13/Qt6.8의 실제 Pi 검증으로 대신하지 않는다. Qt QML plugin target 경고가 있었지만 빌드·Qt 시험은 통과했다.
- `git diff --check`, Python compileall 통과. bytecode는 `/tmp/capstone-prep-pycache`에 한정했다.

재현:

```bash
python3 -m pytest -p no:cacheprovider security/tests \
  ivi_platform/test/test_period_analysis.py ivi_platform/test/test_pi_handoff.py -q
python3 -m security.experiments.vcan_review_smoke --interface vcan91 \
  --receiver-bin /tmp/pi-handoff-verify-20261003-001/Capstone-handoff/ivi_platform/build-handoff/ivi_dashboard_experiment
```

## 남은 사용자 증거

두 Pi 환경 JSON·빌드 결과 → 정상 CAN·노브·독립 Fail-safe IT-002 → 정상 학습 데이터 → MAC IT-004 → IDS IT-005 → 물리 M5 12회 파일럿 → 설정 동결·공식 1,200회와 별도 live 정상 오탐률/오프라인 ROC. 실제 회로, UI 전체 표시 지연, 물리 부하·최종 성능 수치는 미측정이다. 계약·보안 상태 latch는 보존했다.
