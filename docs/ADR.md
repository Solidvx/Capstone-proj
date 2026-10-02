# Architecture Decision Records (ADR)

> **버전**: v1.5 | **작성일**: 2026-03-01 | **최종 수정**: 2026-10-03 | **작성자**: 팀원A, 팀원B
> **프로젝트**: AUTOSAR 계층 기반 IVI-ECU 통합 플랫폼  
> **목적**: 주요 기술 선택의 컨텍스트·대안·근거를 기록하여 면접 질문 "왜 이 기술을 골랐나요?"에 데이터 기반으로 답변할 수 있게 한다.  
> **작성 규칙**: 기술 선택 시점에 즉시 작성. 결정 번복 시 상태를 Superseded로 변경하고 새 ADR 추가.

---

## 목차

| ADR | 제목 | 상태 | 결정일 |
|-----|------|------|--------|
| [ADR-001](#adr-001) | Linux SocketCAN API 사용 (직접 SPI 레지스터 접근 대신) | Accepted | 2026-03-01 |
| [ADR-002](#adr-002) | HMAC-SHA256 절단 MAC (4 B) + 분리 프레임 SecOC | Accepted | 2026-03-01 |
| [ADR-003](#adr-003) | Isolation Forest 기반 ML IDS | Accepted | 2026-03-15 |
| [ADR-004](#adr-004) | HIDL 채택 (AIDL 대신) — Vehicle HAL 인터페이스 | Superseded by ADR-010 | 2026-03-10 |
| [ADR-005](#adr-005) | Extended Kalman Filter SOC 추정 | Accepted | 2026-03-01 |
| [ADR-006](#adr-006) | QEMU user-mode 에뮬레이션 CI 통합 | Accepted | 2026-03-10 |
| [ADR-007](#adr-007) | Docker ARM64 크로스컴파일 컨테이너 | Accepted | 2026-03-10 |
| [ADR-008](#adr-008) | Ablation Study 기반 보안 실험 설계 (3가지 방어 구성) | Accepted | 2026-04-01 |
| [ADR-009](#adr-009) | ML IDS 엔진 실행 위치 — Node A (Ubuntu) | Accepted | 2026-03-15 |
| [ADR-010](#adr-010) | IVI Plan B — Debian 13 + C++ SocketCAN + Qt 6.8 Quick/QML | Accepted / Activated | 2026-09-22 |
| [ADR-011](#adr-011) | 공격 시뮬레이터 및 IDS 구현 언어 — Python (C++ 대신) | Accepted | 2026-03-01 |
| [ADR-012](#adr-012) | SecOC 인증 프레임 분리 전송 (0x102 / 0x103) | Accepted | 2026-03-01 |

---

## ADR-001

### Linux SocketCAN API 사용 (직접 SPI 레지스터 접근 대신)

**상태**: Accepted | **결정일**: 2026-03-01 | **결정자**: 팀원A

#### 컨텍스트

Node A(RPi4)에서 MCP2515 SPI-CAN 컨트롤러를 사용해 CAN 통신을 구현해야 한다.
HW 접근 방식으로 두 경로를 검토했다.

#### 검토된 대안

| 방법 | 장점 | 단점 |
|------|------|------|
| 직접 SPI 레지스터 접근 | AUTOSAR MCAL 수준의 HW 제어 경험, MCP2515 데이터시트 완전 활용 | 개발 기간 대비 리스크 높음, 인터럽트·타이밍 디버깅 복잡, HW 손상 가능성 |
| **Linux SocketCAN API** (채택) | 표준 BSD 소켓 인터페이스, candump/cansniffer 디버깅 도구 풍부, 이식성 보장 | 커널 드라이버 레이어가 추상화됨 |

#### 결정

**Linux SocketCAN (PF_CAN / SOCK_RAW) 사용.**

AUTOSAR BSW/CDD 직무의 핵심 역량은 "드라이버 세부 구현"이 아니라 **"HW 추상화 경계 설계"**다.
`CanDriver` 추상 인터페이스를 먼저 설계하고 `SocketCanCdd`로 구현함으로써, 칩이 MCP2515→다른 CAN 컨트롤러로 교체되어도 상위 Application 코드가 변경되지 않는다는 **AUTOSAR CDD 설계 원칙**을 동일하게 체득할 수 있다.
8개월 기간 내에 검증 가능한 결과물 산출을 위해 개발 효율성을 우선한다.

#### 결과

- `can_driver.h` 추상 인터페이스 → `SocketCanCdd` 구현체 구조로 계층 분리 달성
- `candump`, `cansniffer`, `cansend` 즉시 활용 가능한 디버깅 환경
- 추후 HW 교체(SocketCAN → ISOTP, 실 ECU MCAL) 시 인터페이스 무변경 보장

---

## ADR-002

### HMAC-SHA256 절단 MAC (4 B) + 분리 프레임 SecOC

**상태**: Accepted | **결정일**: 2026-03-01 | **결정자**: 팀원A

#### 컨텍스트

CAN 프레임 DLC 최대 8바이트 제약 내에서 BMS 데이터 무결성을 보장해야 한다.
AUTOSAR SecOC 표준의 핵심인 MAC(Message Authentication Code)를 어떻게 구현할지 결정해야 한다.

#### 검토된 대안

| 방식 | 설명 | 장점 | 단점 |
|------|------|------|------|
| 인라인 MAC (4B 데이터 + 4B MAC) | 8B 페이로드를 데이터/MAC으로 분할 | 프레임 1개로 해결 | 유효 데이터 공간 50% 감소, ICD 복잡 |
| **분리 프레임 MAC** (채택) | 원본(0x100) + 인증(0x102) 별도 전송 | 원본 8B 전부 데이터 사용, 책임 분리 명확 | 프레임 수 2배, 타이밍 동기화 필요 |
| AES-CMAC | 블록 암호 기반 | AUTOSAR SecOC 표준 알고리즘 | OpenSSL 없이 구현 난이도 높음 |
| HMAC-SHA256 전체 32B | 최고 보안 강도 | — | CAN 8B 프레임에 수납 불가 |

#### 결정

**HMAC-SHA256 + 앞 4바이트 절단 + 별도 인증 프레임 전송.**

- AUTOSAR SecOC-MAC 절단(truncation) 개념(AUTOSAR_SWS_SecOC §7.2.3)과 동일
- Python `hmac` 표준 라이브러리 + C++ `OpenSSL libcrypto`로 양 노드 구현 용이
- 롤링 카운터 내재화 → Replay 공격 방어 기본 제공
- `hmac.compare_digest()` 사용 → constant-time 비교로 타이밍 공격 방지

**Trade-off**: 절단 MAC 32→4B로 이론적 충돌 확률 2⁻³²(약 40억 분의 1). 프로젝트 범위(CAN 버스 물리 접근 공격 방어)에는 충분한 수준.

#### 결과

- CAN ID 쌍: `(0x100, 0x102)` BMS 상태, `(0x101, 0x103)` Fail-safe 이벤트
- `ICD §1.4`: TruncatedMAC(4B) + RollingCounter(4B) 레이아웃 확정

---

## ADR-003

### Isolation Forest 기반 ML IDS

**상태**: Accepted | **결정일**: 2026-03-15 | **결정자**: 팀원A

#### 컨텍스트

CAN 버스 이상 트래픽 탐지 ML 알고리즘을 선택해야 한다.
제약 조건: ① 레이블된 공격 데이터셋 없이 동작 ② 실시간 탐지(≤3초) ③ RPi4(ARM64)에서 경량 실행.

#### 검토된 대안

| 알고리즘 | 유형 | 장점 | 단점 |
|----------|------|------|------|
| **Isolation Forest** (채택) | 비지도 이상 탐지 | 레이블 불필요, 경량, 빠른 추론, 이상 점수 연속값 제공 | 공격 유형 자동 분류 불가 → 규칙 기반 후처리 필요 |
| Autoencoder (신경망) | 비지도 | 복잡한 패턴 학습 | 학습 시간 길고 RPi4 추론 속도 불확실 |
| One-Class SVM | 비지도 | 이론적 보장 | 고차원에서 느림, 하이퍼파라미터 민감 |
| Random Forest | 지도 | 분류 정확도 높음 | 레이블 공격 데이터 수집 필요 (본 프로젝트 제약) |
| Rule-based IDS | 규칙 | 설명 가능성 최고 | 사전 미지(zero-day) 공격 패턴 탐지 불가 |

#### 결정

**Isolation Forest (scikit-learn)** + 공격 유형 분류는 규칙 기반 후처리로 보완.

- 정상 트래픽만으로 모델 학습 가능 → 공격 데이터 수집 부담 없음
- `decision_function()` 이상 점수 연속값 → 임계값 조정으로 탐지율/오탐율 트레이드오프 제어 가능
- scikit-learn의 RPi4(ARM64) 빌드 검증됨 (1초 윈도우당 수 ms 추론)
- Ablation Study에서 SecOC vs IDS 독립 기여도 수치화에 적합

#### 결과

- 7차원 특징 벡터: `id_mean`, `id_std`, `interval_mean`, `interval_std`, `msg_count`, `payload_mean`, `payload_std`
- `contamination=0.01` (정상 데이터 내 1% 이상치 가정)
- 탐지 후 공격 유형: msg_count/id_std/payload_std 기반 규칙 분류 → `IDS_Alert(0x200)` 전송

---

## ADR-004

### HIDL 채택 (AIDL 대신) — Vehicle HAL 인터페이스

**상태**: Superseded for current delivery by ADR-010 | **결정일**: 2026-03-10 | **결정자**: 팀원B

#### 컨텍스트

Android 13 AOSP에서 Vehicle HAL 인터페이스 정의 방식을 결정해야 한다.
Android 11부터 Google은 새 HAL에 AIDL 사용을 공식 권장하고 있다.

#### 검토된 대안

| 방식 | 도입 버전 | 현재 상태 | 특징 |
|------|-----------|----------|------|
| **HIDL** (채택) | Android 8.0+ | Legacy — Android 14에서 deprecated 예정 | C++ native 구현, 커뮤니티 RPi4 포팅 예제 HIDL 중심 |
| AIDL (stable) | Android 11+ | Recommended (Google 공식) | Java/C++ 동시 지원, 최신 표준 |

#### 결정

**HIDL 채택.**

- RPi4 AOSP 포팅 레퍼런스(raspberry-vanilla, KonstaKANG)가 Android 13 기준 HIDL 예제를 주로 제공 → 포팅 성공 가능성 ↑
- HAL 구현체가 C++이므로 HIDL C++ 바인딩이 CAN 파싱 로직과 동일 언어로 자연스럽게 통합
- AIDL stable interface 설계는 학습 곡선이 높아 8개월 프로젝트 내 리스크 가중
- 현대모비스 IVI 채용 공고에서 "HIDL 경험" 명시적 요구

**Future Migration**: HIDL deprecated 예정 인식. 캡스톤디자인 II에서 AIDL 마이그레이션 후속 과제 설정.

#### 결과

- `IVehicleHal.hal`, `IVehicleHalCallback.hal` 인터페이스 파일 사용
- HAL 서비스 등록: `android.hardware.vehicle@1.0-service`

---

## ADR-005

### Extended Kalman Filter SOC 추정

**상태**: Accepted | **결정일**: 2026-03-01 | **결정자**: 팀원A

#### 컨텍스트

BMS SOC(State of Charge) 추정 알고리즘을 선택해야 한다.
핵심 요건: "단순 방법 대비 정량적 개선을 수치로 증명 가능"해야 포트폴리오 가치가 있다.

#### 검토된 대안

| 알고리즘 | 복잡도 | 특징 |
|----------|--------|------|
| Coulomb Counting | 최하 | 전류 적분. 센서 드리프트 누적 → 장기 오차 발산 |
| **EKF** (채택) | 중간 | 예측(쿨롱)+관측(OCV) 칼만 융합. 1D 상태 공간이라 Jacobian이 스칼라 |
| UKF (Unscented KF) | 높음 | 비선형 시스템 이론적 우위. OCV-SOC 비선형성은 EKF로 충분 처리 가능 |
| Particle Filter | 매우 높음 | 임의 분포 지원. RPi4에서 100ms 주기 실시간 처리 계산량 부담 |

#### 결정

**EKF (1D 상태 공간)** 채택.

- 상태 변수가 SOC 하나 → Jacobian이 스칼라(`dOCV/dSOC`), 행렬 연산 없음
- 쿨롱 카운팅 대비 RMSE 개선율을 수치로 측정·비교 가능 → 실험 결과 정량화 용이
- S-7=A: NASA 자료는 원시 단셀 재생·데이터 검증으로 유지하고, 정답이 알려진 합성 시나리오에서 SOC 정확도를 비교한다. 두 결과와 ADS1115 취득·통합 결과를 구분하여 보고한다. CALCE 채택이나 실제 배터리 정확도 검증을 완료한 것으로 주장하지 않는다.
- BMS 직무 면접에서 EKF/UKF/PF 비교 설명으로 알고리즘 선택 근거 어필 가능

#### 결과

- 예측: `SOC_pred = SOC - (I × dt) / Q_capacity`
- 업데이트: OCV-SOC 3차 다항식 + Kalman gain 계산 (`K = P_pred × H / S`)
- 튜닝 파라미터 초기값: `Q_noise=1e-5`, `R_noise=1e-2`, `P_init=1.0`

---

## ADR-006

### QEMU user-mode 에뮬레이션 CI 통합

**상태**: Accepted | **결정일**: 2026-03-10 | **결정자**: 팀원B

#### 컨텍스트

GitHub Actions 러너 아키텍처는 x86_64이다.
ARM64 크로스컴파일된 바이너리를 CI에서 **실제 실행**하여 테스트하려면 에뮬레이션이 필요하다.

#### 검토된 대안

| 방식 | 장점 | 단점 |
|------|------|------|
| **QEMU user-mode** (채택) | 무료, 빠름, Docker 내 간단 통합 (`qemu-aarch64-static`) | 커널 모듈·SocketCAN 에뮬레이션 불가 |
| QEMU full-system | ARM64 VM 완전 부팅, SocketCAN 가능 | 부팅 시간 수분 → CI 너무 느림 |
| RPi4 self-hosted runner | 실 ARM64 HW 테스트 | 24/7 RPi4 네트워크 연결 유지 필요 |
| 테스트 건너뜀 | — | 타겟 아키텍처 런타임 버그 CI 미탐지 |

#### 결정

**QEMU user-mode (`qemu-aarch64-static`) Docker 컨테이너 내 통합.**

- `apt install qemu-user-static binfmt-support` + `update-binfmts` 설정으로 적용 간단
- GoogleTest 단위 테스트(SocketCAN 무관 순수 로직)는 QEMU user-mode로 충분히 실행 가능
- "ARM64 타겟 아키텍처에서 단위 테스트까지 CI 자동화" → 면접 어필 강도 증가

**제약 인지**: SocketCAN 의존 통합 테스트는 QEMU user-mode 불가 → 실 RPi4 배포 후 Stage 4 Health Check로 보완.

#### 결과

- GitHub Actions 러너(ubuntu-22.04): `sudo apt-get install -y qemu-user-static`
- CI Stage 3: `qemu-aarch64-static ./build/test_binary --gtest_output=xml` 실행

---

## ADR-007

### Docker ARM64 크로스컴파일 컨테이너

**상태**: Accepted | **결정일**: 2026-03-10 | **결정자**: 팀원B

#### 컨텍스트

개발 PC(Mac/Windows/Linux, x86_64)에서 RPi4(ARM64) 바이너리를 빌드해야 한다.
팀원 간 빌드 환경 일관성 및 CI 완전 재현성이 필요하다.

#### 검토된 대안

| 방식 | 일관성 | CI 통합 | 난이도 |
|------|--------|---------|--------|
| **Docker 크로스컴파일** (채택) | 완전 동일 | `docker run` 한 줄 | Docker 학습 곡선 |
| 직접 툴체인 설치 | 팀원별 불일치 가능 | CI마다 수동 설치 | 낮음 |
| RPi4 native 빌드 | — | 배포 후 자동화 어려움 | 빌드 속도 매우 느림 |

#### 결정

**Docker 기반 ARM64 크로스컴파일 환경 (`Dockerfile.arm64`).**

- `docker build` 한 번으로 팀원A/B 동일 빌드 환경 보장 → "내 PC에서는 됐는데" 문제 원천 차단
- GitHub Actions에서 `docker run`으로 CI 완전 재현성 보장
- `toolchain-aarch64.cmake`로 CMake 크로스컴파일 타겟 명시 → 아키텍처 오빌드 방지

#### 결과

- `FROM ubuntu:22.04` + `aarch64-linux-gnu-gcc-12` (QEMU는 러너에 설치)
- CI: `docker run --platform linux/amd64 arm64-builder cmake --build . --target all`

---

## ADR-008

### Ablation Study 기반 보안 실험 설계 (3가지 방어 구성)

**상태**: Accepted | **결정일**: 2026-04-01 | **결정자**: 팀원A

#### 컨텍스트

4종 CAN 공격 실험에서 SecOC와 ML IDS 각각의 방어 기여도를 독립적으로 측정하지 않으면,
"통합 시스템이 동작했다"는 결과만 남고 각 계층의 독립적 가치를 입증하기 어렵다.

#### 결정

**3가지 방어 구성 Ablation Study 설계:**

| 구성 | SecOC HMAC | ML IDS | 측정 목적 |
|------|:----------:|:------:|-----------|
| Config-1 (무방어 baseline) | ✗ | ✗ | 공격 성공률 100% 기대 → 기준선 설정 |
| Config-2 (SecOC only) | ✓ | ✗ | SecOC 단독 효과 — Spoofing/Replay 차단율 |
| Config-3 (SecOC + IDS) | ✓ | ✓ | 최종 통합 효과 — Flooding/Fuzzy 추가 탐지율 |

**예상 결론 패턴**: "SecOC만으로 Spoofing/Replay는 100% 차단, Flooding은 0% 차단 → IDS가 Flooding을 보완"이라는 계층별 역할 수치화.

#### 결과

- 학술대회 제출 시 Ablation Study가 실험 설계 품질의 핵심 평가 기준으로 작동
- 면접 "왜 두 방어를 함께 쓰는가"에 데이터 기반 답변 가능
- 5개월차(10월) 일정에 3가지 구성 실험 수행 이정표 설정

---

## ADR-009

### ML IDS 엔진 실행 위치 — Node A (Ubuntu)

**상태**: Accepted | **결정일**: 2026-03-15 | **결정자**: 팀원A + 팀원B (공동)

#### 컨텍스트

ML IDS(Isolation Forest) 엔진을 어느 노드에서 실행할지 결정해야 한다.

#### 검토된 대안

| 위치 | 장점 | 단점 |
|------|------|------|
| **Node A (Ubuntu)** (채택) | Python scikit-learn 직접 실행, CAN 버스 직접 접근, Android 의존성 없음 | C++ ECU 코드와 별도 프로세스 |
| Node B (Android) | UI 경보와 같은 노드에서 처리 | Python scikit-learn을 Android NDK로 빌드하거나 TFLite로 변환 필요 → 과도한 작업량 |

#### 결정

**Node A (Ubuntu) Python 프로세스에서 IDS 실행, 탐지 결과를 CAN ID 0x200으로 Node B에 전송.**

- Python scikit-learn의 Android 포팅은 NDK 크로스컴파일 또는 TFLite 변환 모두 과도한 작업
- Node A가 CAN 버스에 직접 접근 → CAN 트래픽 모니터링에 별도 수신 로직 불필요
- 0x200 경보 프레임을 Node B HAL이 기존 수신 경로(0x100/0x101과 동일)로 자연스럽게 처리

#### 결과

- `security/ids/ids_engine.py`: `python3 ids_engine.py --interface can0` 형태로 Node A에서 실행
- SDD-IVI 공격 탐지 시퀀스 다이어그램에 "IDS = Node A 발신" 명시
- ICD §1.1: CAN ID 0x200 방향 `Node A → Node B` 확정

---

## ADR-010

### IVI Plan B — Debian 13 + C++ SocketCAN + Qt 6.8 Quick/QML

**상태**: Accepted / Activated | **결정일**: 2026-09-22 | **결정자**: 팀원B

#### 컨텍스트

남은 일정 안에 AOSP 이미지 선정·대용량 빌드·RPi4 부팅·커널 CAN·HIDL/Binder·앱을 모두 검증할 시간이 부족하다. 현재 저장소에는 Android 제품 코드가 없고, 이전 작업 폴더에는 재사용 가능한 C++ SocketCAN·Qt 자료가 있다. CAN/SecOC 통합과 시연 가능한 대시보드를 우선 완성해야 한다.

#### 결정

현 제출 범위의 Node B를 **Debian 13 ARM64 + C++17 + SocketCAN + Qt 6.8 Quick/QML**로 구현한다. 실제 RPi4의 Debian 13과 배포판 Qt 6.8을 빌드 기준으로 고정하며, 더 낮은 Qt 버전의 전체 대시보드 빌드는 지원 범위에서 제외한다.

- 수신, SecOC, 상태 서비스, ViewModel, QML의 책임을 분리한다.
- 첫 구현은 단일 프로세스로 구성하고 C++ 인터페이스로 계층 경계를 유지한다.
- D-Bus/gRPC 프로세스 분리는 제출 후 확장으로 둔다.
- CAN ID, DLC, byte order, HMAC 입력, rolling counter 규칙은 ICD 현행 계약을 유지한다.
- Android AOSP, HIDL, Binder/AIDL, Jetpack Compose는 현 제출 범위에서 제외하고 과거 설계 자료로 보존한다.
- ICD §8 sensorState는 별도 양 노드 동시 전환 전까지 활성 계약으로 취급하지 않는다.

#### 결과

- ADR-004는 현 제출 범위에서 이 결정으로 대체된다.
- SRS FR-IVI-001~008, SDD-IVI, TEST_PLAN, ICD의 Node B API를 Qt 경로로 동기화한다.
- `ivi_platform/`은 C++/Qt 제품 경계가 되며 이전 소스는 파일별 검토 후 선택 이관한다.
- Android 포팅 경험 대신 Linux IVI 계층 설계, CAN 보안 검증, Qt HMI 통합 결과를 시연한다.

---

## ADR-011

### 공격 시뮬레이터 및 IDS 구현 언어 — Python (C++ 대신)

**상태**: Accepted | **결정일**: 2026-03-01 | **결정자**: 팀원A

#### 컨텍스트

CAN 공격 시뮬레이터와 ML IDS 엔진의 구현 언어를 결정해야 한다.
Node A 코어 로직은 이미 C++17로 확정되었다.

#### 검토된 대안

| 언어 | 공격 시뮬레이터 | IDS 엔진 | 비고 |
|------|---------------|---------|------|
| **Python** (채택) | python-can, Scapy | scikit-learn 직접 사용 | 생태계 최적, 빠른 프로토타이핑 |
| C++ | can-utils wrapping | mlpack, dlib 등 | ML 라이브러리 선택 복잡, 빌드 설정 부담 |

#### 결정

**Python (python-can + Scapy + scikit-learn)** 채택.

- `python-can`이 SocketCAN에 직접 연결 → 공격 패킷 생성/전송 즉시 가능
- `scikit-learn` IsolationForest 5줄로 학습·추론 가능
- Scapy 기반 정밀 패킷 조작 (Replay, Spoofing)
- 현업 패턴: "ECU 코어(C++) + 보안 분석·테스트 툴(Python)" 역할 분리

**경계 원칙**: Python은 `security/` 디렉토리(공격 시뮬레이터, IDS)에만 사용. `adaptive_ecu/` 전체는 C++17 유지.

#### 결과

- `security/` 디렉토리 전체 Python 3.10
- `adaptive_ecu/` 전체 C++17
- `requirements.txt`: python-can, scapy, scikit-learn, numpy, pandas, joblib

---

## ADR-012

### SecOC 인증 프레임 분리 전송 (0x102 / 0x103)

**상태**: Accepted | **결정일**: 2026-03-01 | **결정자**: 팀원A + 팀원B (공동)

#### 컨텍스트

HMAC MAC을 원본 프레임에 인라인 포함할지, 별도 CAN ID로 분리 전송할지 결정해야 한다.
ICD 설계 단계에서 공동 결정이 필요한 인터페이스 수준 결정이다.

#### 검토된 대안

| 방식 | 설명 | 원본 데이터 공간 |
|------|------|----------------|
| 인라인 MAC | 0x100 페이로드 = 4B 데이터 + 4B MAC | 50% (4B) |
| **분리 프레임** (채택) | 0x100(원본 8B) + 0x102(MAC 4B + Counter 4B) | 100% (8B) |

#### 결정

**분리 프레임 방식 채택.**

- 원본 프레임(0x100) 8바이트 전부 BMS 데이터에 할당 → ICD 데이터 밀도 최대화
- `candump` 디버깅 시 원본 데이터를 MAC 간섭 없이 그대로 읽을 수 있어 개발 편의성 향상
- AUTOSAR SecOC "SecuredPDU = DataPDU + Authenticator" 분리 구조와 개념적으로 동일

**Trade-off**: 프레임 수 2배 증가. 원본 프레임 직후 즉시 인증 프레임 전송으로 타이밍 동기화 문제 해결.

#### 결과

- `ICD §1.4`: 0x102/0x103 레이아웃 확정 (TruncatedMAC 4B + RollingCounter 4B)
- Node B 수신 계층: 0x100 수신 후 버퍼링 → 0x102 수신 시 MAC 검증 후 VehicleData 구성

---

## 변경 이력 (Changelog)

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|-----------|--------|
| v1.0 | 2026-03-01 | ADR-001, 002, 005, 010, 011, 012 초안 작성 | 팀원A, 팀원B |
| v1.1 | 2026-03-10 | ADR-004, 006, 007 추가 (HIDL, QEMU, Docker) | 팀원A, 팀원B |
| v1.2 | 2026-03-15 | ADR-003, 009 추가 (IDS 알고리즘, IDS 위치) | 팀원A, 팀원B |
| v1.3 | 2026-04-01 | ADR-008 추가 (Ablation Study 실험 설계) | 팀원A |
| v1.4 | 2026-09-22 | ADR-010 활성화, ADR-004 대체 표시, Qt Plan B 기준 확정 | 팀원B |
| v1.5 | 2026-10-03 | ADR-010 대상 환경을 실제 RPi4 Debian 13·Qt 6.8로 확정 | 팀원B |


## 서면 승인 설계 보완 — S-1~S-3=A

2026-09-06 사용자 상세 답변을 근거로 다음 목표를 채택했다. 기존 ADR 번호를 재사용하거나 제품 전환 완료로 표시하지 않는다. 결정 원문은 [질문리스트](development/governance/의사결정_기록.md#part1-questions), 현재/목표 계약 구분은 [ICD §8](ICD.md#8-승인된-다음-전환-목표--s-3a-제품-반영-전)에 있다.

- S-1: 경보 배너·문구 즉시 표시, 장식 효과만 허용, 사용자 확인 유지. 지연 등장·자동 해제는 채택하지 않는다.
- S-2: 가변저항 기반 가상 배터리의 상태 전이·인증 통보·IVI 경고가 필수 범위. 실제 전류 제어는 필수 기능에서 제외하며 보조배터리 선택 시험은 별도 목적 확인 후 검토한다.
- S-3: 기존 byte 7 상태 번호와 stale·sensorState HAL 확장을 목표 계약으로 채택. ID·DLC·HMAC 입력 순서는 유지하되 새/구형 혼합 인수는 허용하지 않는다. 실제 구현·시험 동기화는 후속 전환 작업이다.

대안 및 선택 근거는 서면 질문의 비교표를 따른다. 세션 인증 후보·snapshot 제한 시간·장비 정보는 이 승인에 포함되지 않는다.


## 2026-09-09 승인된 SecOC 현행 규칙 정정

현행 고정키 수신 규칙은 [ICD §2.3~2.5](ICD.md#23-수신-검증-절차-node-b)를 따른다. 단순 대소 비교나 범위 밖 유효 MAC만으로 counter를 재동기화하는 이전 설명은 적용하지 않는다. 실제 C++/Python verify는 이 정정과 일치하며 알고리즘 변경은 없다. 첫 수신 MAC 성공은 새 부팅을 증명하지 못하고, 수신기 재부팅 후 과거 메시지 수락 위험이 남는다. 요구사항의 replay 방어 기준을 낮추거나 전체 보안 인수를 완료 처리하지 않는다.

인증 세션 자동 복구의 승인된 방향은 유지한다. 세션 상세 계약·양측 전환·재부팅 보안 시험은 [세션 설계안](development/security/CAN_세션인증_설계안.md)의 별도 관문이다. 새 wire·키 파생·HAL 변경을 이번 정정 승인으로 포함하지 않는다.
