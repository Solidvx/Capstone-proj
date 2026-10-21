# LOAD-SPI2M-003 ECU 검토

2026-10-04 08:49:50~08:50:01 KST. SPI2MHz·qlen10·CAN500kbps. Config2 flooding 요청2800fps·3초. COMPLETE/VALID, exit0. 원본 보존·manifest4파일 SHA256 검증 완료.

공격 송신7038·관측7038, 송신오류0, rx_dropped0. 참조 정상관측30·전달30. ECU전체TX13330→20550 증가7220. qdisc drop36→36 증가0, requeue169→237 증가68, 종료backlog0. CAN 오류증가0. Config2 IDS off이므로 detected=false는 탐지기 실패가 아니다.

IVI 자료 미수령으로 전체 CAN payload 대조와 점유율50% 이상 판정은 대기. 이전 실행의62% 또는48%를 재사용하지 않는다. 이번 실행이 유효하다는 것과 공식 flooding 부하 조건 충족은 별도 판정한다. 추가 실행·설정 변경은 보류.

## IVI 대조 및 이번 부하 조건 판정

08H51M 자료 대조 완료. ECU7218관측은 IVI7220의 prefix와 모두 일치. IVI RX96650→103870 증가7220은 ECU TX증가7220과 일치한다. receiver FRAME182건은 알려진ID 필터와 일치, BMS pending91·인증게시91·인증거부0. 세프로그램 종료코드0, 두수집stderr0, CAN errors/drop/bus-off 증가0.

canbusload exact bitstuffing 08:49:57과08:49:58에 각각60% 표시(301592/302223 bits). 따라서 이번 Config2 1회에서는 송신오류0·큐drop증가0과50% 이상 부하를 동시에 관측했다. TC-SEC-005-d의50% 수치조건 충족 근거로 보존한다. 물리본실험1200회 완료나 모든구성에서 동일률 보장을 뜻하지 않는다.

이번에 확인한 조건은 ECU SPI2MHz, IVI SPI1MHz, CAN500kbps, ECU qlen10, flooding 요청2800fps·3초다. 이전SPI1MHz 또는2600/3000fps 결과를 합쳐 성공으로 판정하지 않는다. 큐확대는복구됐고2800fps 설정에서 유효 부하발생을 확인한 것이다.

다음은 이조건을 기준으로 공식실험 실행표와 구성별수집절차를 확정하는 단계다. Config3 정상구간IF_ANOMALY1건과공격창IF단독탐지미입증은별도 잔여항목이다. 공식시행마다실송신·오류·부하조건을 확인하며 이번1회로모든반복을통과처리하지않는다.

[교차검증 JSON](../analysis/load-spi2m-003-crosscheck.json)
