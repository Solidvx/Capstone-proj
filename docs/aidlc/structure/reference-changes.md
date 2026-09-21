# 기존 문서 참조 변경 기록

허용 사유: 구조에 따른 의존성·매핑·언급 연결. 기존 문서의 제목·정책·수치·명령·ID는 바꾸지 않았다. 변경 전은 아래 diff에서 추가 줄이 없는 상태이며, 후는 추가 링크가 있는 상태다.

### README.md

신규 운영·검증 문서로 이동할 수 있도록 링크만 추가했다. 기존 줄은 동일하다.

```diff
--- README.md (before)
+++ README.md (after)
@@ -29,3 +29,6 @@
 - `ivi_platform/`: 앞으로 구현할 Node B 경로. 빈 자리표시자는 보존하지 않는다.
 
 연구·배경 자료는 [문서 목록](docs/README.md)에서 연결한다. 제품 코드의 존재·완료 여부는 실제 파일과 검증 결과로 확인한다.
+
+
+개발 운영과 작업 기록: [운영 안내](docs/development/README.md) · [AIdlc 구조 적용·보존 결과](docs/aidlc/structure/verification.md).
```

### docs/README.md

신규 운영·검증 문서로 이동할 수 있도록 링크만 추가했다. 기존 줄은 동일하다.

```diff
--- docs/README.md (before)
+++ docs/README.md (after)
@@ -39,3 +39,8 @@
 - [Plan 통합 결과](development/정리_이력.md#part4-planmerge): 원문 보존·24개 과제 대응과 폴더 제거 증거
 
 보관 원문을 읽을 때는 [보관본 안내와 경로 대응](../plan/_archive/README.md)을 먼저 확인한다. 보관본의 과거 일정·상대 링크는 현행 개발 지시가 아니다.
+
+
+## 개발 운영·작업 기록 연결
+
+[개발 운영 안내](development/README.md)에서 기존 개발 문서와 신규 절차·양식을 찾는다. [AIdlc 안내](aidlc/README.md)와 [구조 적용 기록](aidlc/structure/verification.md)은 개별 작업 기록·원본 매핑·내용 보존 근거를 제공한다.
```

영향: 두 인덱스에서 신규 문서를 탐색한다. 기존 앵커·역참조 영향 없음. [검증 결과](verification.md)에서 경로·앵커와 변경 범위를 확인한다.


## 골격 선배치 및 최신 참조 정정 — 2026-09-10

이 절은 앞선 최초 적용 diff 이후의 변경을 추가 기록한다. 현재 전체 목록의 진입점은 [document-map](document-map.md)과 [path-map](path-map.csv)이다. 제품 코드·계약·수치 변경은 없다. 이 기록 자체에는 본 절을 추가했으며 이전 내용은 보존했다.

### 앞선 골격 적용의 README 연결 변경

사유: 생성한 골격·현재 배치 결과를 찾도록 연결. 최초 기준선 해시와 일치하는 기존 접두부를 복원해 대조했다.
#### README.md

```diff
--- README.md before scaffold
+++ README.md after scaffold
@@ -32,3 +32,6 @@
 
 
 개발 운영과 작업 기록: [운영 안내](docs/development/README.md) · [AIdlc 구조 적용·보존 결과](docs/aidlc/structure/verification.md).
+
+
+전체 예정 구조의 선배치 결과: [골격 적용 안내](docs/aidlc/structure/scaffold-application.md).
```
#### docs/aidlc/README.md

```diff
--- docs/aidlc/README.md before scaffold
+++ docs/aidlc/README.md after scaffold
@@ -11,3 +11,6 @@
 inception/은 기존 구현 조사·요구·설계·작업 분해, construction/은 작업 단위별 설계·실제 변경 경로·build-and-test/의 검증 근거를 수용한다. 조건부 폴더는 필요할 때 생성한다. construction/.../code/에도 제품 코드를 복제하지 않고 원래 소스 경로와 변경 요약을 둔다.
 
 향후 작업 인덱스에는 작업 기록의 링크만 추가한다. 과거 계획이나 승인 기록을 새 작업의 완료 증거로 재해석하지 않는다.
+
+
+후속 요청에 따른 전체 예정 경로·템플릿의 선배치 결과는 [골격 적용 안내](structure/scaffold-application.md)를 따른다. 위의 미생성 설명은 선배치 이전 기록이다.
```

### 이번 안내·매핑 정정

사유: 생성 경로와 현재 상태의 언급 정합화, 전체 목록 단일화 및 과거 검증 기록과의 연결. 아래는 이번 변경 전후의 전체 diff다.
#### docs/development/tooling.md

```diff
--- docs/development/tooling.md before alignment
+++ docs/development/tooling.md after alignment
@@ -6,11 +6,11 @@
 |---|---|---|
 | 수동 운영 | [workflow](workflow.md), [루트 SKILL](../../SKILL.md) | 문서를 명시적으로 읽고 기존 검증 명령 사용 가능 |
 | 참조형 skill | .agents/skills/capstone-workflow/SKILL.md, .claude/skills/capstone-workflow/SKILL.md 후보 | 배치 결과는 구조 검증 기록 참조. 실제 자동 로딩 미검증 |
-| 공통 로직 | tools/workflow/core.py 후보 | 미구현; 루트·작업·검사 범위를 받아 공통 결과 반환하는 후속 설계 |
-| CLI | tools/workflow/check.py 후보 | 미구현; text/JSON 결과와 실패·미실행 구분 예정 |
-| MCP | tools/workflow/mcp_server.py 후보 | 미구현·미연결; workflow_status/workflow_check는 제안 이름 |
-| hook | .claude/settings.json 후보 | 미생성·미활성화; 실제 지원 이벤트 확인 후 연결 |
-| MCP 설정 | .codex/config.toml 후보, Claude 위치는 후속 확인 | 미생성; 프로젝트 문서만으로 연결되지 않음 |
+| 공통 로직 | tools/workflow/core.py 후보 | 골격 파일 존재·판정 로직 미구현; 루트·작업·검사 범위를 받아 공통 결과 반환하는 후속 설계 |
+| CLI | tools/workflow/check.py 후보 | 골격 파일 존재·CLI 기능 미구현; text/JSON 결과와 실패·미실행 구분 예정 |
+| MCP | tools/workflow/mcp_server.py 후보 | 골격 파일 존재·서버 미구현·미연결; workflow_status/workflow_check는 제안 이름 |
+| hook | .claude/settings.json 후보 | 빈 JSON 객체로 골격 생성·미활성화; 실제 지원 이벤트 확인 후 연결 |
+| MCP 설정 | .codex/config.toml 후보, Claude 위치는 후속 확인 | 주석 전용 TOML 골격 생성; MCP 서버 등록·연결 없음 |
 
 ## 후속 구현과 확인 순서
 
@@ -27,3 +27,6 @@
 제품명/버전, 실행 방식, 정규화한 프로젝트 루트, 준비 조건, 설정 위치, 실제 호출 명령, 기대·실제 결과, 실패 복구, 대상 해시와 증거 경로를 [증거 양식](templates/evidence.md)에 작성한다. 비밀·토큰·실제 장비 주소는 넣지 않는다. 한 실행 조합의 성공을 다른 조합에 확대하지 않는다.
 
 [운영 검증 시나리오](verification/steering-tests.md) · [배치·검증 결과](../aidlc/structure/verification.md)
+
+
+최신 배치·전체 경로는 [현재 구조 매핑](../aidlc/structure/document-map.md)을 따른다. 골격 존재는 실제 도구 기능·연결 성공을 뜻하지 않는다.
```
#### plan/IVI.md

