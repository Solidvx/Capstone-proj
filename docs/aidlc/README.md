# AIdlc 작업 산출물

공식 원본은 [docs 목록](../README.md), 전체 실행 단계는 [ECU](../../plan/ECU.md)·[IVI](../../plan/IVI.md)에 유지한다. 이 영역은 개별 요청의 근거와 진행을 연결한다.

- [구조 적용 매핑](structure/document-map.md): 이번 구조 변경의 원본 관계
- [참조 수정 기록](structure/reference-changes.md) · [보존·검증 결과](structure/verification.md)
- [작업 흐름](../development/workflow.md) · [기록 양식](../development/README.md)

실제 개발 작업은 changes/CHG-번호/에 기록한다. 작은 변경은 change.md, 다단계는 spec.md와 aidlc-state.md를 사용하며 상태를 중복 관리하지 않는다.

## 실제 작업 기록

- [CHG-001](changes/CHG-001/aidlc-state.md): 커밋 지침 배치
- [CHG-002](changes/CHG-002/aidlc-state.md): IVI Qt Plan B P0 문서 기준
- [CHG-003](changes/CHG-003/aidlc-state.md): IVI Plan B P1~P6 진행 상태
  - [P1 구현 결과](changes/CHG-003/construction/P1_구현_결과.md)
  - [P1 빌드·시험 증거](changes/CHG-003/construction/build-and-test/evidence.md)

inception/은 기존 구현 조사·요구·설계·작업 분해, construction/은 작업 단위별 설계·실제 변경 경로·build-and-test/의 검증 근거를 수용한다. 조건부 폴더는 필요할 때 생성한다. construction/.../code/에도 제품 코드를 복제하지 않고 원래 소스 경로와 변경 요약을 둔다.

향후 작업 인덱스에는 작업 기록의 링크만 추가한다. 과거 계획이나 승인 기록을 새 작업의 완료 증거로 재해석하지 않는다.


후속 요청에 따른 전체 예정 경로·템플릿의 선배치 결과는 [골격 적용 안내](structure/scaffold-application.md)를 따른다. 위의 미생성 설명은 선배치 이전 기록이다.
