# CHG-001 — 커밋 지침 배치와 문서 충돌 정정

2026-09-10 사용자 요청: 마지막 검토에서 발견한 모든 문제를 해결한다.

- 기존 커밋 문서 3개를 합의한 위치로 이동하고 Claude용 공통 절차 진입 문서를 추가한다.
- 공동 협업 규약의 위험한 시험 정리 명령, 커밋·브랜치 예시 불일치, Claude의 보조 skill 해석을 정정한다.
- 루트 지침, 문서 목록, 상세 매뉴얼, 구조 안내·현재 경로 매핑을 동기화한다. 과거 이력과 baseline은 보존한다.
- 제품 소스·ICD·요구사항·시험 계약은 변경하지 않는다. Git 초기화·커밋·push·hook/MCP 활성화는 수행하지 않는다.

원본은 [AGENTS](../../../../AGENTS.md), [공동 협업 규약](../../../../plan/detail/common/00_협업_규약.md), [문서 배치 기준](../../../development/README.md#document-placement)이다. 커밋 규칙의 상위 운영 기준은 공동 규약을 유지한다.

검증 기준: 문서 링크·앵커·코드 펜스, skill frontmatter·공통 원본 연결, PowerShell 명령 블록 구문, 현재 파일 목록과 path-map 일치, 수정 전후 해시와 차이 대조. 실제 CLI 인식·GitHub 보호 규칙 동작은 정적 배치 검증과 구분한다.

진행 상태는 [aidlc-state](aidlc-state.md), 결과와 한계는 [audit](audit.md)에 기록한다.