```diff
--- plan/IVI.md before alignment
+++ plan/IVI.md after alignment
@@ -83,7 +83,7 @@
 
 | 영역 | 상태 | 근거 |
 |---|---|---|
-| `ivi_platform/` | **디렉토리 없음** | IVI 코드가 하나도 없다. 전부 신규 구현 |
+| `ivi_platform/` | **README 골격만 존재** | IVI 코드가 하나도 없다. 전부 신규 구현 |
 | `Dockerfile.arm64`, `toolchain-aarch64.cmake` | **없음** | 루트에 존재하지 않음 |
 | `.github/workflows/` | **없음** | CI 미구현 |
 | AOSP 소스 | 저장소 밖 | 확인 불가 |
```
#### plan/detail/ivi/M1_AOSP_Docker_CI.md

```diff
--- plan/detail/ivi/M1_AOSP_Docker_CI.md before alignment
+++ plan/detail/ivi/M1_AOSP_Docker_CI.md after alignment
@@ -55,7 +55,7 @@
 
 | 대상 | 상태 |
 |---|---|
-| `ivi_platform/` | **디렉토리 자체가 없다** |
+| `ivi_platform/` | **README 골격만 존재, 제품 소스 없음** |
 | `Dockerfile.arm64`, `toolchain-aarch64.cmake` | **없음** |
 | `.github/workflows/` | **없음** |
 | AOSP 소스 | 저장소 밖. 확인 불가 |
@@ -459,7 +459,7 @@
 
 ## 하드웨어·Android 실행 조건 검토 — 2026-09-07
 
-현재 작업 폴더에는 `ivi_platform/`가 없으며 AOSP 외부 트리와 대상 부팅은 확인하지 않았다. 보유 장비는 확인사항 §1에 RPi4 8GB·SanDisk 128GB·MCP2515/TJA1050 8MHz·레벨 컨버터·Touch Display 2로 기록됐다. Android A-1~14 답변은 접수 완료했다. 최신 후보·환경은 [Android 환경설정](../../../docs/development/안드로이드_환경설정.md) §6~7을 따르며 장비 인수는 미완료다. 이 문서의 revision·빌드 명령·기동 경로는 해당 정보와 대조하기 전 확정 절차가 아니다.
+현재 작업 폴더의 `ivi_platform/`에는 목적 안내 README만 있으며 AOSP 외부 트리와 대상 부팅은 확인하지 않았다. 보유 장비는 확인사항 §1에 RPi4 8GB·SanDisk 128GB·MCP2515/TJA1050 8MHz·레벨 컨버터·Touch Display 2로 기록됐다. Android A-1~14 답변은 접수 완료했다. 최신 후보·환경은 [Android 환경설정](../../../docs/development/안드로이드_환경설정.md) §6~7을 따르며 장비 인수는 미완료다. 이 문서의 revision·빌드 명령·기동 경로는 해당 정보와 대조하기 전 확정 절차가 아니다.
 
 | 순서 | 수행·증거 | 다음 단계 조건 |
 |---|---|---|
```
#### docs/development/security/보안계획_구현전_인계_및_진행현황.md

```diff
--- docs/development/보안계획_구현전_인계_및_진행현황.md before alignment
+++ docs/development/보안계획_구현전_인계_및_진행현황.md after alignment
@@ -39,7 +39,7 @@
 | 로컬 Python | Windows Python 3.14.3 | 설계 모형 실행 환경 |
 | 로컬 ssl | OpenSSL 3.0.18, HAS_TLSv1_3=True | 라이브러리 기능 보고만 확인. TLS handshake 성공 증거 아님 |
 | adb/openssl/cmake CLI | 현재 PowerShell PATH에서 찾지 못함 | 다른 경로 설치나 원격 서버 상태까지 부재라고 단정하지 않음 |
-| IVI 소스 | 현재 루트에 ivi_platform 없음 | Android/HAL/TLS 제품 빌드·권한 시험 불가 |
+| IVI 소스 | ivi_platform/에 목적 안내 README만 존재, 제품 소스 없음 | Android/HAL/TLS 제품 빌드·권한 시험 불가 |
 | 원격/실장비 | 이번 작업에서 사용할 노드 연결·실행 세션을 확인하지 못함 | 유선망·RPi·Android 시험 미수행 |
 | 서버 소스 가져오기 | 기존 사용자 담당 | 별도 다운로드/설치/접속 작업을 시작하지 않음 |
 
```
#### docs/development/security/인증이벤트_전달_설계안.md

```diff
--- docs/development/인증이벤트_전달_설계안.md before alignment
+++ docs/development/인증이벤트_전달_설계안.md after alignment
@@ -18,7 +18,7 @@
 
 - 사용자 선택 정본: [공동 선택 기준](../../plan/detail/common/00_협업_규약.md#security-adoption)의 Q2=B. 담당·관문: [공동 연계](../../plan/detail/common/01_연계_의존성.md#security-adoption).
 - [ICD](../ICD.md) §1.1·1.5·2에 따르면 0x200은 Node A→Node B의 비인증 참고 경보다. 이를 역방향 전송에 재사용하거나 새 필드를 끼워 넣지 않는다. 현행 counter/pending 및 승인 목표/세션 후보의 구분을 유지한다.
-- [SDD-IVI](../SDD-IVI.md) §4는 HAL 내부 verifier를 계획한다. 실제 파일 목록에는 ivi_platform이 없으므로 아래 IVI 모듈은 모두 예정이다.
+- [SDD-IVI](../SDD-IVI.md) §4는 HAL 내부 verifier를 계획한다. 실제 ivi_platform/에는 목적 안내 README만 있고 제품 소스가 없으므로 아래 IVI 모듈은 모두 예정이다.
 - 실제 [특징 추출기](../../security/ids/feature_extractor.py), [사양 검출기](../../security/ids/spec_detector.py), [IF 검출기](../../security/ids/if_detector.py)는 존재한다. 현재 특징 추출 입력은 raw CAN 기반 7개 특징이며 인증 이벤트 입력 경로는 없다. 존재 확인은 동작 검증이 아니다.
 - [SDD-ECU](../SDD-ECU.md)·[ADR](../ADR.md)의 예정 ids_engine과 실행 계획의 realtime_ids 이름은 구현 시 호출 관계를 확인해 하나로 정한다. 이 설계가 별도 온라인 IDS를 중복 생성하는 근거가 되지 않는다.
 - 현재 폴더에는 Git 메타데이터가 없어 브랜치/HEAD를 확인하지 못했다. 이번 설계 작업은 파일 목록·해시로 범위를 확인한다.
```
#### docs/development/workflow.md

