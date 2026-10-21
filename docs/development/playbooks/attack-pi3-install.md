# 공격 Raspberry Pi 3에 소스 설치하기

대상은 **공격 Pi3 터미널**이다. ECU·IVI의 프로젝트를 덮어쓰지 않는다. 이번 PR 브랜치는 `feat/three-node-campaign`이며 검토·병합 전에는 시험용 브랜치로 사용한다.

## 1. 무엇을 올리는가

개별 파일 복사 대신 저장소를 Git으로 받아 같은 버전을 유지한다. 다운로드하는 것과 실행하는 것은 다르며, Pi3에서는 ECU C++와 IVI Qt를 빌드하지 않는다.

| 경로 | Pi3에서 쓰는 이유 |
|---|---|
| `security/experiments/live_three_node.py` | 12조건 × 100회 캠페인 제어 |
| `security/experiments/live-three-node-settings.template.json` | ECU·IDS·IVI 원격 실행 명령의 양식 |
| `security/experiments/` | CAN 캡처, 공격 시점, replay, 참조 검증, 판정·집계와 원격 프로세스 관리 |
| `security/attacks/`, `security/secoc/`, `security/ids/` | 공격 생성·참조 인증·실험 실행기의 내부 import 의존성 |
| `security/requirements.txt` | Python 의존성의 저장소 기준 |
| `security/tests/` | 로컬 검증 시 사용. 설치 파일만 확인할 때는 실행하지 않아도 됨 |

`live_three_node.py` 한 파일만 옮기면 동작하지 않는다. USB로 전달할 경우에도 **같은 커밋의 `security/` 전체**와 저장소의 패키지 구조를 유지하고 저장소 루트에서 실행한다. Python 가상환경·macOS 바이너리·빌드 폴더는 Pi3로 복사하지 않는다.

키, 정상 캡처, 실장비 설정은 Git에 포함하지 않는다. Pi3의 시험 키는 참조 인증 검증용이고, 실제 ECU/IDS는 ECU에서, Qt 수신기는 IVI에서 실행한다.

## 2. 빈 Pi3에 PR 브랜치 받기

기존 `~/Capstone-three-node` 폴더가 있으면 먼저 확인하고 새 이름을 사용한다. 삭제하거나 덮어쓰지 않는다. 저장소가 비공개이면 기존 GitHub 인증 수단을 사용하며 토큰을 URL에 넣지 않는다.

```bash
sudo apt update
sudo apt install -y git python3-venv python3-pip openssh-client can-utils iproute2
git clone --branch feat/three-node-campaign --single-branch \
  https://github.com/Solidvx/Capstone-proj.git "$HOME/Capstone-three-node"
cd "$HOME/Capstone-three-node"
git status --short
git log -1 --format='%h %s'
```

PR 검토 완료 전이면 이 브랜치가 `develop`에 포함됐다고 가정하지 않는다. 병합 후에는 세 노드의 소스 버전을 함께 맞춘 뒤 새 pilot부터 실행한다.

## 3. Python 환경 만들고 진입점 확인

```bash
python3 -m venv .venv-handoff
.venv-handoff/bin/python -m pip install -r security/requirements.txt
.venv-handoff/bin/python -m security.experiments.live_three_node --help
.venv-handoff/bin/python -m security.experiments.remote_process --help
```

`--help`는 CAN 송신이나 원격 프로세스 실행을 하지 않는다. Pi3 OS/아키텍처에 따라 패키지 설치 시간이 길어질 수 있으며, 오류 시 첫 오류와 Python 버전을 확인한다. 설치 실패를 `sudo pip`로 우회하지 않는다.

## 4. 장비별 설정 준비

```bash
mkdir -p tmp
cp -n security/experiments/live-three-node-settings.template.json tmp/live-three-node-settings.json
nano tmp/live-three-node-settings.json
```

다음 값은 실장비에 맞춰 입력한다.

- ECU·IVI의 SSH 사용자/호스트, 프로젝트 절대 경로.
- ECU 제품 바이너리, IVI의 `ivi_dashboard_experiment` 실제 경로. IVI 빌드는 `-DIVI_BUILD_EXPERIMENT_TOOLS=ON`이 필요하다.
- 세 노드에 배치한 동일한 격리 시험 키의 장비별 경로. 키 내용을 문서나 터미널 출력에 넣지 않는다.
- ECU에 둔 독립 정상 학습·보정 캡처의 경로와 유효 manifest.
- ECU IDS 로그 출력 디렉터리, 파일 권한, 원격 supervisor와 자식의 종료 권한.

ECU·IVI에도 이 PR의 `remote_process`와 관련 구현이 필요하다. Pi3에만 소스를 설치한 것으로 원격 시험 준비가 끝나지 않는다. `ssh -o BatchMode=yes` 접속과 필요한 `sudo -n` 명령의 권한을 개별 확인한다. 템플릿의 `sudo`를 이유로 포괄적 NOPASSWD 설정을 추가하지 않는다.

기본 템플릿은 IVI offscreen 수신 및 ECU constant 입력이다. 실화면·ADC 변화 인수와 구분한다. 정확한 시험 명령과 12회 pilot → 1,200회 게이트는 [3노드 실험 절차](three-node-hardware-experiment.md)의 6절을 따른다.

## 확인된 범위

사용자가 제공한 세 노드 화면에서 ECU·IVI·Pi3가 각각 보낸 0x123 프레임을 다른 두 노드가 수신하고, 표시된 오류 카운터가 0임을 확인했다. 이는 단발 CAN 송수신 증거이며 장시간 부하·SecOC·IDS·원격 실행·1,200회 인수는 아니다. 화면에 나온 장비 주소는 이 문서에 기록하지 않는다.
