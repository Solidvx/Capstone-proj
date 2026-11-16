# Node A CAN IDS 실행

`runtime_detector.py`는 입력 시각을 주입받는 탐지 엔진, `runtime.py`는 JSONL 재생/SocketCAN 입출력이다. 기존 오프라인 `run_eval.py`와 분리되며 기존 7개 특징·IF 구현을 재사용한다.

## 오프라인 평가 지표의 단위·미정의 값

`rule_baseline.confusion_metrics`는 같은 판단 단위의 비음수 정수 TP/FP/TN/FN을 사용한다. Precision/Recall/FPR/FNR/TNR/F1/Balanced Accuracy는 ratio, MCC는[-1,1]의 무차원 계수다. 분모0은None/JSON null·화면N/A이며0%나PASS가 아니다. 빈 자료/한 클래스의 ROC-AUC도 미정의다. metrics_at은 점수/라벨/유형의 길이 불일치·비유한 점수·잘못된 정답 라벨을 거부하고 유형별 detected/windows 원수를 남긴다.

기존 경계는 `metrics_at: score >= threshold`, 오프라인 `analyze_roc: score > threshold`로 서로 다르며 보존했다. 모델/임계 버전과 함께 해석하고 수치만 합치지 않는다. live 유형 MATCH·시행 탐지율·프레임 차단율·정상 윈도우FPR도 분모가 다르다.

`python security/experiments/run_eval.py`는 합성 학습90창·별도 정상 보정60창·평가210창(정상60/공격150)의 예시다. 과거 평가 정상 점수로 임계를 고르던 경로를 분리했다. 기존 학습/평가 draw는 유지하고 별도 draw의 정상 점수만 임계에 사용한다. 고정1%는 합성 보정 목표로서 실제 보정/평가FPR 보장이 아니다. 실제 capture·공격 family holdout·물리 IF 효과의 인수가 아니며, live runtime의 규칙/IF 보정·CAN 계약은 바뀌지 않는다. [원수/두 단계 비교/회귀](../../docs/aidlc/changes/CHG-029/n06-metrics-20261113.json)를 따른다.

## 선택형 CPU·메모리·처리량 계측

기본 실행은 계측하지 않는다. CLI에 `--measure-resources`를 추가하거나, 관리형 IDS의 기존 비공개 설정 JSON에 `"measure_resources": true`를 명시하면 같은 events 로그에 N07 측정을 남긴다. 숫자/문자열을 boolean 대신 사용할 수 없다. START/READY·startup identity에도 선택을 기록하므로 이전 pilot의 실행 형상과 섞지 않는다. 운영 규칙/IF 임계·특징·호출·CAN bytes는 바꾸지 않는다.

| 측정 | 단위·범위 |
|---|---|
| 경과/CPU | 모델 준비·SocketCAN open 후의 host monotonic 초/현재 프로세스 CPU 초. CLOCK/READY·루프·END 기록과 계측 비용 포함. 학습/초기 로드/자식 CPU 제외 |
| CPU 비율 | CPU 초/host 경과 초×100. 한 코어 기준이므로 병렬 사용 시100% 초과 가능 |
| RSS | Linux VmRSS의 시작·종료 bytes. 구간 peak를 측정한 것으로 쓰지 않음 |
| 생애 peak RSS | getrusage의 플랫폼 단위를 bytes로 변환. import/학습을 포함한 프로세스 생애 peak이며 구간 전용 peak 아님. 미지원은null+사유 |
| 프레임/윈도우 | 완료한 모든 원본/auth/제어/경보 프레임과 MODEL_EVALUATION 원수. frames/s와windows/s는 별도 분모이며 최대 지속 능력 아님 |
| 단계 시간 | 프레임/타이머 처리·특징 추출·anomaly·별도 wire_score 호출의ns 원수/실패/합/최소/최대/평균·고정8버킷. detector 시간이 하위 단계를 포함하므로 합산하지 않음 |
| 손실 | 관측 socket drop·feature buffer evict·receive epoch reset과 미상 queue/wire/interface loss를 구분. replay에서 실제 버스 손실0을 가정하지 않음 |
| 모델 | 파일을 로드하지 않고 학습한 실제 state hash. 파일 크기/hash는null이며 pickle 직렬화 크기로 대체하지 않음 |

