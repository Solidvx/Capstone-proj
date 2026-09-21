# PROJECT 제안서 — 캡스톤디자인 I


# 과제 요약

## 1. 과제명

- **국문** : AUTOSAR 계층 기반 IVI-ECU 통합 플랫폼 구현 — CAN 보안 통신, BMS SW 컴포넌트 및 Android IVI 미들웨어 통합 —
- **영문** : Implementation of an AUTOSAR-Layered IVI-ECU Integration Platform with Secure CAN Communication, BMS Software Component, and Android IVI Middleware

---

# 2. 과제개요, 개발 배경, 필요성

## 【 이 프로젝트가 무엇인가? — 한눈에 보는 전체 그림 】

본 프로젝트는 라즈베리파이 2대를 각각 "차량 ECU"와 "차량 인포테인먼트 시스템"으로 구성하고, 두 장치를 CAN 버스로 연결하여 실제 차량 SW 개발 현장에서 다루는 기술을 아래에서부터 위까지 전 계층에 걸쳐 직접 구현하는 것을 목표로 한다.

### 이 프로젝트가 커버하는 영역

**① BSW (Basic Software) 계층 설계**
차량 ECU 내부의 하드웨어 추상화 계층을 AUTOSAR 표준에 따라 구현.
CAN 드라이버(CDD), 보안 통신(SecOC), Watchdog 등을 직접 작성한다.
→ 현대모비스 BSW/CDD 직무, BMS Application SW 직무에 직결

**② IVI (In-Vehicle Infotainment) 미들웨어 플랫폼 구현**
Android HAL(하드웨어 추상화 계층)부터 SystemService, 대시보드 앱까지 차량 인포테인먼트 전 스택을 직접 구현한다.
→ 현대모비스 IVI SW 플랫폼 직무에 직결

**③ CAN 보안 통신 + ML 기반 이상 탐지**
SecOC HMAC 인증으로 위변조를 방어하고, 4종 공격 시뮬레이터와 Isolation Forest IDS로 공격 탐지 실험을 수행한다.
→ 사이버보안 직무 + BSW 직무 보안 역량에 직결

**④ CI/CD 자동화 파이프라인 구축**
Docker 크로스컴파일 환경을 구성하고 GitHub Actions로 빌드 → 테스트 → 라즈베리파이 자동 배포까지 전 과정을 자동화한다.
→ CI/CD 직무 + 전 직무 코드 품질 관리 역량에 직결

즉, 이 프로젝트는 한 명은 "차량 ECU 아래 계층(BSW)"을, 다른 한 명은 "차량 화면 위 계층(IVI)"을 맡아서, 서로 다른 직무로 지원하면서도 같은 시스템을 함께 완성하는 전략이다.

---

## 【 왜 이 주제인가? — 개발 배경 】

### ▶ 배경 1. 현대 자동차는 소프트웨어로 정의되는 시대가 왔다

과거의 자동차는 엔진, 변속기 같은 기계 부품이 핵심이었다.
그러나 현재 고급 차량 1대에는 100개 이상의 ECU(Electronic Control Unit, 전자 제어 장치)가 탑재되어 있고, 이들이 CAN 버스라는 단일 통신선으로 끊임없이 데이터를 주고받으며 차량 전체를 제어한다.

현대차, BMW, 테슬라 등 주요 OEM은 이미 "SDV(Software Defined Vehicle, 소프트웨어 정의 차량)"를 미래 핵심 전략으로 선언하였으며, 차량 SW의 규모는 우주왕복선(약 40만 줄)의 수십 배인 수천만 줄에 달한다.

이에 따라 차량 SW 개발의 표준인 AUTOSAR, 인포테인먼트 플랫폼 Android AAOS, 그리고 차량 사이버보안 역량이 자동차 업계 SW 엔지니어의 핵심 요건이 되었다.

### ▶ 배경 2. BSW 계층 — "차량 SW의 기초 공사"이지만 학부에서 배울 기회가 없다

AUTOSAR BSW(Basic Software)는 ECU 내부에서 하드웨어와 애플리케이션 사이에 위치하는 SW 계층이다. CAN 드라이버, 통신 스택, 운영체제 추상화 등을 담당하며 차량 SW의 안전성과 이식성을 보장하는 기반 계층이다.

그러나 이를 실습할 수 있는 환경이 학부에는 사실상 없다.
- 상용 AUTOSAR 개발 툴 라이선스: 연간 수백만 원
- 상용 차량 HiL 테스트 장비: 수천만 원 ~ 수억 원
- 실제 차량용 ECU 보드: 구매 자체가 어려움

본 프로젝트는 라즈베리파이와 오픈소스 도구만으로 AUTOSAR의 핵심 설계 원칙을 직접 구현하여, 현장에서 즉시 통용되는 BSW 실무 감각을 습득한다.

### ▶ 배경 3. IVI 플랫폼 — Android 기반 전환이 가속화되고 있다

현대차·기아를 비롯한 주요 OEM이 Android Automotive OS(AAOS)를 차량 인포테인먼트(IVI) 기반으로 채택하고 있다. 단순 앱 개발과는 다르게, IVI SW 개발은 Android HAL(Hardware Abstraction Layer)을 직접 작성하고 차량 도메인 데이터를 Android 생태계로 끌어올리는 "플랫폼 엔지니어링"이 핵심 역량이다.

그러나 학부 수준의 Android 교육은 앱 개발에 머물러 있어, HAL 이하 계층을 직접 구현해본 경험을 가진 졸업생이 극히 드문 상황이다.

### ▶ 배경 4. 차량 해킹은 이미 현실적인 위협이다

차량이 네트워크화될수록 사이버 공격에 노출되는 면적도 커진다.

- **2015년 크라이슬러 지프 해킹 (CVE-2015-5611)**
  : 연구자들이 원격으로 고속도로를 달리는 지프의 변속기를 제어하는 데 성공. 결국 140만 대 리콜 사태로 이어졌다.

- **2022년 토요타 CAN 버스 인젝션 공격**
  : 차량 하부 헤드라이트 커넥터에 장치를 연결해 CAN 버스에 가짜 신호를 주입하여 도어 잠금을 해제하고 차량을 탈취하는 방법이 공개되었다.

이에 유엔은 2024년부터 UN R-155 규정을 전 차종에 의무 시행하였으며, 현대차·기아·현대모비스 등 국내 주요 기업이 이 대응을 최우선 과제로 삼고 있다. ISO 21434 표준에 따른 TARA(위협 분석 및 위험 평가) 수행 역량이 차량 SW 엔지니어에게 기본 요건으로 요구되고 있다.

---

## 【 이 프로젝트가 해결하는 문제 — 필요성 】

**문제 1. AUTOSAR BSW 계층을 직접 구현해본 경험이 없다**
→ BSW/RTE/Application의 계층 구조를 교과서가 아닌 실제 동작하는 코드로 구현하고, 두 ECU 간 CAN 통신에 적용해보는 경험을 갖는다.

**문제 2. Android IVI 개발이 앱 개발 수준에 머물러 있다**
→ HAL(하드웨어 추상화 계층)을 직접 작성하여 CAN 데이터를 Android 생태계로 끌어올리는 플랫폼 엔지니어 수준의 역량을 확보한다.

**문제 3. CAN 버스는 설계 당시 보안을 전혀 고려하지 않았다**
→ 누구든 버스에 연결하면 모든 메시지를 도청하고 위조할 수 있다. HMAC 인증 모듈로 이 취약점을 직접 방어하고 검증한다.

**문제 4. 차량 사이버 공격을 실제로 시뮬레이션해본 경험이 없다**
→ 4종 공격(Fuzzy/Replay/Spoofing/Flooding)을 직접 만들어 CAN 버스에 전송하고, ML 알고리즘이 이를 탐지하는 end-to-end 실험을 수행한다.

