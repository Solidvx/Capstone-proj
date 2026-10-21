# PERF-FORMAL-002: Qt 표시 경로 지연·BMS 주기 기준 충족

ECU 원본 9개 파일을 `../raw/PERF-FORMAL-002/ecu/`에 보존했다. [ECU 분석](../analysis/perf-formal-002-ecu.json), [원본 해시](../inventory.json)를 참조한다.

- ECU 캡처 2998프레임: BMS 0x100 및 인증 0x102 각각 1499건, DLC 모두 8.
- 인증 counter 0~1498 연속. MAC 검증이나 IVI 인증 성공 판정과 구분한다.
- ECU TX 21194→24192, 증가량 2998로 캡처 건수와 일치. TX errors/dropped/carrier/collsns는 전후 모두 0.
- 첫~마지막 캡처 간격 149.924762초. 150초 timeout 명령의 종료코드 124, 앱 stopped 메시지 확인.

현재는 ECU 관측 확인까지이며, IVI 지연 CSV·receiver·CAN 캡처와 통계가 도착해야 유효 1000표본 이상, 지연 기준, 인증 거부·누락·양측 payload 일치 여부를 종합 판정할 수 있다. 공식 성능 PASS로 아직 처리하지 않는다. 이전 PERF-FORMAL-001의 오류 증거는 그대로 보존한다.

## 05H14M 수령 후 최종 결과

위 대기는 해소됐다. [지연 분석](../analysis/perf-formal-002-analysis.json)과 [교차 대조](../analysis/perf-formal-002-crosscheck.json)를 보존했다. 원본 압축파일과 내부 10개 파일을 추가했고 inventory는 총 169개다.

| 항목 | 실측 | 판정 |
|---|---|---|
| 완료 표본 | FRAME_SWAPPED 1000 | 1000 이상 충족 |
| 미렌더·판정 불가 | 각각 0 | 기록된 표본에서 없음 |
| T1→T4 평균 | 6.473276ms | 50ms 이하 충족 |
| T1→T4 최대 | 65.029527ms | 100ms 이하 충족 |
| T1→T4 p99 | 14.154987ms | 참고값 |
| BMS 주기 | 1498간격, 99.917~100.267ms | 모두 90~110ms 이내 |
| 양측 CAN | 각각 2998프레임, ID·payload·순서 전부 일치 | 관측 구간 불일치 없음 |
| IVI 인증 | BMS 1000건 성공, 거부 0 | 계측 구간 정상 |
| IVI RX | 4516→7514, 증가 2998 | 캡처와 일치 |
| 오류·drop·bus-off | 표시 통계 전후 0 | 증가 없음 |
| IVI 종료코드 | 0 | 기록 확인 |

receiver 2000행은 CAN 앞 2000행과 정확히 일치한다. 남은 998프레임은 1000표본 수집 후 대시보드가 종료된 뒤에도 CAN 캡처를 유지한 구간이다. 전체 길이를 단순 비교한 JSON의 exact_sequence_match=false는 이 길이 차이를 나타내며 payload 불일치나 앱 수신 손실로 세지 않는다. 종료 후 499개 BMS의 앱 인증 성공까지 주장하지 않는다.

CSV run_id는 PERF-FORMAL-002, boot_id는 64fa5852-f64f-462e-81de-169379b6d000이다. 도구의 formal_verdict=NOT_ASSESSED는 자동 전체 인수 기능이 없다는 뜻이며 위 판정은 CSV와 양측 기록을 함께 검토한 결과다.

**판정: 이번 실행에서 TC-PERF-001의 Qt frameSwapped 기준 소프트웨어 표시 경로 지연 및 TC-PERF-002 관측 주기 조건 충족.** T4는 물리 픽셀 표시/HDMI scanout 실측이 아니며 그 범위는 인수했다고 주장하지 않는다. 이전 001의 실패·보류 기록은 소급 수정하지 않는다. SPI 변경과 재부팅 중 무엇이 이상 해소 원인인지는 여전히 분리 확정하지 않았다. 실행 명령 별도 파일은 전달본에 없고 1000표본 및 설정은 CSV·로그와 담당자 보고로 확인했다.
