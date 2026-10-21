# CHG-014 검증 증거

> 현재 상태는 [aidlc-state](aidlc-state.md), 감사 조치/검증은 [보완 기록](../../../development/reviews/experiment-evidence-audit-2026-10-04/REMEDIATION.md)을 따른다. 이하 v2~v8의 미적용·대기 표기는 기록 당시 시점이며 현재 상태를 덮어쓰지 않는다.


## LOAD-CHECK 후속 진단 v3

attack_tx_errors가 1건이라도 있으면 TX_ERRORS로 INVALID 처리하고 OSError.errno를 raw 로그에 보존하도록 수정했다. 일부 송신 성공과 오류가 공존하는 회귀 및 errno=105 기록 회귀를 포함해 test_live_experiments.py 18 passed(WSL, 1.59s). 송신률·버스 설정은 변경하지 않았다. tmp/load-diagnostic-v3/load-diagnostic-v3.tar.gz는 v2 위에 적용하는 3파일 overlay이며 개별 파일 해시 검증 완료. 물리 원인은 아직 미확정이며 수정본 실장비 재현이 필요하다.

기준일 2026-10-03. 시작 HEAD `118cc9e`, 브랜치 `feat/security-live-validation`. 기존 미추적 수신기·판정기를 보존하여 보완했다. ICD·IVI 제품 코드는 변경하지 않았다.

## 실행 결과

| 검사 | 환경·결과 |
|---|---|
| Python 전체 회귀 | WSL Ubuntu, Python 3.12, 기존 `~/venvs/capstone-security`: 55 passed (기존 37 + 신규 18) |
| ECU configure/build | WSL GCC 13.3, OpenSSL 3.0.13, 기존 `tmp/adc-smoke-deps/install`의 GTest 1.16.0 사용, 성공 |
| ECU CTest | `tmp/chg014-ecu-build`: 17/17 통과 |
| 프로파일 | 실제 SensorSimulator→EKF→FSM 1,000 step. WARNING step 47/SOC 18.422%, CRITICAL step 63/SOC 4.63028%. dt=0.1초 모델 시간이며 물리 지연 아님 |
| ROC 참고 표 | 기존 독립 seed로 재실행. 공식 4종 AUC 1.000, 정상 FPR 3.9%/180창. masquerade 규칙 0%, 사양 100%, 별도 environment 열 CSV 생성 |
| IF 경로 smoke | 합성 독립 seed 42 학습/142 평가, 유효 더미 MAC, 110초 중 워밍업 2초 제외 108창. 규칙 0/108 PASS, 규칙+IF 16/108(약 14.81%) FAIL. CLI는 정상적으로 실패 판정을 반환 |
| vcan | `modprobe --dry-run vcan`: 현재 WSL 커널 `5.15.153.1-microsoft-standard-WSL2`에 모듈 없음. 실제 SocketCAN pilot 미실행 |

GTest 최초 configure는 시스템 설치가 없어 실패했으며 기존 작업공간의 GTest 설치를 명시하여 해결했다. matplotlib 미설치로 ROC PNG는 생성하지 않았고 CSV를 보존했다. 추가 `-Werror` 빌드 시도는 사용량 한도로 도구 실행 전 중단되었으므로 해당 옵션 통과를 주장하지 않는다. 후속 일반 빌드·CTest는 다시 통과했다.

## 재현 명령

```sh
cmake -S adaptive_ecu -B tmp/chg014-ecu-build -DECU_BUILD_TESTS=ON -DCMAKE_PREFIX_PATH="$PWD/tmp/adc-smoke-deps/install"
cmake --build tmp/chg014-ecu-build -j4
ctest --test-dir tmp/chg014-ecu-build --output-on-failure
~/venvs/capstone-security/bin/python -m pytest security/tests -q
~/venvs/capstone-security/bin/python security/experiments/analyze_roc.py --out-dir tmp/chg014-roc
```