---

# 3. 개발 목표 및 개발 내용

## 3.1. 개발 환경

### 하드웨어 구성 및 역할

**① 라즈베리파이 4B (RAM 4GB) × 2대 ▶ 총 160,000원**

**[Node A] — 차량 ECU 역할 (팀원A 담당)**
- OS: Ubuntu 22.04 LTS
- 역할: AUTOSAR 계층 구조 기반으로 BMS(배터리 관리) 데이터를 계산하고 SecOC HMAC 인증을 붙여 CAN 버스로 전송하는 ECU 노드
- 어필 직무: ⚙️ BSW/CDD, 🔋 BMS Application SW

**[Node B] — 차량 IVI + 보안 게이트웨이 역할 (팀원B 담당)**
- OS: Android 13 (AOSP, Raspberry Pi 4 포팅) — AOSP 포팅 실패 시 Plan B로 Ubuntu + Qt/Flutter 대시보드 전환 가능 (상세 내용 3.2절 참조)
- 역할: CAN 데이터를 Android HAL을 통해 수신하고 대시보드 앱에 표시하며, ML IDS로 이상 트래픽을 실시간 탐지하는 IVI 노드
- 어필 직무: 📱 IVI SW 플랫폼, 🔄 CI/CD

**② MCP2515 SPI-CAN 컨트롤러 모듈 × 2개 ▶ 15,000원**
- 라즈베리파이에는 기본적으로 CAN 통신 하드웨어가 없다.
- 이 모듈을 각 라즈베리파이의 SPI 핀에 연결하면 CAN 버스 참여가 가능해진다.
- 두 모듈을 120Ω 종단 저항과 함께 CAN_H / CAN_L 선으로 연결하면 2노드 CAN 버스 네트워크가 완성된다.

**③ USB CAN 분석기 × 1개 ▶ 35,000원**
- CAN 버스를 오가는 모든 메시지를 실시간으로 캡처하고 분석하는 장비.
- 정상 트래픽과 공격 트래픽의 패턴 차이를 시각적으로 비교할 때 사용.
- Linux candump, cansniffer 명령어와 연동하여 디버깅에 활용.

**④ Samsung microSD 128GB × 2장 ▶ 30,000원**
- Node A용: Ubuntu 22.04 LTS 설치 (최소 32GB, C++ 빌드 공간 고려)
- Node B용: Android 13 AOSP 빌드 이미지 플래시 (64GB 이상 필수)

**⑤ 기타 부속품 ▶ 35,000원**
- 라즈베리파이 케이스 + 방열판 × 2 (Android AOSP 빌드 시 CPU 발열이 매우 심함 — 방열판 없으면 스로틀링 발생)
- USB-C 전원 어댑터 5V 3A × 2 (정격 전류 미달 시 전압 강하 → 시스템 불안정 → 필수)
- 브레드보드 + 점퍼선 (MCP2515 ↔ 라즈베리파이 SPI 핀 11개 배선 연결용)

**⑥ 예비비 ▶ 25,000원**
- 부품 손상 대비, 추가 실험 소모품

> **총 예산 합계 : 300,000원**

---

### 소프트웨어 및 개발 도구

| 분류 | 도구 | 용도 및 선택 이유 |
|------|------|-------------------|
| **언어** | C++17 | Node A BSW/ECU 계층 구현 (차량 임베디드 SW 표준 언어) |
| | Python 3.10 | 보안 공격 시뮬레이터, ML IDS 개발 (빠른 프로토타이핑에 최적) |
| | Java / Kotlin | Android HAL, Service, 대시보드 앱 (AOSP 공식 개발 언어) |
| **빌드** | CMake 3.25+ | C++ 프로젝트 크로스플랫폼 빌드 |
| | Gradle | Android AOSP 및 앱 빌드 |
| | Docker (ARM64) | 크로스컴파일 환경 컨테이너화 (개발 PC → RPi4 ARM64 타겟 빌드) |
| **CI/CD** | GitHub Actions | 코드 Push 시 자동 빌드/테스트/배포 |
| | cppcheck | C++ 정적 코드 분석 (잠재적 버그 검출) |
| | lcov / gcov | 코드 커버리지 측정 (라인/브랜치) |
| | Codecov | 커버리지 리포트 자동 시각화 |
| **통신 분석** | can-utils | CAN 버스 메시지 송수신 CLI 도구 (candump, cansend, cansniffer) |
| | python-can | Python에서 CAN 프레임 생성/수신 |
| | Scapy | 네트워크 패킷 조작 (공격 시뮬레이터) |
| **ML** | scikit-learn | Isolation Forest 이상 탐지 모델 |
| | NumPy / Pandas | 데이터 전처리 및 특징 추출 |
| **Android** | AOSP (Android 13) | RPi4 포팅용 Android 오픈소스 |
| | Android Studio | 앱 개발 및 adb 디버깅 |
| **버전관리** | Git / GitHub | 소스코드 관리, PR 기반 코드 리뷰 |

---

## 3.2. 시스템 구조

### 전체 시스템 구성도

```
◀ 팀원A 담당 영역 ▶                        ◀ 팀원B 담당 영역 ▶
┌──────────────────────────────┐           ┌───────────────────────────────┐
│  [Node A]  차량 ECU          │           │  [Node B]  차량 IVI            │
│  Ubuntu 22.04 / C++17        │           │  Android 13 AOSP / Java/Kotlin │
│                              │           │                               │
│  ┌──────────────────────┐    │           │  ┌─────────────────────────┐  │
│  │  Application Layer   │    │           │  │  Android App Layer      │  │
│  │                      │    │           │  │  ┌───────────────────┐  │  │
│  │  ┌────────────────┐  │    │           │  │  │ 대시보드 앱       │  │  │
│  │  │ BMS Component  │  │    │           │  │  │ (Jetpack Compose) │  │  │
│  │  │ · EKF SOC 추정 │  │    │           │  │  │ · SOC 게이지      │  │  │
│  │  │ · SOH 계산     │  │    │           │  │  │ · 공격 경보 배너  │  │  │
│  │  │ · Fail-safe 판단│  │    │           │  │  │ · Fail-safe 표시  │  │  │
│  │  └───────┬────────┘  │    │           │  │  └────────┬──────────┘  │  │
│  │          │ (이벤트발행)│   │           │  │           │ (StateFlow) │  │
│  └──────────┼────────────┘   │           │  └───────────┼─────────────┘  │
│             │                │           │              │                │
│  ┌──────────▼────────────┐   │           │  ┌───────────▼─────────────┐  │
│  │  ara::com (RTE 계층)  │   │           │  │  Android Framework      │  │
│  │  · Pub/Sub 이벤트     │   │           │  │  VehicleDataService     │  │
│  │  · 런타임 서비스 발견 │   │           │  │  (SystemService, Binder)│  │
│  └──────────┬────────────┘   │           │  └───────────┬─────────────┘  │
│             │                │           │              │ (Binder IPC)   │
│  ┌──────────▼────────────┐   │  CAN Bus  │  ┌───────────▼─────────────┐  │
│  │  BSW Layer            │   │◄─────────►│  │  Vehicle HAL (HIDL/C++) │  │
│  │                       │   │ HMAC 인증 │  │  · CAN 프레임 수신/파싱 │  │
│  │  ┌─────────────────┐  │   │           │  │  · HIDL 콜백 Push 방식  │  │
│  │  │ CAN CDD 드라이버│  │   │           │  └───────────┬─────────────┘  │
│  │  │ (SocketCAN 기반)│  │   │           │              │                │
│  │  ├─────────────────┤  │   │           │  ┌───────────▼─────────────┐  │
│  │  │ SecOC HMAC 모듈 │  │   │           │  │  ML IDS 엔진 (Python)   │  │
│  │  ├─────────────────┤  │   │           │  │  · CAN 트래픽 특징 추출 │  │
│  │  │ WatchdogManager │  │   │           │  │  · Isolation Forest 탐지│  │
│  │  └────────┬────────┘  │   │           │  └─────────────────────────┘  │
│  └───────────┼────────────┘   │           │                               │
│              │                │           │  ┌─────────────────────────┐  │
│   ┌──────────▼──────────┐     │           │  │  CI/CD 파이프라인       │  │
│   │  Linux SocketCAN    │     │           │  │  (Docker + GH Actions)  │  │
│   │  (can0 인터페이스)  │     │           │  └─────────────────────────┘  │
│   └──────────┬──────────┘     │           │                               │
│    [MCP2515 모듈]             │           │        [MCP2515 모듈]         │
└──────────────┬────────────────┘           └───────────────┬───────────────┘
               │                                             │
               └───────────── CAN 버스 (120Ω 종단저항) ──────┘
```

