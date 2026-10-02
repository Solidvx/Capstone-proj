# CHG-008 검증 증거

2026-09-28, Windows 작업 트리 `chore/ecu-m1-baseline` (시작 f289395)의 변경분을 WSL Linux x86_64에서 빌드했다. RPi ARM64 실행 증거가 아니다.

## 환경과 명령

- GNU C++ 13.3.0, CMake 3.28, OpenSSL 3.0.13.
- GoogleTest 1.16.0: 공식 GitHub 태그를 `tmp/adc-smoke-deps`에 다운로드·빌드·설치. 시스템 패키지 변경 없음.
- 최초 시도는 GTest 미설치로 설정 실패. 의존성 준비 요청은 한 번 자동 승인 검토 사용량 제한으로 미실행됐고 사용자 재개 후 승인되어 정상 실행됐다.

```bash
cmake -S adaptive_ecu -B tmp/adc-smoke-build -DECU_BUILD_TESTS=ON -DCMAKE_PREFIX_PATH="$PWD/tmp/adc-smoke-deps/install"
cmake --build tmp/adc-smoke-build -j2
ctest --test-dir tmp/adc-smoke-build --output-on-failure
```

결과: 진단 도구와 기존 ECU 실행 파일 빌드 성공. CTest 14/14 통과, 총 0.75초. 기존 13개 시험 및 추가 취득 시험을 포함한다.

최종 재빌드 후 `test_ads1115_sample`의 5개 세부 시험 통과, `--help` 정상 종료, `--i2c-device /dev/i2c-does-not-exist`가 오류 메시지와 종료 코드 2를 반환함을 확인했다. 문서 상대 링크·코드 펜스·`git diff --check` 및 전달 ZIP 5개 항목의 원본 바이트 일치를 확인했다. ZIP SHA-256: `1855ca8d84ee6f80815b6804fe9dad404264da1049535595fa6023e4ecba41dd`.

추가 시험 범위: raw 0/13200/26400 → 팩 30/36/42V 및 기존 CAN 인코딩, I/O·잘못된 설정·범위 오류, 20ms 늦은 결과 폐기·재개, 변환 미완료 만료·재개, 초기/오류 후 3회 연속 정상 인수. 기존 gate·품질·레지스터 회귀 시험도 통과했다.

## 미검증 및 인수 경계

- Linux I²C ioctl 코드의 컴파일만 확인했으며 실제 ADS1115/ARM64 실행은 사용자 시험 대기.
- 이번 도구의 물리 CAN/Qt, 실제 100ms 주기·20ms 인수 비율·지연 실측은 아직 없다.
- 기존 대화의 ADC Python·모의 BMS Qt 성공은 새 도구 성공 증거로 재사용하지 않는다.
- 센서 오류 시 ECU 진단 무송신·복구 정책을 단위로 검증했으며, 실제 버스의 오류 주입·복구는 수행하지 않았다.
- 제품의 비동기 취득·품질 byte 7 전환·SecOC·Fail-safe·Watchdog 통합은 이 진단의 범위 밖이며 미완료.
