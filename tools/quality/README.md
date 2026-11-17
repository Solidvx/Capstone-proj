# 로컬 품질 검사

Linux, GCC와 같은 버전의 gcov, CMake, Qt≥6.8, GoogleTest, cppcheck, Python pytest가 필요하다. 저장소 루트에서 실행한다. 새 build/output 경로를 사용하고 예전 `.gcda`를 섞지 않는다.

```sh
cmake -S adaptive_ecu -B /tmp/ecu-quality -DCMAKE_BUILD_TYPE=Debug -DENABLE_COVERAGE=ON
cmake --build /tmp/ecu-quality -j2
python3 tools/quality/ctest_gate.py --build /tmp/ecu-quality --component ecu
python3 tools/quality/coverage.py --build /tmp/ecu-quality --source adaptive_ecu --component ecu --output-dir /tmp/ecu-coverage
cmake -S ivi_platform -B /tmp/ivi-quality -DCMAKE_BUILD_TYPE=Debug -DENABLE_COVERAGE=ON -DIVI_BUILD_EXPERIMENT_TOOLS=ON
cmake --build /tmp/ivi-quality -j2
QT_QPA_PLATFORM=offscreen python3 tools/quality/ctest_gate.py --build /tmp/ivi-quality --component ivi
python3 tools/quality/coverage.py --build /tmp/ivi-quality --source ivi_platform --component ivi --output-dir /tmp/ivi-coverage
python3 tools/quality/static_analysis.py --output-dir /tmp/cppcheck-quality
python3 -m pytest -p no:cacheprovider security/tests ivi_platform/test tools/quality/tests -q
```

Linux 기본 품질 구성은 ECU28개(새 SOC CSV 제품 시험 포함), IVI21개 CTest를 기대한다. ECU 바이너리를 IVI에 제공해 추가하는 제품 통합 구성은 별도 프로필이며 이 기본 목록과 섞지 않는다. vcan 시험은 기존 가상 인터페이스를 준비하고 `CAPSTONE_SESSION_TEST_INTERFACE=vcan0`을 설정한다. 가상 장치가 없는 개발 환경에서만 `--allow-no-vcan`으로 ECU의 session-vcan/ECU-session-product/receive-lifecycle, IVI의 socketcan-receiver/session-vcan skip을 명시적으로 허용할 수 있다. 그 외 skip이나 시험 누락은 실패다. 현재 GitHub workflow는 가상 CAN을 요구하며 이 완화를 사용하지 않는다. skip은 통과 개수에 포함하지 않는다. 이름/개수 변경 시 `ctest_gate.py` 기대 목록도 리뷰한다. coverage exit1은 목표 미달, exit2는 분석 자체 무효다. cppcheck warnings/styles는 보고하며 Error 또는 실행/파싱 실패는 차단한다. 최신 전체 커버리지 수치는 새 coverage 빌드로 재측정해야 하며 예전 수치를 현재 결과로 재사용하지 않는다.

coverage.json의 uncovered_failsafe_branches는 합집합에서도 미실행인 Fail-safe 분기의 파일/줄/함수/분기 index, gcov의 throw 및 source/destination block을 보존한다. 실행 데이터가 다른 객체에 있으면 중복 분기를 미실행으로 세지 않는다. 이 목록은 검토 근거이며 자동 제외나 분모/합격 기준 변경을 하지 않는다. 예외 심사 전에는 도달 불가로 분석한 경로도 원래 분모에 포함하며 FAIL을 유지한다.

## 제품 통합 검증 프로필

기본 IVI21개와 실제 ECU/IVI 제품 통합23개(현행 CSV 계측·계산/CAN 수신 성공 복구·보호 사건의 저장/새 세션/Qt 이력 연결 포함)를 함께 검증하려면 ECU의 복구 fixture까지 빌드한 뒤 다음을 실행한다. 기존 가상 CAN만 사용하며 실물 장치에는 실행하지 않는다. `ivi-integrated`는44개 이름을 정확히 검사하고 `--allow-no-vcan`을 주더라도 skip을 허용하지 않는다. fixture 누락으로 일부 시험이 등록되지 않으면 실패한다. 보호 사건 제품 시험은 기존300ms BMS 신선도와1초 진단/3초 보고 유효기간을 구분하고 동일 heartbeat의 이력 중복도 거부한다.

