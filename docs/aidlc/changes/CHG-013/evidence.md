# CHG-013 검증 증거

2026-10-03, macOS arm64, 브랜치 `develop`, 기준 commit `6bf9688`.

## 로컬 검증

```bash
python3 -m unittest security.tests.test_attack_tools security.tests.test_runtime_ids -v
PYTHONPYCACHEPREFIX=/tmp/capstone-pycache python3 -m compileall -q security
python3 -m security.attack_simulator --help
python3 -m security.capture_normal --help
python3 -m security.secoc_tamper_fixture --help
python3 -m unittest ivi_platform.test.test_period_analysis -v
cmake -S adaptive_ecu -B /tmp/capstone-ecu-build-no-tests -DECU_BUILD_TESTS=OFF
cmake --build /tmp/capstone-ecu-build-no-tests --target adaptive_ecu -j2
```

- 신규 공격·변조 및 기존 runtime 회귀 15건, 주기 정규화·분석 회귀 4건 통과.
- 4종 frame 형식·결정적 fuzzy seed·replay 동일 payload·spoof SOC raw 200·flood ID/payload를 확인했다.
- 물리 인터페이스 명시 확인, 10초·4,000fps 상한, replay payload 검사, 키/counter 경계를 확인했다.
- IT-004 fixture의 bad MAC counter가 정상 복구에서 재사용되고 정상 MAC이 유효함을 독립 계산했다.
- cooldown 중 먼저 발생한 Fuzzy 증상 뒤 Flooding 분류가 유실되지 않고 bounded pending 1개로 전송 대기하는 회귀를 추가했다.
- Python 전체 문법 검사와 세 CLI help가 통과했다.
- 주기 분석은 90/110ms 포함 경계 PASS, 단일 110.1ms 이탈 FAIL, 짧거나 손상된 캡처 INVALID, 상대/verbose/역행 timestamp 거부를 확인했다.
- 결정적 Fail-safe profile을 독립 계산해 310표본, WARNING cycle 99(SOC 19.9249%), CRITICAL cycle 228(SOC 4.98769%), 전이 간격 12.9초, manifest SHA-256 일치를 확인했다.
- `ECU_BUILD_TESTS=OFF`의 제품 `adaptive_ecu` target은 현재 macOS/OpenSSL 환경에서 구성·컴파일·링크를 통과했다.

## 환경 제한

- 시스템 Python에 pytest와 scikit-learn이 없어 기존 실제 IF 학습 CLI 시험 1건은 이 환경에서 실행하지 못했다. 신규 시험은 표준 `unittest`만으로 통과했다.
- C++ Fail-safe 회귀는 로컬 CMake에 GTest가 없어 구성 단계에서 실행하지 못했다. 같은 CSV·모델 계산은 독립 Python 검사로 확인했지만 대상 Linux의 C++ 시험을 대신하지 않는다.
- Linux SocketCAN이 없는 macOS이므로 실제 `vcan`/`can0` 송수신, 물리 부하, `0x200` IVI 표시, 탐지 지연은 미실행이다.
