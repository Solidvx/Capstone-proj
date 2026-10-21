
## ECU 원본 수령 및 검증

001~003 통합 archive 원본을 raw/ABLATION-FORMAL-C3-FLOOD-001-003/ecu에 보존했다. manifest와 시행별 raw SHA256 모두 일치. 전체 시행번호1~100 중복·누락 없음, 실행기 상태98 VALID/2 INVALID(3·77). IVI 대조는 대기 중이다.

이 실행 상태: {'VALID': 23}. IDS ALERT_TX_FAILED 6건. 참조 전달 446/690. 전달률1초과 시행 0건. 원본 수치를 덮어쓰지 않고 분석 제약과 분리한다.

78~100회23건 VALID·exit0. 송신/own echo159682일치, 최종 공격송신 오류0. syscall367회 오류는366개 프레임의 재시도와 관련하며 오류횟수와 프레임수를 구분한다. IDS 경보 송신 errno105 6건에도 프로세스 지속. ALERT_SENT684는 소켓 수락이며 IVI 도달 미확인. qdisc dropped1140→1801(+661), TX증가163180. 참조 정상 seen616/delivered446/expected690: 실제 수신 손실·인증 가용성·관측 경계 영향은 IVI 대조 전 확정하지 않는다. 전달률1초과 없음.

## IVI 21H10M 수령 및 양측 교차검증

IVI 원본은 raw/ABLATION-FORMAL-C3-FLOOD-001-003/ivi에 보존. 전체 inventory1309파일의 크기·SHA256 검증 완료.

- ECU 관측 163160프레임은 IVI 163180프레임의 정확한 prefix. IVI 추가 끝부분 20프레임은 ECU 관측 종료 이후 구간으로 구분.
- ECU TX 및 IVI RX 증가량 모두 163180. IVI 오류/드롭/bus-off 증가0, candump 오류프레임0.
- receiver FRAME 3498건은 candump의 대상ID 필터 결과와 순서·payload 완전 일치.
- IDS ALERT_SENT 684건은 IVI 0x200 684건과 순서·payload 완전 일치. IVI 경보 분류 바이트 집계 {'1': 683, '4': 1} (1=Fuzzy,4=Flooding). 주입 공격은 flooding이며 유형 분류와 공격 탐지를 구분한다. 화면 캡처 미수집이므로 실제 표시 시각을 주장하지 않는다.
- ECU qdisc dropped 증가 661. 소켓 재시도/IDS 경보 실패와 구분하며 실제 CAN 전송 후 손실로 동일시하지 않는다.
- 3개 IVI 프로그램 exit0, 모든 stderr0바이트. before/after-time은 저장 시각이며 정확한 프로그램 실행 시각이 아니다. 실행 명령 파일은 001 미수집, 002·003 존재.
- 유효 완료 시행 23건 모두 주입 구간 내부 1초 점유율 표본 중50%이상 존재. 이는 전체 공격 구간 평균50%나 모든1초50%를 보장하지 않는다. 세부값은 analysis/ABLATION-FORMAL-C3-FLOOD-003/load-check.json 참조.

IVI 메시지 집계: {"BMS payload pending authentication": 1477, "Authenticated BMS data published": 1307, "IDS event published": 684, "reason=AUTH_TIMEOUT channel=BMS": 72, "reason=AUTH_ORPHAN channel=BMS auth without pending original": 22, "WARNING: reason=AUTH_TIMEOUT channel=BMS": 5}

v8 참조 정상 전달446/690은 IVI 전체 게시1307과 분모/구간이 다르다. CAN 관측 일치는 인증 서비스 가용성 보장이 아니다. IVI AUTH_TIMEOUT72 및 WARNING AUTH_TIMEOUT5, AUTH_ORPHAN22가 남으며 메시지 수를 독립된 유실 패킷 수로 합산하지 않는다. v7/v8 경보송신실패6건은 성공전송684건에 포함되지 않는다.