```sh
cmake -S ivi_platform -B /tmp/ivi-quality -DIVI_TEST_ECU_EXECUTABLE=/tmp/ecu-quality/adaptive_ecu
cmake --build /tmp/ivi-quality -j2
CAPSTONE_SESSION_TEST_INTERFACE=vcan0 QT_QPA_PLATFORM=offscreen python3 tools/quality/ctest_gate.py --build /tmp/ivi-quality --component ivi-integrated
python3 tools/quality/coverage.py --build /tmp/ecu-quality --source adaptive_ecu --component ecu --output-dir /tmp/ecu-integrated-coverage
python3 tools/quality/coverage.py --build /tmp/ivi-quality --source ivi_platform --component ivi --output-dir /tmp/ivi-integrated-coverage
```

coverage는 같은 새 빌드의 기본+제품 실행 누적 결과이며 이전 기본 구성 단독 보고서를 덮어쓰지 않는다.

## GitHub workflow와 로컬 프로필의 경계

quality.yml은 native x86/ARM64의 Debian trixie job 컨테이너에 위 제품 프로필을 연결한다. NET_ADMIN으로 job 내부 vcan0만 생성하고 명시적 health 확인 뒤 ECU28/IVI제품44 strict gate를 실행한다. IVI CMake에는 이미 빌드한 실제 ECU 경로를 전달한다. 가상 CAN 지원/권한이 없거나 fixture/시험이 빠지면 실패하며 기본 프로필로 대체하지 않는다. 커널 모듈 설치・host network・privileged 실행・실물 장치 변경은 이 workflow에 없다.

ECU/IVI/Python 시험과 coverage는 build 성공 뒤 독립 단계라서 한 시험 실패가 다른 보고서를 생략하지 않는다. 양측 coverage가 모두 실행되며 원래 미달/분모・미실행 분기를 보존한다. upload-artifact는 보고서/JUnit 외에 제품 시험 결과 디렉터리도 보존한다. 실제 GitHub runner 커널의 vcan 지원과 job 컨테이너 권한・패키지/Qt 버전 인수는 별도다. 로컬 VM 실행이나 YAML/셸 문법 검사만으로 원격 CI 성공을 주장하지 않는다. 공식 PC1200회・실제 IF 효과・Pi 인수도 이 프로필 범위가 아니다.

## TC-PERF-002 원본 BMS 간격

기존 Linux vcan과 실제 ECU/Qt를 사용해101개 BMS 원본을 수집한다. 상대가 session-v2 교환을 완료해야 하므로 Qt도 함께 실행한다. observer는 수신 전용이며 임시 공개 더미 키를 회수한다. VM 시간 설정이나 실물 인터페이스를 바꾸지 않는다.

```sh
CAPSTONE_SESSION_TEST_INTERFACE=vcan0 python3 common/test_bms_period_product.py --ecu /BUILT/adaptive_ecu --ivi /BUILT/ivi_dashboard --policy adaptive_ecu/data/session-v2-development.conf --out-parent tmp/bms-period-NEW
python3 -m tools.quality.bms_period --input-dir tmp/bms-period-NEW/bms-period-ACTUAL --output tmp/bms-period-NEW/new-report.json
```

실제 출력 폴더는 임의 suffix를 포함해 첫 명령의 output에 표시된다. 두 번째 명령은 보존한 frames.jsonl/capture.json의 재평가이며 새 출력 경로만 허용한다. 절대 kernel realtime stamp를 고정 로컬 monotonic epoch로 매핑하며 최대 변화10ms, boot・경계/순서・SocketCAN/인터페이스 drop・오류를 검사한다. 시계 문제/부분/101프레임 미만은 INVALID(exit2), 유효하지만90~110ms 밖 간격이 있으면 FAIL(exit1), 모두 충족하면 관측 기준 PASS(exit0)다. 모든 간격을 보고하며 평균으로 위반을 감추거나 일부100개만 골라 쓰지 않는다.

원본/auth/제어를 함께 보존하지만0x100/DLC8 표준 데이터만 간격에 포함한다. 절대 ECU 송신 순간이 아닌 수신 관측 간격이다. sender 인증/실제 물리 CAN 송신/버스 부하/실물 TC 합격을 추정하지 않으며 환경 의존 타이밍 합격을 CI에 강제하지 않는다. 최종 소프트웨어 측정/해시를 참고한다.

## NASA 후보 원시 판독

