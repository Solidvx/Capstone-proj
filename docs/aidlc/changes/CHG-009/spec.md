# CHG-009 — 0단계 기준선 통합

요청(2026-10-03): 남은 통합·실험 단계에 앞서 ECU·IVI가 같은 코드 기준에서 시험하도록 미병합 작업을 `develop`에 모으고, 병합 결과를 빌드·시험으로 확정한다. 판단이 애매하면 사용자에게 확인한다.

포함 범위:

- `feat/ecu-can-ids-merge`·`feat/ivi-secoc-hardening-merge`의 `develop` 반영 여부 확인(IVI 팀원 생성, 팀원은 반영됐을 것이라고 답변).
- `chore/ecu-m1-baseline`에 최신 `develop`을 병합하고 문서 인덱스 충돌 해결, 원격 푸시, `develop` 대상 PR.
- 병합 커밋 기준 ECU CTest, IVI core CTest, Python 보안 시험과 `run_eval.py` 실행.
- 대체된 원본 브랜치·worktree 정리 판단.

제외 범위: `feat/ivi-rpi-deployment`(IVI 팀원 요청에 따라 배포 전용 브랜치로 유지, 수정·병합·삭제 안 함), 제품 코드·ICD 변경, IVI Qt 빌드 오류 수정(IVI 담당과 협의 사항).

완료 조건: `develop` 대비 우리 브랜치가 뒤처지지 않고, 병합 커밋의 시험 결과와 미검증 범위를 [증거](evidence.md)에 기록한다. PR 병합은 GitHub 웹에서 사용자가 수행한다.
