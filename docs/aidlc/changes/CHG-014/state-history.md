# CHG-014 과거 상태 이력

감사 보완 전 누적 상태 원문. 최신 상태는 aidlc-state.md만 사용한다. 이하 최신·미완료 표기는 당시 시점이다.

## 최신 공식실행 상태

ABLATION-FORMAL-C1-FLOOD-001 ECU수령: 시도7·실행기VALID6·INVALID1(ENOBUFS1). IVI50024프레임일치·각시행부하50%이상확인. 공식유효6/100 인정,무효1보존. 후속94유효시행필요. 아래 미실행 표기는 이전 이력.

# CHG-014 상태

## 최신 상태: SPI2MHz 2800fps ECU 검증

LOAD-SPI2M-003 COMPLETE/VALID/exit0, 공격7038송신·관측, 오류0·정상30/30·qdisc drop증가0. IVI7220·양측통계일치 및 부하60% 확인. 이번Config2에서50% 이상·송신오류0 동시달성. 부하조정단계 완료, 공식실험 실행준비로 전환. 전체1200회·IF잔여검증은미완료. 아래002 기록은 이전 이력.

LOAD-SPI2M-002 COMPLETE/VALID, 송신5691·오류0·정상30/30·qdisc drop증가0 확인. IVI5873 및 양측통계일치·인증91/거부0. 최대점유율48%로50% 미달. 다음요청2800fps 비교 후보 미실행. 아래001 및 후보 문구는 이전 이력.

LOAD-SPI2M-001 ECU검증 완료. 7299송신/관측, ENOBUFS12, qdisc drop36으로 INVALID 유지. IVI대조7457프레임·통계일치, 부하최대62% 확인. 50% 수치조건 관측이나 송신오류로INVALID 유지. 다음2600fps 비교 후보는 미실행. 아래 큐비교는 이전 이력.

LOAD-QUEUE-001 qlen100에서도 ENOBUFS1796으로 INVALID. IVI 대조 완료:5609 수신·양측 통계 일치, 최대45% 미달. 큐 확대만으로 미해결, qlen10 복구 확인 및 SPI/드라이버 검토 대기. 같은 조건 반복 보류. 아래는 이전 검증 이력.

PHYSICAL-PILOT-IF-002 양측 대조 완료. Config3 4종 VALID 및 주기 오탐 재발 없음. ECU11,790 prefix·IVI11,808·receiver6,391 일치. spoofing 정상2건은 인증 짝 교란으로 MAC 거부. IDS121 게시, CAN 오류0. 대시보드 종료130은 시험 종료 후 Ctrl+C 수동 종료로 사용자 확인. IF 정상구간 이상1건·공식부하24%로 50% 미달은 잔여 항목. 아래 적용 대기 내용은 이전 이력.

v4 코드 수정·패키지 생성·로컬 검증 완료: 전체 Python 66 passed(8.69s). 커널 수신 시각과 idle 타이머 순서를 교정했다. RPi 적용 및 Config 3 재검증 대기이며 물리 해결 완료로 판정하지 않는다. 상세는 evidence.md의 IDS 수신 시각 보완 v4 참조. 아래 기록은 이전 이력이다.

PHYSICAL-PILOT-IF-001 IVI 대조 완료: 중단 대상 counter fe→ff 간격 IVI100.017ms, ECU참조99.930ms, IDS45.851ms. 사용자 공간 수신 시각 왜곡 근거 확인. 다음은 IDS 수신 timestamp 보완. ECU8,926 prefix 일치·IVI8,938·receiver3,521 필터 일치, IDS 게시92건. spoofing 미실행 상태 유지.

PHYSICAL-PILOT-IF-001 ECU 수령: rules+if 모드 앞3종 VALID·경보 관측, spoofing baseline PERIOD_TOO_SHORT(0x102)로 미주입 중단. 동일 프레임 간격이 참조99.930ms/IDS45.851ms로 달라 사용자 공간 수신 시각 지연 의심. IF 이상 경보가 중단 원인은 아님. IVI 대조·수신 시각 보완 검토 대기. [분석](../../../development/experiments/ecu-ivi-integration-2026-10-03_04/reports/PHYSICAL-PILOT-IF-001_결과.md).

