# Capstone Project Agent Guide

이 파일은 저장소 전체에 적용되는 공통 AI 작업 지침이다. Claude는 `CLAUDE.md`, Codex는 `CODEX.md`도 읽고, 비단순 작업에서는 루트 `SKILL.md`의 해당 플레이북을 적용한다.

## 1. 지침 우선순위

충돌 시 아래 순서로 판단한다.

1. 사용자와 실행 환경의 지시
2. 이 `AGENTS.md`
3. 도구별 지침: `CLAUDE.md` 또는 `CODEX.md`
4. 재사용 워크플로: `SKILL.md`
5. 일반 관례

공통 블록(HARD RULES, Source of Truth, 검증 명령, 인터페이스 변경 게이트, DoD)의 캐논은 이 파일이다. 다른 지침은 공통 본문을 복제하지 않고 이 파일의 해당 절을 참조한다. 내용을 바꿀 때는 `AGENTS.md`를 먼저 수정하고 `CLAUDE.md`, `CODEX.md`, `SKILL.md`의 대응 참조·고유 절차를 같은 변경 단위로 동기화한다. 규칙을 인용할 때는 번호가 아니라 이름으로 한다.

도메인 사실은 아래 Source of Truth 순서를 따른다. 단, 파일이나 기능이 **현재 구현되어 있는지**는 문서의 계획이 아니라 대상 브랜치의 실제 파일로 확인한다.

## 2. HARD RULES

1. **ICD 계약을 임의로 변경하지 않는다.** `docs/ICD.md`의 CAN ID, 방향, DLC, 바이트 레이아웃, 스케일, 엔디언, SecOC 입력 순서, HAL API는 명시적 승인 없이 바꾸지 않는다.
2. **현재 구현과 계획을 구분한다.** SRS, SDD, Plan에 적힌 예정 구조를 존재하는 코드처럼 설명하거나 생성하지 않는다. 먼저 `git status`, `git branch --show-current`, `rg --files`로 대상 상태를 확인한다.
3. **사용자 작업을 보존한다.** dirty worktree와 미추적 파일을 사용자 소유로 간주한다. 관련 없는 수정, 포맷, 이동, 삭제, 되돌리기, 스테이징을 하지 않는다.
4. **요청 범위만 수정한다.** 인접 코드 정리, 선제적 추상화, 요청하지 않은 호환 계층과 설정을 추가하지 않는다.
5. **검증 없이 완료라 하지 않는다.** 변경에 가장 가까운 테스트나 문서 검사를 실행한다. 실행할 수 없으면 정확한 이유와 미검증 범위를 보고한다.
6. **수치를 추정으로 채우지 않는다.** 탐지율, 오탐률, 지연, 주기, 커버리지는 실행 결과나 사용자가 제공한 근거만 사용하고 목표값과 실측값을 구분한다.
7. **비밀을 저장하지 않는다.** SecOC 키, 토큰, 장비 주소, 자격 증명은 코드·테스트·문서·로그에 커밋하지 않는다. 테스트에는 명시적인 더미 값을 사용한다.

## 3. Project Snapshot

프로젝트 목표는 RPi4 기반 Node A ECU와 Node B IVI를 CAN으로 연결해 BMS, SecOC, IDS, 대시보드까지 end-to-end로 검증하는 것이다.

| 영역 | 표준 경로 | 현재 판단 원칙 |
|---|---|---|
| Node A ECU | `adaptive_ecu/` | C++17, CMake, GoogleTest/CTest. 소스 존재와 시험 통과를 구분한다. |
| Security/IDS | `security/` | Python SecOC, 공격·IDS·실험. 의존성은 `security/requirements.txt`. |
| Node B IVI | `ivi_platform/` | Ubuntu/C++17/SocketCAN/Qt Quick Plan B. P4 Linux vcan·Qt 계측까지 있으며 후속 단계 완료 여부는 시험 증거로 판단한다. |
| 공식 문서 | `docs/` | 계약·요구사항·설계·시험의 source of truth. |
| 실행 계획 | `plan/ECU.md`, `plan/IVI.md`, `plan/detail/common/00_협업_규약.md` | 상위 2개 계획과 `plan/detail/ecu/`, `ivi/`, `common/`의 상세 절차를 사용한다. 원문 보관 위치는 `plan/_archive/`다. 과거 별도 `Plan/` 원문은 통합·보관했으며 현재 실행 디렉토리는 소문자 `plan/`이다. 현재 구현의 증거가 아니다. |
| 임시 산출물 | `tmp/` | `.gitignore` 대상. 보존이 필요한 최종 문서는 두지 않는다. |

**스냅샷 갱신일 2026-09-23.** 현재 저장소는 Git 원격과 `main`·`develop` 브랜치가 있으며 실제 작업 시작 때 branch와 dirty 상태를 다시 확인한다. ECU와 Python 보안·IDS 소스는 존재하지만 문서 정리가 동작 검증을 의미하지 않는다. ADR-010의 Ubuntu/C++17/SocketCAN/Qt Quick Plan B를 현 제출 기준으로 유지한다. IVI는 P1~P4를 완료했으며 CHG-003에 macOS Qt 시험과 Linux vcan·T1~T4 증거를 기록했다. CHG-004는 Qt 현행 안내와 Android 역사 자료의 읽기 경계를 정리한다. RPi4 물리 통합·CI는 후속 증거가 필요하며, 단계 완료는 실제 빌드·시험 증거로만 판정한다.

