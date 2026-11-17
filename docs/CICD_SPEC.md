> **문서명**: CI/CD Pipeline Specification (CICD_SPEC)
> **최종 검토**: 2026-11-14 · **상태**: native 품질과 별도 ARM64 cross/QEMU job, 읽기 전용 제품 health·로컬 release/rollback 도구 구현. 원격 CI·실제 Pi 자동 배포 인수는 미완료. [후속 증거](aidlc/changes/CHG-029/aidlc-state.md)
> **원천**: [SRS](SRS.md) FR-CI-001~006/NFR-QA, [TEST_PLAN](TEST_PLAN.md) TC-CI-001~006, ADR-006/007
> **2026-11-17 보완**: [PR #33 CI 조사·수정](aidlc/changes/CHG-030/ci-fix-20261117.md). native 시험/health/coverage는 전용 비관리자 UID로 실행하여 권한 기반 저장 장애를 실제 주입한다. 두 원격 native 실패를 재현했고 로컬 수정 검증은 통과했으며 새 원격 결과 인수는 별도다. 아래의 과거 미달·미실행 기록과 구분한다.

# 1. 개요

## 1.1. 목적

Node A ECU와 Node B C++/Qt IVI의 정적 분석→ARM64 빌드→시험/커버리지→대상 배포를 자동화한다. Git 원격과 `main`·`develop` 및 native 품질 기준선 `quality.yml`이 존재한다. 아래 전체 인수 목표를 완료한 상태는 아니며, 자동 배포는 아직 없다.

## 1.2. 파이프라인 4단계 요약

Stage 1 정적 분석 → Stage 2 ARM64 빌드 → Stage 3 시험·커버리지 → Stage 4 main push 배포·health·rollback. 앞 단계 실패 시 후속 단계는 실행하지 않는다. PR에서는 배포와 배포 secrets 사용을 허용하지 않는다.

## 1.3. 참조 파일 목록

| 경로 | 상태·역할 |
|---|---|
| `adaptive_ecu/CMakeLists.txt` | 존재. 실제 executable `adaptive_ecu`, 시험 옵션 `ECU_BUILD_TESTS` |
| `.github/workflows/quality.yml` | native x86/ARM64 빌드·ECU28/IVI제품44 strict CTest·Python·cppcheck·coverage 연결. 보호 사건 제품 시험 추가 후 목록이며 원격 실행 미검증 |
| `Dockerfile.arm64`, `toolchain-aarch64.cmake` | 존재. x86-64 compiler/Qt host tools + ARM64 OpenSSL/GTest/Qt·명시 QEMU. `tools/quality/cross_build.py`가 양측 ELF/시험 검사 |
| `scripts/health_check.sh`, `tools/deployment/health.py` | 존재. 일반 IVI 프로세스·artifact·열고 있는 비공개 로그·인증된 새 ECU 데이터 대조 |
| `tools/deployment/release.py` | 존재. 명시적 hook·상한의 로컬 staging/원자 전환·이전 버전 검증 rollback. 실제 대상/계정/서비스/전달 workflow는 미확정 |
| `ivi_platform/` | Qt/CMake·CTest·수동 Pi 빌드/배포 스크립트 존재. GitHub workflow 연결은 있으나 원격 실행·자동 health/rollback 인수는 남음 |

# 2. GitHub Actions 파이프라인 상세

현행 full-product/coverage 기준선은 Debian trixie 컨테이너의 native 빌드다. 별도 cross-arm64 job은 x86-64 compiler host에서 ARM64 두 제품을 만들고 QEMU로 비장비 C++ 시험을 실행한다. native ARM64 실행만으로 cross 인수를 주장하지 않는다. 컨테이너 tag·패키지 공급은 아직 불변 digest/version lock이 아니며 설치 버전을 artifact에 남긴다. Actions 두 개는 조회한 SHA로 고정했다. Codecov, 실제 배포, secrets, 저장소 보호 설정은 연결하지 않았다. coverage 부족은 `continue-on-error`로 숨기지 않으며 현재 로컬 수치상 해당 게이트는 실패한다.

2026-11-11 제품 통합 연결: job 컨테이너의 NET_ADMIN으로 해당 가상 네트워크에 vcan0을 새로 만들고 kind/UP을 읽기 전용 health로 확인한다. host network·privileged 컨테이너·실물 장치 mount는 사용하지 않는다. runner 커널의 vcan 지원/모듈과 SocketCAN이 필요하다. 생성/권한/지원 실패 시 기본 시험으로 우회하거나 skip을 합격으로 만들지 않는다. ECU28개(실제 SOC CSV 평가 추가)와 IVI기본21+실제 제품23개(현행CSV 계측/계산·CAN 수신 성공 복구 회귀 포함)를 정확히 요구한다. 로컬 도구의 --allow-no-vcan은 별도 개발용이며 이 workflow에서는 사용하지 않는다.

ECU가 먼저 빌드되고 IVI CMake에 실제 adaptive_ecu 절대 경로를 넘겨 제품 시험을 등록한다. ECU/IVI/Python 시험 단계와 양측 coverage는 build 성공을 전제로 독립 실행한다. 앞 시험 실패가 뒤 시험/보고서 생성을 숨기지 않고 job은 실패를 유지한다. JUnit·gcov/요약·개인 임시 키를 보존하지 않는 제품 시험 원본은 artifact 대상이다. GitHub/Docker/runner 커널에서의 실제 인수는 로컬 Linux 프로필 통과와 별도로 필요하다.

컨테이너 옵션과 조건식은 [GitHub workflow 문법](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax), 실패 뒤 독립 단계 조건은 [상태 검사 함수](https://docs.github.com/en/actions/reference/workflows-and-actions/expressions#status-check-functions)를 따른다. run 단계의 기본 셸은 [컨테이너 실행 안내](https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/run-jobs-in-a-container)에 따라 sh이며 bash가 필요한 coverage 단계만 명시한다.

명령·작성 절차의 단일 관리 위치는 [IVI CI 참조 §1](../plan/detail/ivi/ref_CI파이프라인_명령모음.md#1-ci-구현-명세--단일-관리-위치)다. 본 문서는 공식 인수 명세를 관리한다. 전체 YAML/Docker/CMake를 양쪽에 중복 유지하지 않는다. 구현 후 실행 정본은 실제 파일이다.

## 2.1. 트리거 조건 (FR-CI-001)

main/develop push·PR에서 Stage 1~3을 시작한다. 배포는 main push이며 동일 revision의 선행 단계가 통과해야 한다. 브랜치 보호·리뷰 정책(NFR-QA-004)을 실제 저장소에서 설정하고 우회 차단을 시험한다.

## 2.2. Stage 1 — 정적 분석 (FR-CI-002)

cppcheck Error 0건을 검사한다. SRS의 Critical/Error 표현을 실제 도구 severity에 매핑해 버전·대상·억제 사유를 남긴다. `--enable=all --error-exitcode=1`이 Error만 실패시킨다고 가정하지 않는다. 경고/스타일은 보고하고 Error 게이트는 구조화된 출력과 종료 코드로 구분한다. 분석 대상 0개·도구 실행 실패·파싱 실패는 실패다. 의도적인 Error 주입과 Warning만 있는 사례로 차단 정책을 검증한다.

## 2.3. Stage 2 — ARM64 크로스컴파일 빌드 (FR-CI-003)

Docker의 x86-64 compiler host에서 실제 CMake 타겟 `adaptive_ecu`와 `ivi_dashboard`를 ARM64로 빌드한다. ARM64 Qt 라이브러리와 같은 Debian 배포 버전의 x86-64 Qt host tools를 구분한다. 패키지 설치 목록과 image inspect를 보존하며 아직 불변 digest/version pin 전체 인수는 아니다. `ecu_node_a`라는 없는 타겟명을 사용하지 않는다. compiler·sysroot·OpenSSL·GoogleTest의 ARM64 ABI를 확인하고 ELF 아키텍처·소스 revision·artifact hash를 보존한다.

각 CI job은 독립 실행 환경이다. 앞 job에서 로컬로 만든 Docker 이미지를 다음 job에 존재한다고 가정하지 않는다. 고정 digest로 가져오거나 동일 정의로 재빌드하거나 save/load artifact 전달을 구현하고 검증한다.

## 2.4. Stage 3 — 단위 테스트 + 커버리지 (FR-CI-004)

`ECU_BUILD_TESTS=ON`으로 구성한다. ECU CMake에는 `ENABLE_COVERAGE`가 존재하며 로컬 GCC 계측 시험을 실행했다. 옵션 존재만으로 CI 게이트 통과를 뜻하지 않으며 전체 분모·목표 충족은 별도 검증한다. 호스트·ARM64 계측 빌드 디렉토리를 분리한다. `/workspace`에서 생성한 CTest는 동일 마운트 경로의 컨테이너에서 실행한다. ARM64 dynamic loader·라이브러리와 emulator/binfmt를 실제 시험 실행으로 확인한다.

| 게이트 | 합격 조건 | 무효/실패 조건 |
|---|---|---|
| 시험 | 기대 이름·개수 일치, 실행 실패 0 | 시험 0개, timeout, 누락, 실행 불가 |
| C++ Line | 실행 가능 제품 소스 줄 ≥80% | 분모 0, 누락·빈 lcov, 비유한 숫자, 파싱 실패 |
| Fail-safe Branch | `failsafe_sm.cpp`의 계측 분기 100% | BRDA/분기 분모 누락, 일부 분기 미계측 |
| 결과 게시 | 원시 보고서·환경·제외 목록·요약 및 Codecov | 업로드 성공으로 실제 게이트 통과 대체 |

동일 compiler 버전의 gcov와 lcov branch 수집 옵션을 확인한다. source/data mismatch를 무시하지 않는다. 미실행 소스도 분모에서 사라지지 않게 초기 계측 데이터를 병합한다. Python/Qt QML 결과를 ECU C++ coverage에 합산하지 않는다. IVI C++ coverage도 대상·분모를 별도로 보고한다. TC-CI-004와 TC-BMS-004를 연결한다.

## 2.5. Stage 4 — RPi4 자동 배포 + Health Check (FR-CI-005, FR-CI-006)

검증된 동일 revision/hash artifact를 staging 경로로 전달하고 설정·profile·키 접근 조건을 확인한 뒤 전환한다. 정상 데이터 확인 실패 시 이전 artifact·관련 설정으로 복구하고 결과를 기록한다. 구현 절차는 [IVI M4 §3.4~3.7](../plan/detail/ivi/M4_대시보드_Alert_배포.md#34-systemd-유닛)을 따른다. 서명/세션 상태·counter를 임의 초기화하는 rollback을 정상 복구로 보지 않는다.

# 3. Docker 크로스컴파일 환경

## 3.1. Dockerfile.arm64

구현 파일. 소스/키를 이미지에 COPY하지 않으며 `.dockerignore`는 recipe만 build context에 허용한다. 베이스 이미지·설치 패키지를 실행 증거로 기록하고 x86 compiler 도구와 ARM64 타겟 라이브러리를 구분한다. `dpkg --add-architecture arm64` 한 줄만으로 필요한 패키지 공급이 보장되지 않는다. 새 checkout에서 컨테이너 빌드·의존성 탐색·시험을 재현해야 한다.

## 3.2. toolchain-aarch64.cmake

구현 파일. aarch64-linux-gnu compiler·target OpenSSL/GTest/Qt 경로와 CTest의 qemu-aarch64 -L / 접두사를 지정한다. 제품 및 선택한 모든 C++ 시험의 ELF machine183을 검사하고 host compiler machine62와 구분한다.

## 3.3. adaptive_ecu/CMakeLists.txt 필수 옵션

기존 CMake를 별도 골격으로 덮어쓰지 않는다. 실제 옵션 `ECU_BUILD_TESTS`·`ENABLE_COVERAGE`와 타겟을 보존한다. 현재 로컬 재현 명령은 [AGENTS 검증 기준](../AGENTS.md#6-verification-baseline)을 따른다. 계측 활성화·테스트 이름·누락 소스와 실패 전파를 검증한 뒤 CI에 연결한다.

# 4. QEMU user-mode 에뮬레이션 상세 (ADR-006)

## 4.1. 동작 원리

ARM64 사용자 프로그램을 지정 emulator/runtime으로 실행하는 별도 cross job을 구현했다. 정확한 전체 CTest 등록28/21을 확인한 뒤 native/vcan 제품·Python 통합은 native job에 남기고 비장비 C++ ECU24/IVI18을 에뮬레이션한다. failure/error/skip/누락/중복은 실패이며 제외 이유를 result.json에 보존한다. QEMU 설치, binfmt 등록, 동적 runtime 공급은 각각 확인한다. 컨테이너 mount/path와 CTest 명령이 실제 실행 가능해야 한다.

## 4.2. QEMU 에뮬레이션 한계 및 처리 방침

CI에서 Mock/가상 입력 단위시험과 실제 장비 시험을 구분한다. QEMU user-mode 자체가 MCP2515/ADS1115 실장비를 제공하지 않는다. PF_CAN 또는 `/dev/i2c-*`가 모든 QEMU 환경에서 원천 불가능하다고 일반화하지 않는다. 이 계획의 CI에는 해당 장비·드라이버·권한을 제공하지 않으므로 실장비 시험을 별도 실행한다. Mock 성공은 물리 CAN·ADC·실시간 성능의 증거가 아니다.

# 5. GitHub Secrets 관리

## 5.1. 필요한 Secrets 목록

배포 SSH 개인키, 대상 호스트, 검증된 호스트 키, Codecov 토큰은 승인된 비밀 저장소에서 공급한다. 문서에는 값이나 실제 장비 주소를 넣지 않는다. 네트워크 경로·계정 권한을 확인하고 PR에는 배포 secrets를 노출하지 않는다. 임의 `ssh-keyscan` 결과만 신뢰하여 대상 인증을 대체하지 않는다.

## 5.2. RPi4 배포 계정 설정

배포 계정과 ECU 서비스 실행 계정을 구분한다. [IVI M4](../plan/detail/ivi/M4_대시보드_Alert_배포.md)의 과거 계획은 deploy로 전달, root 서비스로 ECU 실행이다. 현재 template 서비스/감독 경계와 차이가 있어 실제 운영 정책 확인이 필요하다. 파일 소유·실행·profile 읽기·키 읽기 권한과 제한된 서비스 관리/전환 권한을 실제 대상에서 검증한다. sudo 그룹 전체 권한을 관례로 추가하지 않는다.

# 6. Health Check 스크립트

`scripts/health_check.sh`와 `tools/deployment/health.py`는 구현됐다. [배포 안전 절차](development/playbooks/deployment-safety.md)에 실제 입력/증거·한계가 있다. 서비스 active 외에 배포 hash/설정, 새 CAN/인증 데이터, 오류·stale 상태, 요구된 IVI 연결을 확인하고 실패 코드를 반환한다. 배터리 보호 상태 자체를 프로그램 장애로 판단하거나 초기화하지 않는다. 검사 기한·재시도 값은 구현/측정 근거를 남긴다. 이전 5회×3초 골격을 승인된 상한으로 취급하지 않는다. 키 누락·프로세스 생존하나 송신 정지·버전 불일치·rollback 실패를 음성 시험에 포함한다.

# 7. ecu-node-a.service systemd 유닛

과거 Node A 설계 파일명은 `/etc/systemd/system/ecu-node-a.service`다. 현재 구현에는 `adaptive_ecu/service/capstone-ecu@.service`와 별도 감독자의 fresh/resume 정책이 있으므로 동일한 설치 서비스라고 가정하지 않는다. 실제 계정/서비스 운영 인수 전까지 [IVI M4 §3.4](../plan/detail/ivi/M4_대시보드_Alert_배포.md#34-systemd-유닛)의 과거 root 예시로 현재 정책을 덮어쓰지 않는다. Node B Qt 앱에는 별도 systemd 서비스/그래픽 세션 정책을 정의하고 이 Node A 유닛을 적용하지 않는다. 서비스 재기동·완료 heartbeat·CAN 재개를 확인하며 SecOC counter/세션 복구는 별도 인수한다.

# 8. 요구사항 추적 매트릭스

| 요구 | 설계·계획 | 공식 검증 |
|---|---|---|
| FR-CI-001 | §2.1 / IVI M1 | TC-CI-001 |
| FR-CI-002, NFR-QA-003 | §2.2 / IVI M1 | TC-CI-002 |
| FR-CI-003 | §2.3·§3 / IVI M2~M3 | TC-CI-003 |
| FR-CI-004, NFR-QA-001 | §2.4 / IVI M3·M6 | TC-CI-004 |
| NFR-QA-002 | §2.4 / ECU M3·IVI M6 | TC-BMS-004, TC-CI-004 |
| NFR-QA-004 | §2.1 / 공동 규약·IVI M7 | PR 리뷰·보호 규칙 프로세스 검증 |
| FR-CI-005 | §2.5·§7 / IVI M4 | TC-CI-005 |
| FR-CI-006 | §6 / IVI M4·M7 | TC-CI-006 |

# 9. 변경 이력

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|-----------|--------|
| v1.0 | 2026-03-15 | 초안 작성 — 4단계 파이프라인, Docker 환경, QEMU 에뮬레이션, 배포 절차 전체 | 팀원B |
| v1.1 | 2026-05-09 | Dockerfile.arm64 ARM64 OpenSSL 크로스컴파일 수정 (`dpkg --add-architecture arm64` + `libssl-dev:arm64`), 참조 문서 버전 SRS v1.3 반영 | 팀원B |
| v1.2 | 2026-05-09 | GoogleTest ARM64 빌드 시 `CMAKE_INSTALL_PREFIX=/usr/aarch64-linux-gnu` 추가 (find_package 경로 수정), SRS v1.3→v1.4 반영 | 팀원B |


### 커버리지 지표 확정 — S-8=B

S-8=B로 공식 기준을 C++ 실행 가능 소스 줄 커버리지 80% 이상으로 변경했다. lcov lines 보고와 라벨을 Line으로 통일하며 문장 커버리지로 부르지 않는다. 현재 CI 구현은 없으며 본문은 예정 명세다. Fail-safe Branch 100%는 별도 기준으로 유지한다. 시험 0개·빈 보고서·측정 불가·파싱 실패는 합격이 아니다. C++/Python 수치는 별도 보고하고 계측 대상·제외 목록·도구 버전을 증거로 남긴다.


2026-09-08: 오래된 전체 실행 골격을 공식 인수 명세와 단일 plan 정본 링크로 대체했다. 바이너리/옵션·job 이미지·CTest 경로·coverage 무효 처리·배포 권한/health 차이를 정정했다. 제품 CI는 여전히 미구현이다.
