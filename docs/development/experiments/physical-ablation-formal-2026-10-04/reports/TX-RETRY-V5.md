# 송신 큐 일시 부족 보완 v5

상태: 로컬 구현 및 Linux Python 시험 완료. 실제 Pi 적용·재시험은 미실행.

## 변경과 판정

- ENOBUFS/EAGAIN만 동일 CAN ID와 payload로 재시도한다. 프레임당 최대 5회, 최초 시도 후 5ms와 공격 종료 시각 중 빠른 시각까지다. 스케줄러가 늦게 깨어나면 추가 송신하지 않는다. 이는 운영체제 실행시간 보장이 아니라 재시도 시작 제한이다.
- 소켓 송신은 nonblocking이다. 영구 오류 또는 제한 내 미완료 프레임은 TX_ERRORS/INVALID이며 중단한다. 실제 수신 누락, CAN 오류, 부하 조건은 양측 증거로 별도 판정한다.
- 원본 JSONL에 모든 실패 syscall의 errno, 시각, ID, payload, retry_planned를 보존한다. 성공 기록 tx_retries는 성공까지의 재시도 수다. attempts에는 tx_syscall_errors, tx_recovered_frames, tx_retry_planned_count를 추가한다. planned는 실제 재시도 실행 횟수와 다를 수 있다.
- attack_tx_errors는 최종 미완료 프레임 수다. 이전 버전의 syscall 실패 수와 의미가 달라졌다. 복구된 syscall 오류가 있어도 전송 완료가 가능하므로 qdisc dropped 증가를 숨기거나 오류 0으로 보고하지 않는다.
- 이 변경은 시험 송신 방법의 개정이다. 기존 공식 1~6번 유효 기록과 7번 INVALID를 수정하지 않는다. 버전별 결과를 구분하고 통합 집계 시 개정 사실을 명시한다.

## 재개

새 run ID와 새 출력 폴더에서 --start-trial 7 --trials 94 --previous-run-id ABLATION-FORMAL-C1-FLOOD-001로 계획 시행 7~100을 실행할 수 있다. seed와 raw 파일 번호는 해당 시행 번호를 따른다. previous-run-id는 출처 연결이며 기존 결과 자동 검증이나 자동 합산 기능은 아니다. 기존 무효 7번과 새 시도를 모두 보존하고, 공식 유효 횟수는 양측 검토 후 집계한다. 기존 집계기는 run ID별 결과를 유지한다.

## 검증

WSL Linux에서 python -m pytest security/tests -q: 74 passed in 10.96s. 일시 오류 복구, 영구 오류, 지속 큐 부족, 공격 종료 제한, 스케줄러 초과 대기, 잘못된 재개 범위 및 기존 회귀 시험을 포함한다. 실제 CAN 성능·50% 부하 달성은 이 테스트의 증명이 아니다.

## 적용 범위

readiness-v2에 v3 및 IDS timestamp-v4가 적용된 ECU가 전제다. C++와 ICD는 변경하지 않는다. 패키지 적용 후 Python 전체 시험을 수행하고 IVI 수집 준비 후 새 실행으로 진행한다.
