# IVI M4 — 대시보드 완성, Alert UI, CI Stage 4, 통합 시험

> **2026-09-09 보안 방식 선별 반영:** 기존 단계·과제에 [하단 추가 수행·인수 조건](#security-adoption)을 함께 적용한다. 구현·시험 완료 기록은 아니다.

> **예시 상태**: 코드·명령은 별도 검증 표시가 없으면 작성 골격·예정 절차다. 실행 전 생성할 파일·의존성·플랫폼을 확인한다. [공동 규약](../common/00_협업_규약.md)의 문서·예시 사용 규칙을 따른다.

> 상위 계획: [IVI.md](../../IVI.md) · 통합 시험: [02_통합시험](../common/02_통합시험.md) · 인계: [01_연계_의존성](../common/01_연계_의존성.md)
> 원본: `_archive/IVI.md` M4, `_archive/IVI_최종_실행계획서.md` §8

---


<a id="security-integration"></a>
## 현행 과제에 병합한 보안 수행·인수 조건 — 인증 채널 배포·표시 회귀

이 절은 2026-09-09 보안 상세 계획을 기존 단계에 반영한 실행 조건이다. 초기 보안 보강 절과 함께 적용하며 제품 실행 완료 기록은 아니다. 상세 규칙은 [메시지·상태 규약](../../../docs/development/security/인증이벤트_메시지_상태규약.md)과 [송신·큐·실패 정책](../../../docs/development/security/인증이벤트_메시지_상태규약.md#planning-final)을 참조한다.

**선행 조건:** IVI M3 결과와 채택한 배포 설정·인증서 공급 절차를 인수한다. Android 배포와 Node A 서비스 관리를 혼용하지 않는다.

**수행:** 인증서 갱신/만료·시각 실패·권한 오류·backoff 한도·유한 종료를 배포 시험에 포함한다. 새 trust 준비→검증→새 연결 확인→이전 자격 제거 순서를 기록하고 실패 시 허용된 복귀 또는 명시적 중단으로 처리한다.

**실패 대응·인계:** 진단 채널 AVAILABLE을 BMS freshness나 안전 상태로 표시하지 않는다. 기존 경보/품질 UI 회귀를 확인하고 새 진단 UI/API는 계약 영향이 있을 때 별도 전환한다. Q2-P08과 시작/종료 증거를 공동에 제공한다.

**완료 확인:**

- [ ] 일반 보안 ON 배포·실패/복구·기존 UI 인수와 신규 진단 표시 범위를 구분했다.
- [ ] 기존 공식 시험 결과와 추가 보조 시나리오의 실제 증거·미검증 사유를 구분했다.


## 1. 목적과 범위

대시보드 전체 UI를 완성하고(DashboardScreen + FailSafeIndicator + AlertBanner), CI Stage 4 SSH 자동 배포와 Health Check를 붙인다. ECU와 물리 CAN 통합 시험 IT-001~005를 수행한다.

| 항목 | 값 |
|---|---|
| 연결 요구사항 | FR-IVI-006~007, FR-CI-005~006 |
| 연결 시험 | TC-IVI-006, TC-IVI-007, TC-CI-005~006, TC-INT-001~004 |
| 산출물 | 대시보드 UI 전체, systemd 유닛, `health_check.sh`, CI Stage 4, IT 결과, 동작 영상 |
| 태그 | `v0.4.0` |
| **ECU 의존** | `0x101` 이벤트, `0x200` 실송신 ([ECU M4](../ecu/M4_IDS_공격_물리통합.md) 3.5) |

### 주차별 작업

| 주차 | IVI 작업 | ECU 연계 |
|---|---|---|
| 1주차 | `DashboardScreen`, `FailSafeIndicator` | `0x101` 이벤트 확인 |
| 2주차 | `AlertBanner`, TC-IVI-006~007 | `0x200` IDS_Alert 연결 |
| 3주차 | systemd, SSH 배포, Health Check | Node A 서비스 재시작 |
| 4주차 | IT-001~005, SDD-IVI App 절 | 공동 통합 시험 |

---

## 2. 선행조건과 현재 구현 상태

**선행조건**: [M3](M3_HAL_Service_대시보드.md) 완료 — 파서, HAL, Service, ViewModel, SocGauge, SecOC verifier, CI Stage 1~3.

| 대상 | 상태 |
|---|---|
| `DashboardScreen`, `FailSafeIndicator`, `AlertBanner` | **미구현** |
| systemd 유닛, `health_check.sh` | **미구현** |
| CI Stage 4 | **미구현** (`docs/CICD_SPEC.md`에 명세만) |
| ECU `0x200` 실송신 | [ECU M4](../ecu/M4_IDS_공격_물리통합.md)에서 구현 예정 |

### 통합 시 해소한 충돌

| 항목 | 세대A | 세대B | 채택 |
|---|---|---|---|
| AlertBanner 표시 조건 | `visible` 플래그 (해제 로직 없음) | `attackType == 0`이면 미표시 | **사용자 I-4-2=A** — 이벤트별 사용자 확인까지 유지, 새 경보는 다시 표시 (3.3) |
| ECU 실행 인자 | `--interface can0` | `--secoc=on --ids=on` (등호, `--ids` 존재) | **`--secoc on`** — 실제 `main.cpp`는 공백 구분이고 `--ids`가 없다 ([ECU ref](../ecu/ref_명령모음.md) §1) |
| 배포 산출물 이름 | `ecu_node_a` | `adaptive_ecu` | **`adaptive_ecu`** (실제 CMake 타겟) |
| 배포 방식 | `scp` 단일 바이너리 | `rsync -avz ./` 전체 트리 | **`scp` 단일 바이너리** — 전체 rsync는 소스·비밀·빌드 산출물까지 밀어넣는다 |
| sudoers | `restart`만 | `restart`, `status` | **세대B** — Health Check에 `status`가 필요 |
| health_check 간격 | 5회 × 3초 | 5회 × 2초 | **5회 × 3초** — 서비스 기동 여유 |

---

## 3. 수행 절차

### 3.1 DashboardScreen

`ivi_platform/app/DashboardScreen.kt`:

```kotlin
@Composable
fun DashboardScreen(viewModel: DashboardViewModel = viewModel()) {
    val state by viewModel.vehicleState.collectAsState()

    Box(modifier = Modifier.fillMaxSize()) {
        Column(
            modifier = Modifier.fillMaxSize().padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            SocGauge(soc = state.soc, modifier = Modifier.padding(top = 32.dp))

            Spacer(Modifier.height(24.dp))
            BmsDataCard(state = state)

            Spacer(Modifier.height(16.dp))
            FailSafeIndicator(state = state.failSafeState, reason = state.failSafeReason)

            Spacer(Modifier.weight(1f))

            // ICD §2.5.1 수신 타임아웃 표시
            if (state.stale) {
                Text(
                    text = "통신 끊김",
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodyLarge
                )
            }
        }

        AlertBanner(
            attackType = state.attackType,
            score = state.anomalyScore,
            modifier = Modifier.align(Alignment.TopCenter)
        )

        if (state.failSafeState >= 2) {          // CRITICAL(2), SHUTDOWN(3)
            CriticalDialog(state = state)
        }
    }
}

@Composable
private fun BmsDataCard(state: VehicleUiState) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text("전압: ${"%.2f".format(state.voltage)} V")
            Text("전류: ${"%.1f".format(state.current)} A")
            Text("온도: ${state.temperature} °C")
            Text("SOH: ${"%.1f".format(state.soh)} %")
        }
    }
}

@Composable
private fun CriticalDialog(state: VehicleUiState) {
    val title = if (state.failSafeState == 3) "SHUTDOWN" else "CRITICAL"
    AlertDialog(
        onDismissRequest = { /* 임의 해제 불가 */ },
        title = { Text(title, color = MaterialTheme.colorScheme.error) },
        text = {
            Text("배터리 상태가 ${title}입니다.\n" +
                 "SOC: ${"%.1f".format(state.soc)}%\n" +
                 "온도: ${state.temperature}°C\n" +
                 "사유 코드: 0x%02X".format(state.failSafeReason))
        },
        confirmButton = { TextButton(onClick = { /* 수동 리셋 요청 */ }) { Text("확인") } }
    )
}
```

**표시 규칙**

- [ ] `stale`일 때 마지막 값을 그대로 보여주되 "통신 끊김"을 함께 표시한다. 오래된 값을 현재 값처럼 보이게 두지 않는다
- [ ] CRITICAL/SHUTDOWN Dialog는 임의 해제되지 않게 한다. `onDismissRequest`를 비워 둔 이유다
- [ ] 사유 코드는 [ICD](../../../docs/ICD.md) §1.3의 정의대로 표시하며, `0x07`(Watchdog 태스크 재시작 3회 연속 실패)을 SOC·온도 사유와 구분한다.

### 3.2 FailSafeIndicator

`ivi_platform/app/FailSafeIndicator.kt`:

```kotlin
@Composable
fun FailSafeIndicator(state: Int, reason: Int = 0, modifier: Modifier = Modifier) {
    val (label, color) = when (state) {
        0 -> "NORMAL"   to Color(0xFF4CAF50)   // Green
        1 -> "WARNING"  to Color(0xFFFF9800)   // Orange
        2 -> "CRITICAL" to Color(0xFFF44336)   // Red
        3 -> "SHUTDOWN" to Color(0xFF9E9E9E)   // Gray
        else -> "UNKNOWN" to Color(0xFF757575)
    }

    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = modifier
            .fillMaxWidth()
            .background(color.copy(alpha = 0.15f), RoundedCornerShape(8.dp))
            .padding(12.dp)
    ) {
        Box(modifier = Modifier.size(12.dp).background(color, RoundedCornerShape(6.dp)))
        Spacer(Modifier.width(8.dp))
        Text(
            text = if (reason != 0) "Fail-Safe: $label (0x%02X)".format(reason)
                   else "Fail-Safe: $label",
            style = MaterialTheme.typography.bodyLarge,
            color = color
        )
    }
}
```

상태 코드는 ICD §1.3과 1:1이다: `0=NORMAL, 1=WARNING, 2=CRITICAL, 3=SHUTDOWN`.

### 3.3 AlertBanner — 사용자 확인까지 유지, I-4-2=A

타이머로 자동 해제하던 코드 예시는 사용자 선택과 달라 제거했다. 구현 산출물은 AlertBanner와 ViewModel의 이벤트별 확인 상태다. 현재 IVI 소스는 없으며 아래는 구현 과제다.

1. 새 IDS 경보마다 내부 event ID와 내용을 함께 보관한다. 같은 attackType의 새 이벤트도 새 경보로 갱신한다.
2. 배너는 해당 이벤트를 사용자가 확인할 때까지 표시한다. 확인 버튼은 표시 중 event ID를 전달한다. 이전 이벤트에 대한 클릭이 더 최신 이벤트를 해제하지 못하게 한다.
3. 확인은 배너 확인 상태만 바꾼다. 탐지 이력·공격 종료 상태·센서 오류·통신 단절·Fail-safe 경고를 정상으로 바꾸지 않는다. 이후 새 경보는 다시 표시한다.
4. 공식 TC-IVI-006의 Flooding 문구와 공격 유형별 표시를 유지한다. 유형 이름 변환은 순수 함수로 시험하되 실제 배너 표시도 별도로 검증한다.
5. 수신→배너 실제 표시 시간, 확인 버튼 접근성, 연속 동일 유형·다른 유형·확인 직전 새 이벤트·앱 재연결을 시험한다. 프로세스 간 이벤트 상태 수명은 M3에서 명세하고 UI 재구성만으로 확인 상태를 초기화하지 않는다.

숫자·SOC 게이지는 사용자 I-4-1=B에 따라 전체 즉시 갱신한다. 가독성 보완과 계측 정본은 [M5](M5_성능_UI개선.md) §3.5다. 센서 표시 정책은 Q-2=A다. 마지막 정상값과 오류/마지막 정상값 표기를 함께 표시하고 정상 측정 이력이 없으면 `측정값 없음`으로 표시한다. R-2=A에 따라 `마지막 정상 데이터 수신 후 …`를 표시하며 [M3](M3_HAL_Service_대시보드.md)의 인증·정상 품질 수신 기록을 사용한다. 기록이 없으면 `경과시간 확인 불가`로 표시한다. R-1=A의 복구 확인 중/상태 확인 불가를 구분하고, R-3=A의 최초 3회 확인 전에는 측정 준비 중·판정 대기를 표시한다. Q-3의 복구 확인 중 오류 표시와 Q-4의 마지막 확정 Fail-safe를 유지한다. 사용자 IDS 확인으로 이 상태들을 해제하지 않는다.

### 3.4 systemd 유닛

사용자 선택 5=C에 따라 **Node A ECU 서비스는 root로 실행**한다. 키는 root 소유·400을 유지한다. 전용 계정·최소 권한·키 전달 방식으로의 전환은 [확인사항](../../../docs/development/governance/의사결정_기록.md#part2-confirmed) §5의 후속 개선 과제다. 배포 SSH 계정은 별개이며 Android Node B에 이 유닛을 적용하지 않는다.


`/etc/systemd/system/ecu-node-a.service` (Node A에 배치):

```ini
[Unit]
Description=Capstone Node A ECU
After=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/ecu
ExecStart=/opt/ecu/adaptive_ecu --interface can0 --secoc on --sensor-mode profile_csv --profile /opt/ecu/data/battery_profile.csv
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

> **인자 표기 주의**: `--secoc on`(공백)이다. `--secoc=on`이나 `--ids=on`은 실제 `main.cpp`가 인식하지 못한다. IDS는 별도 Python 프로세스이므로 필요하면 유닛을 따로 만든다.

```bash
sudo cp ecu-node-a.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ecu-node-a.service
sudo systemctl start ecu-node-a.service

systemctl is-active ecu-node-a.service     # 기대: active
journalctl -u ecu-node-a.service -f
```

### 3.5 SSH 배포 계정과 키

**1) 키 생성 (로컬)**

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ./deploy_key -N ""
cat deploy_key.pub
```

**2) Node A에 배포 계정 등록**

```bash
sudo useradd -m -s /bin/bash deploy
sudo mkdir -p /home/deploy/.ssh /opt/ecu
sudo chown -R deploy:deploy /home/deploy/.ssh /opt/ecu
echo "<deploy_key.pub 내용>" | sudo tee /home/deploy/.ssh/authorized_keys
sudo chmod 700 /home/deploy/.ssh
sudo chmod 600 /home/deploy/.ssh/authorized_keys
sudo chown -R deploy:deploy /home/deploy/.ssh
```

`/etc/sudoers.d/deploy-ecu` — **필요한 명령만 허용한다.**

```text
deploy ALL=(root) NOPASSWD: /bin/systemctl restart ecu-node-a.service, /bin/systemctl status ecu-node-a.service
```

```bash
sudo visudo -c -f /etc/sudoers.d/deploy-ecu     # 문법 검사. 틀리면 sudo 전체가 잠긴다
```

**3) GitHub Secrets 등록**

| Secret | 내용 |
|---|---|
| `RPI_SSH_KEY` | `deploy_key` 개인키 전체 |
| `RPI_NODE_A_HOST` | Node A 접근 주소 |
| `CODECOV_TOKEN` | (Codecov 사용 시) |

- [ ] 개인키·호스트 주소를 저장소나 로그에 남기지 않는다. Secrets만 사용한다
- [ ] `deploy_key`(개인키) 로컬 파일은 등록 후 안전하게 폐기한다

**4) 접속 확인**

