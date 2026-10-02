# CHG-007 검증 증거

- 기준 커밋 8c78672, 브랜치 feat/ecu-can-ids. 기존 원본 작업 트리와 독립 worktree.
- 규칙·독립 SecOC 관찰·IF 연동·JSONL 재생·SocketCAN 경로 구현. 기존 wire/IDS 특징 계약은 유지.
- 최종 명령: `.venv/bin/python -m pytest security/tests -q` → **24 passed in 31.32s**. 기존 13개 + 엔진 8개 + CLI/SocketCAN 모의 3개. 실제 sklearn 모델 학습·IF 모드 재생, 신규 로그 보호, 입력 오류 종료, CAN codec·timeout·short write·close를 확인했다.
- 환경: WSL Ubuntu, Python 3.12.3, scikit-learn 1.9.1, pytest 9.1.1. 가상환경에 security/requirements.txt 설치. 초기 IF 실패는 의존성 설치 미완료였으며 설치 후 전체 재실행 통과.
- 기존 정상 100쌍에 탐지 없음, counter 재사용/역전/+101/wrap/+100, 실패 MAC counter 미소비, 무수신 경계, 버퍼 상한, 자체 경보 피드백 제외, 0x200 BE 8바이트를 자동 시험했다. 이 결정적 사례를 실측 탐지율·오탐률로 해석하지 않는다.
- IF 단독 이상·메시지 누락 등 원인 미확정 사건은 로컬 로그다. 기존 AttackType을 임의 확장하지 않으며 규칙으로 분류한 사건만 전송한다. Node A 독립 SecOC 관찰은 Node B 검증 결과 전달을 대체하지 않는다.
- WSL `vcan` 생성은 Unknown device type으로 실패. 가상/물리 CAN 송수신과 Node B 화면까지 통합은 미검증.
- 기존 `security/experiments/run_eval.py` 종료 코드 0. seed42 기존 합성 평가의 규칙 ROC-AUC 0.873, IF 0.942를 확인했다. 이는 새 runtime 탐지기의 성능 결과가 아니며 기존 평가가 유지됨을 확인한 회귀 실행이다.
- 새 문서 링크·코드 펜스·ICD 무변경 검사 및 `git diff --check` 통과. 핵심 로직은 hardware 없는 테스트로 검증했으며 물리 성능 보장은 하지 않는다.
