# Claude 작업 안내

공통 규칙은 [AGENTS.md](AGENTS.md)의 HARD RULES, Source of Truth, Default Workflow, Verification Baseline, Definition of Done을 따른다. 공통 규칙·명령·인터페이스 변경 게이트를 이 파일에 복제하지 않는다.

## 시작

현행 실행 계획은 [ECU](plan/ECU.md), [IVI](plan/IVI.md), [공동 상세](plan/detail/common/)다. Plan 원문은 `plan/_archive/`에 보관하며 별도 `Plan/` 폴더는 없다.

1. AGENTS의 Project Snapshot을 실제 파일 상태로 재확인한다.
2. 비단순 작업은 [SKILL.md](SKILL.md)의 해당 플레이북을 적용한다. 커밋 작업은 [Claude commit 진입 문서](.claude/skills/commit/SKILL.md)를 통해 공통 절차를 적용한다.
3. [초기 제안서](docs/archive/project-overview.md)는 배경 자료다. 현재 구현·진행 상태의 근거로 사용하지 않는다.

## 근거와 검토

- 파일·함수·시험 ID·명령은 현재 파일에서 확인한 뒤 인용한다.
- 결함이나 개선 항목은 기존 보고서의 ID가 있으면 이어 쓰고 재번호·재사용하지 않는다. 기존 보고서가 없으면 새 체계를 사용한다고 명시한다.
- 대형 보고서는 표와 상세 항목의 건수, 인용 원문, ID 대응을 자체 검사한다.
- 일반 엔지니어링 원칙과 안티패턴은 루트 SKILL의 작업 판단 절에 통합했다. 통합된 과거 보조 지침을 중복해서 읽을 필요는 없으며, 현재 작업에 해당하는 `capstone-workflow`·`commit` skill은 적용한다.

IVI 플랫폼의 현행 기준은 [ADR-010](docs/ADR.md#adr-010)과 [Qt 실행 계획](plan/IVI_PLAN_B_전환계획.md)이다. 과거 Android 절차를 현재 작업 지시로 사용하지 않는다.
