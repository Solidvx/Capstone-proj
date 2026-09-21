# CHG-001 검증 기록

대상과 기준은 [spec](spec.md), 진행 상태는 [aidlc-state](aidlc-state.md)를 따른다.

## 변경·검증

| 검증 | 결과 |
|---|---|
| 기존 커밋 문서 이동 | 3개 모두 새 위치에 존재. Claude용 진입 문서 1개 추가. 옛 폴더는 비어 있음을 확인한 뒤 제거 |
| 공통 규칙·절차 | STEP 1~7, 타입 6개, 한글 메시지·Tidy First·ECU/IVI 범위 유지. 공통 절차 1곳과 Claude 참조 연결 확인 |
| 명령·운영 기준 | 위험한 시험 push·hard reset 두 곳 제거. 보호 규칙 검증 절차 단일화. 한글 type(scope) 예시·작업 브랜치 접두사·develop 승인 1회 기준 일치 |
| 참조·본문 구조 | 전체 Markdown 111개를 markdown-it·GitHub slug 규칙으로 검사. 현행 링크·앵커·중복 ID·코드 펜스 오류 없음 |
| 역사 보관 예외 | plan/_archive/IVI.md의 기존 상대 링크 5개만 남음. 보관 안내에 따른 예외이며 이번 변경 전후 파일 해시 동일 |
| PowerShell | 매뉴얼·공통 규칙·절차의 명령 블록 66개를 PowerShell Parser로 검사, 구문 오류 0개. 명령 실행 성공을 뜻하지 않음 |
| skill 구조 | 두 진입 문서의 name=commit, description, plain-scalar frontmatter, 공통 참조 경로 확인 |
| 파일 매핑 | tmp/ 제외 실제 파일 199개와 path-map applied_path 199개 일치·중복 없음 |
| 보존 범위 | 기존 195개 중 177개는 해시 동일. 15개는 관련 문서·매핑 수정, 3개는 이동·참조 정정. 추가 4개는 Claude 진입 문서와 CHG 기록 3개 |

검사 자료는 `tmp/commit-guidance-migration/`의 `render-audit.json`, `powershell-blocks.json`, `before.sha256.json`, `final.sha256.json`, `verification.json`, `changes.diff`에 있다. 문서 검사는 `node tmp/doc_render_review/audit-commit-guidance.mjs`, 범위·매핑 검사는 `python -X utf8 tmp/commit-guidance-migration/verify.py`로 재현한다. PowerShell 블록은 실행하지 않고 `[System.Management.Automation.Language.Parser]::ParseInput`으로 구문만 확인했다.

skill-creator의 `quick_validate.py`는 두 경로에 실행을 시도했으나 현재 Python의 PyYAML 미설치로 동작하지 않았다. 별도의 의존성 설치 없이 이번 frontmatter가 사용하는 name·description의 단순 문자열 문법과 이름·길이·미완성 표식, 파일 링크·코드 펜스를 대체 검사했다. 범용 YAML 파서 검증이나 실제 CLI 로딩 통과로 확대하지 않는다.

## 환경과 보존

2026-09-10, Windows PowerShell. 프로젝트 Git 메타데이터는 없다. 수정 전 tmp/ 제외 195개 파일의 SHA-256을 확보했다. 임시 백업·검사 자료는 `tmp/commit-guidance-migration/`에 둔다.

실제 제품 빌드·시험, 장비 시험, GitHub 보호 규칙 동작, Claude/Codex의 새 skill 세션 로딩은 이 문서 변경의 검증 결과와 구분한다. Git 초기화·커밋·push 및 설정 활성화는 수행하지 않는다.