원래 실행 계획에 지정한 후보 ZIP을 준비한 뒤 기존 scipy 환경에서 아래를 실행한다. 다운로드 원본은 [NASA PCoE 공식 안내](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/)의 Batteries 배포 ZIP 안의 `5. Battery Data Set/2. BatteryAgingARC_25_26_27_28_P1.zip`이다. 외부 ZIP/원본 MAT는 큰 원시 자료이므로 저장소에 커밋하지 않고 별도 보존한다.

```sh
python3 -m tools.quality.nasa_data --candidate /PRIVATE/candidate.zip --output-dir /PRIVATE/new-inspection
```

이 CLI는 역사 후보 SHA2567fa159be…8c8e3b8과 내부4개 MAT hash/CRC를 검사한다. 원시 Time/전압/전류/온도 배열 길이・유한값・단조 시각, 나머지 측정 필드/Capacity의 유한값을 검사한다. cycle 경계를 잇거나 NaN행을 지우지 않으며 charge/discharge의 INVALID 사유를 전부 보존한다. impedance84개는 이 검사 대상이 아니라고 따로 기록한다. 출력은 새 디렉터리만 허용하고 원본을 수정하지 않는다.

B0028의0-based cycle3은 과거 구조 조사와 대조할 원시 CSV로만 내보낸다. 단셀 terminal V・실제 부호의 A・소수 온도・원시 초를 유지하며 원시 CSV의 hash를 남긴다. 데이터 판독 완료와 유효 cycle 전체/보간/제품 입력/정확도 인수를 구분한다. 소스는 표준 라이브러리로 검사 로직을 시험할 수 있고 실제 MAT CLI에만 scipy가 필요하다. 이번 환경은 이미 설치된 scipy1.16.3을 사용했으며 새 패키지를 설치하지 않았다.

독립 판독 결과는4개 MAT hash・각59개 charge/discharge 중58개 유효/마지막1개 무효・원시641표본을 보존한다. 재표본화 방법/결측 상한・단셀/가상 팩 모델・정수 온도인 제품 로더의 양자화는 아직 별도 검토 대상이다. 이 파일을50Ah 팩 EKF에 바로 넣거나 SOC 정답으로 사용하지 않는다.

### NASA 두 변환 후보·실제 CSV 로더 비교

원시 자료와 가상 팩 모델을 섞지 않고, 역사 비교 cycle3의 첫3600초를0.1초 격자로 변환한다. 두 후보를 모두 보존하며 어느 쪽도 운영 정책으로 자동 채택하지 않는다.

```sh
cmake -S adaptive_ecu -B /PRIVATE/ecu-build -DECU_BUILD_TESTS=ON
cmake --build /PRIVATE/ecu-build --target profile_loader_fixture -j2
python3 -m tools.quality.nasa_replay --candidate /PRIVATE/candidate.zip --loader-executable /PRIVATE/ecu-build/profile_loader_fixture --output-dir /PRIVATE/new-replay-comparison
```

`linear`는 원시 점 사이 선형, `previous`는 다음 원시 점까지 이전 값 유지다. 전류는 각0.1초 구간의 모델 적분을0.1초로 나눈 구간 평균이고, 전압/온도는 종료 시각의 해당 모델 값이다. t0를 첫 update로 중복하지 않고0.1..3600초의36,000행을 만든다. 외삽・NaN행 제거・cycle 이어 붙이기・실제 단셀 전압×10 변환을 하지 않는다. 이 자료는 파일 전체를 사용하는 오프라인 재생 후보이며 선형 방식의 미래 샘플 참조를 실시간 센서 알고리즘으로 설명하지 않는다.

`grid.csv`는 재구성한 시각/단셀 V/A/소수°C, `profile.csv`는 실제 SensorSimulator에 넣는3열, `loader.csv`는 제품 로더가 실제 반환한float V/A/int8°C다. 테스트 전용 profile_loader_fixture는 EKF/CAN/장치/키를 초기화하지 않으며 실제 입력 행 수가 요청과 다르면 마지막 행 유지로 채우지 않는다. 파일/소스/실행본의 전후 hash・모든36,000행의float 변환/온도 반올림・적분 보존을 검사한다.

