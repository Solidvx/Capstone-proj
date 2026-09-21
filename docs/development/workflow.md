# 작업 흐름과 기록 위치

정책 원본은 [AGENTS](../../AGENTS.md), 작업별 절차 원본은 [루트 SKILL](../../SKILL.md)이다. 이 안내는 새 승인 단계나 의무 문서를 추가하지 않는다.

1. 요청 범위와 실제 파일을 확인하고 [공식 문서](../README.md), [ECU](../../plan/ECU.md)·[IVI](../../plan/IVI.md)·[공동 규약](../../plan/detail/common/00_협업_규약.md)에서 관련 과제를 찾는다. 문서를 생성하거나 이동하기 전에 [새 문서 배치 기준](README.md#document-placement)을 확인하여 기존 문서 보완 여부와 저장 위치를 정하고, 해당 기준에 따라 인덱스·매핑 갱신 및 참조 검사를 수행한다.
2. 작은 변경은 [change 양식](templates/change.md) 하나로 기록할 수 있다. 질문·설명·단순 오타에 전체 AIdlc 기록을 강제하지 않는다.
3. 다단계 작업은 docs/aidlc/changes/CHG-번호/에 [spec](templates/spec.md), [aidlc-state](templates/aidlc-state.md), 필요한 [audit](templates/audit.md)을 작성한다. 번호는 기존 작업 목록과 충돌하지 않게 선택한다.
4. inception/에는 실제 코드 조사, 요구 영향, 작업 분해, 설계를 필요한 만큼 작성한다. construction/에는 작업 단위별 설계·변경 요약과 build-and-test/의 검증 증거를 남긴다. 각 폴더는 실제 산출물이 있을 때 만든다.
5. 실제 코드는 기존 제품 경로에서 관리하고, 기록에는 관련 경로·공식 ID·차이만 연결한다. 공식 문서 전체를 복제하지 않는다.
6. 해당 분야의 [플레이북](README.md)과 기존 검증 기준으로 확인하고 [증거](templates/evidence.md)에 명령·환경·대상 해시·결과·미실행 이유를 남긴다.
7. 다단계 상태 원본은 aidlc-state.md 한 곳이다. 작은 작업은 change.md가 상태도 포함한다. 인덱스에는 링크만 두고 완료 상태를 중복 관리하지 않는다.

작업 재개 시 상태 원본→연결된 판단·증거→현재 대상 파일 순서로 대조한다. 대상이 바뀌면 과거 통과를 현재 증거로 사용하지 않는다. ICD 변경 판단은 기존 AGENTS의 인터페이스 변경 게이트를 적용한다.

구조 적용 자체의 경로·보존 기록은 [structure](../aidlc/structure/document-map.md)에 둔다. 이 기록을 제품 구현 완료로 간주하지 않는다.


구조 선배치 후에는 [CHG 템플릿 안내](../aidlc/changes/README.md)에 따라 이미 생성된 템플릿을 사용한다. 위의 필요 시 생성 원칙은 실제 작업 기록에 적용하며, 템플릿의 존재를 실제 작업 착수로 간주하지 않는다.


작업 중 반복 절차나 외부 서비스 접근의 자동화가 필요하면 [자동화 지침](tooling.md#automation)에 따라 대상을 선정한다. 자동화 구축을 모든 제품 작업의 필수 선행조건으로 추가하지 않는다.


ECU·IVI 작업 분담과 저장소·PR·인계 운영은 [협업 전략](governance/협업_형상관리전략.md#collaboration)에서 기존 공동 규약·연계 원본에 연결해 확인한다.


작업의 버전·환경·입력·시험 결과와 최종 수치의 출처는 [형상관리 전략](governance/협업_형상관리전략.md#configuration)에 따라 기존 CHG·증거 기록에 연결한다.