IF smoke의 임시 생성·실행 코드는 `tmp/chg014-if-smoke.py`, 출력은 `tmp/chg014-if/report.json`이다. 정상 입력 생성은 기존 `generate_normal(110, Random(seed))`, 인증은 공개 더미 키 `0x01` 32바이트를 사용했다. 모델/임계를 같은 평가 자료에 맞춰 변경하지 않았다. 이 FAIL은 실측 최종 FPR도, 제품 IF 전체 완료도 아니다.

## 최초 구현 시점의 검증 범위와 남은 인수 (후속 결과는 아래 참조)

새 Python 시험은 MAC 실패 후 counter·pending 보존, 만료/replay/frame flags, 정상 오탐 분모·무수신 timer, 실제 캡처 쌍 선택, MSG_CONFIRM 구분 모의 시험, 송신 실패·프로세스 회수·전체 실행기 성공/실패 원장, 중복 집계·환경 혼합 방지, ADC 원시값 보존을 검사했다. 모의 transport 시험을 vcan 통과로 표기하지 않는다.

- RPi vcan pilot, 물리 1,200 유효 시행, 부하 ≥50%, 물리 정상 FPR·IF 성능은 사용자 실행 대기.
- 실제 드라이버 own echo·캡처 손실·시각 오차·지속 송신률은 pilot 인수 전 미검증. 앱 수신 시각을 정확한 wire 시각으로 간주하지 않는다.
- IVI 시험 모드·제품 수용/거부/화면 로그는 사용자 지시에 따라 IVI 담당자가 구현한다. Python 참조 판정은 제품 인수를 대체하지 않는다.
- ADC 가운데·상단 1,000회, IT-001~005와 T1~T4 실측은 로그 대기.
- IF 추가 합성 오탐 FAIL을 보존한다. 정상 실측 학습/독립 평가 뒤 필요하면 별도 선정 자료로 임계를 검토한다.

실행은 [플레이북](../../../development/playbooks/live-security-validation.md), IVI 경계는 [인계](../../../development/security/IVI_실험_인계.md)를 따른다.

## 2026-10-04 실장비 시험 증거 수령 및 보존

정상 인증·예비 2회·공식 성능 2회·SPI 비교·ADC 노브·RPi vcan pilot 자료를 수령했다. 원본 위치와 시험별 판정은 [시험 보존 기록](../../../development/experiments/ecu-ivi-integration-2026-10-03_04/README.md)을 따른다.

- PERF-FORMAL-001은 양측 인증 payload 4개 불일치로 보류 기록을 유지한다.
- PERF-FORMAL-002는 1000표본, 평균 6.473276ms·최대 65.029527ms, 양측 2998프레임 일치로 Qt 표시 경로 지연·관측 주기 조건 충족. 물리 픽셀 지연은 미측정이다.
- IT002-KNOB-001은 두 전이 인증과 32.626초 간격 확인. 화면 파일은 미첨부이며 사용자 관측으로 구분한다. 프로파일 경로는 별도다.
- RPi CTest 17/17 및 전용 가상환경 pytest 55/55는 사용자 출력 근거다. 최초 시스템 Python은 sklearn 부재로 54통과/1실패였고 가상환경 설치 후 해소됐다.
- VCAN-PILOT-001은 세 구성 12시행 VALID·COMPLETE, 결과 파일 23개 해시 확인. Config 2 replay의 동일 payload/정상 인증 결합 1건은 별도 판정 검토 중이며 물리·IVI 인수를 대신하지 않는다.
- 원본은 tmp 밖의 raw/에 복사 보존하고 Git에서는 제외한다. 물리 Ablation·부하·IF 성능은 미완료, IF 개선은 보류다.