수치적 적분 보존 허용차1e-10Ah는 과거 후보 검토의 수치 기준이며 실제 전류 정확도 기준이 아니다. 제품 로더의float 전류 양자화 뒤 적분 차이와 온도 반올림/clamp 영향도 따로 보고한다. `COMPARISON_COMPLETE`는 두 후보의 수치/로더 비교 완료다. 결측 공백 상한/운영 보간 방식/물리 모델은 채택하지 않았고 제품 main/실시간 센서・SOC 정확도도 인수하지 않는다. 실패/중단 원본과 각 후보를 삭제하거나 기존 출력에 덮어쓰지 않는다.

실제 비교/원본/해시를 따른다. 기존 test_soc_profile_product는 S-21 외에 이 로더의float 변환/온도 경계・잘못된 표본 수/누락 파일을 검사하도록 보완했다. CMake가 실제 fixture 경로를 전달하며 CTest 등록 수28은 유지한다. 새 fixture는 제품 설치 대상이 아니다.

## 분석 그림 사용

### TC-BMS-002 고정 CSV 재현

승인된 S-21 7조건을 실행하려면 저장소 루트에서 아래를 사용한다. Python은 표준 라이브러리만 사용하며 새 출력 경로가 필요하다. 데이터/로그는 큰 생성물이므로 보존할 디렉터리에 별도 두고 보고서의 파일 해시로 연결한다. 실행 시간은1시간분의 고정 간격 계산을 소프트웨어에서 재생하는 시간이며 실제1시간 CAN 주기 측정이 아니다.

```sh
cmake -S adaptive_ecu -B /tmp/ecu-s21 -DECU_BUILD_TESTS=ON
cmake --build /tmp/ecu-s21 --target evaluate_soc_profile -j2
python3 -m tools.quality.bms_profile --executable /tmp/ecu-s21/evaluate_soc_profile --output-dir tmp/s21-NEW
```

`truth.csv`는 t=0과 각 update 종료 시각의 참 SOC36,001행이다. 조건별 `observations.csv`는 전압/전류/온도36,000행이며 정답/시각 열이 없다. native 실행기는 이 관측만 받아 실제 SensorSimulator PROFILE_CSV와 제품 EkfSocEstimator를 호출하고, 동일 float 양자화 전류/dt/초기값의 적분 결과도 `predictions.csv`에 출력한다. SensorSimulator의 마지막 행 유지가 짧은 자료를 완성하는 데 사용되지 않도록 실제 행 수를 확인한다.

`inputs.json`은 고정 조건/모델/관측 시점과 입력 hash, `report.json`은 시행 전후 입력/실행본/소스 확인・실제 관측 echo/시각/표본/유한 범위・RMSE/최대오차・모든 파일 hash를 남긴다. 입력/출력이 불완전하면 INVALID, 필수 주 비교 실패는 FAIL로 남기되 후속 민감도 결과도 수집한다. 기존 출력은 덮어쓰지 않으며 실패/중단의 부분 파일도 보존한다. exit0은 고정 합성 기준 PASS, exit1은 기준 FAIL, exit2는 INVALID/INTERRUPTED다.

주 비교2개는 각각 엄격한 EKF RMSE 우위를 요구한다. 대조군은 기존 float 반올림 누적 상한으로 수치 정합을 확인하며, 민감도4개는 열위도 그대로 보고한다. 이 민감도 행의 PASS는 보고 조건 충족이며 EKF 우위가 아니다. 실제 셀/OCV 정확도・NASA 재생・main/CAN/ADS1115/화면 인수와 구분한다. 이전 예정 `data/battery_profile_1h.csv` 입력은 이 조건별 생성 CSV와 manifest로 관리한다.

같은 실행 경로의 CTest는 `test_soc_profile_product`이며7조건 외에 짧은 CSV/잘못된 표본 수/누락/비유한 관측의 거부를 검사한다. raw 결과는 build의 soc-profile-test-results 아래 보존하며 CI artifact에도 연결한다. 실측 수치/해시를 참고한다.

### N02 센서 입력 보완 사례

기존 가상50Ah/초기80%/-2A/S-21 OCV 궤적과 허용 고정 입력 대조군, 전압 drift/jump/freeze·전압/전류 모델 불일치를 별도 합성 자료로 평가한다. 운영 freeze/정합성 규칙을 켜거나 실제 CAN 공격을 주입하는 도구가 아니다.

