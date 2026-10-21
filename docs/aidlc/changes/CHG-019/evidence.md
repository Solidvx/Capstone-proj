# CHG-019 검증 증거

검증일 2026-10-21. Windows 작업 트리와 WSL Ubuntu/Python 3.12/GCC 13 계열을 사용했다. 입력 기준은 [spec](spec.md)에 기록한다.

| 검사 | 결과 |
|---|---|
| 통합 전 Python | 기존 WSL `~/venvs/capstone-security`: `python -m pytest -p no:cacheprovider security/tests -q`, 97 passed |
| 통합 Python | 147 passed + 9 subtests passed (13.21s). 양쪽 security/tests 및 IVI Python 분석·인계 시험, [기계 기록](validation.json) 참조 |
| ECU CMake/CTest | OpenSSL 3.0.13, 기존 GTest prefix `tmp/adc-smoke-deps/install`, configure/build 및 17개 CTest 통과 |
| IVI CMake/CTest | 코어·시험용 비인증 수신기 9개 통과, SocketCAN 1개 skip |
| Qt 화면·실험 실행 파일 | 미실행: 환경의 Qt 6.4.2는 프로젝트 요구 Qt 6.8보다 낮음. CMake의 Qt 미탐색을 앱 빌드 성공으로 세지 않음 |
| 실제 CAN/vcan·장비 재시험 | 미실행: 준비된 vcan0 및 RPi 연결 없음 |
| 기존 최종 보고서 | 생성 표 4개/12조건/16실행/링크 74개 PASS. 최초 시도 1200/VALID1196/INVALID4 유지 |
| CLI smoke | 합성 24행 생성·집계, IDS/관측 하네스/live 하네스 `--help` 통과 |
| 문서 | 변경 문서 로컬 링크 933개 및 코드 펜스·충돌 표식 검사 통과 |
| 원본·산출물 보존 | inventory 2251파일·생성물61개·과거 분석기38개 해시 일치. 16실행 수신 대조와 기존 프레임 차이3개 예외 유지 |

재현 (저장소 루트, Linux 의존성 준비 후):

```sh
python -m pytest -p no:cacheprovider security/tests ivi_platform/test/test_period_analysis.py ivi_platform/test/test_pi_handoff.py -q
cmake -S adaptive_ecu -B adaptive_ecu/build -DECU_BUILD_TESTS=ON
cmake --build adaptive_ecu/build
ctest --test-dir adaptive_ecu/build --output-on-failure
cmake -S ivi_platform -B ivi_platform/build -DIVI_BUILD_TESTS=ON -DIVI_BUILD_EXPERIMENT_TOOLS=ON
cmake --build ivi_platform/build
ctest --test-dir ivi_platform/build --output-on-failure
python -X utf8 docs/development/reviews/experiment-evidence-audit-2026-10-04/verify_final_report.py
```

이번 WSL 빌드는 기존 의존성을 재사용하고 제품 `build/`와 구분한 `tmp/sync-20261021/{ecu,ivi}-build`에 생성했다. Qt 시험의 완료 판정은 앱 타깃과 `test_dashboard_*`가 실제 생성·실행됐는지 별도로 확인해야 한다.

초기 병합 시험에서 GitHub의 READY 모의 socket에 새 시각 필드가 없어 1개 실패했다. 실제 SocketCan의 `start_time/clock_offset_ns/idle_time` 계약을 모의 객체에 반영했다. 추가 회귀는 양쪽 manifest 경계·변조 입력 거부·FIFO/송신 압력 오류의 결합을 검사한다. 기존 시험 삭제나 합격 기준 완화는 하지 않았다.

증거 자료의 일부 줄 끝 공백·마지막 빈 줄은 원본 SHA256 보존 대상이다. 해당 경로만 Git whitespace 검사에서 제외하며 코드/새 문서는 일반 `git diff --check`를 적용한다. 원본 raw는 Git 제외이고 원격 저장소에 존재한다고 표시하지 않는다.

원격 게시: 통합 커밋 `50e2e5f`를 `chore/team-sync-20261021`에 push하고 [PR #26](https://github.com/Solidvx/Capstone-proj/pull/26)을 생성했다. 로컬 `develop`은 원격과 동일한 `644eb99`로 fast-forward했다. 통합 작업의 `develop` 병합과 상대방 Approve는 대기 중이다. `main`은 기존 릴리즈 기준을 유지했다.