```bash
ssh -i ./deploy_key deploy@<Node-A-Host> "echo ok"
```

### 3.6 health_check.sh — 실행 과제

`scripts/health_check.sh`는 미구현 산출물이다. 기존 is-active만 확인하고 PASS를 출력하는 골격은 서비스 생존 검사로만 의미가 있어 제거한다.

1. Node A에서 서비스 활성 상태·실행 UID=root·기대 artifact 버전/hash·시작 오류를 확인한다. 더미 키 기동 시험과 실제 키 접근 권한 검사를 분리하며 키 내용을 출력하지 않는다.
2. CAN 인터페이스가 UP이어도 충분하지 않다. 정해진 관측 시간창에서 새 0x100/0x102 송신과 송신 오류·bus-off를 검사한다. 물리 송신 확인은 peer 캡처로 별도 수행한다.
3. 배포 인수에는 Node B에서 인증된 BMS 반영·stale 해제까지 연결된 smoke 증거가 필요하다. Android는 systemd 대신 해당 init/HAL/service/app 기동 절차를 사용한다.
4. Config 3에서는 IDS 프로세스·모델 로딩·정상 입력 처리·시험 경보 전달도 확인한다. IDS가 없는데 ECU 서비스만 active라는 이유로 Config 3 배포를 합격시키지 않는다.
5. 제한된 시간·재시도 횟수, 단계별 실패 사유·종료 코드, 이전 artifact 복구와 복구 후 재검증을 구현한다. 배포 실패를 새 버전 인수 완료로 기록하지 않는다.

