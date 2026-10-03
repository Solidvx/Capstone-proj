# CHG-014 검증 기록

2026-10-03, develop dirty worktree에서 CHG-013의 리뷰 후속 수정. 기존 사용자 변경은 보존했으며 commit/stage/push하지 않았다. ICD CAN ID/DLC/스케일·HMAC 입력·counter·HAL 계약은 변경하지 않았다.

## 수정 범위

| 발견 사항 | 반영 |
|---|---|
| 혼합 공격에서 낮은 타입 경보가 계속 밀림 | 타입별 최신 이벤트를 유지하는 최대 4개 FIFO, 전역 100ms 송신 간격. 연속 flooding 혼합 회귀시험 |
| 손상 DLC·다른 target으로 주기 PASS 가능 | v2 schema, target=0x100 고정, DLC8·standard data·시각·hash·통계 엄격 검증 |
| 정상 학습 데이터가 비거나 불연속이어도 성공 | capture COMPLETE/INVALID·3초/각25프레임·300ms 공백·payload·hash 검증, manifest 학습 시 필수 |
| IDS 준비 이전 공격 가능 | socket open·모델 준비 후 run ID 포함 READY, ready-file 새 파일 |
| 공격 실패 시 성공 송신 수/기록 손실 | 상태 manifest와 TX_ACCEPTED journal, OSError/SIGINT 성공 수 보존 |
| 송신 수락 시간을 실제 버스 주입으로 표시 | 필드 이름·시간 의미 수정, 동일 Node B whole-bus clock 지연 계측 |
| raw만 재전송해 freshness 거부를 검증 못함 | 과거 raw/auth 쌍 replay·counter 거부 관측, pair fps 상한 검증 |
| 제품 수신기가 무방어 구성 불가능 | 제품 인증 유지, 별도 opt-in experiment 타깃에만 인증 OFF, 기본 바이너리에서 OFF 거부 |
| 실행 Ablation·분모/증적 관리 미구현 | READY·프로세스 수명·12개 cell·seed·독립 수용/거부/탐지·입력 hash·시행 원장·artifact hash·INVALID/미실시 집계 |
| null/list manifest traceback | INVALID 반환 및 회귀시험 |

추가 실행에서 발견한 동일 노드 socket 기록 순서 차이는 수신기 상관 분석에 10ms pre-roll을 주어 처리했다. 검출 지연 기준은 observer의 실제 수신 시각을 유지한다. 관측 QFile과 pending 원장에는 mutex를 적용하고 callback/10ms timer의 AUTH_TIMEOUT을 해당 raw 입력에 연결한다. 정상 sender 종료는 진행 중인 인증 쌍을 끝낸 뒤 처리해 불완전 쌍으로 availability 실패를 만드는 것을 방지했다.

## 실제 실행 결과

| 검증 | 결과/범위 |
|---|---|
| Python pytest | 46 passed, Linux Python3.14 / sklearn1.7.2 / pytest9.0.2 |
| Linux IVI CTest | 12/12 passed, Qt6.10.2 / GCC15 / ARM64 VM |
| Linux ECU CTest | 16/16 passed, GTest1.17.0; 기존 310-row fail-safe profile 회귀 포함 |
| 기본 제품 인증 OFF 시도 | exit2, separately built experiment required |
| 실제 vcan MAC 변조 | baseline75 게시→MAC_FAIL/위조100 미게시→같은 counter recovery70 게시 |
| silent pending | TIMEOUT 기록에 위조 raw 대응 확인 |
| M5 vcan 파일럿 | 3구성×4공격 각1회, 12 VALID·입력 hash 동일·matrix_complete=true |
| 공식 물리 1,200회 | 미실행, official_1200_complete=false |

`git diff --check`와 Python compileall도 통과했다. macOS 기본 bytecode cache 경로는 sandbox 밖이므로 `/tmp/capstone-review-pycache`로 명시해 검사했다. Linux 검증용 패키지와 독립 vcan91은 기존 VM에만 준비했으며 사용자 Raspberry Pi에는 배포/설정 변경하지 않았다.

재현 명령:

```bash
python3 -m pytest -p no:cacheprovider security/tests ivi_platform/test/test_period_analysis.py -q
cmake -S ivi_platform -B /tmp/ivi-review-linux -DIVI_BUILD_EXPERIMENT_TOOLS=ON
cmake --build /tmp/ivi-review-linux -j4
ctest --test-dir /tmp/ivi-review-linux --output-on-failure
cmake -S adaptive_ecu -B /tmp/ecu-review-linux -DECU_BUILD_TESTS=ON
cmake --build /tmp/ecu-review-linux -j4
ctest --test-dir /tmp/ecu-review-linux --output-on-failure
python3 -m security.experiments.vcan_review_smoke --interface vcan91 \
  --receiver-bin /tmp/ivi-review-linux/ivi_dashboard_experiment
```

최종 원본 증적은 Linux VM `/tmp/capstone-review-vcan-r6n3qy6x/`에 보존했다. 임시 dummy key만 사용했다. 가벼운 [요약](vcan-summary.json)을 이 기록에 보존하고 대량 journal·모델·키는 저장소에 넣지 않는다.

3,000fps 사전 smoke 중 한 구성에서 898 vs 900프레임 입력 차이가 발생했다. 이 run은 `/tmp/capstone-review-vcan-6e63ujwa/`에 matrix_complete=false로 보존했다. 최종 연결 smoke는 1,000fps로 분리했고 실제 flooding ≥50% 인수로 표시하지 않는다. 물리 calibration에서 rate/시간/부하를 확정한 뒤 본 실험을 동결해야 한다.

## 미검증/후속 인수

- 실제 RPi/ADS1115/MCP2515, Debian13/Qt6.8 장비 빌드·물리 CAN 실행은 별도.
- physical bus load, 전체 UI 표시 지연, 정상 FPR/ROC·threshold calibration, 공식 1,200회 결과는 미실행. 미측정값은 null이며 목표값으로 채우지 않았다.
- fixture는 구성 간 입력을 일정하게 하기 위한 시험 송신기다. 제품 ECU의 자체 실시간 처리량/방어 성능 인수를 대신하지 않는다.
- CRITICAL latch는 계약대로 유지한다. 노브를 올려 자동 해제하도록 바꾸지 않았다. 정상 데이터 수신과 안전 상태 복구를 구분해 재시험한다.

## 사용자 수동 Pi 실행을 위한 후속 인계

사용자 요청에 따라 Pi 접속·명령·실제 로그 수집은 사용자가 담당한다. 로컬에서 작업본 snapshot 패키지, 키를 읽지 않는 환경 자료 수집 CLI, [수동 실행 안내](../../../development/playbooks/pi-manual-handoff.md)를 준비했다. 새 시험 디렉토리 사용으로 기존 Pi 프로젝트/키/설치 경로를 덮어쓰지 않는다. 커밋/푸시나 원격 Pi 접근은 수행하지 않았다.

- 생성기: `ivi_platform/scripts/prepare_pi_handoff.py`.
- 수집기: `ivi_platform/scripts/collect_pi_preflight.py` (COLLECTED와 PASS 구분, command 실패 보존, 새 출력만 허용).
- 전달 폴더: 저장소 제외 경로 `tmp/pi-handoff-20261003-001/`.
- archive: `capstone-pi-handoff.tar.gz`, source 126개, 약 145KiB.
- SHA256: `e96f9c851e68b5f93d9179a4f3c5f105900971ab707977a60b1942c2112dd2e5`.
- 키/.env/모델/build 제외·미커밋 포함·심볼릭 링크 거부·키 내용 미열람 회귀시험 3개 추가.
- Linux `/tmp/pi-handoff-verify-20261003-001/`에서 **실제 archive를 추출한 코드**로 전체 source checksum·Release ECU/IVI build·ECU16/16·IVI12/12·Python49 passed 확인.
- Qt6.10.2 동적 QML plugin target 경고는 발생했으나 build와 Qt 시험은 통과했다. Debian13/Qt6.8의 실제 Pi 환경 검증은 반환 자료를 기다린다.

이 기록은 장비 배포/물리 시험 완료 기록이 아니다. 사용자에게 먼저 환경 JSON·빌드/시험 결과를 반환받고 정상 CAN→MAC→IDS→물리 M5 순서로 인수한다.
