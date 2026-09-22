# IVI Plan B 진행 상황 및 프로젝트 구조 안내

> 기준일: 2026-09-22
> 대상: Node B IVI 담당자
> 실행 기준: [IVI 계획](../../../plan/IVI.md), [Plan B 전환 계획](../../../plan/IVI_PLAN_B_전환계획.md)

## 1. 프로젝트를 한 문장으로 이해하기

Node A가 배터리 상태와 Fail-safe 이벤트를 계산해 CAN으로 보내면, Node B IVI가 SecOC 인증을 확인한 뒤 Qt 대시보드에 표시한다. Node A의 IDS가 공격을 탐지하면 `0x200` 경보도 Node B에 전달한다.

```text
센서/시뮬레이터
  → Node A BMS·Fail-safe·SecOC
  → CAN 0x100/101/102/103, IDS 0x200
  → Node B SocketCAN·SecOC·상태 서비스
  → Qt Quick/QML 대시보드
```

현재 제출 경로는 Android 포팅이 아니라 **Ubuntu 22.04 + C++17 + SocketCAN + Qt Quick/QML**이다. CAN wire 계약은 바꾸지 않는다.

## 2. 현재 진행 상황

| 영역 | 실제 상태 | 의미 |
| --- | --- | --- |
| ECU C++ | 소스 존재 | IVI가 연동할 송신측 기반이 있으나 현재 문서 작업이 동작 검증을 뜻하지 않음 |
| 보안·IDS Python | 소스 존재 | 공격/IDS 기반이 있으나 통합 결과는 별도 검증 필요 |
| IVI 제품 코드 | P3 상태·UI 구현 존재 | parser·SecOC·pending/stale service·SocketCAN·Qt/QML과 core·Qt 시험 존재 |
| IVI P0 | 문서 기준 고정 완료 | ADR·SRS·ICD·SDD·TEST_PLAN을 Qt Plan B에 맞춤 |
| IVI P1 | 완료 | core Debug/Release 시험 각 3/3 통과; Qt와 Linux SocketCAN 실동작은 후속 검증 |
| IVI P2 | 완료 | pending·SecOC·frame·retry 정책 구현, Debug/Release 각 6/6 통과 |
| IVI P3 | 완료 | stale·IDS ack·전체 화면 경고, Qt Debug/Release 각 8/8 통과 |
| IVI P4~P6 | 진행 예정 | vcan 통합, 배포, CI·마감 순서로 진행 |
| Git | 원격 연결됨 | `develop`을 통합 기준으로 하고 기능 브랜치에서 PR을 올림 |

P0은 구현 전에 문서 기준을 고정한 단계이고, P1은 선택 이관과 core 재현 빌드를 완료한 단계다. Qt 화면, `vcan0`, RPi4 물리 CAN은 아직 통과로 판정하지 않는다.

## 3. M1~M8은 무엇인가

`M`은 IVI 담당자의 **기능 마일스톤(Milestone)**이다. 숫자는 수행 순서이며 각 단계가 만들어야 할 기능과 증거를 나타낸다.

| 마일스톤 | 뜻 | 완료 시 확인할 것 |
| --- | --- | --- |
| M1 | Qt 개발 환경과 빈 앱 준비 | Qt 6/CMake로 앱이 빌드·실행되고 `vcan0` 준비 절차가 재현됨 |
| M2 | SocketCAN 수신 | 5개 CAN ID 필터, DLC/프레임 검증, 정상 종료가 단위 시험으로 확인됨 |
| M3 | SecOC와 파싱 | 원본+인증 프레임 결합, HMAC/counter 검증, parser 벡터가 통과함 |
| M4 | 상태 서비스 | 인증 성공 값만 게시하고 initial/valid/stale/last-good 정책이 동작함 |
| M5 | Qt 대시보드 | SOC·전압·전류·온도·Fail-safe가 QML에 표시됨 |
| M6 | 경보 UX | IDS 배너, 확인 처리, CRITICAL/SHUTDOWN 전체 화면 경고가 동작함 |
| M7 | 통합·성능 | Node A→CAN→Node B→QML 경로와 변조/replay/timeout, 지연을 측정함 |
| M8 | 배포·마감 | RPi4 `can0` 실행, 운영 절차, 시험 증거, CI/문서가 정리됨 |

## 4. P0~P6은 무엇인가

`P`는 Plan B를 실제로 전환하는 **실행 패키지(Phase)**다. M이 제품 기능의 완성도를 나타낸다면 P는 기존 자료를 어떻게 가져와 위험을 줄이며 구현할지 나타낸다.