구체적인 준비 대기 시간은 장비 부팅·CAN·세션 측정 후 확정한다. 후속 명령의 PASS 출력은 위 기능 검증을 구현한 뒤에만 허용한다.

### 3.7 CI Stage 4 — 배포 + Health Check

Stage 4: main 배포·Health Check. TC-CI-005~006, 대상별 기동 검증·배포 실패·rollback을 확인한다. 전체 설정·산출물·실패 조건은 [CI 참조](ref_CI파이프라인_명령모음.md) §1만 유지한다. 이 단계에서는 해당 Stage를 구현하고 실행 증적을 인계한다.

### 3.8 IT-001~005 참여

절차 전문은 [02_통합시험](../common/02_통합시험.md)에 있다. IVI 측 확인 항목만 둔다.

| IT | 공식 TC | IVI가 확인할 것 |
|---|---|---|
| IT-001 | TC-INT-001 | 대시보드에 SOC/SOH/전압/전류/온도 표시 |
| IT-002 | TC-INT-003 | Fail-safe CRITICAL/SHUTDOWN Dialog 표시 |
| IT-003 | TC-INT-002 | SecOC 검증 성공 로그, 값 정상 갱신 |
| IT-004 | TC-INT-002 | `ERR_HMAC_VERIFY_FAIL` 로그 + **화면 값 미갱신** |
| IT-005 | TC-INT-004 | 공격 주입 후 **3초 내** AlertBanner |

