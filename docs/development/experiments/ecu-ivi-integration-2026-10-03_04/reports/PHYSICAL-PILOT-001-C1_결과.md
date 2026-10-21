# PHYSICAL-PILOT-001 Config 1 ECU 결과

물리 can0, 무방어, constant 입력, 공격 4종 각 1회. IVI 대응 ID는 SECURITY-PILOT-OFF-001이다. manifest COMPLETE, 실행 종료코드 0, 네 시행 모두 VALID. 결과 파일 SHA256을 manifest와 대조했다. [ECU 분석](../analysis/physical-pilot-001-c1-ecu.json), [보존 원장](../inventory.json)을 참조한다.

| 공격 | 송신/자기 echo 관측 | 참조 수신기 결과 |
|---|---|---|
| flooding | 1527/1527 | 정상 BMS 30/30 전달 |
| fuzzy | 1535/1535 | 범위 밖 후보 4개 파싱 거부, 공격 수용 0 |
| replay | 1545/1545 | 공격 데이터 수용 1545 |
| spoofing | 1539/1539 | 공격 데이터 수용 1539 |

각 시행의 attack_tx_errors 및 rx_dropped는 0이다. ECU TX는 24192→30609로 6417 증가했고 표시 오류 통계는 전후 0이다. 공격 프레임 합계와 TX 증가량은 정상 ECU 프레임 포함 여부가 다르므로 단순 동일성 기준을 적용하지 않는다.

요청 rate는 1000fps지만 공격 구간별 실제 송신 건수는 약 509~515fps에 해당한다. 이 설정이 물리 목표 부하 50%를 달성했다는 근거는 아직 없다. 부하 기록과 완전한 공격 구간의 대응을 확인해야 한다.

## IVI 수령 후 최종 대조

05H49M 전달 자료를 보존하고 [양측 대조 결과](../analysis/physical-pilot-001-c1-crosscheck.json)를 생성했다. **Config 1 물리 pilot의 IVI OFF 수신 및 무방어 데이터 수용을 확인했다.** 실행기 원본의 product_verdict=NOT_RUN은 당시 참조 수신기 기록이므로 수정하지 않고, IVI 증거를 본 절에서 별도 판정한다.

| 확인 항목 | 실측 결과와 해석 |
|---|---|
| ECU 관측 대 IVI candump | 6,417프레임 ID·payload·순서 모두 일치 |
| IVI CAN RX 증가량 | 7,514→13,931, 6,417프레임 증가. 오류·드롭·bus-off 증가 없음 |
| receiver 기록 | 수신 대상 ID 0x100/101/102/103/200의 3,364프레임과 정확히 일치. 다른 ID의 필터 제외를 손실로 세지 않음 |
| OFF 실행 확인 | 모든 receiver 프레임 secoc_on=false, SECURITY-PILOT-OFF-001. 대시보드 종료코드 0 |
| 실제 처리 결과 | 게시 3,355건, 파싱 거부 4건, 무시 5건 |
| replay 주입 | IVI에서 1,545건 게시 확인 |
| spoofing 주입 | IVI에서 1,539건 게시 확인 |
| fuzzy 주입 | 수신 대상 중 4건 파싱 거부·5건 무시, 게시 없음 |
| 점유율 | canbusload 설치 위치만 확인. 미수집, 목표 부하 인수 불가 |

OFF 참조 구현은 무시·거부 시 이전 snapshot 메시지를 유지한다. 따라서 해당 행에도 `EXPERIMENT ONLY: unauthenticated data published`가 남는다. 메시지 문자열로 게시 건수를 세지 않고 process_result의 2(게시), 3(거부), 0(무시)로 분류했다. 004 전달본의 UnprotectedTestReceiver 구현과 테스트를 대조했다. 이 문구 문제는 IVI 담당자에게 후속 수정 대상으로 전달할 수 있으며, 이번 처리 코드 기반 대조를 무효화하지 않는다. 게시 로그는 소프트웨어 상태 반영 근거이며 각 공격 프레임의 실제 화면 렌더링을 증명하지 않는다.

다음은 새 IVI 인증 ON 인스턴스로 Config 2 pilot을 준비하는 단계다. Config 3 최종 IDS 구성·부하 계측·본 실험 1,200회 및 IF 성능 인수는 여전히 남아 있다. 이번 한 구성의 pilot을 본 실험 완료로 집계하지 않는다.
