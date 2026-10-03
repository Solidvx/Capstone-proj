# CHG-013 — 보안 실험 도구와 Ablation 합성 사전검증

요청(2026-10-03): 보안 실험(ECU M5)을 진행할 수 있도록 공격 도구, Ablation 하네스, 집계·ROC 도구를 만들고, 합성 등급 사전검증으로 1,200 매트릭스와 정상 오탐을 낸다. 물리 CAN 최종 판정은 장비에서 수행한다.

범위:

- `security/attacks/attack_simulator.py`: 실제 SocketCAN 공격 주입기 4종(flooding·fuzzy·replay·spoofing). 프레임 생성·안전 게이트는 순수 함수. 실제 `can*` 인터페이스는 `--i-am-on-a-test-bus` 필요, rate·duration 상한, 첫 주입 시각 기록.
- `security/experiments/ablation_core.py`: 세 구성(Config 1 무방어 / 2 SecOC / 3 SecOC+IDS)이 같은 trial 입력을 받고, 공격 성공·SecOC 차단·IDS 탐지를 각각 독립 관측. 수신 판정은 실제 `SecOcModule`, IDS는 `runtime_detector` 규칙.
- `security/experiments/run_ablation.py`: 3구성×4공격×100회=1,200행 CSV(합성 등급). 기존 파일 덮어쓰기 거부.
- `security/experiments/summarize_ablation.py`: (구성,공격)별 성공률·차단율·탐지율. 분모 명시, 미측정은 공백 유지.
- `security/experiments/analyze_roc.py`: 규칙 IDS ROC-AUC·확정 임계·정상 오탐(TC-EXP-005). 선정 seed와 평가 seed 분리(M5 3.5.1).

M5 준수: 공격 성공을 `not(blocked or detected)`로 계산하지 않는다. seed에 config를 넣지 않는다. 합성에서 측정 불가한 flooding·fuzzy 가용성은 공백으로 둔다. 모든 결과에 실행 환경 등급(synthetic)을 표기한다.

제외(물리 등급 과제): 두 RPi 물리 CAN에서의 1,200 최종 판정, flooding·fuzzy의 실제 가용성·수용 측정, 실제 공격 시작→경보 지연(TC-PERF-003·IT-005), IVI 화면 통합. IVI·IDS 제품 코드 변경 없음, ICD 변경 없음.
