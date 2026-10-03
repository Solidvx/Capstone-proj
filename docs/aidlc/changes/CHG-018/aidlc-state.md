# CHG-018 — 후속 변경 Draft PR 정리

- 요청: IT-002 결과를 기다리지 않고 브랜치·커밋·push·Draft PR 생성. 머지는 요청하지 않음.
- 브랜치: `feat/common-integration-preparation`, base `develop`.
- 기존 develop의 PR #21 합성 실험과 로컬 후속 도구가 같은 경로를 사용해 충돌했다. 합성 CLI3개를 `*_synthetic.py`로 보존하고 기존 core/시험·CHG-013 원문을 유지했다. 현재 CLI 이름의 변경은 [M5 안내](../../../development/playbooks/m5-ablation-runner.md)에 명시했다.
- PR #24 `feat/ids-normal-fpr`는 별도 열려 있다. 자동 머지/닫기/수정하지 않았으며 SDD 및 CHG-013 기록 변경은 후속 합류 시 검토해야 한다. 본 PR의 wire FPR와 #24의 규칙/합성 FPR 범위를 혼합하지 않는다.
- 결과 경계: 003 Pi ECU16/IVI11/Python63+9 subtests 및 정상 통신 확인. **IT-002·IT-004/005·물리 공식1,200회·장시간 인수 대기**. 워치독 미구현/coverage 미달 유지.
- PR 이전 로컬 소스 재검증: Python71+9 subtests, ECU ASan16/16, IVI ASan12/12 통과. **최신 develop 통합 후 Python80+9 subtests 통과**, 보존 합성 Ablation CLI1,200행 생성/요약 실행 확인. 합성 실행을 물리 인수로 표시하지 않음.
- 제외: 키·토큰·실제 장비 주소·tmp 원시 로그·모델·build/바이너리·003 archive. 원시 자료는 기존 tmp에 보존하며 Pi 코드/키/CAN 설정을 변경하지 않음.
