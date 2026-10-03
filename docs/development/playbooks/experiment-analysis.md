# 실험 설정·돌아온 로그·IF 분석

사용자가 Pi를 조작하고 Codex는 소스와 반환 자료를 검토한다. 최초 장비 준비는 루트 [임시_할일.md](../../../임시_할일.md)의 1~4번이다. 아래는 **자료가 준비된 뒤** 사용하는 도구이며 지금 공격을 시작하라는 지시가 아니다. ICD/HAL/제품 인증 정책과 실행 중인 IDS 임계는 변경하지 않는다.

## M5 설정 사전 검사

`security/experiments/m5-settings.template.json`을 제외 경로 `tmp/`에 복사한 뒤 모든 `REPLACE_`를 실제 환경 값으로 바꾼다. 실제 장비 주소·키 경로가 들어간 설정은 Git에 넣지 않는다. 명령은 프로젝트 루트에서 실행한다.

```bash
python3 -m security.experiments.validate_m5_settings \
  --settings tmp/m5-settings.json --environment physical-can
```

`STATIC_VALID`는 argv·공통 run ID·원격 실행 제한 시간·Node B 대상 일치만 확인한다. SSH 연결, 같은 키, 시계, sudo 권한, 실제 CAN 상태를 증명하지 않는다. observer와 receiver는 **같은 Node B**에서 실행해 단조 시각을 비교한다. Node B에도 `.venv-handoff`와 Python 의존성이 필요하므로 최초 빌드 결과 확인 후 준비한다. `sudo -n`이 거절되면 권한을 임의 완화하지 않고 기존 실행 방식을 검토한다. 템플릿은 공백 없는 프로젝트/키 경로를 전제로 하므로 공백이 있다면 원격 셸 인용도 검토한다.

템플릿의 Qt offscreen은 Service 계측용이지 물리 화면 표시·UI 지연 시험이 아니다. 별도 실제 화면 증거를 수집한다. 제품 ECU 중단, 고립 시험버스 확인, READY 확보 후에만 [M5 파일럿](m5-ablation-runner.md)을 진행한다. 설정 검사가 실행 하네스에도 포함되어 있다. 실패한 실행 산출물은 덮어쓰지 않는다.

## 반환 CAN 자료의 무결성·수락 판정

원본 `candump -L` 파일을 `candump.log`, 같은 실행의 수신기 JSONL을 `receiver.jsonl`로 **복사**해 새 증거 폴더에 둔다. raw 자료는 `tmp/`에 보관한다. `-td` 간격 표시만 남긴 캡처는 절대 시간 분석 입력으로 사용하지 않는다.

```bash
python3 -m security.experiments.inspect_evidence \
  --input-dir tmp/it002-return --mode failsafe --seal \
  --run-id IT002-001 --environment physical-can --interface can0
python3 -m security.experiments.inspect_evidence \
  --input-dir tmp/it002-return --mode failsafe \
  --output-dir tmp/it002-report
```

`--seal`은 SHA256 메타데이터를 새로 만든다. seal 이후 손상 검사이며 수집 전부터 자료가 진짜라는 암호학적 보증은 아니다. `run_id`는 수신기 JSONL과 같아야 한다. 새 출력 폴더만 허용한다. 파일 누락·해시 변경·wire-only 근거는 `INVALID`, 유효한 자료에서 기대 동작 불일치는 `FAIL`로 남긴다.

| mode | 필요한 입력과 판정 |
|---|---|
| `failsafe` | dump+receiver. WARNING→CRITICAL 두 이벤트 간격 >10초, 사이 BMS 인증쌍 >100개, Fail-safe counter 증분 1, 수신기 수락을 함께 확인 |
| `tamper` | dump+receiver. 고립 fixture의 정상75%→MAC_FAIL/last-good75%→거절에 쓴 같은 counter 정상70% 복구 확인 |
| `period` | dump+`period.csv`+`period.manifest.json`. [주기 도구](security-can-integration.md)의 정규화 후 run ID·원본 SHA 일치 검사와 기존 주기 판정 |
| `ablation` | M5 하네스 결과 폴더. seal 없이 12개 파일럿/공식 행렬의 실제 누락·동일 입력·결과를 기존 요약기로 검사 |

`CONFIRMED`는 wire와 Service 반영 확인이다. 화면 픽셀·실제 UI 지연이나 모든 보안 시험 합격을 뜻하지 않는다. 최종 결과는 `result.json`, 간단한 상태표는 `report.md`로 생성한다.

## IF 점수·오탐률·ROC — 오프라인 비교 전용