---

### 핵심 설계 원칙 3가지

**① 계층 분리 원칙 (Separation of Concerns) — BSW 직무 핵심 역량**

- 목적: "HW가 바뀌어도 Application 코드는 수정하지 않는다"
- 적용 방식:
  - BSW 계층이 MCP2515 CAN 칩의 레지스터, 인터럽트 등 HW 세부사항을 캡슐화
  - 상위 BMS 컴포넌트는 "CAN 프레임 보내줘"만 호출, HW 교체 시 BSW만 수정
  - 현업 비유: 삼성 스마트폰 앱이 카메라 제조사(삼성/소니)를 몰라도 되는 것처럼

**② 인터페이스 우선 설계 (Interface-First Design) — 2인 병렬 개발 핵심**

- 목적: "1개월차에 인터페이스를 확정하고, 이후 각자 독립 개발로 충돌을 없앤다"
- 적용 방식:
  - CAN 메시지 ID, 데이터 레이아웃, HAL API 명세를 docs/ICD.md로 먼저 작성
  - 인터페이스 확정 후 팀원A는 Node A, 팀원B는 Node B를 독립 개발
  - 인터페이스 변경 시 반드시 PR + 협의로 관리

**③ 보안 내재화 (Security by Design) — 사이버보안 역량 어필**

- 목적: "보안을 나중에 덧붙이는 것이 아니라 통신 설계 단계에서부터 적용한다"
- 적용 방식:
  - CAN 메시지 전송 시 HMAC-SHA256 서명을 기본으로 첨부
  - 수신측에서 서명 검증 실패 시 메시지 폐기로 스푸핑/재전송 공격 원천 차단
  - ISO 21434 TARA 방법론으로 위협을 체계적으로 식별하고 문서화

---

### AOSP 포팅 리스크 대비 — Plan B 전략 (신규)

> RPi4에 Android 13 AOSP를 포팅하고 그 위에 커스텀 HAL까지 올리는 작업은 가장 큰 기술적 리스크이다. AOSP 빌드 자체가 200GB+ 디스크와 16GB+ RAM을 요구하고, RPi4용 디바이스 트리 설정에서 예상치 못한 문제가 많이 발생한다.

**Plan B: Ubuntu + D-Bus/gRPC 미들웨어 + Qt/Flutter 대시보드**

- Node B도 Ubuntu 22.04로 구성하되, Android HAL 대신 D-Bus 또는 gRPC 기반 미들웨어로 동일한 계층 분리 개념을 구현
- 프론트엔드는 Qt 또는 Flutter 기반 대시보드로 대체
- 핵심 아키텍처(HAL 추상화 → Service 계층 → UI 분리)는 동일하게 유지
- **전환 판단 시점**: 2개월차(7월) 말까지 AOSP 기본 부팅에 성공하지 못하면 Plan B로 전환

이를 통해 AOSP 포팅이 지연되더라도 핵심 아키텍처 시연과 직무 어필은 가능하다.

---

## 3.3. 주요 기능

### 기능 1. AUTOSAR 계층 구조 기반 ECU 노드 — [⚙️ BSW/CDD, 🔋 BMS 직무]

**【 BSW 직무 직결 이유 】**
AUTOSAR BSW/CDD 직무 면접에서 가장 많이 받는 질문은 "CDD를 왜 쓰는가", "AUTOSAR 계층이 왜 분리되어 있는가"이다. 본 기능은 이 질문에 대한 답을 코드로 직접 구현한 경험으로 대답할 수 있게 해준다.

**[1-A] CAN CDD (Complex Device Driver) — BSW 계층 핵심**

- 목적: MCP2515 CAN 칩의 HW 세부사항을 BSW 경계 안에 완전히 캡슐화
- 구현:
  - Linux SocketCAN API(PF_CAN, SOCK_RAW)를 통해 can0 인터페이스에 접속
  - CAN 프레임 구조체: ID(11bit), DLC(데이터 길이 0~8), 8바이트 페이로드
  - 비동기 수신 스레드: 별도 스레드에서 상시 대기 → 프레임 도착 시 콜백 호출
  - 추상 인터페이스 설계: 칩 교체 시 CDD 구현체만 교체, 상위 코드 무수정 보장
- 면접 어필:
  "CAN CDD를 직접 구현했습니다. 추상 인터페이스를 먼저 설계하여 Application Layer가 MCP2515 칩의 존재를 모르도록 설계했고, 이 덕분에 팀원B의 Android HAL과 완전히 독립적으로 개발할 수 있었습니다."

**[1-B] ara::com Pub/Sub 서비스 인터페이스 — AUTOSAR Adaptive 핵심**

- 목적: AUTOSAR Adaptive의 핵심인 런타임 서비스 연결 방식을 직접 구현
- 구현:
  - Publisher\<T\> 템플릿 클래스: BMS 계산 결과를 구독자 전원에게 자동 전달
  - Subscriber 패턴: 관심 있는 데이터만 선택적으로 수신 등록
  - std::mutex + lock_guard: 다중 스레드 동시 접근 시 데이터 손상 방지
- Classic vs Adaptive 비교 경험:
  Classic은 컴파일 타임에 연결 확정(정적), Adaptive는 런타임에 서비스 발견(동적) → 이 차이를 코드로 구현하며 체감한 경험이 면접에서 강력한 어필 포인트가 됨

**[1-C] BMS SW 컴포넌트 — BMS Application SW 직무 핵심**

- 목적: 배터리 관리 시스템의 핵심 알고리즘을 직접 구현하고 정확도 검증

**SOC(State of Charge, 배터리 잔량) 추정 — Extended Kalman Filter (EKF):**
- 단순 방법(쿨롱 카운팅): 전류를 시간으로 적분 → 센서 드리프트로 오차 누적
- EKF 방법: 전류 적분(예측) + OCV-SOC 관계식(보정)을 칼만 필터로 융합 → 장기 운행 시에도 오차가 발산하지 않는 정확한 추정 가능
- 예측 단계: SOC_pred = SOC_prev - (I × dt) / Q_capacity
- 업데이트: K(칼만 게인) 계산 → SOC 보정 → 오차 공분산(P) 갱신
- 검증: 단순 쿨롱 카운팅 대비 장기 누적 오차 감소율을 수치로 측정·비교
- **(개선) 실측 배터리 데이터셋 기반 시뮬레이션**: NASA Battery Dataset 또는 CALCE 데이터 등 공개된 배터리 데이터셋을 활용하여 실측 충방전 프로파일을 CAN 버스로 재생(replay)하는 방식으로 시뮬레이션함으로써, EKF 정확도 검증 결과의 현실적 신뢰성을 확보한다.

