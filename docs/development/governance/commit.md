# GitHub 형상관리 실행 매뉴얼

<!-- 생성 목적: ECU·IVI 담당자가 하나의 GitHub 저장소에서 파일 선택, 브랜치, 커밋, PR, 통합, 릴리즈를 처음부터 수행하도록 안내한다. 사용 목적: 처음 저장소를 등록할 때와 각 작업을 시작·종료할 때 순서대로 따라 한다. -->

작성 기준일: 2026-09-10

이 문서는 Git과 GitHub를 처음 사용하는 팀원도 순서대로 따라 할 수 있는 실행 안내다. 협업 원칙과 형상관리 근거는 [협업·형상관리 전략](협업_형상관리전략.md), 공동 브랜치·PR·릴리즈 규칙은 [공동 협업 규약](../../../plan/detail/common/00_협업_규약.md)을 우선한다. 커밋의 타입·분리·메시지는 공통 원본인 [커밋 규칙](../../../.agents/skills/commit/rules.md), AI에게 대화형 커밋 안내를 요청할 때는 [commit skill](../../../.agents/skills/commit/SKILL.md)을 따른다. CAN·SecOC·HAL 계약을 바꾸려면 [AGENTS](../../../AGENTS.md)의 인터페이스 변경 절차를 적용한다.

현재 확인된 작업 폴더에는 `.git`이 없다. Git은 설치되어 있지만 GitHub CLI인 `gh`는 설치되어 있지 않다. 따라서 아래 절차는 Windows PowerShell의 `git` 명령과 GitHub 웹 화면을 기준으로 한다. 문서에 적힌 저장소 생성·push·보호 규칙이 현재 완료됐다는 뜻은 아니다. 실행 시에는 자신의 환경을 다시 확인한다.

이 매뉴얼은 사람이 Git/GitHub 작업을 선택해 수행하는 상세 안내다. AI에게는 요청한 단계까지만 맡긴다. “검토”는 분석과 제안, “로컬 커밋”은 지정 범위의 검증·stage·commit이며, 초기화·push·PR·병합·태그는 해당 작업까지 요청한 경우에만 진행한다.

## 1. 가장 먼저 이해할 흐름

ECU와 IVI가 각각 별도 저장소를 만드는 방식이 아니다. 두 담당자 모두 하나의 저장소 전체를 clone하고 같은 `develop`을 기준으로 작업한다. 담당 경로는 주로 수정하고 책임질 범위를 뜻하며, 다른 경로를 내려받지 않는다는 뜻이 아니다.

```text
파일 수정
  ↓ git add
이번 커밋에 넣을 파일 선택(stage)
  ↓ git commit
내 컴퓨터의 현재 브랜치에 이력 저장
  ↓ git push
GitHub의 작업 브랜치에 업로드
  ↓ Pull Request
상대 담당자 검토·시험 결과 확인
  ↓ Squash and merge
develop에 통합
  ↓ 공동 통합 시험·인수
develop → main Pull Request
  ↓ Create a merge commit
태그·GitHub Release
```

| 명령 | 쉬운 의미 |
|---|---|
| `git status` | 바뀐 파일과 현재 상태 확인 |
| `git diff` | 추적 중인 파일의 아직 add하지 않은 차이 확인. 미추적 파일 내용은 별도로 읽음 |
| `git add` | 다음 커밋에 넣을 파일 선택 |
| `git diff --cached` | add한 뒤 실제 커밋될 내용 확인 |
| `git commit` | 선택한 변경을 로컬 이력에 저장 |
| `git push` | 로컬 커밋을 GitHub 브랜치에 업로드 |
| `git fetch` | GitHub의 새 이력 정보를 받되 내 파일에는 아직 적용하지 않음 |
| `git pull --ff-only` | GitHub의 최신 이력을 안전하게 현재 브랜치에 반영 |
| `git switch` | 브랜치를 이동하거나 생성 |

`git add`만 해서는 GitHub에 올라가지 않는다. `add → commit → push → PR → review → merge`까지 구분해서 수행한다.

## 2. 공통 저장소에서 누가 무엇을 관리하는가

### 2.1 ECU 담당 중심 경로

아래 파일은 ECU 담당자가 주로 수정한다. 실제 변경과 함께 필요한 시험·계획·증거만 같은 PR에 포함한다.

```text
adaptive_ecu/
├── CMakeLists.txt
├── main.cpp
├── include/                    C++ 헤더·공통 자료형
├── src/app/                    SOC·SOH·Fail-safe 등 앱 로직
├── src/bsw/                    CAN·SecOC·장치 지원
├── test/                       GoogleTest
└── data/                       작고 재현 가능한 입력 자료

security/
├── secoc_module.py
├── requirements.txt
├── ids/                        특징·규칙·사양·IF 탐지기
├── attacks/                    합성 공격 코드
├── experiments/                평가 실행 코드
├── analysis/                   측정·분석 코드
└── tests/                      Python 시험

plan/ECU.md
plan/detail/ecu/
docs/SDD-ECU.md
docs/development/security/      관련 설계·인계 문서
docs/development/experiments/   보존할 실험 결과 보고서
```

`security/`와 `docs/development/security/`는 ECU만 변경할 수 있는 폴더가 아니다. 양측이 관련 보안·IDS 작업에 사용하며, IVI의 인증·표시·통합 동작에 영향을 주면 IVI 담당자의 검토를 받아야 한다.

### 2.2 IVI 담당 중심 경로

아래 파일은 IVI 담당자가 주로 수정한다.

```text
ivi_platform/
├── 프로젝트에서 직접 작성한 HAL
├── Service
├── UI·앱 코드
├── device/product 설정
├── 빌드·배포 스크립트
└── 단위·통합 시험

plan/IVI.md
plan/detail/ivi/
docs/SDD-IVI.md
docs/development/environment/
docs/CICD_SPEC.md                CI 관련 변경 시
```

현재 `ivi_platform/`에는 목적 안내 README만 있고 Android·Qt 제품 코드는 없다. 앞으로 프로젝트에서 직접 작성한 HAL·Service·앱·설정·시험만 관리한다. 외부 AOSP 전체 소스 체크아웃을 이 저장소에 복사하지 않는다.

### 2.3 공동 관리 경로

다음은 공동 기준 또는 운영 자료다. 한 PR에서 편집 담당 한 명을 정하고 상대 담당자가 영향을 확인한다.

```text
README.md
AGENTS.md
CODEX.md
CLAUDE.md
SKILL.md
.gitignore

docs/ICD.md
docs/SRS.md
docs/TEST_PLAN.md
docs/ADR.md
docs/TARA.md
docs/README.md

plan/detail/common/
docs/development/governance/
docs/development/reviews/
docs/aidlc/
tools/
.agents/
.claude/
.codex/
하드웨어 정보/
```