후속 PHYSICAL-PILOT-001 Config 1의 ECU 원본도 수령했다. 4시행 VALID, 실행 COMPLETE 및 종료코드 0, manifest 결과 해시 7개 일치. 공격 자기 echo는 송신 건수와 일치하고 송신 오류·관측 드롭은 0이다. [물리 C1 보고서](../../../development/experiments/ecu-ivi-integration-2026-10-03_04/reports/PHYSICAL-PILOT-001-C1_결과.md)에 참조 수신기 결과를 기록했다. IVI 대조와 버스 부하 인수는 대기하며 전체 본 실험 합격으로 처리하지 않는다.
# Config 2 물리 pilot ECU 자료 추가

PHYSICAL-PILOT-001-C2 archive 및 내부 자료를 보존했다. COMPLETE·4 VALID·종료코드 0, manifest 결과 7개 해시 일치. ECU 참조 판정과 replay 수용 1건의 원시 사건 해석은 [Config 2 결과](../../../development/experiments/ecu-ivi-integration-2026-10-03_04/reports/PHYSICAL-PILOT-001-C2_결과.md)에 기록했다. IVI 제품 판정 및 점유율은 수령 대기이며 이번 자료만으로 합격 처리하지 않았다.

## Config 2 IVI 수령 후 검증

06H09M 자료 포함 보존 원장 253개 해시 검증. ECU 관측 7483건은 IVI 7485건의 앞부분과 정확히 일치하며 마지막 정상 한 쌍은 IVI에만 기록됐다. receiver 4427건은 CAN 필터 대상과 일치. counter 거부 1177건 및 spoofing MAC_FAIL 1건 확인. canbusload 최대 표시 전체 19%, flooding 13%로 공식 50% 부하 기준 미충족. 상세와 재현 방법은 통합 증거 폴더의 PHYSICAL-PILOT-001-C2_결과.md에 기록했다.

## pilot 보완 v2 로컬 검증

송신 select sub-ms 대기 및 처리시간 포함 스케줄, IF 실행 경계 학습·독립 1% 보정 정책 추가. 최종 WSL Python 전체 59 passed in 9.20s. 독립 합성 300초 평가 3세트: 4/298, 0/298, 1/298 오탐 창. 과거 평가 데이터로 임계를 맞추지 않았다. 이상 특징 양의 점수 회귀 유지. WSL vcan0 없음 및 vcan 생성 Unknown device type으로 실 SocketCAN 시험 미실행. 물리 송신률·50% 부하·IF 인수는 미완료.

미커밋 소스 93개 전달 패키지 SHA256: 9afb1cd88d6b29769b86143208dceb136d8eed95e9d054e2495c19483ec3bd21. 원본 입력·최종 pytest 출력·manifest·패키지는 통합 증거 raw에 보존. 실행 절차는 reports/PILOT_보완_v2.md 참조. 키·장비 주소는 포함하지 않았다.
## IDS 수신 시각 보완 v4 (2026-10-04)

Config 3 spoofing 직전 중단 원인은 PERIOD_TOO_SHORT였다. 동일 인증 프레임 간격은 IVI 100.017ms, ECU 참조 99.930ms인데 IDS 처리 시각 기준으로는 45.851ms였다. 이번 수정은 이 측정 경로를 교정한다. IF 임계값, CAN 계약, 경보 중단 조건은 변경하지 않는다.

- security/ids/runtime.py: recv 이후 monotonic 시각 대신 Linux SO_TIMESTAMPNS_NEW의 커널 수신 시각을 읽는다. 시작 시 고정한 offset으로 기존 monotonic 로그와 맞춘다.
- 타임아웃 타이머는 대기 시작 시각까지만 진행하여, 타임아웃 직후 도착한 프레임을 앞지르지 않는다. 무수신 판정은 최대 한 번의 50ms 대기만큼 추가 지연될 수 있다.
- timestamp 누락·잘림·잘못된 형식은 실패로 처리한다. realtime/monotonic offset이 10ms 넘게 바뀌면 중단한다. 시스템 시각 조정 때문에 생긴 결과를 정상 시험으로 채택하지 않는다.
- 회귀 시험: 지연된 읽기에서도 정상 100ms 간격 보존, 실제 10ms 간격 탐지 유지, timeout 경계, 잘못된 timestamp, 시계 변동, Linux UDP loopback의 실제 ancillary ABI 확인.
- 검증: WSL Python 전체 66 passed in 8.69s, git diff --check 통과. UDP 시험은 CAN 시험이 아니다. RPi SocketCAN 적용 및 Config 3 완료는 아직 미검증이다.