**SOH(State of Health, 배터리 건강도) 추정:**
- 누적 방전량 기반 용량 열화 계산 (초기 용량 대비 현재 용량 비율)

**Fail-safe 상태머신:**
- 4단계: NORMAL → WARNING → CRITICAL → SHUTDOWN
- 전이 조건 1: SOC < 5% → 방전 위험, 방전 차단 명령 CAN 전송
- 전이 조건 2: 온도 > 60°C → 과열, 충방전 전류 제한 명령 전송
- 상태 전이 이벤트를 CAN ID 0x101로 Node B에 실시간 통보

---

### 기능 2. Android IVI 미들웨어 플랫폼 — [📱 IVI SW 플랫폼 직무]

**【 IVI 직무 직결 이유 】**
IVI SW 플랫폼 직무 면접에서 "앱 개발자"와 "플랫폼 엔지니어"를 구분하는 기준은 HAL 이하 계층 경험이다. 본 기능은 HAL부터 앱까지 전 스택을 직접 구현하여 "플랫폼 엔지니어" 수준의 포트폴리오를 제공한다.

**[2-A] Vehicle HAL (Hardware Abstraction Layer) — IVI 플랫폼 가장 핵심**

- 목적: CAN 버스에서 오는 차량 데이터를 Android 생태계로 끌어올리는 관문
- 현실 비유: 외국산 상품(CAN 데이터)이 세관(HAL)을 통과하여 국내 규격(Android API)으로 변환되어 국내 소비자(앱)가 쓸 수 있게 됨
- 구현:
  - HIDL(Hardware Interface Definition Language)로 인터페이스 정의
    - IVehicleHal.hal 파일: getVehicleData(), registerCallback() 메서드 명세
    - VehicleData 구조체: SOC, SOH, 전압, 전류, 온도, failSafe, attackDetected
  - C++ HAL 구현체: CAN 수신 스레드 상시 대기 → 데이터 도착 시 즉시 파싱
  - CAN ID별 파싱 처리:
    - 0x100 (BMS 상태): SOC, SOH, 전압, 전류, 온도 디코딩
    - 0x101 (Fail-safe 이벤트): 상태머신 전이 정보 파싱
    - 0x200 (보안 이벤트): ML IDS 탐지 결과 수신
  - Push 방식 콜백: 새 데이터 도착 시 등록된 모든 콜백에 즉시 통보
- 면접 어필:
  "Android 앱이 아닌 HAL 레이어부터 직접 구현했습니다. CAN 데이터를 HIDL로 추상화하고, VehicleService가 Binder IPC로 상위 앱에 전달하는 전체 파이프라인을 직접 작성한 경험이 있습니다."

**[2-B] VehicleDataService (Android SystemService)**

- 목적: HAL에서 받은 데이터를 모든 앱이 표준 API로 접근할 수 있게 제공
- 현실 비유: 차량 상태 데이터의 "우체국" — 누가 요청해도 최신 데이터를 배달
- 구현:
  - Android SystemService로 등록: getSystemService("vehicle_data")로 앱 접근
  - HAL 콜백 → Binder IPC → 앱 ViewModel의 StateFlow 업데이트
  - 주요 API:
    - getCurrentData(): 현재 차량 상태 즉시 조회
    - observeVehicleData(callback): 실시간 변화 구독 등록

**[2-C] 차량 대시보드 Android 앱 (Jetpack Compose)**

- 목적: 운전자가 차량 상태를 직관적으로 확인할 수 있는 실시간 UI
- 구현:
  - SOC 게이지: 원형 프로그레스바 + 색상 코드
    - 50% 이상 → 초록 (정상)
    - 20~50% → 주황 (주의)
    - 20% 미만 → 빨강 (위험)
  - 보안 공격 탐지 경보:
    - 공격 탐지 시 상단에 빨간 경보 배너 애니메이션으로 등장
    - 공격 유형 텍스트 표시: "⚠ Spoofing Attack Detected!"
    - 탐지 시각, 의심 CAN ID 로그에 기록
  - Fail-safe 상태 인디케이터:
    - CRITICAL/SHUTDOWN 상태 시 풀스크린 경고 팝업
  - 실시간 반영:
    - StateFlow + collectAsState()로 100ms 주기 CAN 데이터 지연 없이 표시

---

### 기능 3. CAN 보안 통신 + ML 기반 IDS — [⚙️ BSW 보안 역량 + 🔐 보안 직무]

**【 BSW 직무에서 보안 역량이 중요한 이유 】**
UN R-155 의무화 이후 BSW 개발자도 SecOC(Secure On-Board Communication) 구현 역량이 요구되고 있다. 단순히 CAN 드라이버를 작성하는 것을 넘어 "보안이 내재된 통신 계층"을 설계할 수 있는 능력이 차별점이 된다.

**[3-A] SecOC HMAC-SHA256 인증 모듈 — BSW 계층 보안 통신**

- 동작 원리:

```
[송신 Node A]                        [수신 Node B]
CAN 데이터                            수신 페이로드
  + CAN ID           HMAC 계산          → 데이터 + MAC 분리
  + 롤링 카운터  →   SHA256 해시    →   → MAC 재계산
  = HMAC 입력        앞 4바이트 추출    → 수신 MAC vs 재계산 MAC
                    데이터 + MAC 전송    → 일치: 수신 허용
                                          불일치: 메시지 폐기 ✓
```

- 롤링 카운터: 메시지마다 1씩 증가 → Replay 공격 방어 (동일 메시지를 재전송해도 카운터 불일치로 인증 실패)
- 타이밍 공격 방지: hmac.compare_digest() 사용 (일반 == 비교는 앞 바이트 일치 여부에 따라 처리 시간이 달라 해커가 MAC 값을 유추하는 타이밍 공격이 가능하기 때문)

**[3-B] 4종 CAN 공격 시뮬레이터 (python-can + Scapy)**

**공격 1 — Fuzzy Attack (퍼징 공격)**
- 방법: 무작위 CAN ID와 무작위 8바이트 페이로드로 수천 개 메시지 전송
- 목적: ECU SW의 입력 검증 취약점 탐색, 예외 처리 미비 시 ECU 오작동 유발
- 실험: 공격 중 Node A Fail-safe 로직이 정상 동작하는지 검증

**공격 2 — Replay Attack (재전송 공격)**
- 방법: 정상 BMS 메시지를 캡처한 뒤 동일 메시지를 반복 재전송
- 목적: 과거 SOC 데이터를 주입하여 IVI 화면에 오정보 표시 유도
- 실험: HMAC 롤링 카운터 없을 때 vs 있을 때 공격 성공/실패 비교

**공격 3 — Spoofing Attack (스푸핑/위조 공격)**
- 방법: BMS CAN ID(0x100)로 SOC = 99%라는 가짜 데이터를 전송
- 목적: IVI 화면에 배터리가 거의 꽉 찬 것처럼 오정보 표시 유도
- 실험: HMAC 인증 없을 때 위조 성공, 있을 때 위조 실패 비교 수치화

**공격 4 — Flooding Attack (버스 포화 공격)**
- 방법: 동일 CAN ID로 최대 속도(~10,000 msg/sec) 반복 전송
- 목적: CAN 버스 우선순위 구조를 악용하여 정상 BMS 메시지 전달 방해
- 실험: 공격 중 정상 BMS 메시지의 전달 지연 시간(ms) 측정

**(개선) Ablation Study 기반 보안 실험 설계 (신규)**

> 보안 실험의 학술적 가치를 높이기 위해, 4종 공격 실험을 다음 3가지 방어 구성에서 동일하게 수행하여 각 방어 계층의 독립적 기여도를 정량적으로 비교한다.

