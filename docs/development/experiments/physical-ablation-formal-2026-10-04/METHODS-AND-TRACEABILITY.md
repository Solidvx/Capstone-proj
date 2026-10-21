# 실험 방법·편차·요구사항 추적

## 운영 결정 DEV-EXP-001

2026-10-04 사용자 지시로 ‘유효 100회가 될 때까지 보충’ 대신 ‘오류도 원장에 남기며 계획 100회 수집’으로 운영했다. [TEST_PLAN](../../../TEST_PLAN.md)의 원래 100유효 기준 자체를 소급 완화하거나 기존 INVALID를 유효로 바꾸지 않는다. 수집 완료 표와 원래 기준 충족 여부를 분리한다.

C1 flooding은 첫 실패 trial 7을 재시도했으므로 101시도다. 기본 분석은 최초 시도 선택으로 98 VALID/2 INVALID, 전체 시도는 99 VALID/2 INVALID다. C3 flooding은 98 VALID/2 INVALID로 원래 100유효 조건이 미충족이다. 나머지 조건은 실행기상 100 VALID이나 외부 손실·경보 출처·수신기 판정을 따로 검토한다. INVALID 제외 탐지율만 제시해 시도 실패가 사라지게 하지 않는다.

## 버전·환경

- 004 IVI 전달본, CAN 500kbps; 본 실험 ECU SPI 2MHz·IVI SPI 1MHz·ECU qlen10 조건. 실제 run별 환경은 raw meta가 원천이다.
- flooding 요청 2800fps, 나머지 요청 1000fps; 공격 3초/기준 구간 2초/후속 1초. 요청 fps와 실제 송신률·점유율은 다르다.
- C1 flooding 중 v5/v6, C3 flooding 중 v7/v8로 실행/계측 코드가 바뀌었다. `publication/runs/*/summary.json`에 소스 전체 해시와 시계·이전 run 연결을 기록한다. 결과를 동일 버전의 통제 비교로 과장하지 않는다.
- IF 학습·보정·독립 평가는 각각 다른 300초 캡처이며 평가 298창이다. constant 정상 조건의 오탐 규칙0/298, 규칙+IF1/298. 이 결과는 다른 운전 조건·최종 실시간 버전 전체 인수나 IF의 공격 탐지 추가 기여를 입증하지 않는다.

## 지표와 사용 제한

원본 판정을 보존한 기계 표는 [TABLES](publication/TABLES.md), 전달/게시 표는 [DELIVERY](publication/DELIVERY.md), 오류와 출처는 `publication/runs`를 따른다. run마다 통계·지연을 제시하고 버전이 다른 구간은 별도 표본으로 유지한다.

- C3 flooding 001/002의 dequeue 시각·윈도우 문제 때문에 지연/전달률은 논문 채택에서 제외한다. 002의 62개 전달률>1 원본은 보존한다. 003의 23개 시행만 채택 가능한 지연 부분집합이다.
- reference `attack_success`, 인증 거부가 있었던 시행, 공격 프레임 전량 차단은 서로 다른 지표다. 제품 성공/실패를 참조 판정으로 대체하지 않는다.
- replay의 주입 payload 게시와 새 정상 인증 결합은 과거 인증 counter 재수락과 구분한다. C2의 116건, C3의 137건 출처 분석은 각 보고서와 신규 순서 대조로 연결한다.
- C2/C3 fuzzy의 주입 0x200 중 경보로 처리된 입력은 실제 IDS 탐지로 집계하지 않는다. Config3에서는 IDS ALERT_SENT와 ECU 비주입 경보 및 IVI 수신을 별도 비교한다.
- C1 spoofing 1개, C3 spoofing 2개 주입 프레임 차이 및 CAN 오류 증가는 보존한다. VALID 100개를 무손실 100회로 해석하지 않는다.
- qdisc dropped/requeues는 전후 차이를 쓰며 CAN 전송 후 손실로 동일시하지 않는다. 입력·원본 통계는 run별 meta/crosscheck에 있다.
- Qt 경고, 화면 캡처 없음, 정확한 프로세스 실행 시각 없음은 당시 미수집 한계다. before/after-time은 기록 저장 시각이다. T4는 frameSwapped 대리 지표이며 물리 픽셀 시각이 아니다.

