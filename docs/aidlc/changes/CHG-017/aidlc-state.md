# CHG-017 — 전체 계획 대조·Fail-safe 회귀·품질 실측

- 날짜: 2026-10-03, develop dirty worktree.
- 요청: 사용자 Pi 1~4번 수행 중 독립 작업 및 전체 진척/잔여 과정 보고.
- 반영: Fail-safe GTest 4개 추가, ECU/IVI/CICD 현황 정정, [전체 진행 보고](../../../development/reviews/전체계획_진행보고_20261003.md).
- 제품 ECU/IVI 동작·ICD·HAL·counter·키·CRITICAL latch 변경 없음. 기존 003 archive와 사용자 절차 보존.
- 상태: 이번 회귀시험·실측·보고 완료. 전체 M3~M8 인수 미완료 유지.

## 실행 증거

로컬 Lima Linux ARM64 VM `ivi-p4`, Ubuntu26.04/GCC·gcov15.2/GTest1.17. Raspberry Pi 접근 아님.

```bash
cmake -S adaptive_ecu -B /tmp/capstone-ecu-coverage-20261003-001 \
  -DCMAKE_BUILD_TYPE=Debug -DECU_BUILD_TESTS=ON -DENABLE_COVERAGE=ON
cmake --build /tmp/capstone-ecu-coverage-20261003-001 -j4
ctest --test-dir /tmp/capstone-ecu-coverage-20261003-001 --output-on-failure
cmake --build /tmp/capstone-ecu-asan-20261003-001 -j4
ASAN_OPTIONS=detect_leaks=1 ctest \
  --test-dir /tmp/capstone-ecu-asan-20261003-001 --output-on-failure
```

보강 후 coverage CTest16/16(0.34s), ASan16/16(0.42s) 통과. Fail-safe GTest2→6. 이전003 Release 결과는 CHG-016과 구분한다.

각 `.gcno`를 전부 찾아 고유 디렉토리에서 `gcov -b -j OBJECT.gcno` 실행, gzip JSON v2를 집계했다. 미실행 `.gcda` 부재는 gcov의 0회 계측으로 포함하고, exit code/JSON 부재/스키마 불일치는 실패 처리했다. 제품 `src/`, `include/`, `main.cpp`, `tools/`만 집계; test/system/generated는 제외. 번역단위 중복 `(file,line)`은 실행 여부의 합집합이다. 제품 cpp 목록과 계측 파일을 대조한 누락은 0개. Python/QML/IVI는 합산하지 않았다.

| 범위 | 보강 전 | 보강 후 | 목표 판정 |
|---|---|---|---|
| 전체 ECU 제품 라인 | 516/853=60.49% | 520/853=60.96% | ≥80% 미달 |
| Fail-safe 라인 | 30/35=85.71% | 34/35=97.14% | 별도 참고값 |
| Fail-safe 계측 분기 taken | 25/32=78.125% | 30/32=93.75% | 100% 미달 |

분기 executed와 taken-at-least-once를 혼동하지 않았다. GCC의 callback 예외 분기도 포함하며 임의 제외하지 않았다. 보강 후 미실행 분기는 `failsafe_sm.cpp:57`의 동일 상태 방어 true 경로와 `:65` callback throw 경로다. 계측 데이터는 동일 제품 소스에 대한 보강 전/후 실행이 누적돼 있다. 이번 회귀시험은 이전 경로도 그대로 실행했다. 최종 CI 게이트는 깨끗한 별도 빌드에서 재측정해야 한다.

## 원시 증거 위치와 SHA256

VM 내 보강 전 `/tmp/capstone-ecu-coverage-evidence-20261003-001/coverage.json` 및 번호별 gcov gzip JSON/실행 출력. 후 `/tmp/capstone-ecu-coverage-evidence-20261003-002/coverage.json`.

- 전 집계 SHA256: `859eb3c74a06fd701347e74d397fa03dda4c8bcd8ed0650589565d8ce1220f29`
- 후 집계 SHA256: `549fe3e479c49120f1b56a8b7218f34b145d2275b0a1926afe6ce04a557f66bc`
- 제품 `src/app/failsafe_sm.cpp`: `b14bd3af58b1d25685e934f6e7fc3aa56aebd9e491f22e4b86b26c477ae447fc`
- 보강 시험 `test/test_failsafe_sm.cpp`: `e95a761ca4bfa8695e2792b57be5dea8e24a2c38b2afbe1bd490b0b999dc6cdf`

주요 미실행 라인: main124, can_cdd70, linux_i2c_transport26, smoke tool61. 작은 단위시험 통과만으로 운용 경로의 품질 목표를 만족하지 않는다. cppcheck/lcov/gcovr는 VM에 없어 NOT_RUN; 0건/통과로 보고하지 않는다. 워치독 callback 로그만 존재하는 M3 구현 부채도 전체 보고에 명시했다.

최종 검사: 관련 문서5개 로컬 링크90개/코드펜스 검사 통과, `git diff --check` 통과, Fail-safe GTest6/6 재확인. 003 archive SHA256은 CHG-016의 `a9d8bbf85b27e6aaefb1e4b467d908c255a2ec67aa466751190d48fde66fdb16`과 동일하게 유지됐다.
