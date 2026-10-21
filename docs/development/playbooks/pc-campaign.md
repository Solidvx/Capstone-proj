# PC에서 진행하는 3노드 CAN 실험

PC가 전체 실험을 진행하고 Pi3는 CAN 공격만 송신한다. ECU는 정상 송신·IDS, IVI는 정상 수신·SecOC 검증·서비스 게시를 담당한다. AI 없이 PC에서 Python 명령 하나로 실행한다. 기존 Pi3 진행 방식(`live_three_node*`)은 과거 결과 재현용이며 새 실험에는 사용하지 않는다.

| 장비 | 필요한 것 | 두지 않는 것 |
|---|---|---|
| PC | Python 환경, OpenSSH 클라이언트, PC SSH 개인키, 실행 설정, 수집 결과 | SecOC 키, CAN 장치 불필요 |
| ECU | 기존 ECU/IDS, 정상 학습·보정 자료, SecOC 키, 수신 관찰기 | Pi3에서 관리 접속할 권한 불필요 |
| IVI | 기존 IVI 실험 바이너리, SecOC 키, 수신 관찰기 | Pi3에서 관리 접속할 권한 불필요 |
| Pi3 | Python CAN 공격 모듈, can0, PC SSH 공개키 | SecOC 키, ECU/IVI 접속용 SSH 개인키 불필요 |

PC → SSH → 각 노드는 실행·종료·로그 전송용이다. Pi3 → CAN H/L → ECU·IVI는 실제 공격 경로다. SSH로 공격 데이터를 ECU·IVI 프로그램에 주입하지 않는다. CAN/SecOC wire 계약은 변경하지 않는다.

## 1. 기존 준비는 보존하고 소스만 업데이트

세 노드의 `~/Capstone-three-node`에서 작업 파일·브랜치를 확인하고 최신 develop을 받는다. PR 검토 중이면 해당 PR 브랜치를 사용하며 임의로 dirty 변경을 덮어쓰지 않는다. ECU·IVI의 기존 빌드·Python 환경·CAN 설정·키·결과를 삭제하지 않는다. 이번 변경은 Python 실험 도구 중심이며 기존 ECU·IVI 바이너리를 바꾸지 않는다.

```bash
cd ~/Capstone-three-node
git status --short
git branch --show-current
# develop이고 변경 파일이 없을 때
git pull --ff-only origin develop
```

PC에서도 동일 버전의 저장소와 Python 환경을 준비한다. macOS/Linux 또는 Windows의 WSL에서 실행한다. 네이티브 Windows 셸은 현재 프로세스 그룹·파일 잠금 구현의 지원 대상이 아니다.

```bash
python3 -m venv .venv-handoff
.venv-handoff/bin/python -m pip install -r security/requirements.txt
.venv-handoff/bin/python -m security.experiments.pc_campaign --help
```

PC 명령에는 `--key`가 없다. Qt·ECU를 PC에서 빌드할 필요가 없다. OpenSSH의 ssh·ssh-copy-id·ssh-keygen이 필요하며 ssh-copy-id가 없는 환경에서는 해당 PC의 OpenSSH 설치 방법으로 준비한다.

## 2. PC 전용 SSH 인증 준비

아래는 **PC 터미널**이다. Pi3에서 실행하지 않는다. 기존 PC 전용 SSH 키를 사용할 수도 있다. 새로 만들 때 파일이 이미 있으면 덮어쓰지 않는다.

```bash
ssh-keygen -t ed25519 -f "$HOME/.ssh/capstone_pc" -C capstone-pc-controller
ssh-copy-id -i "$HOME/.ssh/capstone_pc.pub" ECU사용자@ECU주소
ssh-copy-id -i "$HOME/.ssh/capstone_pc.pub" IVI사용자@IVI주소
ssh-copy-id -i "$HOME/.ssh/capstone_pc.pub" Pi3사용자@Pi3주소
```

자동 실행은 SSH agent에 잠금 해제한 키 또는 무암호 전용 키를 사용한다. 키 암호가 있는 경우 PC에서 `ssh-add "$HOME/.ssh/capstone_pc"` 후 실행한다. 대상의 호스트 키를 확인하고, 각 접속에 `-i "$HOME/.ssh/capstone_pc" -o BatchMode=yes`를 붙여 hostname이 나오는지 확인한다. 개인키는 PC에만, 공개키는 각 노드의 authorized_keys에 등록된다. 개인키나 SecOC 키 내용을 채팅·Git에 올리지 않는다.

## 3. PC 설정 파일 만들기

```bash
mkdir -p tmp
cp -n security/experiments/pc-campaign-settings.template.json tmp/pc-campaign-settings.json
```

PC의 편집기로 `tmp/pc-campaign-settings.json`을 연다. 같은 REPLACE 표식은 모두 같은 값으로 바꾼다. 절대경로를 사용하고 `~`는 넣지 않는다.

