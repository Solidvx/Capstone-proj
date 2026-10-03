# CHG-013 — 초기 합성 실험과 후속 물리 통합 기록

서로 다른 작업 환경의 기록을 합쳐 보존한다. 아래 각 절의 실행 환경·시점·판정 범위를 섞지 않는다. 초기 PR #21의 합성 CLI는 `security/experiments/*_synthetic.py`로 보존했고, 원래 파일 이름은 후속 물리 실행/독립 캡처 분석 도구가 사용한다. 초기 실행 명령은 당시 이력이며 현재 재현 명령은 [M5 안내](../../../development/playbooks/m5-ablation-runner.md)의 합성 도구 분리 절을 따른다.

## 초기 합성 실험 — PR #21 기록

# CHG-013 — 보안 실험 도구와 Ablation 합성 사전검증

요청(2026-10-03): 보안 실험(ECU M5)을 진행할 수 있도록 공격 도구, Ablation 하네스, 집계·ROC 도구를 만들고, 합성 등급 사전검증으로 1,200 매트릭스와 정상 오탐을 낸다. 물리 CAN 최종 판정은 장비에서 수행한다.

범위:

- `security/attacks/attack_simulator.py`: 실제 SocketCAN 공격 주입기 4종(flooding·fuzzy·replay·spoofing). 프레임 생성·안전 게이트는 순수 함수. 실제 `can*` 인터페이스는 `--i-am-on-a-test-bus` 필요, rate·duration 상한, 첫 주입 시각 기록.
- `security/experiments/ablation_core.py`: 세 구성(Config 1 무방어 / 2 SecOC / 3 SecOC+IDS)이 같은 trial 입력을 받고, 공격 성공·SecOC 차단·IDS 탐지를 각각 독립 관측. 수신 판정은 실제 `SecOcModule`, IDS는 `runtime_detector` 규칙.
- `security/experiments/run_ablation.py`: 3구성×4공격×100회=1,200행 CSV(합성 등급). 기존 파일 덮어쓰기 거부.
- `security/experiments/summarize_ablation.py`: (구성,공격)별 성공률·차단율·탐지율. 분모 명시, 미측정은 공백 유지.
- `security/experiments/analyze_roc.py`: 오프라인 규칙 베이스라인의 ROC-AUC·확정 임계·정상 오탐(TC-EXP-005). 공식 4종으로 NFR-SEC-003·004를 판정하고 공식 외 masquerade는 규칙·사양기반 참고로 분리. 선정 seed와 평가 seed 분리(M5 3.5.1). Ablation Config 3의 실시간 IDS와는 다른 탐지기다.

M5 준수: 공격 성공을 `not(blocked or detected)`로 계산하지 않는다. seed에 config를 넣지 않는다. 합성에서 측정 불가한 flooding·fuzzy 가용성은 공백으로 둔다. 모든 결과에 실행 환경 등급(synthetic)을 표기한다.

제외(물리 등급 과제): 두 RPi 물리 CAN에서의 1,200 최종 판정, flooding·fuzzy의 실제 가용성·수용 측정, 실제 공격 시작→경보 지연(TC-PERF-003·IT-005), IVI 화면 통합. IVI·IDS 제품 코드 변경 없음, ICD 변경 없음.

---

## 후속 물리 통합 도구 — 로컬 기록

# CHG-013 — 물리 CAN 보안 통합 도구

요청(2026-10-03): 사용자가 ADS1115·SecOC·Fail-safe 물리 시험과 증거 수집을 계속하는 동안, 계획서에 남은 ECU 보안 통합 도구를 구현한다.

범위: FR-SEC-005의 4종 제한형 SocketCAN CLI, IDS 정상 JSONL/manifest 수집, IT-004의 정상 기준→MAC 1비트 변조→같은 counter 복구 fixture, 기존 실시간 IDS의 `0x200` 경보 cooldown 중 상위 Flooding 분류 보존, IT-002 결정적 `failsafe_demo.csv`·manifest와 전이 간격 회귀시험, TC-PERF-002용 `candump -L` 정규화·엄격 판정 도구, 단위시험과 물리 실행 절차.

보존: ICD v1.6의 CAN ID·DLC·payload·HMAC 입력·counter 규칙은 변경하지 않는다. 실제 키를 저장·출력하지 않는다. 공격 도구는 `vcanN`을 기본으로 하고 물리 `canN`은 격리 시험 확인과 실행 상한을 강제한다.

제외: 실장비 공격 실행, 물리 버스 점유율·탐지율·오탐률 주장, 1,200회 Ablation 결과, 미승인 세션 프로토콜, 자동 배선/인터페이스 재설정.