```sh
cmake --build /PRIVATE/ecu-build --target evaluate_soc_profile
python3 -m tools.quality.sensor_scenarios \
  --executable /PRIVATE/ecu-build/evaluate_soc_profile \
  --settings docs/aidlc/changes/CHG-029/sensor-source-settings.json \
  --output-dir /PRIVATE/new-source-results
```

settings의 표본 수/0부터 세는 사건 시작 포함·종료 제외/세 변조량은 모두 명시해야 한다. 제공 파일의2,000표본/사건500,1500)/전압 drift 최종-0.5V·jump-6V/전류 bias+4A는 재현용 fixture다. 실물 센서의 허용 범위나 경보 임계로 채택하지 않는다. 시간은0.1초 계산 간격의 합성 축이며 실제200초 CAN 송신을 측정한 것이 아니다.

| 사례 | 입력 변화 | 라벨 의미 |
|---|---|---|
| control | 기존 S-21 전압 궤적/-2A/25°C | 고장 주입 없음 |
| allowed_constant | 처음 관측 전압을 유지 | 제품에서 허용하는 고정 입력 대조군. 실제 배터리 정상성 주장이 아님 |
| voltage_drift | 사건 구간에서 전압 bias가 지정 최종값까지 증가 | 합성 센서 고장 |
| voltage_jump | 사건 구간에 지정 전압 bias 적용 | 합성 센서 고장 |
| voltage_freeze | 사건 직전 전압만 유지 | 합성 센서 고장. 정상 고정값과 관측이 같을 수 있음 |
| voltage_current_mismatch | 기준 전압은 유지하고 관측 전류에 bias 적용 | 지정 가상 참조 모델과의 불일치. 실차의 보편적 판정 기준이 아님 |

각 사례의 observations.csv만 native SensorSimulator/EKF/제품 encodeBmsStatusFrame에 전달한다. labels.jsonl의 센서 고장 주입 구간/참조 변화는 평가 전용이며 can_attack=null이다. native.csv에는 실제 float 관측/추정과 BMS bytes를 남기고, 공개 더미 인증 fixture로 기존 legacy/session raw 규칙을 대조한다. 실제 ECU/IVI session/참조 수신기·IF는 실행하지 않는다.

원본·생성기·native 실행본/입력 hash·행 수/변환·구간·모든 reason/type을 보존한다. 입력/라벨 변경은 hash만 고쳐도 사전 정의한 내용과 비교해 거부한다. native exit2는 NATIVE_REJECTED로 기록하고 다음 사례를 수행한다. 다른 비정상 종료와 잘못된/부분 출력은 INVALID이며 정상 수집/진단 성공으로 채우지 않는다. COMPLETE 상태는 분석 완료이지 센서 고장 탐지 성공이 아니다. 새 출력 폴더만 허용하며 중단/실패의 원본을 덮어쓰지 않는다.