```diff
--- docs/development/workflow.md before alignment
+++ docs/development/workflow.md after alignment
@@ -13,3 +13,6 @@
 작업 재개 시 상태 원본→연결된 판단·증거→현재 대상 파일 순서로 대조한다. 대상이 바뀌면 과거 통과를 현재 증거로 사용하지 않는다. ICD 변경 판단은 기존 AGENTS의 인터페이스 변경 게이트를 적용한다.
 
 구조 적용 자체의 경로·보존 기록은 [structure](../aidlc/structure/document-map.md)에 둔다. 이 기록을 제품 구현 완료로 간주하지 않는다.
+
+
+구조 선배치 후에는 [CHG 템플릿 안내](../aidlc/changes/README.md)에 따라 이미 생성된 템플릿을 사용한다. 위의 필요 시 생성 원칙은 실제 작업 기록에 적용하며, 템플릿의 존재를 실제 작업 착수로 간주하지 않는다.
```
#### docs/aidlc/structure/document-map.md

```diff
--- docs/aidlc/structure/document-map.md before alignment
+++ docs/aidlc/structure/document-map.md after alignment
@@ -12,6 +12,18 @@
 | [루트 안내](../../../README.md), [문서 목록](../../README.md) | [운영 안내](../../development/README.md), [AIdlc](../README.md) | 기존→신규 탐색 링크만 추가 |
 | [구조 개선안](../../../프로젝트구조개선.md) §4·9·12·15 | 이 structure/ 및 운영 문서 | 이번 구조 배치·보존 검증. 후속 자동화와 구분 |
 
-전체 파일 경로·유지/추가 구분은 [path-map.csv](path-map.csv), 기존 내용 보존은 [baseline](baseline.sha256)과 [참조 변경](reference-changes.md), 현재 결과는 [검증 기록](verification.md)을 따른다.
+현재 전체 파일 경로·유지/추가 구분은 [path-map.csv](path-map.csv)를 단일 목록으로 사용한다(tmp/ 제외). [골격 배치 목록](scaffold-paths.json)은 선배치 단계의 부분 목록이며 전체 목록이 아니다. [최초 baseline](baseline.sha256)·[최초 검증](verification.md)은 당시 보존 기록이고, 후속 배치는 [골격 적용](scaffold-application.md), 최신 참조 정정은 [참조 변경](reference-changes.md)을 따른다.
 
 참조형 skill: [Codex 후보](../../../.agents/skills/capstone-workflow/SKILL.md) · [Claude 후보](../../../.claude/skills/capstone-workflow/SKILL.md). 두 문서는 같은 공통 원본을 가리킨다. 로딩·MCP·hook 활성화는 미검증·미실행이며 [tooling](../../development/tooling.md)에서 후속 조건을 확인한다.
+
+
+## 선배치 구조와 원본 연결
+
+| 실제 배치 | 원본·역할 | 상태 |
+|---|---|---|
+| [작업 템플릿](../changes/README.md) | 개선안 §4·5·7, 작업별 요청·상태·설계·증거 위치 | CHG-template/unit-template은 복사용이며 실제 작업 ID 아님 |
+| [운영 도구](../../../tools/workflow/README.md) | 개선안 §12~15, 공통 로직·CLI·MCP·도구 시험 | 골격 생성, 기능 미구현 |
+| [Claude 설정 설명](../../../.claude/README.md)·[Codex 설정](../../../.codex/config.toml) | 개선안 §12.2, 도구별 연결 위치 | 빈 설정, 연결 미활성화 |
+| [IVI 경계](../../../ivi_platform/README.md) | IVI 계획·SDD-IVI, Node B 구현 위치 | 목적 안내만 존재, 제품 소스 없음 |
+
+path-map의 preserve/reference_only는 최초 구조 적용 기준선과의 관계다. 추가된 파일은 add로 유지하며 이후 문서 참조 수정은 reference-changes에서 별도로 확인한다. 실질적인 제품 구현 상태는 이 배치 구분으로 판정하지 않는다.
```
#### docs/aidlc/structure/scaffold-application.md

```diff
--- docs/aidlc/structure/scaffold-application.md before alignment
+++ docs/aidlc/structure/scaffold-application.md after alignment
@@ -16,6 +16,6 @@
 
 협업 시 공통 기준 커밋에서 분기하고, 실제 작업 ID와 수정 담당을 정한다. 현재 Git 메타데이터는 없으며 이 작업은 저장소 초기화·브랜치 생성·병합을 수행하지 않는다. 골격 배치가 향후 병합 충돌이나 제품 호환성을 보장하지 않는다.
 
-검증 결과는 이번 작업의 [scope-verification.json](scope-verification.json)을 따른다. 기존 경로 매핑·baseline은 이전 구조 적용 기록으로 보존한다. 이번 목록은 [scaffold-paths.json](scaffold-paths.json)이다. 실행 도구·hook·MCP·제품 기능의 구현 완료는 아니다.
+검증 결과는 이번 작업의 [scope-verification.json](scope-verification.json)을 따른다. 최초 baseline은 이전 구조 적용 기록으로 보존한다. [scaffold-paths.json](scaffold-paths.json)은 이번 선배치 단계의 부분 목록이며, 이후 추가·참조 정정을 포함한 현재 전체 목록은 [path-map.csv](path-map.csv), 역할·의존성 진입점은 [document-map.md](document-map.md)이다. 실행 도구·hook·MCP·제품 기능의 구현 완료는 아니다.
 
 구조도에서 추출한 고정·템플릿 경로 73개 모두 존재한다. 이번 신규 파일은 골격·안내 30개와 검증·목록 JSON 2개, 총 32개다. 기존 159개 중 157개는 바이트 동일하며 루트 README와 AIdlc README는 새 적용 기록으로 가는 링크만 추가했다. Python 골격 3개는 구문 검사와 직접 실행 시 미구현 실패 종료를 확인했다. JSON/TOML은 빈 설정으로 파싱된다. 제품 기능과 자동화 연결은 여전히 미구현이다.
```
#### 프로젝트구조개선.md

```diff
--- 프로젝트구조개선.md before alignment
+++ 프로젝트구조개선.md after alignment
@@ -445,3 +445,6 @@
 | 원본 템플릿과의 차이 | 실제 서버 함수·skill 절차·hook 설정을 분석하고 그대로 가져오지 않을 동작 기록 |
 
 이번 보완은 사용자 최신 요청을 반영해 기존 폴더 유지·신규 구조와 문서 추가·기존 실질 본문 보존·최소 제목 및 링크 수정의 경계를 확정했다. 기존 MCP·skill·hook의 원본 구현 설명과 예정 구조는 유지하되, 실행 코드·설정 활성화는 별도 후속 참고 설계로 구분했다. 이번에 수정한 파일은 이 개선안 한 개다. 실제 사용 문서·서버·skill·hook 파일은 생성하지 않았으며, 원본 템플릿과 다른 기존 프로젝트 파일도 수정하지 않았다. 구조 및 도구 구현은 계속 미실행 상태다.
+
+
+현재 적용된 구조·전체 경로·후속 참조 정정은 [구조 매핑](docs/aidlc/structure/document-map.md)을 따른다. 이 개선안의 미생성·당시 파일 수·실행 범위 설명은 제안 작성 시점 기록이며, 사용자 후속 요청에 따른 골격 선배치 결과와 구분한다.
```
#### docs/aidlc/structure/path-map.csv

