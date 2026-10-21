# 3노드 실험 인수인계 — 2026-10-22

## 1. 인수자가 먼저 알아야 할 상태

[실험 보고서](../experiments/three-node-validation-20261022.md)가 결과·한계의 원본이다.
PC가 실험을 제어하고 Pi3는 CAN 공격만 송신한다. ECU는 정상 센서 송신·IDS, IVI는 수신·검증·화면을 담당한다.
360회 유형 시험과 두 정상 조건 오탐률, 네 공격의 화면 표시, 소규모 replay 및 MAC 변조30회 거부를 확인했다.
**공식1200회와 재부팅 자동실행은 사용자가 오늘 범위에서 제외했다.**
Flooding 가용성 정량 평가·필터 차단 효과·일반화 가능한 공격 차단율은 아직 완료되지 않았다.

## 2. 코드와 결과를 혼동하지 않기

- PR #30: isolated-v1, IDS 분류 근거 수정, 오류 발생 후 다음 조합 진행.
- PR #31: IVI 거부 후보 분석과 수동 화면 증거.
- 보고서/인수인계 PR: 후속 실측·MAC 반복 도구·본 안내.
- 실제 시험은 장비에 일부 파일을 직접 반영한 상태에서 진행했다. 당시 git HEAD만으로 실험 소스를 특정하지 않는다.
- 360회 campaign.json의 source_sha256와 증거 묶음 source/pc-run 및 devices의 장비 소스 스냅샷을 함께 확인한다.
- 새 pc_mac_check 모듈은 실제 실행된 로컬 run_mac_check.py를 경로 인수 방식으로 정리한 것이다. 30회 실측은 source/manual의 당시 스크립트 근거이며 새 CLI는 별도 실장비 재실행하지 않았다.

## 3. 증거 묶음 읽기

| 경로 | 내용 |
|---|---|
| pc/pc-types360-001 | 물리360회 원본에서 만든 공유 사본 |
| pc/pc-pilot-* 및 pc/pc-types-001 | 초기 실패·혼합 및 분리 예비시험; 실패를 삭제하지 않음 |
| pc/mac-repeat-20261022-061633 | 30회 변조 주입·IVI 일치 로그·summary |
| devices/ecu | 정상 고정·조작 캡처/평가, 빈 캡처 실패, 당시 IDS 소스 |
| devices/receiver_on | IVI 상세 처리 로그의 수집 시점 스냅샷 |
| devices/attacker | Pi3 수동 replay/MAC 및 반복 주입 로그, 당시 worker 소스 |
| source/pc-run | PC 실행 코드 스냅샷 |
| source/manual | 당시 임시 제어/배포 스크립트의 비식별 공유 사본; 그대로 실행용이 아님 |
| FILES.json | 파일별 원본 SHA-256, 공유 사본 SHA-256, 비식별 처리 여부 |
| SHA256SUMS | 공유 파일 무결성 검사 목록 |

실제 키·인증정보와 PC settings.json은 포함하지 않는다. 주소·계정·홈 경로는 필요한 곳에서 치환했다.
비식별 처리된 파일은 원본 manifest 해시와 다를 수 있다. FILES.json의 redacted와 원본/공유 해시를 확인한다.
공유 묶음은 분석 증거이고 기존 캠페인의 --resume 입력으로 쓰지 않는다. 원본은 원 담당자 PC의 private 보존본 및 장비에 남겨둔다.
실행 중인 IVI 로그는 수집 당시의 스냅샷이며 이후 추가된 로그를 포함하지 않는다.

## 4. 장비 준비 및 버전 업데이트

각 노드 저장소는 사용자 홈의 Capstone-three-node다. 실제 계정·주소는 담당자에게 별도로 받는다.
`git status --short`를 먼저 확인하고 직접 수정본은 해당 파일만 별도 백업/stash로 보존한다.
ECU 직접 수정은 security/ids/runtime.py와 runtime_detector.py, Pi3는 can_attack_worker.py였다.
임의 reset/clean 또는 .ssh 전체 삭제를 하지 않는다. 승인된 PR 머지 뒤 develop을 fast-forward로 받는다.
Python 환경은 .venv-handoff이며 ECU·IVI 실행 파일은 아래 경로다.

- ECU: adaptive_ecu/build/adaptive_ecu
- IVI 일반: ivi_platform/build-handoff/ivi_dashboard
- IVI 실험: ivi_platform/build-handoff/ivi_dashboard_experiment

CAN은 각 노드 can0/500000, ERROR-ACTIVE, loopback/listen-only OFF를 확인한다.
키는 ECU·IVI에만 유지한다. 비밀번호 없는 SSH 관리 접속은 PC 전용 키로 수행한다.
대시보드 자동실행의 /opt/ivi 설치본은 최신 빌드와 다를 수 있다. 재부팅 검증이 끝났다고 가정하지 않는다.

## 5. 실행 방법