LOAD-DIAG-V3-001 양측 대조 완료: ECU prefix5,566 일치, IVI 끝 정상 한 쌍 포함5,568은 양측 통계와 일치. 최대 점유율46% 미달, ENOBUFS1,828 지속. IVI AUTH_TIMEOUT13·AUTH_ORPHAN2. 다음은 송신 경로 병목 근거 검토이며 같은 조건 반복은 보류. 정상 IF 평가 통과는 유지.

LOAD-DIAG-V3-001 ECU 수령: TX_ERRORS로 INVALID, 오류 1,828건 모두 errno 105(ENOBUFS), 성공/echo 5,425 일치. v3 오류 판정·원인 기록 실장비 확인. IVI 대조와 최종 송신 경로 병목 진단은 대기. [진단 결과](../../../development/experiments/ecu-ivi-integration-2026-10-03_04/reports/LOAD-DIAG-V3-001_결과.md).

진단 v3 수정·로컬 검증 완료: TX_ERRORS 무효 판정 및 errno 보존, 전체 Python 59 passed(8.79s). v2 위에 적용하는 3파일 패키지 생성·해시 검증. 물리 송신 실패 원인은 아직 미확정이며 장비에서 동일 조건 1회 진단을 대기한다. [적용 및 후속 절차](../../../development/experiments/ecu-ivi-integration-2026-10-03_04/reports/LOAD_진단_v3.md).

LOAD-CHECK-V2-001 ECU 교차검증: 관측 5,533건 IVI prefix 일치, IVI 끝 정상 한 쌍 포함 5,535건은 양측 CAN 통계 증가와 일치. 주입 send OSError 1,871건이 있으나 판정기의 INVALID 조건 누락으로 원본 VALID. 검토 판정 NOT_ACCEPTED, 부하 45% 및 송신 실패 원인 미해결. AUTH_TIMEOUT은 타이머 로그 포함 12건으로 정정. errno 미기록으로 큐·SPI 원인 확정 불가. 기존 물리 IF 정상 오탐 PASS는 유지한다.

LOAD-CHECK-V2-001 IVI 자료 확인: 최대 부하 표시 45%로 공식 50% 조건 미충족. CAN 5,535·필터 receiver 142 일치, 인증 게시62·AUTH_ORPHAN4·AUTH_TIMEOUT2, CAN 오류 증가 없음. ECU 자료 수령 전 원인·유효성은 대기. [부하 결과](../../../development/experiments/ecu-ivi-integration-2026-10-03_04/reports/LOAD-CHECK-V2-001_결과.md).

물리 정상 IF 평가 수령·검증 완료: NORMAL-IF-20261004-064946의 규칙 0/298, 규칙+IF 1/298(0.33557%)로 이번 constant 운전의 정상 오탐 수치 조건 충족. 독립 세 캡처 해시·창 집계 확인. 실시간 IF 부하·공격 탐지 및 flooding 50% 인수는 대기. [물리 정상 결과](../../../development/experiments/ecu-ivi-integration-2026-10-03_04/reports/NORMAL-IF-20261004-064946_결과.md). 아래 물리 IF 대기 문구는 과거 이력이다.

ECU RPi에서도 Python 59·CTest 17 통과(사용자 출력). VCAN-READINESS-V2-001 두 구성 COMPLETE·8 VALID·manifest 해시 16개 검증, C3 규칙 4종 경보 관측 확인. IF·물리 부하 인수는 아직 남아 있다. [v2 vcan 결과](../../../development/experiments/ecu-ivi-integration-2026-10-03_04/reports/VCAN-READINESS-V2-001_결과.md).