IF 윈도우1개와 scoring method 호출1회는 같은 단위가 아니다. 현재 양성일 때 wire_score가 별도 scoring을 수행하므로 anomaly/wire 호출을 각각 기록한다. 호출0의 시간 최소/평균은null이고 추가 추론으로 수치를 채우지 않는다.

live는1초마다 누적 RESOURCE_SAMPLE을 남기고 정상·오류·인터럽트 종료에는 RESOURCE_SUMMARY를 남긴다. 선택 계측 실행만 SIGTERM을 받아 요약 후143으로 종료하며 owner의 종료 기한/kill은 유지한다. SIGKILL/전원 단절에는 최종 요약이 없을 수 있다. 파일 수집 COMPLETE와 자원 구간 COMPLETE는 다른 상태다. 마지막 sample만 있으면 INCOMPLETE, 종료 요청/오류는 INTERRUPTED/ERROR로 보존한다.

```sh
python3 -m security.ids.runtime --replay INPUT.jsonl --rules-only \
  --measure-resources --run-id N07-REPLAY --log NEW-EVENTS.jsonl
python3 -m security.experiments.summarize_resources --events NEW-EVENTS.jsonl \
  --out NEW-RESOURCE-REPORT.json
```

분석은 한 세대의 고정 파일 budget/64KiB 행·세대/시각/원수·단위·입력 변경/hash를 검사한다. 기본 budget은 기존 수집과 같은64MiB이며 명시적 스트리밍 수집을 선택한 경우 분석의 `--max-bytes`도 같은 예산으로 지정한다. partial/미계측 결과의 CLI exit1은0%나PASS가 아니다. PC session collect_ids는 선택 계측을 확인하면 같은 파일을 분석한 `ids-GENERATION-resources.json`을 해당 case manifest/hash에 포함한다. 시행 구간/공격 유형별 수치로 임의 분배하지 않는다. [실제 vcan 세대/IF 재생·검증/한계](../../docs/aidlc/changes/CHG-029/n07-resources-20261113.json)를 따른다.

## 입력과 모드

저장소 루트에서 `python -m security.ids.runtime --help`를 실행한다. 기본 모드를 묵시적으로 선택하지 않는다. `--train-normal 정상.jsonl`은 별도 정상 데이터로 IF를 학습해 사용하고, `--rules-only`는 개발·ablation용이다. 모델 pickle을 불러오지 않는다. 정상 데이터는 최소 두 개의 완료된 1초 창이 필요하다. `capture_normal` 출력은 `--normal-manifest`로 ids-normal-v2 해시·완료·프레임 검증을 적용한다. `experiments.can_capture` 출력은 `--train-normal <폴더>/frames.jsonl`과 같은 폴더의 manifest.json을 검사한다. manifest 없는 임의 JSONL을 CLI에서 학습하지 않는다. `--calibrate-normal`은 별도 정상 캡처 디렉토리의 frames.jsonl이며 학습과 다른 해시·충분한 창을 요구한다.

JSONL의 CAN ID는 10진 정수, 데이터는 16진 문자열, `t`는 0 이상 단조 증가 초다. `tick`은 프레임 없이 시간만 진행한다. 실제 로그의 Unix 시각과 혼동하지 않는다.

```json
{"t":0.0,"can_id":256,"data":"96be1068ffec4100"}
{"tick":0.3}
```

```sh
python -m pip install -r security/requirements.txt
python -m pytest security/tests -q
python -m security.ids.runtime --replay input.jsonl --rules-only --log events.jsonl
python -m security.ids.runtime --replay input.jsonl --train-normal normal.jsonl --normal-manifest normal.manifest.json --log if-events.jsonl
```

로그는 신규 파일만 생성한다. 이미 있는 파일을 덮어쓰지 않는다. START에는 모드·임계 설정·SecOC 관찰 활성 여부, 프레임에는 NORMAL 또는 ANOMALY/DIAGNOSTIC와 timestamp/can_id/reason/anomaly_score, 정상 종료에는 END를 기록한다. NORMAL은 해당 검사에서 위반 없음이며 인증·무공격 보증이 아니다. 종료 코드 2는 입력/설정/통신 오류, 130은 사용자 중단이다.

## 검사와 경보

