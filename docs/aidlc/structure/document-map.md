# 원본·운영 문서·작업 기록 매핑

2026-09-10 구조 적용 기록. [개선안](../../../프로젝트구조개선.md)은 적용 전 제안과 당시 상태를 보존한다. 그 문서의 미생성·문서 수 설명은 적용 전 기준이며, 적용 후 배치·검증의 원본은 이 기록이다. 기존 문서를 최신화하려고 본문을 고치지 않았다.

| 기존 원본·연결점 | 신규 연결 | 방향·역할 |
|---|---|---|
| [AGENTS](../../../AGENTS.md), [루트 SKILL](../../../SKILL.md), [CODEX](../../../CODEX.md), [CLAUDE](../../../CLAUDE.md) | [workflow](../../development/workflow.md), 참조형 skill | 신규→기존 정책·고유 절차. 원본 본문 유지 |
| [ICD](../../ICD.md), [SRS](../../SRS.md), [SDD-ECU](../../SDD-ECU.md), [SDD-IVI](../../SDD-IVI.md), [TEST_PLAN](../../TEST_PLAN.md), [ADR](../../ADR.md), [TARA](../../TARA.md), [CI 명세](../../CICD_SPEC.md) | [분야별 안내](../../development/README.md), 향후 작업 spec·evidence | 신규→원본 절·FR/NFR/TC/ADR. 원본 우선순위 유지 |
| [ECU](../../../plan/ECU.md), [IVI](../../../plan/IVI.md), [공동 규약](../../../plan/detail/common/00_협업_규약.md) | 작업별 요구·계획·상태 기록 | M1~M8·과제 ID·담당·선행조건 연결; 독립 일정 복제 없음 |
| 기존 development 11개 | [운영 인덱스](../../development/README.md) | 신규→기존 결정·후보·역사 기록. 실질 내용 보존. 현재 위치는 아래 최신 배치 기준 참조 |
| adaptive_ecu/, security/ | 향후 construction 작업 기록 | 기록→실제 소스·시험 경로; 제품 소스 이동·복제 없음 |
| [루트 안내](../../../README.md), [문서 목록](../../README.md) | [운영 안내](../../development/README.md), [AIdlc](../README.md) | 기존→신규 탐색 링크만 추가 |
| [구조 개선안](../../../프로젝트구조개선.md) §4·9·12·15 | 이 structure/ 및 운영 문서 | 이번 구조 배치·보존 검증. 후속 자동화와 구분 |

현재 전체 파일 경로·유지/추가 구분은 [path-map.csv](path-map.csv)를 단일 목록으로 사용한다(tmp/ 제외). [골격 배치 목록](scaffold-paths.json)은 선배치 단계의 부분 목록이며 전체 목록이 아니다. [최초 baseline](baseline.sha256)·[최초 검증](verification.md)은 당시 보존 기록이고, 후속 배치는 [골격 적용](scaffold-application.md), 최신 참조 정정은 [참조 변경](reference-changes.md)을 따른다.

참조형 skill: [Codex 후보](../../../.agents/skills/capstone-workflow/SKILL.md) · [Claude 후보](../../../.claude/skills/capstone-workflow/SKILL.md). 두 문서는 같은 공통 원본을 가리킨다. 로딩·MCP·hook 활성화는 미검증·미실행이며 [tooling](../../development/tooling.md)에서 후속 조건을 확인한다.


## 선배치 구조와 원본 연결

| 실제 배치 | 원본·역할 | 상태 |
|---|---|---|
| [작업 템플릿](../changes/README.md) | 개선안 §4·5·7, 작업별 요청·상태·설계·증거 위치 | CHG-template/unit-template은 복사용이며 실제 작업 ID 아님 |
| [운영 도구](../../../tools/workflow/README.md) | 개선안 §12~15, 공통 로직·CLI·MCP·도구 시험 | 골격 생성, 기능 미구현 |
| [Claude 설정 설명](../../../.claude/README.md)·[Codex 설정](../../../.codex/config.toml) | 개선안 §12.2, 도구별 연결 위치 | 빈 설정, 연결 미활성화 |
| [IVI 경계](../../../ivi_platform/README.md) | IVI 계획·SDD-IVI, Node B 구현 위치 | 목적 안내만 존재, 제품 소스 없음 |