패키지: tmp/ids-timestamp-v4/ids-timestamp-v4.tar.gz. 기존 v2+v3 위에 runtime.py와 대응 테스트 두 파일을 적용한다. 개별 파일 해시는 패키지 manifest에 있으며 압축 후 재검증했다. C++ 변경이 없어 재빌드 불필요. 적용 전 실행 중인 ECU/IDS/하네스가 없는지 확인하고 대상 파일을 백업한다. 적용 후 기존 venv로 security/tests 전체를 실행한다. 통과하면 기존 fit/calibration을 그대로 사용해 새 run ID와 출력 폴더로 Config 3 pilot을 수행한다. 이전 부분 실행은 보존하며 덮어쓰지 않는다.

본 실험 1,200회 완료나 flooding 50% 문제 해결을 뜻하지 않는다. 고부하 ENOBUFS 문제는 별도 미해결 항목이다.

커널 API 근거: https://docs.kernel.org/networking/timestamping.html (SO_TIMESTAMPNS_NEW, __kernel_timespec).

PHYSICAL-PILOT-IF-002 ECU 검토: COMPLETE·4 VALID·exit0, v4 커널 시각 적용 확인 및 manifest9파일 해시 검증. baseline 주기 오탐 재발 없음. 단 spoofing baseline IF_ANOMALY 1건(비송신)이 있으며 공격 창 IF 경보는 0건이다. spoofing 정상 31관측/29전달은 IVI 대조 필요. IVI 인수 및 본 실험 대기. 상세: [결과](../../../development/experiments/ecu-ivi-integration-2026-10-03_04/reports/PHYSICAL-PILOT-IF-002_결과.md).

PHYSICAL-PILOT-IF-002 IVI 교차검증 완료: ECU11,790 prefix 일치·IVI11,808 및 양측 CAN 증가량 일치, receiver6,391 필터 일치. BMS312·IDS121 게시. spoofing counter270/278 MAC_FAIL은 주입 원본과 정상 인증의 짝 교란으로 양측 일치하며 정상 2건 가용성 영향으로 기록한다. CAN 오류 증가0. dashboard130/candump0/canbusload0, 최대부하24%. 공식부하 미달·IF 1건은 남음. 결과 보고서에 기록.

PHYSICAL-PILOT-IF-002 종료 경위 보완: 사용자가 IVI 팀원 확인을 전달함. 대시보드 exit130은 시험 종료 후 Ctrl+C 수동 종료. 원본 종료코드를 유지하고 보고서와 상태 문서에 반영함.

LOAD-QUEUE-001 ECU 검증: qlen100에서도 INVALID/TX_ERRORS. 5445송신/관측, ENOBUFS1796, qdisc drop증가1814, 종료backlog0. manifest4파일 검증·raw 보존. 기존qlen10의5425송신/1828오류와 비교해 문제 미해결. IVI 대조 및 qlen10 복구 확인 대기. [보고서](../../../development/experiments/ecu-ivi-integration-2026-10-03_04/reports/LOAD-QUEUE-001_결과.md).

LOAD-QUEUE-001 IVI 대조 완료: ECU5607 prefix 일치·IVI5609=양측 CAN 증가량, receiver164 필터 일치·정상게시80. 종료코드 모두0·CAN 오류증가0, 최대부하45%. 큐 변경만으로 미해결. 원인 확정 없이 SPI/드라이버 처리 경로 검토로 전환하며 동일 시험 반복하지 않음.