허용 ID/DLC/형식, BMS·Fail-safe 범위, BMS SOC/온도/전류 변화, 0x100/0x102 주기·누락, 전체 빈도를 검사한다. 이벤트형 0x101/0x103에 주기 timeout을 적용하지 않는다. `Config` JSON을 `--config`로 전달하면 운영 임계값을 변경할 수 있다. 기본 50ms 최소 주기, 300ms 누락, 초당 100프레임, 1초 내 실패 3회, SOC 20%p/온도 20°C/전류 100A 변화는 시험용 초기 정책이며 실차·실물 보정값이 아니다. 전압·전류의 ICD 표현 가능 범위는 추가 물리 제한을 임의로 만들어 좁히지 않는다.

`--secoc-key`에 정확히 32바이트 키 파일을 제공하면 Node A에서 버스를 독립 관찰한다. 두 원본/auth 슬롯과 counter 이력을 분리하고 100ms 만료, HMAC 상수시간 비교, uint32 delta 1..100을 적용한다. 키를 생략하면 MAC/Replay 검증은 비활성이다. 이 관찰은 Node B의 실제 인증 결과 수신이 아니며, 향후 인증 이벤트 전달 프로토콜을 임의 구현하지 않는다. 처음 관찰한 MAC과 재부팅의 replay 한계는 ICD와 같다.

IF는 최근 1초의 최대 4096개 프레임에서 7개 특징을 계산해 1초 간격으로 평가한다. 저장 한도 초과 상황에서는 잘린 창을 사용하므로 IF 점수의 완전성을 주장하지 않으며 FRAME_RATE 규칙을 병행한다. 학습은 최대 10000창으로 제한한다. IF_ANOMALY만으로 공격 유형을 추측해 새 wire 코드를 만들지 않는다.

추론 실행 근거는 로컬 JSONL의 `MODEL_EVALUATION`/`IF_WINDOW`로 남긴다. 시각, 창 시작, 프레임 수, 7개 특징, 보정 임계를 뺀 점수를 기록한다. 이 행의 `anomaly_score`는 부호가 있는 IF 결정값이며 확률이나 CAN 점수가 아니다. 양수일 때 별도 `ANOMALY`/`IF_ANOMALY` 행이 생긴다. 입력이 없으면 `MODEL_SKIPPED`/`IF_NO_INPUT`이며 정상 판정으로 세지 않는다. 두 계측 행은 공격 유형0이고 CAN 경보·사건 mask에 추가하지 않는다. 따라서 IF 단독 이상이 네 공격 중 하나로 표시되거나 공격을 차단했다고 해석해서는 안 된다.

`input_complete=false`는 해당 1초 창에서 4,096프레임 저장 상한 때문에 앞선 입력이 제거되었음을 뜻한다. 이 점수는 잘린 입력에 대한 진단값으로 보존하고 완전한 성능 평가 표본에서는 제외한다. 제거된 프레임이 창 밖으로 나가면 true로 복귀한다. 이 필드는 사용자 공간 창의 잘림만 추적하며 커널 drop·수신 epoch 공백이 없음을 증명하지 않는다. 정상 학습/평가 입력의 용량 초과는 기존대로 거부한다.

### session-v2 정상 IF 평가

새 세션은 제어/진단 프레임이 추가되므로 옛 정상 데이터를 재사용하지 않는다. `security.capture_normal --protocol session-v2`로 별도의 학습·보정·평가 자료를 수집한다. 세 자료는 같은 환경(vcan 또는 physical-can), 다른 run-id/내용/파일, 겹치지 않는 수집 시간이어야 한다. manifest의 해시·완료·프레임·주기 검사도 적용한다. 정상이라는 운영자의 선언 자체를 암호학적으로 증명하는 검사는 아니다. live session-v2 학습+보정에도 같은 분리 검사를 적용한다.

저장소 루트에서 실행 예시(경로는 실제 새 캡처로 대체):

```sh
python -m security.experiments.evaluate_session_if \
  --train fit.jsonl --train-manifest fit.manifest.json \
  --calibrate calibration.jsonl --calibration-manifest calibration.manifest.json \
  --evaluate evaluation.jsonl --evaluation-manifest evaluation.manifest.json \
  --out if-normal-report.json
```

