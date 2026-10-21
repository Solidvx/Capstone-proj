# LOAD-SPI2M-002 ECU 검토

2026-10-04 08:41:38~08:41:49 KST. SPI2MHz·qlen10·CAN500kbps, Config2 flooding 요청2600fps·3초. COMPLETE/VALID, exit0. 원본 보존 및 manifest4파일 해시 검증 완료.

공격 송신5691·관측5691, 송신오류0, rx_dropped0. 정상 원본30관측·30전달(참조 수신기). ECU전체TX7457→13330 증가5873. qdisc drop36→36 증가0, requeue64→169 증가105, 종료backlog0. CAN 오류증가0. Config2 IDS는 off이므로 detected=false는 IDS 실패 판정이 아니다.

오류 없이 완료한 이번 조건은 확인했으나, 요청2600fps와 실송신률은 다르다. 공격5691건/약3초로 전체 평균 약1897fps이며 공식50% 부하 충족은 이 값만으로 판정하지 않는다. IVI canbusload와 프레임 대조를 받은 뒤 판정한다. 이전3000fps 실행의 최대62%를 이번 실행 성적으로 재사용하지 않는다. 다음 시험·설정 변경은 보류한다.

## IVI 교차검증 완료

08H45M 자료 보존 및 대조. ECU5871 관측은 IVI5873의 prefix와 모두 일치한다. IVI RX90777→96650 증가5873은 ECU TX증가5873과 일치. receiver182프레임은 알려진ID 필터와 일치하며 BMS pending91·인증게시91, 인증거부 메시지0이다. 세 프로그램 종료0, 수집stderr0바이트, CAN 오류/drop/bus-off 증가0.

canbusload exact bitstuffing 08:41:45/46/47 표시48%/48%/40%. 최대 표시48%로 공식50% 기준은 미충족. 오류없는 유효 시행과 flooding 부하 기준 합격은 구분한다. 1초 보고의 최대 used bits242660은500000 대비48.532%이며50% 미달 판단은 정수 표시의 반올림 문제로 해소되지 않는다.

다음 후보는 동일 SPI2MHz·qlen10에서 요청2800fps·3초(LOAD-SPI2M-003). 현재 두 측정점2600fps오류0/48%,3000fps오류12/62% 사이 조건을 1회 확인하려는 것이며 선형비례나 성공을 보장하지 않는다. 같은 조건 반복·SPI 추가상향은 하지 않는다. 50%와 송신오류0을 동시에 충족하기 전 공식 flooding 시험 완료로 표시하지 않는다.

[양측 대조 집계](../analysis/load-spi2m-002-crosscheck.json)
