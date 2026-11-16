# 프로젝트 문서

진행 기준은 [ECU](../plan/ECU.md), [IVI](../plan/IVI.md), [Common](../plan/detail/common/00_협업_규약.md) 세 계획이다. 계약·요구사항·시험 기준은 아래 공식 문서를 따른다.

## 공식 문서

| 문서 | 역할 |
|---|---|
| [ICD](ICD.md) | CAN/SecOC와 Node B C++ Service 계약 |
| [ICD 인증 세션](ICD-CAN-SESSION.md) · [ICD 인증 진단](ICD-CAN-DIAGNOSTIC.md) |2026-11-11 승인된 session-v2/diagnostic-v1 제품 전환 계약. 실제 연결/인수 상태는 CHG-029 참조 |
| [SRS](SRS.md) | 기능·비기능 요구사항과 추적성 |
| [SDD-ECU](SDD-ECU.md) | Node A 설계 |
| [SDD-IVI](SDD-IVI.md) | Ubuntu/C++/Qt Plan B의 Node B 설계 |
| [TEST_PLAN](TEST_PLAN.md) | 공식 TC와 합격 기준 |
| [ADR](ADR.md) | 채택 결정과 전환 대안 |
| [TARA](TARA.md) | 위협·위험·완화 및 보안 실험 |
| [CICD_SPEC](CICD_SPEC.md) | 예정 CI/CD 명세; 실제 CI 구현은 아직 없음 |

문서에 등장하는 소스 경로·명령은 예정 항목일 수 있다. 현재 구현 상태는 각 계획과 실제 파일로 확인한다. 원천 우선순위와 변경 절차는 [AGENTS](../AGENTS.md)를 따른다.

## 배경·연구·변경 기록

- [초기 제안서](archive/project-overview.md): 배경·예산·기대효과, 현재 구현의 근거 아님
- [보안 계획 적용 범위](../plan/detail/common/00_협업_규약.md#security-adoption): 현행 사용자 선택·적용 범위; 미채택 정책을 계약으로 적용하지 않음
- [문서·구조 정리 이력](development/reviews/정리_이력.md): 1차 구조 개선·중복 파일 검토·정리 적용의 통합 기록

## 개발 재개 기준과 설계 보완

- [종합 정합성 검토·매핑·착수 관문](development/reviews/문서_종합정합성_검토.md): 최신 문서 검토 결과와 계약/실행 경계
- [계획 검토](development/reviews/계획_검토.md): 개선 제안·계획 인수 이력과 문서 검토 D1~D6·실행 관문 E1~E6
- [의사결정 기록](development/governance/의사결정_기록.md): 질문·사용자 답변·반영 기록의 ID 색인, 하드웨어 정보
- [현재 요구→역할 과제→시험 연결](../plan/detail/common/01_연계_의존성.md#10-공식-요구사항에서-수행검증까지의-매핑): 전체 49개 요구
- [IVI Plan B 진행·구조 안내](development/governance/IVI_Plan_B_진행상황_및_구조_안내.md): 현재 상태, M/P 단계, 폴더 구조, 다음 작업
- [Android 환경설정](development/environment/안드로이드_환경설정.md): superseded된 과거 포팅 조사 자료; 현 실행 기준 아님
- [SOC·센서 구현 및 사전 검증 기록](development/experiments/SOC_합성실험_결과.md): 최신 절과 제품 실행 한계 구분
- [세션 인증 설계 이력](development/security/CAN_세션인증_설계안.md): 과거 방향 선택/후보 검증 기록.2026-11-11 전환 승인 뒤 공식 원본은 위 ICD 세션/진단이며 구현/인수는 [CHG-029](aidlc/changes/CHG-029/aidlc-state.md)를 따른다.
- [보안 계획 구현 전 인계·진행현황](development/security/보안계획_구현전_인계_및_진행현황.md#planning-complete): 보안 계획의 읽기 순서·담당·설정 확정 절차와 계획/구현 인수 구분
- [Q2 인증 이벤트 전달 설계안](development/security/인증이벤트_전달_설계안.md): 수단 비교·유선 IP/상호 TLS 우선 후보·신뢰 경계·시험 시나리오
- [Q2 메시지·상태 규약](development/security/인증이벤트_메시지_상태규약.md#planning-final): 후보 2와 §10의 최신 송신·큐·기한·장애 정책; 공식 계약 채택·제품 검증은 미완료
- [Q2 전달 사전검증](development/security/인증이벤트_전달_설계안.md#delivery-precheck): 최초 독립 모형의 부분 검증 기록; 후속 규약 전체나 실장비의 검증 결과가 아님
- [Plan 통합 결과](development/reviews/정리_이력.md#part4-planmerge): 원문 보존·24개 과제 대응과 폴더 제거 증거

보관 원문을 읽을 때는 [보관본 안내와 경로 대응](../plan/_archive/README.md)을 먼저 확인한다. 보관본의 과거 일정·상대 링크는 현행 개발 지시가 아니다.


## 개발 운영·작업 기록 연결

[개발 운영 안내](development/README.md)에서 기존 개발 문서와 신규 절차·양식을 찾는다. [AIdlc 안내](aidlc/README.md)와 [구조 적용 기록](aidlc/structure/verification.md)은 개별 작업 기록·원본 매핑·내용 보존 근거를 제공한다.


development 문서는 [카테고리별 운영 목록](development/README.md)에서 탐색한다. 자동화 원칙과 상태는 tooling, 협업과 형상관리는 협업_형상관리전략, 전달 설계와 최초 사전검증은 인증이벤트_전달_설계안의 각 Part로 통합했다.

문서 생성·이동 전에는 [새 문서 배치 기준](development/README.md#document-placement)을 확인한다. development의 현재 폴더별 배치와 이전 위치 대응은 [최신 구조 매핑](aidlc/structure/document-map.md#current-development-layout)을 따른다.

처음 참여하는 팀원을 위한 [프로젝트 구조 사용 안내](development/governance/프로젝트구조_사용안내.md)는 전체 파일의 목적과 실제 작업 흐름을 연결한다. 공식 계약과 정책은 각 원본을 따른다.

GitHub 저장소의 최초 등록과 ECU·IVI별 파일 선택·브랜치·커밋·PR·릴리즈 명령은 [GitHub 형상관리 실행 매뉴얼](development/governance/commit.md)을 따른다. 운영 원칙의 원본은 협업·형상관리 전략과 공동 협업 규약이다.