평가기는 실시간과 같은 1초 특징 창 경계를 사용하고 IF 단독 정상 오탐 창 수/분모·점수·보정값·입력/소스 해시를 기록한다. 평가100창 미만은 `INSUFFICIENT_WINDOWS`다. `COMPLETE`는 계산 완료이며 품질 합격이 아니다. 결과는 공격 탐지율·유형 정확도·차단율·규칙 대비 추가 탐지 기여·실시간 인증을 측정하지 않는다. 기존 `evaluate_normal`의 legacy 보고서와 섞지 않는다.

재현을 위해 Python/scikit-learn/NumPy 버전과 실제 모델 매개변수도 기록한다. NaN/무한대 점수는 보고를 중단하며 오탐0으로 취급하지 않는다. 모델 계측 행은 경보 큐와 사건 mask에 반영되지 않는 회귀 시험으로 확인한다.

긴 제품 검사는 실패/사용자 중단도 `summary.json`의 `INVALID`/`INTERRUPTED`로 남긴다. 자식 프로세스와 임시 키 정리 후 `artifact-hashes.json`에 남은 로그·캡처·요약의 상대 경로와 SHA-256을 기록한다. 실행 실패를 오탐률0이나 제품 PASS로 바꾸지 않는다. OS 강제 종료/전원 단절처럼 정리 코드가 실행되지 못한 경우에는 최종 요약/해시가 없을 수 있으므로 완료 증거로 취급하지 않는다.

`common/test_session_if_products.py`는 선택 실행하는 긴 Linux vcan 제품 검사다. 기존 가상 버스가 비어 있어야 하며 `CAPSTONE_IF_LONG_TEST=1`과 `CAPSTONE_SESSION_TEST_INTERFACE=vcanN`을 모두 요구한다. 실제 ECU/Qt/규칙 IDS에서 기본105초씩 세 캡처를 만들고, IF 정상 평가 뒤 `rules+if` 감독자로 전환하여 추론10회 이상을 확인한다. 물리 can0는 거부하고 더미 키는 임시 디렉터리에서 정리한다. `--help`의 ECU/IVI/정책/감독자/출력 경로를 명시한다. 정상 수집 시계 변화·유실·공백은 무효로 보존하며 임계 완화나 성공할 때까지 자동 재시도하지 않는다. 이 짧은 제품 검사로 TC-SEC-006의 정상1000창/공격100창 인수를 대신하지 않는다.

| 로컬 사유 | 0x200 AttackType |
|---|---|
| UNKNOWN_ID_DIVERSITY (최근 1초 서로 다른 미등록 ID 3개 이상) | 1 Fuzzy |
| COUNTER_REUSE / COUNTER_BACKWARD | 2 Replay 의심 |
| MAC_FAIL 중 대기 원본이 이전에 인증된 payload와 동일 | 2 Replay 의심 |
| BMS_RANGE / BMS_STEP / FAILSAFE_RANGE / 그 외 MAC_FAIL | 3 Spoofing 의심 |
| FRAME_RATE 중 1초 창의 과반을 단일 미등록 ID가 차지 (suspect=그 ID) | 4 Flooding 의심 |
| 단일 UNKNOWN_ID / DLC / FRAME_FORMAT, PERIOD_TOO_SHORT, COUNTER_WINDOW, 위 조건 밖의 FRAME_RATE | 로컬 진단만; 유형 미지정 |
| MESSAGE_MISSING / AUTH_TIMEOUT / AUTH_ORPHAN / SECOC_FAILURE_BURST / IF_ANOMALY | 로컬 진단만; 원인 미확정 |

우선순위: Fuzzy 판정(미등록 ID 다양성)이 유지되는 동안 등록 ID의 내용·인증 이상(BMS/Fail-safe 범위·변화, MAC/counter)과 DLC/FRAME_FORMAT은 1 Fuzzy로 귀속한다. 무작위 ID가 등록 ID에 걸리는 것은 fuzzing의 일부이므로 별도 Spoofing/Replay로 보내지 않는다. 같은 시간에 실제 별개 공격이 겹치면 Fuzzy로만 보일 수 있다. 등록 ID의 고빈도(Replay/Spoofing 주입)와 짧은 주기는 Flooding으로 단정하지 않고 기록만 한다. 사유 문자열은 IVI SecOC 거부 사유(MAC_FAIL/COUNTER_*)와 같게 유지한다.