| 실험 구성 | SecOC HMAC | ML IDS | 측정 항목 |
|-----------|:----------:|:------:|-----------|
| 구성 1: 방어 없음 | ✗ | ✗ | 공격 성공률 (baseline) |
| 구성 2: SecOC만 | ✓ | ✗ | 위변조 차단율, 통과된 공격 비율 |
| 구성 3: SecOC + IDS | ✓ | ✓ | 최종 탐지율, 오탐율, 레이턴시 |

이를 통해 "SecOC만으로 Spoofing/Replay는 100% 차단되지만 Flooding은 차단 불가 → IDS가 Flooding을 보완한다"는 식의 계층별 방어 효과를 수치로 입증하며, 학술대회 제출 시에도 강력한 실험 설계가 된다.

**[3-C] ML 기반 IDS — Isolation Forest (비지도 학습)**

- 현실 비유: 은행 CCTV가 평소와 다른 행동 패턴을 감지하듯, IDS는 정상 CAN 트래픽 패턴을 학습한 뒤 이상 패턴을 잡아낸다.
- 동작 방식:
  - 학습: 정상 운행 CAN 트래픽 데이터로 "정상 모델" 학습
  - 탐지: 새 트래픽이 정상 모델에서 얼마나 벗어났는지 이상 점수 계산
  - 판정: 점수가 임계값 초과 시 → 공격으로 판정, Android에 경보 전송
- 특징 벡터 (CAN 1초 슬라이딩 윈도우 기준):
  - ID 평균값, 표준편차 (Flooding이면 표준편차 ≈ 0 → 쉽게 탐지)
  - 메시지 간격 평균/표준편차 (정상 CAN은 주기적 → 불규칙이면 이상)
  - 1초 내 총 메시지 수 (정상 대비 급증이면 Flooding 의심)
  - 페이로드 평균/표준편차 (Fuzzy 공격은 랜덤값 → 표준편차 급증)

**[3-D] ISO 21434 기반 TARA 문서 작성**

- 자산(Asset) 식별: BMS 제어 명령, SOC 데이터, Fail-safe 트리거
- 위협 모델링: STRIDE 프레임워크 적용 (Spoofing / Tampering / Repudiation / Info Disclosure / DoS / EoP)
- Attack Feasibility 계산: 각 위협을 4요소로 수치화
  - Elapsed Time (공격 준비 시간), Expertise (필요 기술 수준)
  - Knowledge (내부 지식 필요 여부), Window of Opportunity (접근 난이도)
- Risk Level: Feasibility × Impact → High / Medium / Low / Negligible

---

### 기능 4. CI/CD 자동화 파이프라인 — [🔄 CI/CD + 전 직무]

**【 CI/CD가 BSW·IVI 직무 어필에도 중요한 이유 】**
A-SPICE SWE.4는 SW 단위 검증을 요구한다. CI 파이프라인으로 커버리지를 자동 측정하고 품질 게이트를 통과시키는 경험은 BSW/IVI 지원자 모두에게 "코드 품질을 관리하며 개발했다"는 신뢰도 높은 어필 포인트가 된다.

**[4-A] Docker 기반 ARM64 크로스컴파일 환경**

- 문제: 개발 PC(x86_64 CPU)에서 라즈베리파이(ARM64 CPU)용 코드를 빌드하려면 크로스컴파일러(aarch64-linux-gnu-gcc)가 필요하다.
- 해결: Dockerfile에 크로스컴파일러 설치를 명시 → 컨테이너화. 어느 PC(Mac/Windows/Linux)에서도 동일한 빌드 환경 보장
- cmake toolchain-aarch64.cmake: 컴파일러 경로, 타겟 시스템 정보 명시

**[4-B] GitHub Actions 4단계 자동화 파이프라인**

- 트리거: main / develop 브랜치 Push 또는 PR 생성 시 자동 실행

**Stage 1 | 정적 분석 (cppcheck)**
- C++ 코드에서 메모리 누수, 미초기화 변수, 범위 초과 등 자동 검출
- 오류 발견 시 파이프라인 즉시 중단 → 불량 코드가 다음 단계로 진행 불가

**Stage 2 | ARM64 크로스컴파일 빌드**
- Docker 컨테이너에서 라즈베리파이용 바이너리 생성
- 빌드 성공 시 바이너리를 GitHub Artifact로 보관

**Stage 3 | 단위 테스트 + 커버리지 측정**
- CMake CTest + GoogleTest 프레임워크로 단위 테스트 실행
- gcov / lcov로 코드 커버리지 측정 → Codecov에 자동 리포트
- **(개선) QEMU user-mode 에뮬레이션**: Docker 컨테이너 내에 QEMU user-mode를 세팅하여 크로스컴파일된 ARM64 바이너리를 GitHub Actions 러너(x86)에서 직접 실행·테스트 가능하게 한다. 이를 통해 "실제 타겟 아키텍처에서 테스트까지 CI에서 자동화했다"는 어필이 가능해진다.
- 품질 게이트 기준 (A-SPICE SWE.4 참조):
  - Statement Coverage: 80% 이상
  - Branch Coverage (Fail-safe 안전 로직): 100% 필수
  - cppcheck Critical/Error 건수: 0건

**Stage 4 | 라즈베리파이 자동 배포 (main 브랜치만 실행)**
- SSH 키를 GitHub Secret으로 안전하게 보관
- SCP로 바이너리 전송 → SSH로 서비스 재시작 명령 자동 실행
- 배포 후 Health Check: 서비스 정상 기동 여부 자동 확인

---

## 3.4. 개발 방법

**① 인터페이스 우선 설계 (Interface-First) — 2인 병렬 개발의 충돌 방지 핵심**

1개월차에 CAN 메시지 ID, 데이터 레이아웃, HAL API, 콜백 시그니처를 docs/ICD.md로 문서화 후 확정. 인터페이스 확정 이후 각자 독립 구현을 시작한다. 인터페이스 변경 시 반드시 GitHub PR + 상호 협의 후 반영한다.

**② Git 브랜치 전략**

```
main ← develop ← feature/bsw-can-driver     (팀원A)
               ← feature/bms-ekf             (팀원A)
               ← feature/secoc-hmac          (팀원A)
               ← feature/ml-ids              (팀원A)
               ← feature/android-hal         (팀원B)
               ← feature/vehicle-service     (팀원B)
               ← feature/dashboard-app       (팀원B)
               ← feature/cicd-pipeline       (팀원B 주도, 공동)
```

각 기능 → feature 브랜치 개발 → PR 생성 → 상대방 코드 리뷰 → develop 머지.
develop → main 머지는 CI 파이프라인 전체 통과 필수.

**③ 주 2회 동기화 미팅 (30분, 비대면 가능)**
- 진행 현황 공유, 인터페이스 변경 협의, 통합 이슈 조기 발견
- GitHub Issues로 할 일 관리, Milestone으로 월별 목표 추적

**④ A-SPICE 프로세스 참조 산출물 관리**

| 문서 | 내용 | 담당 |
|------|------|------|
| docs/SRS.md | SW 요구사항 명세서 | 공동 작성 |
| docs/ICD.md | CAN 메시지 ID / HAL API 인터페이스 명세 | 공동 작성 |
| docs/SDD-ECU.md | ECU 모듈 SW 상세 설계 | 팀원A 작성 |
| docs/SDD-IVI.md | IVI 모듈 SW 상세 설계 | 팀원B 작성 |
| docs/TARA.md | ISO 21434 위협 분석 문서 | 팀원A 주도, 팀원B 검토 |
| **(신규)** docs/ADR.md | Architecture Decision Records (기술 선택 근거 기록) | 공동 작성 |

