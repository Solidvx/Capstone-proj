# ECU 참조 — 명령, 파일 경로, 셀프 QA

> **예시 상태**: 코드·명령은 별도 검증 표시가 없으면 작성 골격·예정 절차다. 실행 전 생성할 파일·의존성·플랫폼을 확인한다. [공동 규약](../common/00_협업_규약.md)의 문서·예시 사용 규칙을 따른다.

> 상위 계획: [ECU.md](../../ECU.md)
> 원본: `_archive/INDEX.md` §8, `_archive/ECU.md` 부록 A·B, `_archive/ECU_최종_실행계획서.md` §15~§16

Linux/SocketCAN 명령은 Node A 또는 준비된 Linux 시험 호스트에서 저장소 루트를 기준으로 실행한다. CMake/CTest는 실제 C++17·OpenSSL·GoogleTest 환경이 필요하며 Windows에서 Linux CAN 명령을 직접 실행하지 않는다. M8 태그 예시는 공동 승인 뒤 IVI 릴리즈 조정자만 수행한다. 시험 등록 13종은 실행 통과 수가 아니다.

이 문서는 조회용이다. 절차와 맥락은 각 단계 상세 문서에 있다.

---

## 1. 실행 인자 — 정본

`adaptive_ecu/main.cpp`가 실제로 파싱하는 인자다. **다른 표기는 동작하지 않는다.**

| 인자 | 값 | 기본값 |
|---|---|---|
| `--interface` | CAN 인터페이스 이름 | `vcan0` |
| `--sensor-mode` | `constant` / `profile_csv` / `random_walk` / `ads1115` | `constant` |
| `--profile` | PROFILE_CSV 입력 경로 | `adaptive_ecu/data/battery_profile.csv` |
| `--secoc` | `on` / `off` | `off` |
| `--key` | SecOC 키 경로 | `/etc/secoc/key.bin` |

**과거 문서에 나오지만 존재하지 않는 인자**: `--secoc=on`(등호), `--secoc-enabled`, `--secoc-disabled`, `--ids=on`, `--ids`, `--soc=19`, `--log-ekf`.
**삭제 대상 모드**: `potentiometer` — SRS FR-BSW-007에 없고 동작하지 않는다 ([M3](M3_EKF_Failsafe_SecOC.md) 3.11.1).
IDS는 ECU 프로세스가 아니라 Python 별도 프로세스로 띄운다.

```bash
# 정상 실행
./adaptive_ecu/build/adaptive_ecu --interface vcan0 --secoc on --sensor-mode profile_csv

# 무방어
./adaptive_ecu/build/adaptive_ecu --interface vcan0 --secoc off
```

---

## 2. 단계별 필수 명령

### M1 — 환경

```bash
sudo ip link set can0 up type can bitrate 500000 && ip link show can0
sudo modprobe vcan && sudo ip link add dev vcan0 type vcan && sudo ip link set vcan0 up
cmake --version && gcc --version && cansend --help
```

### M2 — CAN CDD

```bash
cmake -S adaptive_ecu -B adaptive_ecu/build -DECU_BUILD_TESTS=ON
cmake --build adaptive_ecu/build
ctest --test-dir adaptive_ecu/build --output-on-failure

candump -t d vcan0 | head -20        # 송수신 관찰용. 여러 ID의 줄 간격은 BMS 주기가 아님
```

### M3 — 핵심 로직

```bash
ctest --test-dir adaptive_ecu/build -R test_ekf_soc          --output-on-failure
ctest --test-dir adaptive_ecu/build -R test_failsafe_sm      --output-on-failure
ctest --test-dir adaptive_ecu/build -R test_watchdog_manager --output-on-failure
ctest --test-dir adaptive_ecu/build -R test_secoc            --output-on-failure
python -m pytest security/tests/test_secoc.py -v

# Fail-safe 브랜치 커버리지
cmake -S adaptive_ecu -B adaptive_ecu/build-cov -DECU_BUILD_TESTS=ON -DENABLE_COVERAGE=ON
cmake --build adaptive_ecu/build-cov
ctest --test-dir adaptive_ecu/build-cov -R test_failsafe_sm --output-on-failure
lcov --capture --directory adaptive_ecu/build-cov --output-file cov.info
lcov --extract cov.info '*/failsafe_sm.cpp' --output-file fs.info
lcov --summary fs.info               # branches: 100.0%
```

### M4 — IDS와 통합