짧은100표본 사례에서는 control/allowed_constant/voltage_freeze가 같은 raw 및 더미 인증 프레임 입력을 만들었다. 긴2,000표본에서도 기존 raw 규칙의 고장 진단/공격 유형은0건이었다. 이 결과를 실제 탐지율/정상 오탐률/공격 차단율로 쓰지 않는다. [원본/수치/소스, 적용 범위 결정은 CHG-029를 따른다.

기존5열 evaluate_soc_profile 출력은 유지하고 명시적 --emit-bms만6번째 bms_payload_hex를 추가한다. test_soc_profile_product는 기존7조건×36,000회/원래 우위·열위 결과와 별개로6개100표본 보완 사례/짧은 동일 프레임 반례를 검사한다.

### R02 로그 전용 센서 시험 검사

알려진 native6사례 결과에 명시적인 합성 시험 정책을 적용한다. 운영 센서 규칙이나 CAN 공격 분류가 아니다.

```sh
python3 -m tools.quality.sensor_checks --input-root /PRIVATE/new-source-results \
  --settings docs/aidlc/changes/CHG-029/sensor-checks-fixture.json \
  --output-dir /PRIVATE/new-sensor-checks
```

검사 입력은 native 관측과 사전에 정의한 정상 프로필이다. fault 라벨을 검사에 넘기지 않는다. 변화해야 하는 참조와 비교할 때만 고정을 의심하므로 허용 고정 입력을 자동으로 고장 처리하지 않는다. 전압 프로필 불일치·급변·고정·전류 프로필 불일치의 상세 JSONL을 남기며, 설정/소스/입력 hash·행 수·시간·부분/변경 입력을 검사한다. 정책의 수치는 합성 fixture 전용이며 실제 배터리 임계나 탐지율/차단율의 근거가 아니다. 정상과 고장 관측이 같고 사전 참조도 없다면 이 방식으로 고장을 단정할 수 없다.

### 과거360회 C3의 IF 출력 귀속

```sh
python3 -m tools.quality.legacy_if_history --root /PRIVATE/pc-types360-001
```

원본은 읽기 전용으로 열고 C3 네 묶음의 manifest15파일씩/총60개 hash, 완료/정리 확인·30개 유효 시행·ECU observer_a의120개 phase marker와 evidence-v2 START/READY를 검사한다. 출력은 stdout JSON이며 실제 detector를 재생하거나 IF를 재학습하지 않는다. 다른 버전/빠진·변경된 원본을 정상 결과로 받아들이지 않는다.

같은 Node A 시계라는 원래 실험 역할 계약에서 IF 양성 **평가 시점**을 baseline/attack/post/시행 외로 분리한다. IF 입력 윈도우 자체의 시작/내용·음성 추론/모든 평가 분모는 이 과거 로그에 없으므로 endpoint를 윈도우 정답/FPR/추가 탐지 효과로 바꾸지 않는다. 보존본의 IF1건은Flooding28회 baseline 시점이고 attack endpoint는0건이다. 분석/원본 hash를 따른다. 현행 session-v2/실장비 IF 인수는 별도다.

### N07 실행 자원·수집 재현

실제 runtime CLI의 `--measure-resources` 또는 관리형 비공개 IDS 설정의 boolean `measure_resources`로 선택한다. 기본은 꺼져 있고 운영 임계/IF 특징·호출/CAN을 바꾸지 않는다. 별도 모델 파일이 없으므로 실제 state hash와 파일 크기 N/A를 구분한다. CPU/메모리·프레임/윈도우의 단위와 종료 범위는 [IDS 안내](../../security/ids/README.md#선택형-cpu메모리처리량-계측)를 따른다.

```sh
python3 -m pytest -p no:cacheprovider security/tests/test_resource_metrics.py security/tests/test_resource_analysis.py security/tests/test_session_campaign.py security/tests/test_runtime_cli.py security/tests/test_owned_ids_settings.py -q
python3 -m security.experiments.summarize_resources --events /PRIVATE/closed-events.jsonl \
  --out /PRIVATE/new-resources.json
CAPSTONE_SESSION_TEST_INTERFACE=vcan0 TMPDIR=/var/tmp python3 common/test_managed_ecu_ids.py \
  --ecu /BUILT/ecu/adaptive_ecu --ivi /BUILT/ivi/ivi_dashboard \
  --policy adaptive_ecu/data/session-v2-development.conf \
  --supervisor adaptive_ecu/scripts/supervise_ecu.py \
  --out-parent /PRIVATE/new-n07-products --measure-resources
```

제품 검사는 기존 비어 있는 가상 CAN을 다른 시험과 직렬로 사용한다. 실제 key/노드/새 vcan을 요구하지 않으며 더미 키는 정리한다. Linux 경로/짧은 private runtime이 필요하다. 첫 IDS 강제 종료 후 마지막 sample은 INCOMPLETE, 다음 세대의 종료 요청 요약은 INTERRUPTED이며 파일 hash/프로세스 회수/ECU·Qt 복구와 함께 검사한다. CPU/RSS의 실제 관찰값이지 최대 처리량·실물 Pi 성능·IF 추가 효과의 합격 수치가 아니다.

최종 소스/전체 Python639·기본 제품7·선택 제품1/IF 재생·원본 해시에 검증 범위를 남겼다. 기본 제품7개를 전체 IVI43개 재실행으로 합치지 않으며, 원래 clean native148소스/Fail-safe113/115 미달은 유지한다. 두 쌍의 작은 ON/OFF 메모리 재생 시간 차이에는 캐시/스케줄 영향이 포함돼 격리된 계측 비용으로 사용하지 않는다.

### N06 지표·합성 보정 재현

```sh
python3 -m pytest -p no:cacheprovider security/tests/test_evaluation_metrics.py security/tests/test_ids_baseline.py security/tests/test_analysis_artifacts.py security/tests/test_experiment_preparation.py -q
python3 security/experiments/run_eval.py
python3 - <<'PY'
import json, random
from security.experiments.run_eval import eval_rule
for seed in (42, 43, 44):
    print(json.dumps({'seed': seed, **eval_rule(random.Random(seed))}, allow_nan=False))
PY
```

입력은 합성이며 학습90창·별도 정상 보정60창·평가210창을 사용한다. 같은PRNG의 분리된 생성 호출이므로 실제 수집/공격 family holdout으로 표현하지 않는다. 운영 규칙/IF threshold·CAN은 바꾸지 않았다. Precision/Recall/FPR/FNR/TNR/F1/Balanced Accuracy는 ratio, MCC는 무차원 계수이며 분모0은null/N/A다. 원수/길이/라벨/점수의 오류를 거부하고 기존 점수 경계의 차이를 보존한다.

두 단계 원수/소스/실행 근거에 분모 보완만의 기존 결과 동등성과 별도 보정 후의 새 결과를 나눴다. 목표FPR1%가 실제 보정/평가FPR을 보장하지 않으며, live IF 추가 효과·최대 처리량/자원·정식 실물 인수는 남는다.

### 기존 실험/추정 결과의 그림

`pip install -r security/requirements.txt`로 matplotlib를 포함한 의존성을 준비한다. 아래 입력 경로는 실제 run 경로로 바꾼다. 출력 폴더는 없어야 한다.

```sh
python3 -m security.experiments.plot_results ablation --input-dir tmp/ablation-run --output-dir tmp/ablation-plots
python3 -m security.experiments.plot_results ekf --csv tmp/ekf.csv --manifest tmp/ekf-manifest.json --output-dir tmp/ekf-plots
```

Ablation 입력은 `run_ablation`이 남긴 manifest/settings/attempts/trial artifacts 전체다. 개별 파일 hash 검증을 통과해야 그린다. C1/C2의 IDS 지표는 N/A, 미탐지는 지연 0으로 채우지 않는다. 지연은 탐지된 시행만 평균이며 그림에 탐지수/유효시행수를 표시한다. 미수행·무효 건수는 동반 `summary.json`에서 확인한다.

EKF CSV 헤더는 정확히 `time_s,reference_soc_pct,estimated_soc_pct`다. 시간은 비음수·엄격 증가, SOC는 0~100이다. manifest 형식:

```json
{"schema":"ekf-reference-v1","environment":"synthetic","reference_source":"참조 SOC를 얻은 방법과 데이터 식별자","csv_sha256":"CSV의 실제 SHA256"}
```

environment는 synthetic/vcan/physical-can 중 실제 출처다. 물리 전압만으로 참 SOC가 알려졌다고 쓰지 않는다. EKF 결과는 선언된 참조 대비 표본 가중 RMSE/max 오차(percentage points)이며 자동 공식 인수 판정은 하지 않는다. 합성 fixture를 물리 정확도 수치로 사용하지 않는다.

## ARM64 cross/QEMU와 최신 인계

`Dockerfile.arm64`·`toolchain-aarch64.cmake`·`cross_build.py`는 native ARM64와 구분한 x86-64→ARM64 경로다. `quality.yml`의 cross job 명령을 정본으로 사용한다. 전체 CTest 등록28/21을 검사하고 비장비 C++24/18을 QEMU로 실행하며 native28/44·Python·coverage를 유지한다. [공식 CI 명세](../../docs/CICD_SPEC.md)와 배포 안전 절차를 따른다.

`python3 tools/quality/handoff.py create --repo . --out NEW-software-handoff.tar.gz`는 현재 tracked/untracked 공개 소스·공식 문서/계획·작은 증거의 목록/길이/hash를 고정한다. archive의 SHA256을 기록하고 `verify --archive ARCHIVE --sha256 SHA --extract-to NEW_DIRECTORY`로 검증·새 경로 추출한다. source reread와 목록 변화를 검사하며 기존 폴더를 덮어쓰지 않는다. 키/빌드/가상환경·주소가 있는 역사 계획·이전 source archive·공유 결정 전 큰 raw는 제외한다. 알려진 비밀 표식 검사를 포괄적 비밀 탐지 보장으로 표현하지 않는다.

추출본의 full CTest·Python/배포 도구·coverage를 새 디렉터리에서 실행해야 재현 완료다. Git commit/push·팀원 인수·실제 Pi 배포는 별도다. 생성 뒤 추가한 재현 보고서는 그 archive 안에 소급 포함되지 않는다.
