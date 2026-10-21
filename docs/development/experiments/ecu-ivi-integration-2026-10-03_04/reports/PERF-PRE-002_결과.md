# PERF-PRE-002 예비 계측 결과

03H14M archive를 안전한 별도 tmp/perf-pre-002-received 경로에 추출했다. CSV·receiver·candump·manifest 4개이며 ECU 캡처는 포함돼 있지 않다. manifest는 검증한004와 일치한다. 담당자는 대시보드 종료코드0을 보고했다.

- [CSV 분석](../analysis/perf-pre-002-analysis.json): FRAME_SWAPPED300, NOT_RENDERED0, INDETERMINATE0. 미확정표본·중복stage/frame ID·시각역전 없음. 실제run/boot ID 기록.
- T1→T4 Qt 신호 기준 평균9.386113ms, 최대86.162014ms, p99 18.448838ms. 예비 표본의 수치는 평균50/최대100ms 이내. 공식1000표본 요구와 물리 픽셀 표시 증거를 대신하지 않음.
- [CAN 교차분석](../analysis/perf-pre-002-crosscheck.json): IVI receiver600행(BMS300·인증300)은 CAN 앞600행과 완전 일치. 인증실패·SOC 디코딩 불일치 없음.
- CAN은844행(BMS422·인증422), counter0~421 연속. 관측 범위42.140682초. BMS421간격 최소99.722ms/평균100.092686ms/최대100.498ms로 전부90~110ms.
- IVI 앱 종료 후 CAN 꼬리244행이 남아 있다. 이 차이를 앱 수신 손실로 계산하지 않는다.

## 남은 수집 범위 확인

ECU 사용자 출력은60초 timeout 종료코드124, 정상stop, 최종TX13680이다. 직전보고TX12480과 차이는1200이지만 이번can-before 원본은 아직 못 받았다. IVI CAN파일은 시작counter0에서421까지42.14초뿐이므로 “ECU 송신 종료 후 캡처 종료”라는 운영자 설명과 전체60초 포함 여부를 대조해야 한다. 파일이 짧다는 사실만으로CAN 손실을 단정하지 않는다.

ECU tmp/perf-pre-002-ecu 전체 폴더(특히candump·can-before·can-after)를 받아 동일payload/counter 시퀀스를 대조한다. 서로 다른 노드의시계를 직접 빼지 않는다. 001의MAC_FAIL은002의관측범위에서 재발하지 않았지만 원인이 규명되거나 수정된 것은 아니다. 기존001FAIL 근거를 보존한다.

현재 판단: 300표본 정상 인증·계측 성공, 관측구간 수치 목표 이내. ECU원본 대조와캡처범위 확인 대기. 아직 공식1000표본시험 완료로 표시하지 않는다.

## ECU 원본 수령 후 양측 대조 완료

ECU tmp/perf-pre-002-ecu의7파일을 수령했다. HEAD9568d907d1c57271a19eb986b23638b5eec70c1a, git-status 비어있음, 종료코드124, 정상stop기록을 확인했다. 사전TX12480→사후13680으로 정확히1200증가, 보고된오류·drop·bus-off0이다.

[양측 대조 JSON](../analysis/perf-pre-002-two-node-analysis.json): ECU CAN1200프레임,59.954273초,인증counter0~599연속. IVI844프레임은 ECU앞844프레임과 ID·payload·순서가 전부같다. IVI앱600프레임 역시 해당 공통구간 안에 있어300인증·300계측의 수집대응이 확인됐다. 서로다른노드시각을빼서전송지연을계산하지않았다.

IVI파일에는 ECU끝356프레임이 없다. 끝부분이 없는 원인은 조기캡처종료·파일잘림·수신중단 중 어느것인지 자료만으로확정하지못한다. 이를무조건버스손실로계산하거나전체60초무손실로표기하지않는다. 예비300표본구간은양측일치확인완료이며추가예비재시험은요구하지않는다. 공식시험은 별도run에서1000표본이상, 양측캡처를ECU종료후까지보존하고 IVI캡처종료코드·전후통계도수집한다. 001의MAC_FAIL원인은계속미확정으로남긴다.