- [ ] IT-004는 "에러 로그가 찍혔다"만으로 통과가 아니다. **가짜 값이 화면에 반영되지 않아야** 통과다
- [ ] IT-005의 3초는 공격 주입 시점부터 화면 표시 시점까지다. 측정 지점을 ECU와 합의해 기록한다
- [ ] 결과를 `docs/TEST_PLAN.md`에 기록하고 동작 영상을 촬영한다

### 3.9 SDD-IVI App 레이어 절

```markdown
## §3.4 App Layer — Compose Dashboard

### 3.4.1 DashboardViewModel
- StateFlow<VehicleUiState> 기반 상태 관리
- VehicleRepository로부터 데이터 수신
- TC-IVI-008: StateFlow 갱신 지연 ≤20ms

### 3.4.2 SocGauge
- Canvas drawArc + Stroke 원형 게이지
- 색상: ≥50% Green / ≥20% Orange / <20% Red
- TC-IVI-005: 경계 6케이스

### 3.4.3 AlertBanner
- 경고 배너·텍스트 즉시 표시; 장식 요소에만 효과 허용 (S-1=A)
- 새 IDS 이벤트를 표시하고 사용자 확인까지 유지; 새 이벤트는 다시 표시
- TC-IVI-006

### 3.4.4 FailSafeIndicator / CriticalDialog
- 4상태 표시, 사유 코드 병기 (ICD §1.3)
- CRITICAL/SHUTDOWN 시 해제 불가 Dialog
- TC-IVI-007

### 3.4.5 통신 상태
- ICD §2.5.1: 300ms 미수신 시 stale 표시, 유효 수신 시 자동 복구
```

