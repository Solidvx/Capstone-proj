# IVI 실행 계획 — Node B

> **2026-09-22 플랫폼 결정:** 시간 제약에 따라 현 제출 범위는 **Plan B(Ubuntu + C++17 + SocketCAN + Qt Quick/QML)**로 전환한다. 아래 Android Plan A 중심 내용은 결정 배경과 과거 계획으로 보존하며, 이후 실행 순서와 완료 기준은 [IVI Plan B 전환 및 구현 계획](IVI_PLAN_B_전환계획.md)을 우선 적용한다. CAN ID, payload와 SecOC 계약은 현행 `docs/ICD.md`를 유지한다.

> **2026-09-09 보안 후속 계획:** [공동 적용 규약](detail/common/00_협업_규약.md#security-adoption)에 따라 기존 과제에 [M3 pending·인증 이벤트](detail/ivi/M3_HAL_Service_대시보드.md#security-adoption), [M4 배포·표시](detail/ivi/M4_대시보드_Alert_배포.md#security-adoption), [M5 계측](detail/ivi/M5_성능_UI개선.md#security-adoption)의 추가 조건을 적용한다. Q2의 상세 전달 계약은 미확정이며 IVI 구현 완료를 뜻하지 않는다.

> **담당**: IVI / HAL / Service / Dashboard / CI·CD · **플랫폼**: RPi4 Android AOSP (Plan A) 또는 Ubuntu (Plan B)
> **짝 계획**: [ECU.md](ECU.md) · **공동 절차**: [detail/common/](detail/common/)
> **갱신 기준일**: 2026-09-09 (문서 안내 정정; 구현 스냅샷 날짜와 별개)

---


<a id="security-integration"></a>
## 보안 상세 계획 병합 적용 — 2026-09-09

기존 단계별 과제에 보안 상세 계획의 최신 수행·실패 대응·인수 조건을 반영했다. [M1](detail/ivi/M1_AOSP_Docker_CI.md#security-integration) · [M3](detail/ivi/M3_HAL_Service_대시보드.md#security-integration) · [M4](detail/ivi/M4_대시보드_Alert_배포.md#security-integration) · [M5](detail/ivi/M5_성능_UI개선.md#security-integration) · [M6](detail/ivi/M6_문서_Coverage.md#security-integration) · [M7](detail/ivi/M7_안정성_교차검토.md#security-integration)의 병합 절을 기존 본문과 함께 적용한다. [공동 인계](detail/common/01_연계_의존성.md#security-integration)와 [공동 시험](detail/common/02_통합시험.md#security-integration)이 양측 제공물·동일 run 증거를 관리한다.

M1 환경 확인→M3/M4 구현→M5 계측→M6 검토→M7 재현→기존 M8 제출 순서를 유지한다. 새 단계·중복 과제를 추가하지 않는다. 상세 규약은 설계 참조이며 실제 계약 채택·제품 실행 상태는 각 과제의 증거로 판단한다. 문서 병합 완료만으로 실행 체크박스를 완료하지 않는다.


## 0. 이 문서 사용법

최신 개발 착수 판정은 [종합 검토](../docs/development/reviews/문서_종합정합성_검토.md#2026-09-09-개발-기준본-진입점-정정)를 따른다. 요구·설계·역할별 절차는 개발 방향으로 사용할 수 있지만, G1의 세션 상세 전환을 포함한 미결 항목을 전체 확정으로 해석하지 않는다. [이전 계획 인수 보고서](../docs/development/reviews/계획_검토.md#part2-verdict)는 당시 검토 기록이다.

공통 목표는 가상 배터리 기반 Node A BMS·Fail-safe → SecOC 적용 CAN → Node B HAL·Service·대시보드 전달과 Node A IDS 탐지·경보를 end-to-end로 검증하는 것이다. 실제 배터리 제어·표준 VHAL·외부 안전 인증을 필수 범위로 추가하지 않는다.

**개발 착수: 승인된 범위에서 가능. 현행 SecOC 문구 충돌: 승인 정정 완료. 세션 상세 전환: 별도 관문.** [공동 규약](detail/common/00_협업_규약.md)과 [확인사항](../docs/development/governance/의사결정_기록.md#part2-confirmed)의 기존 결정을 적용하고, 종합 검토의 G/E별 차단 범위와 종료 증거를 확인한다. 제품 시험·장비 인수는 후속 실행 과제이며 모든 시험 완료를 문서 계획 완성의 선행조건으로 삼지 않는다.

이 문서는 **무엇을·왜·언제·무엇으로 판정하는가**를 담는다. **어떻게 하는가**(명령·코드·기대 출력)는 [detail/ivi/](detail/ivi/)의 단계별 문서에 있다.

1. §2에서 현재 구현 상태를 확인한다. IVI 영역은 대부분 신규 구현이다.
2. §4 표에서 해당 단계 행을 찾아 상세 문서로 들어간다.
3. 상세 문서의 6블록(목적 / 선행조건·현재상태 / 수행 절차 / 검증 / 실패 대응 / 완료 체크)을 순서대로 수행한다.
4. 공동 작업(브랜치·PR·마일스톤·통합 시험·발표)은 [detail/common/](detail/common/)을 따른다.

**원천 우선순위와 검증 명령은 [AGENTS.md](../AGENTS.md)의 Source of Truth·Verification Baseline을 따른다.** 이 문서에 복제하지 않는다.
계약 값(CAN ID·레이아웃·스케일·HAL API)은 요약본을 만들지 않고 [docs/ICD.md](../docs/ICD.md)를 직접 읽는다.

> 이 계획은 진행 기준이며 **구현 완료의 증거가 아니다.** 파일이 있다는 이유로 시험 통과를 표시하지 않는다.

---

**확정 결정과 후속 작업:** [공동 규약](detail/common/00_협업_규약.md)의 Q/R 정책을 따른다. [확인사항](../docs/development/governance/의사결정_기록.md#part2-confirmed)은 사용자 결정·미결정의 기록이며, [요구·원천 매핑](detail/common/01_연계_의존성.md) §10~11은 담당·시험·Plan 비교 위치를 연결한다. 개발자는 승인된 과제의 구현·시험을 진행하고 미승인 계약 적용은 해당 관문에서 멈춘다. 2026-09-08 사용자 명시 지시에 따른 Plan 통합과 재검사를 반영했다. 과제 ID별 주관 위치는 공동 규약의 Plan 병합 기록을 따른다. 개발 재개 순서는 종합 검토의 「개발자가 다음에 수행할 순서」를 따른다. 공동 연계의 과거 문서 검토 범위를 제품 개발 금지로 해석하지 않는다.

## 1. 최종 목표와 완료 판정

**환경·소스 검토:** 사용자 정의 HIDL HAL → Android 서비스 → 대시보드 앱을 구현하며 표준 VHAL·CarService는 요구하지 않는다. [환경설정 §6](../docs/development/environment/안드로이드_환경설정.md)의 Raspberry Vanilla Android 16을 우선 검증 후보로 조사했다. 최종 채택은 소스 고정·부팅·HIDL 호출·CAN·DSI 시험 후 판정한다. 기존 주차표는 최신 시연 기한의 달성 보장이 아니다.

Node B를 차량 IVI 플랫폼처럼 구성하고, ECU가 보내는 CAN·SecOC·IDS 데이터를 **HAL → Service → UI**까지 전달한다. CI/CD 파이프라인으로 명세된 자동 검사를 수행하고, 장비·통합 시험 증거와 함께 품질을 판정한다.

**최신 일정 입력:** A-1~A-14 답변 접수 완료. 서버 자원은 충분하다는 사용자 확인을 전제로 주 빌드 장비를 서버로 배치하며 사양 재질문은 종료한다. 전체 시연 마감은 2026-09-18이며 9/8 준비, 9/9~18 D1~D10 배분과 지연 시 인터뷰 조건은 [Android 환경설정 §4](../docs/development/environment/안드로이드_환경설정.md)를 따른다. 운영체제·도구/다운로드 조건은 실제 착수 점검으로 이관한다. 앞선 서버 사양·기한 답변 대기는 이 기록으로 대체한다.

- [ ] AOSP·사용자 정의 HIDL을 우선 검증하고, 일정상 실패 경계에 도달하면 원인·영향·대안을 인터뷰한다. Plan B는 사용자 선택과 인터페이스 변경 승인 후 전환한다
- [ ] `ivi_platform/`에 HAL, parser, service, dashboard 구조를 만든다
- [ ] CAN ID `0x100`, `0x101`, `0x102`, `0x103`, `0x200`을 ICD대로 파싱한다
- [ ] SecOC verifier가 ECU 테스트 벡터와 동일하게 HMAC을 검증한다
- [ ] 대시보드가 SOC/SOH/전압/전류/온도, Fail-safe, IDS 경보를 표시한다
- [ ] GitHub Actions Stage 1~4를 구축한다: cppcheck → ARM64 빌드 → QEMU 시험 → SSH 배포·Health Check
- [ ] `docs/SDD-IVI.md`, `docs/CICD_SPEC.md`, `README.md`, 발표 자료를 완성한다
- [ ] ECU 담당자와 IT-001~005를 통과시키고 최종 데모를 완성한다

### 완료 판정 기준

| 영역 | 기준 |
|---|---|
| HAL / parser | TC-IVI-001~002 통과, CAN ID 5종 파싱 정확 |
| Service / UI | TC-IVI-003~008 통과, 대시보드·경보 동작 |
| SecOC | ECU 벡터와 동일 MAC, 변조 MAC 폐기 후 **값 미갱신** |
| CI/CD | Stage 1~4 녹색, ARM64 artifact, Health Check PASS |
| 통합 | IT-001~005 전부 Pass, TC-INT-001~004 결과 기록 |
| 성능 | e2e 평균 ≤50ms, 최대 ≤100ms, IDS 응답 ≤3초 |
| 안정성 | 장시간 시험 Pass, 메모리 누수 0건 |
| 문서 | SDD-IVI, CICD_SPEC, README, Release note 완성 |

> **수치 규칙**: 위 값은 **목표**다. 문서·발표에는 목표값과 실측값을 구분해 적고, 측정 구간과 표본 수를 함께 남긴다. 실행하지 않은 항목을 통과로 적지 않는다.

---

## 2. 현재 구현 상태 스냅샷

**환경 결정과 실행 점검:** A-1~A-14 답변을 접수했으며 서버 자원 재질문은 종료했다. 서버를 주 빌드 장비로 사용하고 서버에서 소스를 받아오는 작업은 사용자가 담당한다. [Android 환경설정](../docs/development/environment/안드로이드_환경설정.md)의 최신 결정과 §6~7에 따라 Raspberry Vanilla Android 16 후보를 검증한다. OS·도구·다운로드 조건과 revision·빌드·부팅·HIDL/CAN/화면 호환성은 실제 착수 시 확인할 항목이며 완료된 것으로 가정하지 않는다.

**확인 기준일 2026-09-06.** 실제 파일을 확인해 작성했다.

| 영역 | 상태 | 근거 |
|---|---|---|
| `ivi_platform/` | **README 골격만 존재** | IVI 코드가 하나도 없다. 전부 신규 구현 |
| `Dockerfile.arm64`, `toolchain-aarch64.cmake` | **없음** | 루트에 존재하지 않음 |
| `.github/workflows/` | **없음** | CI 미구현 |
| AOSP 소스 | 저장소 밖 | 확인 불가 |
| `docs/ICD.md` §3 HAL API | **존재** | 기존 HIDL 11필드. 승인 목표는 ICD §8의 13필드·동일 callback이며 제품 전환 미완료 |
| `docs/CICD_SPEC.md` | **존재** | 4단계 명세. **구현 전에 쓰인 예정 문서** |
| `docs/SDD-IVI.md` | **존재** | 구현에 맞춘 갱신 필요 |
| ECU 측 SecOC | **구현됨** | 벡터 대조 가능 ([ECU M3](detail/ecu/M3_EKF_Failsafe_SecOC.md)) |

### 계획 원문에서 발견한 결함 (상세 문서에서 해소)

| # | 내용 | 처리 |
|---|---|---|
| D1 | 파서의 전류 디코딩 `((d[4]<<8)\|d[5]) * 0.1f - 3276.8f`가 **틀렸다.** ECU는 int16 2의 보수로 싣는다 | `int16_t` 캐스트로 정정 ([M3](detail/ivi/M3_HAL_Service_대시보드.md) 3.1) |
| D2 | 온도 디코딩 `static_cast<int8_t>(d[6]) - 40`이 raw > 127에서 깨진다 (90°C → −166) | `int` 확장 후 −40 ([M3](detail/ivi/M3_HAL_Service_대시보드.md) 3.1) |
| D3 | SecOC 카운터 비교가 단순 대소 비교라 `0xFFFFFFFF → 0` 래핑에서 정상 프레임을 거부 | 현행 구현은 unsigned delta 방식 ([M3](detail/ivi/M3_HAL_Service_대시보드.md) 3.6). 현행 ICD 규칙은 승인 정정 완료. 세션 상세 전환은 종합 검토 G1에서 관리하며 전체 보안 인수 완료가 아님 |
| D4 | 지연 측정 스크립트가 **프레임 간 간격(주기)** 을 재고 그것을 "e2e latency"로 판정 | TC-PERF-001과 TC-PERF-002를 분리 측정 ([M5](detail/ivi/M5_성능_UI개선.md) 2장) |
| D5 | CI가 `-DBUILD_TESTS=ON`을 쓰는데 실제 옵션은 `ECU_BUILD_TESTS`. 기본값은 ON이므로 옵션명 정정과 별도로 시험 수·기대 목록 검사 필요 | 옵션명 정정 ([ref](detail/ivi/ref_CI파이프라인_명령모음.md) §1) |
| D6 | ECU 실행 인자 `--secoc=on`, `--ids=on`이 실제 `main.cpp`에 없음 | `--secoc on`으로 정정, `--ids` 제거 |
| D7 | AlertBanner의 이벤트 확인·해제 수명주기 필요 | 사용자 I-4-2=A: 확인까지 유지하고 새 경보 재표시 ([M4](detail/ivi/M4_대시보드_Alert_배포.md) 3.3) |

---

## 3. 지켜야 할 계약

IVI는 **ECU 데이터를 해석하는 수신자다.** 바이트 레이아웃을 임의로 재해석하면 통합이 실패한다. 값은 [docs/ICD.md](../docs/ICD.md)에서 직접 읽는다.

| 대상 | 참조 |
|---|---|
| CAN ID 5종·방향·주기·DLC | ICD §1.1 |
| `0x100`~`0x200` 레이아웃 | ICD §1.2~1.5 |
| SecOC 수신 검증 절차 | ICD §2.3 |
| 롤링 카운터 규칙·래핑 | ICD §2.4 |
| 수신 타임아웃·에스컬레이션·재동기화 | ICD §2.5 |
| HAL API (`IVehicleHal`, `VehicleData`) | ICD §3.1~3.3 |

**디코딩 규칙 3가지** — 상세는 [M3](detail/ivi/M3_HAL_Service_대시보드.md) 3.1.

1. uint16/uint32는 빅엔디언 그대로
2. 전류는 `int16_t`로 캐스트해 2의 보수 복원 (양수=충전)
3. 온도는 `int`로 넓힌 뒤 −40 (`int8_t` 캐스트 금지)

**Plan B로 전환하면 HAL API(ICD §3)가 HIDL → D-Bus로 바뀐다.** 코드부터 고치지 말고 [detail/common/00_협업_규약.md](detail/common/00_협업_규약.md)의 `interface-change` 게이트를 먼저 통과한다. CAN 레이아웃(§1)과 SecOC(§2)는 바뀌지 않는다.

**보안 규칙**: SecOC 키·SSH 개인키·토큰을 코드·문서·로그·커밋·릴리즈 첨부에 남기지 않는다. GitHub Secrets만 사용한다.

---

## 4. 단계별 실행 과제

| 단계 | 주제 | 선행 | 핵심 산출물 | 연결 TC | 상세 |
|---|---|---|---|---|---|
| **M1** | AOSP·Docker·HIDL·CI Stage 1 | — | 빌드 환경, ARM64 이미지, 골격, HIDL 초안 | TC-CI-001~002 | [M1](detail/ivi/M1_AOSP_Docker_CI.md) |
| **M2** | HAL Mock·AOSP 부팅·**Plan A/B 판정** | M1 | Mock, Repository, 부팅 결과, 전환 결정 | TC-CI-003 | [M2](detail/ivi/M2_HALMock_PlanAB.md) |
| **M3** | Parser·HAL·Service·대시보드·SecOC | M2 | 파서, 수신 루프, IPC, ViewModel, verifier, CI Stage 2~3 | TC-IVI-001~005, 008 / TC-INT-002 / TC-CI-003~004 | [M3](detail/ivi/M3_HAL_Service_대시보드.md) |
| **M4** | 대시보드 완성·Alert·배포·통합 시험 | M3 | UI 전체, systemd, Health Check, CI Stage 4 | TC-IVI-006~007 / TC-CI-005~006 / TC-INT-001~004 | [M4](detail/ivi/M4_대시보드_Alert_배포.md) |
| **M5** | 성능 측정·최적화·UI 개선 | M4 | 지연 측정 도구·결과, 최적화, ADR | TC-PERF-001~002, TC-IVI-008 | [M5](detail/ivi/M5_성능_UI개선.md) |
| **M6** | SDD-IVI·README·CICD_SPEC·Coverage | M5 | 문서 최종화, Coverage ≥80%, CI 전체 녹색 | TC-PERF-003, TC-CI-001~006 | [M6](detail/ivi/M6_문서_Coverage.md) |
| **M7** | 안정성·CI 점검·교차 검토 | M6 | 장시간 시험, 누수 점검, ICD 교차 검토 | TC-PERF 최종, TC-INT 재검증 | [M7](detail/ivi/M7_안정성_교차검토.md) |
| **M8** | 데모·발표·제출 | M7 | 데모 A/B, 슬라이드, 보고서, Release | — | [M8](detail/ivi/M8_데모_제출.md) |

CI 구현 명세·명령·파일 경로·셀프 QA는 [ref_CI파이프라인_명령모음](detail/ivi/ref_CI파이프라인_명령모음.md).

> **일정 표기 규칙**: M1~M8 표는 **의존성 순서**를 나타내며 과거 절대 날짜를 적용하지 않는다. 사용자 확정 마감 2026-09-18과 D1~D10 배분은 공동 규약의 최신 일정 입력을 따른다. 원본 계획의 2026-06 ~ 2027-01 날짜는 [_archive/](_archive/)에 남아 있으며 현재 기준이 아니다.

---

## 5. 단계 게이트와 산출물

| 단계 | 태그 | 게이트 조건 |
|---|---|---|
| M1 | `v0.1.0` | `repo sync` 완료, Docker ARM64 빌드 성공, HIDL이 ICD §3.1과 일치, CI Stage 1 녹색, ICD 확정 참여 |
| M2 | `v0.2.0` | Mock 100ms 갱신, ECU `0x100` 샘플 동일 해석, **Plan A/B 판정 완료**, 필요 시 ADR-010 |
| M3 | `v0.3.0` | TC-IVI-001~005·008 통과, ECU 벡터로 SecOC 검증, CI Stage 2~3 녹색 |
| M4 | `v0.4.0` | TC-IVI-006~007 통과, Stage 4 배포·Health Check, IT-001~005 수행, **IT-004에서 값 미갱신 확인** |
| M5 | `v0.5.0` | TC-PERF-001/002 분리 측정, 표본 1,000개 이상, 측정 구간 기록, ADR-004/006/007(+010) |
| M6 | `v0.6.0` | SDD-IVI·CICD_SPEC·README 최신, Coverage ≥80%, CI Stage 1~4 전부 녹색 |
| M7 | `v0.7.0` | 안정성 시험 Pass, 누수 0건, ICD 교차 검토 불일치 0건, TC-PERF 최종 수치 |
| M8 | `v1.0.0` | 데모 A/B 재현, 발표·보고서 완성, Release 8개, 키 노출 점검 |

태그·Milestone·Release 처리 절차는 [detail/common/00_협업_규약.md](detail/common/00_협업_규약.md).

---

## 6. ECU 연계 지점

전체 의존 관계와 지연 시나리오는 [detail/common/01_연계_의존성.md](detail/common/01_연계_의존성.md).

인계 시점·산출물·제공자·수신자는 [공동 인계 정본 §2](detail/common/01_연계_의존성.md#2-인계-지점-전체-테이블)에서 한 번만 관리한다. 이곳에 별도 축약 표를 복제하지 않는다. M3 이벤트 포맷 제공과 M4 실제 전이/경보 통합, M5 임계 변경 사전 통지와 측정 시간대 분리, M7 최종 빌드/데이터·재현성·안정성, M8 스크립트/실행/영상 인수를 각각 구분한다.

IVI 담당은 ECU 인계물의 계약/버전/형식을 먼저 확인하고 파서·verifier·UI·측정/안정성 결과를 돌려준다. 공동 증적을 확인한 뒤 릴리즈 조정자로 동일 태그를 한 번 생성한다. 파일 존재만으로 인수를 닫지 않으며 수신자가 실행 환경·공식 TC·hash·미통과 조건을 확인한다. SecOC 벡터가 없으면 Mock의 독립 작업은 가능하되 인증 통합을 완료 처리하지 않는다.

---

## 7. 위험과 우회

| 위험 | 즉시 조치 | 최종 조치 |
|---|---|---|
| AOSP `repo sync` 실패 | `repo sync -j4 --force-sync` 재시도 | 네트워크·디스크 확인. 디스크 부족이면 Plan B 판단 앞당김 |
| AOSP 부팅 실패 | **M2 말 Plan B 전환** | ADR-010 작성, HAL C++ 재사용 |
| 파서 값 불일치 | ICD 기준으로 파서 수정 | ECU와 샘플 payload 재검증. 전류·온도 디코딩부터 확인 |
| SecOC MAC 불일치 | Python 벡터로 바이트 단위 비교 | 입력 순서·키 길이·CAN ID 폭 확인 |
| AlertBanner 미표시 | `candump`으로 `0x200` 수신 확인 | HAL → Service → UI 경로를 나눠 디버깅 |
| CI ARM64 빌드 실패 | Docker 안에서 수동 빌드 | toolchain 경로·`libssl-dev:arm64` 확인 |
| SSH 배포 실패 | 키·known_hosts·Secrets 확인 | 러너가 사설망 접근 불가면 self-hosted runner |
| 지연 목표 초과 | 구간별로 나눠 측정 | 병목 최적화. **미달이면 미달로 기록** |
| Coverage 미달 | 파서·verifier·에러 경로 시험 추가 | 임계를 낮추지 않는다 |

**금지**: 목표 미달을 기준 완화·측정 지점 변경으로 통과 처리하지 않는다. `vcan0` 측정을 물리 CAN 측정으로 표기하지 않는다.

---

## 8. 진행 기록과 차단 요인

| 단계 | 상태 | 검증 결과 | 차단 요인 | 갱신일 |
|---|---|---|---|---|
| M1 | | | | |
| M2 | | | | |
| M3 | | | | |
| M4 | | | | |
| M5 | | | | |
| M6 | | | | |
| M7 | | | | |
| M8 | | | | |

기록 규칙: 상태는 `미착수 / 진행 / 검증대기 / 완료`. 검증 결과에는 **실행한 명령과 결과**를 적는다. 차단 요인에는 의존 대상과 필요한 조치를 적는다.

**Plan A/B 결정 기록** (M2에서 채운다)

| 항목 | 값 |
|---|---|
| 결정 | Plan A 유지 / Plan B 전환 |
| 판정 근거 | (4개 조건 표 결과) |
| 결정일 | |
| ADR-010 | 작성 / 불필요 |


Plan 승계 과제 색인: [공동 병합 기록](detail/common/00_협업_규약.md#plan-merge-20260908). 기존 Plan 링크는 새 주관 위치로 연결되며 구현·시험 완료 상태를 별도로 부여하지 않는다.
