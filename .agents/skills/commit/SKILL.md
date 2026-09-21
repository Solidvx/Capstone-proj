---
name: commit
description: Capstone 변경을 분석해 목적별 커밋과 메시지를 제안한다. 커밋 검토·분리·실행 요청에 사용하며, 분석만 요청받으면 stage·commit하지 않는다.
---

# commit — 단계별 커밋 가이드

Cursor 터미널의 Claude Code·Codex CLI에서 ECU·IVI 모두 아래 순서로 적용한다. [AGENTS.md](../../../AGENTS.md)와 해당 도구의 [CLAUDE.md](../../../CLAUDE.md) 또는 [CODEX.md](../../../CODEX.md)를 따른다. 이미 읽고 변경되지 않은 지침은 재사용한다.
이 파일은 Codex용 배치 경로에 둔 공통 절차다. Claude는 [진입 문서](../../../.claude/skills/commit/SKILL.md)에서 이 원본을 읽는다. 요청 예: **“.agents/skills/commit/SKILL.md에 따라 ECU 변경을 검토해줘.”** 또는 **“같은 지침으로 IVI 변경을 로컬 커밋해줘.”** skill 선택은 커밋 실행 권한을 추가하지 않으며 실제 CLI 인식 여부는 [tooling](../../../docs/development/tooling.md#commit-skill)에서 확인한다.

## STEP 1: 현황 파악

```powershell
git rev-parse --show-toplevel
git status --short --branch
git branch --show-current
git diff --name-status
git diff --cached --name-status
```

1. Git 저장소가 아니면 Git 실행은 중단하고 파일 기반 분석만 한다. 임의로 초기화하지 않는다.
2. 충돌·진행 중인 merge/rebase가 있으면 상태를 보고하고 일반 커밋 절차를 멈춘다.
3. 요청 범위와 기존 staged·unstaged·미추적 목록을 구분한다. 미추적 내용은 `git diff`에 나오지 않는다.
4. 이번 요청에 해당하는 변경이 없으면 안내하고 종료한다.

## STEP 2: 변경사항 분류

1. 같은 디렉토리의 [rules.md](rules.md)를 적용한다.
2. 아래 명령의 경로를 실제 대상으로 바꿔 필요한 diff만 읽고, 관련 미추적 파일은 별도로 읽는다.

```powershell
git diff -- "검토할/파일"
git diff --cached -- "검토할/파일"
```

3. 삭제·추가 쌍은 내용과 참조를 비교해 이동인지 확인한다. 기존 사용자 변경은 별도로 구분한다.
4. **실제 파일 / 변경 유형 / 추천 타입**을 표로 정리한다. 분류 예시는 다음과 같다.

| 영역 | 변경 유형 | 추천 타입 |
|---|---|---|
| ECU `adaptive_ecu/` | 동작 보존 함수 분리 | `refactor(bsw)` |
| 보안 `security/` | 인증 오류 수정과 회귀 시험 | `fix(secoc)` |
| IVI `ivi_platform/` (구현 후) | 상태 표시 기능과 시험 | `feat(ui)` |
| 양측 `docs/`, `plan/` | 담당 설계·시험 문서 수정 | `docs(bms)` 또는 `docs(hal)` |

## STEP 3: 분리 판단

- **한 목적:** 대응 코드·시험·문서를 묶어 진행한다.
- **여러 독립 목적:** 커밋별 포함 파일·변경 조각과 순서를 제안한다.
- **Tidy First:** 필요한 독립적 정리 → 기능/수정 → 필요한 후속 정리·최적화.
- **100줄 이상:** 목적이 섞였는지 확인한다. 줄 수만으로 강제 분리하지 않는다.
- 검토만 요청받았으면 STEP 5의 메시지 추천까지 보고하고 끝낸다. STEP 4·6의 변경 명령은 실행하지 않는다.

## STEP 4: 검증·Staging

1. AGENTS의 Verification Baseline을 적용한다. ECU는 대응 CTest, 보안은 대응 pytest, IVI는 실제 구현·환경의 빌드/시험, 문서는 링크·ID 검사를 선택한다. 미구현 시험 명령을 만들거나 통과했다고 가정하지 않는다.
2. 포함 범위를 구체화한다. 커밋 실행 권한이 이미 있으면 진행하고, 불명확한 대상만 확인한다.
3. 브랜치·대상 내용·기존 stage가 검토 이후 바뀌지 않았는지 재확인한다.
4. 아래에서 **해당하는 예시만** 선택해 실제 파일 경로로 바꿔 stage한다. 요청 밖 변경이 섞인 파일은 전체를 stage하지 않는다.

```powershell
# ECU 예: CAN 송신 변경과 대응 시험
git add -- "adaptive_ecu/src/bsw/can_publisher.cpp" "adaptive_ecu/test/test_can_publisher.cpp"

# IVI 예: 구현 후 실제 소스·시험 경로로 치환
git add -- "ivi_platform/변경소스" "ivi_platform/대응시험"

# 이동이 있을 때
git add -A -- "옛경로/파일" "새경로/파일"

# 커밋에 담길 전체 내용 확인
git diff --cached --name-status -M
git diff --cached --check
git diff --cached
```

일반 commit은 **index 전체**를 담는다. 요청 밖 staged 변경이 있으면 임의로 비우거나 함께 커밋하지 말고 범위를 확인한다.
stage가 비었으면 빈 커밋을 만들지 않는다. 이동의 삭제·추가 포함 여부를 확인하되 `R100`을 강제하지 않는다.
stage 실패는 해결하고 포함 범위를 재확인한 뒤 진행한다. 검증 실패·미실행은 원인과 범위를 보고하며, 미완성 작업 저장을 명시적으로 요청받은 경우에만 그 검증 상태를 밝혀 커밋한다.

## STEP 5: 커밋 메시지 추천

1. 실제 커밋 대상의 핵심을 `type(scope): 한글 한 줄 요약`으로 제안한다.
2. 메시지 선택을 원하는 사용자에게는 2~3개 후보를 제시한다. 실행을 위임받았다면 가장 적합한 메시지를 사용하며 반복 승인을 요구하지 않는다.
3. 검토 모드에서는 stage 여부와 무관하게 이번 요청의 변경만 기준으로 추천하고 종료한다.

## STEP 6: 커밋 실행

확정한 메시지로 한 번 실행한다. 아래 예시 중 실제 변경에 맞는 형식으로 작성한다.

```powershell
# ECU 예
git commit -m "fix(bsw): CAN 송신 오류 처리 수정"
# IVI 예
git commit -m "fix(hal): CAN 수신 오류 처리 수정"
```

성공 여부를 확인한다. 실패 시 원인을 확인하고 hook 우회·이력 재작성을 임의로 하지 않는다.
hook이 파일을 바꾸면 변경 내용을 다시 검토하고 필요한 검증을 수행한다.

## STEP 7: 반복·완료 보고

```powershell
git show --stat --oneline HEAD
git status --short --branch
```

1. 커밋 성공 후 실제 해시·메시지·포함 파일을 확인한다.
2. **요청 범위의 남은 묶음만** STEP 4부터 반복한다. 상태가 달라졌으면 STEP 2에서 재분류한다.
3. 커밋 목록, 검증 결과·미실행 이유, 남은 작업과 원격 반영 여부를 짧게 보고한다.
4. 무관한 변경까지 커밋해 작업 트리를 비우지 않는다. push·PR·태그는 요청받은 경우만 별도로 진행한다.