```diff
--- docs/aidlc/structure/path-map.csv before alignment
+++ docs/aidlc/structure/path-map.csv after alignment
@@ -1,9 +1,14 @@
 original_path,applied_path,action,reason
+,.agents/skills/capstone-workflow/SKILL.md,add,added structure artifact; path existence is not functional completion
+,.claude/README.md,add,added structure artifact; path existence is not functional completion
+,.claude/settings.json,add,added structure artifact; path existence is not functional completion
+,.claude/skills/capstone-workflow/SKILL.md,add,added structure artifact; path existence is not functional completion
+,.codex/config.toml,add,added structure artifact; path existence is not functional completion
 .gitignore,.gitignore,preserve,original bytes retained
 AGENTS.md,AGENTS.md,preserve,original bytes retained
 CLAUDE.md,CLAUDE.md,preserve,original bytes retained
 CODEX.md,CODEX.md,preserve,original bytes retained
-README.md,README.md,reference_only,navigation links only
+README.md,README.md,reference_only,structure/status/reference mapping only; see reference-changes.md
 SKILL.md,SKILL.md,preserve,original bytes retained
 adaptive_ecu/CMakeLists.txt,adaptive_ecu/CMakeLists.txt,preserve,original bytes retained
 adaptive_ecu/data/battery_profile.csv,adaptive_ecu/data/battery_profile.csv,preserve,original bytes retained
@@ -52,32 +57,75 @@
 docs/ADR.md,docs/ADR.md,preserve,original bytes retained
 docs/CICD_SPEC.md,docs/CICD_SPEC.md,preserve,original bytes retained
 docs/ICD.md,docs/ICD.md,preserve,original bytes retained
-docs/README.md,docs/README.md,reference_only,navigation links only
+docs/README.md,docs/README.md,reference_only,structure/status/reference mapping only; see reference-changes.md
 docs/SDD-ECU.md,docs/SDD-ECU.md,preserve,original bytes retained
 docs/SDD-IVI.md,docs/SDD-IVI.md,preserve,original bytes retained
 docs/SRS.md,docs/SRS.md,preserve,original bytes retained
 docs/TARA.md,docs/TARA.md,preserve,original bytes retained
 docs/TEST_PLAN.md,docs/TEST_PLAN.md,preserve,original bytes retained
+,docs/aidlc/README.md,add,added structure artifact; path existence is not functional completion
+,docs/aidlc/changes/CHG-template/aidlc-state.md,add,added structure artifact; path existence is not functional completion
+,docs/aidlc/changes/CHG-template/audit.md,add,added structure artifact; path existence is not functional completion
+,docs/aidlc/changes/CHG-template/construction/README.md,add,added structure artifact; path existence is not functional completion
+,docs/aidlc/changes/CHG-template/construction/build-and-test/README.md,add,added structure artifact; path existence is not functional completion
+,docs/aidlc/changes/CHG-template/construction/plans/README.md,add,added structure artifact; path existence is not functional completion
+,docs/aidlc/changes/CHG-template/construction/unit-template/README.md,add,added structure artifact; path existence is not functional completion
+,docs/aidlc/changes/CHG-template/construction/unit-template/code/README.md,add,added structure artifact; path existence is not functional completion
+,docs/aidlc/changes/CHG-template/construction/unit-template/functional-design/README.md,add,added structure artifact; path existence is not functional completion
+,docs/aidlc/changes/CHG-template/construction/unit-template/infrastructure-design/README.md,add,added structure artifact; path existence is not functional completion
+,docs/aidlc/changes/CHG-template/construction/unit-template/nfr-design/README.md,add,added structure artifact; path existence is not functional completion
+,docs/aidlc/changes/CHG-template/construction/unit-template/nfr-requirements/README.md,add,added structure artifact; path existence is not functional completion
+,docs/aidlc/changes/CHG-template/inception/README.md,add,added structure artifact; path existence is not functional completion
+,docs/aidlc/changes/CHG-template/inception/application-design/README.md,add,added structure artifact; path existence is not functional completion
+,docs/aidlc/changes/CHG-template/inception/plans/README.md,add,added structure artifact; path existence is not functional completion
+,docs/aidlc/changes/CHG-template/inception/requirements/README.md,add,added structure artifact; path existence is not functional completion
+,docs/aidlc/changes/CHG-template/inception/reverse-engineering/README.md,add,added structure artifact; path existence is not functional completion
+,docs/aidlc/changes/CHG-template/inception/user-stories/README.md,add,added structure artifact; path existence is not functional completion
+,docs/aidlc/changes/CHG-template/mistakes.md,add,added structure artifact; path existence is not functional completion
+,docs/aidlc/changes/CHG-template/spec.md,add,added structure artifact; path existence is not functional completion
+,docs/aidlc/changes/README.md,add,added structure artifact; path existence is not functional completion
+,docs/aidlc/structure/baseline.sha256,add,added structure artifact; path existence is not functional completion
+,docs/aidlc/structure/document-map.md,add,added structure artifact; path existence is not functional completion
+,docs/aidlc/structure/path-map.csv,add,added structure artifact; path existence is not functional completion
+,docs/aidlc/structure/reference-changes.md,add,added structure artifact; path existence is not functional completion
+,docs/aidlc/structure/scaffold-application.md,add,added structure artifact; path existence is not functional completion
+,docs/aidlc/structure/scaffold-paths.json,add,added structure artifact; path existence is not functional completion
+,docs/aidlc/structure/scope-verification.json,add,added structure artifact; path existence is not functional completion
+,docs/aidlc/structure/verification.md,add,added structure artifact; path existence is not functional completion
 docs/archive/project-overview.md,docs/archive/project-overview.md,preserve,original bytes retained
 docs/development/CAN_세션인증_설계안.md,docs/development/CAN_세션인증_설계안.md,preserve,original bytes retained
+,docs/development/README.md,add,added structure artifact; path existence is not functional completion
 docs/development/SOC_합성실험_결과.md,docs/development/SOC_합성실험_결과.md,preserve,original bytes retained
+,docs/development/playbooks/docs-review.md,add,added structure artifact; path existence is not functional completion
+,docs/development/playbooks/ecu.md,add,added structure artifact; path existence is not functional completion
+,docs/development/playbooks/ivi-integration.md,add,added structure artifact; path existence is not functional completion
+,docs/development/playbooks/security.md,add,added structure artifact; path existence is not functional completion
 docs/development/q2_validation/check_design.py,docs/development/q2_validation/check_design.py,preserve,original bytes retained
 docs/development/q2_validation/fixtures.json,docs/development/q2_validation/fixtures.json,preserve,original bytes retained
 docs/development/q2_validation/protocol_fixtures.json,docs/development/q2_validation/protocol_fixtures.json,preserve,original bytes retained
 docs/development/q2_validation/protocol_model.py,docs/development/q2_validation/protocol_model.py,preserve,original bytes retained
 docs/development/q2_validation/protocol_schema.json,docs/development/q2_validation/protocol_schema.json,preserve,original bytes retained
 docs/development/q2_validation/test_protocol.py,docs/development/q2_validation/test_protocol.py,preserve,original bytes retained
+,docs/development/templates/aidlc-state.md,add,added structure artifact; path existence is not functional completion
+,docs/development/templates/audit.md,add,added structure artifact; path existence is not functional completion
+,docs/development/templates/change.md,add,added structure artifact; path existence is not functional completion
+,docs/development/templates/evidence.md,add,added structure artifact; path existence is not functional completion
+,docs/development/templates/spec.md,add,added structure artifact; path existence is not functional completion
+,docs/development/tooling.md,add,added structure artifact; path existence is not functional completion
+,docs/development/verification/steering-tests.md,add,added structure artifact; path existence is not functional completion
+,docs/development/workflow.md,add,added structure artifact; path existence is not functional completion
 docs/development/계획_검토.md,docs/development/계획_검토.md,preserve,original bytes retained
 docs/development/문서_종합정합성_검토.md,docs/development/문서_종합정합성_검토.md,preserve,original bytes retained
-docs/development/보안계획_구현전_인계_및_진행현황.md,docs/development/보안계획_구현전_인계_및_진행현황.md,preserve,original bytes retained
+docs/development/보안계획_구현전_인계_및_진행현황.md,docs/development/보안계획_구현전_인계_및_진행현황.md,reference_only,structure/status/reference mapping only; see reference-changes.md
 docs/development/안드로이드_환경설정.md,docs/development/안드로이드_환경설정.md,preserve,original bytes retained
 docs/development/의사결정_기록.md,docs/development/의사결정_기록.md,preserve,original bytes retained
 docs/development/인증이벤트_메시지_상태규약.md,docs/development/인증이벤트_메시지_상태규약.md,preserve,original bytes retained
 docs/development/인증이벤트_전달_사전검증.md,docs/development/인증이벤트_전달_사전검증.md,preserve,original bytes retained
-docs/development/인증이벤트_전달_설계안.md,docs/development/인증이벤트_전달_설계안.md,preserve,original bytes retained
+docs/development/인증이벤트_전달_설계안.md,docs/development/인증이벤트_전달_설계안.md,reference_only,structure/status/reference mapping only; see reference-changes.md
 docs/development/정리_이력.md,docs/development/정리_이력.md,preserve,original bytes retained
+,ivi_platform/README.md,add,added structure artifact; path existence is not functional completion
 plan/ECU.md,plan/ECU.md,preserve,original bytes retained
-plan/IVI.md,plan/IVI.md,preserve,original bytes retained
+plan/IVI.md,plan/IVI.md,reference_only,structure/status/reference mapping only; see reference-changes.md
 plan/_archive/ECU.md,plan/_archive/ECU.md,preserve,original bytes retained
 plan/_archive/ECU_최종_실행계획서.md,plan/_archive/ECU_최종_실행계획서.md,preserve,original bytes retained
 plan/_archive/INDEX.md,plan/_archive/INDEX.md,preserve,original bytes retained
@@ -103,7 +151,7 @@
 plan/detail/ecu/M7_최종검증_재현성.md,plan/detail/ecu/M7_최종검증_재현성.md,preserve,original bytes retained
 plan/detail/ecu/M8_데모_제출.md,plan/detail/ecu/M8_데모_제출.md,preserve,original bytes retained
 plan/detail/ecu/ref_명령모음.md,plan/detail/ecu/ref_명령모음.md,preserve,original bytes retained
-plan/detail/ivi/M1_AOSP_Docker_CI.md,plan/detail/ivi/M1_AOSP_Docker_CI.md,preserve,original bytes retained
+plan/detail/ivi/M1_AOSP_Docker_CI.md,plan/detail/ivi/M1_AOSP_Docker_CI.md,reference_only,structure/status/reference mapping only; see reference-changes.md
 plan/detail/ivi/M2_HALMock_PlanAB.md,plan/detail/ivi/M2_HALMock_PlanAB.md,preserve,original bytes retained
 plan/detail/ivi/M3_HAL_Service_대시보드.md,plan/detail/ivi/M3_HAL_Service_대시보드.md,preserve,original bytes retained
 plan/detail/ivi/M4_대시보드_Alert_배포.md,plan/detail/ivi/M4_대시보드_Alert_배포.md,preserve,original bytes retained
@@ -123,7 +171,12 @@
 security/secoc_module.py,security/secoc_module.py,preserve,original bytes retained
 security/tests/test_ids_baseline.py,security/tests/test_ids_baseline.py,preserve,original bytes retained
 security/tests/test_secoc.py,security/tests/test_secoc.py,preserve,original bytes retained
-프로젝트구조개선.md,프로젝트구조개선.md,preserve,original bytes retained
+,tools/workflow/README.md,add,added structure artifact; path existence is not functional completion
+,tools/workflow/check.py,add,added structure artifact; path existence is not functional completion
+,tools/workflow/core.py,add,added structure artifact; path existence is not functional completion
+,tools/workflow/mcp_server.py,add,added structure artifact; path existence is not functional completion
+,tools/workflow/tests/README.md,add,added structure artifact; path existence is not functional completion
+프로젝트구조개선.md,프로젝트구조개선.md,reference_only,structure/status/reference mapping only; see reference-changes.md
 하드웨어 정보/ADS1115.jpg,하드웨어 정보/ADS1115.jpg,preserve,original bytes retained
 하드웨어 정보/mcp2515.jpg,하드웨어 정보/mcp2515.jpg,preserve,original bytes retained
 하드웨어 정보/가변저항.jpg,하드웨어 정보/가변저항.jpg,preserve,original bytes retained
@@ -137,24 +190,3 @@
 하드웨어 정보/촬영_사진1.png,하드웨어 정보/촬영_사진1.png,preserve,original bytes retained
 하드웨어 정보/촬영_사진2.png,하드웨어 정보/촬영_사진2.png,preserve,original bytes retained
 하드웨어 정보/컨버터O_배선완결판.html,하드웨어 정보/컨버터O_배선완결판.html,preserve,original bytes retained
-,.agents/skills/capstone-workflow/SKILL.md,add,structure documentation; no product implementation
-,.claude/skills/capstone-workflow/SKILL.md,add,structure documentation; no product implementation
-,docs/aidlc/README.md,add,structure documentation; no product implementation
-,docs/aidlc/structure/baseline.sha256,add,structure documentation; no product implementation
-,docs/aidlc/structure/document-map.md,add,structure documentation; no product implementation
-,docs/aidlc/structure/path-map.csv,add,structure documentation; no product implementation
-,docs/aidlc/structure/reference-changes.md,add,structure documentation; no product implementation
-,docs/aidlc/structure/verification.md,add,structure documentation; no product implementation
-,docs/development/README.md,add,structure documentation; no product implementation
-,docs/development/playbooks/docs-review.md,add,structure documentation; no product implementation
-,docs/development/playbooks/ecu.md,add,structure documentation; no product implementation
-,docs/development/playbooks/ivi-integration.md,add,structure documentation; no product implementation
-,docs/development/playbooks/security.md,add,structure documentation; no product implementation
-,docs/development/templates/aidlc-state.md,add,structure documentation; no product implementation
-,docs/development/templates/audit.md,add,structure documentation; no product implementation
-,docs/development/templates/change.md,add,structure documentation; no product implementation
-,docs/development/templates/evidence.md,add,structure documentation; no product implementation
-,docs/development/templates/spec.md,add,structure documentation; no product implementation
-,docs/development/tooling.md,add,structure documentation; no product implementation
-,docs/development/verification/steering-tests.md,add,structure documentation; no product implementation
-,docs/development/workflow.md,add,structure documentation; no product implementation
```

