# CHG-019 — 로컬·GitHub 개발 기준 통합과 팀 인계

- 요청: Git과 GitHub를 동기화해 팀원이 지금까지의 진행 상태와 남은 작업을 확인할 수 있게 한다.
- 입력: 로컬 `feat/security-live-validation`의 `8a57f7f` 및 미커밋 25파일·미추적 279파일, GitHub `develop`의 `644eb99`(PR #24·#25).
- 보존: 로컬 작업을 `5779431`에 커밋했다. 변경 전 620파일의 ZIP/개별 SHA256 및 Git bundle은 Git 제외 `tmp/sync-20261021/`에 보존했다. 실험 raw·키·개인 논문 모음은 기존 제외 규칙을 유지한다.
- 범위: 양쪽 실험 도구·IVI 계측·회귀시험·증거 문서를 통합하고 현재 상태/인계 안내를 정정한다. ICD·CAN·SecOC·HAL 계약, 탐지 임계, 과거 실험 판정은 변경하지 않는다.
- 브랜치: `chore/team-sync-20261021`, 대상 `develop`. `main`은 공동 인수 릴리즈 기준으로 유지한다.
- 검증: Python 양쪽 시험과 통합 경계 회귀, ECU/IVI CTest, 합성 CLI smoke, 문서 참조·충돌 표식·실험 보존 해시·Git 제외 범위 확인.
- 병합 운영: 작업 브랜치→develop은 공동 규약의 Squash Merge와 상대방 Approve 조건을 따른다. 코드 동기화 요청을 상대방이 리뷰했다는 증거로 기록하지 않는다.

## 충돌 해결 기준

| 항목 | 통합 내용 |
|---|---|
| IDS runtime | 로컬의 커널 수신 시각·독립 보정·부모 수명·송신 backpressure 처리와 GitHub의 READY/run-id·유형별 최대 4개 FIFO를 함께 유지. 송신 실패는 기록 후 소비하며 재큐잉하지 않음 |
| 학습 입력 | GitHub `ids-normal-v2` 명시 manifest와 로컬 `frames.jsonl`+`manifest.json` 캡처 디렉토리를 각각 기존 검증기로 확인. `train_model`의 calibration과 manifest를 명시적으로 분리 |
| 실험 CLI | GitHub `run_ablation/analyze_roc/summarize_ablation`은 물리/관측 경로. 기존 합성은 `*_synthetic.py`, 10월 4일 실험은 `live_ablation/summarize_live/publication`으로 보존 |
| Fail-safe 입력 | `failsafe_demo.csv`는 GitHub의 310행 시연 입력. 로컬의 11행 빠른 입력은 `failsafe_demo_fast.csv`와 별도 manifest·기존 대응 시험으로 보존 |
| CHG-014 번호 중복 | 실장비·감사 현재 상태를 유지하고 GitHub 리뷰 상태/증거는 같은 폴더의 `review-*-2026-10-03.md`로 원문 보존. `vcan-summary.json`도 보존 |
| 증거 파일 | `.gitattributes`로 실험·감사 자료의 바이트 및 기존 SHA256 유지. 역사 자료의 공백·개행을 일괄 정리하지 않음 |

통합된 IDS의 공정 큐/학습 경계 조합은 새로운 소스 버전이다. 10월 4일 실장비 결과를 이 통합 버전의 물리 재시험으로 간주하지 않는다.