---

## 4. 검증 명령과 합격 기준

```bash
cd ivi_platform/app && ./gradlew test
./gradlew connectedAndroidTest        # Compose UI 시험 (에뮬레이터/실기기 필요)

ssh -i ./deploy_key deploy@<Node-A-Host> "bash /opt/ecu/scripts/health_check.sh"
systemctl is-active ecu-node-a.service
```

| TC | 합격 기준 |
|---|---|
| TC-IVI-006 | AlertBanner에 공격 유형 텍스트 표시, `attackType=0`이면 미표시 |
| TC-IVI-007 | CRITICAL/SHUTDOWN 풀스크린 Dialog, NORMAL에서는 미표시 |
| TC-CI-005 | Stage 4 배포 성공 |
| TC-CI-006 | Health Check PASS |
| TC-INT-001~004 | IT-001~005 전부 Pass |
| 증적 | 동작 영상 촬영, 결과 TEST_PLAN 기록 |
| 태그 | `v0.4.0` |

---

## 5. 실패 시 대응과 우회

**CI에서 SSH 접속 타임아웃**
- GitHub Actions 러너가 사설망의 RPi4에 직접 접근할 수 없다. 이게 가장 흔한 원인이다
- 대안 1: Tailscale·VPN으로 러너를 같은 망에 넣는다
- 대안 2: **self-hosted runner**를 같은 네트워크에 설치한다 (권장)
- 대안 3: Stage 4를 수동 트리거(`workflow_dispatch`)로 바꾸고, 자동 배포 미달성을 문서에 남긴다

