# IVI 참조 — CI 파이프라인 전문, 명령, 파일 경로, 셀프 QA

> **상태(2026-09-22)**: ADR-010의 Qt Plan B 활성화로 이 문서의 Android/AOSP 실행 절차는 현 제출 범위에서 superseded된 역사 자료다. 현재 작업은 [IVI 계획](../../IVI.md)과 [Plan B 전환 계획](../../IVI_PLAN_B_전환계획.md)을 따른다.


## 현재 실행 진입점 — Qt Plan B

이 파일의 이전 M단계 절차·명령·체크리스트는 역사 자료이며 현재 완료 판정에 직접 사용하지 않는다. 현행 작업은 [IVI M1~M8 매핑](../../IVI.md#4-m1m8-마일스톤)과 [Qt P0~P6 실행 계획](../../IVI_PLAN_B_전환계획.md#3-단계별-실행-계획)을 따른다. Qt 관련 과거 대안도 현재 채택 구조와 다를 수 있으므로 D-Bus/Flutter를 추가 요구하지 않는다. 공식 요구·계약·시험은 SRS/ICD/TEST_PLAN이 원본이다.

---


> **예시 상태**: 코드·명령은 별도 검증 표시가 없으면 작성 골격·예정 절차다. 실행 전 생성할 파일·의존성·플랫폼을 확인한다. [공동 규약](../common/00_협업_규약.md)의 문서·예시 사용 규칙을 따른다.

> 상위 계획: [IVI.md](../../IVI.md)
> 원본: `_archive/IVI.md` 부록 A·B·C, `_archive/INDEX.md` §8, `_archive/IVI_최종_실행계획서.md` §15~§16

이 문서는 조회용이다. 절차와 맥락은 각 단계 상세 문서에 있다.

---

## 1. CI 구현 명세 — 단일 관리 위치

이 절은 **신규 구현할 CI의 명세**다. 아직 실행 확인하지 않은 전체 YAML을 완성본으로 배포하지 않는다. 실제 `.github/workflows/ci.yml`을 생성한 뒤에는 파일을 실행 정본으로 삼고 여기에는 Stage·검증 계약만 유지한다. SRS FR-CI-001~006, NFR-QA-001~004와 [CICD_SPEC](../../../docs/CICD_SPEC.md)을 따른다.

| 단계 | 구현 시점·산출물 | 반드시 확인할 실행·실패 조건 |
|---|---|---|
| 1 정적 분석 | M1, main/develop push·PR 이벤트, cppcheck | ECU src/include 필수; IVI 신규 생성 단계에는 존재 여부 기록, M3 이후 필수. 분석 대상 0개를 성공 처리하지 않음. 오류 주입 PR 실패·정상 PR 통과 (TC-CI-001~002) |
| 2 ARM64 빌드 | M2~M3, Dockerfile·toolchain·ECU ARM64 artifact, IVI core ARM64 산출물 | `file` 아키텍처, compiler/sysroot·OpenSSL/Threads·GoogleTest ABI 일치. AOSP 서비스·앱은 별도 대상 빌드로 검증 (TC-CI-003) |
| 3 시험·커버리지 | M3, CTest/QEMU·lcov·앱 시험 결과 | 시험 수 >0 및 기대 시험 목록 일치, 실패 전파·timeout. C++ line ≥80%, Fail-safe branch 100%, 자료 없음은 INVALID/실패 (TC-CI-004) |
| 4 배포·상태 점검 | M4, main push에서만 배포, 대상별 설치·health·rollback | 검증된 artifact 버전 일치, 서비스 상태 외 정상 CAN/인증 데이터·앱 연결 확인, 실패 시 이전 artifact 복구 (TC-CI-005~006) |

### 1.1 ARM64 시험 실행 경계

1. host 빌드·ARM64 빌드를 서로 다른 경로에 둔다. Docker 안의 `/workspace`에서 configure한 테스트는 **같은 경로가 마운트된 컨테이너 안에서** 실행한다. 호스트에서 컨테이너 절대 경로가 적힌 CTest 파일을 그대로 실행하지 않는다.
2. toolchain에 emulator와 대상 runtime sysroot를 명시하거나 검증된 binfmt 실행 환경을 제공한다. 동적 loader·ARM64 OpenSSL·표준 라이브러리를 실제 시험 바이너리 실행으로 확인한다. QEMU 설치만으로 실행 검증을 대신하지 않는다.
3. ECU 시험 옵션은 `ECU_BUILD_TESTS`이며 현재 기본값 ON이다. 재현을 위해 ON을 명시한다. 옵션 누락과 시험 0개를 동일 원인으로 설명하지 않는다. configure 후 `ctest --show-only=json-v1` 결과의 시험 수·이름을 검사하고, runner가 지원하는 `--no-tests=error`도 사용한다.
4. coverage는 계측 빌드와 **동일 compiler 버전의 gcov**로 같은 경로에서 수집한다. lcov 버전에 맞춰 branch 수집을 명시하고 BRDA·분모 존재를 확인한다. mismatch를 무조건 무시하거나 빈 숫자를 0으로 변환하지 않는다.
5. Stage 3에 IVI core·앱 시험을 연결한다. host 단위시험·ARM64 QEMU·Android 기기 시험의 환경과 범위를 각각 기록한다. 장비 미연결을 전체 품질 PASS로 처리하지 않는다.

### 1.2 배포 경계

Node A ECU는 Linux systemd/SSH 배포 대상이다. Node B Android Plan A는 AOSP 모듈·앱 설치 및 init/service 등록 경로를 사용하며 Node A의 systemd 명령을 복사하지 않는다. Plan B 승인 시 Node B Linux 서비스·Qt 앱 배포를 별도로 구현한다. 각 대상에 artifact 해시·버전·기동·데이터 경로·rollback 증적을 남긴다.

SSH 키·호스트 식별 정보는 승인된 비밀 저장소에서 제공한다. 러너 네트워크 연결성과 호스트 키 신뢰를 사전에 확인한다. 배포 직전에 임의 호스트 키를 신뢰하는 것으로 검증을 대체하지 않는다. PR 코드에서 배포 secrets를 사용하지 않는다.

### 1.3 재현·회귀 인수 조건

- [ ] 새 checkout에서 Stage 1~3 성공; deliberately failing 단위시험·cppcheck 오류·0개 시험·coverage 파일 없음은 실패
- [ ] ARM64 artifact가 QEMU 환경에서 실행되고 CTest 결과·coverage source 경로가 실제 소스와 대응
- [ ] main 배포에서만 Stage 4 실행; 이전 버전으로 복구하는 시험 통과
- [ ] 액션·도구 버전과 외부 의존성 고정 방법, 러너·컨테이너 요구를 구현 시 기록
- [ ] ECU·IVI 양측 증적 확인 뒤 공동 릴리즈 조정자가 태그 생성

---

## 2. 단계별 필수 명령

실행 위치는 저장소 루트다. M1 Docker/AOSP는 준비된 Linux 빌드 호스트, M2의 adb는 연결 호스트에서 Android 장비 대상, M3/M6/M7 CMake·Gradle은 구현 후 호스트 core/앱 시험이다. AOSP HAL 빌드·등록·기기 UI 시험은 Android 환경설정 §7과 M1~3에서 별도 인수한다. M4 systemd와 M5 candump·governor, M7 journalctl은 Node A Linux 대상이다. M8 ECU 실행은 Node A, Git 태그는 실제 저장소와 양측 증적을 확인한 IVI 릴리즈 조정자만 수행한다. 각 블록은 독립 절차이며 앞 블록의 cd 상태를 이어 쓰지 않는다.

### M1 — 환경

```bash
docker --version && docker run hello-world
repo version
du -sh ~/aosp-rpi4

docker build -f Dockerfile.arm64 -t capstone-arm64 .
docker run --rm -v "$(pwd)":/workspace capstone-arm64 bash -c \
  "cmake -S /workspace/adaptive_ecu -B /workspace/build-arm64 \
     -DCMAKE_TOOLCHAIN_FILE=/opt/toolchain-aarch64.cmake && \
   cmake --build /workspace/build-arm64"
file build-arm64/adaptive_ecu
```

### M2 — Mock과 AOSP

```bash
cd ~/aosp-rpi4 && source build/envsetup.sh && lunch && m -j$(nproc)
ls out/target/product/*/system.img
adb shell whoami
adb shell ip link show can0
```

### M3 — 파서·HAL·UI

```bash
cmake -S ivi_platform -B ivi_platform/build -DCMAKE_BUILD_TYPE=Debug
cmake --build ivi_platform/build
ctest --test-dir ivi_platform/build -R test_can_parser     --output-on-failure
ctest --test-dir ivi_platform/build -R test_secoc_verifier --output-on-failure

cd ivi_platform/app && ./gradlew test --tests "*.SocGaugeTest"
```

### M4 — 배포

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ecu-node-a.service
systemctl is-active ecu-node-a.service
journalctl -u ecu-node-a.service -f

ssh -i ./deploy_key deploy@<Node-A-Host> "bash /opt/ecu/scripts/health_check.sh"
```

### M5 — 성능

```bash
# TC-PERF-002 주기
# M5 §3.1의 캡처 어댑터로 절대시각 원시 로그를 CSV·manifest로 정규화한 뒤 실행
python3 ivi_platform/scripts/analyze_period.py --input period_raw.csv --manifest capture_manifest.json

# TC-PERF-001 e2e 지연
python3 ivi_platform/scripts/analyze_latency.py --input latency_raw.csv --manifest capture_manifest.json --stages t1,t4

# TC-IVI-008
python3 ivi_platform/scripts/analyze_latency.py --input latency_raw.csv --manifest capture_manifest.json --stages t2,t3

# 환경 고정
for cpu in /sys/devices/system/cpu/cpu[0-3]; do
    echo performance | sudo tee "$cpu/cpufreq/scaling_governor"
done
```

### M6 — 문서·커버리지

```bash
lcov --summary coverage_filtered.info
lcov --list coverage_filtered.info
cd ivi_platform/app && ./gradlew test
```

### M7 — 안정성

```bash
cmake -S ivi_platform -B ivi_platform/build-asan -DENABLE_ASAN=ON -DCMAKE_BUILD_TYPE=Debug
cmake --build ivi_platform/build-asan
ctest --test-dir ivi_platform/build-asan --output-on-failure

journalctl -u ecu-node-a.service --since "24 hours ago" | grep -ci restart
ip -s link show can0
```

### M8 — 데모·릴리즈

```bash
./adaptive_ecu/build/adaptive_ecu --interface can0 --secoc on --sensor-mode profile_csv
candump -t a -l can0

git switch main && git pull origin main
git tag -a v1.0.0 -m "v1.0.0: 최종 릴리즈"
git push origin v1.0.0
git tag -l
```

---

## 3. 파일 경로 종합

### 현재 존재 여부

**IVI 영역은 전부 미구현이다** (확인 기준일 2026-09-05). `ivi_platform/` 디렉토리 자체가 없다.

| 파일 | 경로 | 만들 단계 |
|---|---|---|
| `IVehicleHal.hal`, `IVehicleHalCallback.hal` | `ivi_platform/hal/` | [M1](M1_AOSP_Docker_CI.md) |
| `VehicleHalMock.java` | `ivi_platform/hal/mock/` | [M2](M2_HALMock_PlanAB.md) |
| `VehicleRepository.kt` | `ivi_platform/app/data/` | [M2](M2_HALMock_PlanAB.md) |
| `can_parser.h/.cpp` | `ivi_platform/hal/` | [M3](M3_HAL_Service_대시보드.md) |
| `vehicle_hal_impl.h/.cpp` | `ivi_platform/hal/` | [M3](M3_HAL_Service_대시보드.md) |
| `secoc_verifier.h/.cpp` | `ivi_platform/hal/` | [M3](M3_HAL_Service_대시보드.md) |
| `IVehicleDataService.aidl`, `IVehicleDataListener.aidl` | `ivi_platform/service/` | [M3](M3_HAL_Service_대시보드.md) |
| `VehicleDataParcel.java`, `VehicleDataService.java`, `VehicleDataManager.java` | `ivi_platform/service/` | [M3](M3_HAL_Service_대시보드.md) |
| `DashboardViewModel.kt`, `SocGauge.kt` | `ivi_platform/app/` | [M3](M3_HAL_Service_대시보드.md) |
| `DashboardScreen.kt`, `FailSafeIndicator.kt`, `AlertBanner.kt` | `ivi_platform/app/` | [M4](M4_대시보드_Alert_배포.md) |
| `test_can_parser.cpp`, `test_secoc_verifier.cpp` | `ivi_platform/test/` | [M3](M3_HAL_Service_대시보드.md) |
| `SocGaugeTest.kt` | `ivi_platform/app/test/` | [M3](M3_HAL_Service_대시보드.md) |
| `DashboardScreenTest.kt`, `DashboardViewModelTest.kt` | `ivi_platform/app/test/` | [M4](M4_대시보드_Alert_배포.md) |
| `Dockerfile.arm64`, `toolchain-aarch64.cmake` | 루트 | [M1](M1_AOSP_Docker_CI.md) |
| `ci.yml` | `.github/workflows/` | M1~M4 단계별 |
| `health_check.sh` | `scripts/` | [M4](M4_대시보드_Alert_배포.md) |
| `ecu-node-a.service` | Node A 배포 | [M4](M4_대시보드_Alert_배포.md) |
| `analyze_period.py`, `analyze_latency.py` | `ivi_platform/scripts/` | [M5](M5_성능_UI개선.md) |
| `codecov.yml` | 루트 | [M6](M6_문서_Coverage.md) |

**Plan B로 전환한 경우**: `hal/` C++ 파일은 그대로, `service/`는 D-Bus daemon으로, `app/`은 Qt QML 또는 Flutter로 대체된다. 파일 목록도 그에 맞게 갱신한다.

---

## 4. 최종 셀프 QA

### 코드·플랫폼

- [ ] `ivi_platform/`이 표준 구조로 존재한다
- [ ] Plan A 또는 Plan B가 명확히 결정되고 문서화됐다
- [ ] CAN 파서가 `0x100`/`0x101`/`0x102`/`0x103`/`0x200`을 ICD대로 처리한다
- [ ] 전류는 int16 2의 보수, 온도는 int 확장 후 −40으로 디코딩한다
- [ ] `0x100`을 `0x102` 검증 통과 후에 전달한다
- [ ] SecOC verifier가 ECU 벡터를 통과한다
- [ ] 카운터 비교가 unsigned delta 방식이다
- [ ] Service와 대시보드가 재연결·재시작을 견딘다
- [ ] SSH 개인키·SecOC 키가 저장소에 없다

### 시험 결과 기록

- [ ] TC-IVI-001~008
- [ ] TC-INT-001~004
- [ ] TC-PERF-001~003
- [ ] TC-CI-001~006
- [ ] IT-001~005

각 항목에 Pass / Fail / Skip과 근거를 남긴다. 실행하지 않은 것을 Pass로 적지 않는다.

### CI/CD

- [ ] Stage 1 cppcheck 녹색
- [ ] Stage 2 ARM64 빌드 녹색, artifact 생성
- [ ] Stage 3 QEMU 시험 녹색, 커버리지 게이트 통과
- [ ] Stage 4 배포·Health Check 통과. 미달성 사유는 기록하되 해당 완료 체크와 TC-CI-005는 미완료 유지
- [ ] required check가 브랜치 보호 규칙에 등록됨
- [ ] 게이트가 실제로 막는지 확인함 ([M7](M7_안정성_교차검토.md) 3.3)

### 문서·데모

- [ ] SDD-IVI 최신, 구현과 일치
- [ ] CICD_SPEC 최신
- [ ] README 실측값 반영, 미측정 항목 표시
- [ ] 지연·안정성 결과 보관, 측정 조건 명시
- [ ] 정상·공격 데모 영상 백업

---

## 5. 한 줄 실행 순서

```text
GitHub 인프라
-> M1 AOSP / Docker / HIDL / CI Stage 1
-> M2 HAL Mock / AOSP 부팅 / Plan A·B 판정
-> M3 Parser / HAL / Service / Dashboard / SecOC verifier / CI Stage 2~3
-> M4 Alert UI / CI Stage 4 / IT-001~005
-> M5 지연 측정 / 최적화 / UI 개선
-> M6 SDD-IVI / CICD_SPEC / README / Coverage
-> M7 안정성 / 교차 검토 / 최종 성능
-> M8 데모 / 발표 / v1.0.0
```

---

## 6. 부록 — 원본 계획의 시간 추정

`_archive/IVI.md` 부록 B의 추정치다. **근거가 기록되지 않은 추정이므로 일정 약속이 아니라 참고로만 쓴다.**

| 단계 | 추정 | 주요 산출물 |
|---|---|---|
| M1 | 18~22h | AOSP 환경, Docker, CI Stage 1, HIDL 초안 |
| M2 | 26~34h | HAL Mock, AOSP 부팅 시도, Plan A/B 결정 |
| M3 | ~42h | CAN 파서, HAL, Service, SocGauge, CI Stage 2~3 |
| M4 | ~31.5h | DashboardScreen, AlertBanner, CI Stage 4, IT-001~005 |
| M5 | ~29h | 지연 측정·최적화, UI 개선, ADR |
| M6 | ~28h | SDD-IVI, README, Coverage |
| M7 | ~24h + 24h 운행 | 안정성 시험, CI 점검, 교차 검토 |
| M8 | ~30h | 데모 리허설, 발표 자료, Release, v1.0.0 |

합계 약 228~240시간.


<a id="ivi-ci-01"></a>
### IVI-CI-01 — Plan 승계 과제

원문: [IVI.md](../../_archive/plan_20260908/IVI.md.txt)의 IVI-CI-01. 실행 상태는 해당 역할의 진행 표·공동 인수 기록을 사용한다. 이 병합은 과제 실행 완료가 아니다.

선행·착수: [COM-BASE-01](../common/00_협업_규약.md#com-base-01) 저장소/환경, ECU 빌드 입력

보존한 수행·인수 조건: M1~M4 CI 구축과 M6 인수: 실제 트리거·ARM64 의존성/QEMU·분석/시험/coverage 실패 전파·대상별 배포/복구를 검증한다. ECU-QA-01에 재현 환경을 제공하고 릴리즈는 COM-REL-01로 인계한다.

현재 기준 적용: 예정 CI를 구현 완료로 승격하지 않음; Linux/Android 분리 유지. 본문의 공식 FR/TC·승인 정책·실패 대응을 함께 적용한다.