| 단계 | 목적 | 연결되는 마일스톤 |
| --- | --- | --- |
| P0 | 결정·요구·설계·시험 기준을 Qt로 고정 | 전체 M의 출발 조건 |
| P1 | 이전 폴더에서 필요한 C++/QML만 선별 이관하고 빌드 재현 | M1 |
| P2 | 수신·파싱·SecOC의 치명 오류 수정 | M2~M3 |
| P3 | 상태 정책과 Qt UI 완성 | M4~M6 |
| P4 | vcan 통합 및 end-to-end 계측 | M7 |
| P5 | RPi4/can0 물리 배포·통합 | M7~M8 |
| P6 | CI, 실행 문서, 증거와 데모 마감 | M8 |

P1에서 이전 `/Desktop/도토리팀_소스코드`를 통째로 복사하지 않는다. 먼저 파일별 출처와 수정 필요성을 기록하고, C++ SocketCAN·parser·QML처럼 재사용 가능한 파일만 가져온다. Android/HIDL/AIDL/Kotlin 자리표시자와 빌드 산출물·키는 제외한다.

## 5. 전체 폴더 구조

```text
Capstone-proj/
├── AGENTS.md, SKILL.md        작업 규칙과 검증 기준
├── README.md                  프로젝트 첫 진입점
├── adaptive_ecu/              Node A ECU C++ 제품 코드
├── security/                  공격 시뮬레이터·IDS Python 코드
├── ivi_platform/              Node B C++/Qt 제품 코드·시험·실행 스크립트
├── docs/
│   ├── ADR.md                 왜 이 구조를 선택했는가
│   ├── SRS.md                 무엇을 만족해야 하는가
│   ├── ICD.md                 CAN/SecOC/API 계약
│   ├── SDD-ECU.md             Node A 설계
│   ├── SDD-IVI.md             Node B Qt 설계
│   ├── TEST_PLAN.md           어떻게 합격을 증명하는가
│   ├── CICD_SPEC.md           자동화·배포 기준
│   ├── development/           환경·운영·협업·플레이북
│   └── aidlc/                 변경 단위 기록과 문서 매핑
├── plan/
│   ├── ECU.md                 ECU 실행 계획
│   ├── IVI.md                 현재 IVI 실행 계획
│   ├── IVI_PLAN_B_전환계획.md 전환·이관 상세 계획
│   └── detail/                과거/세부 단계 자료
├── tests/                     저장소 공통 시험·검증 위치
├── tools/                     보조 도구와 workflow 골격
└── _archive/                  과거 문서 보존 영역
```

IVI 담당자가 자주 보는 문서는 다음 순서가 효율적이다.

1. 이 안내서와 `plan/IVI.md`로 현재 상태와 순서를 파악한다.
2. `ICD.md`에서 CAN/SecOC 계약을 확인한다.
3. `SRS.md`의 FR-IVI-001~008로 요구를 확인한다.
4. `SDD-IVI.md`로 구현 경계와 클래스 책임을 정한다.
5. `TEST_PLAN.md`에서 각 구현의 합격 증거를 확인한다.
6. 세부 이관·배포는 `IVI_PLAN_B_전환계획.md`를 따른다.

## 6. 지금부터 해야 할 일

P1에서 이전 소스 inventory, 선택 이관, CMake core Debug/Release 검증을 완료했다. P2에서는 인증 후 게시, counter wrap, pending 만료·교체·orphan, CAN frame 검사와 제한 수신 재시도를 구현했다. P3에서는 300ms stale, last-good, IDS sequence 확인, Fail-safe 전체 화면 경고를 완성하고 macOS Qt 6.11.2 Debug/Release 각 8개 시험과 offscreen 화면을 검증했다.

이제 P4에서 Linux vcan 수신 복구 확인과 T1~T4 지연 계측을 끝낸 후 P5의 실제 RPi4/can0로 넘어간다. 마지막 P6에서 CI와 실행 문서, 시험 원본을 정리한다. sensorState wire 활성화는 ICD §8에 따라 ECU와 동시 전환할 때만 수행한다.

각 단계는 코드 존재만으로 완료하지 않는다. 빌드 명령, 시험 결과, 장비/인터페이스, 원시 로그를 남겨 다른 팀원이 같은 조건에서 재현할 수 있어야 한다.

P1부터의 상세 상태와 결과물 목록은 [CHG-003](../../aidlc/changes/CHG-003/aidlc-state.md), 최신 상세는 [P3 구현 결과](../../aidlc/changes/CHG-003/construction/P3_구현_결과.md)와 [P3 증거](../../aidlc/changes/CHG-003/construction/build-and-test/P3_빌드_시험_증거.md)에서 확인한다.