`docs/ICD.md`, SRS, 양측 SDD, TEST_PLAN처럼 연결된 공식 문서는 한쪽 구현만 보고 임의로 바꾸지 않는다. 변경이 필요하면 영향을 먼저 제시하고 승인을 받은 뒤 계약·양측 설계·구현·시험을 같은 변경 단위 또는 명확히 연결된 PR로 관리한다.

## 3. GitHub에 포함하지 않는 파일

다음은 커밋에서 제외할 대상이다. 실제 무시 규칙은 루트 [.gitignore](../../../.gitignore)를 확인한다. 목록에 없더라도 키·토큰·자격 증명·개인 장비 주소는 커밋하지 않는다. 이미 추적된 파일은 `.gitignore`에 추가해도 자동으로 제외되지 않으므로 staged diff까지 확인한다.

### 3.1 ECU·CMake 제외 대상

```text
adaptive_ecu/build/
adaptive_ecu/bin/
build/
cmake-build-*/
CMakeFiles/
CMakeCache.txt
Testing/
compile_commands.json
*.o
*.a
*.so
*.elf
coverage/
*.gcov
```

### 3.2 Python·보안 실험 제외 대상

```text
__pycache__/
.pytest_cache/
.venv/
venv/
*.pyc
security/ids/models/
security/ids/data/
security/ids/logs/
security/attack_simulators/logs/
*.candump
*.pcap
*.pcapng
```

보안 실험의 코드·작은 더미 벡터·요약 결과·재현 명령은 Git으로 관리한다. 대형 CAN 로그·학습 모델·원시 CSV는 별도 보관하고 CHG 기록에 위치·SHA-256·보관 담당·복구 방법을 적는다.

### 3.3 IVI·AOSP 제외 대상

```text
AOSP 전체 소스 체크아웃
.repo/
out/
.gradle/
ivi_platform/app/build/
ivi_platform/*/build/
local.properties
*.apk
*.aab
*.dex
*.keystore
*.jks
captures/
.externalNativeBuild/
*.iml
ivi_platform/hal/gen/
.docker/
toolchain/sysroot/
```

`.repo/`처럼 현재 `.gitignore`에 명시되지 않은 외부 AOSP 경로도 저장소 안에 만들지 않는다. 부득이하게 새 제외 규칙이 필요하면 `.gitignore` 변경을 별도 확인하고 적용한다. `git add -f`로 무시 규칙을 강제로 우회하지 않는다.

### 3.4 공통 제외 대상

```text
.env
.env.*
secrets/
*.pem
*.key
*.p12
id_rsa
id_ed25519
secoc_key.bin
hmac_key.*
*.log
logs/
tmp/
temp/
IDE 개인 설정
```

빈 디렉터리는 Git이 추적하지 않는다. 목적상 반드시 유지할 빈 폴더라면 의미 없는 빈 파일보다 목적·사용 시점·현재 상태가 적힌 README를 둔다.

## 4. 명령을 실행하는 위치와 표기

Cursor에서 프로젝트를 열고 `Terminal → New Terminal`로 PowerShell 터미널을 연다. 모든 공통 Git 명령은 프로젝트 루트에서 실행한다. 아래 경로는 현재 컴퓨터의 예시이며 팀원은 자신의 프로젝트 경로로 바꾼다.

```powershell
Set-Location "C:\Users\maphc\Desktop\캡디\Capstone-proj"
Get-Location
```

`<GITHUB_OWNER>`, `<REPOSITORY_NAME>`, `<파일 경로>`는 실제 값으로 교체하는 자리표시자다. 따옴표 안의 자리표시자도 반드시 바꾼다. 경로·브랜치 인수는 따옴표를 유지하면 공백과 한글을 안전하게 전달할 수 있다.

각 명령의 출력과 성공 여부를 확인한 뒤 다음 줄로 진행한다. 검증·stage·commit이 실패했는데 뒤의 commit·push까지 한꺼번에 실행하지 않는다. “예시” 블록은 현재 작업에 해당하는 것만 선택한다.

```powershell
git add -- "하드웨어 정보/mcp2515.jpg"
```

## 5. 최초 GitHub 저장소 만들기 — 저장소 소유자 한 명만 수행

### 5.1 기존 저장소 여부부터 확인

```powershell
Set-Location "C:\Users\maphc\Desktop\캡디\Capstone-proj"

Test-Path ".git"
git status
```

현재 기준으로 `Test-Path`는 `False`, `git status`는 `not a git repository`가 정상이다. 기존 원격 저장소나 보존해야 할 이력이 발견되면 여기서 중단한다. 기존 이력이 있는데 `git init`으로 새 이력을 만들거나 서로 다른 두 저장소를 나중에 억지로 합치지 않는다.

### 5.2 각자 Git 작성자 정보 확인

```powershell
git config --global --get user.name
git config --global --get user.email
```

비어 있거나 잘못되어 있으면 각자 자신의 값으로 설정한다.

```powershell
git config --global user.name "<본인 이름>"
git config --global user.email "<GitHub 이메일>"
```

### 5.3 GitHub 웹에서 빈 저장소 생성

1. GitHub에 로그인한다.
2. `New repository`를 선택한다.
3. 저장소 소유자와 이름을 정한다.
4. Public 또는 Private을 팀 합의에 따라 선택한다.
5. `Add a README file`은 선택하지 않는다.
6. `.gitignore`는 `None`을 선택한다.
7. License도 이 단계에서는 자동 추가하지 않는다.
8. `Create repository`를 선택한다.

현재 프로젝트의 README와 `.gitignore`를 첫 기준본으로 올리기 위해 빈 저장소를 만든다.

### 5.4 로컬 Git 초기화와 원격 연결

```powershell
git init -b main

git remote add origin "https://github.com/<GITHUB_OWNER>/<REPOSITORY_NAME>.git"
git remote -v
```

원격 URL에 토큰을 직접 넣지 않는다. GitHub 로그인 창이나 Git Credential Manager를 사용한다.

### 5.5 첫 등록 후보 검사

```powershell
# 실제 add 전에 등록 후보만 확인
git add -n .

# 무시되는 파일까지 표시
git status --ignored --short

# 크기가 큰 파일 상위 20개 확인
Get-ChildItem -Recurse -File |
    Sort-Object Length -Descending |
    Select-Object -First 20 FullName, Length
```

`.env`, 키, 인증서, 빌드 결과, 대형 원시 로그, AOSP 전체 소스가 후보에 보이면 실제 add를 진행하지 않는다. 필요한 `.gitignore` 규칙과 파일 위치를 먼저 정리한다. 비밀 파일의 내용을 터미널에 출력해서 검사하지 않는다.

### 5.6 첫 기준본 커밋과 push

첫 등록은 “검토한 현재 프로젝트의 기준본 저장”이라는 한 목적의 커밋이다. [커밋 규칙](../../../.agents/skills/commit/rules.md)은 100줄을 금지 기준으로 삼지 않는다. 소유자가 전체 후보를 확인하고 모두 등록하기로 한 이 단계에서만 `git add .`을 사용한다. 일반 개발에서는 실제 변경 파일을 명시한다.