현재 폴더에 없는 `CAR-ECU/`, `.github/` CI, `Dockerfile.arm64`, ARM64 toolchain, `.clang-format`, AOSP 소스는 존재한다고 가정하지 않는다. 초기 제안서는 `docs/archive/project-overview.md`에서 배경 자료로 보존한다.

## 4. Source of Truth

1. `docs/ICD.md`: CAN/SecOC/HAL 인터페이스 계약
2. `docs/SRS.md`: FR/NFR과 추적성
3. `docs/SDD-ECU.md`, `docs/SDD-IVI.md`: 모듈 설계
4. `docs/TEST_PLAN.md`: 공식 TC ID와 합격 기준
5. `docs/ADR.md`: 채택된 설계 결정과 대안
6. `docs/TARA.md`: 위협, 위험, 완화책
7. `plan/ECU.md`, `plan/IVI.md`: 역할별 실행 과제. `plan/detail/common/00_협업_규약.md`: 공동 운영 규약. 의존성·통합 시험·제출은 같은 디렉토리의 01·02·03 문서를 사용한다. `plan/_archive/`는 현행 실행 기준이 아니다
8. `docs/CICD_SPEC.md`: 예정 CI/CD 명세. 기술하는 GitHub Actions 4단계, Docker ARM64, QEMU는 아직 구현되지 않았다. `docs/README.md`는 문서 목록 안내다.

문서끼리 충돌하면 상위 문서를 우선하고 충돌을 보고한다. 구현이 문서 계약과 다르면 조용히 한쪽을 맞추지 말고 drift를 식별한다.

### 고정 인터페이스 참조

CAN ID·방향·주기·DLC·레이아웃은 [ICD](docs/ICD.md)의 CAN 메시지 규격, HMAC 입력·rolling-counter 예외 규칙은 SecOC 절, Node B API는 C++ Service API 절을 직접 읽는다. 요약을 별도 유지하지 않는다.

## 5. Default Workflow

1. 작업 범위, 대상 브랜치, dirty 상태를 확인한다.
2. 작업 유형에 맞는 source 문서와 실제 구현 파일만 읽는다. 커밋 검토·분리·실행 요청에는 [공통 커밋 절차](.agents/skills/commit/SKILL.md)와 그 절차가 연결하는 규칙을 적용한다. 사람용 상세 매뉴얼은 필요한 경우에만 읽는다.
3. 다단계 작업은 구현 전에 짧은 계획과 검증 기준을 세운다.
4. 최소 변경으로 구현하고 기존 스타일과 경계를 유지한다.
5. 가장 좁은 의미 있는 검증부터 실행한다.
6. diff를 다시 읽어 요청 밖 변경, 계약 drift, 누락된 테스트를 확인한다.
7. 변경 파일, 검증 결과, 미실행 항목과 이유를 간결하게 보고한다.

인터페이스 변경이 필요하면 먼저 영향받는 CAN ID/필드/HAL API와 Node A·Node B·SecOC·시험 영향을 제시하고 승인을 받는다. 승인 후에는 ICD, SRS, 양측 SDD, TEST_PLAN, 구현과 테스트를 한 변경 단위로 동기화한다.

## 6. Verification Baseline

PowerShell과 POSIX 셸 모두에서 의미가 같은 CMake 명령을 우선한다.

```text
cmake -S adaptive_ecu -B adaptive_ecu/build -DECU_BUILD_TESTS=ON
cmake --build adaptive_ecu/build
ctest --test-dir adaptive_ecu/build --output-on-failure
python -m pytest security/tests -v
python security/experiments/run_eval.py
```

- ECU 한 모듈 수정: `ctest --test-dir adaptive_ecu/build -R <test_name> --output-on-failure`
- Python 한 모듈 수정: 대응 테스트 파일만 먼저 실행한 뒤 필요 시 전체 실행
- 문서 수정: 경로·링크·제목·FR/TC/ADR ID와 코드 펜스 정합 검사
- CAN/하드웨어: 단위 테스트를 먼저 실행하고 장비나 `vcan0`가 있을 때만 smoke test

의존성 설치, 네트워크, 하드웨어, 관리자 권한이 필요한 검증은 임의로 우회하지 않는다.

## 7. Definition of Done

- 변경한 모든 줄이 요청과 연결된다.
- 현재 구현과 계획, 목표값과 실측값을 구분했다.
- ICD와 보안 가정을 보존했거나 승인된 변경 프로토콜을 완료했다.
- 대응 테스트와 추적 문서를 함께 갱신했다.
- 최소 1개의 의미 있는 검증을 실행하고 결과를 확인했다.
- 사용자 변경을 보존했고 새 비밀·빌드 산출물·대형 로그를 추가하지 않았다.
- 최종 보고에 변경 위치, 검증, 남은 한계를 포함했다.
