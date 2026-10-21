# PERF-FORMAL-001 결과: 지연 수치 충족, 전체 인수 보류

03H37M archive의 CSV·JSONL·CAN·manifest·종료기록·사후통계를 별도 tmp/perf-formal-001-received에 추출했다. ECU 로그도 수령했다. 사전 IVI 통계 미수집은 원본 메모에 명시돼 있다.

## 지연 및 기록

[분석 JSON](../analysis/perf-formal-001-analysis.json): 유효 FRAME_SWAPPED1000, NOT_RENDERED0, INDETERMINATE0. 평균9.158719ms, 최대65.740385ms, p99 16.456318ms. 기록된 인증 성공 표본의 Qt신호 지연은 평균50/최대100ms 수치조건 충족. 물리픽셀 지연은 아니다.

[CAN 대조](../analysis/perf-formal-001-crosscheck.json): IVI CAN2998개(BMS1499/auth1499),149.929652초. BMS1498간격은99.630~100.537ms,평균100.085438ms,범위위반0. 앱FRAME2008행은 IVI CAN앞2008행과일치한다. 앱정상인증1000건 외 거부4건과TIMEOUT3행이 있다. timeout을독립손상프레임3개로추가계산하지않는다. 대시보드종료0은운영자기록이다.

## 양측 프레임 차이

[양측 결과](../analysis/perf-formal-001-two-node.json): ECU·IVI각2998프레임이며같은위치ID는모두일치한다. ECUauth counter0~1498연속. payload차이는아래4개다. 1기준행번호를사용한다.

| 행 | ECU 0x102 | IVI 0x102 | IVI 결과 |
|---|---|---|---|
|84|07aab03b00000029|0755607600000052|MAC_FAIL counter82|
|804|523d082600000191|523d082600000122|COUNTER_BACKWARD counter290|
|806|e0e5341b00000192|e0e5341b00000124|COUNTER_BACKWARD counter292|
|1858|4f567faa000003a0|4f567faa00000340|COUNTER_BACKWARD counter832|

나머지 2994개payload는일치한다. ECU의로컬CAN echo와IVI수신기록의차이를확인한것이지ECU의실제물리송신파형을측정한것은아니다. IVI앱과candump는동일손상값을보므로Qt CSV만의문제로설명되지않는다. 이전예비001의84행이상값과이번84행값이동일하다. 값변화일부가byte shift처럼보이나드라이버/SPI/컨트롤러/송신경로등원인은미확정이다. 배선노이즈나특정프로그램탓으로단정하지않는다.

IVI사후RXerrors12,error-warn5,error-pass5,drop0,bus-off0이다. 사전값이없어이번시험증가량은알수없다. ECU사후오류0과혼동하지않는다.

## 판정과 다음 작업

인증된1000표본만의지연수치는충족했으나 정상송신시험의4프레임불일치가있어전체공식인수PASS는보류한다. 오류행을제외하여전체정상성공률을주장하지않는다. TC-PERF-002관측주기수치는충족했지만TC-PERF-001전체유효성검토와정상인증경로문제는남는다.

다음은양측동일한드라이버·커널·CAN설정과시험시간대커널오류기록을수집해원인을좁힌다. 현재동작프로세스의유무만반복확인하지않는다. bit rate·SPI속도·DeviceTree·키를근거없이변경하지않는다. 새공식시험을반복하기전에원인분석을진행한다. IF개선은보류유지.