> **(개선) ADR(Architecture Decision Records) 추가**: "왜 Isolation Forest를 선택했는가(vs Autoencoder, vs Rule-based)", "왜 HIDL을 선택했는가(vs AIDL)" 같은 의사결정 근거를 ADR 형식으로 기록하여, 면접에서 "왜 이 기술을 선택했나요?"라는 질문에 체계적으로 답할 수 있게 한다. A-SPICE 프로세스 경험도 더 두텁게 어필 가능.

**⑤ 검증 방법 요약**
- 단위 테스트: GoogleTest — 각 함수 단위 입출력 검증
- 통합 테스트: CAN 실물 연결, Node A → Node B end-to-end 시나리오
- 보안 테스트: 4종 공격 각 100회 수행, 탐지율/오탐율 측정 (3가지 방어 구성별 ablation study)
- 성능 테스트: CAN 수신 → Android UI 반영 end-to-end 레이턴시 측정. 목표: 평균 50ms 이하 / 최대 100ms 이하

---

# 4. 구성원 역할 분담

## 2인 팀 분담 전략

핵심 전략: 팀원A는 "차량 ECU 하위 계층(BSW)"을, 팀원B는 "차량 IVI 상위 계층"을 각각 수직으로 담당하여, 같은 시스템을 함께 만들되 서로 다른 직무로 지원한다.

- **팀원A** → ⚙️ BSW/CDD 직무 또는 🔋 BMS Application SW 직무 지원
- **팀원B** → 📱 IVI SW 플랫폼 직무 지원 (CI/CD 역량도 병행 어필)

---

### 팀원A : [성명]

**담당 직무 포지션 : ⚙️ AUTOSAR BSW/CDD + 🔋 BMS Application SW**

**【 담당 역할 1 】 AUTOSAR 계층 기반 ECU 노드 (Node A) 전체 구현**

- CAN CDD 드라이버 설계 및 구현 (Linux SocketCAN 기반, C++17)
  - PF_CAN / SOCK_RAW 소켓 기반 can0 인터페이스 초기화 및 접속
  - CAN 프레임 송수신 + 비동기 수신 콜백 등록 구현
  - 추상 인터페이스(CanDriver 클래스) 설계로 HW 교체 시 상위 무수정

- ara::com Publisher/Subscriber 경량 구현 (C++17 템플릿)
  - Publisher\<T\> 템플릿: Send() 호출 시 등록된 모든 Subscriber에 전달
  - std::mutex 기반 스레드 안전 설계
  - AUTOSAR Adaptive 동적 서비스 발견 원리를 직접 코드로 구현

- BMS SW 컴포넌트 개발
  - Extended Kalman Filter SOC 추정 알고리즘 구현 + 정확도 검증
  - **(개선)** NASA Battery Dataset / CALCE 등 실측 배터리 데이터 기반 시뮬레이션으로 EKF 정확도 검증의 현실적 신뢰성 확보
  - SOH 추정: 누적 방전량 기반 배터리 용량 열화 계산
  - Fail-safe 상태머신: Normal/Warning/Critical/Shutdown 4단계
  - CAN 메시지 ID 정의 및 데이터 인코딩 규격 문서화 (ICD.md)

**【 담당 역할 2 】 차량 사이버보안 구현**

- SecOC HMAC-SHA256 인증 모듈 구현 (Python 프로토타입 → C++ 이식)
  - 롤링 카운터 기반 Replay 공격 방어
  - hmac.compare_digest()로 타이밍 공격 방지

- 4종 CAN 공격 시뮬레이터 개발 (python-can + Scapy)
  - Fuzzy / Replay / Spoofing / Flooding Attack 각각 구현
  - 터미널 인자로 공격 유형 선택 가능한 CLI 인터페이스 제공

- Isolation Forest 기반 ML IDS 구현 (scikit-learn)
  - 정상 트래픽 데이터셋 수집 및 모델 학습
  - 1초 슬라이딩 윈도우 기반 실시간 특징 추출 및 이상 점수 계산
  - **(개선)** 3가지 방어 구성별 ablation study 실험 수행 (방어 없음 / SecOC만 / SecOC+IDS)
  - 공격 유형별 탐지율/오탐율 측정 실험 수행 (각 공격 100회 반복)

- ISO 21434 기반 TARA 문서 작성
  - 자산 식별, STRIDE 위협 모델링, Attack Feasibility 4요소 계산
  - Risk Level 결정: High/Medium/Low/Negligible

**【 담당 산출물 】**
- adaptive_ecu/ 전체 소스코드 (C++17)
- security/ 전체 소스코드 (Python)
- docs/SDD-ECU.md (ECU 모듈 SW 상세 설계 문서)
- docs/TARA.md (ISO 21434 위협 분석 및 위험 평가 문서)
- **(신규)** docs/ADR.md 중 ECU·보안 관련 기술 선택 근거 기록
- 실험 보고서: EKF 정확도 비교 그래프, 공격별 탐지율/오탐율 표 (ablation study 포함)

---

### 팀원B : [성명]

**담당 직무 포지션 : 📱 IVI SW 플랫폼 + 🔄 CI/CD 자동화**

**【 담당 역할 1 】 Android IVI 미들웨어 플랫폼 (Node B) 전체 구현**

- AOSP Android 13 Raspberry Pi 4 포팅 및 빌드
  - RPi4 전용 디바이스 트리(Device Tree) 설정
  - MCP2515 CAN 드라이버 커널 모듈 통합
  - AOSP 빌드 환경 구성 (최소 200GB 디스크, 16GB RAM 권장)
  - **(개선)** 2개월차 말까지 부팅 실패 시 Plan B(Ubuntu + D-Bus/gRPC + Qt/Flutter) 전환 판단

- Vehicle HAL 구현 (HIDL, C++)
  - IVehicleHal.hal 인터페이스 파일 정의
  - CAN 수신 스레드 + HIDL 콜백 Push 구조 구현
  - CAN ID(0x100, 0x101, 0x200)별 VehicleData 파싱 처리

- VehicleDataService 개발 (Android SystemService, Java)
  - SystemService 등록: getSystemService("vehicle_data") 접근 가능
  - Binder IPC 기반 앱-서비스 간 실시간 데이터 전달 구조

- 차량 대시보드 앱 개발 (Jetpack Compose, Kotlin)
  - SOC 게이지 (색상 코드: 초록/주황/빨강)
  - 보안 공격 경보 배너 (탐지 시 즉시 애니메이션 등장)
  - Fail-safe 상태 표시, 실시간 전압/전류/온도 데이터
  - StateFlow + collectAsState()로 100ms 주기 데이터 지연 없이 반영

**【 담당 역할 2 】 CI/CD 파이프라인 및 시스템 통합**

- Docker ARM64 크로스컴파일 환경 구축
  - Dockerfile.arm64: aarch64-linux-gnu 툴체인 컨테이너화
  - CMake toolchain-aarch64.cmake 작성
  - **(개선)** QEMU user-mode 에뮬레이션 세팅으로 CI에서 ARM64 바이너리 직접 테스트 가능

- GitHub Actions 4단계 파이프라인 구현
  - cppcheck 정적분석 → ARM64 빌드 → CTest+lcov 테스트 → SSH 배포
  - 품질 게이트 설정: Statement 80%, Fail-safe Branch 100%

- 시스템 통합 테스트 환경 구성
  - Node A ↔ Node B CAN 실물 연결 end-to-end 통신 검증
  - 레이턴시 측정 스크립트 작성 (CAN 수신 → Android UI 반영 시간)

