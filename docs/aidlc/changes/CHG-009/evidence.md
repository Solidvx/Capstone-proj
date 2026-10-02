# CHG-009 검증 증거

2026-10-03, Windows 작업 트리 `chore/ecu-m1-baseline`의 병합 커밋 `8e5e5d6`(부모 `f6013ed`, `origin/develop` `ba3c24b`)을 WSL2 Ubuntu x86_64에서 빌드·시험했다. RPi ARM64·물리 CAN 실행 증거가 아니다.

## develop 반영 확인

- `origin/develop` 최근 이력: #6 Qt 대시보드, #7 Linux vcan·T1~T4, #8 SecOC 무수신 만료(CHG-006), #9 Node A IDS(CHG-007).
- `git diff origin/feat/ecu-can-ids-merge origin/develop -- security/ docs/aidlc/changes/CHG-007/` 차이 없음.
- `git diff origin/feat/ivi-secoc-hardening-merge origin/develop -- ivi_platform/ docs/aidlc/changes/CHG-006/` 차이 없음.
- 원본 `feat/ecu-can-ids`(`3813f4b`)의 `security/`·CHG-007은 `develop`과 동일하다. 원본 `feat/ivi-secoc-hardening`(`081aa13`)은 `-merge` 이력에 포함되며, 이후 develop 병합과 stale·pending 타이머 일원화(`b6291db`, IVI 팀원)가 더해진 판본이 #8로 반영됐다. 원본의 `test_vehicle_data_service.cpp` 수정도 `develop`에 동일하게 있다.

## 병합

`git merge --no-ff origin/develop` 충돌은 `docs/aidlc/changes/README.md`, `docs/aidlc/structure/document-map.md`, `docs/aidlc/structure/path-map.csv` 3건이며 양측 항목을 모두 유지했다. 해결 후 `git diff --check` 통과, 두 Markdown의 상대 링크 83개 모두 존재, `path-map.csv` 264행 중 add/preserve 대상 누락 0건. 커밋 `8e5e5d6`을 `origin/chore/ecu-m1-baseline`에 푸시했다. 푸시 시점 `develop` 대비 앞섬 3, 뒤처짐 0.

## 시험

| 영역 | 명령 | 결과 |
|---|---|---|
| ECU | `cmake -S adaptive_ecu -B tmp/stage0-ecu-build -DECU_BUILD_TESTS=ON -DCMAKE_PREFIX_PATH=$PWD/tmp/adc-smoke-deps/install`, build, `ctest` | 14/14 통과 |
| IVI core | `cmake -S ivi_platform -B tmp/stage0-ivi-build -DIVI_BUILD_TESTS=ON -DIVI_BUILD_QT_APP=OFF`, build, `ctest` | 8/9 통과. `test_socketcan_receiver` 실패 |
| IVI Qt | 위 명령에서 `-DIVI_BUILD_QT_APP=OFF` 없이 구성 | 구성 실패 |
| Python | `python -m pytest security/tests -v -p no:cacheprovider` | 24/24 통과 |
| 합성 IDS 평가 | `python security/experiments/run_eval.py` | 정상 종료. Isolation Forest ROC-AUC 0.942(합성 트래픽 참고값) |

환경: GNU C++ 13, CMake 3.28.3, Qt 6.4.2(apt), GoogleTest는 CHG-008에서 `tmp/adc-smoke-deps`에 설치한 것. Python 3.12.3 가상환경을 저장소 밖 WSL 홈(`~/venvs/capstone-security`)에 만들어 `security/requirements.txt`를 설치했다(numpy 2.5.3, scikit-learn 1.9.1, pandas 3.0.6, python-can 4.6.1, pytest 9.1.1). 빌드 산출물은 Git 제외 경로 `tmp/stage0-*`에 있다.

## 실패·미검증과 원인

- `test_socketcan_receiver`: `FAIL ... failed to open sender on vcan0`. 이 WSL 커널에는 `vcan` 모듈이 없다(`modinfo vcan` 없음). 시험은 `ENODEV`·`ENXIO`·`EPERM`만 SKIP(77)으로 분류하므로 CAN 소켓 자체를 쓸 수 없는 환경을 실패로 보고한다. 제품 결함으로 판정하지 않았으며 vcan이 있는 Linux에서 재실행이 필요하다.
- IVI Qt: `ivi_platform/CMakeLists.txt`의 `qt_policy(SET QTP0001 NEW)`·`qt_policy(SET QTP0004 NEW)`가 Qt 6.4에서 `Unknown CMake command "qt_policy"`로 실패한다. `find_package(Qt6 6.2 ...)`는 6.2 이상을 허용하므로 선언과 실제 요구 버전이 다르다. 배포 브랜치는 Ubuntu 22.04와 Debian 13을 지원 대상으로 둔다. IVI 담당과 협의 중이며 이 기록에서 수정하지 않았다.
- RPi 실장비, 물리 CAN, Qt 화면은 이 단계의 시험 범위가 아니다.
