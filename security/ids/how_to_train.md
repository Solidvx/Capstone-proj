# IDS 학습·평가 재현 절차

프로젝트 루트에서 실행한다. 사용자 첫 작업은 [임시_할일.md](../../임시_할일.md)이며, 아래 CAN 실행은 환경·빌드·정상 통신 확인 **이후** 단계다. 기존 키·모델·정상 로그를 덮어쓰지 않는다. 실제 키 내용은 공개하지 않는다.

## 1. 정상 학습 데이터

공격 송신기가 없고 정상 제품 ECU만 송신하는 고립 시험버스를 사용한다. 예시 위치 `tmp/`를 먼저 준비하고 신규 파일 이름/run ID를 정한다. 노브를 정상 구간으로 유지한다. 센서 측정/가상값 혼합인 경우 원자료 manifest에 source mode를 별도 기록한다.

```bash
.venv-handoff/bin/python -m security.capture_normal \
  --interface can0 --duration 30 --run-id train-normal-001 \
  --output tmp/train-normal-001.jsonl --manifest tmp/train-normal-001.manifest.json
```

capture는 COMPLETE·SHA·프레임 형식/연속성을 검사한다. 최소 조건 통과가 학습 대표성·최종 성능 합격은 아니다. interrupted/INVALID 자료를 이름만 바꿔 사용하지 않는다. 라이브 실행 시 raw와 manifest를 반드시 함께 지정한다.

```bash
.venv-handoff/bin/python -m security.ids.runtime \
  --interface can0 --train-normal tmp/train-normal-001.jsonl \
  --normal-manifest tmp/train-normal-001.manifest.json \
  --secoc-key /EXISTING_KEY_PATH --run-id ids-check-001 \
  --log tmp/ids-check-001.jsonl --duration 30 --send-alerts
```

`/EXISTING_KEY_PATH`는 기존 키 경로로 바꾼다. READY의 rules+if/send_alerts와 종료코드를 확인한다. --rules-only는 IF 성능 시험이 아니다. pickle 모델을 읽지 않고 기존 train_model과 고정 random_state로 매번 학습한다. 학습 SHA·sklearn 버전·파라미터가 바뀌면 동일 모델 실험으로 합치지 않는다.

## 2. 임계 후보와 독립 최종 평가

학습·calibration·evaluation을 별도 capture/run/SHA로 분리한다. 인접 윈도우를 같은 캡처에서 잘라 두 split으로 나누어 독립이라고 주장하지 않는다. 공격 라벨은 실제 주입 구간을 검증해 만들며 경보로 추측하지 않는다. 사용한 seed/profile/family 목록을 보존한다. 새로운 seed가 미지 공격이라는 뜻은 아니다.

설정·분석 안내에 따라 captures template → score_ids_captures → analyze_roc → render_roc를 실행한다. 기본 후보 조건은 정상 FPR ≤5%와 **각 네 공격** TPR ≥90%이며 calibration만 사용한다. 후보가 없으면 미달을 그대로 기록한다. 평가 결과로 임계를 재튜닝한 자료를 같은 독립 최종 평가라고 하지 않는다.

## 3. wire FPR·Ablation·반복

오프라인 IF ROC, 실제 정상 0x200 윈도우 FPR, 3구성×4공격 시행 결과는 각각 다른 분모다. 위 분석 안내의 run_normal_fpr·M5 12회 파일럿을 통과한 뒤 장비 조건과 임계를 동결하고 공식 물리 실험을 진행한다. 반복은 verify_reproducibility로 raw manifest/원장을 검증해 비교한다. 누락·손상·중단은 원본을 보존하고 새 run ID로 재수집한다.

## 제한

- IF_ANOMALY는 원인 미분류 로컬 진단이며 현재 wire 공격 유형을 임의로 만들어 전송하지 않는다. 이를 유형화·전송하려면 정책/계약 검토가 선행돼야 한다.
- 현재 후보 분석이 runtime의 `anomaly > 0` 임계를 자동 변경하지 않는다. 적용에는 별도 코드·회귀·장비 평가가 필요하다.
- vcan에는 물리 중재/부하/센서·화면 표시 지연이 없다. 그 결과로 실제 Pi·공식 물리 합격을 대신하지 않는다.
