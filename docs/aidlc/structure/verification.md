# 구조 적용·보존 검증

적용일: 2026-09-10. 대상: 현재 Capstone-proj 작업 폴더. Git 메타데이터가 없어 파일 목록·SHA-256과 참조 diff로 검증한다.

## 적용 범위

[개선안](../../../프로젝트구조개선.md) §4·9·12·15의 구조 적용 행에 따라 운영 안내·참조형 플레이북·양식·검증 시나리오·AIdlc 안내·매핑·보존 증거와 참조형 skill 문서를 추가했다. 제품 코드·설정·공식 요구·설계·시험·사용자 답변·기존 계획의 내용과 경로는 유지한다.

[파일 매핑](path-map.csv)은 기존 138개와 신규 21개 파일을 열거한다. 신규 문서는 docs/development/에 13개, docs/aidlc/에 6개, 도구별 참조형 skill 2개다. 기존 development 최상위 문서 11개는 모두 보존했고 새 최상위 안내 3개를 추가했다. 기존 문서의 과거 개수·미생성 설명은 적용 전 기록으로 보존하며 현재 배치는 이 기록과 운영 인덱스를 따른다.

기존 파일 중 README.md와 docs/README.md의 신규 탐색 연결만 추가했다. [참조 변경 diff](reference-changes.md)가 변경한 모든 줄과 사유를 기록한다. 다른 기존 파일은 [적용 전 SHA-256](baseline.sha256)과 동일해야 한다. 기준선은 tmp/를 제외한 적용 전 프로젝트 파일 전체다. 기존 tmp 자료는 삭제·이동하지 않았으며 이번 검사기의 임시 산출물은 tmp/structure_apply_20260910/와 tmp/doc_render_review/에 둔다.

## 검증 결과

- 기존 138개 파일 중 136개는 SHA-256 동일, 나머지 2개는 기존 전체 바이트를 그대로 접두부로 보존하고 탐색 링크만 추가했다. 삭제·이동 0개, 신규 21개다.
- 참조형 skill 포함 Markdown 78개·링크 1,500개 렌더링 검사에서 신규 경로·앵커 오류 0건이다. plan/_archive/IVI.md의 기존 상대 링크 5건은 보관본 안내에 대응 경로가 있는 기존 예외로 유지한다.
- 신규 문서의 코드 펜스·표 열 수와 매핑 목록, 기존 개발 문서 11개의 인덱스 연결을 확인했다.
- 두 skill의 필수 name/description·폴더명 일치와 링크를 검사했다. 번들 quick_validate.py는 PyYAML 미설치로 실행 불가였으며 단순 frontmatter와 참조는 표준 라이브러리 검사로 대체했다. 실제 제품 로딩은 검증하지 않았다.
- 새 문서만 대상으로 정적 검증했다. 제품 코드·빌드 입력·import·공식 계약은 바이트 동일성을 확인했으므로 이번 배치에서 제품 빌드·장비 시험을 실행하지 않았다.

재현 자료: tmp/structure_apply_20260910/verify.py 및 result.json, tmp/doc_render_review/audit-structure.mjs 및 render-audit.json. 임시 경로는 운영의 필수 의존성이 아니며 보존 판정·매핑·기존 참조 diff는 이 structure/에 남긴다.

## 적용하지 않은 후속 범위

- 실제 제품 작업이 아직 없으므로 changes/CHG-번호/와 조건부 inception/construction 하위 폴더는 해당 작업 시작 때 생성한다. 가상 완료 기록은 없다.
- tools/workflow/ CLI·MCP 코드와 .codex/config.toml·hook 설정은 생성·활성화하지 않았다.
- 참조형 skill 파일 배치와 실제 도구의 자동 탐색·로딩은 다르다. 자동 로딩·MCP 연결·hook 이벤트·도구 전환 재개 시험은 미실행이다.
- IVI 제품 코드·새 정책·실장비 시험은 이번 구조 적용 범위 밖이다. 기존 제품 시험을 수행한 것으로 표시하지 않는다.

현재 사용할 수 있는 것은 [수동 작업 흐름](../../development/workflow.md)과 문서·양식이다. 후속 자동화의 선행조건은 [tooling](../../development/tooling.md), 실제 시나리오는 [steering-tests](../../development/verification/steering-tests.md)를 따른다.
