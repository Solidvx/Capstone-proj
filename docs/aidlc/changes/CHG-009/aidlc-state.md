# CHG-009 — 0단계 기준선 통합

- 요청: [spec](spec.md). 검증: [증거](evidence.md).
- 대상: `chore/ecu-m1-baseline`, 시험 커밋 `8e5e5d6`(`origin/develop` `ba3c24b` 병합).
- 상태(2026-10-03): `-merge` 2개의 `develop` 반영 확인, 최신 `develop` 병합·충돌 해결·푸시 완료. ECU 14/14, IVI core 8/9, Python 24/24. `develop` 대상 PR 생성·Squash 병합 대기(사용자 GitHub 웹 수행).
- 제외: `feat/ivi-rpi-deployment`는 IVI 배포 전용으로 유지.
- 남은 일: PR 병합 후 `develop`과 시험 커밋 내용 대조. IVI Qt 구성 오류(`qt_policy`, Qt 6.5 미만)와 RPi 대상 Qt 버전은 IVI 담당과 협의. vcan 수신 시험은 vcan 지원 Linux에서 재실행.
- 정리(2026-10-03): 대체된 원본 브랜치 `feat/ecu-can-ids`(`3813f4b`)·`feat/ivi-secoc-hardening`(`081aa13`)을 로컬·원격에서 삭제하고 `tmp/worktrees/` 2개를 제거했다(사용자 실행). 두 커밋은 원격에 남은 IVI 팀원의 `-merge` 브랜치 이력에 포함된다. WSL에서 만든 `.venv`의 리눅스 심볼릭 링크는 Windows Git이 지우지 못하므로 이런 폴더는 WSL에서 삭제한다.
- 실험 기록 규칙: ECU는 `develop` 커밋, IVI 실장비는 배포 브랜치 커밋을 각각 남긴다.