path-map의 preserve/reference_only는 최초 구조 적용 기준선과의 관계다. 추가된 파일은 add로 유지하며 이후 문서 참조 수정은 reference-changes에서 별도로 확인한다. 실질적인 제품 구현 상태는 이 배치 구분으로 판정하지 않는다.


[자동화 지침](../../development/tooling.md#automation)은 반복 작업 선정·skill/CLI/hook 역할·외부 및 자체 MCP의 도입 기준을 설명한다. workflow는 사용 시점, tooling은 실제 구현·연결 상태를 관리하며 기존 공식 지침·계약은 유지한다.


[협업 전략](../../development/governance/협업_형상관리전략.md#collaboration)은 공동 협업 규약·연계 의존성을 두 담당자의 저장소·PR·통합 운영에 적용하는 안내다. 기존 규칙·인계표의 원본을 대체하지 않는다. 운영 README와 workflow에서 이 문서로 연결한다.


[형상관리 전략](../../development/governance/협업_형상관리전략.md#configuration)은 공동 규약·ECU M5·공식 시험 원본을 기준으로 코드·환경·실험 설계·원자료·분석·릴리즈·최종 보고서의 식별과 재현을 연결한다. 협업 전략은 역할·PR 운영, 형상관리 전략은 기준본·증거 계보를 담당하며 원본 실험 조건을 대체하지 않는다.


## development 카테고리 통합 — 2026-09-10

카테고리 통합 당시 development 최상위 문서를 17개에서 14개로 줄였다. 이후 이 중 11개를 목적별 하위 폴더로 이동하여 현재 최상위는 3개다. 기존 하위 디렉터리는 유지했다. 현재 목록은 [운영 README](../../development/README.md)와 [전체 경로 목록](path-map.csv)을 따른다. 과거 구조도·검증 기록의 파일 수는 해당 시점의 기록이다.

| 통합 전 원문 | 현재 원본·구역 | 처리 |
|---|---|---|
| 협업전략.md | [협업·형상관리 Part 1](../../development/governance/협업_형상관리전략.md#collaboration) | 본문 보존 후 기존 파일 제거 |
| 형상관리전략.md | [협업·형상관리 Part 2](../../development/governance/협업_형상관리전략.md#configuration) | 본문 보존 후 기존 파일 제거 |
| 자동화지침.md | [tooling Part 1](../../development/tooling.md#automation) | 본문 보존 후 기존 파일 제거 |
| tooling.md | [tooling Part 2](../../development/tooling.md#tooling-runtime) | 기존 경로 유지 |
| 인증이벤트_전달_설계안.md | [전달 설계 Part 1](../../development/security/인증이벤트_전달_설계안.md#delivery-design) | 통합 당시 경로 유지, 이후 security/로 이동 |
| 인증이벤트_전달_사전검증.md | [전달 설계 Part 2](../../development/security/인증이벤트_전달_설계안.md#delivery-precheck) | 본문 보존 후 기존 파일 제거 |

원문별 SHA-256은 각 통합본의 머리말에 있다. 제목 단계·참조·명시 앵커의 가역 변환으로 원문을 보존했다. 최초 부분 모형의 12개 검사를 최신 규약이나 실장비 인수로 확대하지 않는다. 상세 변경·검증은 [참조 기록](reference-changes.md)을 따른다.

<a id="current-development-layout"></a>

## 최신 development 배치 — 2026-09-10

최상위에는 README.md·workflow.md·tooling.md를 유지한다. 기존 최상위 문서 중 11개를 아래와 같이 이동했다. 이동 자체는 내용 변경 없이 수행했고 이후 별도 요청으로 상대 링크·외부 참조·경로 매핑을 정정했다.

| 현재 위치 | 이동한 문서 |
|---|---|
| `docs/development/governance/` | 협업_형상관리전략.md, 의사결정_기록.md |
| `docs/development/security/` | 인증이벤트_전달_설계안.md, 인증이벤트_메시지_상태규약.md, CAN_세션인증_설계안.md, 보안계획_구현전_인계_및_진행현황.md |
| `docs/development/environment/` | 안드로이드_환경설정.md |
| `docs/development/experiments/` | SOC_합성실험_결과.md |
| `docs/development/reviews/` | 계획_검토.md, 문서_종합정합성_검토.md, 정리_이력.md |

playbooks/·templates/·verification/·q2_validation/는 기존 위치를 유지한다. 새 문서의 배치 기준 원본은 [운영 README](../../development/README.md#document-placement)이며 [workflow](../../development/workflow.md)에서 생성·이동 전에 확인한다. 협업·형상관리와 자동화 안내도 이 기준을 참조한다. 공식 계약·계획·작업 기록의 원본 역할은 그대로 유지한다.

[path-map.csv](path-map.csv)의 original_path는 과거 원본 위치, applied_path는 현재 위치다. action과 reason은 최초 등록·구조 적용 당시 기록이며 이후 본문이 바이트 단위로 불변이라는 보증이 아니다. 후속 참조 정정은 [변경 이력](reference-changes.md#development-layout-sync)에 연결한다. 과거 baseline·골격 목록·검증 결과는 당시 증거로 보존한다.

[프로젝트 구조 사용 안내](../../development/governance/프로젝트구조_사용안내.md)를 신규 추가했다. 루트 README·공식 문서 목록·운영 인덱스에서 연결하며, 기존 11개 이동 문서에 추가된 governance/ 안내다. 배치 기준·공식 원본·작업 기록을 탐색하는 역할로 사용한다.

<a id="commit-guidance-layout"></a>

## 커밋 지침 배치·정합성 정리 — 2026-09-10

[사람용 매뉴얼](../../development/governance/commit.md)은 governance/에, [공통 커밋 절차](../../../.agents/skills/commit/SKILL.md)와 [규칙](../../../.agents/skills/commit/rules.md)은 Codex skill 경로에 배치했다. [Claude 진입 문서](../../../.claude/skills/commit/SKILL.md)는 이 공통 원본을 참조한다. 기존 capstone-workflow와 루트 SKILL의 역할을 유지하며 커밋 작업에서만 상세 지침을 읽는다.

기존 루트의 커밋 문서 3개는 위 위치로 이동했고 비워진 폴더만 제거했다. 최초 생성 위치·규칙은 [과거 기록](reference-changes.md)에 보존하며 현행 탐색에는 path-map의 applied_path를 사용한다. 변경 범위·검증·미실행 항목은 [CHG-001](../changes/CHG-001/aidlc-state.md), 실제 사용 조건은 [tooling](../../development/tooling.md#commit-skill)에 연결한다. 현재 파일 목록은 199개(tmp/ 제외)다.

## IVI Qt Plan B 기준 동기화 — 2026-09-22

[IVI Plan B 진행·구조 안내](../../development/governance/IVI_Plan_B_진행상황_및_구조_안내.md)를 governance에 추가했다. 이 문서는 IVI 담당자의 탐색·인계용이며 공식 계약은 ICD/SRS/SDD-IVI/TEST_PLAN, 실행 순서는 plan/IVI와 Plan B 전환 계획이 원본이다. 변경 범위와 검증은 [CHG-002](../changes/CHG-002/aidlc-state.md)에 기록한다.

## IVI Qt Plan B P1 구현 — 2026-09-22

[CHG-003](../changes/CHG-003/aidlc-state.md)은 로컬 보관본과 ECU 제공물을 기준으로 선택 이관한 IVI P1 구현, 실제 core 빌드·시험, P2~P6 상태를 연결한다. 제품 코드는 `ivi_platform/`, 변경 설명은 [P1 구현 결과](../changes/CHG-003/construction/P1_구현_결과.md), 실제 명령과 제한은 [P1 증거](../changes/CHG-003/construction/build-and-test/evidence.md)에 있다. Qt 화면·Linux vcan·물리 CAN은 이 기록에서 통과로 판정하지 않는다.
