# IVI M5 — 성능 측정·최적화, UI 개선

> **2026-09-09 보안 방식 선별 반영:** 기존 단계·과제에 [하단 추가 수행·인수 조건](#security-adoption)을 함께 적용한다. 구현·시험 완료 기록은 아니다.

> **예시 상태**: 코드·명령은 별도 검증 표시가 없으면 작성 골격·예정 절차다. 실행 전 생성할 파일·의존성·플랫폼을 확인한다. [공동 규약](../common/00_협업_규약.md)의 문서·예시 사용 규칙을 따른다.

> 상위 계획: [IVI.md](../../IVI.md) · 실험 결합: [02_통합시험](../common/02_통합시험.md)
> 원본: `_archive/IVI.md` M5, `_archive/IVI_최종_실행계획서.md` §9

---


<a id="security-integration"></a>
## 현행 과제에 병합한 보안 수행·인수 조건 — Q2 구간 계측과 운영 파일럿

이 절은 2026-09-09 보안 상세 계획을 기존 단계에 반영한 실행 조건이다. 초기 보안 보강 절과 함께 적용하며 제품 실행 완료 기록은 아니다. 상세 규칙은 [메시지·상태 규약](../../../docs/development/security/인증이벤트_메시지_상태규약.md)과 [송신·큐·실패 정책](../../../docs/development/security/인증이벤트_메시지_상태규약.md#planning-final)을 참조한다.

**선행 조건:** 기존 공식 측정 구간과 IVI M3/M4의 이벤트·배포 버전을 인수한다. [M5 공동 인계 순서](../common/02_통합시험.md#m5-handoff-order)에 따라 ECU와 run/trial·입력·구성을 사전 합의한 뒤 계측을 준비한다. ECU M5 결과나 전체 완료를 기다리지 않으며 공동 실행 후 수신/UI 결과를 인계한다.

**수행:** Node B 발생→offer의 source age, Node A 수신→소비의 consumer age와 큐/직렬화/write 지연을 각각 계측한다. 노드 간 monotonic 값을 직접 빼지 않고 시계 오차 근거가 없는 전체 지연은 미산출로 둔다.

**실패 대응·인계:** 메시지 크기·큐 bytes/건수·status 빈도·read/write/재연결 기한을 메모리/지연 예산과 정상/느린 peer 파일럿으로 확정한다. 기존 BMS/UI 성능 인수와 계측 오버헤드를 함께 확인한다. 불가능한 예산은 보고하며 기준을 임의 완화하지 않는다.

**완료 확인:**

- [ ] 구간별 시각·단위·drop·CPU/RSS·확정 설정과 미계측 한계를 공동/M7에 인계했다.
- [ ] 기존 공식 시험 결과와 추가 보조 시나리오의 실제 증거·미검증 사유를 구분했다.


## 1. 목적과 범위

end-to-end 지연을 **정의된 지점에서** 측정하고 병목을 줄인다. 대시보드 UI/UX를 다듬고 IVI 담당 ADR을 최종화한다.

| 항목 | 값 |
|---|---|
| 연결 시험 | TC-PERF-001, TC-PERF-002, TC-IVI-008 |
| 산출물 | 지연 측정 도구·결과 CSV, 최적화 적용, UI 개선, ADR-004/006/007/010 |
| 태그 | `v0.5.0` |
| **일정 조율** | ECU Ablation 실행 시간과 측정 시간을 분리한다 ([01_연계_의존성](../common/01_연계_의존성.md)) |

---

## 2. 선행조건과 현재 구현 상태

**선행조건**: [M4](M4_대시보드_Alert_배포.md) 완료 — 대시보드 전체, 배포, IT-001~005.

| 대상 | 상태 |
|---|---|
| 지연 측정 도구 | **미구현**. 과거 `measure_latency.py` 자리표시자는 0바이트였고 정리 시 제거됨 |
| `latency_results.csv` | 미생성 |
| ADR-004/006/007/010 | 초안 상태 ([M1](M1_AOSP_Docker_CI.md), [M2](M2_HALMock_PlanAB.md)) |

### 해소한 결함 — **측정 지표가 서로 다른 것을 같은 이름으로 부르고 있었다**

세대A의 `analyze_latency.py`는 `candump -t d`의 **프레임 간 도착 간격(delta)** 을 계산한 뒤 그것을 "e2e Latency"로 출력하고 `TC-PERF-001 avg <= 50ms`를 판정한다. 그런데 프레임 간 간격은 **송신 주기**이고, 이는 TC-PERF-002(100ms ±10ms)의 지표다.

| 지표 | 정의 | 대응 TC | 기대값 |
|---|---|---|---|
| **송신 주기** | 연속된 `0x100` 프레임의 도착 시각 차 | **TC-PERF-002** | 100ms ±10ms |
| **e2e 지연** | Node B CAN 수신 → 화면 반영 (T1→T4) | **TC-PERF-001** | 평균 ≤50ms, 최대 ≤100ms |

세대A 스크립트를 그대로 쓰면 100ms 부근 값이 나오고, 이는 TC-PERF-001 기준(≤50ms)에 **항상 FAIL로 보이거나**, 반대로 주기가 짧을 때 **통과한 것처럼 잘못 보인다.** 두 지표는 값의 크기도 의미도 다르다.

> **결정**: 두 지표를 분리해 각각 측정한다. 3.1이 TC-PERF-002(주기), 3.2가 TC-PERF-001(e2e 지연)이다. 주기 측정값을 e2e 지연으로 보고하지 않는다.
>
> 측정 구간의 정본은 **상위 요구인 SRS NFR-PERF-001**이다. TEST_PLAN v1.4에서 측정 방법을 여기에 맞춰 T1→T4로 통일했다. 공동 정의표는 [02_통합시험](../common/02_통합시험.md) 6.1.

### 그 외 해소한 충돌

| 항목 | 세대A | 세대B | 채택 |
|---|---|---|---|
| ECU 실행 인자 | `--secoc=on --ids=on` | 동일 | **`--secoc on`** (실제 `main.cpp`) |
| 백분위 계산 | `sorted(x)[int(n*0.95)]` | `statistics.quantiles(n=100)[94]` | **§3.2의 선형 보간 정의**로 통일하고 경계 표본 시험 |
| 측정 입력 | candump 텍스트 파싱 | 사전 준비된 `latency_raw.csv` | **둘 다** — 3.1은 candump, 3.2는 타임스탬프 쌍 |
| candump 시각 옵션 | `-t d` (델타) | — | **`-t a` (절대)** — 델타는 ID 무관 직전 프레임 기준이라 `0x102`가 끼면 주기가 아니다 |
| 합격 판정 | 표준편차만 / 유효성 검사 없음 | — | **종합 판정** — 평균·편차·범위 비율, 음수·최소 표본 거부 |

---

## 3. 수행 절차

### 3.1 TC-PERF-002 — 주기 수집·분석 과제

수치·시계·원시 데이터의 정본은 [공동 통합시험](../common/02_통합시험.md) §6이다. 아래 도구는 미구현 산출물이며 기존 seq 전용 CSV·candump 파서 골격을 공식 분석기로 사용하지 않는다.

1. 대상 캡처 어댑터를 작성해 실제 candump/SocketCAN 출력 fixture를 정규화한다. 절대 또는 단조 수신 시각을 사용하며 전체 프레임 delta를 대상 ID 주기로 쓰지 않는다.
2. `run_id,boot_id,sample_id,can_id,timestamp_ns` CSV와 manifest를 만든다. manifest는 수집 환경·도구 버전·시계·구간·대상 ID·총행수·드롭/오류·원본 hash를 포함한다.
3. manifest와 실제 행을 대조한 뒤 run/boot별로 0x100만 선택한다. 원래 시간 순서를 검사하고, 정렬로 역행을 숨기거나 다른 부팅 사이의 차이를 계산하지 않는다.
4. 101개 이상 프레임에서 100개 이상 간격을 계산한다. 각 간격 90~110ms를 모두 충족해야 PASS다. 평균·표준편차·최소·최대·이탈 수를 함께 출력한다. 소수의 이탈을 95% 기준으로 허용하지 않는다.
5. 캡처 누락·중복·손상·시계 불명·표본 부족은 INVALID, 유효한 범위 이탈은 FAIL이다. 목표를 낮추는 옵션은 공식 판정에 허용하지 않는다.

예정 CLI: `analyze_period.py --input period_raw.csv --manifest capture_manifest.json`. 실기기 수집 명령은 Android 환경과 도구 지원 확인 후 확정한다. Node B 수신 간격은 버스 지연을 포함하므로 ECU 송신 요청의 진단 시각과 구분한다.

### 3.2 TC-PERF-001 / TC-IVI-008 — 지연 분석 과제

입력은 `run_id,boot_id,sample_id,stage,timestamp_ns` CSV와 manifest다. 같은 sample의 T1~T4를 내부 계측 문맥으로 연결하고 CAN payload나 HIDL에 측정용 필드를 임의 추가하지 않는다.

| 검사 | 판정·산출물 |
|---|---|
| 공통 식별자 | run/boot/sample 및 stage 유일성, 전체 기대 표본과 대조 |
| 시각 | 정수 ns·동일 Node B 단조 시계, 단계 역행·부팅 혼합 금지 |
| T1→T4 | 1,000개 이상, 평균 ≤50ms AND 최대 ≤100ms |
| T2→T3 | 100개 이상, 평균 ≤20ms AND P99 ≤50ms |
| P99 계산 | 오름차순 n개에서 h=(n-1)×0.99, 인접 두 값 선형 보간; 알고리즘을 결과에 명시 |
| 손실 | 미렌더·coalescing·수집 누락·중복을 각각 계수; 조용히 제외하고 PASS 금지 |
| 종료 상태 | PASS=0, FAIL=1, INVALID/입력 오류=2. NOT_RUN은 실행 전 상태 |

예정 CLI: `analyze_latency.py --input latency_raw.csv --manifest capture_manifest.json --stages t1,t4`. T2→T3도 같은 입력과 식별자를 사용한다. 정식 기준·최소 표본은 옵션으로 낮추지 않는다. 진단 구간은 공식 TC와 구분해 출력한다.

**회귀 인수:** 정상·경계·최소 표본, 최소값 하향 요청, 음수·빈 입력·잘못된 stage·NaN·중복·누락·부팅 혼합, 95% 정상 주기+5% 이탈, 대상 ID 혼합, manifest 행수 불일치, 수집 손상. 현재 문서 검사는 미래 분석기의 실행 시험을 대신하지 않는다.

### 3.3 구간별 병목 분석

| 구간 | 목표 | 측정 |
|---|---|---|
| T1 − T0: CAN 전송 | — | 두 노드 시계 오차에 묻히는 구간 |
| T2 − T1: HAL 수신 → 콜백 | ≤5ms | HAL 내부 `steady_clock` |
| T3 − T2: Binder IPC → StateFlow | ≤15ms | Service·ViewModel 로그 |
| T4 − T3: recomposition → 렌더 | ≤20ms | Compose 프레임 콜백 |

HAL 계측은 [IVI M3](M3_HAL_Service_대시보드.md) §3.2의 pending→인증→commit→callback 흐름에 삽입한다. 수신 직후 직접 파싱·콜백하던 예시는 제거한다. T1은 원본 수신, T2는 실제 Service 발행이며 인증 대기·스레드 전환을 포함한다. 함수 실행 시간은 별도 진단값으로만 기록한다.

계측 로그는 bounded buffer에 모으고 수집 누락을 계수한다. 버퍼 부족이나 과도한 로그 지연을 숨기지 않는다. 측정 mode와 실제 배포 mode의 차이를 결과에 남긴다.

### 3.4 최적화

| 병목 | 조치 |
|---|---|
| CAN 수신 스레드 지연 | blocking read + 전용 스레드 유지. 폴링으로 바꾸지 않는다 |
| 프레임별 동적 할당 | 파서에서 힙 할당 제거, 스택·고정 배열 사용 |
| Binder 갱신 과다 | queue·coalescing을 계측한다. 표본을 생략해 지연 합격시키지 않으며 stale 감시는 유효 수신마다 유지 |
| Compose recomposition 과다 | UI state를 최소 단위로 쪼갠다. 큰 data class 하나가 전부를 다시 그리게 하지 않는다 |
| 로그 과다 | release/demo 빌드에서 debug 로그 축소 |
| CPU governor | performance 고정 |

**CAN 수신 스레드 우선순위** (권한이 있을 때만):

```cpp
void VehicleHalImpl::start() {
    running_ = true;
    rx_thread_ = std::thread(&VehicleHalImpl::rxLoop, this);

    struct sched_param param{};
    param.sched_priority = 50;      // SCHED_FIFO 1~99
    if (pthread_setschedparam(rx_thread_.native_handle(), SCHED_FIFO, &param) != 0) {
        LOG_WARN("RT priority 설정 실패 — 일반 우선순위로 계속");
    }
}
```

> `SCHED_FIFO`는 root 또는 `CAP_SYS_NICE`가 필요하다. 실패해도 동작은 계속돼야 한다. 우선순위를 너무 높이면 다른 스레드를 굶길 수 있으므로 50 이상으로 올리지 않는다.

**소켓 수신 버퍼**:

```bash
sudo sysctl -w net.core.rmem_max=2097152
sudo sysctl -w net.core.rmem_default=1048576
# 영구 적용
echo "net.core.rmem_max=2097152"     | sudo tee -a /etc/sysctl.conf
echo "net.core.rmem_default=1048576" | sudo tee -a /etc/sysctl.conf
```

**`read()` 타임아웃 예시** — 종료 대기를 제한한다. 즉시 종료는 별도 wake-up 경로로 설계·검증한다:

```cpp
struct timeval tv{};
tv.tv_sec = 1;
tv.tv_usec = 0;
setsockopt(sock_, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
```

**CPU governor**:

```bash
sudo apt install -y cpufrequtils
for cpu in /sys/devices/system/cpu/cpu[0-3]; do
    echo performance | sudo tee "$cpu/cpufreq/scaling_governor"
done
```

- [ ] 최적화 **전후 수치를 모두 기록한다.** "개선했다"가 아니라 "x ms → y ms"로 적는다
- [ ] 최적화가 효과 없으면 그것도 기록한다. 되돌릴 근거가 된다

### 3.5 SocGauge — 전체 즉시 갱신, I-4-1=B

사용자는 숫자·게이지·경고 모두 최신 유효값으로 즉시 갱신하도록 선택했다. 값 보간 애니메이션을 넣지 않는다. T4는 해당 값의 실제 화면 그리기 완료이며 함수 호출·애니메이션 시작으로 대신하지 않는다.

사용자가 요청한 편안한 표시는 갱신 지연 없이 배치를 안정시키는 방식으로 보완한다. 숫자 영역 폭·정렬·단위 위치·표시 자릿수 형식을 일정하게 유지하고, 숫자 폭이 같은 글꼴을 대상 환경에서 검토한다. 경고 영역이 나타나도 핵심 값의 위치가 불필요하게 밀리지 않도록 한다. SOC 값·경고 판정에 이동평균·debounce·새 히스테리시스를 임의 추가하지 않는다.

- [ ] TC-IVI-005: 색상 경계는 최신 유효값 기준으로 함수·실제 화면에서 시험한다.
- [ ] 9→10, 99→100, 음수/양수 전류와 단위·소수점 변경에서 숫자 영역과 주변 레이아웃이 흔들리지 않는지 확인한다.
- [ ] 글자 확대·대상 화면 크기·빠른 변화에서 잘림/겹침·반복 깜빡임을 점검한다. 동일 값에서 불필요한 화면 재등장은 피하되 유효 수신 감시·표본 계측은 유지한다.
- [ ] TC-PERF-001: 실제 숫자·게이지 반영과 오류/위험 표시까지 계측한다. 측정용 빌드만 별도로 효과를 꺼서 통과시키지 않는다.

### 3.6 AlertBanner 경보 수명

같은 attackType만 effect key로 사용하던 예시는 제거한다. 같은 유형의 새로운 경보도 별도 이벤트로 식별하고 갱신해야 한다. 내부 이벤트 식별자는 HAL/CAN 계약 변경 없이 생성·전달할 수 있는 계층을 설계한다.

현재 ICD에는 공격 종료를 인증하는 별도 메시지가 없으므로 표시 타이머 만료를 '공격 종료'로 해석하지 않는다. 사용자 I-4-2=A에 따라 사용자 확인 전까지 유지한다. 확인은 해당 경보를 읽었다는 뜻이며 공격 종료나 보안 정상 판정이 아니다.

- [ ] TC-IVI-006의 공식 배너 문자열과 attackDetected 표시 조건을 유지한다.
- [ ] 동일 유형 연속 경보, 다른 유형 교체, 과거 타이머가 새 경보를 지우는 경쟁, 앱 재기동, 통신 단절·인증 오류 동시 발생을 시험한다.
- [ ] 타이머 자동 숨김을 사용하지 않는다. 확인 후 새 경보는 같은 유형이어도 다시 표시하고 과거 이벤트의 확인 동작이 더 최신 경보를 지우지 못하게 한다.
- [ ] 센서 오류·stale·CRITICAL/SHUTDOWN은 IDS 배너 확인으로 해제하지 않는다. M3 상태 모델·M4 화면·M7 안정성 시험에 같은 규칙을 적용한다.

### 3.7 ADR 최종화

| ADR | 주제 | 최종화 시 담을 근거 |
|---|---|---|
| ADR-004 | HIDL vs AIDL | 실제 구현 경험, Android 13 제약 |
| ADR-006 | QEMU user-mode 시험 | CI Stage 3 실행 시간, 네이티브 대비 배수 |
| ADR-007 | Docker ARM64 크로스컴파일 | 빌드 시간, CI/로컬 일치성 |
| ADR-010 | Plan B 전환 (해당 시) | [M2](M2_HALMock_PlanAB.md)의 실제 실패 로그 |

- [ ] 각 ADR에 **측정한 수치**를 넣는다. "빠르다/편하다"가 아니라 실제 값
- [ ] Plan A를 유지했다면 ADR-010은 작성하지 않는다. 빈 ADR을 만들지 않는다

### 3.8 ECU와 측정 시간 분리

ECU의 Ablation 실험([ECU M5](../ecu/M5_Ablation.md))은 버스에 공격 트래픽을 흘린다. 그 시간대에 지연을 측정하면 값이 오염된다.

- [ ] 측정 시간대를 ECU 담당자와 미리 합의한다
- [ ] 측정 중에는 공격 스크립트를 실행하지 않는다
- [ ] 측정 로그에 시작·종료 시각을 남겨 사후 대조가 가능하게 한다

---

## 4. 검증 명령과 합격 기준

```bash
# 주기 (TC-PERF-002) — 절대 시각으로 캡처한다
# 대상 도구로 캡처 후 §3.1 어댑터를 통해 period_raw.csv·manifest 생성 (미구현)
python3 ivi_platform/scripts/analyze_period.py --input period_raw.csv --manifest capture_manifest.json

# e2e 지연 (TC-PERF-001) — CAN 수신 -> 화면 반영
python3 ivi_platform/scripts/analyze_latency.py --input latency_raw.csv --manifest capture_manifest.json --stages t1,t4

# Service -> StateFlow (TC-IVI-008)
python3 ivi_platform/scripts/analyze_latency.py --input latency_raw.csv --manifest capture_manifest.json --stages t2,t3

# (진단) 구간별 병목 — 공식 판정에는 쓰지 않는다
python3 ivi_platform/scripts/analyze_latency.py --input latency_raw.csv --manifest capture_manifest.json --stages t1,t2
python3 ivi_platform/scripts/analyze_latency.py --input latency_raw.csv --manifest capture_manifest.json --stages t3,t4

cd ivi_platform/app && ./gradlew test
```

| TC | 측정 구간 | 합격 기준 | 최소 표본 |
|---|---|---|---|
| TC-PERF-001 | T1 → T4 | 평균 ≤50ms, 최대 ≤100ms | 1,000 |
| TC-PERF-002 | `0x100` 연속 수신 차 | 모든 간격 90~110ms, 평균·표준편차·최소·최대 병기 | 100 |
| TC-IVI-008 | T2 → T3 | 평균 ≤20ms **AND** P99 ≤50ms | 100 |

| 항목 | 기준 |
|---|---|
| 유효성 | 음수·짝 불완전·중복·캡처 손상 0건; 있으면 INVALID |
| 시계 | T1~T4는 Node B 동일 단조 시계; 노드 간 진단은 오차 상한 필수 |
| 기록 | 결과 CSV에 TC 이름과 측정 구간 포함 |
| UI | 숫자·게이지 즉시 갱신, 배치 안정성, IDS 경보 사용자 확인 해제 |
| ADR | 004/006/007(+010) 최종화, 수치 근거 포함 |
| 태그 | `v0.5.0` |

---

## 5. 실패 시 대응과 우회

**e2e 지연이 목표 초과**
1. 구간별 수치를 먼저 본다. 어느 구간이 큰지 모르면 최적화가 추측이 된다
2. 로그 출력이 측정 자체를 늦추고 있지 않은지 확인한다
3. 3.4의 순서대로 적용하고 **매번 재측정**한다
4. 그래도 미달이면 **목표를 바꾸지 말고** 미달값과 병목 분석을 기록한다

**두 노드 시계가 안 맞음**
- `chrony`로 동기화한다. 같은 NTP 서버를 쓴다
- 공식 TC-PERF-001은 Node B 단독 T1→T4다. 노드 간 동기가 없어도 동일 단조 시계로 측정한다. T0→T1 진단 측정은 오차 상한을 확보하지 못하면 INVALID로 남긴다.

**표본이 안 모임**
- `0x100`이 실제로 오는지 `candump can0 | grep 100`
- 시퀀스 매칭이 안 되면 `0x102` RollingCounter 추출부를 확인한다
- 100ms 주기면 10분에 약 6,000개다. 1,000개가 안 모이면 수신 자체가 끊기고 있다

**`SCHED_FIFO` 설정 실패**
- 권한 문제다. 실패해도 계속 동작해야 한다(`LOG_WARN` 후 진행)
- 실장비에서 필요하면 `setcap cap_sys_nice+ep`를 검토한다

**화면 반영이 늦거나 불편함**
- 사용자 선택에 따라 값 보간은 사용하지 않는다. 실제 그리기 시각과 데이터 전달 지연을 분리해 진단한다.
- 고정 배치·텍스트 정렬·글꼴과 불필요한 전체 재구성을 점검한다. 합격을 위해 T4 정의를 바꾸지 않는다.

---

## 6. 완료 체크리스트

- [ ] TC-PERF-001과 TC-PERF-002를 **서로 다른 지표로** 분리 측정
- [ ] 측정 지점 T0~T4 정의를 문서에 기록, **공식 TC 구간과 일치** (PERF-001=T1→T4, IVI-008=T2→T3)
- [ ] 주기 캡처를 `candump -t a`로 수행, 대상 ID만 골라 연속 차분 계산
- [ ] 주기 판정이 평균·표준편차·범위 비율을 **모두** 확인
- [ ] 지연 판정이 음수·최소 표본을 거부, TC-IVI-008의 **P99 기준 포함**
- [ ] 두 노드 시계 동기 확인 또는 오차·구간 한계 명시
- [ ] 표본: PERF-001 1,000개 이상, PERF-002·IVI-008 100개 이상
- [ ] 결과 CSV에 TC 이름·측정 구간·유효성 통계 포함
- [ ] 진단값(T0→T1, T1→T2, T3→T4)을 공식 TC 결과로 보고하지 않음
- [ ] 구간별 병목 수치 확보
- [ ] 최적화 전후 수치 기록
- [ ] `SocGauge` 전체 즉시 갱신·배치 안정성·실제 T4 계측 검증
- [ ] `AlertBanner` 공격 유형별 아이콘·색상
- [ ] ADR-004/006/007(+010) 최종화, 수치 근거 포함
- [ ] ECU Ablation과 측정 시간 분리 합의·기록
- [ ] `v0.5.0` 태그 생성


**S-1=A 확정:** 경고 배너·문구를 즉시 완전히 표시하고 장식 효과만 허용한다. 사용자 확인까지 유지하고 신규 경보는 다시 표시한다. 경고 인지/실제 렌더 시점을 장식 효과 시작·종료로 대체하지 않는다. 공식 기준은 SRS FR-IVI-006·SDD-IVI·TEST_PLAN TC-IVI-006의 S 답변 보완을 따른다.


<a id="ivi-meas-01"></a>
### IVI-MEAS-01 — Plan 승계 과제

원문: [IVI.md](../../_archive/plan_20260908/IVI.md.txt)의 IVI-MEAS-01. 실행 상태는 해당 역할의 진행 표·공동 인수 기록을 사용한다. 이 병합은 과제 실행 완료가 아니다.

선행·착수: [IVI-APP-01](M3_HAL_Service_대시보드.md#ivi-app-01), ECU 송신/경보 인계; 물리 측정은 [COM-INT-01](../common/02_통합시험.md#com-int-01) 준비

보존한 수행·인수 조건: collector/어댑터·시각 계산·샘플 매칭을 시험한다. 동일 run/입력 조건으로 수신/UI 결과를 ECU-EXP-01에 인계하며 표본·누락·분포·시계 오차를 기록한다. 공식 TC 측정 구간은 공동 측정 정본을 따른다.

현재 기준 적용: measure_latency.py 후보 대신 현재 M5 CSV/manifest·analyze_* 절차로 대체. 본문의 공식 FR/TC·승인 정책·실패 대응을 함께 적용한다.


<a id="security-adoption"></a>
## 보안 차용 보강 — 구간 계측과 배치 비용 인계

### 목적·선행조건

IVI-MEAS-01에 Q3=A·N07을 연결한다. [공동 측정 기준](../common/02_통합시험.md)의 기존 §6 구간과 TC-PERF-001~003을 유지한다. Q2의 추가 이벤트 전달 지연은 별도 진단 구간이며 기존 0x200 수신 지연을 대체하지 않는다.

### 수행 절차

1. 기존 CSV/manifest와 예정 `analyze_period.py`·`analyze_latency.py`를 확장한다. 원자료의 `measure_latency.py` 후보를 별도 중복 도구로 만들지 않는다.
2. 원본 수신, 인증 처리 시작/완료, 상태 commit, Service 게시, 실제 UI 렌더 사건을 같은 sample 문맥으로 기록한다. 발표자료의 T 번호를 그대로 복사하지 않고 노드·사건 이름·clock을 연결한다. pending 대기·스레드 전환·전처리를 전체 구간에서 제외하지 않는다.
3. Q2의 Node B 사건 생성·송신, Node A 수신 검증·IDS 집계 시각을 수집한다. 노드 간 monotonic을 직접 차감하지 않으며 공통 관찰 시계 또는 동기 방법·오차 근거가 없으면 정확한 전달 지연으로 인수하지 않는다.
4. 모델 크기·hash는 ECU 측에서 받고 양측 CPU·RSS·입력/처리/드롭 수·관찰 시간·실행 모드를 기록한다. frames/s·windows/s·bus load와 순수 MAC 계산 시간을 구분한다. 측정 도구 자체의 추가 부하·버퍼 손실도 공개한다.
5. 기존 실행 데이터에서 P50/P95/P99·run별 분포·미매칭을 산출한다. 부족한 표본으로 분위값이나 최대 지속 처리량을 보장하지 않는다. 보조 지표를 위한 새 대규모 반복은 추가하지 않으며 공식 최소 표본·합격 기준은 유지한다.

### 검증·실패 대응

음수·중복·역순·부팅 혼합·잘못된 stage·행수 불일치·수집 손상·coalescing·미렌더를 검사한다. 공식 PASS에 필요한 계측이 깨졌으면 INVALID로 남기고 원인을 해결한다. 유효한 미탐·지연 초과는 FAIL이다. 실패를 0 지연이나 삭제된 행으로 처리하지 않는다.

### 완료 체크

- [ ] 사건 이름·노드·clock·공식/진단 구간·sample 매칭 검사
- [ ] 기존 증거의 분위값·자원·처리량·드롭·미산출 한계 인계
- [ ] ECU M5/M7이 같은 원수와 manifest로 결과를 재생성할 수 있음