### 검증 범위

현재 경로 목록과 실제 파일 집합을 비교하고, 기존 파일 목록 보존·변경 파일 제한·위 diff를 확인한다. 원본 보존 대상은 해시로 확인한다. Markdown 렌더링 경로·앵커 검사는 기존 보관본 링크 5건만 예외로 허용한다. 제품 기능·skill 로딩·MCP·hook 실행 인수는 이번 참조 정정의 결과가 아니다.

이번 검사 결과: 전체 파일 191개와 path-map의 경로 집합 일치, 구조도 경로 73개 누락 0개, 변경 문서·매핑 11개 외 기존 파일 해시 동일, 추가·삭제·이동 0개. Markdown 103개·링크 1518개에서 신규 오류 0개이며 기존 보관본 링크 5건은 예외로 유지한다. 검사 자료는 tmp/structure_alignment/result.json 및 tmp/doc_render_review/render-audit.json에 있다.


## 자동화 지침 추가와 탐색 연결 — 2026-09-10

사용자 요청으로 docs/development/자동화지침.md를 작성했다. 기존 운영 문서에는 해당 안내의 역할·사용 시점을 연결하는 문구만 추가했고 전체 경로 목록에 등록했다. 실행 코드·설정 활성화·공식 계약 변경은 없다. 이 절은 해당 참조 변경의 추가 기록이다.

