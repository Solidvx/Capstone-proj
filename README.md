# IVI–ECU Capstone

RPi4 Node A ECU와 Node B IVI를 CAN으로 연결해 BMS, SecOC, IDS, 대시보드를 검증하는 프로젝트다.

## 처음 참여한 팀원

1. [프로젝트 구조 사용 안내](docs/development/governance/프로젝트구조_사용안내.md)에서 전체 구조를 확인하고, IVI 담당자는 [Plan B 진행 안내](docs/development/governance/IVI_Plan_B_진행상황_및_구조_안내.md)를 이어서 읽는다.
2. [공통 지침](AGENTS.md)과 아래 담당 계획·공동 규약을 읽는다.
3. [작업 흐름](docs/development/workflow.md)에 따라 관련 계약·선행 과제를 확인하고 작업·검증·인계를 기록한다.
4. GitHub 저장소를 만들거나 브랜치·커밋·PR을 관리할 때는 [GitHub 형상관리 실행 매뉴얼](docs/development/governance/commit.md)을 순서대로 따른다.

## 주요 디렉터리

| 위치 | 역할 |
|---|---|
| `adaptive_ecu/` | Node A C++ 소스·헤더·시험·입력 자료 |
| `security/` | Python SecOC·IDS·합성 공격·평가 코드 |
| `ivi_platform/` | Node B C++17/SocketCAN/Qt Quick 코드·시험·실행 스크립트 |
| `plan/` | ECU·IVI·공동 실행 계획과 단계별 과제 |
| `docs/` | 공식 계약·요구·설계·시험 및 개발 운영 자료 |
| `docs/development/` | 목적별 운영 지침·설계 보충·실험 보고서·양식 |
| `docs/aidlc/` | 개별 작업 기록 템플릿과 구조 변경 증거 |
| `tools/workflow/` | 운영 자동화의 미구현 골격 |
| `.agents/`, `.claude/`, `.codex/` | AI 안내·설정 골격; 배치와 활성화 구분 |
| `하드웨어 정보/` | 장비 사진·배선 참고 자료 |
| `tmp/` | 임시 분석·출력; 보존할 최종 문서 위치 아님 |

전체 파일 설명은 [상세 안내](docs/development/governance/프로젝트구조_사용안내.md), 새 문서 위치는 [배치 기준](docs/development/README.md#document-placement), GitHub 작업은 [실행 매뉴얼](docs/development/governance/commit.md)을 따른다.

## GitHub 공유와 팀원 로컬 설정

코드·ICD·설계·시험·실행 계획은 함께 공유한다. 실제 암호·API 토큰·SecOC 키·장비 접속 정보는 `secrets/` 또는 `private/`에 보관하고 커밋하지 않는다. 필요한 값은 접근이 제한된 팀 비밀번호 관리자나 비공개 파일 전달 수단으로 담당 팀원에게 전달한다. GitHub 이슈·PR·커밋 메시지에 비밀값을 적지 않는다.

- 설정 항목은 [`.env.example`](.env.example)에 빈 값으로 공유한다. 필요하면 `.env`로 복사해 로컬에서 채운다. 현재 제품은 이 파일을 자동으로 읽지 않으므로 각 도구에 맞게 설정한다.
- ECU는 현재 `--key <키 파일 경로>`로 SecOC 키를 읽는다(기본 경로 `/etc/secoc/key.bin`). ECU·IVI 통합 시 키 파일 형식·길이는 [ICD](docs/ICD.md)를 따르고 양측 담당자가 동일한 실제 키를 별도로 배치한다. `.env`에 경로를 적는 것만으로 ECU에 적용되지는 않는다. IVI 구현과 키 로딩은 아직 구현 예정이다.
- 테스트용 더미 키와 실제 통합 키를 구분한다. 공유용 `*.example` 파일에는 실제 비밀값을 넣지 않는다. 개인 설정을 공유해야 하면 인증정보를 제거한 예제를 제공한다. `.codex/config.toml`과 `.claude/settings.json`은 공용 설정이므로 비밀값을 넣지 않는다.
- 하드웨어 JPG 원본은 촬영 위치정보가 있어 Git에서 제외한다. IVI 팀원은 [`하드웨어 정보/shared/`](하드웨어%20정보/shared/)의 공개용 사본을 사용한다. 사본은 촬영 위치·시간·기기 메타데이터를 제거하고 표시 방향만 보존했다. 새 사진도 메타데이터와 화면 속 개인정보를 확인한 뒤 공유 경로에 넣는다. 기존 PNG·배선 자료는 원래 경로에서 공유한다.
- `.gitignore`는 이미 추적된 파일이나 과거 커밋을 제거하지 않는다. Git 저장소를 만든 뒤 업로드 전에 `git status --short`와 `git diff --cached`로 실제 포함 파일을 확인한다. 제외 파일을 `git add -f`로 추가하지 않는다. 폴더 전체 ZIP에는 제외 규칙이 적용되지 않는다.

## 진행 계획

| 문서 | 담당 |
|---|---|
| [ECU 계획](plan/ECU.md) | 팀원A: ECU·BMS·보안·실험 |
| [IVI 계획](plan/IVI.md) | 팀원B: Ubuntu·C++ SocketCAN·Qt Quick/QML·측정·CI |
| [공동 계획](plan/detail/common/00_협업_규약.md) | 공동 일정·선행 조건·통합 시험·릴리즈·최종 제출 |

M1~M8 단계 순서는 유지한다. 사용자 지정 시연 마감은 2026-09-18이며 단계별 완료 상태는 증거로 확인한다. 파일이 있다는 이유만으로 구현 완료나 시험 통과로 표시하지 않는다.

## 현재 상태

2026-09-23 파일·Git 대조 기준 ECU C++와 Python 보안·IDS 소스가 있다. IVI는 Ubuntu/C++17/SocketCAN/Qt Quick Plan B의 P3 상태·UI까지 완료했고 Qt 6 Debug/Release 시험이 각 8/8 통과했다. Linux vcan·RPi4 물리 통합과 CI·ARM64 Docker는 아직 미검증 또는 미구현이다. Git 원격과 `develop` 브랜치가 존재한다.

- [공식 문서 목록](docs/README.md): 계약·요구사항·설계·시험
- [공통 작업 지침 및 검증 명령](AGENTS.md): 환경 조건을 확인한 뒤 필요한 검증 실행
- [정리 결과](docs/development/reviews/정리_이력.md#part3-apply): 변경 내역·백업·검증·이관 근거

개발 재개 시 [종합 정합성 검토·착수 관문](docs/development/reviews/문서_종합정합성_검토.md)을 먼저 확인한다.

## 소스

- `adaptive_ecu/`: C++17 ECU, CMake, GoogleTest
- `security/`: Python SecOC, 합성 공격·IDS 비교, 실험·측정
- `ivi_platform/`: C++/Qt Node B 코드, core·Qt 시험과 실행 보조 스크립트. P1~P3 결과와 후속 제한은 [CHG-003](docs/aidlc/changes/CHG-003/aidlc-state.md)에 기록한다.

연구·배경 자료는 [문서 목록](docs/README.md)에서 연결한다. 제품 코드의 존재·완료 여부는 실제 파일과 검증 결과로 확인한다.


개발 운영과 작업 기록: [운영 안내](docs/development/README.md) · [AIdlc 구조 적용·보존 결과](docs/aidlc/structure/verification.md).


전체 예정 구조의 선배치 결과: [골격 적용 안내](docs/aidlc/structure/scaffold-application.md).
