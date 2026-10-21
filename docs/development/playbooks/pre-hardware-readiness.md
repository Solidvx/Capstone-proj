# 물리 시험 전 독립 준비 완료표

2026-10-03. 대상은 현재 ECU M4/M5·IVI 계측·M7 재현/안전 검증으로 이어지는 **시험 준비**다. 프로젝트 전체 개발/물리 최종 인수 완료표는 아니다. ICD/HAL/wire·CRITICAL latch·IDS 미분류 유형 정책은 유지했다. Pi 접속은 사용자가 담당한다.

| 계획 요구/문제 | 현재 제공/검증 | 남은 조건 |
|---|---|---|
| 두 Pi 동일 수정본 전달 | 003 worktree snapshot·파일 SHA·독립 추출 시험 | 사용자가 복사/빌드/환경 결과 반환 |
| 정상 학습·READY·공격 시작 순서 | capture 정상 manifest, rules+if/send_alerts READY, managed 수명 | 장비 정상-only 원본·실제 key/프로세스 준비 |
| 오래 떨어진 Fail-safe 독립 counter | IT-002 dump+receiver 판정, warning→critical·>10초·BMS >100쌍 회귀 | 실제 수락 JSONL·화면/0x101·0x103 |
| MAC 차단·같은 counter 복구 | fixture/Service 판정과 vcan 회귀 | IT-004 물리 raw/receiver/UI 증거 |
| 3구성×4공격 동일 입력 | 12회 파일럿 2개·같은 설정/seed/input hash 검증 | 물리 12회 인수 후 1,200회·실제 flooding 부하 |
| 정상 오탐률 100윈도우 | 실제 0x200 run/analyze 정상 FPR, vcan 100윈도우 경로 시험 | 물리 정상-only 대표성·실측 결과 |
| 수집 중단/손실을 0%로 오판 | READY/END, socket overflow, interface 통계·연속 프레임·고정 분모, INVALID 보존 | driver 통계 미지원이면 해결 후 재수집, 조용히 완화하지 않음 |
| 학습/임계/최종 평가 분리 | distinct run/hash+실제 sklearn, calibration-only threshold, frozen evaluation | 실제 독립 자료·공격별 목표 만족·후보 적용 결정 |
| 그래프/원수/보조 지표 | 두 패널 ROC SVG, JSON/CSV, 혼동행렬·Precision/Recall/F1/MCC 등 | 발표 PNG 필요 시 SVG 변환, 환경/분모 캡션 유지 |
| REP-1=A 재현 비교 | 두 검증 원장·설정/코드/입력 비교, 성공률 ≤5%p | 공식 100회/조합 반복. 파일럿을 공식으로 대체하지 않음 |
| IDS 학습/재현 문서 없음 | `security/ids/how_to_train.md`, README CLI manifest 누락 수정 | 환경에 맞춘 장비 명령 확인 |
| ASan 옵션 없음/성공 문자열 오해 | ECU/IVI ENABLE_ASAN 기본 OFF, ASan+누수 검사 ECU16/IVI12 통과 | Pi 장시간 안정성·부하 중 메모리/CPU/RSS·8시간 실제 운영 |
| “미구현” 계획 drift | M5/M7 현행 CLI·상태 정정, 역사적 골격 구분 | 실행 완료 체크는 실제 물리 증거로만 갱신 |
| IF-only 사건 wire 유형 미확정 | IF_ANOMALY는 로컬 진단임을 분석/재현 문서에 명시 | 전송이 필요하면 유형/정책 합의 및 필요 시 ICD 승인. 임의 Fuzzy/None/새 코드 할당 금지 |
| 인증 이벤트·새 세션/Q2 후보 | 현재 승인 계약과 후속 설계/인수를 분리 | 공동 wire/세션 계약·정책 확정 전 구현/인수 확대하지 않음 |
| 실제 UI·물리 성능·CI/제출 | 현행 도구/소스 제공, 미실측 명시 | 픽셀 표시 지연/부하/CPU/RSS/최종 TC, CI 플랫폼·외부 실행 권한/후속 단계별 별도 수행 |

## 완료라고 부르지 않는 것

- 코드·가상 CAN·짧은 ASan 시험은 배선·센서·Debian13/Qt6.8 Pi 배포·8시간 안정성의 증거가 아니다.
- wire FPR 0%여도 미분류 IF 사건의 탐지율이나 전체 공격 성능을 증명하지 않는다. 오프라인 후보가 만족되지 않으면 그대로 미달을 기록한다.
- 하네스 완전성/재현성/공식 인수는 다른 판정이다. false 공식 상태를 문서 목표값으로 바꾸지 않는다.
- 최종 발표 숫자·ADR/TARA 결과 확정·release tag/commit/push는 원본 인수와 별도 요청 전 수행하지 않는다.

사용자 작업은 [임시_할일.md](../../../임시_할일.md)의 1~4번이며, 다음 명령은 결과 확인 뒤 이어간다. 구현/재현 상세는 [실험 분석](experiment-analysis.md), 이번 로컬 실제 결과는 [CHG-016](../../aidlc/changes/CHG-016/evidence.md)을 따른다.