LOAD-SPI2M-001 ECU 수령·보존·manifest4파일 검증. SPI2MHz/qlen10, 송신7299·ENOBUFS12·qdisc drop36, INVALID/TX_ERRORS 유지. 이전1MHz/qlen10 송신5425·오류1828보다 개선 관측. IVI부하·대조 대기이며 해결 완료 아님.

LOAD-SPI2M-001 IVI 검증완료: ECU7455 prefix/IVI7457 및 양측통계 일치, receiver158 필터일치. 부하61/62/56% 관측으로50% 수치 넘었으나 TX_ERRORS12로INVALID 유지. AUTH_TIMEOUT11·ORPHAN1, CAN오류0. 다음후보2600fps는 미실행.

LOAD-SPI2M-002 ECU 수령검증: manifest4파일 해시확인, COMPLETE/VALID/exit0, 요청2600fps·3초, 송신/관측5691·오류0·정상30/30, qdisc drop증가0. 전체TX증가5873. IVI점유율·대조는 대기이며50% 충족 미확정.

LOAD-SPI2M-002 IVI검증: ECU5871 prefix/IVI5873 및 통계일치, receiver182필터일치·정상91게시·인증거부0. 최대48%(242660bits/500000=48.532%)로50% 미충족. 시행VALID와부하기준미달 분리. 다음2800fps 후보 미실행.

LOAD-SPI2M-003 ECU 검증완료: manifest4파일 해시검증·원본보존, SPI2MHz/qlen10 요청2800fps, COMPLETE/VALID/exit0, 공격7038송신·관측/오류0·정상30/30, qdisc drop증가0·전체TX증가7220. IVI 대조·50% 부하판정 대기.

LOAD-SPI2M-003 IVI대조완료: ECU7218prefix/IVI7220·양측통계일치, receiver182일치·인증91/거부0·오류증가0. exact부하60%가2보고구간에서관측, 송신오류0·qdisc drop증가0 동시확인. 이번Config2시행 TC-SEC-005-d수치조건충족. 공식1200회·Config3 IF검증완료와구분.

공식 첫 실행 ABLATION-FORMAL-C1-FLOOD-001 ECU수령: 7회시도·VALID6/INVALID1, 7회ENOBUFS1로중단, 8~100미실행. 공식전용디렉토리에원본보존·manifest10파일검증. IVI부하·대조전공식인정횟수미확정.

공식 C1 flooding 첫실행 IVI대조완료: 전체50024프레임일치·IVIRX통계일치·receiver453일치, 시행1~6 각각59~61%내부부하보고 확인. 공식유효6/100 인정,7회ENOBUFS1무효유지. 원본과표본별근거는공식전용보고서에보존.

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

## 감사 보완 최종 검증

WSL 전체 security/tests 97 passed (10.11s). 원본 inventory 2,251개 해시 일치, 12조건/16실행 재생성, 출력61개 해시 및 receiver/candump16실행 일치 확인. 프레임 차이3개는 기존 C1/C3 spoofing 예외로 보존. 상대 링크·코드 펜스 검사 통과. [기계 검증](../../../development/reviews/experiment-evidence-audit-2026-10-04/validation.json). 장비 재시험/물리 픽셀 측정/외부 백업 완료를 뜻하지 않는다.

## 최종 실험 결과 보고서 검증

[보고서](../../../development/experiments/최종실험_결과_보고서.md)의 4개 생성 표를 12조건·16실행 publication/summary.json과 대조했다. 정상 성능·FPR 주요 수치, 상대 링크·명시 앵커·TC/NFR ID·표 열 수·코드 펜스·UTF-8 검사를 수행했다. 저장소 루트 명령: `python -X utf8 docs/development/reviews/experiment-evidence-audit-2026-10-04/verify_final_report.py`. [기계 결과](../../../development/reviews/experiment-evidence-audit-2026-10-04/final-report-validation.json)를 참조한다. 이번 변경은 보고서·문서 연결·검증 도구이며 하드웨어 재시험이나 제품 코드 변경은 수행하지 않았다.
