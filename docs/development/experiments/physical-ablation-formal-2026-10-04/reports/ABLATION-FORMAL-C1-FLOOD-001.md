# ABLATION-FORMAL-C1-FLOOD-001 ECU 검토

공식 시행 시도 기록. 2026-10-04 09:08:12~09:08:59 KST. Config1·flooding·요청2800fps·공격3초·baseline2초·post1초·목표100회. ECU SPI2MHz·CAN500kbps·qlen10. 전체ERROR/exit2, 7회차INVALID에서중단. manifest10파일 해시검증완료.

| 시행 | 실행기판정 | 공격송신/관측 | 송신오류 | 정상관측/전달 |
|---|---|---|---:|---|
|1|VALID|7075/7075|0|30/30|
|2|VALID|6962/6962|0|30/30|
|3|VALID|7144/7144|0|30/30|
|4|VALID|7119/7119|0|30/30|
|5|VALID|7035/7035|0|30/30|
|6|VALID|7101/7101|0|30/30|
|7|INVALID/TX_ERRORS|7135/7135|1|30/30|

7회차 오류는 errno105 ENOBUFS, monotonic2363.056326690. qdisc drop36→37 증가1, requeue237→341 증가104, 종료backlog0. 8~100회는 미실행.

앞6회는 실행기VALID이며 IVI시행별부하·payload대조·제품판정 대기다. 공식인정횟수는미확정이다. 기존pilot부하60%를이실행에재사용하지않는다. 마지막무효시행도보존하며유효표본만선택한것처럼전체시도수를숨기지않는다. 후속실행은새ID로분리하고seed·시행번호중복을확인해야하며아직재실행하지않았다.

[ECU 집계](../analysis/ABLATION-FORMAL-C1-FLOOD-001/ecu-summary.json)

## IVI 대조 및 공식 표본 인정

09H15M 수령자료 대조: ECU와 IVI 전체50024프레임의 순서·ID·payload가 일치. IVI RX103870→153894 증가50024는 ECU TX증가와 일치. 알려진ID receiver453건이 CAN필터와 일치하며 SecOC OFF 게시453건이다. 세프로그램 종료0, IVI CAN오류/drop/bus-off 증가0.

ECU own주입 프레임을 일치하는 IVI candump 인덱스에 연결하여 실제 주입의 epoch구간을 정했다. 해당 구간 내부의 canbusload 보고값을 시행별로 대조했다(호스트간 monotonic값 직접비교 안 함). 1~6회 부하조건50% 이상과송신오류0을확인하여 유효공식표본6회로 인정한다. 공격성공률/차단율은 flooding의 null 정의를 유지하고 VALID를 방어성공으로 해석하지 않는다.

|시행|내부 부하보고(%)|판정|
|---|---|---|
|1|60,60|유효|
|2|59,60|유효|
|3|61,60|유효|
|4|60,60|유효|
|5|60,60|유효|
|6|60,60|유효|
|7|61,60|ENOBUFS1로무효유지|

Config1 flooding 진행은 유효6/100, 무효1, 유효94회가더필요하다. 전체목표대비6/1200이며 다른구성/공격은미실행이다. 후속실행에서시행번호·seed중복과무효재시도를별도기록해야하며 아직재시작하지않았다. 현재단일오류를무시하는판정변경은하지않는다.

[양측 및 시행별 부하 대조](../analysis/ABLATION-FORMAL-C1-FLOOD-001/crosscheck.json)
