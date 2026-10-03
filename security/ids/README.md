# Node A CAN IDS 실행

`runtime_detector.py`는 입력 시각을 주입받는 탐지 엔진, `runtime.py`는 JSONL 재생/SocketCAN 입출력이다. 기존 오프라인 `run_eval.py`와 분리되며 기존 7개 특징·IF 구현을 재사용한다.

## 입력과 모드

저장소 루트에서 `python -m security.ids.runtime --help`를 실행한다. 기본 모드를 묵시적으로 선택하지 않는다. `--train-normal 정상.jsonl`은 별도 정상 데이터로 IF를 학습해 사용하고, `--rules-only`는 개발·ablation용이다. 모델 pickle을 불러오지 않는다. 정상 데이터는 최소 두 개의 완료된 1초 창이 필요하며 학습 데이터의 정상성은 공급자가 확인한다.

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

| 로컬 사유 | 0x200 AttackType |
|---|---|
| UNKNOWN_ID / DLC / FRAME_FORMAT | 1 Fuzzy |
| COUNTER_REUSE / BACKWARD / WINDOW | 2 Replay 의심 |
| BMS_RANGE / BMS_STEP / FAILSAFE_RANGE / MAC_FAIL | 3 Spoofing 의심 |
| FRAME_RATE / PERIOD_TOO_SHORT | 4 Flooding 의심 |
| MESSAGE_MISSING / AUTH_TIMEOUT / AUTH_ORPHAN / SECOC_FAILURE_BURST / IF_ANOMALY | 로컬 진단만; 원인 미확정 |

유형은 규칙에 따른 의심 분류이며 실제 공격 원인 확정이 아니다. 미분류 사건을 AttackType=0 경보로 전송하지 않으므로 IVI 경고를 잘못 해제하지 않는다. 자체 0x200 입력은 탐지 창에서 제외한다. 경보 점수는 규칙 발생 시 1.00, IF 진단은 기존 IF wire_score 정규화 값을 기록하며 확률이 아니다.

## Linux SocketCAN (장비 없이도 vcan 사용 가능)

이미 준비된 가상/실 CAN 인터페이스만 연다. 이 프로그램은 인터페이스 생성·bitrate 변경을 하지 않는다.

```sh
python -m security.ids.runtime --interface vcan0 --train-normal normal.jsonl --normal-manifest normal.manifest.json --secoc-key /path/to/key.bin --log live.jsonl --duration 30 --send-alerts
```

`--send-alerts` 없이 수신·로그만 수행한다. 송신은 기존 ICD 0x200 8바이트 BE이며 epoch 초의 하위32비트를 사용한다. 전체 경보 송신은 100ms 간격으로 제한한다. 로그에는 모든 탐지와 실제 ALERT_SENT를 구분한다. 키/페이로드를 로그에 복사하지 않는다. 송신/수신 오류는 종료하고 소켓을 닫는다.

## 완료 범위

현재 학습·평가·오탐률/ROC·반복 절차는 [how_to_train.md](how_to_train.md)를 따른다. READY에는 `send_alerts`를 명시해 수신-only를 경보 모드로 오인하지 않는다. CHG-014~016의 vcan/분석 검증은 아래 원래 CHG-007 소프트웨어 범위를 보완하며 물리 합격을 대신하지 않는다.

[CHG-007](../../docs/aidlc/changes/CHG-007/audit.md)의 소프트웨어 시험 범위만 완료로 판단한다. 물리 CAN·vcan 실제 송수신, Node B 화면까지의 통합, 탐지율/오탐률·CPU/RAM 목표 달성, 인증 이벤트 채널, 새 세션은 후속 검증이다. 이번 작업은 발표의 1차 IDS 소프트웨어 구현이며 ECU M4/M5 전체 완료 선언이 아니다.
