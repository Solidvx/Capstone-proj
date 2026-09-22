# CHG-002 — IVI Qt Plan B P0 문서 동기화

## 요청

IVI 담당자가 이해할 수 있는 현재 진행 상황·M/P 단계·전체 구조 문서를 추가하고, Android 포팅 기준 문서를 Ubuntu/C++17/SocketCAN/Qt Quick Plan B 기준으로 고친다. 기존 main 대상 PR은 닫고 develop 대상 PR을 새로 만든다.

## 범위

- ADR-010 활성화와 ADR-004 대체 표시
- FR-IVI, Node B API, SDD-IVI, TC-IVI/성능 기준 Qt 동기화
- 실행 계획, 현재 상태, 구조·문서 색인 갱신
- Android 상세 문서는 역사 자료로 표시
- CAN ID/DLC/payload/HMAC/counter wire 계약은 유지

## 완료 조건

- P0 문서가 모두 같은 플랫폼·API 경계를 지시한다.
- 새 안내 문서가 인덱스와 path-map에 연결된다.
- Markdown 상대 링크와 diff 형식 검사를 통과한다.
- 변경을 기능 브랜치에 커밋·푸시하고 develop 대상 PR을 만든다.