```bash
python security/experiments/run_eval.py
python security/analysis/measure_can_secoc.py
python -m pytest security/tests -v

# 물리 CAN 양방향
# Node B: candump can0 &
# Node A: cansend can0 100#DEADBEEF
# Node A: candump can0 &
# Node B: cansend can0 200#CAFEBABE
```

### M5 — Ablation

아래 세 스크립트는 후속 구현 대상이며 현재 실행 가능한 CLI로 보장되지 않는다. M5의 오프라인/vcan/물리 범위와 구성 전환·수신 관측 조건을 먼저 확인한다. 실행 전 실제 파일·`--help`·인자·출력 경로를 검증하고 준비 실패를 결과 0으로 대체하지 않는다.

```bash
python security/experiments/run_ablation.py --trials 100 --out results/ablation.csv
python security/experiments/summarize_ablation.py
python security/experiments/analyze_roc.py
```

### M6 — 문서·품질

```bash
# 물리 CAN 인계 결과 예시. 입력 manifest가 합성/vcan이면 각각 synthetic/vcan을 지정한다.
python security/experiments/plot_ablation.py --environment physical_can
python security/experiments/plot_ekf.py

cppcheck --enable=all --error-exitcode=1 --suppress=missingIncludeSystem \
         -I adaptive_ecu/include adaptive_ecu/src adaptive_ecu/main.cpp

lcov --capture --directory adaptive_ecu/build-cov --output-file cov.info
lcov --remove cov.info '/usr/*' --output-file cov.info
lcov --summary cov.info              # lines >= 80.0%
```

### M7 — 최종 검증

```bash
for cpu in /sys/devices/system/cpu/cpu[0-3]; do
    echo performance | sudo tee "$cpu/cpufreq/scaling_governor"
done

python security/experiments/verify_reproducibility.py --threshold 5
ctest --test-dir adaptive_ecu/build --output-on-failure --timeout 60
python -m pytest security/tests -v
candump -t a can0 > perf002_raw.txt        # TC-PERF-002: M7 §3.5의 0x100 선별·100간격 검사 후 판정
```

### M8 — 데모·릴리즈

```bash
./adaptive_ecu/build/adaptive_ecu --interface can0 --secoc on --sensor-mode profile_csv
candump -t a -l can0                 # candump-*.log 로 증적 저장

git switch main && git pull origin main
git tag -a v1.0.0 -m "M8: 최종 발표 준비 완료"
git push origin v1.0.0
git tag -l                           # v0.1.0 ~ v1.0.0
```

---

## 3. 파일 경로 종합

### C++ (`adaptive_ecu/`) — 현재 존재하는 것

| 파일 | 경로 |
|---|---|
| `can_driver.h`, `can_cdd.h`, `can_publisher.h`, `mock_can_driver.h` | `include/` |
| `publisher.h`, `subscriber.h`, `bms_types.h` | `include/` |
| `ekf_soc_estimator.h`, `soh_estimator.h`, `failsafe_sm.h` | `include/` |
| `secoc_module.h`, `watchdog_manager.h`, `sensor_simulator.h` | `include/` |
| `can_cdd.cpp`, `can_publisher.cpp`, `mock_can_driver.cpp` | `src/bsw/` |
| `secoc_module.cpp`, `watchdog_manager.cpp` | `src/bsw/` |
| `ekf_soc_estimator.cpp`, `failsafe_sm.cpp` | `src/app/` |
| `sensor_simulator.cpp`, `soh_estimator.cpp` | `src/app/` |
| `main.cpp`, `CMakeLists.txt` | `adaptive_ecu/` |
| `battery_profile.csv` | `adaptive_ecu/data/` |

**존재하지 않음**: `bms_component.cpp` — 그 역할은 `main.cpp`가 한다.

### 시험 (`adaptive_ecu/test/`) — CTest 등록 13종

`test_ads1115_conversion`, `test_sensor_quality`, `test_adc_acquisition_gate`, `test_ads1115_registers`, `test_publisher`, `test_mock_can_driver`, `test_sensor_simulator`, `test_can_publisher`,
`test_ekf_soc`, `test_soh_estimator`, `test_failsafe_sm`, `test_watchdog_manager`, `test_secoc`

**존재하지 않음**: `test_can_cdd`, `test_bms_component`

### Python (`security/`) — 현재 존재하는 것

| 파일 | 경로 |
|---|---|
| `secoc_module.py` | `security/` |
| `traffic_gen.py` | `attacks/` |
| `feature_extractor.py`, `rule_baseline.py`, `spec_detector.py`, `if_detector.py` | `ids/` |
| `run_eval.py` | `experiments/` |
| `measure_can_secoc.py` | `analysis/` |
| `test_secoc.py`, `test_ids_baseline.py` | `tests/` |
| `requirements.txt` | `security/` |

