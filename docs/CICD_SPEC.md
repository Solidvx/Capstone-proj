> **문서명**: CI/CD Pipeline Specification (CICD_SPEC)
> **최종 검토**: 2026-10-03 · **상태**: CI 예정 명세. GitHub workflow·Docker ARM64·cross toolchain은 없으나 IVI 제품/수동 배포 스크립트와 ECU 계측 옵션은 존재한다. [실행 현황](development/reviews/전체계획_진행보고_20261003.md)
> **원천**: [SRS](SRS.md) FR-CI-001~006/NFR-QA, [TEST_PLAN](TEST_PLAN.md) TC-CI-001~006, ADR-006/007

# 1. 개요

## 1.1. 목적

Node A ECU와 Node B C++/Qt IVI의 정적 분석→ARM64 빌드→시험/커버리지→대상 배포를 자동화한다. Git 원격과 `main`·`develop`은 존재하지만 `.github/` workflow와 배포 자동화는 아직 없다.

## 1.2. 파이프라인 4단계 요약

Stage 1 정적 분석 → Stage 2 ARM64 빌드 → Stage 3 시험·커버리지 → Stage 4 main push 배포·health·rollback. 앞 단계 실패 시 후속 단계는 실행하지 않는다. PR에서는 배포와 배포 secrets 사용을 허용하지 않는다.

## 1.3. 참조 파일 목록

| 경로 | 상태·역할 |
|---|---|
| `adaptive_ecu/CMakeLists.txt` | 존재. 실제 executable `adaptive_ecu`, 시험 옵션 `ECU_BUILD_TESTS` |
| `.github/workflows/ci.yml` | 예정. 이벤트·jobs·품질 게이트 |
| `Dockerfile.arm64`, `toolchain-aarch64.cmake` | 예정. 대상 compiler/runtime/의존성 |
| `scripts/health_check.sh` | 예정. Node A 정상 데이터 확인·실패 코드 |
| `ivi_platform/` | 구현됨. Qt/CMake·CTest·수동 Pi 빌드/배포 스크립트 존재. GitHub CI 연결·자동 health/rollback 인수는 남음 |

# 2. GitHub Actions 파이프라인 상세