**【 담당 산출물 】**
- ivi_platform/ 전체 소스코드 (Java/Kotlin/C++)
- .github/workflows/ci.yml (CI/CD 파이프라인 전체)
- Dockerfile.arm64, toolchain-aarch64.cmake
- docs/SDD-IVI.md (IVI 모듈 SW 상세 설계 문서)
- **(신규)** docs/ADR.md 중 IVI·CI/CD 관련 기술 선택 근거 기록
- GitHub README.md (시스템 설명, 빌드 방법, 실험 결과 전체)

---

### 공동 담당 항목

- docs/ICD.md : CAN 메시지 규격 + HAL API 인터페이스 명세 (1개월차)
- docs/SRS.md : SW 요구사항 명세서 (1개월차)
- **(신규)** docs/ADR.md : Architecture Decision Records (기술 선택 시점마다 수시 작성)
- 5~6개월차 통합 테스트 디버깅 및 성능 최적화
- 7~8개월차 완성도 향상, 실험 보완, 문서 최종화
- 최종 발표 자료 및 최종 보고서

---

# 5. 개발 추진 일정

**(개발기간 : 2026년 6월 1일 ~ 2027년 1월 31일, 총 8개월)**

| 기간 | 팀원A (ECU / BSW / 보안) | 팀원B (IVI / CI/CD) |
|------|--------------------------|---------------------|
| **1개월차 (6월)** | · 라즈베리파이 Ubuntu 22.04 셋업 | · AOSP 빌드 환경 구성 |
| **[환경 구축 + 설계]** | · SocketCAN 기초 loopback 테스트 | · Docker 크로스컴파일 환경 초기 구축 |
| | · CAN CDD 추상 인터페이스 설계 | · GitHub 레포 브랜치 전략 설정 |
| | · ara::com 구조 설계 | |
| | **── 공동: 아키텍처 확정, CAN 메시지 규격 + HAL API 명세 (docs/ICD.md, docs/SRS.md) 작성 완료 ──** | |
| | **이 시점 이후 각자 독립 개발 시작** | |
| **2개월차 (7월)** | · CAN CDD 드라이버 구현 완성 (can0 실제 송수신 확인) | · AOSP RPi4 기본 부팅 성공 **(실패 시 Plan B 전환 판단)** |
| **[핵심 기능 1차]** | · ara::com Pub/Sub 구현 + 단위 테스트 통과 | · Vehicle HAL 뼈대 구현 (HIDL 인터페이스 정의) |
| | · BMS 데이터 CAN 전송 확인 (candump으로 수신 검증) | · GitHub Actions 기초 CI (빌드 자동화만) |
| | · NASA/CALCE 배터리 데이터셋 분석 및 전처리 | |
| **3개월차 (8월)** | · EKF SOC 추정 구현 + 실측 데이터 기반 검증 (쿨롱 카운팅 대비 정확도 측정) | · HAL CAN 수신 스레드 완성 + 콜백 동작 확인 |
| **[핵심 기능 2차]** | · Fail-safe 상태머신 구현 + 단위 테스트 Branch 100% 달성 | · VehicleDataService 구현 |
| | · SecOC HMAC 모듈 구현 | · 대시보드 앱 기본 UI 완성 (SOC 게이지) |
| | · 공격 시뮬레이터 v1 개발 (Fuzzy, Flooding 우선) | · 단위 테스트 + 커버리지 자동화 추가 |
| | | · QEMU user-mode 에뮬레이션 CI 통합 |
| **4개월차 (9월)** | · Isolation Forest IDS 학습 + 탐지 모델 기본 검증 | · Node A↔B CAN 실물 연결 end-to-end 통신 완성 |
| **[1차 통합]** | · 4종 공격 실험 수행 + 탐지율/오탐율 1차 측정 | · 보안 경보 배너 Android UI 연동 완성 |
| | · TARA 문서 v1 작성 | · SSH 자동 배포 파이프라인 완성 |
| | **── 공동: 전체 시스템 1차 통합 테스트 + 버그 수정 (핵심 마일스톤) ──** | |
| **5개월차 (10월)** | · Ablation study 실험 수행 (3가지 방어 구성별 비교) | · 레이턴시 측정 + 1차 최적화 |
| **[보안 실험 심화]** | · IDS 탐지율 최적화 (특징 튜닝) | · 대시보드 앱 UI/UX 개선 |
| | · 공격 시뮬레이터 v2 (Replay, Spoofing 정밀화) | · docs/ADR.md IVI 관련 기술 선택 기록 정리 |
| | · docs/ADR.md ECU·보안 관련 기술 선택 기록 정리 | |
| **6개월차 (11월)** | · Ablation study 결과 분석 및 비교 보고서 작성 | · end-to-end 레이턴시 최종 최적화 (목표: 평균 50ms 이하) |
| **[완성도 향상]** | · EKF 정확도 실험 결과 데이터 정리 + 그래프 작성 | · docs/SDD-IVI.md 완성 |
| | · docs/SDD-ECU.md 완성 | · GitHub README 완성 |
| | · TARA 문서 최종화 | · CI 뱃지 전체 녹색 달성 (Coverage 80% 이상) |
| **7개월차 (12월)** | · 실험 결과 종합 분석 및 재현성 검증 | · 시스템 안정성 테스트 (장시간 운행 시뮬레이션) |
| **[최종 검증 + 문서화]** | · 부족한 실험 보완 (탐지율 미달 공격 유형 재실험) | · 전체 문서 교차 검토 및 수정 |
| | · 최종 실험 보고서 작성 (ablation study 포함) | · CI/CD 파이프라인 최종 점검 |
| | **── 공동: 전체 시스템 최종 통합 테스트 + 성능 최종 검증 ──** | |
| | **── 공동: 학술대회 제출용 실험 데이터 정리 (선택) ──** | |
| **8개월차 (1월)** | **── 공동: 최종 발표 준비 + 보고서 작성 + 제출 ──** | |
| **[발표 준비]** | · 데모 시나리오 구성 및 리허설 | |
| | · 발표 자료 제작 (아키텍처 다이어그램, 실험 결과 그래프, BSW/IVI 어필 포인트, 각자 직무별 차별화 포인트 슬라이드 별도 준비) | |
| | · 최종 보고서 작성 및 제출 | |

---

### 월별 핵심 체크포인트

| 월 | 완료 조건 |
|----|-----------|
| 1개월차 (6월) | ICD.md 확정, GitHub 레포 구성, 각자 개발 환경 동작 |
| 2개월차 (7월) | CAN CDD 실 송수신 확인, HAL 뼈대 동작 (또는 Plan B 전환 결정), 기초 CI 동작 |
| 3개월차 (8월) | EKF 정확도 측정 데이터 (실측 데이터 기반), 대시보드 기본 UI, HMAC 완성, QEMU CI 통합 |
| 4개월차 (9월) | end-to-end 전체 동작 영상, 공격 탐지 실험 데이터 |
| 5개월차 (10월) | Ablation study 3가지 구성 실험 완료, IDS 최적화 완료, ADR 기록 정리 |
| 6개월차 (11월) | SDD 2종 완성, TARA 문서 최종화, CI 전체 녹색, README 완성 |
| 7개월차 (12월) | 최종 통합 테스트 통과, 실험 보고서 완성, 전체 문서 교차 검토 완료 |
| 8개월차 (1월) | 최종 보고서, 발표 자료, GitHub 최종 정리 완료 |

---

# 6. 결과 활용, 기대효과

## 【 직무 적합성 기대효과 — 팀원별 어필 포인트 】

### ■ 팀원A — ⚙️ BSW/CDD 직무 어필 포인트