사용자 요청으로 IF 개선 보류를 해제했다. 송신 select 대기·스케줄 처리시간 보완, IF 학습 윈도우 정합·독립 정상 보정과 평가 분리를 구현했다. WSL 전체 Python 59 passed. 독립 합성 평가 4/298·0/298·1/298창 오탐. 로컬 WSL vcan 미지원으로 실 SocketCAN 송신률 및 물리 IF 인수는 대기다. 이전의 IF 보류·미개선 문구는 과거 이력이다. [수정·검증·ECU 인계 절차](../../../development/experiments/ecu-ivi-integration-2026-10-03_04/reports/PILOT_보완_v2.md).

## 이전 검증과 수령 이력

- 소프트웨어 구현·호스트 검증 완료: 정상 캡처·IF 평가, 실시간 시험 하네스, MAC 변조 fixture, Fail-safe 프로파일, ADC 원시 측정, 증거 집계. Python 55/55, ECU 17/17.
- RPi vcan pilot 실행 완료: VCAN-PILOT-001 세 구성 12시행 VALID, 세 실행 COMPLETE, 결과 해시 검증. Config 3은 규칙 전용. Config 2 replay의 동일 payload/정상 인증 결합 수용 1건은 기존 넓은 성공 정의에 따라 유지하며 과거 counter 재수용과 구분한다. 실행기 수정 없이 물리 pilot 준비 가능. 물리 pilot과 IVI 제품 인수는 미완료. [상세](../../../development/experiments/ecu-ivi-integration-2026-10-03_04/reports/VCAN-PILOT-001_결과.md).
- 발견: 독립 합성 IF smoke 오탐 16/108창(14.81%)으로 5% 기준 미달. 규칙은 0/108. 임계 미조정, 실측 평가 대기.
- 실제 물리 시험: 정상 인증 및 ADC 노브 전이·이벤트 인증 확인. PERF-FORMAL-002는 1000표본 Qt frameSwapped 지연 평균 6.473276ms·최대 65.029527ms, 양측 2998프레임 일치로 소프트웨어 표시 경로 지연·관측 주기 조건 충족. 물리 픽셀 지연은 미측정. 노브 화면은 사용자 관측이며 파일 미첨부. 물리 Ablation pilot·본 실험은 미완료. [시험 증거](../../../development/experiments/ecu-ivi-integration-2026-10-03_04/README.md).
- IVI 시험 전용 OFF·로그 구현: 사용자 결정에 따라 IVI 담당자 소관, 인계 명세 작성 완료.
- 기존 EXQ-11: [draft PR #24](https://github.com/Solidvx/Capstone-proj/pull/24), base develop. 자동 병합하지 않았다.
- 물리 Config 1 pilot ECU 증거 수령: PHYSICAL-PILOT-001의 4종 각 1시행 VALID, manifest COMPLETE, 종료코드 0, 결과 해시 7개 일치. 송신 오류·관측 드롭 0. 실제 송신률 약 509~515fps로 요청 1000fps와 구분한다. IVI 제품 관측·부하 기록 대조 전이며 Config 2·3 물리 pilot과 본 실험은 미실행. [결과](../../../development/experiments/ecu-ivi-integration-2026-10-03_04/reports/PHYSICAL-PILOT-001-C1_결과.md).
- 후속 IVI 자료 대조 완료: Config 1 양측 CAN 6,417프레임 및 필터 대상 receiver 3,364건 일치. OFF replay 1,545건·spoofing 1,539건 게시 확인. 오류 증가 없음. 이전 항목의 IVI 대기는 해소됐으며 부하 미수집과 Config 2·3 pilot/본 실험 대기는 유지한다. OFF 메시지는 무시·거부 시 이전 게시 문구를 유지하므로 처리 코드로 판정했다.
- [요구](spec.md) · [검증](evidence.md) · [실행 절차](../../../development/playbooks/live-security-validation.md)
- Config 2 IVI 후속 대조 완료: ECU 관측 7,483건은 IVI 앞부분과 일치, IVI 끝 정상 한 쌍 포함 CAN 7,485·receiver 4,427. counter 거부 1,177·spoofing MAC_FAIL 1, 정상 인증 게시 271. flooding 부하 최대 표시 13%로 TC-SEC-005-d 50% 기준 미충족. Config 2 수신·인증 pilot 확인 완료와 공식 부하 인수 미완료를 구분한다. 이후 문장의 IVI 대기는 이 후속 결과로 해소됨.
- Config 2 물리 pilot ECU 수령 완료: 4시행 VALID, COMPLETE, exit 0, 결과 해시 7개 검증. CAN TX 증가 7,485, 오류 증가 없음. replay 게시 1건은 동일 payload와 새 정상 인증 결합으로 확인했으며 과거 counter 수용과 구분한다. IVI 제품 결과·점유율 대조 대기. Config 3 및 본 실험 미완료.

공식 실험 보존 전용 디렉토리 physical-ablation-formal-2026-10-04 준비 완료. 아직 공식시행 및 결과수령 없음. pilot과 합산하지 않음.

## 송신 재시도 v5 보완

ENOBUFS/EAGAIN 유한 재시도와 새 run ID에서 시행 번호 재개를 구현했다. 최종 미완료는 INVALID로 중단하며 syscall 실패는 모두 보존한다. 기존 7번 INVALID는 유지한다. WSL Python 74개 통과, Pi 적용·물리 검증 미실행. 상세 방법 변경과 한계: [TX-RETRY-V5](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/TX-RETRY-V5.md).

## v6 계획 시행 계속 수집

사용자 확정: 유효100회 보충이 아닌 계획100회 기록 수집. --continue-invalid로 판정된 INVALID를 보존 후 다음 번호 진행, 실행 불가능 예외는 중단. 종료 경계 미호출의 TX_ERRORS 오집계 수정. WSL 77개 통과, Pi 미적용. [상세 및 002 터미널 근거](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/CONTINUE-INVALID-V6.md).

## 공식 C1 flooding 002·003 ECU 수령

계획 번호 1~100 기록 수집 완료, 중복 포함 101시도·실행기 VALID99/INVALID2. 003은 79회 VALID, 복구17건, qdisc dropped +21. 양측 무손실·부하 판정은 IVI 대조 전 보류. [원본 검토](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/ABLATION-FORMAL-C1-FLOOD-002-003.md).

## 002·003 IVI 대조 완료

16H45M 원본 보존. 공통 CAN ID/payload/순서 일치, 003 TX/RX 증가량 562968 일치. 002 15시도·003 79시도 모두 내부 부하50% 보고 존재. 002 dashboard127 실제 종료값 미확인, 전후시각은 실행시각 아님. C1 flooding 계획 번호 수집 완료; INVALID와 중복 및 버전별 구분 유지. [교차검증 보고](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/ABLATION-FORMAL-C1-FLOOD-002-003.md).

## C1 fuzzy 공식 ECU 수령

100회 VALID, exit0, 공격 송신/own echo277993 일치, syscall 오류0, qdisc drop 증가0. 정상 기대 대비1건 차이는 미확정, IVI 대조 대기. [보고서](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/ABLATION-FORMAL-C1-FUZZY-001.md).

## C1 fuzzy IVI 대조 완료

17H13M 원본 보존, 공통284182프레임 일치·TX/RX증가284184일치, receiver6884필터일치. 오류 증가0·종료0. OFF published 문구는 처리결과0에도 있어 실제게시로 단독집계하지 않는다. [검토](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/ABLATION-FORMAL-C1-FUZZY-001.md).

## C1 replay ECU 수령

100회 VALID·exit0, 공격 송신/own echo278319, syscall오류0. 원본 해시 검증·보존 완료, IVI 제품 판정 대기. [보고서](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/ABLATION-FORMAL-C1-REPLAY-001.md).

## C1 replay IVI 교차검증 완료

17H38M 원본 보존, TX/RX284518 및 공통구간순서 일치. replay278319건 모두 IVI process_result2·OFF게시. 오류 증가0·종료0. 실제 화면 갱신과 구분. [보고서](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/ABLATION-FORMAL-C1-REPLAY-001.md).

## C1 spoofing ECU 수령

100회 VALID·exit0, 송신/own echo278232 일치, 정상3000/3000. 원본 해시 검증 및 보존 완료, IVI 대조 대기. [보고서](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/ABLATION-FORMAL-C1-SPOOF-001.md).

## C1 spoofing IVI 수신 오류 기록

18H08M 대조 완료. IVI RX errors+1·오류프레임1·송신대비일반1건부족, 시행60 공격 구간 순서 차이. receiver와 IVI 일반캡처는 일치. 실행기100 VALID 유지 및 외부 손실관측 별도 기록. 자동보충 없음. [보고서](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/ABLATION-FORMAL-C1-SPOOF-001.md).

## C2 flooding ECU 수령

100회 VALID·exit0, 공격704701 송신/own echo 일치. syscall51 복구, qdisc +83, 정상 참조전달2967/기대3000. 원본 해시 검증·보존 완료. IVI 제품 및50%부하 대조 대기. [보고서](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/ABLATION-FORMAL-C2-FLOOD-001.md).

## C2 flooding IVI 대조 완료

18H30M 원본 보존, TX/RX717287 일치, 공통순서 일치. 100회 내부부하50% 보고 존재. timeout4·orphan6은 인증 가용성 저하로 기록. IVI CAN오류 증가0. [보고서](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/ABLATION-FORMAL-C2-FLOOD-001.md).

## C2 fuzzy ECU 원본 검토

100회 VALID, 공격277757 송신/own echo일치, 정상2999/기대3000. 오류0, qdisc증가0. 다른 공격명 표시 원인은 IVI 대조 전 미확정. [보고서](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/ABLATION-FORMAL-C2-FUZZY-001.md).

## C2 fuzzy 경보 출처 대조 완료

18H53M 원본보존, TX/RX290125일치. 시행10·42 own0x200 payload가IVI경보2건과일치. 154개중152거부·2게시, 실제IDS탐지로 제외하고 경보입력수락으로 기록. IVI정상BMS6184인증게시, CAN오류증가0. [보고서](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/ABLATION-FORMAL-C2-FUZZY-001.md).

## C2 replay ECU 검토

100회 VALID·exit0, 송신/own echo287914일치, 오류0. 참조 정상전달2880·attack_published116, 출처/정상인증결합 여부와 IVI 대조 전 제품차단율 확정하지 않음. [보고서](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/ABLATION-FORMAL-C2-REPLAY-001.md).

## C2 replay IVI 및116건 출처 확인

19H24M 원본보존. TX/RX300318일치, 게시116건은 모두 동일payload재전송+정상새인증 결합이며 IVI에도 게시됨. 과거인증쌍 수락으로 집계하지 않음. Qt경고9회 사후메모·화면영향미확인 보존. [보고서](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/ABLATION-FORMAL-C2-REPLAY-001.md).

## C2 spoofing ECU 검토

원본해시검증·보존완료. 100회VALID, 송신오류0·qdisc증가0, 참조공격게시0·정상전달2759/3000. IVI 제품대조대기. [보고서](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/ABLATION-FORMAL-C2-SPOOF-001.md).

## C2 spoofing IVI 대조 완료

20H15M 원본 보존. TX/RX289691일치, 공통게시5952 정상원본/인증, 끝2게시 출처대조범위밖. 위조게시 증거없음. MAC_FAIL238 위조pending+정상인증 확인, timeout1. Qt경고메모의 미확인 한계 보존. C2 네 공격 대조완료. [보고서](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/ABLATION-FORMAL-C2-SPOOF-001.md).

## C3 flooding IDS 송신 버퍼 부족 보완 v7

001 시행1·2 VALID, 시행3 INVALID ERROR, IDS errno105 종료(사용자 출력). 일시 송신 오류를 ALERT_TX_FAILED로 보존하고 탐지 지속, 실패 포함100ms 간격, 비일시 오류 종료. ICD 및 탐지 임계 불변. Linux 관련16개·전체83개 통과. Pi 적용·물리 검증 및 양측 원본 대조 대기. [보고서](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/ABLATION-FORMAL-C3-FLOOD-001.md).

## C3 장기 실행 및 시각 집계 v8

002는 시행4~76 VALID·77 INVALID ERROR, IDS END(사용자 출력). 836초 lifetime 경로와 누적 로그 전체 스캔/수신 dequeue 시각 집계 결함을 보완. 부모 수명 연동·증분 로그 읽기·커널 수신 시각을 적용, Linux88 passed10.29s. Pi 미적용, 과거 C3 전달률 재분석 필요. [근거 및 제한](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/ABLATION-FORMAL-C3-FLOOD-002.md).

## C3 flooding ECU 001~003 수령 완료

archive 및 manifest/raw 해시 일치, inventory1263파일. 100회 기록98 VALID/2 INVALID. 003 v8 23회완료 exit0, 경보송신실패6건 기록 후 지속. 정상전달446/690 참조값이며 IVI 교차검증 필요. 002 전달률 이상 재분석 보류. [003 보고서](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/ABLATION-FORMAL-C3-FLOOD-003.md).

## C3 flooding IVI 001~003 검토

21H10M수령, 전체inventory1309파일 해시검증. TX/RX16286·531211·163180각일치, receiver필터완전일치, IVI오류증가0. 경보64·2214·684모두도달. 003송신실패6에도완료; 정상인증가용성 저하 관측. 002잘못된 전달률은 최종 성능수치로 사용금지, 버전별 구분. 화면미수집·명령001미수집·전후저장시각 한계 기록. [교차검토](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/ABLATION-FORMAL-C3-FLOOD-003.md).

## C3 fuzzy ECU 검토

원본/manifest/raw해시검증 완료.100 VALID·exit0, 참조정상전달3000/3000, TX오류0/qdisc증가0. IVI제품 대조대기. [보고서](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/ABLATION-FORMAL-C3-FUZZY-001.md).

## C3 fuzzy IVI검토 완료

21H33M원본보존·해시검증. TX/RX292233일치, IDS송신3001모두IVI게시. fuzzy0x200154중152거부/2게시이며 탐지에서제외. CAN오류증가0, Qt경고4화면영향미확인. [보고서](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/ABLATION-FORMAL-C3-FUZZY-001.md).

## C3 replay ECU 수령

해시검증·보존완료,100 VALID·exit0. 참조own게시137 모두정상auth결합/동일payload. IVI제품대조대기. [보고서](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/ABLATION-FORMAL-C3-REPLAY-001.md).

## C3 replay IVI검토 완료

21H54M보존·해시검증, TX/RX302236일치, 경보3041모두도달. 재전송pending137은정상새auth결합·IVI게시대응확인. Qt경고25, 화면영향미확인. [보고서](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/ABLATION-FORMAL-C3-REPLAY-001.md).

## C3 spoofing ECU 검토

원본/해시검증완료.100 VALID·exit0, 송신/echo275374일치, 참조공격게시0·정상전달2802/3000. IVI교차검증대기. [보고서](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/ABLATION-FORMAL-C3-SPOOF-001.md).

## C3 spoofing IVI 최종수령

22H37M보존/해시검증. TX291061/RX291059, RX오류+1·위조2부족 별도예외. IDS3033전부도달, 공통게시6120정상출처, MAC_FAIL199위조pending결합. Qt경고21. 12조합수집·개별검토완료, 통합분석대기. [보고서](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/ABLATION-FORMAL-C3-SPOOF-001.md).
