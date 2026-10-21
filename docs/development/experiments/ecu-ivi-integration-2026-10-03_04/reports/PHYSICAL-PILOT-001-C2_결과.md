# PHYSICAL-PILOT-001 Config 2 ECU 결과

## 현재 판정

물리 can0, SecOC ON·IDS OFF, constant 입력, 4공격 각 1회 pilot이다. 실행 COMPLETE·종료코드 0, 모두 VALID이며 IVI 제품 판정은 자료 대조 대기다. 본 실험 완료 또는 방어 전부 성공을 의미하지 않는다.

[ECU 분석 원본](../analysis/physical-pilot-001-c2-ecu.json), [보존 원장](../inventory.json). 원본 archive와 내부 14파일을 raw/PHYSICAL-PILOT-001-C2에 보존했다. manifest에 명시된 결과 7개 및 각 시행 raw 해시 4개를 검증했다.

| 공격 | 주입 송신/관측 | 공격 게시 | 공격 인증 거부 | 정상 전달/기대 |
|---|---|---|---|---|
| flooding | 1533/1533 | 0 | 0 | 30/30 |
| fuzzy | 1534/1534 | 0 | 0 (파싱 거부 4) | 30/30 |
| replay | 2356/2356 | 1 | 1177 | 29/30 |
| spoofing | 1518/1518 | 0 | 1 | 29/30 |

위 수치는 ECU 참조 수신기의 판정이다. 모든 시행 attack_tx_errors=0, rx_dropped=0. ECU TX는 30,609→38,094로 7,485프레임 증가했으며 CAN 오류·드롭·bus-off 표시값은 전후 0이다. 요청률 1000fps와 실측 주입량은 구분한다. IVI 수신 일치·제품 거부·버스 점유율은 아직 확인하지 않았다.

## replay 수용 1건의 의미

replay-001.jsonl의 monotonic 36320.356817304에 정상 BMS가 들어온 뒤, 36320.357371443에 동일 payload c8c81068ffec4100의 주입 프레임이 인증 대기 데이터를 교체했다. 36320.357930193의 정상 인증 프레임(counter 0xad, own=false)이 이를 인증하여 PUBLISHED, own=true, auth_own=false가 됐다. 바로 다음 주입 인증(counter 0x97)은 AUTH_ORPHAN으로 거부됐다.

따라서 기존 넓은 공격 성공 정의에 따른 attack_success=true·attack_published=1을 보존한다. 이 사건은 과거 counter 인증 프레임의 수용이나 MAC 위조 성공을 입증하지 않는다. 정상 전달 29/30 역시 참조 수신기의 원본 출처 분류이며 IVI가 화면 갱신을 1회 누락했다는 뜻으로 단정하지 않는다. vcan에서 관찰한 동일 payload/정상 인증 결합과 같은 형태다.

## IVI 수령 후 최종 대조

06H09M의 SECURITY-PILOT-ON-001 자료를 보존했다. 앞의 IVI 대기 상태는 아래 결과로 갱신한다. [대조 분석](../analysis/physical-pilot-001-c2-crosscheck.json), [재현 스크립트](../tools/analyze_physical_c2_ivi.py)를 참조한다. 스크립트는 저장소 루트에서 Python으로 실행한다.

| 항목 | 확인 결과 |
|---|---|
| ECU 송신 통계 / IVI RX 증가 / IVI candump | 모두 7,485프레임 |
| ECU 참조 관측 원본 | 7,483프레임. IVI 앞부분과 ID·payload·순서 전부 일치 |
| IVI 추가 끝부분 | 06:05:23.682587 BMS와 06:05:23.683195 인증(counter 0x10f), 정상 한 쌍. ECU 관측 파일에는 없어 전체 양측 원본 완전 일치라고 표현하지 않음 |
| IVI receiver | 필터 대상 4,427프레임과 전부 일치, 모두 SecOC ON |
| 정상 인증 게시 | 전체 수집 구간 271건. 공격별 baseline·post·warmup도 포함한 수량 |
| 과거 counter 거부 | replay 구간 1,177건, counter 151(0x97) |
| MAC_FAIL | spoofing 구간 1건, counter 253(0xfd). 공격 중 기록으로 앞선 정상 시험의 원인 미확정 MAC_FAIL과 구분 |
| 기타 판정 | BMS AUTH_ORPHAN 4, Fail-safe AUTH_ORPHAN 1, invalid Fail-safe 3, invalid BMS 1, invalid IDS 1 |
| 오류·종료 | IVI CAN 오류·드롭·bus-off 증가 0, dashboard와 canbusload 종료코드 0, 두 수집 도구 stderr 비어 있음 |

replay 게시 1건에 대응하는 IVI 0x102 프레임도 Authenticated BMS data published를 기록했다. 출처 분류는 ECU own 표식과 순서 대응에 근거하며, IVI 단독 로그가 주입 출처를 식별한 것은 아니다. 과거 인증 프레임 수용으로 바꾸어 해석하지 않는다. 정상 인증 게시가 이후에도 이어졌다. WARNING/CRITICAL이라는 counter 거부 메시지는 이번 SecOC 처리 기록이며 Config 3 IDS 탐지 증거로 세지 않는다.

### 점유율과 공식 시험 제한

수집 옵션은 `canbusload -t -e can0@500000`. 28개 출력 표본의 최대 표시값은 19%다. 이 값은 도구의 구간별 정수 표시이며 순간 최대나 소수점 정밀 계측값으로 주장하지 않는다. CAN payload·순서 대응으로 주입 프레임을 IVI candump 시각에 연결했으며, 다른 장비 monotonic 시각을 직접 빼지 않았다.

| 공격 | IVI 최초~마지막 주입 시각(KST) | 해당 구간과 겹치는 출력의 최대 표시값 |
|---|---|---|
| flooding | 06:05:01.557020~06:05:04.556161 | 13% |
| fuzzy | 06:05:07.581240~06:05:10.580699 | 12% |
| replay | 06:05:13.608079~06:05:16.605878 | 19% |
| spoofing | 06:05:19.655428~06:05:22.654689 | 12% |

TC-SEC-005-d의 flooding 점유율 50% 이상 조건은 이번 계측으로 충족하지 못했다. Config 2 pilot의 실행·수신·인증 동작 확인은 완료했으나 공식 부하 조건 인수는 미완료다. 송신 강도 조정과 계측 검증을 본 실험 전에 처리해야 하며 이번 시행을 공식 100회 중 하나로 자동 편입하지 않는다. Config 3 및 공식 1,200회도 남아 있다.