유형은 규칙에 따른 의심 분류이며 실제 공격 원인 확정이 아니다. 미분류 사건을 AttackType=0 경보로 전송하지 않으므로 IVI 경고를 잘못 해제하지 않는다. 자체 0x200 입력은 탐지 창에서 제외한다. 경보 점수는 규칙 발생 시 1.00, IF 진단은 기존 IF wire_score 정규화 값을 기록하며 확률이 아니다.

## Linux SocketCAN (장비 없이도 vcan 사용 가능)

이미 준비된 가상/실 CAN 인터페이스만 연다. 이 프로그램은 인터페이스 생성·bitrate 변경을 하지 않는다.

```sh
python -m security.ids.runtime --interface vcan0 --train-normal normal.jsonl --normal-manifest normal.manifest.json --secoc-key /path/to/key.bin --log live.jsonl --duration 30 --send-alerts
```

`--send-alerts` 없이 수신·로그만 수행한다. 송신은 기존 ICD 0x200 8바이트 BE이며 epoch 초의 하위32비트를 사용한다. 전체 경보 송신은 100ms 간격으로 제한한다. 로그에는 모든 탐지와 실제 ALERT_SENT를 구분한다. 실제 키와 원본 BMS payload를 로그에 복사하지 않는다. 경보 payload는 전송 근거로 기록한다. 경보 송신은 nonblocking이며 ENOBUFS/EAGAIN은 ALERT_TX_FAILED(errno, timestamp, data)로 기록하고 수신·탐지를 계속한다. 유형별 최대4개 FIFO가 경보 유형의 기아를 막고 전체100ms 시도 간격을 적용한다. 선택된 경보는 송신 실패에도 소비하고 재큐잉·재전송하지 않는다. READY/run-id와 부모 수명 모드를 함께 지원한다. ALERT_SENT는 소켓 수락이며 IVI 도달 증거는 아니다. 그 밖의 송신 오류와 수신 오류는 종료하고 소켓을 닫는다.

## 완료 범위

2026-10-03 후속: EXQ-11의 규칙 기본 임계는 SDD-ECU §3.9.5에 확정 기록됐고 합성 정상 오탐은 CHG-013에 보존했다. 위 "시험용 초기 정책"은 최초 구현 당시 설명이며 실물 보정이 완료됐다는 뜻은 아니다. 당시 도구/실행 근거는 [CHG-014](../../docs/aidlc/changes/CHG-014/aidlc-state.md)에 보존했다. 현행 session-v2 수집·IF 검증/자동 실험은 [session 실행 절차](../../docs/development/playbooks/session-campaign.md)를 따른다.

현재 학습·평가·오탐률/ROC·반복 절차는 [how_to_train.md](how_to_train.md)를 따른다. READY에는 `send_alerts`를 명시해 수신-only를 경보 모드로 오인하지 않는다. CHG-014~016의 vcan/분석 검증은 아래 원래 CHG-007 소프트웨어 범위를 보완하며 물리 합격을 대신하지 않는다.

과거 [CHG-007](../../docs/aidlc/changes/CHG-007/audit.md) 이후 vcan 및 실장비 결과는 [CHG-014](../../docs/aidlc/changes/CHG-014/aidlc-state.md)에 있다. 최신 통합 코드의 회귀·미검증 범위는 [CHG-019](../../docs/aidlc/changes/CHG-019/aidlc-state.md)를 따른다. 전체 M4/M5 인수, 물리 화면·CPU/RAM·새 세션 완료를 뜻하지 않는다.

실험 실행기가 지정하는 `--parent-pid`는 실제 부모 PID와 일치해야 하며, 이 모드에서는 duration 대신 부모 수명과 cleanup으로 종료한다. 독립 실행의 duration은 유지한다.

## N03 로컬 판단 근거: `ids-finding-v1`

기존 Rule/Model 결과에 선택적 `finding` 객체를 덧붙인다. 공격 유형/임계/IF7특징/0x200·인증 CAN 본문을 바꾸는 필드가 아니다. `RuleEvent`는 기존 `Event`의 하위 형식이며 Event의 기존 인수·경보 bytes를 유지한다. 판단 지점에서 값을 캡처하며 뒤의 로그/공격 정답으로 소급 작성하지 않는다.

