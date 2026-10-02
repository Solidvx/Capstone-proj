# CHG-012 검증 증거

2026-10-03, 브랜치 `fix/secoc-counter-per-id`(기준 `develop` `919db40`), WSL2 Ubuntu x86_64.

## 발견 근거

CHG-011 증거 §3.2·§5(`docs/aidlc/changes/CHG-011/evidence.md`, 별도 PR): ECU RPi `vcan0`에서 두 `0x103`의 counter가 0x4A→0x5F로 증가했다. 그 사이 `0x102`가 송신됐기 때문이다.

## 시험

```bash
cmake -S adaptive_ecu -B tmp/secoc-ecu-build -DECU_BUILD_TESTS=ON -DCMAKE_BUILD_TYPE=Release \
  "-DCMAKE_CXX_FLAGS=-Wall -Wextra -Wpedantic -Werror" -DCMAKE_PREFIX_PATH=$PWD/tmp/adc-smoke-deps/install
cmake --build tmp/secoc-ecu-build -j4
ctest --test-dir tmp/secoc-ecu-build
python -m pytest security/tests -q -p no:cacheprovider
```

- ECU: 경고 없이 빌드, CTest 14/14 통과. `test_secoc` 9건 중 신규 `CountersAreIndependentPerAuthenticatedStream`은 두 `0x103` 인증 사이에 `0x102` 150회를 넣고 두 번째 `0x103` counter가 1이며 수락되는지 확인한다.
- Python: pytest 25/25 통과(신규 `test_counters_are_independent_per_authenticated_stream` 포함). 기존 dummy-key 경계 벡터와 counter 0 벡터(`D0DDFC05`)는 그대로 통과했다.
- 회귀 확인: Python 모듈만 변경 전으로 되돌리면 신규 시험이 두 번째 `0x103` counter(1이 아님)에서 실패하고, 복원하면 통과한다.

## 미실행

- ECU RPi와 IVI 실장비에서 10초 넘게 간격을 둔 두 Fail-safe 이벤트의 IVI 수락(IT-002 단계).
- IVI·IDS 코드는 바꾸지 않았으므로 해당 시험은 재실행하지 않았다.
