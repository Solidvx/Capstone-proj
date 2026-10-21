# ABLATION-FORMAL-C3-FLOOD-001 중단 및 v7 보완

## 근거와 상태

사용자 제공 ECU 터미널 출력 기준이다. 양측 원본 archive 수령·해시 검증·교차대조는 아직 수행하지 않았다.

- config 3, rules+IF, flooding 2800 fps, baseline 2s / attack 3s / post 1s, 100회 계획.
- trial 1·2 VALID, trial 3 INVALID ERROR, runner exit 2.
- ids-process.log: `IDS stopped: [Errno 105] No buffer space available`.
- IDS 경보 송신 OSError가 최상위 종료 처리로 전파되어 프로세스가 종료되는 코드 경로 확인. ECU stopped는 실행기 cleanup으로도 발생하므로 ECU 자발 종료 증거로 사용하지 않는다.
- trial 1: own 송신/수신 6690, 정상 전달 28/30, 탐지 0.000833s, rules 6690, IF 0.
- trial 2: own 송신/수신 6962, 정상 전달 28/30, 탐지 0.031817s, rules 6962, IF 0.
- 위 탐지 지연은 참조 실행기 수치이며 IVI 경보 도달·화면 표시 지연이 아니다.

## v7 보완

security/ids/runtime.py의 0x200 송신에 MSG_DONTWAIT 적용. ENOBUFS/EAGAIN만 ALERT_TX_FAILED로 기록하고 수신·탐지 지속. 실패에도 기존 100ms 전역 간격 적용, 실패 경보 재전송·누적하지 않음. 다른 오류 및 소유 프로세스 종료는 기존대로 중단. ICD payload, 모델·학습·보정·탐지 임계와 continue-invalid 판정은 변경하지 않음.

ALERT_TX_FAILED는 탐지 결과와 구분하고 IVI 전달 성공에 포함하지 않는다. ALERT_SENT도 소켓 수락만 나타내며 양측 원본 CAN 대조로 전달을 판단해야 한다. v6/v7 실행 버전을 분리하여 보존한다.

## 검증과 후속

WSL Linux: 관련 16 passed (3.32s), 전체 security/tests 83 passed (8.52s). 모의 버퍼 부족 후 수신·탐지 지속, 후속 경보 성공, 실패 간격 제한, 비일시 오류 종료를 검증했다. 실제 Pi 설치 및 부하 환경 검증은 미실행.

기존 001 원본과 trial 3 INVALID를 그대로 보존한다. 새 실행에서 trial 4부터 97회로 남은 계획을 이어갈 수 있다. 자동으로 실패 시행을 성공할 때까지 반복하지 않는다. IVI는 새 run ID로 수집하며 기존 결과를 보존한다. 정확한 재개 명령은 보완 설치 검증과 IVI 준비 후 제공한다.

## ECU 원본 수령 및 검증

001~003 통합 archive 원본을 raw/ABLATION-FORMAL-C3-FLOOD-001-003/ecu에 보존했다. manifest와 시행별 raw SHA256 모두 일치. 전체 시행번호1~100 중복·누락 없음, 실행기 상태98 VALID/2 INVALID(3·77). IVI 대조는 대기 중이다.

이 실행 상태: {'VALID': 2, 'INVALID': 1}. IDS ALERT_TX_FAILED 0건. 참조 전달 56/60. 전달률1초과 시행 0건. 원본 수치를 덮어쓰지 않고 분석 제약과 분리한다.

## IVI 21H10M 수령 및 양측 교차검증

IVI 원본은 raw/ABLATION-FORMAL-C3-FLOOD-001-003/ivi에 보존. 전체 inventory1309파일의 크기·SHA256 검증 완료.

- ECU 관측 16284프레임은 IVI 16286프레임의 정확한 prefix. IVI 추가 끝부분 2프레임은 ECU 관측 종료 이후 구간으로 구분.
- ECU TX 및 IVI RX 증가량 모두 16286. IVI 오류/드롭/bus-off 증가0, candump 오류프레임0.
- receiver FRAME 500건은 candump의 대상ID 필터 결과와 순서·payload 완전 일치.
- IDS ALERT_SENT 64건은 IVI 0x200 64건과 순서·payload 완전 일치. IVI 경보 분류 바이트 집계 {'1': 64} (1=Fuzzy,4=Flooding). 주입 공격은 flooding이며 유형 분류와 공격 탐지를 구분한다. 화면 캡처 미수집이므로 실제 표시 시각을 주장하지 않는다.
- ECU qdisc dropped 증가 26. 소켓 재시도/IDS 경보 실패와 구분하며 실제 CAN 전송 후 손실로 동일시하지 않는다.
- 3개 IVI 프로그램 exit0, 모든 stderr0바이트. before/after-time은 저장 시각이며 정확한 프로그램 실행 시각이 아니다. 실행 명령 파일은 001 미수집, 002·003 존재.
- 유효 완료 시행 2건 모두 주입 구간 내부 1초 점유율 표본 중50%이상 존재. 이는 전체 공격 구간 평균50%나 모든1초50%를 보장하지 않는다. 세부값은 analysis/ABLATION-FORMAL-C3-FLOOD-001/load-check.json 참조.

IVI 메시지 집계: {"BMS payload pending authentication": 220, "Authenticated BMS data published": 216, "IDS event published": 64}