| 필드 | 의미 |
|---|---|
| `source_id`, `sequence`, `capture_epoch` | 로컬 detector의 공개 UUID/증가 순번/수신 epoch. 사건·공격자·CAN 세션 ID가 아니다. epoch 변경에도 순번은 재사용하지 않는다 |
| `rule_id`, `rule_version`, `profile`, `origin` | 실제 reason, raw의 evidence-v3/session의 session-observation-v1 및 legacy-v1/session-v2 적용 범위. raw/raw-timer/local-secoc/session/model을 구분 |
| `observed`, `expected`, `unit` | 실제 측정·판단 기준·단위. 해당 규칙이 검사한 값만 기록하며 전체 payload/MAC/key를 복제하지 않는다 |
| `authentication` | Node A 로컬 검사에서 not_checked/failed/verified. IVI 수락/차단 증거가 아니다 |
| `model_identity_reference` | session-v2 모델이면 START.startup_identity.trained_model_sha256 참조. 이것 자체가 모델 해시/원격 attestation이 아니며 참조가 없는 실행은 미확인 |
| `severity`, `severity_policy` | 현재 null/not_calibrated. 새 위험 등급을 임의 부여하거나 기존 anomaly_score를 위험 등급으로 바꾸지 않는다 |

live는 실제 SocketCan에 붙인 detector의 ID를 READY.finding_source_id에 남긴다. START의 finding_source_id는 live에서 null, replay에서는 실제 replay detector ID다. 정상 프레임은 기존 NORMAL 기록을 유지하며 새 경보/근거 생성을 강제하지 않는다. 일반 Event API로 만든 외부 이벤트는 finding이 없을 수 있다.

- MESSAGE_MISSING은 raw 마지막 수신/경과 시간과 missing_s의 대조이며 인증된 유효 수신의 보장이 아니다. PERIOD_TOO_SHORT는 실제 raw 간격과 min_period_s를 기록한다.
- rate는 창 안의 프레임 **수**와 dominant ID/count를 기록한다. 실제 fps·물리 bus load로 바꾸지 않는다. BMS_STEP은 이전/현재 raw 값과 절대 차이를 구분하고 SOC 값의 percent와 차이의 percentage_points를 구분한다.
- legacy counter 규칙은 MAC 검사 이전이므로 not_checked다. session의 태그 확인 뒤 Replay/인증 충돌은 verified다. pair 기한 만료/후보·검증 예산 초과는 MAC 실패나 IVI 차단으로 표시하지 않는다.
- ModelEvaluation은 실제 anomaly와7특징을 기록한다. msg_rate의 실제 값은 frames_in_window, payload_change는 changed_bytes_per_pair다. IF_ANOMALY의 정규화 값과 anomaly를 구분하며 추가 추론/특징 기여도/네 공격 정답을 만들지 않는다.

기존 규칙의 출력 보완 범위다. 추가 freeze/plausibility·severity calibration·규칙/IF 결합 효과는 별도 과제다. [실제6제품/전체Python/변경 전후 근거](../../docs/aidlc/changes/CHG-029/rule-findings-20261112.json)를 따른다. 실제 Pi 성능·긴 연속 로그의 용량 보장은 이 결과와 다르다. 특히 기존 세대 수집의64MiB 파일/64KiB 행 상한과30/100시행 로그 크기를 검증하기 전 공식 campaign 준비 완료로 표시하지 않는다.


### 제한된 live 수신 순서 정리 — 2026-11-17

`OrderedSocketCan`은 같은 커널 타임스탬프를 보존한 채1ms/4096개 상한으로 미세한 전달 순서 역전을 정리한다. 동률은 수신 순서를 유지한다. timeout watermark는 아직 보관 중인 프레임을 추월하지 않는다. 이미 공개한 시각보다 늦게 도착한 과거 프레임·저장 용량 초과는 상세 이유와 epoch 오류로 남기며10ms 시계 매핑 검사/실제 유실/관찰 지연은 완화하지 않는다. CLOCK 로그에 예산·END에 정리 횟수를 기록한다. Pi 운용값/IF 효과는 로컬 vcan 통과와 구분한다. `security/tests/test_receive_order.py`의 경계/음성 회귀를 따른다.