명령·작성 절차의 단일 관리 위치는 [IVI CI 참조 §1](../plan/detail/ivi/ref_CI파이프라인_명령모음.md#1-ci-구현-명세--단일-관리-위치)다. 본 문서는 공식 인수 명세를 관리한다. 전체 YAML/Docker/CMake를 양쪽에 중복 유지하지 않는다. 구현 후 실행 정본은 실제 파일이다.

## 2.1. 트리거 조건 (FR-CI-001)

main/develop push·PR에서 Stage 1~3을 시작한다. 배포는 main push이며 동일 revision의 선행 단계가 통과해야 한다. 브랜치 보호·리뷰 정책(NFR-QA-004)을 실제 저장소에서 설정하고 우회 차단을 시험한다.

## 2.2. Stage 1 — 정적 분석 (FR-CI-002)

cppcheck Error 0건을 검사한다. SRS의 Critical/Error 표현을 실제 도구 severity에 매핑해 버전·대상·억제 사유를 남긴다. `--enable=all --error-exitcode=1`이 Error만 실패시킨다고 가정하지 않는다. 경고/스타일은 보고하고 Error 게이트는 구조화된 출력과 종료 코드로 구분한다. 분석 대상 0개·도구 실행 실패·파싱 실패는 실패다. 의도적인 Error 주입과 Warning만 있는 사례로 차단 정책을 검증한다.

## 2.3. Stage 2 — ARM64 크로스컴파일 빌드 (FR-CI-003)

Docker에서 실제 CMake 타겟 `adaptive_ecu`를 빌드한다. IVI 소스가 생기면 Qt 6 ARM64 개발 패키지를 고정하고 `ivi_platform`의 CMake target도 별도 artifact로 빌드한다. 예를 들어 빌드 경로가 `build-arm64/`면 artifact는 `build-arm64/adaptive_ecu`다. `ecu_node_a`라는 없는 타겟명을 사용하지 않는다. compiler·sysroot·OpenSSL·GoogleTest의 ARM64 ABI를 확인하고 ELF 아키텍처·소스 revision·artifact hash를 보존한다.

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

예정 파일. 베이스 이미지와 패키지 버전을 기록하고 x86 compiler 도구와 ARM64 타겟 라이브러리를 구분한다. Ubuntu 멀티아키텍처 저장소를 실제 지원 아키텍처에 맞춰 구성한다. `dpkg --add-architecture arm64` 한 줄만으로 필요한 패키지 공급이 보장되지 않는다. 새 checkout에서 컨테이너 빌드·의존성 탐색·시험을 재현해야 한다.

## 3.2. toolchain-aarch64.cmake

예정 파일. compiler/processor·find root·target runtime·CTest emulator를 정하고 OpenSSL/Threads/GoogleTest가 호스트 라이브러리에 잘못 연결되지 않는지 확인한다. 구체 값은 실제 이미지와 일치시킨다.

## 3.3. adaptive_ecu/CMakeLists.txt 필수 옵션

기존 CMake를 별도 골격으로 덮어쓰지 않는다. 실제 옵션 `ECU_BUILD_TESTS`·`ENABLE_COVERAGE`와 타겟을 보존한다. 현재 로컬 재현 명령은 [AGENTS 검증 기준](../AGENTS.md#6-verification-baseline)을 따른다. 계측 활성화·테스트 이름·누락 소스와 실패 전파를 검증한 뒤 CI에 연결한다.

# 4. QEMU user-mode 에뮬레이션 상세 (ADR-006)

## 4.1. 동작 원리

ARM64 사용자 프로그램을 지정 emulator/runtime으로 실행하는 계획이다. QEMU 설치, binfmt 등록, 동적 runtime 공급은 각각 확인한다. 컨테이너 mount/path와 CTest 명령이 실제 실행 가능해야 한다.

## 4.2. QEMU 에뮬레이션 한계 및 처리 방침

CI에서 Mock/가상 입력 단위시험과 실제 장비 시험을 구분한다. QEMU user-mode 자체가 MCP2515/ADS1115 실장비를 제공하지 않는다. PF_CAN 또는 `/dev/i2c-*`가 모든 QEMU 환경에서 원천 불가능하다고 일반화하지 않는다. 이 계획의 CI에는 해당 장비·드라이버·권한을 제공하지 않으므로 실장비 시험을 별도 실행한다. Mock 성공은 물리 CAN·ADC·실시간 성능의 증거가 아니다.

# 5. GitHub Secrets 관리

## 5.1. 필요한 Secrets 목록

배포 SSH 개인키, 대상 호스트, 검증된 호스트 키, Codecov 토큰은 승인된 비밀 저장소에서 공급한다. 문서에는 값이나 실제 장비 주소를 넣지 않는다. 네트워크 경로·계정 권한을 확인하고 PR에는 배포 secrets를 노출하지 않는다. 임의 `ssh-keyscan` 결과만 신뢰하여 대상 인증을 대체하지 않는다.

## 5.2. RPi4 배포 계정 설정

배포 계정과 ECU 서비스 실행 계정을 구분한다. [IVI M4](../plan/detail/ivi/M4_대시보드_Alert_배포.md)의 현재 계획은 deploy로 전달, root 서비스로 ECU 실행이다. 파일 소유·실행·profile 읽기·키 읽기 권한과 제한된 서비스 관리/전환 권한을 실제 대상에서 검증한다. sudo 그룹 전체 권한을 관례로 추가하지 않는다.

# 6. Health Check 스크립트

`scripts/health_check.sh`는 예정이다. 서비스 active 외에 배포 hash/설정, 새 정상 CAN/인증 데이터, 오류·stale 상태, 요구된 IVI 연결을 확인하고 실패 코드를 반환한다. 검사 기한·재시도 값은 구현/측정 근거를 남긴다. 이전 5회×3초 골격을 승인된 상한으로 취급하지 않는다. 키 누락·프로세스 생존하나 송신 정지·버전 불일치·rollback 실패를 음성 시험에 포함한다.

# 7. ecu-node-a.service systemd 유닛

Node A 대상 파일은 `/etc/systemd/system/ecu-node-a.service`다. 실행 파일·인자·작업 디렉토리·profile/키 권한의 정본은 [IVI M4 §3.4](../plan/detail/ivi/M4_대시보드_Alert_배포.md#34-systemd-유닛)에 둔다. Node B Qt 앱에는 별도 systemd 서비스/그래픽 세션 정책을 정의하고 이 Node A 유닛을 적용하지 않는다. 서비스 재기동·완료 heartbeat·CAN 재개를 확인하며 SecOC counter/세션 복구는 별도 인수한다.

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