**`health_check.sh` 실패**
```bash
sudo systemctl status ecu-node-a.service
journalctl -u ecu-node-a.service --since "5 minutes ago"
ls -la /opt/ecu/adaptive_ecu       # 실행 권한 확인
```
- `ExecStart` 경로와 인자 표기(`--secoc on`)를 먼저 확인한다
- CAN 인터페이스가 없으면 ECU가 `CAN open failed`로 즉시 종료된다. `Restart=always`와 겹쳐 재시작 루프가 된다

**`scp` 시 `Text file busy`**
- `.new`로 보낸 뒤 `mv`로 교체하는 순서를 지켰는지 확인한다

**AlertBanner가 안 뜸**
1. `0x200`이 실제로 오는지: `candump can0 | grep 200`
2. 파서가 `attackType`을 옳게 뽑는지 ([M3](M3_HAL_Service_대시보드.md) 3.1)
3. Service → StateFlow 전파 경로
4. event ID·사용자 확인 상태가 새 경보를 잘못 숨기지 않는지

**IT-004에서 가짜 값이 화면에 뜸**
- `0x100`을 `0x102` 검증 전에 전달하고 있다는 뜻이다. [M3](M3_HAL_Service_대시보드.md) 3.2의 보류 구조를 확인한다. **이것은 통합 시험 실패이자 보안 결함이다**