학습, 임계 선정(calibration), 최종 평가(evaluation)는 **별도 캡처/run ID/SHA256**로 준비한다. 같은 파일을 이름만 바꾸거나 학습 자료를 평가에 쓰면 거절한다. 최종 평가를 보고 임계를 재선정하지 않는다. 먼저 정상 학습 raw+manifest가 `security.capture_normal.validate_capture`를 통과해야 한다.

`security/experiments/ids-captures.template.json`을 `tmp/`에 복사해 각 경로·SHA256·실측 수집 시간·run ID를 바꾼다. 예시 120초/3초는 실측이 아니다. 정상과 네 공격 유형을 calibration/evaluation 각각 별도 기록한다. 완전한 수집을 확인한 경우만 `COMPLETE`로 표시한다. 공격 파일 전체에 공격 라벨을 붙이려면 전체가 실제 공격 구간이어야 한다. warmup/baseline/drain이 섞인 파일은 검증된 구간으로 분리하고 그 파생 파일의 SHA·시간 원점을 다시 기록한다.

평가 캡처 JSONL은 한 줄에 프레임 하나이며 `t`는 해당 캡처 시작 후 초, `can_id`는 정수, `data`는 hex이다.

```json
{"t":0.1,"can_id":256,"data":"96c80e10ffec4100","dlc":8,"extended":false,"remote":false,"error":false}
```

시간 역행/범위 위반, 잘못된 프레임·해시·라벨은 거절한다. 1초 비중첩 완전 윈도우 `[n,n+1)`를 사용하고 끝의 부분 윈도우는 버린다. 빈 완전 윈도우는 유지하며, 표준 DLC8이고 오류/remote가 아닌 프레임만 특징에 넣고 IDS 자체 0x200은 제외한다. accepted 프레임 >4096/윈도우, 전체 점수 >20,000이면 조용히 잘라내지 않고 거절한다. 이는 live 스트리밍 윈도우 스케줄과 같다고 주장하지 않는다.

```bash
.venv-handoff/bin/python -m security.experiments.score_ids_captures \
  --dataset tmp/ids-captures.json --output-dir tmp/ids-analysis-001
```

실제 sklearn IF를 기존 `train_model`로 학습하며 pickle 모델은 불러오지 않는다. 학습 SHA·파라미터·라이브러리 버전·model ID·각 윈도우 점수·ROC/AUC·분모를 결과에 기록한다. 기본 후보 조건은 calibration 정상 FPR ≤5%, **각각의** 네 공격 TPR ≥90%다. 가장 높은 만족 임계를 선택하고 동결해 evaluation에 적용한다. 만족 후보가 없으면 `NO_FEASIBLE_THRESHOLD`와 종료코드 2를 남긴다. 실패가 없었던 것처럼 수치를 채우지 않는다.

이미 생성된 점수/manifest를 재판정할 때:

```bash
python3 -m security.experiments.analyze_roc \
  --manifest tmp/ids-analysis-001/manifest.json \
  --output tmp/ids-analysis-001/roc-recheck.json
```

`normal_100_window_minimum_met`는 최종 평가 정상 완전 윈도우가 100개 이상이라는 뜻이다. FPR 분모는 그 정상 윈도우 수다. ROC/AUC는 IF 점수의 비교이며 **실제 0x200 경보 오탐률·rules+IF 전체 탐지율·SecOC 차단율·1,200회 공식 trial 합격과 다른 지표**다. `official_trial_acceptance`는 항상 false다. runtime의 임계나 IF 경보 전송 정책은 자동 수정하지 않는다. 후보 적용은 별도 코드·회귀 검증과 live 정상 오탐률 시험 후 결정한다.

## 현재 검증 경계

Linux 단위시험에는 실제 sklearn 점수 생성 경로가 포함된다. 합성 fixture 테스트 통과를 실제 두 Pi 탐지 성능으로 발표하지 않는다. Node A/B 환경·물리 CAN·배선·실제 화면·공식 1,200회 결과는 사용자의 반환 자료를 받아 별도 인수한다.

## 실제 0x200 정상 윈도우 오탐률

`run_normal_fpr.py`는 위의 M5 설정을 재사용해 인증 ON receiver·정상 fixture·IDS를 준비하고 **공격 프로세스 없이** Node B whole-bus observer를 실행한다. 같은 버스의 제품 ECU를 동시에 송신시키면 안 된다. 첫 Pi 빌드/정상 통신 인수 후에만 실행한다.

```bash
.venv-handoff/bin/python -m security.experiments.run_normal_fpr \
  --settings tmp/m5-settings.json --output-dir tmp/normal-fpr-001 \
  --run-id normal-fpr-001 --interface can0 --environment physical-can \
  --windows 100 --warmup 5 \
  --confirm-product-ecu-stopped --confirm-isolated-test-bus
```