### Python — 앞으로 만들 것 (미구현)

| 파일 | 경로 | 단계 |
|---|---|---|
| `ids_alerter.py` | `ids/` | [M4](M4_IDS_공격_물리통합.md) |
| `realtime_ids.py` | `ids/` | [M4](M4_IDS_공격_물리통합.md) |
| `fuzzy_attack.py`, `flooding_attack.py` | `attacks/` | [M4](M4_IDS_공격_물리통합.md) |
| `replay_attack.py`, `spoofing_attack.py` | `attacks/` | [M5](M5_Ablation.md) |
| `run_ablation.py`, `summarize_ablation.py`, `analyze_roc.py` | `experiments/` | [M5](M5_Ablation.md) |
| `plot_ablation.py`, `plot_ekf.py` | `experiments/` | [M6](M6_문서_품질.md) |
| `verify_reproducibility.py` | `experiments/` | [M7](M7_최종검증_재현성.md) |
| `how_to_train.md` | `ids/` | [M7](M7_최종검증_재현성.md) |
| `test_ids_alerter.py` | `tests/` | [M4](M4_IDS_공격_물리통합.md) |

---

## 4. 최종 셀프 QA

### 코드

- [ ] `adaptive_ecu/`와 `security/`가 표준 구조로 존재한다
- [ ] Mock과 SocketCAN이 `CanDriver`로 교체 가능하다
- [ ] `0x100`, `0x101`, `0x102`, `0x103`, `0x200` 인코딩이 ICD와 일치한다
- [ ] 실행 인자 `--interface`, `--secoc`, `--sensor-mode`, `--profile`, `--key`가 동작한다
- [ ] SecOC 키가 코드·시험·문서·로그·커밋 어디에도 없다

### 시험 결과 기록

- [ ] TC-BSW-001~008
- [ ] TC-BMS-001~007
- [ ] TC-SEC-001~007
- [ ] TC-EXP-001~005
- [ ] TC-PERF-001~003
- [ ] IT-001~005

각 항목에 Pass / Fail / Skip과 근거를 남긴다. 실행하지 않은 것을 Pass로 적지 않는다.

### 실험·문서·데모

- [ ] `results/ablation.csv`, `ablation_summary.csv` 보관
- [ ] ROC·Ablation·EKF 그래프 생성
- [ ] SDD-ECU / TARA / ADR / TEST_PLAN 최신 상태
- [ ] `how_to_train.md`만으로 재현 가능
- [ ] 정상·공격 데모 영상 백업
- [ ] 합성 결과와 실측 결과를 문서 전반에서 구분 표기

---

## 5. 한 줄 실행 순서

```text
GitHub 인프라
-> M1 환경 / ICD 확정
-> M2 CAN CDD / Mock / 100ms 송신
-> M3 EKF / Fail-safe / Watchdog / SecOC
-> M4 IDS 평가 / 공격 / 0x200 / 물리 통합
-> M5 Ablation 1,200 시행
-> M6 문서 / 그래프 / Coverage
-> M7 재현성 / ICD 교차검토 / TC-PERF
-> M8 데모 / 발표 / v1.0.0
```

---

## 6. 부록 — 원본 계획의 시간 추정

아래는 `_archive/ECU.md` 부록 A의 추정치다. **근거가 기록되지 않은 추정이므로 일정 약속이 아니라 참고로만 쓴다.**

| 단계 | 추정 | 주요 산출물 |
|---|---|---|
| M1 | 16~20h | RPi4 환경, CAN loopback, 인터페이스 헤더, ICD·ADR 초안 |
| M2 | 29~32h | Mock, CAN CDD, Publisher, SensorSimulator, 프로파일 데이터 |
| M3 | 38~44h | EKF, Fail-safe, SecOC(Python+C++), Watchdog, 단위 시험 |
| M4 | 24~28h | IDS 평가, 공격, `0x200`, TARA |
| M5 | 37~42h | Ablation 1,200 시행, ROC, ADR 최종화 |
| M6 | 34~38h | 그래프, SDD-ECU, TARA, Coverage |
| M7 | 31~36h | 재현성, 보완 실험, 실험 보고서, 재현 문서 |
| M8 | 25~29h | 데모, 슬라이드, 보고서, 리허설 |

합계 약 234~269시간.