새 기능을 섞지 않고 현재 상태·실행한 검증·미검증 범위를 기록한다. 최초 기준본 저장을 기능 완료로 표시하지 않는다. AI에게 맡길 때도 저장소 초기화와 전체 기준본 등록을 명시적으로 요청해야 한다.

```powershell
git add .

git status --short
git diff --cached --stat
git diff --cached --check
git diff --cached
```

검사 결과가 예상과 일치할 때 커밋한다.

```powershell
git commit -m "chore(repo): 프로젝트 기준본 등록"
git push -u origin main
```

그다음 공동 통합 브랜치를 만든다.

```powershell
git switch -c develop
git push -u origin develop
```

확인한다.

```powershell
git branch --all
git remote -v
git status
git log --oneline --decorate -5
```

## 6. GitHub 공동 설정 — 한 번만 수행

### 6.1 IVI 또는 ECU 팀원 초대

GitHub 저장소의 `Settings → Collaborators`에서 상대 팀원을 초대하고 Write 권한과 실제 push 가능 여부를 확인한다. 초대 수락 전에는 clone만 가능하거나 private 저장소에 접근하지 못할 수 있다.

### 6.2 main과 develop 보호

GitHub 저장소의 `Settings → Branches` 또는 현재 제공되는 Rulesets 화면에서 `main`, `develop` 규칙을 만든다.

`main`:

- Pull Request를 통해서만 병합
- 승인 1회 필요
- 강제 push 차단
- 브랜치 삭제 차단
- 실제 CI 검사 이름이 생긴 뒤에만 해당 검사를 필수로 지정

`develop`:

- Pull Request를 통해서만 병합
- 상대 담당자 리뷰를 팀 규칙으로 적용
- 강제 push 차단
- 실제 CI가 확인된 뒤 필수 검사 지정

CI가 아직 없는데 존재하지 않는 검사 이름을 필수로 등록하면 모든 PR이 대기 상태에 머물 수 있다. 문서에 예정된 CI를 실제 검사로 간주하지 않는다.

### 6.3 Issue·라벨·마일스톤

공동 규약의 라벨과 M1~M8 마일스톤을 생성한다. Issue에는 담당, 범위, 완료 조건, 관련 M단계, 선행 과제와 차단 요인을 적는다.

```markdown
## 작업 목적
- 관련 계획 과제:
- 관련 요구·시험:

## 담당과 범위
- 담당: ECU / IVI / 공동
- 수정 예상 경로:
- 포함하지 않을 범위:

## 완료 조건
- [ ] 구현 또는 문서 변경
- [ ] 관련 시험
- [ ] 상대 담당자 인계

## 선행 조건·차단 요인
- 선행 Issue/PR:
- 현재 차단:
```

## 7. 두 번째 팀원의 최초 참여

두 번째 팀원은 별도로 `git init`하지 않고 공동 저장소를 clone한다.

```powershell
Set-Location "<프로젝트를 저장할 상위 폴더>"

git clone "https://github.com/<GITHUB_OWNER>/<REPOSITORY_NAME>.git"
Set-Location "<REPOSITORY_NAME>"

git remote -v
git branch --all
git switch develop
git pull --ff-only origin develop
git status
git log --oneline --decorate -5
```

ECU·IVI 모두 전체 저장소를 받는다. clone 후 담당 폴더만 수정하되 공통 계약과 상대 인계 문서는 읽을 수 있어야 한다.

## 8. 브랜치 이름 규칙

영구적으로 `ecu`와 `ivi` 브랜치를 따로 유지하지 않는다. 한 작업 또는 한 Issue마다 짧은 작업 브랜치를 만든다.

| 유형 | 의미 | 예시 |
|---|---|---|
| `feat/` | 새 기능 | `feat/ecu-m2-can-publisher` |
| `fix/` | 버그 수정 | `fix/ivi-stale-state` |
| `test/` | 시험 추가·수정 | `test/ecu-ids-ablation` |
| `docs/` | 문서 변경 | `docs/common-icd-secoc` |
| `chore/` | 환경·CI·구조 | `chore/ivi-ci-stage1` |
| `refactor/` | 동작 변화 없는 구조 정리 | `refactor/ecu-publisher` |

ECU 예시:

```text
feat/ecu-m2-can-publisher
feat/ecu-m3-secoc
fix/ecu-counter-replay
test/ecu-ids-ablation
docs/ecu-m5-experiment
```

IVI 예시:

```text
feat/ivi-m3-can-parser
feat/ivi-m4-dashboard
fix/ivi-stale-state
test/ivi-hal-mock
chore/ivi-ci-stage1
```

공동 예시:

```text
docs/common-icd-secoc
docs/common-test-mapping
chore/common-workflow
```

브랜치의 `refactor/`와 커밋의 `refactor(scope): 설명`은 모두 동작 변화 없는 정리에 사용한다. 예: `refactor/ecu-publisher` 브랜치에서 `refactor(bsw): CAN 인코딩 보조 함수 분리`로 커밋한다.

## 9. 모든 작업을 시작할 때 공통 순서

작업 전 저장소 위치·브랜치·기존 변경을 확인한다. Git이 없으면 5장의 최초 등록 또는 7장의 기존 저장소 참여 중 필요한 절차를 사람이 먼저 결정한다.

```powershell
git rev-parse --show-toplevel
git status --short --branch
git branch --show-current
git diff --cached --name-status
```

`git status --short`의 자주 보는 표시는 다음과 같다.

| 표시 | 의미 |
|---|---|
| `??` | 미추적 새 파일. 내용을 별도로 읽어야 함 |
| ` M` | 추적 파일을 수정했지만 아직 stage하지 않음 |
| `M ` | 수정분을 stage함 |
| `MM` | stage한 뒤 파일을 다시 수정함. 두 diff를 모두 확인 |
| `A ` | 새 파일을 stage함 |
| ` D` / `D ` | 아직 stage하지 않은 삭제 / stage한 삭제 |
| `R ` | Git이 이름변경으로 탐지한 stage |