---

## 6. 완료 체크리스트

- [ ] `DashboardScreen` 전체 레이아웃, Preview 동작
- [ ] `FailSafeIndicator` 4상태 + 사유 코드 표시
- [ ] `AlertBanner` 표시·사용자 확인 해제·새 경보 재표시 (TC-IVI-006)
- [ ] CRITICAL/SHUTDOWN Dialog (TC-IVI-007)
- [ ] `stale` 통신 끊김 표시
- [ ] Node A ECU의 systemd 유닛 등록·`is-active` 확인(IVI 담당의 배포 과제). Android Node B에는 적용하지 않음
- [ ] 배포 계정·SSH 키·sudoers 최소 권한 설정
- [ ] `health_check.sh` 동작 (TC-CI-006)
- [ ] CI Stage 4 배포 성공 (TC-CI-005). 미달성 사유는 기록하되 해당 시험·완료 체크는 미완료로 유지
- [ ] IT-001~005 수행, IT-004에서 값 미갱신 확인
- [ ] 동작 영상 촬영, TEST_PLAN 기록
- [ ] `docs/SDD-IVI.md` App 레이어 절 작성
- [ ] `v0.4.0` 태그 생성


**S-1=A 확정:** 경고 배너·문구를 즉시 완전히 표시하고 장식 효과만 허용한다. 사용자 확인까지 유지하고 신규 경보는 다시 표시한다. 경고 인지/실제 렌더 시점을 장식 효과 시작·종료로 대체하지 않는다. 공식 기준은 SRS FR-IVI-006·SDD-IVI·TEST_PLAN TC-IVI-006의 S 답변 보완을 따른다.


<a id="security-adoption"></a>
## 보안 차용 보강 — 배포 설정·경보와 품질 표시

### 목적·선행조건

N01의 보안 시작 인수와 IVI-APP-01의 표시 회귀를 보강한다. [IVI M3](M3_HAL_Service_대시보드.md#security-adoption)의 verifier 결과와 Q2 계약 상태를 확인한다. Android Node B에 Node A systemd 명령을 적용하지 않는다.

### 수행 절차

1. 일반 배포·시작·재시작에서 양측 인증 설정과 키 로딩 성공/실패를 실제 로그로 대조한다. ECU 배포의 기존 `--secoc on`을 확인하고 C0 실험 OFF를 일반 서비스에 승계하지 않는다.
2. 검증된 정상 값, 오래된 값(stale), 센서 품질 오류, 로컬 인증 오류, 기존 IDS 경보, ECU 실제 Fail-safe를 분리해 표시·기록한다. 정상 이벤트 하나로 사용자 확인 대기 경보를 자동 해제하지 않는다.
3. 0x200 위조·재전송·유실에서 자동 안전 제어가 없고 독립 stale가 동작하는지 시험한다. A5/A6의 로컬 reason을 기존 attackType 5/6 또는 다른 유형으로 임의 인코딩하지 않는다.
4. Q2 전달 오류의 진단 경로는 공동 설계에 연결하되 새로운 HAL/UI 필드를 승인 없이 추가하지 않는다. 이벤트 전달 완료와 UI 렌더 완료를 구분하여 계측한다.

### 검증·실패 대응

TC-IVI-006·TC-INT-002~004와 기존 배포 시험의 실제 화면·상태·시각 증거를 유지한다. 보안 OFF/키 실패의 일반 배포는 정상 인수를 보류하고 구성·키 접근 원인을 해결한다. 경고 문구가 가려지거나 실제로 렌더되지 않았으면 텍스트 로그만으로 통과하지 않는다.

### 완료 체크

- [ ] 시작/재시작/C0 예외의 양측 보안 상태 확인
- [ ] 사용자 확인 경보 정책과 값·센서·통신·보안 상태 구분 검증
- [ ] 미인증 경보의 안전 영향 없음과 실제 렌더 증거 인계