### 자동 유형 시험

PC에서 pc-campaign-settings.template.json을 로컬 제외 경로로 복사하고 실제 장비 정보·원격 키 경로를 채운다.
키 내용은 설정에 넣지 않는다. 수동 ECU/IDS/IVI 프로세스가 있으면 먼저 정상 종료해 중복 실행을 막는다.
[PC 실행 안내](pc-campaign.md)의 명령을 사용하며 아래 인수로 이번 조건을 재현한다.

```bash
python -m security.experiments.pc_campaign --settings LOCAL_SETTINGS.json --stage test360 --attack-profile isolated-v1 --sensor-mode ads1115 --max-recoveries 2 --continue-on-error --no-can-reset --run-id NEW-RUN-ID --out NEW-OUTPUT --i-am-on-a-test-bus
```

정상 시 조합별30회 연속 실행, 총12세션이다. 유형 오판정/미탐을 숨기지 않는다.
복구 소진 후 안전한 다음 조합 진행은 PARTIAL로 남기며 완료되지 않은 번호만 재개한다.
원격 종료 미확인·저장/로그 수집 오류·CAN 이상은 계속하지 않는다.

### 정상 오탐률

ECU 창1은 정상 송신, 창2는 캡처 후 평가에 사용한다. Pi3 공격과 별도 IDS는 끈다.
대시보드는 선택적으로 켜둘 수 있지만 이는 오프라인 IDS 평가다.
고정과 조작을 새 디렉터리로 각각 캡처한다. 같은 환경의 기존 fit/calibration과 독립 평가 자료를 사용한다.
빈 캡처나 드롭/오류가 있으면 오탐0으로 계산하지 않는다. 실제 명령과 계산은 보고서6절을 따른다.

### 반복 MAC 거부 시험

ECU 정상 송신과 observation-jsonl을 기록하는 최신 IVI 대시보드를 먼저 실행한다. 별도 IDS/Pi3 공격은 종료한다.
현재 PC 도구는 수신 로그의 최근 SecOC ON 정상 게시를 확인한 뒤 Pi3에서30쌍을 주입한다.

```bash
python -m security.experiments.pc_mac_check --settings LOCAL_SETTINGS.json --ivi-log ivi-evidence/BLOCK-RUN/ivi.jsonl --out NEW-MAC-OUTPUT --i-am-on-a-test-bus
```

IVI 경로는 IVI 사용자 홈에 상대적이다. 공격 모듈에 키를 전달하지 않는다.
MAC_REJECTED, OTHER_REJECTION, PUBLISHED, UNOBSERVED, AMBIGUOUS를 구분한다.
complete_coverage=false이면 일부 귀속 가능 후보의 비율을 전체 차단율로 발표하지 않는다.
도구는 입력 파일을 덮어쓰지 않는다. 실패 출력과 로그를 보존하고 새 출력 폴더로 재시도한다.

## 6. 자주 발생한 오류

- Mac 명령 앞에 ssh를 붙이면 `cd`를 호스트로 해석한다. PC 실행기를 Mac에서 직접 실행한다.
- 정상 송신 `adaptive_ecu`와 IDS `rules+if` READY는 다른 프로세스다. IDS만 실행하면 정상 캡처가 비게 된다.
- can_capture는300초 동안 출력이 없을 수 있다. candump 5초 동안 아무 프레임도 없는 것은 정상 수신 확인 실패다.
- 줄 끝 역슬래시 뒤 공백은 셸 명령 연결을 깨뜨린다.
- worker의 수동 stdin에 빈 줄을 넣으면 JSON 파싱 오류로 종료될 수 있다. 준비된 PC 자동 도구를 사용한다.
- CAN 상태가500000과 다르면 직접 설정을 확인한다. sudo 임시 인증은 SSH 비대화형 권한 보장이 아니다.
- 화면이 없더라도 offscreen 시험은 실행된다. 화면 시험을 했다는 근거로 대신 쓰지 않는다.

## 7. 종료와 다음 담당자의 작업

PC 자동 실험은 종료 ACK를 수집한다. 수동 시험의 ECU/IDS/Pi3는 해당 터미널 Ctrl+C로 종료한다.
화면을 계속 쓸 경우 정상 ECU와 IVI는 유지할 수 있다. 인수 시 어떤 프로세스를 남겼는지 별도로 확인한다.
원격 상태가 현재도 같다고 가정하지 않는다.

1. 보고서·공유 묶음 무결성을 확인하고 정상 FPR 원본 및 거부 source_data를 검토한다.
2. 미완료 flooding 가용성의 분모·부하·정상 BMS 갱신 기준을 고정하고 별도 실행한다.
3. 필요 시 반복 replay 및 C1/C2/C3 인증 공격 대조로 소규모 결과를 확장한다.
4. 사용자가 제외한 공식1200회와 재부팅 자동실행은 별도 일정에서 진행한다.