| 표식 | 넣을 값 |
|---|---|
| REPLACE_PC_SSH_PRIVATE_KEY | PC의 capstone_pc 개인키 절대경로 |
| NODE_A / NODE_B / NODE_C USER·HOST | 각각 ECU / IVI / Pi3 계정·주소 |
| NODE_A / NODE_B / NODE_C PROJECT | 각 노드의 Capstone-three-node 절대경로 |
| NODE_A_KEY / NODE_B_KEY | 해당 노드에만 있는 동일 시험용 SecOC 키의 경로 |
| NODE_A_TRAIN_CAPTURE / CALIBRATION_CAPTURE | 기존 검증된 독립 정상 캡처 경로 |
| NODE_A_LOG_DIRECTORY | ECU에 존재하며 해당 계정이 쓸 수 있는 로그 디렉터리 |

키 내용이 아니라 경로만 설정한다. Pi3 명령에는 SecOC 키 경로가 없다. PC도 해당 키 파일을 읽지 않는다. 설정 파일은 명령을 포함하는 신뢰된 로컬 파일로 취급하며 Git에 커밋하지 않는다. 실제 프로젝트/SSH 키 경로에 공백이 있으면 원격 셸 인용을 맞춰야 한다.

기본 interface는 모든 노드에서 can0/500000이며 변경 시 모든 관련 명령과 CLI를 일치시킨다. ECU·IVI는 기존 키·학습/보정 데이터 준비가 필요하다. ECU의 CAN·I²C·키 접근 권한과 health/IVI 명령의 sudo -n 실행 권한도 필요하다. 무제한 NOPASSWD 규칙을 추가하지 않는다. 권한이 없으면 스크립트는 비밀번호를 기다리지 않고 중단한다.

기본 IVI는 offscreen 실험 바이너리로 서비스 게시를 기록한다. 실제 모니터 표시 시험이 필요하면 receiver_on/off의 Qt 환경을 해당 IVI 사용자 세션에 맞추어 별도 검증한다. offscreen 로그를 화면 표시 성공으로 간주하지 않는다.

## 4. Pi3에 만들었던 불필요한 SSH 권한 정리

**PC의 독립 키로 세 노드 접속을 확인한 다음에만** 정리한다. 이번에 만들었던 이름과 지문이 일치하는 키만 대상으로 한다.

PC에서 삭제 없이 미리보기:

```bash
.venv-handoff/bin/python -m security.experiments.retire_pi3_ssh \
  --settings tmp/pc-campaign-settings.json
```

출력의 matching_lines·fingerprint와 대상 노드를 확인한 다음 실제 적용:

```bash
.venv-handoff/bin/python -m security.experiments.retire_pi3_ssh \
  --settings tmp/pc-campaign-settings.json --apply
```

삭제 범위는 정확히 다음과 같다.

- ECU·IVI authorized_keys에서 Pi3의 `capstone_experiment.pub`와 **키 본문이 같은 행만** 제거한다. 원본 authorized_keys는 별도 백업한다.
- PC 접속을 재확인한 뒤 Pi3의 `~/.ssh/capstone_experiment` 및 `.pub`만 제거한다.
- PC가 삭제 대상 Pi3 키를 복사해 쓰는 경우 거부한다. 개인키/공개키 지문이 다르거나 심볼릭 링크이면 거부한다.
- 기본 미리보기는 삭제하지 않는다. 이미 키를 정리한 뒤 다시 실행하면 키 없음으로 멈추며, 다른 키를 추측해서 지우지 않는다.

`~/.ssh` 전체, 다른 SSH 키, known_hosts, SecOC 키, 저장소, `.venv-handoff`, CAN 부팅 설정, 학습/보정 자료, 기존 결과는 삭제하지 않는다. 현재 확인된 불필요한 신규 산출물은 Pi3의 관리용 키 쌍과 A/B의 해당 공개키 권한이다. 과거 tar.gz·프로젝트 복사본은 역할·보존 필요성을 확인하지 못했으므로 자동 삭제 대상으로 삼지 않는다. 실행 실패 시 이미 끝난 정리 단계와 백업을 확인하고 개인키를 임의로 재생성하지 않는다.

## 5. 한 명령으로 실험 실행

실험은 전용 CAN 시험 버스에서만 진행한다. PC가 켜져 있고 네트워크가 연결된 상태를 유지한다. 기존 수동 ECU·IDS·IVI 실험 프로세스는 종료해 중복 송신을 피한다.

먼저 12조건 한 회씩 점검:

```bash
.venv-handoff/bin/python -m security.experiments.pc_campaign \
  --settings tmp/pc-campaign-settings.json --stage pilot \
  --run-id PC-PILOT-001 --out tmp/pc-pilot-001 --i-am-on-a-test-bus
```