```diff
--- docs/aidlc/structure/document-map.md before
+++ docs/aidlc/structure/document-map.md after
@@ -27,3 +27,6 @@
 | [IVI 경계](../../../ivi_platform/README.md) | IVI 계획·SDD-IVI, Node B 구현 위치 | 목적 안내만 존재, 제품 소스 없음 |
 
 path-map의 preserve/reference_only는 최초 구조 적용 기준선과의 관계다. 추가된 파일은 add로 유지하며 이후 문서 참조 수정은 reference-changes에서 별도로 확인한다. 실질적인 제품 구현 상태는 이 배치 구분으로 판정하지 않는다.
+
+
+[자동화 지침](../../development/자동화지침.md)은 반복 작업 선정·skill/CLI/hook 역할·외부 및 자체 MCP의 도입 기준을 설명한다. workflow는 사용 시점, tooling은 실제 구현·연결 상태를 관리하며 기존 공식 지침·계약은 유지한다.
```

```diff
--- docs/development/README.md before
+++ docs/development/README.md after
@@ -23,3 +23,6 @@
 - [인증이벤트_전달_사전검증](인증이벤트_전달_사전검증.md)
 - [인증이벤트_전달_설계안](인증이벤트_전달_설계안.md)
 - [정리_이력](정리_이력.md)
+
+
+- [자동화 지침](자동화지침.md): 반복 작업의 skill·CLI·hook 적용과 외부/자체 MCP 도입 기준
```

```diff
--- docs/development/tooling.md before
+++ docs/development/tooling.md after
@@ -30,3 +30,6 @@
 
 
 최신 배치·전체 경로는 [현재 구조 매핑](../aidlc/structure/document-map.md)을 따른다. 골격 존재는 실제 도구 기능·연결 성공을 뜻하지 않는다.
+
+
+자동화 대상 선정·역할 분담·도입 순서는 [자동화 지침](자동화지침.md)을 따른다. 이 문서에서는 실제 구현·연결 상태와 사용법을 관리한다.
```

```diff
--- docs/development/workflow.md before
+++ docs/development/workflow.md after
@@ -16,3 +16,6 @@
 
 
 구조 선배치 후에는 [CHG 템플릿 안내](../aidlc/changes/README.md)에 따라 이미 생성된 템플릿을 사용한다. 위의 필요 시 생성 원칙은 실제 작업 기록에 적용하며, 템플릿의 존재를 실제 작업 착수로 간주하지 않는다.
+
+
+작업 중 반복 절차나 외부 서비스 접근의 자동화가 필요하면 [자동화 지침](자동화지침.md)에 따라 대상을 선정한다. 자동화 구축을 모든 제품 작업의 필수 선행조건으로 추가하지 않는다.
```

경로 매핑 추가: original_path는 빈 값, applied_path는 docs/development/자동화지침.md, action은 add다. 기존 매핑 행은 보존했다. 링크·목록·변경 범위 검증 자료는 tmp/automation_guidance/에 기록한다.


## 협업 전략 추가·참조 연결 — 2026-09-10

사용자 요청으로 docs/development/협업전략.md를 신규 작성했다. 공동 규약·연계 원본을 보존하고 운영 README·workflow·문서 매핑에 탐색 연결만 추가했다. 전체 path-map에 새 문서를 add로 등록했으며 기존 행은 유지했다. 이 절은 추가 참조 이력이다.

```diff
--- docs/development/README.md before
+++ docs/development/README.md after
@@ -26,3 +26,6 @@
 
 
 - [자동화 지침](자동화지침.md): 반복 작업의 skill·CLI·hook 적용과 외부/자체 MCP 도입 기준
+
+
+- [협업 전략](협업전략.md): ECU·IVI 역할 분담, 공동 저장소·브랜치·PR·인계·릴리즈 운영
```

```diff
--- docs/development/workflow.md before
+++ docs/development/workflow.md after
@@ -19,3 +19,6 @@
 
 
 작업 중 반복 절차나 외부 서비스 접근의 자동화가 필요하면 [자동화 지침](자동화지침.md)에 따라 대상을 선정한다. 자동화 구축을 모든 제품 작업의 필수 선행조건으로 추가하지 않는다.
+
+
+ECU·IVI 작업 분담과 저장소·PR·인계 운영은 [협업 전략](협업전략.md)에서 기존 공동 규약·연계 원본에 연결해 확인한다.
```

```diff
--- docs/aidlc/structure/document-map.md before
+++ docs/aidlc/structure/document-map.md after
@@ -30,3 +30,6 @@
 
 
 [자동화 지침](../../development/자동화지침.md)은 반복 작업 선정·skill/CLI/hook 역할·외부 및 자체 MCP의 도입 기준을 설명한다. workflow는 사용 시점, tooling은 실제 구현·연결 상태를 관리하며 기존 공식 지침·계약은 유지한다.
+
+
+[협업 전략](../../development/협업전략.md)은 공동 협업 규약·연계 의존성을 두 담당자의 저장소·PR·통합 운영에 적용하는 안내다. 기존 규칙·인계표의 원본을 대체하지 않는다. 운영 README와 workflow에서 이 문서로 연결한다.
```

검증은 전체 경로 목록·실제 파일 집합, 렌더링 링크·앵커, 변경 파일 범위를 대조한다. 검사 증거는 tmp/collaboration_strategy/와 tmp/doc_render_review/에 남긴다. 저장소 설정·제품 실행 결과는 아니다.


## 형상관리 전략 추가·참조 연결 — 2026-09-10

사용자 요청으로 docs/development/형상관리전략.md를 작성했다. 일반 형상관리와 보안 실험의 설계·실행·분석·최종 보고서 추적을 통합하고 기존 협업·실험 원본에 연결했다. 아래 기존 문서는 탐색 연결만 추가했으며 원본 규칙·수치·코드는 보존했다. 이 절은 추가 참조 기록이다.

