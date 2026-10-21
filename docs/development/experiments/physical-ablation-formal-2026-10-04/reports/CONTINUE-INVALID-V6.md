# 시행 기록 유지 및 계속 진행 v6

사용자 확정: 계획 100회는 유효 100회가 아니라 번호 1~100의 시행 기록이다. 개별 INVALID도 보존하고 다음 번호로 진행한다. 무효 시행 자동 보충은 하지 않는다. 과거 재시도 번호 7은 별도 시도로 보존하며 집계에서 중복을 명시한다.

## 구현

--continue-invalid를 지정하면 판정 완료된 INVALID를 attempts.jsonl에 flush한 뒤 다음 계획 번호로 진행한다. 옵션 미지정은 기존 중단 동작이다. 프로세스 종료, 소켓 예외, 정상 baseline 준비 실패 등 실행 불가능 조건은 계속 중단한다. COMPLETE/exit 0은 계획 수행 완료이며 모든 시행 유효 또는 제품 합격을 의미하지 않는다.

공격 종료 전에 syscall을 한 번도 호출하지 못한 경우 None과 tx_skipped=ATTACK_DEADLINE을 기록하고 TX_ERRORS에 포함하지 않는다. 실제 호출 실패 후 재시도 미완료는 그대로 TX_ERRORS다. tx_deadline_skipped 건수도 시행별 기록한다. 기존 21번은 TX_ERRORS 1, syscall 오류 0으로 이 경계 문제와 부합하지만 원본은 INVALID 그대로 보존한다.

## 현재 기록과 다음 실행

사용자 제공 터미널: 002의 7~20번 VALID 14회, 21번 INVALID, exit 2. IVI 대조와 원본 수령은 아직 미완료다. 001의 1~6번과 합쳐 실행기 VALID는 20회다. 번호 7 중복을 포함해 지금까지 22회 시도했다. 다음 새 실행 003은 --start-trial 22 --trials 79 --previous-run-id ABLATION-FORMAL-C1-FLOOD-002 --continue-invalid로 번호 22~100을 수집한다. 완료하면 번호 1~100 및 과거 중복 시도 하나를 모두 보존한다.

## 검증 및 적용

WSL Linux security/tests 전체 77 passed in 8.42s. 종료 경계 미호출, 실제 오류 재시도 제한, INVALID 정책, 수집기의 미호출 프레임 오집계 회귀 시험 포함. 실제 Pi 적용과 79회 물리 수집은 미실행이다. v5 위에 live_ablation.py와 test_ablation_resume.py를 교체하며 C++ 빌드는 필요 없다.