앞 칸은 index(stage), 뒤 칸은 작업 파일 상태다. 충돌·merge/rebase 진행 중이면 일반 커밋 흐름을 멈추고 해당 작업을 먼저 정리한다. [Git 상태 표시 설명](https://git-scm.com/docs/git-status)

기존 수정이나 stage가 있으면 누구의 어떤 작업인지 확인한다. 작업 트리를 비우려고 다른 변경까지 커밋·unstage하지 않는다. 새 작업은 깨끗한 상태의 최신 `develop`에서 시작하고, 진행 중인 작업을 재개할 때는 기존 작업 브랜치에서 상태를 확인한다.

Cursor Source Control과 Claude Code·Codex CLI는 같은 작업 트리의 branch와 index를 공유한다. 한 주체만 파일 수정·stage·commit을 수행하고, 다른 모델로 바꿀 때 대상 파일·검증 결과·기존 stage를 인계한다. 동시에 개발하려면 별도 clone/worktree와 브랜치가 필요하다.

```powershell
git switch develop
git pull --ff-only origin develop
git log --oneline --decorate -5

git switch -c "<작업 브랜치 이름>"
git branch --show-current
```

예시:

```powershell
git switch -c feat/ecu-m2-can-publisher
```

## 10. ECU 담당자 작업 전체 예시

예시 작업은 CAN Publisher 기능 추가다. 아래 파일은 실제로 존재하지만 이 예시가 구현·시험 완료를 뜻하지는 않는다. 이미 있는 기능의 오류를 고친다면 브랜치와 메시지를 `fix`로 바꾼다. 9장의 상태 확인을 마친 뒤 새 작업을 시작한다.

### 10.1 최신 기준에서 ECU 브랜치 만들기

```powershell
git switch develop
git pull --ff-only origin develop
git switch -c feat/ecu-m2-can-publisher
```

### 10.2 코드 수정 후 차이 확인

```powershell
git status --short
git diff -- adaptive_ecu
```

### 10.3 관련 시험 실행

```powershell
cmake -S adaptive_ecu -B adaptive_ecu/build -DECU_BUILD_TESTS=ON
cmake --build adaptive_ecu/build
ctest --test-dir adaptive_ecu/build --output-on-failure
```

보안 Python을 수정했다면 대응 시험부터 실행하고 필요할 때 전체 시험으로 확장한다.

```powershell
python -m pytest security/tests/test_secoc.py -v
python -m pytest security/tests -v
```

검증이 실패하면 원인을 해결한 뒤 다시 확인한다. 실행할 수 없는 시험은 환경·장비·의존성 등 이유를 PR과 증거에 적는다. 실패·미검증 상태를 저장할 필요가 있으면 13장의 중간 저장 절차를 따르고 기능 완료로 표시하지 않는다.

### 10.4 필요한 ECU 파일만 add

아래 파일 중 이번 목적에 맞게 실제로 변경한 것만 선택한다. 한 파일에 다른 작업이 섞였다면 12.3절의 변경 조각 선택을 사용한다.

```powershell
git add -- adaptive_ecu/include/can_publisher.h
git add -- adaptive_ecu/src/bsw/can_publisher.cpp
git add -- adaptive_ecu/test/test_can_publisher.cpp
```

관련 문서도 실제로 함께 바꿨을 때만 추가한다.

```powershell
git add -- docs/SDD-ECU.md
git add -- plan/detail/ecu/M2_CAN_CDD_Publisher.md
```

### 10.5 커밋 전 최종 확인

```powershell
git status --short
git diff --cached --stat
git diff --cached --check
git diff --cached
```

일반 commit은 현재 index 전체를 담는다. 내가 이번에 잘못 add한 파일은 아래처럼 stage에서 뺄 수 있다. 기존에 다른 사람이나 모델이 stage한 변경이면 임의로 빼지 말고 소유자와 범위를 확인한다.

```powershell
git restore --staged -- "<제외할 파일 경로>"
```

이 명령은 작업 파일 내용을 삭제하지 않고 해당 파일의 stage만 취소한다. 부분 stage가 섞인 파일과 최초 커밋 전 상태의 처리법은 18.1절을 따른다.

### 10.6 ECU 커밋과 push

```powershell
git commit -m "feat(bsw): CAN Publisher 인코딩 기능 추가"
git show --stat --oneline HEAD
git status --short --branch
```

성공한 커밋의 해시·내용을 확인한 뒤, GitHub에 올리기로 한 경우 다음을 실행한다. AI에게 로컬 커밋만 요청했다면 여기서 끝낸다.

```powershell
git push -u origin feat/ecu-m2-can-publisher
```

처음 push가 성공해 upstream이 설정되면, 같은 브랜치의 후속 커밋 업로드에는 `git push`를 사용한다.

```powershell
git push
```

## 11. IVI 담당자 작업 전체 예시

현재 IVI 제품 코드는 아직 없으므로 아래 `<실제 파일>` 자리표시자는 구현 후 생성된 정확한 경로로 교체한다. 없는 파일을 명령 예시 때문에 만들지 않는다. 계획·설계만 변경했다면 실제 문서 경로만 선택하고 `docs(hal)` 등의 메시지를 사용한다.

### 11.1 최신 기준에서 IVI 브랜치 만들기

```powershell
git switch develop
git pull --ff-only origin develop
git switch -c feat/ivi-m3-can-parser
```

### 11.2 IVI 파일과 제외 파일 확인

```powershell
git status --short
git diff -- ivi_platform
git status --ignored --short
```

`out/`, `.gradle/`, `build/`, `local.properties`, APK, 서명키가 등록 후보에 없는지 확인한다.

### 11.3 검증 후 실제로 작성한 파일만 add

IVI 빌드·시험은 실제 Android/AOSP 환경과 구현 경로의 명령으로 먼저 수행한다. 문서만 바꿨다면 링크·제목·관련 ID를 검사한다. ECU의 CTest를 IVI 시험의 대체 증거로 사용하지 않는다. 실패·미실행이면 이유를 적고 13장의 중간 저장 조건을 확인한다.

```powershell
git add -- "ivi_platform/<HAL 또는 Service 실제 파일>"
git add -- "ivi_platform/<대응 시험 실제 파일>"
```

계획·설계도 실제 변경한 경우에만 추가한다.

```powershell
git add -- docs/SDD-IVI.md
git add -- plan/detail/ivi/M3_HAL_Service_대시보드.md
```

### 11.4 IVI 커밋과 push

```powershell
git diff --cached --stat
git diff --cached --check
git diff --cached

git commit -m "feat(hal): CAN 상태 파서 추가"
git show --stat --oneline HEAD
git status --short --branch
```

staged diff에 다른 작업이 없고 커밋이 성공했는지 확인한다. 로컬 저장까지만 요청받았다면 여기까지 수행한다. 업로드할 때는 다음을 실행한다.

```powershell
git push -u origin feat/ivi-m3-can-parser
```

검증한 후 파일을 다시 수정했다면 해당 변경을 재검증·stage해야 한다. 예정 명령을 실행 성공으로 기록하지 않는다.

## 12. 커밋 분리·파일 이동·메시지 작성법

판단 기준은 [rules.md](../../../.agents/skills/commit/rules.md), AI의 STEP 1~7 실행 순서는 [SKILL.md](../../../.agents/skills/commit/SKILL.md)다. 이 장은 사람이 그 기준을 적용하는 구체적인 방법이다.

### 12.1 무엇을 한 커밋으로 묶는가

**한 커밋에 한 가지 설명 가능한 목적을 담는다.** 파일 확장자나 타입이 다르다는 이유로 분리하지 않는다.

| 변경 상황 | 처리 | 이유 |
|---|---|---|
| ECU 송신 기능 + 대응 시험 + 필요한 설계 설명 | 같은 목적의 `feat(bsw)`로 묶음 | 기능을 검토·검증할 자료가 함께 있어야 함 |
| IVI 파서 오류 수정 + 회귀 시험 | `fix(hal)`로 묶음 | 수정과 검증이 한 동작을 설명함 |
| 기능 개발과 관계없는 포맷 정리 | 분리하거나 이번 작업에서 제외 | 무관한 변경을 섞지 않음 |
| 파일 이동 + import·CMake·문서 링크 수정 | 같이 반영 | 이동 후에도 빌드·참조가 유지되어야 함 |
| 100줄 이상인 한 목적의 변경 | 분리할 독립 목적이 있는지 검토 | 100줄은 금지 기준이 아님 |
| 승인된 ICD 계약 변경과 양측 대응 | 같은 논리적 변경 단위로 관리 | 한쪽 계약·시험만 먼저 바뀌는 불일치를 방지 |

Tidy First의 순서는 `필요한 독립적 정리 → 기능/수정 → 필요한 후속 정리·최적화`다. 정리가 불필요하면 바로 기능을 변경한다. 분리된 각 커밋의 빌드·참조 관계를 유지하고, 커밋 개수를 늘리려고 코드를 추가로 정리하지 않는다.

### 12.2 타입과 메시지 선택

| 타입 | 사용할 때 |
|---|---|
| `refactor` | 동작을 유지하는 정리·코드 이동 |
| `feat` | 새 기능과 그 기능에 필요한 시험·문서 |
| `fix` | 오류 수정과 회귀 시험 |
| `test` | 제품 동작을 바꾸지 않는 시험 추가·수정 |
| `docs` | 문서 내용·위치·참조 수정 |
| `chore` | 빌드·환경·설정 변경 |

기존 `tidy`의 정리 개념은 공동 규약의 `refactor`로 표현한다. `style`·`perf`를 별도 타입으로 추가하지 않고 실제 목적에 맞는 위 타입을 사용한다. 성능 향상을 주장할 때는 측정 근거를 연결한다.

메시지는 **`type(scope): 한글 한 줄 요약`**이다. scope는 변경 중심을 하나 고른다.

| 담당·작업 | scope 예시 | 메시지 예시 |
|---|---|---|
| ECU CAN·기반 기능 | `bsw` | `feat(bsw): CAN 상태 송신 기능 추가` |
| ECU BMS | `bms` | `test(bms): Fail-safe 복구 전이 시험 추가` |
| 보안·IDS | `secoc`, `ids` | `fix(secoc): 재전송된 카운터 거부 처리 수정` |
| IVI HAL | `hal` | `feat(hal): CAN 상태 파서 추가` |
| IVI Service·화면 | `service`, `ui` | `fix(ui): 오래된 CAN 상태 표시 수정` |
| 공동 계약·문서 | `icd`, `docs` | `docs(icd): SecOC 문서 참조 경로 정정` |
| CI·저장소 설정 | `ci`, `repo` | `chore(repo): 프로젝트 기준본 등록` |

`repo`·`docs`는 공통 작업을 설명하는 scope 예시다. CAN·SecOC·IDS 같은 기술명과 코드 식별자는 원문 그대로 쓴다. `수정`, `작업`, `최종`만으로 메시지를 만들지 않는다. 상세 근거·시험 결과는 PR·작업 기록에 남기고 요청하지 않은 `Co-Authored-By`는 추가하지 않는다.

### 12.3 한 파일에 여러 작업이 섞였을 때

전체 파일을 add하면 그 파일의 다른 작업까지 함께 들어간다. 먼저 이미 stage된 변경을 확인한 뒤, 아직 stage하지 않은 **이번 작업의 변경 조각만** 선택한다. 아래 경로는 실제 파일로 바꾼다.

```powershell
git diff --cached -- "검토할/파일"
git diff -- "검토할/파일"
git add -p -- "검토할/파일"
```

대화형 선택에서 `y`는 현재 조각 포함, `n`은 제외, `s`는 더 작게 분리, `q`는 종료다. `s`가 불가능하거나 한 조각에 다른 사람의 작업이 섞여 있으면 임의로 포함하지 말고 범위를 확인한다. 새 파일은 이 절차를 그대로 적용할 수 없는 경우가 있으므로 내용을 먼저 검토해 별도로 선택한다. [Git 변경 조각 선택 설명](https://git-scm.com/docs/git-add)

```powershell
git diff --cached --name-status
git diff --cached --check
git diff --cached
```

마지막 diff는 일부 파일만 보지 말고 **이번 commit에 담길 index 전체**를 확인한다. 기존 사용자 stage가 섞여 있으면 임의로 비우거나 함께 커밋하지 않는다. 18.1절의 unstage도 소유와 범위를 확인한 경우에만 적용한다.

### 12.4 파일 이동·이름변경

옛 경로의 삭제와 새 경로의 추가를 같은 커밋에 담는다. 독립적인 동작 변경은 가능하면 분리하지만, 이동 때문에 필요한 import·CMake·문서 링크 수정은 함께 담는다.

아래는 **이미 파일을 이동한 뒤** 사용하는 예시다. 옛 경로·새 경로·참조 문서를 실제 파일로 바꾸고 필요한 행만 실행한다.

```powershell
git add -A -- "옛경로/파일.md" "새경로/파일.md"
git add -- "실제로/참조를수정한문서.md"
git diff --cached --name-status -M
git diff --cached --check
git diff --cached
```

`R100`은 내용이 같은 이름변경 표시다. Git은 유사도로 이동을 탐지하므로 이 표시가 필수는 아니다. `A`·`D`라면 옛 삭제·새 추가가 모두 들어갔는지, 내용 차이가 큰지, 참조가 맞는지 확인한다. 이력이 영구 소실됐다고 단정하거나 같은 add를 반복하지 않는다. [Git 이름변경 탐지 설명](https://git-scm.com/docs/git-diff)

검토·문서 검증 후 문서 이동만 담긴 경우의 메시지 예시는 다음과 같다.

```powershell
git commit -m "docs(docs): 문서를 목적별 디렉터리로 이동"
git show --stat --oneline HEAD
git status --short --branch
```

코드의 동작 보존 이동이라면 `refactor(bsw)`·`refactor(hal)` 등 실제 영역을 사용한다. 디렉토리 전체를 stage하면 다른 변경이 섞일 수 있으므로 이동 전후 파일을 직접 지정하는 방식을 우선한다.

### 12.5 Cursor에서 Claude Code·Codex CLI에 맡기기

Cursor의 프로젝트 터미널에서 `Get-Location`으로 루트를 확인한 뒤 이번 작업을 맡길 CLI 하나를 실행한다. Codex는 `.agents/skills/commit/SKILL.md`, Claude는 `.claude/skills/commit/SKILL.md`를 진입점으로 쓰며 공통 절차는 한 곳에서 관리한다. CLI가 skill을 표시하지 않으면 아래 예시처럼 원본 경로를 지정해 읽도록 요청한다. 실제 인식 확인 방법은 [tooling](../tooling.md#commit-skill)을 따른다.

Claude Code를 사용할 때:

```powershell
claude
```

Codex CLI를 사용할 때:

```powershell
codex
```

아래는 CLI가 열린 뒤 AI에게 보내는 문장이다. PowerShell 명령으로 실행하지 않는다. 두 파일은 경로를 지정해 읽는 공용 지침이며, 이 위치에 파일을 두는 것만으로 `/commit`·`$commit` 명령이 자동 등록되지는 않는다.

**ECU 변경의 검토만 요청:**

```text
.agents/skills/commit/rules.md와 .agents/skills/commit/SKILL.md를 적용해줘.
이번 대상은 내가 지정한 adaptive_ecu/ 변경과 직접 관련된 시험·문서야.
관련 security/ 변경은 별도 목적이 있는지 구분해줘.
기존 사용자 stage와 무관한 변경을 보존하고,
포함 파일·제외 사유·커밋 묶음·메시지·필요한 검증을 보고해줘.
아직 stage·commit·push는 하지 마.
```

**IVI 변경의 검토만 요청:**

```text
.agents/skills/commit/rules.md와 .agents/skills/commit/SKILL.md를 적용해줘.
이번 대상은 ivi_platform/의 실제 변경과 대응 시험·문서야.
HAL·SecOC·ICD와 ECU 측 영향도 확인해서 커밋 분리안을 보고해줘.
구현이 없고 계획·설계만 바뀌었다면 실제 변경 문서만 대상으로 해줘.
기존 사용자 변경을 보존하고 아직 stage·commit·push는 하지 마.
```

**검토한 묶음을 로컬 커밋까지 요청 — 양측 공통:**

```text
방금 제안한 파일·변경 범위와 메시지대로 로컬 커밋까지 진행해줘.
현재 상태가 제안 때와 같은지 확인하고 필요한 검증을 실행해줘.
실패는 먼저 해결하고, 기존 사용자 stage와 무관한 변경은 보존해줘.
완료 후 커밋 해시·메시지·검증 결과·남은 변경을 보고해줘.
GitHub push·PR·병합·태그는 하지 마.
```

이미 커밋 실행을 위임했다면 각 add·메시지 단계마다 반복 승인을 요구하지 않는다. 다른 사용자 변경처럼 범위가 불명확한 부분만 확인한다. Git이 없으면 분석까지만 수행하며, 5장의 초기화는 별도 요청 대상이다.

업로드도 맡길 때는 대상 브랜치를 확인한 뒤 “방금 만든 커밋을 origin의 실제 작업 브랜치로 push해줘”처럼 범위를 지정한다. PR은 준비된 본문과 base/compare를 확인해 별도로 요청하고, 병합·태그까지 자동 포함하지 않는다. GitHub 도구·권한이 없으면 사람이 웹 절차를 수행한다.

### 12.6 STEP 1~7과 매뉴얼 연결

| SKILL 단계 | 사람이 확인할 내용 | 이 문서의 위치 |
|---|---|---|
| 1. 현황 파악 | 저장소·브랜치·기존 변경 | 9장 |
| 2. 변경 분류 | 담당 범위·실제 파일·제외 대상 | 2~3장, 12.3절 |
| 3. 분리 판단 | 한 목적과 필요한 의존 관계 | 12.1절 |
| 4. 검증·stage | 대응 시험·명시적 파일 선택·index 전체 확인 | ECU 10.3~10.5절 / IVI 11.3~11.4절 |
| 5. 메시지 추천 | 실제 변경에 맞는 한글 한 줄 | 12.2절 |
| 6. 커밋 실행 | 로컬 commit의 성공·실패 | ECU 10.6절 / IVI 11.4절 |
| 7. 반복·결과 확인 | 요청 범위의 남은 묶음만 처리 | 각 commit 뒤 show/status, 22장 |

검토만 요청하면 분석과 메시지 추천으로 마친다. 커밋 실행 중 실패하면 다음 push를 진행하지 않는다. hook이 파일을 바꿨다면 diff를 다시 확인하고 필요한 검증을 수행하며, `--no-verify`로 임의 우회하지 않는다.

## 13. 작업 중간 저장

작업 전체가 끝나지 않아도, 의미 있는 단위로 검증된 변경은 개인 작업 브랜치에 저장할 수 있다. 한 파일에 다른 작업이 섞였다면 12.3절처럼 구분한다.

시험 실패·미검증 상태를 그대로 보관하려면 **미완성 작업 저장이라는 의도를 명확히 하고** 실패·미실행 이유·남은 작업을 기록한다. AI에게 일반 커밋만 요청한 경우에는 실패를 먼저 해결하며, 미완성 저장은 명시적으로 요청한다. stage 실패나 요청 밖 변경 혼입은 미완성 저장의 예외 사유가 아니다.

```powershell
git status --short --branch
git add -- "<현재까지 작업한 파일>"
git diff --cached --check
git diff --cached
git commit -m "test(secoc): 인증 실패 사례 시험 초안 추가"
git show --stat --oneline HEAD
git status --short --branch
```

커밋 성공을 확인하고 원격에도 보관하기로 했다면 다음을 실행한다. 최초 push는 10.6절 또는 11.4절처럼 upstream을 먼저 설정한다.

```powershell
git push
```

완료되지 않은 작업은 Draft PR로 유지하고 `develop`에 병합하지 않는다. 나중에 검증과 인수를 마친 뒤 완료로 전환한다. `git stash`는 변경을 잊기 쉬우므로 기본 작업 방식으로 사용하지 않는다.

## 14. Pull Request 생성 순서

작업 브랜치를 push한 뒤 GitHub 웹에서 수행한다.

1. 저장소 페이지를 연다.
2. `Compare & pull request`를 선택한다.
3. `base`가 `develop`인지 확인한다.
4. `compare`가 자신의 작업 브랜치인지 확인한다.
5. 작업이 진행 중이면 `Create draft pull request`를 선택한다.
6. 유형·담당 라벨과 관련 M1~M8 마일스톤을 지정한다.
7. 상대 담당자를 Reviewer로 지정한다.
8. 아래 본문을 채운다.

```markdown
## 작업 목적
- 관련 Issue:
- 관련 계획 과제:
- 관련 FR/NFR/TC/ADR:
- 담당: ECU / IVI / 공동

## 변경 내용
- 변경 전:
- 변경 후:
- 실제 수정 경로:

## 계약·상대 노드 영향
- ICD 영향: 있음 / 없음
- ECU 영향:
- IVI 영향:
- 제공하거나 다시 받아야 할 인계물:

## 검증
- 실행 명령:
- 실제 결과:
- 미실행 항목과 이유:

## 재현·인계
- 적용 커밋:
- 환경·설정:
- 팀원이 확인할 순서:
- 후속 작업·차단 요인:
```

작업·검증·인계가 준비되면 Draft를 `Ready for review`로 바꾼다.

## 15. 리뷰어가 확인하는 순서

GitHub의 `Files changed`에서 다음을 확인한다.

1. PR 목적과 관계없는 파일이 섞이지 않았는가.
2. 빌드 결과·로그·비밀·대형 자료가 포함되지 않았는가.
3. ECU와 IVI의 인터페이스가 ICD와 일치하는가.
4. 계획·구현·시험 ID와 실제 결과가 연결됐는가.
5. 미실행 항목이 성공처럼 쓰이지 않았는가.
6. 상대 담당자가 재현할 정보가 있는가.

로컬에서 상대 브랜치를 확인해야 하면 현재 사용자 변경·stage를 먼저 보존하고, 전환 가능한 상태에서 정확한 브랜치 이름으로 실행한다.

```powershell
git fetch origin
git switch --track "origin/<상대 작업 브랜치>"
git status
```

이미 같은 이름의 로컬 브랜치가 있으면 `--track`을 반복하지 말고 해당 브랜치로 이동한 뒤 pull한다.

## 16. 최신 develop을 작업 브랜치에 반영

개인 작업 중 다른 PR이 먼저 `develop`에 병합되었다면, 현재 작업과 stage를 정리한 뒤 다음 순서로 반영한다. AI에게는 이 통합 작업까지 요청했을 때만 실행하도록 한다.

```powershell
git fetch origin
git switch "<내 작업 브랜치>"
git merge origin/develop -m "chore(repo): 최신 develop 변경 통합"
```

충돌이 없으면 시험을 다시 실행하고 push한다.

```powershell
git push
```

충돌이 있으면 다음 순서로 처리한다.

```powershell
git status

# 충돌 파일을 열어 양쪽 변경의 의미를 확인하고 직접 수정
git add -- "<충돌을 해결한 파일>"

git status
git diff --cached --check
git diff --cached
# 충돌 해소와 관련 검증을 마친 뒤 실행
git commit -m "chore(repo): 최신 develop 변경 통합"
git push
```

공동 계약·상태표·시험 기대값의 충돌은 자신의 쪽만 선택해 해결하지 않는다. 상대 담당자와 의미를 확인하고 관련 시험을 다시 실행한다. 공유 브랜치 이력을 다시 쓰는 `git push --force`를 사용하지 않는다.

## 17. PR 병합과 브랜치 정리

작업 브랜치에서 `develop`으로 병합할 때 GitHub의 `Squash and merge`를 사용한다. GitHub가 제시한 squash 커밋 메시지도 `type(scope): 한글 한 줄 요약`에 맞춰 확인한다. 병합 후 GitHub에서 원격 작업 브랜치를 삭제할 수 있다.

로컬에서는 다음처럼 최신화한다.

```powershell
git switch develop
git pull --ff-only origin develop
git fetch --prune
git log --oneline --decorate -5
```

Squash merge를 사용하면 일반 삭제가 거부될 수 있다. PR이 병합됐고 필요한 변경이 `develop`에 들어간 것을 확인한 뒤에만 로컬 작업 브랜치를 삭제한다.

```powershell
git branch -D "<병합 완료를 확인한 작업 브랜치>"
```

`-D`는 로컬 브랜치를 강제로 삭제한다. PR 병합·미반영 변경·브랜치 이름을 먼저 확인한다. 확실하지 않으면 삭제하지 않아도 된다.

## 18. 자주 발생하는 실수와 안전한 처리

### 18.1 잘못 add한 파일 빼기

**내가 이번에 잘못 stage한 범위만** 취소한다. 기존 사용자 stage를 AI가 임의로 비우면 안 된다.

이미 첫 커밋이 존재하고, 선택한 파일의 stage 전체를 취소해도 되는 경우:

```powershell
git restore --staged -- "<파일 경로>"
git diff --cached --name-status
git status --short
```

`--staged`는 index만 변경해 작업 파일 내용은 유지한다. 옵션을 빼고 실행하면 의미가 달라지므로 그대로 사용한다. [Git restore 설명](https://git-scm.com/docs/git-restore)

같은 파일에 보존해야 할 staged 조각이 있으면 파일 전체를 취소하지 않는다. 내가 추가한 조각만 골라 취소할 수 있을 때 다음을 사용한다.

```powershell
git restore --staged -p -- "<파일 경로>"
```

아직 최초 커밋 전이면 HEAD가 없어 위 기본 restore가 실패할 수 있다. **첫 등록에서 잘못 추가한 파일 하나**를 제외하려면 아래처럼 index에서만 제거하고 내용을 다시 확인한다.

```powershell
git rm --cached -- "<첫 등록에서 제외할 파일>"
git status --short
```

`--cached`를 빼거나 `-f`로 강제하지 않는다. 거부되면 원인을 먼저 확인한다. 전체 `git restore --staged .`는 다른 사람의 stage까지 취소할 수 있으므로 이 매뉴얼의 기본 복구 방법으로 사용하지 않는다.

### 18.2 아직 커밋하지 않았는데 브랜치를 잘못 선택한 경우

현재 수정을 유지하면서 올바른 브랜치를 만든다.

```powershell
git status --short
git switch -c "<올바른 작업 브랜치>"
git branch --show-current
```

### 18.3 pull이 거부된 경우

```powershell
git status --short
git branch --show-current
git fetch origin
```

현재 수정·브랜치·원격 차이를 확인한다. 원인을 모른 채 `reset --hard`, 강제 push, 파일 삭제를 실행하지 않는다.

### 18.4 비밀이나 대형 파일을 발견한 경우

커밋 전이면 해당 파일을 공개하지 말고 18.1절에 따라 stage에서 제거한다. 다른 사용자가 stage한 경우에는 노출 없이 소유자와 조치 범위를 확인한다. `.gitignore` 적용 여부도 확인한다.

```powershell
# 첫 커밋이 존재하고 해당 stage를 취소할 범위가 확인된 경우
git restore --staged -- "<파일 경로>"
git check-ignore -v -- "<파일 경로>"
git status --short
```

이미 GitHub에 push했다면 단순 삭제 커밋만으로 과거 이력에서 비밀이 사라지지 않는다. 해당 키·토큰을 즉시 폐기·교체하고 저장소 소유자와 이력 정리 방법을 결정한다.

## 19. 공동 문서·ICD 변경 절차

ICD·CAN ID·DLC·바이트 레이아웃·SecOC 입력·HAL API에 영향을 줄 가능성이 있으면 코드를 먼저 확정하지 않는다.

1. Issue에 변경 이유와 영향을 적는다.
2. ECU·IVI·SecOC·시험 영향을 정리한다.
3. 사용자 승인을 받는다.
4. 공동 편집 담당 한 명을 정한다.
5. `docs/common-...` 작업 브랜치를 만든다.
6. ICD, SRS, 양측 SDD, TEST_PLAN, 구현, 시험을 같은 변경 단위로 연결한다.
7. 양측 리뷰와 필요한 검증 후 `develop`에 병합한다.

```powershell
git switch develop
git pull --ff-only origin develop
git switch -c docs/common-icd-secoc
```

승인되지 않은 계약 후보는 현행 ICD를 대체한 것처럼 커밋 메시지나 PR에 쓰지 않는다.

## 20. 보안 실험 파일의 형상관리

Git으로 관리할 대상:

```text
실험 실행·분석 코드
작은 고정 입력과 명시적 더미 벡터
실험 설계와 평가 기준
run manifest와 시행 원장 중 경량 자료
요약 CSV·표·그림 생성 코드
재현 명령과 한계
최종 보고서
```

Git으로 직접 관리하지 않을 대상:

```text
수 GB 원시 CAN 로그
학습 모델 바이너리
대형 영상·패킷 캡처
비밀 키와 장비 자격 증명
재생성 가능한 중간 산출물
```

실험별 기록은 다음 흐름을 유지한다.

```text
Git 커밋
  → docs/aidlc/changes/CHG-<실험작업>/
    → construction/build-and-test/<run-id>/
      → manifest·증거·시도 원장
        → 원자료 위치·SHA-256
          → 분석 코드·표·그래프
            → docs/development/experiments/의 최종 보고서
```

합성·vcan·물리 CAN을 구분하고 없는 수치를 추정해서 넣지 않는다.

## 21. develop에서 main으로 통합하고 릴리즈

공동 통합 시험과 양측 인수가 끝난 뒤 GitHub에서 `develop → main` PR을 만든다. 작업 PR과 달리 `Create a merge commit`을 사용한다.

병합 뒤 로컬 `main`을 최신화한다.

```powershell
git switch main
git pull --ff-only origin main
git log --oneline --decorate -5
```

해당 마일스톤의 실제 인수 조건이 충족됐을 때만 태그를 만든다. 공동 규약에 따라 IVI 담당이 양측 승인 후 같은 태그를 한 번만 생성하고 ECU 담당이 증적을 확인한다.

```powershell
git tag -a v0.1.0 -m "M1 accepted baseline"
git push origin v0.1.0
```

M8 최종 인수 뒤의 예시는 다음과 같다.

```powershell
git tag -a v1.0.0 -m "M8 final accepted release"
git push origin v1.0.0
```

공개·인계한 태그를 다른 커밋으로 옮기지 않는다. 수정본은 새 버전으로 발행한다. GitHub Release에는 적용 커밋, ICD·환경 버전, 실행 산출물 해시, 검증 요약, 미실행·한계와 재현 방법을 연결한다.

## 22. 작업별 체크리스트

### 작업 시작 전

- [ ] 기존 사용자 변경·stage·진행 중인 merge/rebase를 확인했는가.
- [ ] 새 작업이라면 `develop`으로 이동했는가.
- [ ] 새 작업이라면 `git pull --ff-only origin develop`으로 기준을 최신화했는가.
- [ ] 새 작업 전용 브랜치를 만들었거나 재개할 기존 브랜치를 확인했는가.
- [ ] 같은 작업 트리의 수정·stage·commit 주체가 한 명인가.
- [ ] 관련 계획·ICD·시험 기준을 확인했는가.
- [ ] 상대 담당자에게 받아야 할 입력을 확인했는가.

### 커밋 전

- [ ] 한 목적의 소스·시험·필수 문서와 이동 전후 파일을 선택했는가.
- [ ] 기존 사용자 stage와 요청 밖 변경이 포함되지 않았는가.
- [ ] 메시지가 `type(scope): 한글 한 줄 요약`인가.
- [ ] 빌드 결과·로그·키·대형 데이터가 포함되지 않았는가.
- [ ] `git diff --cached`로 내용을 읽었는가.
- [ ] `git diff --cached --check`가 통과했는가.
- [ ] 가장 가까운 시험을 실행했는가.
- [ ] 미실행 시험과 이유를 기록했는가.

### PR 전

- [ ] 올바른 작업 브랜치를 push했는가.
- [ ] PR의 base가 `develop`인가.
- [ ] 관련 Issue·계획·FR·TC를 적었는가.
- [ ] ECU·IVI 영향과 인계 내용을 적었는가.
- [ ] 실제 검증 결과와 미검증 범위를 구분했는가.

### 병합 전

- [ ] 상대 담당자의 리뷰를 받았는가.
- [ ] 충돌을 해결한 뒤 관련 시험을 다시 실행했는가.
- [ ] 확인된 CI와 수동 시험이 요구 조건을 만족하는가.
- [ ] 작업 브랜치 → `develop` 병합에 Squash 방식을 선택했는가.

### 릴리즈 전

- [ ] ECU·IVI의 실제 커밋 조합을 기록했는가.
- [ ] 적용 ICD·환경·설정·산출물 해시를 기록했는가.
- [ ] 공동 통합 시험과 양측 인수가 끝났는가.
- [ ] `develop → main` PR을 Merge commit으로 병합했는가.
- [ ] 태그·Release의 버전과 증거가 일치하는가.

## 23. 매일 사용할 최소 명령 요약

아래는 **새 작업을 시작하는 경우**다. 현재 변경과 stage를 확인한 뒤 실행한다. 작업 재개라면 새 브랜치를 만들지 말고 기존 브랜치에서 계속한다. 자리표시자는 실제 값으로 바꾸고 각 명령의 성공을 확인한다. AI의 로컬 커밋 요청에는 마지막 push를 포함하지 않는다.

기능 추가 예시이므로 오류 수정·시험·문서 작업이면 브랜치 타입과 메시지를 바꾼다. scope도 실제 변경에 맞춰 선택한다. add 예시에는 실제로 변경한 파일만 남기고, 대응 문서를 바꾸지 않았다면 그 인수를 생략한다.

### ECU 담당

```powershell
git switch develop
git pull --ff-only origin develop
git switch -c "feat/ecu-<작업명>"

# 작업·시험 후
git status --short
git diff -- adaptive_ecu security
git add -- "<수정한 ECU·security 파일>" "<대응 시험·문서 파일>"
git diff --cached --check
git diff --cached
git commit -m "feat(bsw): <ECU 변경 설명>"
git show --stat --oneline HEAD
git status --short --branch
# 커밋 성공 후 업로드할 경우만
git push -u origin "feat/ecu-<작업명>"
```

### IVI 담당

```powershell
git switch develop
git pull --ff-only origin develop
git switch -c "feat/ivi-<작업명>"

# 작업·시험 후
git status --short
git diff -- ivi_platform
git add -- "<수정한 IVI 파일>" "<대응 시험·문서 파일>"
git diff --cached --check
git diff --cached
git commit -m "feat(hal): <IVI 변경 설명>"
git show --stat --oneline HEAD
git status --short --branch
# 커밋 성공 후 업로드할 경우만
git push -u origin "feat/ivi-<작업명>"
```

### PR 병합 후

```powershell
git switch develop
git pull --ff-only origin develop
git fetch --prune
git status
```

모르는 오류가 발생하면 변경을 삭제하거나 강제 push하지 않는다. `git status`, 현재 브랜치, 실행한 명령과 오류 메시지를 보존해 팀원 또는 담당 AI에게 확인을 요청한다.
