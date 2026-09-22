# IVI M6 — SDD-IVI, README, CICD_SPEC, Coverage

> **상태(2026-09-22)**: ADR-010의 Qt Plan B 활성화로 이 문서의 Android/AOSP 실행 절차는 현 제출 범위에서 superseded된 역사 자료다. 현재 작업은 [IVI 계획](../../IVI.md)과 [Plan B 전환 계획](../../IVI_PLAN_B_전환계획.md)을 따른다.


## 현재 실행 진입점 — Qt Plan B

이 파일의 이전 M단계 절차·명령·체크리스트는 역사 자료이며 현재 완료 판정에 직접 사용하지 않는다. 현행 작업은 [IVI M1~M8 매핑](../../IVI.md#4-m1m8-마일스톤)과 [Qt P0~P6 실행 계획](../../IVI_PLAN_B_전환계획.md#3-단계별-실행-계획)을 따른다. Qt 관련 과거 대안도 현재 채택 구조와 다를 수 있으므로 D-Bus/Flutter를 추가 요구하지 않는다. 공식 요구·계약·시험은 SRS/ICD/TEST_PLAN이 원본이다.

---


> **예시 상태**: 코드·명령은 별도 검증 표시가 없으면 작성 골격·예정 절차다. 실행 전 생성할 파일·의존성·플랫폼을 확인한다. [공동 규약](../common/00_협업_규약.md)의 문서·예시 사용 규칙을 따른다.

> 상위 계획: [IVI.md](../../IVI.md) · 교차 검토: [03_발표_제출](../common/03_발표_제출.md)
> 원본: `_archive/IVI.md` M6, `_archive/IVI_최종_실행계획서.md` §10

---

## 1. 목적과 범위

IVI 설계 문서와 CI/CD 문서를 최종화하고 프로젝트 README를 완성한다. 커버리지 게이트를 통과시키고 CI 4단계를 전부 녹색으로 만든다.

| 항목 | 값 |
|---|---|
| 연결 시험 | TC-CI-001~006, TC-PERF-003, 전 TC 결과 기록 |
| 산출물 | `docs/SDD-IVI.md`, `README.md`, `docs/CICD_SPEC.md` 최신화, Coverage ≥80% |
| 태그 | `v0.6.0` |

---

## 2. 선행조건과 현재 구현 상태

**선행조건**: [M5](M5_성능_UI개선.md) 완료 — 지연 측정 결과, 최적화, ADR.

| 대상 | 상태 |
|---|---|
| `docs/SDD-IVI.md` | **존재** — 구현에 맞춘 갱신 필요 |
| `docs/CICD_SPEC.md` | **존재** — 4단계 명세. 구현과 대조 필요 |
| `README.md` | **존재** — 현재는 정리 결과 안내 중심. 프로젝트 소개로 확장 |
| `codecov.yml` | **없음** |

> **README 주의**: 루트 `README.md`는 이미 있고 현재 구현 상태(2026-09-05 기준 IVI 미구현)를 정확히 적고 있다. **덮어쓰지 말고 확장한다.** "IVI·CI·ARM64 Docker 환경은 미구현" 같은 문장은 실제로 구현된 뒤에 고친다.

---

## 3. 수행 절차

### 3.1 TC-PERF-003 — IDS 응답 시간 최종 확인

측정 정본은 [공동 통합시험](../common/02_통합시험.md) §6과 [TEST_PLAN](../../../docs/TEST_PLAN.md)의 TC-PERF-003·TC-INT-004다.

| 항목 | 시작 → 종료 | 판정 |
|---|---|---|
| TC-PERF-003 | 실제 공격 주입 시작 → Node B의 해당 0x200 수신 | ≤3초 |
| TC-INT-004 | 실제 공격 주입 시작 → 해당 경보 화면 표시 | 공식 통합 기준으로 별도 판정 |

1. ECU M4의 공격·IDS·수신 계측 구현이 선행한다. trial마다 수집기를 먼저 준비하고 이전 경보를 구분할 run/trial ID와 시간창을 설정한다.
2. 셸에서 `date`를 실행한 시각 대신 공격 프로세스의 첫 실제 프레임 주입 시각을 기록한다. 경보 수신·화면 그리기도 해당 trial과 연결한다.
3. 양측 파일을 동일 분석 호스트에 수집한다. 서로 다른 노드의 monotonic 시각을 직접 빼지 않는다. 공통 관찰 시계 또는 측정 전후 동기 오차 상한을 확보한 시각을 사용한다.
4. 음수·짝 누락·중복·오차 상한 미확보는 INVALID, 유효한 시행의 미검출·미수신·미표시는 FAIL로 기록한다. 미응답을 0초로 계산하거나 행에서 지우지 않는다.
5. 지연과 오차 상한을 합해도 기준 이내인지 확인한다. 공격별 반복 수·전 시행 결과·최악값·손실·시계 조건·증적 위치를 함께 남긴다.

- [ ] 공격→수신과 공격→화면의 두 열을 각각 기록
- [ ] 실제 주입 전에 수집 준비 확인, 오래된 경보 제외
- [ ] 원시 로그의 run/trial·노드·시계·단위·증적 연결 확인
- [ ] 미실시·실패·계측 오류를 합격과 구분

### 3.2 SDD-IVI 최종화

<a id="security-integration"></a>
### 3.2.1 Q2 송신부·배포 정책의 문서화 인수

**담당·선행:** IVI M6 담당이 M3 producer/worker, M4 배포, M5 계측의 실제 산출물을 인수한다. [ECU M6](../ecu/M6_문서_품질.md#security-integration)는 receiver/IDS 및 공동 계약 정합을 교차 검토하며 IVI 설계 작성 책임을 대신하지 않는다.

**수행:** [메시지·상태 규약 §10](../../../docs/development/security/인증이벤트_메시지_상태규약.md#planning-final)에서 실제 채택한 profile/schema와 다음 내용을 SDD-IVI의 해당 모듈·생명주기·배포 절에 반영할 과제로 편입한다.

- verifier 결과와 기존 pending/commit의 경계, producer epoch·ready cutoff·이전 worker 회수
- producer 큐/FIFO/status 예약·snapshot 순서·원장 보존식·포화/만료 처리
- TLS peer·인증서 갱신·HAL 도메인 소켓/키 권한과 설정 공급
- 연결·backoff·부분 I/O 기한·종료 취소·회수 실패, UI/안전 경로 비차단
- 실제 설정·파일·시험 증거, Q2-D/P 보조 시나리오와 기존 공식 TC의 관계

**인계·실패 대응:** 실제 CI 검사/배포 절차가 변경됐으면 CICD_SPEC·README의 해당 설명도 근거에 맞게 갱신한다. 미구현/미채택 규칙은 예정으로 남기고 후보를 구현 완료로 옮기지 않는다. 공식 계약과 drift가 있으면 공동 인계에서 승인·동기화 범위를 정한다. 새 HAL API·CAN 필드를 문서화 과정에서 임의 도입하지 않는다.

- [ ] SDD-IVI의 Q2 구조·권한·큐·종료 정책과 실제 구현/설정/시험이 대응한다.
- [ ] ECU M6 교차 검토와 공동 제출에 채택 버전·drift·미검증 목록을 인계했다.


```markdown
# SDD-IVI: IVI Software Design Document

## §1. 문서 개요
목적, 범위, 참조 문서 (ICD, SRS, TEST_PLAN, CICD_SPEC)

## §2. 시스템 아키텍처
CAN Bus → HAL Layer → Service Layer → App Layer
각 계층 역할과 의존 방향 (단방향: 아래에서 위로만)

## §3. 모듈 상세 설계

### §3.1 HAL Layer
- can_parser.h/.cpp — CAN 프레임 파싱 (ICD §1.2~1.5)
  · 디코딩 규칙: uint16/uint32 BE, current는 int16 2의 보수, temperature는 int 확장 후 −40
  · TC: TC-IVI-002-a/b/c
- vehicle_hal_impl.h/.cpp — SocketCAN 수신 스레드, 콜백 관리(최대 10), 타임아웃 stale 처리
  · TC: TC-IVI-001
- secoc_verifier.h/.cpp — HMAC 검증 (ICD §2.3), 카운터 윈도우(unsigned delta), 재동기화, 에스컬레이션
  · TC: TC-INT-002 (ECU TC-SEC-001~004와 교차)

### §3.2 Service Layer
- IVehicleDataService.aidl / IVehicleDataListener.aidl — Binder IPC (oneway)
- VehicleDataParcel.java — Parcelable, 읽기/쓰기 순서 일치
- VehicleDataService.java — RemoteCallbackList 브로드캐스트
- VehicleDataManager.java — 클라이언트 API, RemoteException 방어
  · TC: TC-IVI-003, TC-IVI-004

### §3.3 App Layer
- DashboardViewModel.kt — StateFlow<VehicleUiState>   · TC: TC-IVI-004, TC-IVI-008
- SocGauge.kt — Canvas 원형 게이지, socColor() 순수 함수, 애니메이션 300ms
                · TC: TC-IVI-005 (경계 6케이스)
- AlertBanner.kt — 유형별 아이콘·색상, autoHide   · TC: TC-IVI-006
- FailSafeIndicator.kt / DashboardScreen.kt — 4상태, CriticalDialog  · TC: TC-IVI-007

### §3.4 SecOC Verifier 상세
HMAC 입력 14B 구성, 절단 MAC 4B, 상수시간 비교, 카운터 윈도우 1~100, 첫 수신 통과 규칙

## §4. 데이터 흐름
CAN Frame → can_parser → vehicle_hal_impl → (0x102 검증 통과 후) callback
→ VehicleDataService (Binder) → VehicleDataManager → DashboardViewModel (StateFlow) → Composable

## §5. 에러 처리
- ICD §3.3 에러 코드 (ERR_CAN_INIT_FAIL ~ ERR_UNKNOWN_CAN_ID)
- ICD §2.5.1 수신 타임아웃 300ms → stale
- ICD §2.5.2 HMAC 연속 실패 에스컬레이션 (1~3 / 4~9 / 10+)
- ICD §2.5.3 카운터 재동기화
- Service death → 재바인딩

## §6. 테스트 케이스 매핑
| TC ID | 모듈 | 검증 대상 | 결과 |
```

**반드시 반영할 것** — 계획 원문과 실제 구현이 갈렸던 지점이다.

- [ ] 파서의 **전류·온도 디코딩 규칙**을 명시한다 ([M3](M3_HAL_Service_대시보드.md) 2장의 결함 2건)
- [ ] `0x100`을 `0x102` 검증 **후에** 전달한다는 순서를 §4에 명시한다
- [ ] SecOC 카운터 비교가 **unsigned delta** 방식임을 §3.4에 적는다
- [ ] Plan B로 전환했다면 §3.2를 D-Bus 기준으로 다시 쓰고, HIDL 서술을 남기지 않는다
- [ ] 미구현 항목은 "미구현"으로 적는다. 설계만 있는 것을 구현된 것처럼 쓰지 않는다

**추적성 검사**:

```bash
grep -o "TC-[A-Z]*-[0-9]*" docs/SDD-IVI.md | sort -u
grep -o "TC-IVI-[0-9]*\|TC-CI-[0-9]*" docs/TEST_PLAN.md | sort -u
# IVI 담당 TC가 모두 SDD의 어느 절엔가 매핑되는지 대조
```

### 3.3 CICD_SPEC 최신화

`docs/CICD_SPEC.md`는 **구현 전에 쓰인 명세**다. 구현과 대조해 갱신한다.

| 항목 | 확인 |
|---|---|
| Stage 1 cppcheck | 실제 대상 경로, 억제 규칙 |
| Stage 2 ARM64 빌드 | 산출물 이름 `adaptive_ecu`, artifact 이름 |
| Stage 3 QEMU + Coverage | CMake 옵션 `ECU_BUILD_TESTS`/`ENABLE_COVERAGE`, timeout 값, 게이트 임계 |
| Stage 4 배포 | `.new` → `mv` 교체, sudoers 최소 권한, `main` 푸시 한정 |
| 러너 | GitHub-hosted / self-hosted 중 실제로 쓴 것 |

- [ ] 명세와 구현이 다르면 **어느 쪽이 옳은지 정하고 한쪽을 고친다.** 둘 다 남겨두지 않는다
- [ ] Stage 4가 네트워크 제약으로 자동화되지 않았다면 그 사실을 명세에 적는다

### 3.4 README 확장

기존 `README.md`의 현재 상태 서술을 **실제 구현 상태에 맞게 갱신**하면서 프로젝트 소개를 더한다.

```markdown
# AUTOSAR 계층 기반 IVI-ECU 통합 플랫폼

[![CI](https://github.com/<user>/<repo>/actions/workflows/ci.yml/badge.svg)](...)
[![codecov](https://codecov.io/gh/<user>/<repo>/branch/main/graph/badge.svg)](...)

## 프로젝트 개요
RPi4 2대를 Node A ECU와 Node B IVI로 구성하고 CAN·SecOC·IDS를 end-to-end로 검증한다.

## 시스템 아키텍처
```
[Node A — RPi4 Ubuntu]              CAN Bus 500kbps         [Node B — RPi4 AOSP/Ubuntu]
├── BSW (C++)                ◄── 0x100 BMS_Status ──►      ├── HAL (C++)
│   ├── CAN CDD              ◄── 0x101 FailSafe   ──►      │   ├── can_parser
│   ├── SecOC HMAC           ◄── 0x102/0x103 SecOC ─►      │   ├── secoc_verifier
│   └── Watchdog             ◄── 0x200 IDS_Alert  ──►      │   └── vehicle_hal_impl
├── App (C++)                                               ├── Service (Java)
│   ├── EKF SOC / SOH                                       │   └── VehicleDataService
│   └── Fail-safe FSM                                       └── App (Kotlin)
└── Security (Python)                                           ├── DashboardViewModel
    ├── IDS (규칙/사양/IF)                                       ├── SocGauge
    └── 트래픽 생성·평가                                          ├── AlertBanner
                                                                └── FailSafeIndicator
```

## 빌드 방법
### Node A (C++ ECU)
    cmake -S adaptive_ecu -B adaptive_ecu/build -DECU_BUILD_TESTS=ON
    cmake --build adaptive_ecu/build
    ctest --test-dir adaptive_ecu/build --output-on-failure

### ARM64 크로스 빌드
    docker build -f Dockerfile.arm64 -t capstone-arm64 .
    docker run --rm -v "$(pwd)":/workspace capstone-arm64 bash -c \
      "cmake -S /workspace/adaptive_ecu -B /workspace/build-arm64 \
         -DCMAKE_TOOLCHAIN_FILE=/opt/toolchain-aarch64.cmake && \
       cmake --build /workspace/build-arm64"

### Node B
    (Plan A) cd ~/aosp-rpi4 && source build/envsetup.sh && lunch <target> && m -j$(nproc)
    (Plan B) cmake -S ivi_platform -B ivi_platform/build && cmake --build ivi_platform/build

## 실험 결과
| 항목 | 측정값 | 목표 | 조건 |
|---|---|---|---|
| e2e 지연 평균 | (실측) | ≤50ms | 측정 구간 T1→T4 |
| 0x100 주기 | (실측) | 100ms ±10ms | — |
| IDS 응답 | (실측) | ≤3초 | 공격 주입 → 배너 표시 |
| Ablation | (실측) | — | 합성 트래픽 1,200 시행 |

## 문서
ICD · SRS · SDD-ECU · SDD-IVI · TEST_PLAN · TARA · ADR · CICD_SPEC
```

- [ ] **표의 (실측) 자리를 추정치로 채우지 않는다.** 측정 전이면 빈칸이나 "미측정"으로 둔다
- [ ] Ablation 결과에 "합성 트래픽" 조건을 명시한다
- [ ] 배지 URL의 `<user>/<repo>`를 실제 값으로 바꾼다. 그대로 두면 깨진 배지가 노출된다
- [ ] 아키텍처 그림에 없는 모듈(미구현)을 그려 넣지 않는다

### 3.5 Coverage 게이트

`codecov.yml` (프로젝트 루트):

```yaml
codecov:
  require_ci_to_pass: true

coverage:
  status:
    project:
      default:
        target: 80%
        threshold: 2%
    patch:
      default:
        target: 80%

ignore:
  - "adaptive_ecu/test/"
  - "security/tests/"
  - "ivi_platform/test/"
```

Codecov 연동:

1. codecov.io에서 저장소 추가
2. 토큰을 GitHub Secrets `CODECOV_TOKEN`으로 등록
3. CI Stage 3의 업로드 스텝에서 사용

```bash
lcov --summary coverage_filtered.info
lcov --list coverage_filtered.info      # 파일별 커버리지 확인
```

**80% 미달 시 보강 우선순위**

1. `can_parser.cpp` — 모든 CAN ID 경로, 경계값(전류 부호, 고온)
2. `secoc_verifier.cpp` — 검증 실패·카운터 밖·재동기화·에스컬레이션 경로
3. `vehicle_hal_impl.cpp` — 에러 경로 (`ERR_CAN_INIT_FAIL`, `ERR_CAN_READ_FAIL`, `ERR_CALLBACK_FULL`)

- [ ] 커버리지를 올리려고 **의미 없는 시험을 추가하지 않는다.** 위 세 곳은 실제 결함이 숨을 수 있는 자리다
- [ ] 목표 미달이면 수치와 미커버 지점을 기록한다. 게이트 임계를 낮춰 통과시키지 않는다

### 3.6 CI 전체 녹색 확인

```bash
# 로컬 사전 확인
cppcheck --enable=all --error-exitcode=1 --suppress=missingIncludeSystem \
         -I adaptive_ecu/include adaptive_ecu/src ivi_platform/hal

cmake -S ivi_platform -B ivi_platform/build && cmake --build ivi_platform/build
ctest --test-dir ivi_platform/build --output-on-failure

cd ivi_platform/app && ./gradlew test
```

| Stage | TC | 확인 |
|---|---|---|
| 1 cppcheck | TC-CI-002 | 오류 0건 |
| 2 ARM64 빌드 | TC-CI-003 | artifact 생성 |
| 3 QEMU + Coverage | TC-CI-004 | 시험 통과 + 게이트 |
| 4 배포 + Health Check | TC-CI-005~006 | 배포·PASS |
| 트리거 | TC-CI-001 | PR/Push에서 자동 기동 |

---

## 4. 검증 명령과 합격 기준

```bash
lcov --summary coverage_filtered.info
grep -o "TC-[A-Z]*-[0-9]*" docs/SDD-IVI.md | sort -u | wc -l
cd ivi_platform/app && ./gradlew test
```

| 기준 | 합격 조건 |
|---|---|
| TC-PERF-003 | 공격 주입 → 0x200 수신 ≤3초, 화면 지연은 TC-INT-004로 별도 기록 |
| SDD-IVI | 전 모듈 절 완성, TC 매핑, 구현 불일치 반영 |
| CICD_SPEC | 실제 구현과 일치 |
| README | 아키텍처·빌드·결과·문서 링크, 미측정 항목 표시 |
| Coverage | 라인 ≥80% |
| CI | Stage 1~4 전부 녹색 (TC-CI-001~006) |
| 태그 | `v0.6.0` |

---

## 5. 실패 시 대응과 우회

**TC-PERF-003 미달**
- 어느 구간이 긴지 나눠 본다: 탐지 지연(IDS 윈도우 1초) / 송신 / 수신·파싱 / UI 표시
- IDS 윈도우가 1초이므로 그 자체가 예산의 1/3이다. 윈도우를 줄이면 탐지율이 떨어진다 — 트레이드오프를 기록한다
- 미달이면 값과 구간 분해를 남긴다

**Coverage 80% 미달**
- `lcov --list`로 파일별 수치를 본다
- `main.cpp`나 UI Composable은 단위 시험 대상이 아닐 수 있다. `ignore`에 넣을지 판단하되, **넣은 이유를 남긴다**
- 임계를 낮추지 않는다

**Codecov 업로드 실패**
- 토큰이 Secrets에 있는지 확인한다
- 업로드가 안 돼도 로컬 `lcov --summary` 수치로 게이트를 판정할 수 있다. CI 게이트는 이미 그렇게 돼 있다

**CI Stage 4가 네트워크 때문에 안 됨**
- [M4](M4_대시보드_Alert_배포.md) 5장의 대안(self-hosted runner 등)을 검토한다
- 자동화가 불가능하면 **수동 배포 절차를 문서화하고 TC-CI-005를 미달성으로 기록한다.** 통과로 적지 않는다

**SDD와 구현이 계속 어긋남**
- 구현을 정본으로 삼되, ICD 계약(§1·§2)에 관한 것이면 반대다. 계약은 ICD가 정본이고 구현을 맞춘다

---

## 6. 완료 체크리스트

- [ ] TC-PERF-003 수신 지연과 TC-INT-004 화면 지연을 분리 측정, 반복 최악값 기록
- [ ] `docs/SDD-IVI.md` 전 모듈 절 완성
- [ ] 파서 디코딩 규칙·검증 순서·카운터 방식 명시
- [ ] Plan B 전환 시 Service 절 D-Bus 기준으로 재작성
- [ ] `docs/CICD_SPEC.md` 구현과 일치하도록 갱신
- [ ] `README.md` 확장, 미측정 항목 표시, 배지 URL 실제 값
- [ ] `codecov.yml` 추가, 토큰 등록
- [ ] Coverage 라인 ≥80%, 미달 시 수치·지점 기록
- [ ] CI Stage 1~4 전부 녹색 (TC-CI-001~006)
- [ ] `docs/TEST_PLAN.md`에 IVI TC 결과·Skip 사유 기록
- [ ] `v0.6.0` 태그 생성
