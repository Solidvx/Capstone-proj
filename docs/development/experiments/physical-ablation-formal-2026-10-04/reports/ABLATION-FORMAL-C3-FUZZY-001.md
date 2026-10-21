# ABLATION-FORMAL-C3-FUZZY-001 ECU 검토

ECU archive 원본을 raw/ABLATION-FORMAL-C3-FUZZY-001/ecu에 보존. manifest 및100개 raw 파일 SHA256 검증 통과. 시행1~100 누락·중복 없음,100 VALID/exit0. 붙여넣기 화면의 겹침과 달리 필요한 boot/SPI/CAN/qdisc/시각/exit 파일은 실제로 존재하고 읽기 확인했다.

공격 송신/own echo276704 일치, 송신 syscall/최종오류0, deadline 미시도3건. 참조 정상 expected/seen/delivered3000/3000/3000, 공격 BMS게시0, parse거부274. 이 수치는 참조 수신기이며 IVI 제품 판정과 구분한다.

ECU TX증가292233, qdisc dropped1801→1801(증가0), requeues증가6538. CAN 오류 통계 증가0. 기간2026-10-04 21:16:50~21:27:24 KST(메타 기록 시각).

IDS 결과: {"ids_results": {"START": 1, "CLOCK": 1, "NORMAL": 12455, "ANOMALY": 276946, "ALERT_SENT": 3001}, "sent_alert_types": {"1": 2994, "3": 5, "4": 2}, "reasons": {"UNKNOWN_ID": 276015, "PERIOD_TOO_SHORT": 254, "AUTH_ORPHAN": 261, "FRAME_RATE": 105, "FAILSAFE_RANGE": 144, "SECOC_FAILURE_BURST": 36, "BMS_RANGE": 130, "IF_ANOMALY": 1}, "detected_trials": 100, "rule_events": 276845, "if_events": 0, "process_log": ""}

fuzzy의 0x200 주입과 실제 IDS 경보를 IVI 수신 기록에 대조할 때 구분해야 한다. detected 플래그만으로 경보 출처나 유형 정확도를 확정하지 않는다. IVI 원본은 아직 미수령이며 교차검증·최종 성능 판정 대기.

## IVI 21H33M 교차검증 완료

압축 및 개별 원본 보존, 해당 실행 inventory SHA256 검증 완료. ECU TX/IVI RX 증가량292233일치. ECU관측292215프레임이 IVI CAN의 정확한 prefix이며 끝18프레임은 ECU관측 종료 이후 구간. receiver FRAME16218건이 CAN의 대상ID 필터 결과와 순서·payload완전일치. CAN오류프레임0, IVI오류·드롭·bus-off 증가0, ECU qdisc dropped증가0.

경보게시3003건 중 실제 IDS ALERT_SENT3001건은 ECU own=false 0x200 및 IVI게시와 순서·payload완전일치. fuzzy own=true 0x200154건 중152형식거부,2게시: 0410dd8488fefa46(Flooding),0369b3c5eaa5db70(Spoofing). 이2건은 IDS탐지에서 제외하고 비인증 경보입력 수락으로 분류. source는 analysis/ABLATION-FORMAL-C3-FUZZY-001/alert-attribution.json. 0x200인증비대상 계약을 실험 중 변경하지 않음.

IVI 정상인증게시6264건(전체수집구간), BMS인증orphan123, Fail-safe잘못된payload144 및 orphan138, 잘못된BMS130. 참조정상전달3000/3000은 공격창분모로 전체게시6264와 구분한다. fuzzy에 flooding의50%점유율 기준을 적용하지 않는다.

프로그램3개exit0, candump/canbusload stderr빈파일. dashboard.stderr에는 QUnifiedTimer::stopAnimationDriver: driver is not running 정확히4줄. 원본 경고발생시각 없고 화면캡처 미수집, 화면영향은 미확인. before/after는 기록저장시각이다. 실제IDS경보와 주입경보를 구분했으며 수신기게시를 실제화면표시시각으로 해석하지 않는다.
