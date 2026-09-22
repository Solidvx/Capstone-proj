# P1 빌드·시험 증거

> 실행일: 2026-09-22
> 호스트: macOS Darwin arm64
> 컴파일러: AppleClang 21.0.0.21000101
> CMake: 4.4.3
> OpenSSL: Homebrew `openssl@3` 3.6.4

## Debug

```bash
cmake -S ivi_platform -B ivi_platform/build-debug \
  -DCMAKE_BUILD_TYPE=Debug \
  -DIVI_BUILD_QT_APP=OFF \
  -DOPENSSL_ROOT_DIR=/opt/homebrew/opt/openssl@3
cmake --build ivi_platform/build-debug --parallel
ctest --test-dir ivi_platform/build-debug --output-on-failure
```

결과: `test_can_parser`, `test_secoc_verifier`, `test_vehicle_data_service` **3/3 통과**, 총 1.21초.

## Release

```bash
cmake -S ivi_platform -B ivi_platform/build-release \
  -DCMAKE_BUILD_TYPE=Release \
  -DIVI_BUILD_QT_APP=OFF \
  -DOPENSSL_ROOT_DIR=/opt/homebrew/opt/openssl@3
cmake --build ivi_platform/build-release --parallel
ctest --test-dir ivi_platform/build-release --output-on-failure
```

결과: 같은 시험 **3/3 통과**, 총 1.03초. 시험은 `assert`에 의존하지 않아 `NDEBUG` Release에서도 실제 검사를 수행한다.

## 스크립트 점검

- `PYTHONPYCACHEPREFIX=/tmp/ivi-pycache python3 -m py_compile ...`: 송신·계측 스크립트 문법 통과.
- 두 개의 비음수 표본으로 `measure_latency.py` 입출력 형식 확인: `samples=2`, 평균 `0.062ms`, p95/p99/최대 `0.075ms`.
- 위 값은 도구 smoke test용 합성 입력이며 IVI 성능 측정값이 아니다.
- `check_qt_ivi_env.sh`: C++와 CMake 확인, Qt 6 미설치, Darwin의 SocketCAN 미지원 표시.
- AppleClang `-Wall -Wextra -Wpedantic -Werror`로 Debug/Release core 시험과 비-Linux receiver stub을 별도 컴파일했고 모두 통과했다.
- 기본 `IVI_BUILD_QT_APP=ON` 구성에서도 Qt 부재를 감지해 core와 시험만 정상 구성·빌드하고 3/3 통과했다.

## 미실행

- Qt 6 앱 빌드와 QML 화면 시험: 호스트에 Qt 6 도구가 없다.
- Linux `vcan0`/SocketCAN 수신 시험: 현재 호스트가 macOS다.
- RPi4 `can0`, Node A 물리 통합, T1~T4 성능: 장비와 Linux 대상 환경에서 P4~P5로 수행한다.
