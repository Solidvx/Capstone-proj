# Codex 작업 안내

공통 규칙은 [AGENTS.md](AGENTS.md)의 HARD RULES, Source of Truth, Default Workflow, Verification Baseline, Definition of Done을 따른다. 공통 규칙·명령·인터페이스 변경 게이트를 이 파일에 복제하지 않는다.

## 시작과 작업 분기

1. AGENTS의 Project Snapshot을 실제 파일 상태로 재확인한다. Git이 없으면 브랜치를 추정하지 않고 파일 목록·해시로 변경 범위를 확인한다.
2. 비단순 작업은 [SKILL.md](SKILL.md)의 해당 플레이북을 적용한다. 커밋 작업은 [commit skill](.agents/skills/commit/SKILL.md)로 연결한다.
3. 일정·역할 작업은 [ECU](plan/ECU.md), [IVI](plan/IVI.md), [공동](plan/detail/common/00_협업_규약.md)에서 필요한 부분만 읽는다.

## 탐색·편집·보고

- 검색은 `rg --files`와 `rg -n`, 편집은 패치 기반 변경을 우선한다.
- 설명·진단·리뷰는 근거부터 보고하고, 수정 요청이 있을 때 대상 파일을 편집한다.
- 다른 폴더·브랜치의 구현을 발견해도 현재 구현으로 설명하거나 요청 없이 병합하지 않는다.
- 결과는 변경 위치, 실행한 검증, 미검증 범위와 이유를 간결하게 보고한다. 로컬 파일은 가능한 경우 클릭 가능한 절대 경로로 연결한다.

기존 Codex 보조 문서와 미사용 메타데이터는 루트 지침으로 통합했다. 별도 운영 팩을 읽을 필요가 없다.

IVI 플랫폼의 현행 기준은 [ADR-010](docs/ADR.md#adr-010)과 [Qt 실행 계획](plan/IVI_PLAN_B_전환계획.md)이다. 과거 Android 절차를 현재 작업 지시로 사용하지 않는다.
