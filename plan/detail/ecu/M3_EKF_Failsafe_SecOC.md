# ECU M3 — EKF, SOH, Fail-safe, Watchdog, SecOC

> **2026-09-09 보안 방식 선별 반영:** 기존 단계·과제에 [하단 추가 수행·인수 조건](#security-adoption)을 함께 적용한다. 구현·시험 완료 기록은 아니다.

> **예시 상태**: 코드·명령은 별도 검증 표시가 없으면 작성 골격·예정 절차다. 실행 전 생성할 파일·의존성·플랫폼을 확인한다. [공동 규약](../common/00_협업_규약.md)의 문서·예시 사용 규칙을 따른다.

> 상위 계획: [ECU.md](../../ECU.md) · 공동 절차: [00_협업_규약](../common/00_협업_규약.md) · 인계: [01_연계_의존성](../common/01_연계_의존성.md)
> 원본: `_archive/ECU.md` M3, `_archive/ECU_최종_실행계획서.md` §7

---


<a id="security-integration"></a>
## 현행 과제에 병합한 보안 수행·인수 조건 — 입력·보안 설정의 Q2 인계

이 절은 2026-09-09 보안 상세 계획을 기존 단계에 반영한 실행 조건이다. 초기 보안 보강 절과 함께 적용하며 제품 실행 완료 기록은 아니다. 상세 규칙은 [메시지·상태 규약](../../../docs/development/security/인증이벤트_메시지_상태규약.md)과 [송신·큐·실패 정책](../../../docs/development/security/인증이벤트_메시지_상태규약.md#planning-final)을 참조한다.

**선행 조건:** ECU-SEC-01의 적용 ICD/profile과 양측 보안 설정을 먼저 확인한다. 일반 실행의 명시적 --secoc on과 현재 main의 기본 OFF를 구분한다.

**수행:** N01/N02에 따라 시작·재시작·키 오류 및 C0 우회를 인계한다. profile/source_mode·입력/설정 hash·seed·단위와 실제 sender 중단/재개 경계를 M4에 제공한다. 진단 epoch 변경을 CAN counter 초기화로 취급하지 않는다.

**실패 대응·인계:** Q2가 사용할 결과 의미·적용 버전은 IVI와 대조하되 기존 pending·commit·안전 루프를 보존한다. 설정 오류·센서 결함·공격·송신 중단을 다른 사건으로 기록한다.

**완료 확인:**

- [ ] 양측 설정·입력 계보·실패/복구 제공물을 M4와 IVI M3에 인계했다.
- [ ] 기존 공식 시험 결과와 추가 보조 시나리오의 실제 증거·미검증 사유를 구분했다.


## 1. 목적과 범위

**추가 승인 방향:** 인증 세션을 CAN으로 교환해 재부팅 후 자동 복구한다. ECU의 세션 메시지 수신·응답과 세션키 수명 관리가 새 과제다. [CAN 세션 인증 설계안](../../../docs/development/security/CAN_세션인증_설계안.md)의 ID·키 파생·counter 소진·복구 시간은 아직 검토 대기다. 아래 기존 고정키·래핑 예시는 현재 계약 기준으로 구분하며, 새 프로토콜 완료 증거로 사용하지 않는다. 구체적 계약 승인 후 Python·ECU·IVI 교차 벡터와 재부팅 시험을 함께 갱신한다.

EKF SOC 추정기와 SOH 추정기를 확보하고, Fail-safe 4상태 FSM의 모든 전이를 Branch Coverage 100%로 검증한다. Watchdog을 붙이고, SecOC HMAC-SHA256을 Python·C++ 양쪽에서 동일 결과로 동작시킨다.

| 항목 | 값 |
|---|---|
| 연결 요구사항 | FR-BMS-001~008, FR-SEC-001~007, FR-BSW-006~007<br>**NFR-SEC-001** (검증 실패 폐기율 100%), **NFR-SEC-002** (Replay 차단율 100%), **NFR-REL-001** (감시 1s/타임아웃 3s), **NFR-REL-002** (CAN 수신 스레드 복구; BMS 복구와 별도, ECU M2·공동 매핑 참조) |
| 연결 시험 | TC-BMS-001~004, TC-BSW-006~007, TC-SEC-001~004 |
| 산출물 | `ekf_soc_estimator`, `soh_estimator`, `failsafe_sm`, `watchdog_manager`, `secoc_module`(C++/Python), `/etc/secoc/key.bin` |
| 태그 | `v0.3.0` |
| **IVI 인계** | `secoc_module.cpp` 완성 → IVI가 `secoc_verifier` 구현 시작. 4주차에 통보 ([01_연계_의존성](../common/01_연계_의존성.md)) |

### 주차별 작업

| 주차 | ECU 작업 | IVI 연계 |
|---|---|---|
| 1주차 | EKF 구현·튜닝, `test_ekf_soc` | — |
| 2주차 | 프로파일 재생 정확도 검증, SOH, ADS1115 연결 | — |
| 3주차 | Fail-safe FSM, TC-BMS-004 전 케이스, Watchdog | `0x101` 전이 이벤트 포맷 공유 |
| 4주차 | SecOC Python → C++, 교차 벡터 | **SecOC 테스트 벡터 인계** |

---

## 2. 선행조건과 현재 구현 상태

**선행조건**: [M2](M2_CAN_CDD_Publisher.md) 완료 — CAN 송수신, 센서 입력, `0x100` 인코딩.

**구현 상태 (2026-09-05 조사, EKF 항목은 2026-09-08 갱신)**

| 대상 | 상태 | 실제 내용 |
|---|---|---|
| `ekf_soc_estimator.h/.cpp` | **정정 적용·실행 미검증** | SOC-2=A로 50Ah·3차 OCV·SOC 의존 미분·내부 팩/셀 변환 적용. C++17 환경에서 대응 시험 실행 필요 |
| `soh_estimator.h/.cpp` | **구현됨(정정 필요)** | `recordDischarge()`, `recordCycle()`, `soh()`. 초기 용량 **2.6 Ah → 50.0 Ah**로 EKF와 맞춘다 (3.4) |
| `failsafe_sm.h/.cpp` | **구현됨** | `State` 4종 + `Reason` 7종 상수. `evaluate()` bool 반환, 콜백으로 `FailSafeEvent` 발행 |
| `watchdog_manager.h/.cpp` | **구현됨(부분)** | 1000ms 주기 / 3000ms 타임아웃, `timeoutCount()` 누적. **재시작 3회 후 Fail-safe 전이 로직은 없음** |
| `security/secoc_module.py` | **구현됨** | `SecOcModule.sign()/verify()`, 카운터 윈도우 100 |
| `adaptive_ecu/src/bsw/secoc_module.cpp` | **구현됨** | Python과 동일 규칙. `CRYPTO_memcmp` 상수시간 비교 |
| ADS1115 하드웨어 모드 | **제품 연결 구현·장비 시험 대기** | 2026-10-03 [CHG-011](../../../docs/aidlc/changes/CHG-011/aidlc-state.md): 별도 취득 worker·순번 기반 새 측정·3회 확인·오류 시 송신 보류를 `main`에 연결. 단위 시험 통과, RPi 실측은 미완료. **Fail-safe 데모의 주 경로** |
| `Mode::POTENTIOMETER` | **제거됨(2026-10-03)** | I-5=B 이관 완료: setter 시험을 ADS1115 모드·모드 이름 검증 시험으로 옮기고 enum·CLI·setter 3종을 삭제. [CHG-011](../../../docs/aidlc/changes/CHG-011/aidlc-state.md) |

**현재 시험 목록과 공식 TC 대응**

| CTest | 포함 TEST | 대응 TC | 상태 |
|---|---|---|---|
| `test_ekf_soc` | `MaintainsSocWhenVoltageMatchesModel`, `TracksHigherVoltageUpward`, `DischargeCurrentReducesPrediction` | TC-BMS-001/002에 **미대응** | 정성 시험만 있음 |
| `test_soh_estimator` | `StartsAtFullHealth`, `UsesMeasuredCapacityRatio`, `ClampsCapacityAboveInitial` | TC-BMS-003 부분 | — |
| `test_failsafe_sm` | `CoversIcdTransitions`, `WarningCanEscalateDirectlyToShutdownOnHighTemperature` | TC-BMS-004 | Branch Coverage 미측정 |
| `test_watchdog_manager` | `CallsTimeoutCallback`, `KickPreventsTimeout` | TC-BSW-006 | TC-BSW-007 **미구현** |
| `test_secoc` | `SignsKnownCounterZeroVector`, `VerifiesAndRejectsTamper`, `RejectsReplayCounter`, `CounterIncrementsAcrossMessages`, `AcceptsCounterWrap` | TC-SEC-001~004 | 교차 벡터 확인 필요 |

> **남은 작업의 실체**: 모듈은 대부분 있지만 두 종류의 격차가 있다.
> 1. **동작 결함** — EKF 스케일·모델(3.1), Watchdog 복구 경로(3.6), ADS1115 미구현(3.11)
> 2. **검증 격차** — 공식 TC의 정량 기준(TC-BMS-001 오차 ≤0.5%, TC-BMS-002 RMSE 비교, TC-BMS-004 Branch 100%, TC-BSW-007)이 자동 검증되지 않는다
>
> 1번을 먼저 고쳐야 2번을 측정할 수 있다. EKF가 SOC를 고착시키는 상태에서는 어떤 정량 시험도 의미가 없다.

### 통합 시 해소한 충돌

아래 표는 수정 전 조사 이력이다. EKF 제품의 최신 상태는 위 구현 상태 표와 3.1의 SOC-2=A 기록을 따른다.

| 항목 | 세대A 계획 | 실제 구현 | 조치 |
|---|---|---|---|
| `update()` 인자 순서 | `update(voltage, current, dt)` | **`update(dt_s, current_a, voltage_v)`** | 실제 기준. 계획 예제 그대로 쓰면 값이 뒤바뀐다 |
| 전류 부호 | `soc - (dt*current)/(cap*3600)` | **`soc + (current_a*dt)/(cap*3600)`** | 실제 기준. ICD의 "양수=충전"과 일치 |
| OCV 모델 | 3차 다항식 a3=-1.031, a2=3.685, a1=-0.858, a0=2.374 | 선형 `3.0 + 1.2*soc` | **양쪽 다 폐기.** 구 3차는 단조성 위반, 선형은 근사에 그침 → SDD v1.6의 재피팅 계수 채택 (3.1) |
| 용량 | 50.0 Ah | 2.6 Ah (셀 기준) | **50.0 Ah** (팩) — SDD §3.7.2·TEST_PLAN TC-BMS-001과 일치 (3.1) |
| 전압 스케일 | 명시 없음 | 팩 전압을 단셀 모델에 직접 입력 | **팩 → 단셀 변환 추가** (`/10`). 미변환이 SOC 고착의 직접 원인 (3.1) |
| 수동 리셋 진입 상태 | 세대A: CRITICAL에서 리셋 | **SHUTDOWN에서만 허용** (`manualReset()`이 그 외 상태에서 `false`) | 실제 기준. 세대B TC-BMS-004-e와 일치 |
| 카운터 윈도우 검사 | `received <= last \|\| received > last+100` | **`delta = recv - last` (unsigned), `delta==0 \|\| delta>100` 거부** | 실제 기준. 세대A식은 `0xFFFFFFFF` 래핑에서 오탐 |

---

## 3. 수행 절차

### 3.1 EKF SOC 추정기 — 스케일·모델 정정

> **수정 전 결함 이력:** 아래 표의 3차 모델·50Ah·팩/셀 변환은 SOC-2=A로 제품에 적용했다. 현재 과제는 정정 소스의 실제 실행 검증이다. 적용 사실과 시험 통과를 구분한다.

**정정할 3가지**

| # | 현재 구현 | 정정 후 | 근거 |
|---|---|---|---|
| 1 | `main.cpp`가 **팩 전압 42V를 그대로** EKF에 전달 | `update(dt_s, current_a, voltage_pack_v)`에는 팩 V 전달, §3.1의 내부 관측 변환에서만 직렬수로 나눔 | SDD §3.7.2 — OCV 모델은 **단셀 기준** |
| 2 | `capacity_ah = 2.6f` (셀 용량) | **`50.0f`** (팩 용량) | SDD §3.7.2, TEST_PLAN TC-BMS-001 입력 조건 |
| 3 | OCV 선형 `3.0 + 1.2*soc`, 야코비안 상수 `1.2` | **3차 다항식**, 야코비안은 SOC 함수 | SDD §3.7.2 확정 계수 |

**왜 고착되는가**: 42V를 단셀 모델(3.0~4.2V)에 넣으면 innovation이 `42 − 4.2 = 37.8V`가 되어 칼만 게인이 SOC를 즉시 상한으로 밀어붙인다. 이는 입력 단위 불일치의 설명이며 현재 실행 결과가 아니다. SOC 저하 전이 재현이 어려워질 수 있으므로 단위 변환과 경계 시험을 먼저 수행한다.

**정정 후 헤더**

```cpp
class EkfSocEstimator {
public:
    static constexpr int   kCellsInSeries = 10;      // 팩 전압 = 단셀 OCV x 10
    // OCV(SOC) = a3*SOC^3 + a2*SOC^2 + a1*SOC + a0   [단셀 V]  (SDD-ECU §3.7.2)
    static constexpr float kA3 =  2.1667f;
    static constexpr float kA2 = -3.7321f;
    static constexpr float kA1 =  2.7655f;
    static constexpr float kA0 =  3.0000f;

    struct Config {
        float initial_soc = 0.75f;          // SOC-1=B 일반 기본값; S-21 시험은 0.80 명시
        float capacity_ah = 50.0f;           // 팩 용량 (was 2.6f)
        float process_noise = 1.0e-5f;       // Q
        float measurement_noise = 0.02f;     // R: SOC-1=B, SDD 초기 설정과 통일
        float initial_covariance = 0.01f;    // P0: 실장비 최적값 확정 아님
    };

    EkfSocEstimator();
    explicit EkfSocEstimator(const Config& config);

    /// voltage_pack_v: 팩 전압(V). 내부에서 단셀로 변환한다.
    float update(float dt_s, float current_a, float voltage_pack_v);
    float soc() const;

private:
    float ocvFromSoc(float soc) const;   // 3차 다항식
    float dOcvDSoc(float soc) const;     // 야코비안 — SOC 인자를 받는다 (was 상수)
    ...
};
```

**정정 후 구현**

2026-09-08 SOC-2=A 반영: 아래 목표의 3차 모델·내부 팩/단셀 변환·50Ah를 실제 추정기 헤더와 구현에 적용하고 대응 시험을 수정했다. C++ 실행은 로컬 GCC 6.3의 `std::clamp` 미지원·CMake 부재로 미검증이다. 아래 예제와 소스 존재가 시험 통과를 뜻하지 않는다. 증거와 후속 명령은 [SOC 실험 결과 §7](../../../docs/development/experiments/SOC_합성실험_결과.md)을 따른다.

```cpp
float EkfSocEstimator::ocvFromSoc(float soc) const {
    return ((kA3 * soc + kA2) * soc + kA1) * soc + kA0;   // Horner
}

float EkfSocEstimator::dOcvDSoc(float soc) const {
    return (3.0f * kA3 * soc + 2.0f * kA2) * soc + kA1;
}

float EkfSocEstimator::update(float dt_s, float current_a, float voltage_pack_v) {
    // Predict
    const float predicted_soc =
        std::clamp(soc_ + (current_a * dt_s) / (capacity_ah_ * 3600.0f), 0.0f, 1.0f);
    const float predicted_covariance = covariance_ + process_noise_;

    // Update — 팩 전압을 단셀로 변환해 관측값으로 쓴다
    const float cell_v = voltage_pack_v / static_cast<float>(kCellsInSeries);
    const float h = dOcvDSoc(predicted_soc);
    const float innovation = cell_v - ocvFromSoc(predicted_soc);
    const float innovation_covariance = (h * predicted_covariance * h) + measurement_noise_;
    const float kalman_gain = predicted_covariance * h / innovation_covariance;

    soc_ = std::clamp(predicted_soc + kalman_gain * innovation, 0.0f, 1.0f);
    covariance_ = (1.0f - kalman_gain * h) * predicted_covariance;
    return soc_;
}
```

- [ ] **야코비안이 상수를 반환하지 않게 한다.** 3차 모델에서 기울기는 SOC에 따라 변한다(0%에서 +2.77, 60% 부근에서 +0.63, 100%에서 +1.80). 상수로 두면 저·고 SOC 구간에서 보정이 과도하거나 부족해진다
- [ ] 변환을 `update()` 안에 두면 호출부가 팩 전압을 그대로 넘겨도 안전하다. 이 문서의 헤더·구현 예시처럼 호출부에서는 나누지 않는다 — **양쪽에서 나누면 4.2V가 0.42V가 된다**

**곡선 검증값** (SDD §3.7.2 표와 동일)

| SOC | 단셀 OCV | 팩 전압 | dOCV/dSOC |
|---:|---:|---:|---:|
| 0% | 3.000V | 30.00V | +2.766 |
| 5% | 3.129V | 31.29V | +2.409 |
| 20% | 3.421V | 34.21V | +1.533 |
| 60% | 3.784V | 37.84V | +0.627 |
| 100% | 4.200V | 42.00V | +1.801 |

기울기 최솟값이 **+0.6227**(SOC 57%)로 전 구간 양수다. Fail-safe 임계인 5%·20%도 단조 구간 안에 있다. 이 성질만으로 EKF 정확도·수렴·Fail-safe 시험 통과가 입증되는 것은 아니다.

**단위 통일 규칙**

- [ ] 전류는 A, 시간은 초, 용량은 Ah, 전압은 **팩 V**(내부에서 단셀 변환)
- [ ] `main.cpp`는 `update(0.1f, current_a, voltage_v)`로 100ms 주기를 넘긴다
- [ ] SOC 반환은 0.0~1.0. `main.cpp`가 `* 100.0f`로 퍼센트 변환한다

**튜닝 기준**

| 증상 | 조치 |
|---|---|
| 전압 관측에 과민 반응 | `measurement_noise`(R) 증가 (0.02 → 0.05) |
| SOC 수렴이 느림 | R 감소 (0.02 → 0.005) |
| 전류 적분 누적 오차 | `process_noise`(Q) 증가 (1e-5 → 1e-4) |
| 추정값이 불안정 | Q 감소 (1e-5 → 1e-6) |

- [ ] 최종 Q/R/P0 값은 `docs/SDD-ECU.md`에 기록한다.

**정정 후 회귀 확인** — 기존 시험 3개의 기대값이 바뀐다.

```bash
ctest --test-dir adaptive_ecu/build -R test_ekf_soc --output-on-failure
```

| 기존 시험 | 영향 |
|---|---|
| `MaintainsSocWhenVoltageMatchesModel` | 입력 3.9V는 **단셀 값**이었다. 팩 기준 39.0V로 바꾸고, 3차 모델에서 SOC 75%에 해당하는 전압으로 기대값 재계산 |
| `TracksHigherVoltageUpward` | 4.08V → 팩 40.8V. 상승 방향만 보므로 부등호는 유지 |
| `DischargeCurrentReducesPrediction` | 용량 2.6→50Ah로 변경돼 감소폭이 작아진다. `measurement_noise=100.0f`로 관측을 무력화한 시험이라 방향은 유지되나 여유를 확인한다 |

**진단 — 어디서 발산하는지 확인**

```bash
./adaptive_ecu/build/adaptive_ecu --sensor-mode profile_csv --profile adaptive_ecu/data/battery_profile_1h.csv 2>&1 | tee ekf_trace.csv
# 로그 포맷 목표: timestep,true_soc,ekf_soc,P,K,innovation
```

> 현재 `main.cpp`에는 EKF trace 로그 옵션이 없다. 튜닝이 필요하면 로그 출력을 먼저 추가한다(주기 루프 밖에서 버퍼링해 TC-BMS-007 지터를 건드리지 않는다).


### 3.2 OCV 계수를 재산출할 때의 제약

§3.1의 계수는 `docs/SDD-ECU.md` §3.7.2에서 확정한 값이다. 다른 셀 데이터로 바꿔야 할 일이 생기면 **아래 두 조건을 반드시 검증한 뒤에** 교체한다.

| 조건 | 왜 필요한가 | 확인 방법 |
|---|---|---|
| **단조 증가** — 전 구간 `dOCV/dSOC > 0` | EKF는 OCV 곡선을 역산해 SOC를 추정한다. 기울기가 음수인 구간에서는 칼만 보정 방향이 **반대로 뒤집혀** SOC가 발산한다 | SOC 0~1을 촘촘히 훑어 기울기 최솟값이 양수인지 |
| **끝점 정합** — `OCV(0)×10 = 30.0V`, `OCV(1)×10 = 42.0V` | §3.7.3의 ADS1115 매핑 범위와 맞아야 가변저항 전 구간이 SOC 0~100%에 대응한다 | 양 끝점 값 직접 계산 |

> 구 계수는 단조성·끝점 정합 문제가 있어 현재 가상 모델로 교체했다. 특정 SOC 고착값이나 시연 불가능 여부는 당시 실행 조건과 로그 없이 확정하지 않는다. 현재 모델 역시 실제 셀 정확도·수렴을 별도 검증해야 한다.

**재산출 절차** (표준 라이브러리만 사용, numpy 불필요)

```python
# 끝점 고정 3차 최소자승: OCV(0)=CELL_MIN, OCV(1)=CELL_MAX 제약
CELL_MIN, CELL_MAX = 3.0, 4.2          # 팩 30~42V / 10직렬

def fit_constrained(soc, ocv):
    suu = svv = suv = sur = svr = 0.0
    for s, y in zip(soc, ocv):
        u = s**3 - s
        v = s**2 - s
        r = y - (CELL_MAX - CELL_MIN) * s - CELL_MIN
        suu += u*u; svv += v*v; suv += u*v; sur += u*r; svr += v*r
    det = suu*svv - suv*suv
    a3 = (sur*svv - svr*suv) / det
    a2 = (svr*suu - sur*suv) / det
    a1 = (CELL_MAX - CELL_MIN) - a2 - a3
    return a3, a2, a1, CELL_MIN

def verify(a3, a2, a1, a0):
    f  = lambda s: ((a3*s + a2)*s + a1)*s + a0
    df = lambda s: (3*a3*s + 2*a2)*s + a1
    grid = [i/5000 for i in range(5001)]
    return {
        "ocv_0":  f(0.0), "ocv_1": f(1.0),
        "min_slope": min(df(s) for s in grid),        # > 0 이어야 한다
        "monotonic": min(df(s) for s in grid) > 0,
    }
```

- [ ] `verify()`의 `monotonic`이 True인지 확인한다
- [ ] 끝점이 3.000V / 4.200V인지 확인한다 (반올림 후에도)
- [ ] 교체하면 `docs/SDD-ECU.md` §3.7.2의 계수·검증표를 같은 변경 단위로 갱신한다
- [ ] `docs/ADR.md`에 모델 변경 근거를 남긴다


### 3.3 TC-BMS-001 / TC-BMS-002 시험 추가 (미구현 과제)

현재 `test_ekf_soc.cpp`는 정성 시험 3개뿐이다. 공식 기준을 검증하려면 아래를 추가한다. **입력 조건은 `docs/TEST_PLAN.md`를 따른다** — 임의 값으로 바꾸지 않는다.

```cpp
// TC-BMS-001: 정전류 방전 1,000 step(100초) 후 이론 SOC와 오차 <=0.5%
// TEST_PLAN 입력: I=-2.0A, dt=0.1s, Q=50Ah, SOC0=80%, 1,000 타임스텝
// 기대: 79.8889% (= 0.80 - 2.0*0.1*1000/(50*3600))
TEST(EkfSocEstimator, TC_BMS_001_ConstantDischarge) {
    EkfSocEstimator::Config cfg;
    cfg.initial_soc = 0.80f;
    cfg.capacity_ah = 50.0f;          // 팩 용량
    EkfSocEstimator ekf(cfg);

    const float current = -2.0f;      // 2A 방전
    const float dt = 0.1f;            // 100ms
    float true_soc = 0.80f;

    for (int i = 0; i < 1000; ++i) {
        true_soc += (current * dt) / (50.0f * 3600.0f);
        // 모델과 일치하는 이상적 팩 전압 (단셀 OCV x 10)
        const float pack_v = ekfOcvForTest(true_soc) * 10.0f;
        ekf.update(dt, current, pack_v);
    }

    EXPECT_NEAR(true_soc, 0.798889f, 1e-5f);      // 이론값 자체 확인
    EXPECT_NEAR(ekf.soc(), true_soc, 0.005f);     // <=0.5%
}
```

> `ekfOcvForTest()`는 §3.1의 3차 다항식을 시험 쪽에서 재현한 헬퍼다. 구현과 같은 계수를 쓰되, 시험이 구현 내부 함수에 의존하지 않도록 별도로 둔다. 계수를 바꾸면 양쪽을 함께 고친다.

```cpp
// TC-BMS-002: EKF RMSE < 쿨롱 카운팅 RMSE
// TEST_PLAN 입력: PROFILE_CSV 모드, 1시간(36,000 타임스텝) 프로파일
TEST(EkfSocEstimator, TC_BMS_002_EkfBeatsCoulombCounting) {
    // data/battery_profile_1h.csv 를 로드해 두 추정기를 같은 입력으로 돌린다.
    // 쿨롱 카운팅은 전압 보정 없이 전류만 적분한다.
    // 독립 기준 SOC와 고정된 평가 입력을 사용한다. 결과를 유리하게 만들기 위해 잡음을 바꾸지 않는다.
    EXPECT_LT(rmse_ekf, rmse_coulomb);
}
```

`ECU_SOURCE_DIR` 컴파일 정의가 이미 각 시험에 주입되므로 CSV 경로는 그것을 기준으로 잡는다.

- [ ] **`battery_profile_1h.csv`가 필요하다.** 현재 `battery_profile.csv`는 **5행**뿐이라 36,000 타임스텝을 채울 수 없다. 출처·전처리·기준 SOC 확보 절차는 3.12
- [ ] 이론값 79.8889%가 TEST_PLAN 기대값 79.89%와 일치하는지 시험 안에서 함께 확인한다


### 3.4 SOH 추정기

```cpp
class SohEstimator {
public:
    explicit SohEstimator(float initial_capacity_ah = 50.0f);   // 팩 용량 (was 2.6f)
    void recordDischarge(float discharged_ah);
    void recordCycle(float measured_capacity_ah);
    float soh() const;                    // 0.0~1.0
    float initialCapacityAh() const;
    float estimatedCapacityAh() const;
};
```

SOH = 추정 용량 / 초기 용량. `recordCycle()`로 실측 용량이 들어오면 비율을 갱신하고, 초기 용량을 넘는 값은 clamp한다. `main.cpp`는 `soh() * 100.0f`로 퍼센트를 만들어 `0x100` byte 1에 싣는다.

- [ ] **초기 용량 기본값을 `50.0f`로 바꾼다.** EKF의 `capacity_ah`와 같은 값이어야 한다. 한쪽만 고치면 SOC와 SOH가 서로 다른 배터리를 가리킨다
- [ ] S-4=A와 TC-BMS-003에 따라 `Q_initial=50Ah, Q_current=45Ah → SOH 90.0%`를 검증한다. `recordCycle()`에 가상 추정 용량을 공급하고 누적 방전 기록만으로 SOH가 감소하지 않는지도 확인한다. 실제 용량 측정이나 수명 추정 실증으로 표시하지 않는다.

### 3.5 Fail-safe 상태 머신

실제 전이 규칙이다. **ICD §1.3의 Reason 코드와 1:1로 맞물려 있으므로 임의로 바꾸지 않는다.**

```cpp
enum class State : uint8_t { NORMAL = 0, WARNING = 1, CRITICAL = 2, SHUTDOWN = 3 };

enum Reason : uint8_t {
    REASON_NONE               = 0x00,
    REASON_LOW_SOC_WARNING    = 0x01,
    REASON_LOW_SOC_CRITICAL   = 0x02,
    REASON_HIGH_TEMP_WARNING  = 0x03,
    REASON_HIGH_TEMP_SHUTDOWN = 0x04,
    REASON_RECOVERED          = 0x05,
    REASON_MANUAL_RESET       = 0x06
};
```

평가 순서 (`evaluate()`가 위에서부터 검사한다):

1. `temp > 60`
   - 현재 WARNING 또는 CRITICAL → **SHUTDOWN** (`0x04`)
   - 현재 NORMAL → **WARNING** (`0x03`)
   - 그 외(SHUTDOWN) → 전이 없음
2. `soc < 5` 이고 현재 WARNING → **CRITICAL** (`0x02`)
3. 현재 NORMAL
   - `soc < 20` → **WARNING** (`0x01`)
   - `temp > 55` → **WARNING** (`0x03`)
4. 현재 WARNING 이고 `soc >= 20` 이고 `temp <= 55` → **NORMAL** (`0x05`)
5. `manualReset()` — **SHUTDOWN 상태에서만** NORMAL 복귀 (`0x06`). 그 외에는 `false` 반환

> 주의할 두 가지: ① NORMAL에서 온도 60°C 초과는 SHUTDOWN이 아니라 WARNING을 거친다. ② **CRITICAL에서 NORMAL로 복귀하는 경로가 없다** — SOC가 회복돼도 CRITICAL에 머문다. 이것이 의도인지 `docs/SRS.md`와 대조하고, 의도가 아니면 시험과 함께 고친다.

**TC-BMS-004 케이스 표** (세대B판 + 실제 구현으로 검증)

| TC | 입력 | 시작 상태 | 기대 전이 | Reason |
|---|---|---|---|---|
| TC-BMS-004-a | SOC=19%, Temp=30 | NORMAL | → WARNING | `0x01` |
| TC-BMS-004-b | SOC=4%, Temp=30 | WARNING | → CRITICAL | `0x02` |
| TC-BMS-004-c | SOC=10%, Temp=61 | CRITICAL | → SHUTDOWN | `0x04` |
| TC-BMS-004-d | SOC=25%, Temp=30 | WARNING | → NORMAL | `0x05` |
| TC-BMS-004-e | manual reset | SHUTDOWN | → NORMAL | `0x06` |
| TC-BMS-004-f | SOC=60%, Temp=30 | NORMAL | 전이 없음 | — |
| TC-BMS-004-g | SOC=60%, Temp=56 | NORMAL | → WARNING | `0x03` |

**Branch Coverage 측정** — `ENABLE_COVERAGE` 옵션이 이미 CMake에 있다.

```bash
cmake -S adaptive_ecu -B adaptive_ecu/build-cov \
      -DECU_BUILD_TESTS=ON -DENABLE_COVERAGE=ON -DCMAKE_BUILD_TYPE=Debug
cmake --build adaptive_ecu/build-cov
ctest --test-dir adaptive_ecu/build-cov -R test_failsafe_sm --output-on-failure

lcov --capture --directory adaptive_ecu/build-cov --output-file cov.info
lcov --extract cov.info '*/failsafe_sm.cpp' --output-file fs.info
genhtml fs.info --output-directory cov_report
# cov_report/index.html 에서 Branch Coverage 100% 확인
```

Coverage가 100% 미만이면 `genhtml` 출력에서 미커버 branch 라인을 찾아 해당 전이 케이스를 추가한다.

### 3.6 Watchdog Manager

```cpp
WatchdogManager(int check_period_ms = 1000, int timeout_ms = 3000);
void start(TimeoutCallback callback);   // callback(uint32_t timeout_count)
void kick();
std::uint32_t timeoutCount() const;
```

감시 루프는 `check_period_`마다 깨어나 마지막 `kick()` 이후 경과가 `timeout_` 이상이면 카운트를 올리고 콜백을 호출한 뒤 **기준 시각을 재설정**한다(연속 폭주 방지). `main.cpp`는 주기 루프 맨 앞에서 `watchdog.kick()`을 부른다.

**TC-BSW-007 (미구현 과제)** — 정본은 TEST_PLAN의 본문과 SDD-ECU §3.4.3이다. NORMAL에서 재시작 시도가 3회 연속 실패하면 WARNING으로 전이하고 ICD 사유 `0x07`의 `0x101`을 전송한다. 누적 timeout 횟수를 재시작 실패 횟수로 대신하지 않는다.

1. Watchdog는 timeout을 감지하고 태스크 소유자인 main에 알린다. main이 정지 요청·자원 회수·재시작·정상 heartbeat 확인을 담당한다. timeout 콜백에서 감시 스레드 자신을 join하지 않는다.
2. 성공한 재시작은 연속 실패 집계를 0으로 초기화한다. 재시작 실패는 시도별로 한 번 집계하고 3번째 실패에서 전이를 요청한다. 4번째 실패를 기다리지 않는다.
3. TC-BSW-006은 감지뿐 아니라 재시작·정상 heartbeat 복귀까지 확인한다. TC-BSW-007/TC-BMS-004-h는 실패 1·2회에는 최종 전이가 없고 3회에 reason=0x07이 발생하는지 검증한다.
4. main의 루프 자체가 멈추면 콜백만으로 복구 가능한지 별도로 검토한다. 사용자 I-3=A에 따라 main 소유 BMS 작업을 복구 대상으로 확정한다. 중단 가능한 경계·heartbeat 성공 판정·종료 대기 상한을 명세하며 스레드 강제 종료나 회수 전 중복 실행을 사용하지 않는다.

**I-3=A 인수 보강:** BMS 작업의 생존 신호는 main의 루프가 도는지만 확인하는 것으로 대신하지 않는다. BMS 작업의 실제 처리 완료 지점을 감시하고 main은 감시·회수·재시작을 수행한다. 성공 heartbeat 전에는 성공으로 집계하지 않는다. 재시작 중 CAN 세션·카운터와 마지막 유효 BMS/Fail-safe 상태의 소유자를 명시하고 상태를 임의 초기화하지 않는다. 회수되지 않은 작업 위에 새 작업을 추가하지 않는다. 프로세스 전체 장애는 systemd 기동 검증과 별개 시험으로 구분한다.

**Q-5~6=A 수행 과제:** main 또는 작업 외부 소유 저장소에 EKF 내부 상태·SOH 누적 상태 등 계산 재개에 필요한 전체 snapshot을 원자적으로 게시한다. SOC 숫자만 복원하지 않는다. 실제 클래스의 내부 상태와 시간 기준을 조사해 상태 스키마·검증 조건을 구체안으로 제시한다. R-4=A에 따라 관측하지 못한 중단 구간은 임의로 적분하지 않고 새 유효 입력부터 재개한다. 중단 구간의 시작/끝·관측 부재·재개 상태를 증적에 기록하며, 첫 재개 계산에 중단 전체 시간을 정상 dt처럼 넣지 않도록 시간 기준을 설계한다. 실행 재개와 SOC/SOH 정확도 재인수는 구분하고 후자의 조건·표시는 별도 검토한다. R-5=A에 따라 snapshot 허용 노후도·종료 대기 상한은 취득/저장 간격·종료 지연·공백 영향 분석을 근거로 각각 제안해 답변 후 확정한다. 검증되지 않은 새 상태로 정상 snapshot을 덮어쓰지 않는다. 유효 snapshot 부재/손상 또는 복원 실패는 성공으로 처리하지 않는다. 정상 heartbeat까지 확인한 뒤 복구 성공으로 집계하며 세션·counter·기존 Fail-safe는 임의 초기화하지 않는다.

이전 작업 회수 실패 시 새 작업 생성과 자동 전체 프로세스 재시작을 하지 않는다. 가능한 독립 감시/로그 경로로 운영자 개입 필요를 표시한다. main·CAN까지 정지한 경우 IVI 경고 전달은 보장하지 않으며 통신 timeout 검증과 로컬 진단 경로를 구분한다. `Restart=always` 서비스 예시를 이 예외의 자동 복구 승인으로 해석하지 않는다. 회수 불가를 가짜 재시작 3회로 집계하지 않으며 기존 TC-BSW-007의 실제 시도별 실패 조건과 구분해 명세한다.

- [ ] TC-BSW-006의 하위 시험으로 일관된 상태 복원·누적값 연속성·성공 heartbeat·중복 작업 부재를 확인한다.
- [ ] snapshot 없음/손상/허용 노후도 초과·종료 무응답을 주입해 성공 오보고와 자동 재초기화가 없는지 검증한다. 노후도·종료 상한은 구체안 승인 후 시험값을 정한다.
- [ ] 회수 실패에서 운영자 재시작 요구·로그를 검증하고, 실제 재시작 3회 실패의 TC-BSW-007/TC-BMS-004-h와 분리한다. 운영자 서비스 재시작 이후는 새 프로세스/세션 복구 절차이며 메모리 snapshot 영속 복구를 주장하지 않는다.

### 3.7 SecOC — Python

`docs/ICD.md`가 계약 정본이며 `security/secoc_module.py`는 현재 구현이다. 새 세션 인증 방향과의 차이는 첫 절의 설계안에서 관리한다. **HMAC 입력 구성은 ICD §1.4를 따른다: `CAN_ID(2B BE) || RollingCounter(4B BE) || Payload(8B)`, MAC = HMAC-SHA256의 앞 4바이트.**

```python
class SecOcModule:
    def sign(self, auth_can_id: int, original_can_id: int, payload: bytes) -> AuthFrame:
        self._require_key()
        if len(payload) != 8:
            raise ValueError("SecOC payload must be 8 bytes")

        rolling_counter = self.counter
        self.counter = (self.counter + 1) & 0xFFFFFFFF
        mac = self._mac(original_can_id, rolling_counter, payload)
        return AuthFrame(auth_can_id, mac + rolling_counter.to_bytes(4, "big"))

    def verify(self, original_can_id: int, payload: bytes, auth_data: bytes) -> bool:
        self._require_key()
        if len(payload) != 8 or len(auth_data) != 8:
            return False

        rolling_counter = int.from_bytes(auth_data[4:8], "big")
        if self.last_verified_counter is not None:
            delta = (rolling_counter - self.last_verified_counter) & 0xFFFFFFFF
            if delta == 0 or delta > 100:
                return False

        expected = self._mac(original_can_id, rolling_counter, payload)
        if not hmac.compare_digest(expected, auth_data[:4]):
            return False

        self.last_verified_counter = rolling_counter
        return True

    def _mac(self, original_can_id: int, rolling_counter: int, payload: bytes) -> bytes:
        hmac_input = (
            original_can_id.to_bytes(2, "big")
            + rolling_counter.to_bytes(4, "big")
            + payload
        )
        return hmac.new(self.key, hmac_input, hashlib.sha256).digest()[:4]
```

핵심 규칙 3가지:
- **인증 프레임 8바이트 = MAC 4B + RollingCounter 4B (BE)**. MAC만 담지 않는다
- 카운터 비교는 **부호 없는 delta**로 한다. `recv <= last` 식은 `0xFFFFFFFF` 래핑에서 정상 프레임을 거부한다
- 비교는 `hmac.compare_digest` / `CRYPTO_memcmp` — 타이밍 공격 방지

```bash
python -m pytest security/tests/test_secoc.py -v
```

### 3.8 SecOC — C++ 이식

```cpp
class SecOcModule {
public:
    static constexpr std::size_t kKeySize = 32;

    bool loadKey(const std::string& path);
    void setKey(const std::array<uint8_t, kKeySize>& key);

    CanFrame sign(uint32_t auth_can_id, uint32_t original_can_id,
                  const std::array<uint8_t, 8>& payload);
    bool verify(uint32_t original_can_id, const std::array<uint8_t, 8>& payload,
                const CanFrame& auth_frame);
    uint32_t nextCounter() const;
    void resetCounter(uint32_t counter = 0);
};
```

MAC 계산부 — Python `_mac()`과 바이트 단위로 같아야 한다.

```cpp
std::array<uint8_t, 4> SecOcModule::computeMac(
    uint32_t original_can_id, uint32_t rolling_counter,
    const std::array<uint8_t, 8>& payload) const {
    std::array<uint8_t, 14> input{};
    writeUint16Be(input, original_can_id);          // [0..1]
    writeUint32Be(&input[2], rolling_counter);      // [2..5]
    std::copy(payload.begin(), payload.end(), input.begin() + 6);  // [6..13]

    std::array<uint8_t, EVP_MAX_MD_SIZE> digest{};
    unsigned int digest_len = 0;
    HMAC(EVP_sha256(), key_.data(), static_cast<int>(key_.size()),
         input.data(), input.size(), digest.data(), &digest_len);

    std::array<uint8_t, 4> truncated{};
    std::copy_n(digest.begin(), truncated.size(), truncated.begin());
    return truncated;
}
```

검증부의 상수시간 비교와 카운터 윈도우:

```cpp
const uint32_t rolling_counter = readUint32Be(&auth_frame.data[4]);
if (last_verified_counter_.has_value()) {
    const uint32_t delta = rolling_counter - last_verified_counter_.value();
    if (delta == 0U || delta > 100U) return false;
}
const auto expected = computeMac(original_can_id, rolling_counter, payload);
if (CRYPTO_memcmp(expected.data(), auth_frame.data.data(), expected.size()) != 0) return false;
last_verified_counter_ = rolling_counter;
return true;
```

CMake는 이미 `find_package(OpenSSL REQUIRED)` + `target_link_libraries(ecu_core PUBLIC OpenSSL::Crypto)`로 링크한다.

### 3.9 키 파일 준비

```bash
sudo mkdir -p /etc/secoc
sudo openssl rand -out /etc/secoc/key.bin 32
sudo chmod 400 /etc/secoc/key.bin
sudo chown root:root /etc/secoc/key.bin

ls -la /etc/secoc/key.bin
# 기대: -r-------- 1 root root 32 ... key.bin
```

- [ ] 같은 키를 Node B에도 수동 복사한다 (프로젝트 범위에서는 사전 공유)
- [ ] **키 값을 코드·시험·문서·로그·커밋에 남기지 않는다.** 시험에는 `b'\x01' * 32` 같은 명시적 더미를 쓴다

### 3.10 TC-SEC-004 교차 검증

```bash
# Python으로 기준 벡터 생성 (더미 키)
python3 -c "
from security.secoc_module import SecOcModule
m = SecOcModule(b'\\x01' * 32)
f = m.sign(0x102, 0x100, bytes([1,2,3,4,5,6,7,8]))
print('auth_data:', f.data.hex())
"
# 출력 hex를 C++ 시험의 기대값으로 사용한다
ctest --test-dir adaptive_ecu/build -R test_secoc --output-on-failure
```

현재 `test_secoc.cpp`의 `SignsKnownCounterZeroVector`가 이 역할을 한다. 벡터를 바꾸면 Python 쪽 기대값도 같이 갱신한다.

- [ ] 4주차에 IVI 담당자에게 **키 배포 방법 + 테스트 벡터**를 인계한다 ([01_연계_의존성](../common/01_연계_의존성.md))

### 3.11 ADS1115 I2C 센서 연결 — 가상 배터리 주 경로

제품 연결(2026-10-03, [CHG-011](../../../docs/aidlc/changes/CHG-011/aidlc-state.md)): 순서 3 드라이버와 4 연결을 구현했다. 사용자 결정 D1(준비·오류·지연 중 송신 보류), D2(가상 고정 -2A·25°C), D3(복구 뒤 EKF 마지막 추정값에서 재개), D4(POTENTIOMETER 제거) 기준이다. I-2=B의 '통신 유지 + 별도 오류 전달'은 ICD §8 동시 전환 때 완성하며 이번에는 byte 7을 0으로 둔다. 순서 5 실기기 시험은 사용자 장비 실행 대기다. 설계는 [SDD-ECU §3.7.3](../../../docs/SDD-ECU.md)을 따른다.

레지스터 단계 진척(2026-09-08): `ads1115_registers` 헤더·소스에 단일변환 프로토콜과 전송 인터페이스를 추가했다. 가짜 전송을 사용한 실제 C++ 검사에서 signed 65,536개 디코딩·설정 변조·실패·중복 처리를 확인했다. Linux I2C 어댑터와 실제 루프 연결은 미구현이다. [SOC 결과 §12](../../../docs/development/experiments/SOC_합성실험_결과.md)에 근거·범위를 기록했다.

ADC-1/2=A 반영(2026-09-08): 단일변환·128SPS, 요청 간 최소 100ms, 조회 간 최소 1ms, 인수 마감 20ms를 첫 시험 조건으로 채택했다. `adc_acquisition_gate.h`에 시간 제어를 구현하고 실제 C++ 호스트에서 완료 시각 201개와 중복·마감·진행 중 요청 보호를 검사했다. I2C 호출·스레드·통신 연결은 아직 없으며 마감은 호출 강제 종료를 뜻하지 않는다. [SOC 결과 §11](../../../docs/development/experiments/SOC_합성실험_결과.md)을 따른다.

승인 상태 정정(2026-09-08): 아래 과거 설명의 ‘비트 배치·HAL 미확정’은 ICD §8의 S-3=A 승인으로 해소됐다. 상태 번호와 HAL 확장 목표는 승인됐으나 제품 형식 전환은 양측·Python·Mock·시험 동기화 전까지 미적용이다. `sensor_quality.h`에 최초·복구 3회 확인을 구현하고 독립 C++ 검사로 길이 10의 59,049개 이벤트 열을 확인했다. 새 변환 식별·시간 초과 판정·I2C·CAN 연결은 포함하지 않는다.

2026-09-08 진척: `ads1115_conversion.h`와 `src/app/ads1115_conversion.cpp`의 순수 변환 모듈을 추가했다. 제품 함수를 실제 호스트 C++로 연결해 signed 16bit 65,536개 입력을 검사했다. CMake 등록·GoogleTest 시험 2개는 추가했으나 CTest는 미실행이다. I2C 취득과 SensorSimulator 연결은 아직 없으므로 하드웨어 모드 구현 완료로 표시하지 않는다. [SOC 실험 결과 §9](../../../docs/development/experiments/SOC_합성실험_결과.md)에 범위·재현 명령·해시를 기록했다.

가변저항을 사용한 가상 배터리 모사가 사용자 확정 주 계획이다. ADC 하드웨어 경로는 실제 입력 인수 대상이며 CSV는 개발·데모 백업이다. CSV 성공을 ADC 시험 성공으로 대체하지 않는다.

장비는 ADS1115 16-bit I2C ADC+PGA 보드와 10kΩ 가변저항으로 확인됐다. [확인사항](../../../docs/development/governance/의사결정_기록.md#part2-confirmed) §1에 따라 ADS1115는 3.3V, ADDR-GND(0x48), A0 단일종단, PGA ±4.096V를 초기 설정으로 사용하며 가변저항 양끝은 3.3V/GND, 와이퍼는 A0에 연결한다. PGA FSR이 입력 핀의 허용 전압을 늘리는 것은 아니므로 실제 입력은 0~3.3V로 제한한다. [SDD-ECU §3.7.3](../../../docs/SDD-ECU.md)의 기존 FSR 충돌은 ±4.096V 변환식과 0/중간/상단 계산 벡터로 정정했다. 해당 벡터의 드라이버 시험과 기존 센서 오류 정책 검증은 구현 시 수행하며 문서 계산 검증을 장비 시험 통과로 표시하지 않는다.

| 순서 | 수행 과제 | 인수 조건 |
|---|---|---|
| 1 사양 확인 | 제품 회로·전원·I2C pull-up·주소·AIN 입력 범위·PGA 확인 | RPi 신호 전압과 모듈 사양 대조, 실제 선택 근거 기록 |
| 2 단위 계약 | raw signed 16bit→ADC V→가상 팩 V의 변환 구간·보정점 확정 | 실제 입력 최대가 선택 범위를 넘지 않음, SDD·시험 입력 동기화 |
| 3 드라이버 | I2C 초기화·변환 설정·ready 확인·읽기·종료, 재시도 상한 | 읽기 실패·분리·포화·오래된 샘플을 정상 새 값으로 처리하지 않음 |
| 4 연결 | 실제 읽은 SensorData를 주기 루프·EKF·Fail-safe·CAN에 전달 | setAdcData만 만든 상태나 I2C 주소 검출만으로 완료하지 않음 |
| 5 실기기 시험 | 알려진 입력점·양끝·중간·단절·복구·스텝 입력 | raw/ADC V/가상 팩 V·SOC·전이·실측 수렴시간 기록, TC-BSW-008-d 연결 |

사용자 I-2=B에 따라 ADC 오류 중에도 BMS 통신을 유지하며 마지막 유효값과 별도 오류/유효성을 함께 전달하는 설계를 수행한다. Q-1=B·Q-2~4=A에 따라 기존 BMS 예약 영역을 이용하고, 마지막 정상값을 구분해 유지하며 새 정상 입력 3회 후 복구하고 센서 오류만으로 Fail-safe를 변경하지 않는다. R-1=A의 상세 센서 상태와 R-3=A의 최초 3회 확인도 반영한다. 비트 배치·HAL 목표는 ICD §8의 S-3=A로 승인됐고 제품 전환은 미완료이며 R-2=A의 화면 시간은 IVI 정상 데이터 수신 기준으로 정했다. [공동 규약](../common/00_협업_규약.md)의 Q 공통 정책을 따른다. 통신 유지가 입력 유효성을 의미하지 않는다. 오류를 숨기고 CONSTANT/CSV로 자동 전환하지 않는다. 가변저항으로 임계 전압을 만든 사실과 EKF가 임계 SOC에 도달한 사실은 구분해 계측한다. '<5%' 판정은 5%와 같다는 이유로 통과시키지 않는다.

### 3.11.1 POTENTIOMETER 사용처 조사·이관 후 제거 — I-5=B

**완료(2026-10-03, CHG-011)**: 아래 사용처 4곳을 모두 정리했다. 범위 제한(clamp) 시험의 의미는 실제 ADC 경로에서 범위 밖 값을 거부하는 기존 변환·취득 시험이 담당하고, `SensorSimulator`에는 ADS1115 모드 출력·모드 이름 검증 시험을 둔다. 장비 없는 시험에서 I2C를 열지 않는다.

사용자가 조사→필요 기능 이관→삭제→회귀 검증을 선택했다. 이번 작업은 그 실행 계획을 반영하며 현재 소스를 삭제하지 않는다.

| 현재 확인한 사용처 | 후속 과제 |
|---|---|
| `adaptive_ecu/include/sensor_simulator.h`의 enum·ADC 값 setter | ADC 변환/시험 입력의 책임을 분리하고 필요한 setter 사용처를 확인 |
| `adaptive_ecu/src/app/sensor_simulator.cpp`의 POTENTIOMETER/ADS1115 분기 | 실제 ADC 읽기 경로와 시험 입력 경로를 구분한 뒤 중복 분기 정리 |
| `adaptive_ecu/main.cpp`의 문자열 파싱 | 이관 후 옛 CLI를 제거하고 미지원 모드 오류 처리를 시험; 조용히 다른 모드로 대체하지 않음 |
| `adaptive_ecu/test/test_sensor_simulator.cpp`의 `PotentiometerModeReturnsClampedAdcData` | 주입값 범위 제한을 검사하는 기존 의미를 ADC 변환 단위시험으로 이관하는 안을 구체화 |

정적 조사에서 실제 단위시험 사용처가 발견됐다. 이관안은 기존 명목 범위 제한 시험과 새 ADC 포화/오류 판정을 구분해야 한다. 단순히 enum 이름만 ADS1115로 바꿔 물리 장비가 없는 시험에서 I2C를 열게 하지 않는다. 시험 입력 주입 경계·새 실패 조건을 정리해 확인한 후 구현한다. 소스·CLI·시험·현행 계획의 참조를 함께 정리하고 공식 4모드 요구와 대조한다.

### 3.12 정확도 평가 자료와 데모 입력 분리

| 용도 | 예정 산출물 | 필요한 근거 |
|---|---|---|
| TC-BMS-002 합성 정량 평가 | `adaptive_ecu/data/battery_profile_1h.csv` 및 별도 참 SOC·manifest (예정) | S-7=A: 생성 모델·관측 오차·단위·capacity·초기값·seed·분리된 참 상태와 동일 관측 |
| NASA 재생·데이터 검증 | 원시 MAT·변환 입력·검사 결과·manifest (최종 경로 미확정) | 원시 단셀 단위·cycle·시간·출처/해시·전처리·결측·적분 보존; 정확도 정답으로 사용하지 않음 |
| 가변저항 장애 시 데모 백업 | `adaptive_ecu/data/failsafe_demo.csv` 및 manifest | NORMAL 시작→WARNING→CRITICAL 재현, 초기값·dt·온도·전류·입력 유지시간과 실측 도달 시각 |

현재 5행 battery_profile.csv는 어느 목적의 완료 증거도 아니다. 정확도 평가에 임의의 전압 램프를 NASA 데이터로 사용하거나 행 복제만으로 1시간 자료를 구성하지 않는다. 합성 조건은 S-21=A로 확정됐으며 TC-BMS-002 제품 실행·증거 인수는 후속 과제다. NASA 재생 인수는 별도로 진행한다.

정확도 기준값을 비교 대상 쿨롱 카운팅과 동일한 입력·식으로 만들면 비교가 순환적이므로 사용하지 않는다. 데이터 선택·변환과 잡음/초기 오차 조건은 평가 전에 고정하고 학습·튜닝과 평가를 분리한다. S-7=A에 따라 합성 모의 시험을 TC-BMS-002의 정량 평가로 표시하며 NASA 재생·실장비 결과와 분리한다. EKF 우위가 나오도록 평가 입력을 사후 변경하지 않는다.

데모 입력은 상태 전이 검증용으로만 생성한다. 전압 램프는 후보이며 모델 응답 시험으로 WARNING·CRITICAL이 실제 발생하는지 확인한 후 파일을 인계한다. 10직렬·50Ah는 SDD의 가상 모델 설정이고 실제 보조배터리 사양이 아니다. 사용자 I-6=A의 NASA 유지 결정은 S-7=A로 재생·데이터 검증 목적에 유지한다. 정량 비교 입력은 S-21=A의 고정 합성 조건으로 분리하며 제품 실행 증거는 후속 인수한다.

실행·영상·백업의 공동 정본은 [공동 통합시험](../common/02_통합시험.md) IT-002다. 데모 수렴시간과 모델 정확도는 별도 결과로 보고한다.

**NASA 후보 1차 확인:** [NASA Li-ion Battery Aging Datasets](https://data.nasa.gov/dataset/li-ion-battery-aging-datasets)는 충전·방전·임피던스, 온도·전압·전류·시간·방전 용량을 설명하며 정격 용량 2Ah의 열화 실험을 기술한다. 공개 필드 목록에는 직접 측정한 SOC 정답이 명시돼 있지 않다. 따라서 가상 50Ah와 바로 같다고 보거나 독립 SOC 기준을 확보했다고 주장할 수 없다.

이전에는 메타데이터만 확인했으나 후속 원시 후보 검토를 수행했다. 최신 접근 경로·해시·샘플/구간 확인과 한계는 이 문서의 “NASA 원시 후보 확인 결과와 입력 인수 게이트”를 따른다. 자료 확보 경로는 [NASA PCoE 저장소](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/)에서 추적한다. 원시 파일·배포 조건을 확인하고, 비교 대상과 독립적으로 설명 가능한 SOC 기준·오차/초기 상태 조건을 확보한 뒤 모델 적용안을 제시한다. 부적합하면 공식 시험/모델 변경을 다시 확인한다.

---

## 4. 검증 명령과 합격 기준

```bash
cmake -S adaptive_ecu -B adaptive_ecu/build -DECU_BUILD_TESTS=ON
cmake --build adaptive_ecu/build

ctest --test-dir adaptive_ecu/build -R test_ekf_soc          --output-on-failure
ctest --test-dir adaptive_ecu/build -R test_soh_estimator    --output-on-failure
ctest --test-dir adaptive_ecu/build -R test_failsafe_sm      --output-on-failure
ctest --test-dir adaptive_ecu/build -R test_watchdog_manager --output-on-failure
ctest --test-dir adaptive_ecu/build -R test_secoc            --output-on-failure

python -m pytest security/tests/test_secoc.py -v
```

| TC | 합격 기준 | 현재 |
|---|---|---|
| TC-BMS-001 | 1,000 step(100초) 후 이론 SOC와 오차 ≤0.5% | 시험 추가 필요 (3.3) |
| TC-BMS-002 | RMSE_EKF < RMSE_쿨롱카운팅 | 시험 추가 필요 (3.3) |
| TC-BMS-003 | SOH 정확도 | 시험 존재, 이번 작업에서 미실행 |
| TC-BMS-004 | 전이 a~h 전부 + Branch Coverage 100% | 시험 재실행·Coverage 측정 필요 (3.5) |
| TC-BSW-006 | 타임아웃 감지 | 기존 감지 시험 존재, 재시작 포함 검증 필요 |
| TC-BSW-007 | 재시작 3회 연속 실패 시 NORMAL→WARNING, reason=0x07 | **미구현** (3.6) |
| TC-SEC-001~004 | 생성·검증·리플레이 거부·교차 벡터 | 현재 시험 재실행 및 새 계약 시험 필요 |

---

## 5. 실패 시 대응과 우회

**SOC 오차가 기준을 넘음**
1. 인자 순서(`dt, current, voltage`)와 전류 부호를 먼저 확인한다. 가장 흔한 원인이다
2. 3.1 표대로 R → Q 순으로 조정한다
3. 그래도 안 되면 평가 입력·독립 기준값·모델 적용 범위를 점검한다. 계수 변경은 3.2의 제약과 변경 근거를 검토한 뒤 수행한다

**Branch Coverage 100% 미달**
- `genhtml` 리포트에서 미커버 라인을 확인한다
- CRITICAL 관련 분기가 자주 빠진다. WARNING → CRITICAL → SHUTDOWN 순서로 상태를 만들어 진입한다
- `manualReset()`의 "SHUTDOWN이 아닐 때 false" 경로도 시험 대상이다

**Python ↔ C++ MAC 불일치**
- 입력 조립 순서를 바이트 단위로 덤프해 비교한다: CAN_ID 2B → Counter 4B → Payload 8B, 총 14B
- CAN ID를 4바이트로 쓰지 않았는지 확인한다 (2바이트 BE가 계약)
- 키 길이가 32바이트인지 확인한다. `loadKey()`는 `gcount() != 32`면 실패한다

**OpenSSL 링크 에러**
```bash
pkg-config --libs openssl
# 기대: -lssl -lcrypto
sudo apt install -y libssl-dev
```

**ADS1115 0x48 미검출**
- 배선과 ADDR 핀 접지 확인
- `sudo apt install -y python3-smbus` 후 Python으로 직접 읽어 하드웨어 문제인지 분리
- 미해결 시 `CONSTANT`/`PROFILE_CSV` 모드로 개발을 계속한다. 백업 진행을 ADC 인수 완료로 처리하지 않는다

---

## 6. 완료 체크리스트

- [ ] EKF 단위·정량 시험 통과 (TC-BMS-001, TC-BMS-002)
- [ ] 최종 Q/R/P0와 OCV 모델을 `docs/SDD-ECU.md`에 기록
- [ ] SOH 시험 통과 (TC-BMS-003)
- [ ] Fail-safe 전이 a~h 통과, `failsafe_sm.cpp` Branch Coverage 100%
- [ ] CRITICAL 복귀 경로 유무를 SRS와 대조해 결론을 남김
- [ ] Watchdog 타임아웃 감지 통과 (TC-BSW-006), TC-BSW-007 재시작 실패·전이 구현 및 검증
- [ ] SecOC Python·C++ 시험 통과 (TC-SEC-001~004)
- [ ] `/etc/secoc/key.bin` 생성, 퍼미션 400, 저장소에 키 없음
- [ ] IVI에 SecOC 테스트 벡터와 키 배포 방법 인계 완료
- [ ] `v0.3.0` 태그 생성


### 계산 snapshot의 실제 상태 대응과 검증 과제

현재 헤더와 소스를 정적으로 확인했다. snapshot 내보내기/복원 API는 아직 없으며 아래는 구현할 상태 계약의 목록이다. 상태가 있다는 사실을 복원 기능 존재로 표시하지 않는다.

| 현재 클래스·필드 | 보존·대조 목적 | 복원 전에 검증할 조건 |
|---|---|---|
| EkfSocEstimator: `soc_`, `covariance_` | SOC와 추정 불확실성을 같은 계산 완료 시점으로 복원 | 유한값, SOC [0,1], 공분산 음수 아님; 손상값을 clamp해 정상 복원했다고 하지 않음 |
| `capacity_ah_`, `process_noise_`, `measurement_noise_` | 이전 상태와 현재 추정 설정의 일치 | 용량 양수·유한, 잡음값 유효, 혁신 공분산 분모가 유효한 설정인지 검증 |
| SohEstimator: `initial_capacity_ah_`, `estimated_capacity_ah_`, `accumulated_discharge_ah_` | 초기/추정 용량과 누적 방전량 연속성 | 유한값, 초기 용량 양수, 추정 용량 0~초기 용량, 누적량 음수 아님 |
| 향후 모델/설정 식별자·snapshot 버전 | 과거 선형/2.6Ah 기록과 현재 3차/50Ah 소스의 혼용 방지 | 모델·단위·팩/셀 기준·설정 불일치는 복원 실패. 저장 포맷을 아직 구현됐다고 하지 않음 |
| 향후 완료 샘플 식별·시각·작업 세대 | 중간 상태/다른 프로세스 상태 혼입 및 중복 반영 방지 | main 외부 저장소에 하나의 계산 완료 묶음으로 게시; 작업 회수 후 같은 묶음 인수 |

R-4=A에 따라 공백을 가짜 입력으로 적분하지 않는다. 정확도 재인수 조건은 실행 heartbeat와 분리한다. R-5=A의 허용 노후도와 종료 상한은 미확정이다. 설정·시각 일치/불일치, NaN/Inf·부분 게시·중복 인수·snapshot 없음의 하위 시험을 설계한다. SecOC 키/counter와 Fail-safe 상태는 이 추정기 묶음으로 초기화하지 않는다.

### POTENTIOMETER 기존 시험의 의미별 이관

기존 `PotentiometerModeReturnsClampedAdcData`는 setter에 45V/-20A/80°C를 주고 42V/-10A/70°C로 제한되는지를 검사한다. 실제 ADC 연결/읽기/오류를 검사하는 시험이 아니다.

1. 가상 입력의 범위 제한이라는 기존 검증 의미는 독립 변환/범위 검사 단위시험으로 이관한다. 실제 I2C를 여는 하드웨어 모드로 이름만 바꾸지 않는다.
2. 실제 ADS1115 취득에는 유효 범위 밖·변환 미완료·I/O 오류를 품질 오류로 판정하는 별도 시험을 둔다. 가상 입력 clamp를 실제 오류 은폐에 재사용하지 않는다.
3. 실제 소스에서 CLI `potentiometer` 파싱·enum·분기·setter 호출과 문서 사용처를 다시 검색하고, 이관 시험이 검증된 변경 단위에서 옛 모드를 제거한다.
4. 정식 4개 모드의 회귀와 CLI 오류 안내를 확인한다. 이번 계획 단계에서는 enum·setter·제품 시험을 삭제하거나 변경하지 않았다.


### NASA 원시 후보 확인 결과와 입력 인수 게이트

> 이 절의 독립 SOC 확보 논의와 TC-BMS-002 연결은 S-7 이전 조사 기록이다. 현재 NASA의 역할은 §3.12와 아래 S-7 적용 과제의 재생·데이터 검증이며, 합성 정확도 인수의 대기 사유와 구분한다.

2026-09-06 [NASA PCoE 공식 배포 안내](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/)의 Batteries 항목에서 [원본 배포 ZIP](https://phm-datasets.s3.amazonaws.com/NASA/5.+Battery+Data+Set.zip)을 확인했다. ZIP 전체 크기는 209,708,670바이트이며 HTTP 범위 읽기로 목록을 확인한 뒤 내부 `2. BatteryAgingARC_25_26_27_28_P1.zip`만 조사용으로 확보했다. 이 후보를 최종 평가 자료로 채택한 것은 아니다.

내부 ZIP SHA-256: `7fa159be0c4e78d97233ef777587f46270d1389b5d8a21d33c6e7573a8c8e3b8`.

| 파일 | 원시 cycle 전체 | charge/discharge cycle | 1시간 이상 cycle | 유한값 조건 실패 cycle | MAT SHA-256 |
|---|---:|---:|---:|---:|---|
| B0028.mat | 80 | 59 | 58 | 1 | `050c377e85a2c41165f2e2e0d22bf9575385dd8c835a713c27edb65af6bb25e8` |
| B0025.mat | 80 | 59 | 58 | 1 | `38894747a9c79d719e95a2e6c42be18017e29c522b760056b680a65105d1a15f` |
| B0026.mat | 80 | 59 | 58 | 1 | `ca5eee0b33d8070e3a6c254696444a0c65a12f40587fcfc8db858640b2e6e36c` |
| B0027.mat | 80 | 59 | 58 | 1 | `de2b4045ef20a6900885e169f3540664bb637f5f94b41fb4333c31d759237209` |

검사는 ZIP 무결성 확인과 제한된 MATLAB-v5 읽기 도구를 사용한 원시 구조/숫자 검토다. scipy가 설치돼 있지 않아 이 후보의 구조만 읽는 임시 도구를 사용했다. 독립적인 MATLAB/scipy 교차 판독과 최종 CSV 변환 검증은 아직 수행하지 않았다. 조사 기록은 `tmp/nasa_review/outer_manifest.json`, `candidate_manifest.json`, `mat_inspection.json`, 재현 도구는 `tmp/inspect_nasa_zip.py`, `tmp/inspect_nasa_mat.py`다. 주요 출처·해시·결론은 이 문서에 보존하므로 임시 파일만이 유일한 근거가 되지 않게 한다.

**원시 관측:** B0028의 0-based cycle 3(discharge)은 641개 샘플, 6,515.422초, 인접 시간 간격 약 9.36~10.578초다. cycle 1(charge)은 3,815개 샘플, 10,806.079초다. 조사한 236개 charge/discharge cycle의 시간은 증가하지만 각 파일의 cycle 79에는 입력 필드 중 비유한값이 있고 길이도 1시간 미만이다. 이 행들을 무조건 정상 데이터로 인수하지 않는다. 원시 필드 목록에는 별도의 SOC 정답 필드가 없다.

따라서 NASA 자료에 1시간 구간이 없어서 차단된 것이 아니라, **0.1초 평가 격자 변환·참조 SOC·모델 적용 조건이 아직 해결되지 않은 것**이다. README의 부하 설명만으로 실제 Current_measured 시퀀스를 대체하지 않는다.

1. 최종 후보는 원시 시각/전압/전류/온도 배열 길이 일치, 유한값, 단조 시간, 구간 경계, 결측을 교차 판독으로 검증한다. 실패 cycle 제외 근거는 성능 결과를 보기 전에 고정한다.
2. 36,000 step은 시험의 계산 격자이지 NASA 원시 샘플 수가 아니다. 0.1초 재표본화 방법, 시간 경계(초기 상태와 36,000회 update), 전류 적분 보존 오차, 전압/온도 보간, 결측 차단 조건을 명세하고 원시 해상도를 증적에 남긴다. 드문 샘플을 복제했다고 10Hz 실측을 확보했다고 하지 않는다.
3. 직접 SOC 정답은 확인되지 않았다. 관측 전압을 같은 OCV 식에 역대입하거나 비교 대상 쿨롱 적분을 그대로 정답으로 사용하지 않는다. 기준 용량·초기/종료 상태·독립 기준 생성 근거·불확실성을 마련한 뒤 참조 SOC 채택안을 검토한다. 확보 불가 시 공식 시험 변경 대안을 사용자에게 제시한다.
4. NASA 개별 셀 데이터와 가상 10직렬/50Ah의 단위·용량·OCV를 자동 동일시하지 않는다. 원시 셀에 맞춘 평가 설정 또는 근거 있는 변환안을 비교해 선택받는다. 전압만 10배 바꾸고 용량/전류/시간을 그대로 두는 것으로 타당성이 입증되지 않는다.
5. 모델 튜닝과 평가 구간/셀을 분리하고 동일 고정 입력·초기 조건으로 EKF와 비교기를 평가한다. 자료 선정·보간·기준 생성 규칙을 성능을 본 뒤 유리하게 바꾸지 않는다. 모델별 RMSE와 최대 오차를 구분하고 기준 불확실성을 함께 보고한다.

**현재 판정:** 후보 원시 자료 접근/구조 확인은 진행됐고, TC-BMS-002의 최종 입력·독립 기준·모델 정합 인수는 보류다. 위 수치는 자료 구조 측정이며 EKF 성능이나 실제 장비 성능 결과가 아니다.


**S-3=A 후속 상태:** 이전 본문의 byte 7·HAL “검토 대기”는 [ICD §8](../../../docs/ICD.md#8-승인된-다음-전환-목표--s-3a-제품-반영-전)의 목표 계약 승인으로 갱신됐다. 목표를 다시 제안하는 단계는 끝났고 실제 양측 구현·직렬화·Mock·참조·시험 동시 전환이 남아 있다. 기존 코드 예시는 전환 전 상태이며 목표가 이미 구현됐다고 해석하지 않는다. S-2=A의 상태 통보가 실제 전류 제어를 뜻하지 않는다는 기준도 적용한다.


### 독립 SOC·재표본화 검토 결과 — 3번 단계

2026-09-06 `python tmp/soc_reference_review.py`로 원시 후보 B0028의 0-based cycle 3을 추가 조사했다. 제한 MAT 판독기를 재사용한 수치 검토이며 독립 판독·제품 EKF 실행·실제 SOC 측정은 아니다. 결과는 `tmp/nasa_review/soc_reference_review.json`, 도구 SHA-256은 `10349a03209628384be27e8c80246e6c6553c9b1524e7a27c123fc81ecf1bd38`이다.

| 검토 | 관찰 결과 | 의미 |
|---|---|---|
| 첫 1시간 전류의 구간별 선형 복원 적분 | -0.9962237086299596Ah | 원시 샘플 사이를 선형으로 가정한 값이며 실제 연속 전류를 복원했다는 뜻은 아님 |
| 0.1초 구간 평균 전류 36,000개로 변환 | 위 가정의 적분 대비 보존 오차 0.0Ah(이번 부동소수점 계산 결과) | 숫자 검사 허용차 1e-10Ah 이내. 센서 정확도·재표본화 물리 오차의 합격 기준이 아님 |
| 전체 구간 적분 절댓값과 Capacity 필드 | 1.8046847720100747Ah와 1.8046847720100736Ah | 약 1.1e-15Ah 차이. 이 구간의 Capacity를 전류 적분과 독립적인 SOC 정답의 근거로 사용할 수 있다고 입증하지 못함 |
| 같은 적분·초기값·용량을 기준과 비교기에 사용 | 비교기 RMSE=0 | 음수가 될 수 없는 EKF RMSE에 대해 엄격한 개선을 요구하는 평가가 퇴화한다는 수학적 반례. EKF 성능 실험 결과가 아님 |
| 부호·단위 확인 | 80%, -2A, 100초, 50Ah → 79.8888888888889% | TC-BMS-001과 일치. SDD 기존 식은 clamp 전 480%가 되어 오류 확인; 실제 코드와 계획의 올바른 식에 맞춰 SDD 정정 |

검사 3개(적분 보존·동일 기준 반례·기존 공식 이론값) 통과. 원시 필드의 직접 SOC 정답 부재는 [NASA 공식 필드 설명](https://data.nasa.gov/dataset/li-ion-battery-aging-datasets)과도 대조했다. 공식 안내의 약 10Hz 수집 설명을 이 후보의 실제 Time 간격 대신 사용하지 않는다. README는 0.05Hz 사각 부하를 기술하지만 이번 저장 샘플 간격은 약 10초이므로, 선형 복원이나 반복 행으로 실제 부하 전환 시점을 확보했다고 주장하지 않는다. Capacity의 계산 내부 구현까지 확인한 것은 아니다.

#### 입력 변환과 평가의 필수 조건

1. 원시 구간은 모델 결과를 보기 전에 선정한다. cycle 경계를 이어 붙이지 않으며 배열 길이·단조 시각·유한값·부호·단위·누락 구간을 먼저 검사한다. 제외 규칙과 원시 해시를 manifest에 보존한다.
2. 이번 선형 복원은 비교용 후보다. 채택 시 구간 전류 평균을 원시 시각에서 적분해 구하고 0.1초 구간별 적분량을 보존한다. 초기 상태 t=0과 36,000번 update의 종료 t=3600을 구분한다. 전압·온도는 종료 시각 보간 값인지 명시하고 보간 자료와 원시 관측의 구분을 남긴다. 외삽하지 않는다. 스트리밍 실행에서는 미래 샘플 접근 가능 여부를 따로 검토한다.
3. 결측 상한·보간 방법·전류 적분 불확실성을 근거 없이 수치로 고정하지 않는다. 선형/유지 복원 민감도와 부하 해상도 한계를 검토하여 채택안을 제시한다. 수치 적분 보존은 측정의 정확성 보장이 아니다.
4. S-7=A에 따라 NASA 단셀 재생·데이터 검증과 10직렬/50Ah 가상 장비 시험을 분리한다. NASA 단자 전압을 평형 OCV로 자동 간주하지 않는다. 내부 저항·부하 영향·온도·용량·OCV 식의 적용 범위와 튜닝/평가 자료 분리가 필요하다.
5. 기준 SOC 생성기는 제품 추정 결과를 읽지 않고 기준 파일을 평가 전에 고정한다. 동일 코드의 OCV 함수를 복제한 시험은 구현 정합 검사로 분류하며 실제 셀 모델 유효성 증거로 쓰지 않는다. 독립 구현만으로 물리적 독립 정답이 생기지는 않는다.
6. 합성 기준을 채택하더라도 참 상태와 관측을 분리하고 두 추정기에 동일한 관측·초기 조건을 준다. 잡음·바이어스·용량 오차·seed·구간을 성능 결과 전에 고정하고 무오차 대조군도 보고한다. 실제 근거 없는 잡음 수치를 실측으로 표시하거나 EKF 승리를 위해 사후 조정하지 않는다.
7. 두 RMSE와 최대 절대 오차는 SOC 백분율 포인트로 보고한다. 0.1초 균일 격자의 평균과 불균일 원시 격자의 시간 가중 평균을 혼동하지 않는다. 동일 평가 구간·표본 수·실패/클리핑 건수·초기 구간 제외 여부를 명시한다. 기준 불확실성이 미정이면 물리적 정확도 합격으로 판정하지 않는다.

**판정:** 수치 변환의 실행 가능성과 공식 식 오류는 확인했다. NASA 후보만으로 독립 SOC 기준을 확보하지 못했으므로 FR-BMS-002/TC-BMS-002 인수는 보류한다. [질문리스트](../../../docs/development/governance/의사결정_기록.md#part1-questions)의 S-7=A 답변으로 공식 TC 입력은 합성으로 변경했으며 비교 합격 기준은 유지한다. 아래 S-7 적용 과제를 따른다.



### S-7 적용 과제 — 세 가지 증거를 분리

1. NASA 변환기는 원시 단셀 단위를 유지한다. MAT 독립 판독, 배열·시각·유한값·구간 검사, 전처리/재표본화 규칙 확정과 로더 출력 대조를 진행한다. 원시 간격과 실제 센서 해상도의 한계를 기록한다. 팩용 EKF 실행을 NASA 재생 완료의 필수 조건으로 추가하지 않는다.
2. 합성 시험은 참 상태 생성기 → 관측 생성기 → 동일 관측을 받는 EKF/쿨롱 비교기 → 참 상태를 읽는 평가기로 구성한다. 제품 추정 결과를 참 상태 생성에 되먹이지 않는다. 초기 상태와 각 update 종료 시각을 맞추고 누락·중복·참 상태 노출을 차단한다.
3. 생성 모델과 제품 OCV 모델의 관계, 전류/전압 오차·바이어스, 초기 오차·용량, 부하 범위, seed/반복, 대조군·합격 대상 시나리오를 근거와 영향표로 구체화한다. 애매한 선택·미확정 수치는 인터뷰 후 확정한다. 현재 3차 OCV를 복사했다는 이유만으로 독립 물리 모델이 됐다고 하지 않는다.
4. 조건을 고정한 뒤 1시간 합성 관측·참 상태·manifest를 생성한다. 양측 추정기 입력이 동일한지 확인하고 전체 구간 RMSE·최대 오차·실패/클리핑을 기록한다. 기존 엄격한 RMSE 비교 기준을 유지하고 미달 결과를 그대로 보고한다.
5. 가변저항·ADS1115 시험은 기존 TC에 따라 취득·품질·상태 통보·화면 전달 증거를 수집한다. 합성 정확도와 NASA 재생 결과를 별도 목록으로 인계한다.

완료 조건: 세 종류의 입력·단위·조건·결과·주장 범위가 구분되고 각 검증이 실제 실행되어야 한다. 이번 작업은 평가 구성의 승인 반영이며 CSV 생성·제품 시험·하드웨어 인수 완료가 아니다.



### 복구 조건·제한 시간 검토 — 4번 단계

현재 `adaptive_ecu/src/bsw/watchdog_manager.cpp`는 주기 sleep 후 마지막 kick 경과를 확인하고 timeoutCount를 증가시켜 콜백을 호출한다. 콜백 이후 기준 시각을 다시 설정한다. `main.cpp`는 처리 시작 전에 kick하며, 작업별 회수·재시작·snapshot 복원 API는 없다. 기존 시험 두 개는 콜백 발생과 kick에 의한 timeout 방지만 확인한다. 실제 BMS 복구 시간이나 종료 상한을 측정할 구현은 아직 없으므로 이를 실측했다고 하지 않는다.

#### 서로 다른 시간과 상태를 분리

| 항목 | 측정 기준·용도 | 현재 상태 |
|---|---|---|
| 감시 주기·무응답 임계 | 마지막 처리 완료 heartbeat부터 경과 측정; 1초 감시·3초 임계 | SRS의 기존 기준 유지. 임계 도달 시각과 실제 감지 시각은 구분 |
| snapshot 시각 | 마지막 유효 계산 입력 시각과 원자적 게시 시각을 각각 기록 | 정상 계산 직후 게시할 계획; 센서 오류 중 유효 상태가 없으면 옛 snapshot 시각을 새것으로 바꾸지 않음 |
| snapshot 노후도 | 복원 검사 시각에서 해당 마지막 유효 계산 시각까지 경과 | R-5=A의 최대 허용값 미확정. 게시 지연·감지 지연·회수 대기까지 고려 |
| 종료 대기 | main의 정지 요청부터 기존 작업의 실제 종료·자원 회수 확인까지 | 상한 미확정. 시간 만료 자체를 종료 완료로 간주하지 않음 |
| 복구 실행 시간 | 감지→정지 요청→회수→복원→새 작업 처리 완료를 구간별 기록 | 신규 작업 실행만으로 성공 판정하지 않음 |
| 센서 품질·정확도 | 3회 새 유효 ADC 변환과 공백 이후 추정 오차를 각각 관찰 | 처리 완료 heartbeat·센서 정상 복귀·정확도 재인수는 별개 |

1초 감시의 이상적 시계 모형에서 마지막 heartbeat 위상 1,000개를 조사한 결과 감지 경과는 3,000~3,999ms였다. 연속 위상의 이상적 범위는 3초 이상 4초 미만이며 실제 OS 스케줄링·콜백/I/O 지연을 포함한 상한이 아니다. `python tmp/recovery_timing_review.py`의 논리 검사 3개 통과, 결과 `tmp/recovery_timing_result.json`, 도구 SHA-256 `71bf8e12c0aac87c9578b1a1789824e7fb8e5544838b5edd30f1e09b8543ee73`. 제품 재시작 시험이나 실장비 지연 검증이 아니다.

따라서 snapshot 상한을 BMS 100ms 주기와 같게 두거나 무조건 3초로 정하면, 정상적으로 저장했던 상태도 장애 감지 시 이미 오래되어 복원 불가가 될 수 있다. 반대로 오래 허용하면 관측 공백에 따른 정확도 손실이 커질 수 있다. 상한은 자동으로 정하지 않는다. 필요 연령은 마지막 유효 상태→마지막 처리 완료의 차이, 임계 대기, 감시 위상/실행 지연, 정지·회수·검사 지연을 합쳐 분석한다. 센서 오류가 먼저 지속됐다면 마지막 유효 상태는 더 오래됐을 수 있다.

#### 복구 상태 전이와 실패 처리

1. main이 소유한 감독 경로는 BMS 작업과 독립적으로 진행해야 한다. 처리 완료 지점 heartbeat를 작업 식별자와 연결한다. 살아 있는 main 루프나 재전송만으로 BMS 진행을 대신하지 않는다. 오류를 정상 처리한 주기와 유효 센서 계산 여부는 구분해 기록한다.
2. 동일 작업의 복구가 진행 중이면 timeout 알림을 중복 재시작으로 집계하지 않는다. `timeoutCount()`는 감지 횟수이며 실제 복구 시도/연속 실패 횟수와 다른 값이다. 한 작업의 실제 시도 시작·결과·세대를 기록한다.
3. 정지 요청 후 기존 작업의 종료와 자원 회수를 확인한 경우에만 복원과 새 작업 시작을 허용한다. 오래된 작업이 뒤늦게 heartbeat/snapshot을 게시해 새 작업 성공이나 상태로 오인되지 않도록 세대 경계를 검증한다.
4. 회수 실패는 Q-6=A에 따라 복구 실패·운영자 서비스 재시작 필요로 보고한다. 기존 작업이 남아 있는 상태에서 3회 숫자를 채우려고 새 작업을 만들거나 프로세스를 자동 재시작하지 않는다. TC-BSW-007의 회수 가능한 실제 재시작 3회 실패와 별개 경로다.
5. snapshot은 같은 프로세스의 검증된 전체 상태를 사용한다. 없음·손상·모델/단위 불일치·허용 연령 초과는 복원 실패다. 미래 시각·부분 게시·이전 세대·다른 부팅의 시각도 검증 대상이다. 단조 시계를 쓰되 프로세스/부팅을 넘긴 영속 복원으로 확대하지 않는다.
6. 공백 구간은 R-4=A에 따라 적분하지 않는다. 복원 전후 기준 시각과 최초 신규 관측을 기록하며 공백 전체를 첫 update의 dt로 넣지 않는다. 정확한 최초 update 경계 정책은 구현 후보를 제시할 때 명시한다. 보안 세션·counter·기존 Fail-safe를 추정기 복원과 함께 초기화하지 않는다.
7. 새 작업의 실제 처리 완료 heartbeat와 올바른 상태 소유를 확인해야 실행 복구 성공이다. 센서 품질 복귀는 기존 Q-3/R-3의 새 유효 변환 3회 조건을 따르고, 정확도 재인수는 S-7 합성 공백 시나리오의 별도 결과로 남긴다. heartbeat만으로 값이나 정확도를 정상으로 표시하지 않는다.

#### 숫자 확정을 위한 선행 측정과 인수

R-5=A의 기존 답변을 다시 묻지 않는다. 아래 증거를 확보한 후 snapshot 허용 노후도·종료 대기 상한을 구체적인 숫자와 선택안으로 인터뷰한다. 현재 미구현 상태의 임의 기본값을 만들지 않는다.

- 취득/I2C 호출·잠금·계산·대기·CAN 송신 경계별 정지 응답 가능 여부와 최대 블로킹 조건을 조사한다. 블로킹이 무제한이면 짧은 join 대기 값을 선언하는 것으로 해결하지 않는다.
- 대상 장비에서 정상/부하/센서 오류/CAN 장애별 입력 완료·snapshot 게시·heartbeat·timeout 감지·정지 요청·종료 확인·복원·새 처리 완료를 단조 시각으로 기록한다. 실제 값·목표·시험 주입값을 분리한다.
- 관측된 최댓값은 보편적 상한이 아니므로 장비/커널/빌드/부하/반복 조건과 예외·미회수 사례를 함께 기록한다. 측정 여유의 근거와 의도적으로 포기하는 복구 범위를 제시한다.
- S-7 합성 평가에서 관측 공백 길이에 따른 복원 후 RMSE·최대 오차·초기 상태 불확실성을 검토한다. 공백 동안 전류가 알려져 있다고 제품에 제공하지 않는다. 모델·오차 조건이 미확정이면 정확도 기반 노후 상한을 확정할 수 없다.
- 승인된 상한의 직전·경계·직후, 시각 역행/미래값, 없음·손상, 회수 실패, 오래된 작업의 지연 게시, 실제 재시작 실패 1/2/3회와 정상 복귀를 TC-BSW-006/007의 하위 조건으로 검증한다. 경계 비교 연산과 연속 실패 초기화 시점은 명세에 명시한다.

**판정:** 복구 조건·시간의 역할과 선행 검증 절차는 보완했다. 수치 확정·제품 복구 구현·실장비 측정·정확도 재인수는 미완료다. 미확정 숫자는 차후 확인사항으로 유지하며 전체 계획을 최종 통과로 표시하지 않는다.



### ADS1115 실장비 착수·인수 조건

확인사항 §1에 실제 ADS1115 보드·3.3V 전원·PGA ±4.096V·ADDR-GND(0x48)·가변저항 0~3.3V/A0 배선을 기록했다. [TI ADS1115 제품/데이터시트](https://www.ti.com/product/ADS1115)와 실제 측정을 대조하여 아날로그 입력 제한, I2C pull-up, 변환 완료 판단을 검증한다. PGA 측정 범위를 입력 핀에 가해도 되는 전압 범위로 동일시하지 않는다. 가상 30~42V는 매핑 결과이지 ADC에 직접 인가할 전압이 아니다.

1. 전원·접지·입력/신호 전압·ADDR/실제 버스·배선과 측정 장비를 확인하고 기록한다. 주소가 보이는 것만으로 변환 성공이라 하지 않는다.
2. 승인한 설정으로 새 변환 완료와 원시 signed 값·스케일을 확인한다. 독립 전압 계측과 원시값/변환값을 대조하고 허용 오차는 장비/데이터시트 근거 후 정한다.
3. 원시 ADC→입력 전압→가상 팩 전압→EKF 내부 단셀 변환이 각각 한 번인지 확인한다. ADC 오류·변환 미완료·범위 초과를 clamp로 정상화하지 않는다.
4. 초기/오류/회복/정상 상태와 새 유효 변환 3회를 검증한다. 같은 변환값의 재전송을 3번으로 세지 않는다. 물리 오류 주입은 전압 제한을 넘기는 대신 지원되는 단절/Mock 경로를 구분해 계획한다.
5. 실제 획득·계산·송신·화면 전달 시각과 설정/버전을 기록한다. 취득 주기·CAN 주기·복구 지연·정확도는 별도 결과다. S-7의 합성 SOC 정확도 결과를 실제 ADC 정확도 결과로 표시하지 않는다.

현재 장비와 초기 설정은 확인됐지만 독립 계측 허용치·실제 시험은 미확정/미실행이며 공식 byte 7 목표 구현과 시험 전환도 별도 선행 과제다.



### S-10=A 연결 복구 후 현재 위험 상태 인계

READY 완료 후 현재 위험 상태를 한 번 인증 전달하고 연결 대기 중 전이 이력은 ECU 진단 자료에 남긴다. 과거 전이를 현재 사건으로 재전송하지 않는다. 로컬 판단·센서 오류 중 상태 유지·기존 Fail-safe 전이 규칙은 유지한다. 실제 신규 전이와 동기화가 경합해 오래된 상태를 마지막에 보내지 않도록 검증한다.

0x101은 전이 시점 필드와 사유를 갖기 때문에 초기 NORMAL·사유 부재·동기화 구분을 임의 값으로 인코딩하지 않는다. [세션 설계안 §14](../../../docs/development/security/CAN_세션인증_설계안.md#14-s-10a-반영--현재-위험-상태-동기화)의 계약 영향·유실/중복/경합 검토 후 양측 구현을 전환한다. 공식 ICD와 실제 소스는 아직 변경하지 않았다.



### S-11=A·S-12=A 상태 송신·수신 확인 과제

현재 상태 전용 원본/인증 쌍을 사용하고 IVI의 인증된 수신 확인을 받는 방향으로 구현 과제를 정리한다. 선택 후보는 [세션 설계안](../../../docs/development/security/CAN_세션인증_설계안.md) §15~16의 0x104/0x105와 별도 receipt다. 정식 계약 적용 전 후보 검증이 선행되며 기존 0x101/103의 전이 의미를 예약 바이트로 변경하지 않는다.

동기화 pending을 세션·ID·counter·payload와 연결하고 수신 확인 검증 후에만 완료 처리한다. READY·송신 함수 성공·BMS 주기 송신으로 동기화 완료를 대신하지 않는다. 상태 변화 경합·확인 유실·재시도 소진·재부팅·전역 counter를 결합한 시험을 만든다. 단계/전체 상한은 미확정이다. 상태 미확인 중 일반 BMS 송신은 S-13=A에 따라 대기하며 아래 송신 재개 조건을 따른다.



### S-13=A·S-14=A 송신 재개 조건

연결 복구 시 READY 후에도 최신 현재 상태의 인증 receipt 확인까지 일반 BMS 송신을 대기한다. 로컬 계산·위험 판단은 계속한다. 대기 중 상태가 바뀌면 최신 건을 새 counter로 보내고 이전 receipt는 송신 게이트를 열지 못하게 한다. payload가 다시 같은 값이 되어도 내부 세대/메시지 식별로 이전 확인과 구분한다.

상태 변경·receipt 검증·송신 허용을 일관된 소유 경계에서 처리하고 전체 기한/재시도 예산을 상태 변경으로 연장하지 않는다. 상세 기대값은 [세션 설계안](../../../docs/development/security/CAN_세션인증_설계안.md) §18이다. 현재는 후보 정책 반영이며 실제 게이트·시험 구현과 수치 확정은 남아 있다.



### S-15=A·S-16=A 이후 송신·확인 과제

[세션 설계안](../../../docs/development/security/CAN_세션인증_설계안.md) §23의 선택과 영향표를 따른다. IVI의 제한된 인증 데이터 정렬을 고려하더라도 ECU는 세션 전역 counter 발급과 송신 순서를 직렬화한다. 최신 상태의 receipt까지 일반 BMS 송신을 대기하며, 큐 입장이나 READY만으로 적용 완료를 간주하지 않는다.

receipt는 현재 후보 조각 형식을 유지하고 조립 실패/만료 후 제한 재개·재시도한다. 상태 변경이나 구확인으로 전체 기한을 연장하지 않는다. 반복 조각 혼합은 실패/재연결 조건으로 시험한다. 송신 성공을 IVI 적용 성공으로 대신하지 않는다. 운영 상수·포화 정책·캐시/세션 전환은 상세 확정 후 구현하며 2 tick/8건 같은 시험값을 기본 설정으로 복사하지 않는다.



### S-17=A·S-18=A 이후 수신 실패 대응

IVI는 위험 메시지용 공간을 예약하고 예약 구역 포화 또는 같은 counter의 인증 상충이면 수신 세션 실패로 전환한다. ECU는 이를 정상 수신/상태 적용으로 추정하지 않으며 제한 재교환·최신 상태 확인을 수행한다. 로컬 계산/위험 판단은 계속하고 전역 counter를 재사용하지 않는다. [세션 설계안](../../../docs/development/security/CAN_세션인증_설계안.md) §25의 모형은 후보 검증이며 실제 운영 수치는 후속 확정하며 구세션 송신 종료는 S-19=A에 따라 새 CONFIRM 인증 성공 시점이다.

### 합성 정확도 조건 — S-21=A 반영

S-7의 NASA 재생/합성 SOC/ADS1115 통합 분리는 유지한다. TC-BMS-002는 1시간·0.1초·36,000 update, 참 SOC는 제품 추정 출력을 읽지 않는 생성기로 계산하고 두 추정기에 같은 관측·초기 조건을 준다. SOC-2=A로 실제 코드에 목표 3차 OCV를 적용했지만 실행 검증은 미완료다. 실행할 소스 해시와 모델·설정을 기록하고 과거 선형 구현 결과와 혼용하지 않는다.

사용자 S-21=A로 아래 고정 합성 조건과 합격 적용 범위를 선택했다. 모두 시험 설정이며 실제 셀/센서 측정값이 아니다. CSV 생성·제품 추정기 실행은 후속 구현 과제다.

| 항목 | 선택한 조건과 근거/한계 |
|---|---|
| 참 상태 | 가상 용량 50Ah·초기 SOC 80%·정전류 -2A·1시간. 기존 공식 단위 시험 조건을 시간 확장; 이상적 종료 SOC 76%는 단위식의 계산값 |
| 전압 생성 | SDD-ECU의 목표 3차 OCV와 가상 10직렬을 참 SOC에 적용. 같은 가상 모델의 소프트웨어 정합 시험이며 독립 실물 셀 유효성 증거 아님 |
| 무오차 대조군 | 전류/전압 오차 0, 참 용량·초기값 일치. 값·단위·시각 정합을 검사하고 EKF가 오차 0인 적분보다 엄격히 좋아야 한다고 요구하지 않음 |
| 필수 주 비교 2개 | 전류 관측 바이어스 각각 +0.1A/-0.1A, 전압 오차 0. 같은 관측을 양 추정기에 제공, 두 조건 각각 기존 엄격한 EKF RMSE < 적분 RMSE 판정 |
| 민감도 분석 4개 | 전류 바이어스 ±0.1A와 단셀 전압 바이어스 ±0.01V의 네 조합. 실패/역전 포함 모두 보고, 실제 센서 오차 범위라는 주장은 금지 |
| 재현성 | 결정적 고정 입력으로 seed 불필요. 생성기·추정기·조건 manifest/hash·샘플 수/단위 고정, 실행 후 유리한 조건만 선택 금지 |

S-21=A에 따라 주 비교 2개 각각을 필수 엄격 비교 대상으로 하고 민감도 4개는 불리한 결과까지 한계 분석으로 보고한다. 무오차 대조군은 단위·시각·참 상태 정합을 검사한다. 어떤 선택도 실제 실행 전 통과를 보장하지 않는다. 목표 OCV 계수의 실측 피팅 원자료·독립 검증 근거는 현재 확인되지 않았으므로 가상 모델이라고 명시하고 독립 셀 검증 증거로 사용하지 않는다. 공식 TEST_PLAN의 TC-BMS-002 추가 조건을 따른다.


### S-19=A·S-20=A 실행 연결

새 CONFIRM 인증 성공 시 구세션 송신·미전송 큐를 닫고 최신 상태 receipt 후 새 BMS를 연다. 실패 시 구키/counter로 되돌리지 않는다. 사유 없음은 HAL에서 0으로 표현하는 목표이며 기존 0x101에 reason=0을 보내지 않는다. 세션 설계안 §26의 경계 시험과 상세 계약 전환을 완료한 뒤 제품에 적용한다.

### S-22=A와 운영 수치 근거

일반 BMS 구역만 차면 신규 BMS를 거부·진단하고 기존 대기 건과 위험 예약 공간을 보존한다. 해당 포화만으로 즉시 재연결하지 않으며 지속 누락의 counter/timeout 처리는 기존 정책을 따른다. 위험 구역 포화·인증 상충은 계속 세션 실패다. 상세 인수와 담당별 수치 측정·승인 기준은 [세션 설계안](../../../docs/development/security/CAN_세션인증_설계안.md) §28을 따른다. 실제 UI 시각·커널 송신 경계·장비 부하는 후속 검증이다.


<a id="ecu-bms-01"></a>
### ECU-BMS-01 — Plan 승계 과제

원문: [ECU.md](../../_archive/plan_20260908/ECU.md.txt)의 ECU-BMS-01. 실행 상태는 해당 역할의 진행 표·공동 인수 기록을 사용한다. 이 병합은 과제 실행 완료가 아니다.

선행·착수: [ECU-CAN-01](M2_CAN_CDD_Publisher.md#ecu-can-01)

보존한 수행·인수 조건: SOC 모델·부호·초기조건·장기 비교, SOH와 main 갱신, Fail-safe 전이/복귀/수동 리셋·인증 이벤트·주기를 공식 TC로 검증한다. 정상/경계/전이/복귀 데이터를 IVI-APP-01에 인계한다.

현재 기준 적용: SOH 누적 방전 중심 설명은 SRS FR-BMS-003의 용량비/별도 누적으로 대체; S-21/SOC 결정 유지. 본문의 공식 FR/TC·승인 정책·실패 대응을 함께 적용한다.


<a id="ecu-wdg-01"></a>
### ECU-WDG-01 — Plan 승계 과제

원문: [ECU.md](../../_archive/plan_20260908/ECU.md.txt)의 ECU-WDG-01. 실행 상태는 해당 역할의 진행 표·공동 인수 기록을 사용한다. 이 병합은 과제 실행 완료가 아니다.

선행·착수: [ECU-CAN-01](M2_CAN_CDD_Publisher.md#ecu-can-01), [ECU-BMS-01](M3_EKF_Failsafe_SecOC.md#ecu-bms-01)

보존한 수행·인수 조건: BMS와 CAN 수신 각각 지연·종료·재시작·최종 복구 실패를 주입한다. 로그만으로 복구 성공 처리하지 않고 IVI 중단/재개 관측과 연결한다. snapshot·회수 실패 처리는 본문의 Q/R 승인 정책을 따른다.

현재 기준 적용: 후속 승인된 복구 정책을 우선; 임의 자동 프로세스 재시작 금지. 본문의 공식 FR/TC·승인 정책·실패 대응을 함께 적용한다.


<a id="ecu-sec-01"></a>
### ECU-SEC-01 — Plan 승계 과제

원문: [ECU.md](../../_archive/plan_20260908/ECU.md.txt)의 ECU-SEC-01. 실행 상태는 해당 역할의 진행 표·공동 인수 기록을 사용한다. 이 병합은 과제 실행 완료가 아니다.

선행·착수: [ECU-CAN-01](M2_CAN_CDD_Publisher.md#ecu-can-01), [ECU-BMS-01](M3_EKF_Failsafe_SecOC.md#ecu-bms-01)

보존한 수행·인수 조건: 더미 키로 Python/C++ 정상·변조·Replay·초기값·wrap 교차 벡터와 거부 결과를 대조한다. BMS/Fail-safe 인증 쌍 실송신·키 로드 실패·비활성 시험을 구분해 IVI-SEC-01로 인계한다.

현재 기준 적용: 현행 ICD와 승인 목표·세션 후보를 구분; 미승인 상세 전환 금지. 본문의 공식 FR/TC·승인 정책·실패 대응을 함께 적용한다.


<a id="security-adoption"></a>
## 보안 차용 보강 — 입력 출처·보안 시작·안전 경계

### 목적·선행조건

ECU-BMS-01·ECU-WDG-01·ECU-SEC-01에 N01/N02를 연결한다. [공동 기준](../common/00_협업_규약.md#security-adoption)과 현행 ICD·승인된 센서 품질·세션 상세 미결 상태를 확인한다. 이번 보강은 예정 수행·인수 조건이며 현재 시험 통과를 의미하지 않는다.

### 수행 절차

1. 일반 실행과 서비스 시작·재시작에서 실제 송신 보안 설정과 키 로딩 상태를 확인한다. 기존 `--secoc on` 배포 설정을 우선 대조하며 main의 기본값 변경은 별도 실제 코드 검토 후 판단한다. C0 실험 예외는 구성·환경을 manifest에 남기고 일반 실행으로 복사하지 않는다.
2. 입력 profile/source_mode, 입력 파일 hash·seed·모델 설정과 run 식별을 연결한다. 정상 입력·추정 상태·센서 품질·IDS 판정의 출처를 구분한다. 점진적 drift·jump·freeze·신호 정합성은 보완 사례로 M4에 인계하며 기존 SOC/SOH 공식 시험과 별도 기록한다.
3. 키 누락·길이/내용 오류·권한 실패에서 인증이 필요한 일반 경로의 실패 상태를 기록한다. 실제 키는 출력하지 않는다. 송신/수신 모두 확인해야 보안 ON 인수가 성립한다.
4. ECU 로컬 태스크 정지, CAN 송신 중단, 센서 고장, IDS 경보를 다른 사건으로 유지한다. Watchdog callback은 짧게 유지하고 실제 복구 문맥·회수 결과·정상 작업 재개로 성공을 판단한다. 기존 reason·복구 정책을 새로 선택하지 않는다.
5. Q1 공격기에는 정상 sender의 시험용 제어 경계와 중단/재개 증거를 제공한다. 실제 안전 계산 중단을 A5 송신 중단과 동일 시험으로 취급하지 않는다.

### 검증

TC-SEC-001~004의 벡터와 키 오류·재시작 증거를 IVI-SEC-01에 인계한다. counter 실패 후 정상 수락·교차 ID·wrap 및 현행 재부팅 한계를 구분한다. N02 보완 입력은 기대 변화·센서 고장/공격 라벨·정상 profile별 오탐·제어 루프 기능 보존으로 검증하며 임계·횟수를 추정으로 확정하지 않는다.

### 실패 대응

보안 설정이 OFF이거나 키 로딩이 실패한 일반 실행을 정상 운용으로 인수하지 않는다. 센서 이상·보안 이벤트 때문에 기존 안전 판단을 임의 해제하지 않는다. 세션 미확정 재부팅 보안은 기존 관문에 남기고 단위 시험 성공으로 닫지 않는다.

### 완료 체크

- [ ] 일반 시작/재시작 및 C0 예외의 양측 보안 상태 인계
- [ ] profile·입력·추정·품질·run 출처와 N02 보완 사례 인계
- [ ] 인증·센서·태스크·통신 사건별 실패/복구 증거와 기존 공식 TC 결과 구분
