# 개발 운영 안내

기존 정책은 [AGENTS](../../AGENTS.md), 절차는 [루트 SKILL](../../SKILL.md), 공식 문서는 [docs 목록](../README.md)을 따른다. 이 인덱스는 직전 최상위 문서 정리 대상 14개와 기존 하위 자료를 역할별로 안내한다. 최상위에는 README.md·workflow.md·tooling.md를 두고, 나머지 11개 문서는 governance/·security/·environment/·experiments/·reviews/에 분류한다. 기존 하위 디렉터리는 유지한다.

<a id="document-placement"></a>

## 새 문서 배치 기준

문서를 생성하기 전에 기존 문서에 포함할 내용인지 먼저 확인한다. 같은 목적의 문서를 중복 생성하지 않으며, 새 문서가 필요하면 아래 기준에 따라 주된 사용 목적에 맞는 한 곳에 배치한다. 다른 분류에서는 원문을 복제하지 않고 링크로 연결한다. 이 절을 배치 기준의 원본으로 사용한다.

| 문서 종류 | 배치 위치 | 예시 |
|---|---|---|
| 협업·저장소·형상관리·공통 의사결정 | `governance/` | 브랜치 운영, 담당자 인계 |
| 보안 상세 설계·규약·구현 인계 | `security/` | IDS 설계 보충, 인증 흐름 |
| 개발 환경 설치·설정 | `environment/` | ECU 환경설정, Linux/Qt 환경 |
| 장기 보존할 실험 분석·결과 보고서 | `experiments/` | SOC 실험, 보안 성능 비교 |
| 여러 계획·문서에 걸친 종합 검토·정리 이력 | `reviews/` | 정합성 검토, 문서 통합 이력 |
| 반복 사용하는 작업 절차 | `playbooks/` | ECU 시험 절차, 문서 검토 절차 |
| 재사용할 문서 양식 | `templates/` | 인계서·검증 증거 양식 |
| 개발 운영·자동화의 검증 시나리오 | `verification/` | hook 동작 검증 절차 |

위 경로는 `docs/development/` 기준이다. 최상위에는 `README.md`, `workflow.md`, `tooling.md`를 유지하고 새 문서는 원칙적으로 목적별 하위 폴더에 둔다. 추가 세분화는 실제 문서가 늘어나 탐색이 어려워질 때 판단한다.

- 특정 작업의 계획·진행·검증 기록은 [AIdlc 작업 기록](../aidlc/changes/README.md)에 따라 `docs/aidlc/changes/CHG-…/`에서 관리한다. `development/`에는 여러 작업에서 계속 참고할 자료를 둔다. 실험 보고서는 실행 증거가 있는 기존 AIdlc 기록에 연결하고 같은 결과를 중복 관리하지 않는다.
- 공식 요구사항·인터페이스 계약·시험 기준·설계 결정은 [공식 문서](../README.md)의 기존 원본에서 관리한다. 보충 문서는 해당 원본과 연결하며 별도 기준을 만들지 않는다. 역할별 실행 일정·과제는 [ECU](../../plan/ECU.md)·[IVI](../../plan/IVI.md)와 연결된 `plan/` 문서에서 관리한다.
- 임시 분석·중간 출력은 `tmp/`에 둔다. 제품 코드와 시험 코드는 기존 제품 경로에서 관리한다. 기존 `q2_validation/`은 특정 설계 검증 코드·데이터의 보존 위치이며 새 검증 자료의 공통 저장소가 아니다.
- 문서를 생성하거나 이동하면 이 README의 해당 분류에 링크를 등록·갱신하고, 필요한 [문서 매핑](../aidlc/structure/document-map.md)과 [경로 매핑](../aidlc/structure/path-map.csv)을 함께 정정한다. 변경된 상대 링크·외부 참조·앵커를 검사한다. 인덱스에는 진행 상태를 중복 기록하지 않는다.

## 운영·협업·자동화

- [IVI Plan B 진행·구조 안내](governance/IVI_Plan_B_진행상황_및_구조_안내.md): IVI 현재 상태, M/P 단계, 폴더 구조와 다음 작업

