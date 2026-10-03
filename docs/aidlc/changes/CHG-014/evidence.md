# CHG-014 검증 증거

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

## 검증 범위와 남은 인수

새 Python 시험은 MAC 실패 후 counter·pending 보존, 만료/replay/frame flags, 정상 오탐 분모·무수신 timer, 실제 캡처 쌍 선택, MSG_CONFIRM 구분 모의 시험, 송신 실패·프로세스 회수·전체 실행기 성공/실패 원장, 중복 집계·환경 혼합 방지, ADC 원시값 보존을 검사했다. 모의 transport 시험을 vcan 통과로 표기하지 않는다.

- RPi vcan pilot, 물리 1,200 유효 시행, 부하 ≥50%, 물리 정상 FPR·IF 성능은 사용자 실행 대기.
- 실제 드라이버 own echo·캡처 손실·시각 오차·지속 송신률은 pilot 인수 전 미검증. 앱 수신 시각을 정확한 wire 시각으로 간주하지 않는다.
- IVI 시험 모드·제품 수용/거부/화면 로그는 사용자 지시에 따라 IVI 담당자가 구현한다. Python 참조 판정은 제품 인수를 대체하지 않는다.
- ADC 가운데·상단 1,000회, IT-001~005와 T1~T4 실측은 로그 대기.
- IF 추가 합성 오탐 FAIL을 보존한다. 정상 실측 학습/독립 평가 뒤 필요하면 별도 선정 자료로 임계를 검토한다.

실행은 [플레이북](../../../development/playbooks/live-security-validation.md), IVI 경계는 [인계](../../../development/security/IVI_실험_인계.md)를 따른다.