| 채용 공고 요구 사항 | 본 프로젝트 경험 |
|---------------------|------------------|
| AUTOSAR BSW 설계 및 구현 | ara::com + BSW/CDD 계층 직접 구현 |
| CAN 드라이버 개발 경험 | Linux SocketCAN 기반 CDD 직접 작성 |
| 임베디드 C/C++ 역량 | C++17 기반 ECU 전 계층 구현 |
| SecOC / 보안 통신 구현 | HMAC-SHA256 인증 모듈 직접 구현 |
| ISO 21434 / TARA 이해 | TARA 문서 직접 작성 경험 |
| 단위 테스트 및 커버리지 관리 | GoogleTest + lcov CI 연동 경험 |
| **(추가)** 기술 선택 근거 설명 능력 | ADR 문서 작성으로 의사결정 과정 체계적 기록 |

**면접 핵심 멘트:**
"저는 AUTOSAR 계층 구조를 교과서가 아닌 실제 동작하는 코드로 구현했습니다. CAN CDD를 직접 설계할 때 추상 인터페이스를 먼저 확정해서 HW가 교체돼도 Application 코드는 단 한 줄도 바뀌지 않는 구조를 만들었고, 그 덕분에 팀원과 충돌 없이 병렬 개발을 완성할 수 있었습니다."

---

### ■ 팀원B — 📱 IVI SW 플랫폼 직무 어필 포인트

| 채용 공고 요구 사항 | 본 프로젝트 경험 |
|---------------------|------------------|
| Android HAL / Framework 개발 | Vehicle HAL(HIDL) + SystemService 직접 구현 |
| AOSP 빌드 및 포팅 경험 | Android 13 AOSP RPi4 포팅 경험 |
| 차량 도메인 Android 개발 | CAN 데이터를 Android로 끌어올린 경험 |
| Binder IPC 이해 | HAL → Service → App 파이프라인 직접 구현 |
| 임베디드 CI/CD 구축 | Docker 크로스컴파일 + GH Actions 파이프라인 |
| **(추가)** QEMU 에뮬레이션 테스트 | CI에서 ARM64 타겟 바이너리 직접 테스트 자동화 경험 |

**면접 핵심 멘트:**
"저는 Android 앱 개발자가 아닌 플랫폼 엔지니어로서 HAL 계층부터 직접 구현했습니다. CAN 데이터를 HIDL로 추상화하고, VehicleDataService가 Binder IPC로 앱에 전달하는 전체 파이프라인을 직접 작성했습니다. AOSP 포팅 과정에서 디바이스 트리 수정과 커널 드라이버 통합도 경험했습니다."

---

## 【 기술적 기대효과 】

**① 차량 SW 전 계층 수직 관통 경험**
BSW(하드웨어 추상화) → RTE(서비스 연결) → Application(BMS 로직) → HAL(Android 연결) → Framework(Service) → App(UI) → 보안(IDS) → CI/CD 까지 차량 SW 전 계층을 하나의 프로젝트에서 경험한다.

**② 후속 연구 확장 가능성**
- 캡스톤디자인 II 연계: OTA(Over-The-Air) 펌웨어 업데이트 기능 추가, Post-Quantum 암호화 적용 등 심화 연구로 확장 가능
- 졸업 논문 연계: EKF 기반 SOC 추정 정확도 분석 또는 CAN IDS 성능 분석 결과를 논문으로 정리하여 학술대회 제출 가능
- **(개선)** Ablation study 기반 보안 실험 결과는 학술대회 제출 시 실험 설계의 체계성을 강하게 어필 가능
- 오픈소스 공개: 후배 팀의 유사 프로젝트 참고 플랫폼으로 활용

**③ (신규) 실측 데이터 기반 검증으로 산업체 신뢰도 확보**
NASA Battery Dataset 등 공인 데이터셋 기반으로 EKF 알고리즘을 검증함으로써, 면접에서 "실제 배터리 특성이 반영된 건가요?"라는 질문에 수치 근거로 답변할 수 있는 포트폴리오를 갖춘다.

---

## 【 교육적 기대효과 】

**SW 계층 설계 사고 능력:**
"왜 BSW와 Application을 분리해야 하는가", "왜 HAL이 필요한가"를 교과서가 아닌 실제 디버깅 문제로 경험함으로써 SW 아키텍처 설계 감각을 기른다.

**협업 능력:**
인터페이스 명세 → 병렬 개발 → 코드 리뷰 → 통합 테스트의 실제 개발 사이클을 2인 팀으로 운영하며 현업 협업 방식을 체득한다.

**문제 해결 능력:**
"CAN 버스에 공격 패킷을 보냈는데 IDS가 못 잡는다", "HAL과 BSW 간 데이터 레이아웃이 맞지 않아 SOC 값이 이상하게 나온다" 와 같은 실제 통합 디버깅 상황에서 로그 분석, 패킷 캡처, 특징 튜닝 등 공학적 문제 해결 과정을 경험한다.

**(신규) 기술 의사결정 능력:**
ADR 작성을 통해 "왜 이 기술을 선택했는가"를 논리적으로 정리하는 습관을 기르며, 면접 및 실무에서 기술 선택의 근거를 체계적으로 설명하는 역량을 확보한다.

---

# [ 이 하 여 백 ]

## ※ 제출 전 교체 항목

- [학과명], [학년], [학번] → 팀원 실제 정보로 교체
- [팀원A 성명], [팀원B 성명] → 실제 이름으로 교체
- [교수님 성함] → 지도 교수님 성함으로 교체

## ※ 구현 완료 후 실측값으로 업데이트할 항목

- EKF SOC 추정 오차 개선율 (단순 쿨롱 카운팅 대비 %)
- IDS 탐지율 (공격 유형별 %, 각 100회 실험 기준)
- IDS 오탐율 (정상 트래픽이 공격으로 잘못 판정되는 비율 %)
- **(신규)** Ablation study 방어 구성별 비교 수치 (방어 없음 / SecOC만 / SecOC+IDS)
- end-to-end 레이턴시 (CAN 수신 → Android UI 반영, ms)
- 코드 커버리지 (Statement %, Fail-safe Branch %)

## ※ 예산 관련 안내

- MCP2515 모듈은 알리익스프레스(배송 2~3주 소요) 또는 국내 쇼핑몰 구매 가능
- 라즈베리파이 4B 품귀 시 라즈베리파이 5로 대체 가능 (SocketCAN 동일 지원)
- 학교 지원 금액 기준에 맞게 품목/금액 조정 가능

---

## ※ 개선 버전 변경 이력 요약

> 본 제안서는 원본 대비 다음 사항이 개선되었으며, 원본의 모든 내용은 그대로 유지되었다.

| # | 개선 항목 | 반영 위치 |
|---|-----------|-----------|
| 1 | **개발기간 8개월** (6월~1월) | 표지, 5절 일정 전체 |
| 2 | **AOSP 포팅 리스크 대비 Plan B 전략** 추가 | 3.1절 Node B 설명, 3.2절 신규 섹션, 5절 2개월차 |
| 3 | **실측 배터리 데이터셋 기반 BMS 시뮬레이션** 추가 | 3.3절 기능1 [1-C], 4절 팀원A 역할, 5절 2~3개월차 |
| 4 | **Ablation Study 기반 보안 실험 설계** 추가 | 3.3절 기능3 신규 섹션, 3.4절 검증방법, 5절 5개월차 |
| 5 | **QEMU user-mode 에뮬레이션 CI 통합** 추가 | 3.3절 기능4 Stage 3, 4절 팀원B 역할, 5절 3개월차 |
| 6 | **ADR(Architecture Decision Records)** 추가 | 3.4절 산출물 관리, 4절 공동 담당, 5절 5개월차 |
| 7 | **7개월차(최종 검증+문서화) + 8개월차(발표 준비)** 신규 일정 | 5절 일정표, 월별 체크포인트 |
| 8 | **기대효과에 실측 데이터 신뢰도, 기술 의사결정 역량** 추가 | 6절 기술적/교육적 기대효과, 어필 포인트 표 |