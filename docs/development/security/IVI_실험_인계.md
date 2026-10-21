# IVI 시험 모드·수신 관측 인계 (EXQ-8)

2026-10-03 사용자 결정: IVI 담당자가 구현하며 이 작업에서는 IVI 제품 소스를 변경하지 않는다. wire·HAL API를 변경하지 않는다. [실행 절차](../playbooks/live-security-validation.md)와 [CHG-014](../../aidlc/changes/CHG-014/aidlc-state.md)에 연결한다.

## 실행 모드

- 기본 제품 실행은 인증 필수로 유지한다. 시험 전용 실행 파일 또는 명시적 시험 설정에서만 SecOC OFF를 허용하고 화면/로그에 표시한다. 데모 snapshot 모드는 실제 CAN 수신 시험을 대신하지 않는다.
- Config 1: 실제 CAN raw를 기존 파서로 검사한 뒤 인증 없이 반영. Config 2/3: 기존 SecOC 검증 성공 후에만 반영. Config 3의 IDS는 Node A에서 실행한다.
- 모드·소스 커밋·바이너리·키 종류(실제 값/해시 제외)·수신 준비 완료를 로그에 남긴다. 원격으로 모드를 바꾸는 새 CAN 메시지는 만들지 않는다.
- 구성별 독립 시험 인스턴스를 시작한다. 시행마다 제품 counter를 초기화하지 않는다. 재부팅/복구 시험은 별도 사례다.

## 남길 관측

| 범위 | 필요한 필드 |
|---|---|
| 공통 식별 | run_id, config, 환경, 소스/빌드 식별, 인증 모드, 수신 준비 시각 |
| 원시 수신 | Node B monotonic 수신 시각, CAN ID, DLC/flags, payload, 순번 |
| 인증 | 대응 원본/auth 순번·counter, MAC/윈도우 검사 결과, pending 교체/만료/orphan, 사유 |
| 상태 | 수용/거부, 반영 전후 SOC·Fail-safe·last-good·measurement sequence |
| IDS | `0x200` 수신·유형·sequence, UI banner 반영/렌더 시각 |
| 신뢰성 | 수신 손실/오류, 앱 시작/종료, 링크 장애/복구, 미반영 표본 |

키 자체를 로그에 기록하지 않는다. 참조 수신기 raw 파일과 CAN ID/payload/counter/프레임 순서로 대응한다. 서로 다른 노드의 monotonic 값을 직접 빼지 않는다. 정확한 시행 경계와 공격 귀속을 대응할 수 없으면 `unmatched`로 남기고 해당 제품 지표의 인수를 보류한다.

## 인수 사례

1. Config 1에서 정상 raw가 실제 화면에 반영되며 시험 모드가 표시된다.
2. Config 2/3에서 인증 실패 raw는 반영되지 않고 정상 쌍은 계속 갱신된다.
3. IT-004의 더미 키 fixture: 정상 → MAC 1비트 변조 거부 → 동일 next-counter 정상 수용. counter 오류·orphan·timeout 거부로 MAC 실패를 대신하지 않는다.
4. IT-002: ECU 프로파일/노브 각각의 WARNING→CRITICAL, 간격이 긴 `0x103` 두 건 수용.
5. IT-005: Node A 경보가 Node B에 도착하고 화면에 표시됨. 공격→경보 수신과 공격→화면을 별도로 기록한다.
6. TC-PERF-001: 기존 T1~T4 CSV 1,000표본과 누락 수를 인계한다.

수신기 설정·실행 CLI와 위 관측 로그의 실제 스키마를 전달받은 후 공동으로 하네스 결과와 대응한다. 이 문서는 준비 요청이며 팀원 구현·시험 완료를 뜻하지 않는다.