이 명령은 CAN/키/서비스 설정을 바꾸지 않는다. 소유한 자식 프로세스만 회수한다. Node B의 observer는 natural END까지 정상 완료해야 한다. IDS READY는 rules+if 및 send_alerts=true, receiver/sender READY는 인증 ON이어야 한다. supervisor는 수집 종료까지 세 프로세스가 살아 있음을 확인한다. 원격 명령은 실제 작업을 기다리는 foreground 명령이어야 하며 daemon을 띄우고 곧바로 종료하는 wrapper를 사용하지 않는다.

사전 고정 정책: warmup 뒤 길이=이동폭=1초인 `--windows`개의 완전 윈도우. 종료에는 여유 1초를 추가하지만 분모는 고정 개수만 사용한다. 표준 DLC8 BMS 0x100/0x102가 **각 윈도우에 각각 최소 8개**, 평가 경계 포함 최대 공백 300ms 이하이어야 한다. 빈/유실 윈도우를 TN으로 넣거나 조용히 제외하지 않고 전체 자료를 INVALID로 보존한다. driver rx_dropped/rx_errors/tx_errors 전후 증가·reset·미수집, SO_RXQ_OVFL 소켓 drop, 프레임 손상/예상 밖 ID, 중단/END 누락도 거절한다. 증거 hash와 run ID를 재검사한다.

0x200 AttackType 1~4가 한 번 이상 수신된 정상 윈도우가 FP다. 같은 윈도우의 여러 경보는 FP 1개이며 AttackType 0=None은 FP로 세지 않는다. 정상 FP+TN이 분모다. 100개 미만은 `INSUFFICIENT_WINDOWS`, 충분하면 ≤5%는 관측 목표 PASS, 초과는 FAIL이다. 오류는 INVALID다. 3윈도우 연결 파일럿의 종료코드 2는 분모 미달이라는 정상적인 결과일 수 있으므로 JSON status를 함께 확인한다.

```bash
python3 -m security.experiments.analyze_normal_fpr \
  --input-dir tmp/normal-fpr-001 --output tmp/normal-fpr-001/recheck.json
```

산출물은 bus/receiver/normal/ids-console 로그·stderr·settings·manifest·`fpr-result.json`이다. IF_ANOMALY는 현재 원인 미분류 로컬 진단이므로 **wire로 전송하지 않는다**. 따라서 wire 경보 FPR와 오프라인 IF FPR를 모두 보고하며, 낮은 wire FPR가 IF 탐지 성능을 증명하지 않는다. 0x200은 ICD상 인증 비대상이다. 정상-only 출처·다른 송신기 부재·fixture의 제품 정상 입력 대표성은 별도 운영자 확인이 필요하며 `official_acceptance`는 자동 true로 바꾸지 않는다. vcan 결과는 물리 최종 인수가 아니다.

## 그림·CSV·재현성 인계

matplotlib 없이 headless SVG를 생성한다. calibration/evaluation ROC를 별도 패널로 표시하며 AUC·좌표·완전 endpoint를 검사한다. SVG는 브라우저에서 열 수 있고 PNG가 필수인 발표 템플릿에서는 별도 변환한다. JSON 원수를 보존한다.

```bash
python3 -m security.experiments.render_roc \
  --input tmp/ids-analysis-001/roc-result.json --output tmp/ids-analysis-001/roc_curve.svg
python3 -m security.experiments.summarize_ablation \
  --input-dir tmp/m5-001 --output tmp/m5-001.summary.json \
  --csv-output tmp/m5-001.summary.csv
python3 -m security.experiments.verify_reproducibility \
  --previous tmp/m5-001 --current tmp/m5-002 --output tmp/m5-repro.json
```

CSV는 비율 0..1·환경·유효/무효/미실시 분모·지연을 그대로 보존하고 None은 빈 칸으로 둔다. 미정의 값을 0으로 채우지 않는다. IF ROC JSON에는 같은 윈도우 TP/FP/TN/FN 기준 Precision/Recall/FNR/TNR/F1/Balanced Accuracy/MCC도 기록한다. 분모 0은 null이며 시행 기반 지표와 합치지 않는다.

재현성 비교는 별도 run ID의 두 **완전한 검증 행렬**을 입력으로 받고, 환경·시행수·설정/도구 hash·구간·실제 입력 hash·seed가 같아야 한다. REP-1=A의 공격 성공률 절대 차이 ≤5%p를 12개 조합 각각 비교한다. 0%→5%도 5%p다. 작은 파일럿은 경로 검증이며 100회/조합의 공식 재현성·통계적 신뢰성을 대신하지 않는다. 같은 폴더, 누락, 입력/모델 조건 변경은 INVALID로 남긴다.