테스트 360회(3구성 × 4공격 × 30회):

```bash
.venv-handoff/bin/python -m security.experiments.pc_campaign \
  --settings tmp/pc-campaign-settings.json --stage test360 \
  --run-id PC-TEST360-001 --out tmp/pc-test360-001 --i-am-on-a-test-bus
```

정식 1,200회(구성·공격별100회)는 동일 소스·설정·조건으로 깨끗하게 종료한 유효12회 PC pilot이 필요하다:

```bash
.venv-handoff/bin/python -m security.experiments.pc_campaign \
  --settings tmp/pc-campaign-settings.json --stage official --pilot-dir tmp/pc-pilot-001 \
  --run-id PC-OFFICIAL-001 --out tmp/pc-official-001 --i-am-on-a-test-bus
```

정상일 때 조합 내 프로그램/IDS 상태를 유지해 연속 실행한다. 구성·공격 조합 전환 또는 실행 오류 복구 시에만 재시작한다. 유형 불일치·미탐·개별 INVALID는 기록하고 계속한다. 프로세스 종료·baseline 부족 등 복구 가능한 오류는 종료 확인 후 CAN 상태를 점검/필요시 재설정하고 최대2회 재시도한다. 잘못된 키·설정·저장·로그수집 오류나 원격 종료 불명은 중단한다. `--max-recoveries 0`으로 자동 복구를 끈다.

중단 후에는 같은 명령 끝에 `--resume`을 붙인다. 완료된 번호는 INVALID를 포함해 건너뛰고 미완료 번호부터 이어간다. 실패 기록을 삭제하지 않는다. 매회 재시작/기존 Pi3 진행 결과는 PC 실행기로 재개할 수 없다. 강제 종료로 미봉인되거나 원격 종료 불명 상태이면 자동 재개를 거부한다. 코드/설정이 바뀌었으면 새 run-id/out을 사용한다.

## 6. PC에 모이는 결과

출력 경로 아래에 아래 자료가 저장된다. SSH stdout/stderr 수집과 ECU IDS 원본 로그 가져오기는 스크립트가 수행한다.

| 파일 | 내용 |
|---|---|
| campaign.json, settings.json | 실행 조건·소스 해시·로컬 설정 사본 |
| checkpoint.json | 최근 종료된 구간의 완료 번호와 상태 |
| summary.json | 계획/완료/유효/무효/남은 수, 구성·공격별 유형 집계 |
| C3-fuzzy/attempt-001/attacker.jsonl | Pi3 TX·RX·송신 오류·replay 원본 증거 |
| 같은 경로의 observer_a/b.jsonl | ECU·IVI 전체 버스 수신 및 구간 ACK |
| ivi.jsonl, ecu.jsonl, ids-console.jsonl 및 stderr | 각 프로그램 원격 출력 |
| ids-events.jsonl | ECU의 IDS 원본 이벤트 로그(C3) |
| attempts.jsonl, manifest.json | 회차 판정·무효 사유와 증거 파일 해시 |

MATCH=기대유형만, COMPOUND=기대유형 포함 여러 유형, MISMATCH=다른 유형만, MISSED=경보 없음이다. C1/C2는 IDS OFF이므로 NOT_EVALUATED다. 수신/정상 게시 증거가 부족하면 INVALID다. 상대 노드에서 공격 payload가 관찰됐는지와 Pi3의 자기 echo를 구분한다.

CAN payload 일치는 발신자 인증이 아니다. Replay는 키 없이 정상 버스에서 관찰한 raw/auth 쌍을 복사하며, MAC 검증 여부를 `authenticated=false`로 명시한다. 실제 SecOC 검증은 ECU·IVI가 수행한다. ECU IDS 원본의 ANOMALY/ALERT_SENT를 ECU 관찰기 구간으로 분리하고, IVI에 게시된 같은 경보 payload와 연결한다. raw CAN 경보와 실제 IDS 송신에 연결된 IVI 유형 결과를 구분한다. 0x200은 인증 비대상이므로 payload 일치 자체를 암호학적 발신 증명으로 간주하지 않는다. IVI 유형 판정은 Node B 관찰기 구간과 IVI의 같은 호스트 monotonic 타임스탬프를 비교하며 다른 노드의 시각을 빼지 않는다. 이 모드의 차단율·공격 성공률·탐지 지연은 측정하지 않으며 null/NOT_EVALUATED로 남긴다. 과거 공격자 참조 인증 지표와 합산하지 않는다.

종료 코드0은 모든 계획 번호의 유효한 수집 완료이며 탐지 합격을 뜻하지 않는다. 무효/실행 오류는2, Ctrl+C는130이다. 소프트웨어 시험 통과와 실장비360회 성공은 구분한다.