## TC/요구사항–증거 연결

| 기준 | 관련 근거 | 현재 판정 범위/잔여 한계 |
|---|---|---|
| NFR-SEC-003, TC-EXP-001 spoofing | publication/cases/C1~3-spoofing 및 각 run/report | 3구성 수집, IDS 유효 시행 탐지와 게시 출처 대조; C1/C3 수신 차이 포함 |
| NFR-SEC-003, TC-EXP-002 replay | publication/cases/C1~3-replay 및 attribution 보고서 | 새 정상 인증 결합과 옛 counter 거부 구분; 게시를 전부 인증 우회로 해석하지 않음 |
| NFR-SEC-003, TC-EXP-003 flooding | publication/cases/C1~3-flooding, load-check/부하 분석 | 수집 완료, INVALID·재시도·버전 변경 포함; 100유효 및 C3 전체 지연 인수 미충족 |
| NFR-SEC-003, TC-EXP-004 fuzzy | publication/cases/C1~3-fuzzy, 경보 출처 분석 | 주입 0x200과 IDS 송신 구분; 탐지율과 분류 정확도 별도 |
| NFR-SEC-004, TC-EXP-005 | [NORMAL-IF](../ecu-ivi-integration-2026-10-03_04/reports/NORMAL-IF-20261004-064946_결과.md) | constant 독립 재생 평가 298창 수치 조건 충족; 실시간 모든 버전으로 일반화 불가 |
| TC-SEC-005-d | C1/C2/C3 flooding의 기존 crosscheck/load-check 및 원본 canbusload | 공격 내부 완전한 1초 표본의 ≥50% 관측; 시작 1초 이내 상승을 동일 주장으로 대체하지 않음 |
| NFR-PERF-003, TC-PERF-003 | publication/TABLES.md, run별 지연/미탐지/INVALID | 참조 관측 호스트 기준; C3 flooding v8 23회 부분집합. IVI 화면 지연 아님 |
| NFR-PERF-001, TC-PERF-001 | [PERF-FORMAL-002](../ecu-ivi-integration-2026-10-03_04/reports/PERF-FORMAL-002_결과.md) | 1,000표본 Qt 경로 평균6.473276ms·최대65.029527ms; 물리 픽셀 미측정 |
| NFR-PERF-002, TC-PERF-002 | 같은 PERF-FORMAL-002 보고서·양측 CAN 원본 | 정상 성능 시험의 주기 근거; 공격 중 정상 전달과 분리 |
| TC-INT-003, 공동 IT-002 | [IT002-KNOB-001](../ecu-ivi-integration-2026-10-03_04/reports/IT002-KNOB-001_결과.md) | WARNING/CRITICAL 인증 간격32.626초, 화면은 사용자 관측·별도 캡처 없음 |
| TC-INT-004 | Config3 IDS/IVI 경보 대조 | CAN 경보 도착 증거 있음, 화면 표시 시각·정확한 분류 일치 전체 인수 아님 |
| TC-SEC-002/003, 공동 IT-004 | MAC/counter 관련 단위·참조·Ablation 기록 | 전용 변조 fixture의 물리 화면/복구 인수를 Ablation으로 대체하지 않음 |

## 제출용 사용법

표에는 분모·INVALID·재시도·버전·측정 종료점을 함께 기재한다. ‘모든 TC PASS’, ‘IF가 단독으로 모든 공격 탐지’, ‘물리 화면 지연 측정’, ‘무손실 전송’ 같은 근거 범위를 넘는 결론은 쓰지 않는다. 미수집 근거를 새 수치로 채우지 않으며 추가 측정은 필요한 주장 범위를 정한 뒤 별도 결정한다.