```diff
--- docs/development/README.md before
+++ docs/development/README.md after
@@ -29,3 +29,6 @@
 
 
 - [협업 전략](협업전략.md): ECU·IVI 역할 분담, 공동 저장소·브랜치·PR·인계·릴리즈 운영
+
+
+- [형상관리 전략](형상관리전략.md): 코드·환경·릴리즈 기준본과 보안 실험 설계·원자료·분석·보고서 추적
```

```diff
--- docs/development/workflow.md before
+++ docs/development/workflow.md after
@@ -22,3 +22,6 @@
 
 
 ECU·IVI 작업 분담과 저장소·PR·인계 운영은 [협업 전략](협업전략.md)에서 기존 공동 규약·연계 원본에 연결해 확인한다.
+
+
+작업의 버전·환경·입력·시험 결과와 최종 수치의 출처는 [형상관리 전략](형상관리전략.md)에 따라 기존 CHG·증거 기록에 연결한다.
```

```diff
--- docs/development/협업전략.md before
+++ docs/development/협업전략.md after
@@ -113,3 +113,6 @@
 반복되는 검토·검증·기록은 [자동화 지침](자동화지침.md)에 따라 skill·CLI·hook으로 보조한다. 외부 저장소·CI 조회는 필요한 경우 MCP 연결을 검토한다. 도구가 승인·계약 합의·실장비 인수를 대신하지 않으며 자동화를 완성할 때까지 제품 개발을 일괄 중단하지 않는다.
 
 이 문서는 운영 전략을 정리한 것이다. Git 초기화·원격 설정·브랜치 보호·팀원 초대·PR 생성·외부 메시지 전송을 수행하지 않았다. 실제 실행 결과와 접근 정보는 해당 과제 기록에서 필요한 범위만 관리한다.
+
+
+코드·계약·환경·릴리즈와 보안 실험 설계·원자료·분석 결과의 버전 연결은 [형상관리 전략](형상관리전략.md)을 참조한다. 이 문서의 담당·브랜치·인계 규칙은 그대로 유지한다.
```

```diff
--- docs/aidlc/structure/document-map.md before
+++ docs/aidlc/structure/document-map.md after
@@ -33,3 +33,6 @@
 
 
 [협업 전략](../../development/협업전략.md)은 공동 협업 규약·연계 의존성을 두 담당자의 저장소·PR·통합 운영에 적용하는 안내다. 기존 규칙·인계표의 원본을 대체하지 않는다. 운영 README와 workflow에서 이 문서로 연결한다.
+
+
+[형상관리 전략](../../development/형상관리전략.md)은 공동 규약·ECU M5·공식 시험 원본을 기준으로 코드·환경·실험 설계·원자료·분석·릴리즈·최종 보고서의 식별과 재현을 연결한다. 협업 전략은 역할·PR 운영, 형상관리 전략은 기준본·증거 계보를 담당하며 원본 실험 조건을 대체하지 않는다.
```

전체 path-map에는 docs/development/형상관리전략.md를 add로 등록했다. 기존 행은 보존했다. 신규 경로·링크·표 및 실제 파일 목록·변경 범위를 검사하고 tmp/configuration_strategy/와 tmp/doc_render_review/에 증거를 남긴다. Git 설정·실험 실행·릴리즈 발행 결과가 아니다.


## development 최상위 카테고리 통합 — 2026-09-10

사용자 승인 범위: 최상위 파일을 보고한 세 카테고리로 통합하고 다른 문서는 독립 유지한다. 하위 디렉터리의 자료는 이동·통합하지 않고 필요한 참조만 정정했다. 기존 원문·공식 ID·수치·결정은 보존하며 읽기 순서·제목 단계·앵커·링크와 인덱스를 정리했다.

원본 대응은 [document-map](document-map.md)의 카테고리 통합 표와 각 통합본 머리말을 따른다. 변경 전 프로젝트 전체 194개 파일의 목록·해시·바이트 백업은 tmp/development_category_merge/before/ 및 baseline.json에 보관했다. 과거 참조 기록의 옛 파일명과 diff는 해당 시점 기록으로 보존한다.

### 원문 보존 방법

여섯 원문 각각을 BEGIN/END preserved-source 경계로 유지했다. 제목 앞에 구역별 고유 앵커를 추가하고 제목 단계를 한 단계 내렸다. 기존 본문 절 번호·표·코드·수치·사용자 결정은 재작성하지 않았다. 원문별 heading/link 변환을 역적용한 SHA-256이 통합 전 SHA-256과 일치함을 확인했다. 각 통합본 Part의 당시 완료·미실행·예정 표현은 역사적 유효 범위를 유지한다.

### 제거·추가 및 기존 문서 변경

제거한 파일은 협업전략.md, 형상관리전략.md, 자동화지침.md, 인증이벤트_전달_사전검증.md의 네 파일뿐이다. 모두 docs/development 바로 아래이며 여섯 원문 보존 확인 후 제거했다. 신규 문서는 협업_형상관리전략.md 하나, tooling.md와 인증이벤트_전달_설계안.md는 경로를 유지한 통합본이다. 운영 README는 14개 문서와 하위 자료를 구분하는 인덱스로 재구성했다.

기존 파일로 향하던 활성 링크는 아래대로 바꿨다. 동일 경로의 문서 전체를 가리키는 링크는 통합 목차를 열도록 유지했다. 코드 펜스 속 과거 diff는 변경하지 않았다. 전체 path-map은 제거한 4행을 제외하고 새 통합본 1행을 추가했다. 문서 목록·구조 개선안·document-map에는 현재 카테고리와 이전 기록의 대응만 보완했다.

| 참조 문서 | 기존 대상 | 통합 후 대상 |
|---|---|---|
| `docs/development/governance/협업_형상관리전략.md` | `자동화지침.md` | `tooling.md#automation` |
| `docs/development/governance/협업_형상관리전략.md` | `형상관리전략.md` | `#configuration` |
| `docs/development/governance/협업_형상관리전략.md` | `협업전략.md` | `#collaboration` |
| `docs/development/governance/협업_형상관리전략.md` | `자동화지침.md` | `tooling.md#automation` |
| `docs/development/tooling.md` | `tooling.md` | `#tooling-runtime` |
| `docs/development/tooling.md` | `자동화지침.md` | `#automation` |
| `docs/development/security/인증이벤트_전달_설계안.md` | `인증이벤트_전달_사전검증.md` | `#delivery-precheck` |
| `docs/development/security/인증이벤트_전달_설계안.md` | `인증이벤트_전달_설계안.md` | `#delivery-design` |
| `docs/README.md` | `development/인증이벤트_전달_사전검증.md` | `development/인증이벤트_전달_설계안.md#delivery-precheck` |
| `docs/development/README.md` | `인증이벤트_전달_사전검증.md` | `인증이벤트_전달_설계안.md#delivery-precheck` |
| `docs/development/README.md` | `자동화지침.md` | `tooling.md#automation` |
| `docs/development/README.md` | `협업전략.md` | `협업_형상관리전략.md#collaboration` |
| `docs/development/README.md` | `형상관리전략.md` | `협업_형상관리전략.md#configuration` |
| `docs/development/workflow.md` | `자동화지침.md` | `tooling.md#automation` |
| `docs/development/workflow.md` | `협업전략.md` | `협업_형상관리전략.md#collaboration` |
| `docs/development/workflow.md` | `형상관리전략.md` | `협업_형상관리전략.md#configuration` |
| `docs/development/security/인증이벤트_메시지_상태규약.md` | `인증이벤트_전달_사전검증.md` | `인증이벤트_전달_설계안.md#delivery-precheck` |
| `docs/aidlc/structure/document-map.md` | `../../development/자동화지침.md` | `../../development/tooling.md#automation` |
| `docs/aidlc/structure/document-map.md` | `../../development/협업전략.md` | `../../development/협업_형상관리전략.md#collaboration` |
| `docs/aidlc/structure/document-map.md` | `../../development/형상관리전략.md` | `../../development/협업_형상관리전략.md#configuration` |

