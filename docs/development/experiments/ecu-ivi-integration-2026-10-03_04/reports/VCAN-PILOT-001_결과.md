# VCAN-PILOT-001 원장 검토

세 manifest 모두 COMPLETE, 12시행 모두 VALID다. manifest에 기록된 결과 파일 23개의 SHA256을 검증했다. 원본 압축파일과 내부 파일은 `../raw/VCAN-PILOT-001/`에 보존했고 전체 inventory는 197개다. [시행 요약](../analysis/vcan-pilot-001-review.json)을 참조한다.

| 구성 | 결과 |
|---|---|
| 1: 무방어 | replay·spoofing 수용 관측. fuzzy의 범위 밖 후보는 파싱 거부. flooding 정상 전달 30/30 |
| 2: SecOC | spoofing 공격 수용 0. replay는 공격 귀속 수용 1건과 인증 거부 1081건이 함께 기록됨 |
| 3: SecOC+규칙 IDS | 4종 모두 탐지. replay·spoofing 공격 수용 0. IF 미사용 |

전 시행에서 attack_sent=attack_seen, 송신 오류 및 관측 rx_dropped는 0이다. Config 3의 경보 수신 지연은 flooding 0.410ms, fuzzy 0.177ms, replay 0.339ms, spoofing 1.450ms다. 같은 호스트 vcan·참조 수신기 결과이며 물리 CAN이나 IVI 제품 판정이 아니다. product_verdict는 NOT_RUN으로 유지한다. 목표 1000fps는 설정값이며 실제 3초 송신 건수는 2051~2424로 목표 송신률 달성을 주장하지 않는다.

## Config 2 replay 수용 1건의 원시 기록

`results/vcan-pilot-001-c2/replay-001.jsonl`에서 다음 순서를 확인했다.

1. 정상 BMS payload `c8c81068ffec4100` 수신.
2. 동일 payload의 공격 BMS가 pending을 교체(34131.105214157).
3. 정상 ECU의 새로운 인증 프레임 `8374e1e7000000ba` 수신(34131.1054763).
4. 결과 PUBLISHED, own=true, auth_own=false.
5. 과거 인증 프레임 `53b38ff900000097`은 AUTH_ORPHAN 거부.

따라서 이 1건을 과거 인증 counter 재사용 성공 또는 MAC 위조 성공으로 설명할 수 없다. 동일 payload가 정상 인증 프레임과 결합한 관측이다. 현재 judge_trial은 replay 성공을 own=true인 PUBLISHED 존재 여부로 집계하므로 attack_success=true가 된다. blocked=true는 일부 인증 거부가 존재한다는 뜻이지 시행 전체 차단을 의미하지 않는다. 정상 전달 29/30의 귀속도 이 교체와 함께 해석해야 한다.

**판정: 실행·저장 경로의 vcan pilot 완료. replay 성공 지표의 의미 검토는 필요하며 12개 보안 시험 전체 합격으로 표기하지 않는다.** 원장은 수정하지 않는다. 본 실험 전 과거 인증 재수용과 동일 payload의 정상 인증 결합을 구분할 보고 기준을 확정해야 한다. Config 3의 규칙 전용 pilot은 IF 성능 완료를 대신하지 않는다.

## 판정 정의 대조 결과

M5 §3의 replay 성공 정의는 재생 프레임의 수용 관측이다. 현재 구현의 own PUBLISHED 판정은 이 넓은 정의에 해당하므로 관측된 1건을 삭제하거나 실패로 뒤집지 않는다. 이를 과거 인증 counter 재수용으로 해석하는 설명이 부정확한 것이다. 기존 성공 지표는 유지하고 보고서에서 동일 payload/새 정상 인증 결합과 과거 인증 프레임 재사용을 구분한다. 코드·ICD·임계는 변경하지 않았다. 이 결과는 참조 수신기 관측이며 물리 IVI에서도 동일하게 발생한다고 가정하지 않는다. 물리 pilot 준비를 막는 실행기 오류로 판정하지 않는다.

## IVI 담당자 물리 pilot 준비 회신

사용자 전달 회신 기준이며 아직 실행 증거는 아니다. IVI 004-verified 전달본의 실험용 `ivi_dashboard_experiment`는 `--experiment-secoc-off --confirm-isolated-test-bus`로 Config 1을 준비한다. Config 2와 Config 3은 일반 `ivi_dashboard --secoc-key /etc/ivi/secoc.key`를 각각 새 인스턴스로 실행한다. 공통으로 `--interface can0 --run-id <구성별 ID> --observation-jsonl <새 폴더>/receiver.jsonl`을 사용하고 표본 수 자동 종료는 적용하지 않는다.

대응 ID는 Config 1 SECURITY-PILOT-OFF-001, Config 2 SECURITY-PILOT-ON-001, Config 3 SECURITY-PILOT-IDS-001로 구분한다. Config 2와 3이 같은 ON 프로세스의 counter 이력을 공유하지 않도록 한다. 하네스는 IVI 실행을 제어하지 않으며 READY·캡처 시작 확인 이후 송신한다. 오류 프레임 포함 candump, CAN 전후 통계, 종료코드를 함께 보존한다. SPI 1MHz·CAN 500kbps 유지, 물리 버스 점유율 계측 도구 준비는 별도 확인 필요다.