- [작업 흐름](workflow.md): 요청 분류·작업 기록·검증 진입점
- [협업·형상관리 전략](governance/협업_형상관리전략.md): 역할·저장소·PR·인계 및 환경·실험·릴리즈 증거 관리
- [GitHub 형상관리 실행 매뉴얼](governance/commit.md): ECU·IVI별 포함·제외 파일과 최초 등록·브랜치·커밋·PR·릴리즈 명령
- [자동화 지침과 도구 운영](tooling.md): 자동화 원칙과 실제 배치·구현·연결 상태

## 보안 설계·인계

- [인증 이벤트 전달 설계와 사전검증](security/인증이벤트_전달_설계안.md): 전달 설계·최초 부분 모형 검증 기록
- [인증 이벤트 메시지·상태 규약](security/인증이벤트_메시지_상태규약.md): 후보 2 및 최신 상태·송신·장애 정책
- [보안 계획 구현 전 인계·진행 현황](security/보안계획_구현전_인계_및_진행현황.md): 전체 보안 적용 범위·담당·인수 상태
- [CAN 세션 인증 설계안](security/CAN_세션인증_설계안.md): 별도 세션 프로토콜 후보·승인 이력

## 환경·실험·결정

- [Android 환경설정](environment/안드로이드_환경설정.md): superseded된 과거 포팅 조사·인계 자료
- [SOC 합성실험 결과](experiments/SOC_합성실험_결과.md): 특정 실험의 조건·수치·제품 반영 근거
- [의사결정 기록](governance/의사결정_기록.md): 사용자 답변과 결정 원본

## 검토·역사 기록

- [계획 검토](reviews/계획_검토.md): 개선·계획 인수 과정
- [문서 종합정합성 검토](reviews/문서_종합정합성_검토.md): 과거 검증 기록과 Qt 전환 후 개발 재개 안내
- [정리 이력](reviews/정리_이력.md): 구조 변경·삭제·통합의 역사 기록

## 하위 자료

- [ADS1115 → CAN → Qt 전압 표시 진단](playbooks/ads1115-can-smoke.md): 기존 프레임을 사용하는 독립 실측 진단과 제품 통합 경계

- 플레이북: [ECU](playbooks/ecu.md), [보안](playbooks/security.md), [IVI·통합](playbooks/ivi-integration.md), [문서 검토](playbooks/docs-review.md)
- 양식: [작은 변경](templates/change.md), [요청](templates/spec.md), [상태](templates/aidlc-state.md), [판단](templates/audit.md), [증거](templates/evidence.md)
- [운영 검증 시나리오](verification/steering-tests.md)
- [AIdlc 작업 기록](../aidlc/README.md) · [전체 구조·문서 매핑](../aidlc/structure/document-map.md)

2026-09-10 통합: 협업전략+형상관리전략 → 협업_형상관리전략, 자동화지침+tooling → tooling, 인증이벤트 전달 설계+사전검증 → 전달 설계안. 원문별 SHA-256·Part 대응은 각 통합본 머리말, 보존·참조 정정 결과는 [구조 참조 기록](../aidlc/structure/reference-changes.md)에 있다.

처음 참여한 팀원은 [프로젝트 구조 사용 안내](governance/프로젝트구조_사용안내.md)에서 전체 디렉터리·파일별 목적·담당별 작업 예시를 확인한다. 이 안내는 governance/에 추가한 공통 탐색 문서이며 앞서 정리한 14개 문서의 통합 이력과 구분한다.

커밋 규칙·AI 절차의 공통 원본은 [commit skill](../../.agents/skills/commit/SKILL.md), Claude 연결·배치 상태는 [tooling](tooling.md#commit-skill)을 따른다. 사람용 매뉴얼과 AI 지침을 중복 원본으로 관리하지 않는다.

- [IVI Qt 현행 안내 정정 기록](../aidlc/changes/CHG-004/aidlc-state.md)

- [ECU–IVI 하드웨어 연결 가이드](environment/ECU_IVI_하드웨어_연결가이드.html): 기존 배치·사진 기반 전원/ADC/CAN 조립과 점검
