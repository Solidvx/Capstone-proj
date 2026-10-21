# ABLATION-FORMAL-C3-FLOOD-002: 시간 만료와 집계 보완

## 수령 근거

사용자가 제공한 터미널 출력만 확인했다. ECU/IVI 원본 archive 수령 및 교차검증은 대기 중이다. v7 Pi 시험은 83 passed in 26.32s.

4~76회 73건 VALID, 77회 INVALID ERROR, runner exit 2. ids-process.log 출력 없음, ids.jsonl은 END로 종료. 코드상 IDS 정상 시간 만료 경로와 일치한다. 이전 errno105 재발로 판정하지 않는다. 당시 설정된 IDS lifetime은 60 + 97*(2+3+1+2)=836초였다. 실제 CLOCK 시작과 END 간격은 원본 수령 후 대조한다.

시행76 정상 expected30/seen78/delivered73, ratio2.4333. baseline start17109.930081385, attack start17116.821543143: baseline 설정2초와 달리 공격 시작까지 약6.891초. baseline 후 IDS 누적 로그 전체 읽기, 수신 dequeue 시각 사용이 적체 프레임을 이후 공격 구간에 배정할 수 있는 코드 경로를 확인했다. 실제 적체량/손실은 양측 원본 없이는 확정하지 않는다. 기존 VALID 표시는 실행기 원본 상태이며 해당 전달률의 타당성을 보장하지 않는다.

## v8 수정

- IDS --parent-pid: 현재 실제 부모 PID 검증. 실행기가 살아 있는 동안 duration에 따른 종료를 하지 않고 실행기 cleanup SIGINT에 따라 종료한다. 부모 종료·재부모화 감지 시 스스로 종료한다. 독립 CLI의 --duration 동작은 유지한다.
- IDS 증거 읽기를 실행별 증분 offset 방식으로 변경. 완결된 줄만 처리하며 부분 줄은 다음 읽기에 재처리. 조회 시작 이전 이벤트 제거, 미래 이벤트 유지. 한 번의 읽기는 진입 시 파일 크기로 한정한다.
- 공격 실행기의 CaptureSocket(transmit=True)에 Linux SO_TIMESTAMPNS_NEW 적용. 고정 realtime→monotonic 매핑으로 실제 커널 도착 시각 사용. timestamp 누락/절단/clock step은 조용히 대체하지 않는다. 수신 대기 전 시각을 idle watermark로 사용한다. 수신 전용 정상 캡처 경로는 유지한다.
- 소유 프로세스 종료 문구에 로그 파일명과 실제 exit code를 포함한다.
- v7 경보 backpressure 기록 및 continue-invalid 유지. ICD/공격 rate/학습/보정/탐지 임계 불변.

## 검증 및 잔여 제한

Linux 전체 security/tests 88 passed in 10.29s. 부모 생존 시 짧은 duration을 넘겨 지속 및 부모 소멸 종료, 대량 로그 증분/부분 줄/미래 이벤트, 적체 시 커널 도착 시각 및 공격 이전 정상 프레임 집계 제외 검증. 실제 Pi 설치와 물리 CAN 재개는 미실행. 무조건 무중단을 보장하지 않는다. 버스/시계/디스크/실제 프로세스 오류는 기록 후 중단한다.

001/002 원본·INVALID 및 수정 전 수치 그대로 보존. 과거 전달률을 임의로100%로 자르거나 덮어쓰지 않는다. IVI candump와 연계한 재분석 전 C3 성능 확정 보류. 재개 시 78~100회 23건을 새 ID/폴더에서 수집하며, 3·77회 INVALID를 성공으로 치환하지 않는다. v6/v7/v8 버전 경계와 timestamp 측정 방식 차이를 최종 분석에 표시한다.

## ECU 원본 수령 및 검증

001~003 통합 archive 원본을 raw/ABLATION-FORMAL-C3-FLOOD-001-003/ecu에 보존했다. manifest와 시행별 raw SHA256 모두 일치. 전체 시행번호1~100 중복·누락 없음, 실행기 상태98 VALID/2 INVALID(3·77). IVI 대조는 대기 중이다.

이 실행 상태: {'VALID': 73, 'INVALID': 1}. IDS ALERT_TX_FAILED 6건. 참조 전달 3616/2190. 전달률1초과 시행 62건. 원본 수치를 덮어쓰지 않고 분석 제약과 분리한다.

## IVI 21H10M 수령 및 양측 교차검증

IVI 원본은 raw/ABLATION-FORMAL-C3-FLOOD-001-003/ivi에 보존. 전체 inventory1309파일의 크기·SHA256 검증 완료.

- ECU 관측 531211프레임은 IVI 531211프레임의 정확한 prefix. IVI 추가 끝부분 0프레임은 ECU 관측 종료 이후 구간으로 구분.
- ECU TX 및 IVI RX 증가량 모두 531211. IVI 오류/드롭/bus-off 증가0, candump 오류프레임0.
- receiver FRAME 18628건은 candump의 대상ID 필터 결과와 순서·payload 완전 일치.
- IDS ALERT_SENT 2214건은 IVI 0x200 2214건과 순서·payload 완전 일치. IVI 경보 분류 바이트 집계 {'1': 2214} (1=Fuzzy,4=Flooding). 주입 공격은 flooding이며 유형 분류와 공격 탐지를 구분한다. 화면 캡처 미수집이므로 실제 표시 시각을 주장하지 않는다.
- ECU qdisc dropped 증가 999. 소켓 재시도/IDS 경보 실패와 구분하며 실제 CAN 전송 후 손실로 동일시하지 않는다.
- 3개 IVI 프로그램 exit0, 모든 stderr0바이트. before/after-time은 저장 시각이며 정확한 프로그램 실행 시각이 아니다. 실행 명령 파일은 001 미수집, 002·003 존재.
- 유효 완료 시행 73건 모두 주입 구간 내부 1초 점유율 표본 중50%이상 존재. 이는 전체 공격 구간 평균50%나 모든1초50%를 보장하지 않는다. 세부값은 analysis/ABLATION-FORMAL-C3-FLOOD-002/load-check.json 참조.

IVI 메시지 집계: {"BMS payload pending authentication": 8330, "Authenticated BMS data published": 8061, "IDS event published": 2214, "reason=AUTH_TIMEOUT channel=BMS": 76, "reason=AUTH_ORPHAN channel=BMS auth without pending original": 18}

수정 전 ECU 002 전달률1초과는 폐기·덮어쓰기 없이 계측 결함으로 표시한다. IVI 전체 인증 게시8061건을 공격 구간 정상 전달률로 대체하지 않는다. 원본의 receive dequeue 시각을 커널 시각으로 소급 복원할 수 없으므로, 정확한 창 경계 대응을 추가 검증하기 전 해당 전달률/지연을 최종 수치로 사용하지 않는다.