검증 자료: tmp/development_category_merge/check_content.py, body-manifest.json, link-changes.json 및 final-verification.json. 전체 렌더링은 tmp/doc_render_review/audit-full-scaffold.mjs를 사용한다. 보관본 plan/_archive/IVI.md의 기존 상대 링크 5개는 공개된 보존 예외로 유지하며 신규 오류로 숨기지 않는다. 제품 실행·실장비·자동화 인수는 이번 문서 통합의 범위가 아니다.

최종 검증: development 최상위 17개→14개, 원문 6개→통합본 3개, 제거 4개·신규 1개. 원문 6개의 역변환 SHA-256 모두 일치. 현재 파일 191개와 path-map 일치, 제품·독립 문서의 무관한 본문 보존 확인. 렌더링 Markdown 103개에서 기존 보관본 링크 5건 외 오류 없음. 과거 별도 원본 URL의 외부 북마크는 저장소 밖에서 자동 갱신할 수 없으며 위 대응표와 통합본의 Part 앵커를 사용한다.

<a id="development-layout-sync"></a>

## development 하위 분류·참조 정정·배치 지침 반영 — 2026-09-10

앞 절의 17개→14개는 문서 통합 당시 검증이다. 이후 사용자 요청에 따라 문서 11개를 governance/·security/·environment/·experiments/·reviews/로 이동하여 최상위에는 README.md·workflow.md·tooling.md 3개를 남겼다. 기존 하위 폴더와 제품 경로는 유지했다. 이동 당시 tmp/ 제외 191개 파일의 SHA-256을 대조하여 내용 변경·파일 유실이 없음을 확인했다.

후속 요청으로 이동 문서의 상대 링크와 외부 참조, 현재 경로 매핑을 정정했다. 이후 운영 README에 배치 기준을 추가하고 workflow에서 연결했다. 이번 동기화는 현재 위치 설명과 당시 통합 기록을 구분하고, 협업·형상관리·자동화·공식 문서 안내를 배치 기준에 연결한다. 제품 요구·계약·수치·실험 조건·구현 상태는 변경하지 않는다.

현재 위치의 원본은 [최신 구조 매핑](document-map.md#current-development-layout)과 [전체 경로 목록](path-map.csv), 문서 생성 위치의 원본은 [배치 기준](../../development/README.md#document-placement)이다. 이전 표의 통합 전후 문자열과 최초 baseline은 당시 변환 증거이며 현행 경로로 일괄 치환하지 않는다. path-map의 applied_path를 현재 탐색에 사용한다.

검증은 전체 Markdown 링크·앵커 검사, 현재 파일 목록과 path-map 대조, 변경 전후 해시·차이 검토로 수행한다. 기존 plan/_archive/IVI.md의 상대 링크 5건은 보관본 안내에 따른 역사 보존 예외다. 제품 실행·실장비·자동화 활성화 검증은 이 문서 동기화의 범위가 아니다.

## 신규 팀원 구조 안내 추가 — 2026-09-10

루트 README에 주요 디렉터리·첫 읽기 순서를 추가하고 governance/프로젝트구조_사용안내.md에 현재 구조·파일별 목적·ECU/IVI 작업·기록·인계 예시를 작성했다. 공식 문서 목록·운영 인덱스·문서 매핑·path-map에 연결했다. 새 안내 1개로 전체 보존 파일은 192개(tmp/ 제외)다. 제품 코드·계약·기존 전략 본문은 수정하지 않았다. 파일별 색인은 실제 목록 기준이며 자동 갱신 도구가 아니므로 향후 생성·이동 시 함께 관리한다.

## GitHub 형상관리 실행 매뉴얼 추가 — 2026-09-10

사용자 지정 위치인 루트 하위 `커밋관련지침/commit.md`를 생성했다. 하나의 공동 저장소를 기준으로 ECU·IVI 담당 경로와 공동 경로, `.gitignore`에 따른 제외 대상, 최초 GitHub 등록, 작업 브랜치, 선택적 add·commit·push, Draft PR·리뷰·병합, 충돌 처리, 보안 실험과 릴리즈 순서를 PowerShell 명령과 함께 정리했다. 현재 Git 메타데이터 없음, Git 설치됨, GitHub CLI 미설치 상태를 구분했다. 루트·공식 문서·운영 인덱스·구조 안내·문서 매핑·path-map에서 새 매뉴얼을 연결했다. 제품 코드·계약·계획의 실질 내용은 변경하지 않았다.

검증 과정에서 같은 폴더에 이미 있던 `rules.md`와 `SKILL.md`가 이전 전체 경로 목록·파일별 색인에 누락된 것을 확인했다. 두 기존 파일의 내용은 수정하지 않고 path-map과 프로젝트 구조 사용 안내에 추가했다. 매뉴얼의 영문·영역 괄호형 커밋 예시는 기존 규칙의 한글 한 줄 `타입: 설명` 형식으로 정정하고, Tidy First와 파일 이동의 삭제·추가 동시 staging 절차를 연결했다. 현재 파일 목록은 195개다.

<a id="commit-guidance-migration"></a>

## 커밋 문서 이동·공통 skill 연결·충돌 정정 — 2026-09-10

사용자 요청으로 커밋관련지침/의 commit.md를 docs/development/governance/commit.md로, rules.md·SKILL.md를 .agents/skills/commit/으로 이동했다. .claude/skills/commit/SKILL.md는 공통 원본을 읽는 짧은 진입 문서로 추가했다. 옛 폴더는 세 파일 이동 후 비어 있음을 확인하고 제거했다. 이전 절의 위치·내용·수치는 당시 기록으로 보존한다.

공동 규약의 시험용 main 커밋·push와 무조건 hard reset 절차 두 곳을 하나의 규칙 조회·실제 차단 증거 확인 절차로 대체했다. 거부 증거가 없으면 동작은 미검증으로 남긴다. 한글 type(scope) 예시·작업 브랜치 표현을 통일하고 CLAUDE의 보조 skill 해석을 명확히 했다. 루트 지침·매뉴얼·인덱스·구조 안내·현재 applied_path를 동기화했다. 제품 코드·보안 계약·역사 보관본은 수정하지 않았다.

현재 경로와 원본 관계는 [구조 매핑](document-map.md#commit-guidance-layout), 작업 상태·검증 결과는 [CHG-001](../changes/CHG-001/aidlc-state.md)을 따른다. 기존 생성 기록의 보존·검증 주장은 해당 시점의 기록이며 이번 이동 뒤 바이트 불변을 뜻하지 않는다.
