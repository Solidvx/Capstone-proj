# Pi 수동 실행 인계 — 작업본 패키지

담당 경계: 사용자는 Pi 파일 전송·명령·화면/회로 조작·원본 로그 수집, Codex는 코드·패키지·로컬 검증·반환 로그 분석을 맡는다. 원격 접속 정보나 키 내용은 전달할 필요가 없다.

이 패키지는 **미커밋 파일을 포함하는 현재 작업본 snapshot**이며 Git release가 아니다. 기존 프로젝트·설치 바이너리·키·systemd·CAN 설정을 덮어쓰지 않는다. 새 시험 디렉토리에서 빌드하고 원본은 보존한다. archive에 키, .env, 가상환경, 바이너리, 모델, 원시 로그는 넣지 않는다.

## 1. 패키지 복사·검증 — 두 Pi 모두

Mac의 전달 폴더에서 다음 두 파일을 원하는 방법으로 **각 Pi의 홈 디렉토리**에 복사한다.

- `capstone-pi-handoff.tar.gz`
- `capstone-pi-handoff.tar.gz.sha256`

Pi 터미널에서 다음을 실행한다. checksum이 `OK`가 아니면 중단한다.

```bash
cd ~
sha256sum -c capstone-pi-handoff.tar.gz.sha256
```

checksum 확인 후 새 시험 디렉토리에 푼다. 같은 이름이 있으면 다른 새 이름을 정한다. `mkdir` 실패 시 추출하지 않도록 `&&`를 사용한다.

```bash
mkdir "$HOME/capstone-test-20261003-003" && \
  tar -xzf "$HOME/capstone-pi-handoff.tar.gz" -C "$HOME/capstone-test-20261003-003"
cd "$HOME/capstone-test-20261003-003/Capstone-handoff"
sha256sum -c HANDOFF-FILES.sha256
```

모든 파일이 `OK`인지 확인한다. 이후 모든 상대 경로 명령은 이 `Capstone-handoff` 디렉토리에서 실행한다.

## 2. 읽기 전용 환경 자료 — 역할별 실행

기존 키의 **실제 경로**를 지정한다. 아래 경로는 기존 절차의 예시이며 서로 다를 수 있다. 존재하는 경로를 사용하고 새 키를 생성하거나 내용을 출력하지 않는다. 서로 다른 파일 경로라도 양측 key 내용은 동일해야 한다.

ECU Pi:

```bash
python3 ivi_platform/scripts/collect_pi_preflight.py \
  --role ecu --key /etc/secoc/key.bin --output ECU-preflight.json
```

대시보드 Pi의 화면이 있는 데스크톱 터미널:

```bash
python3 ivi_platform/scripts/collect_pi_preflight.py \
  --role ivi --key /etc/ivi/secoc.key --output IVI-preflight.json
```

명령은 CAN bitrate/UP 상태·프로세스·키 파일 크기/권한·Qt/CMake/Python 버전을 **수집만** 한다. 키 내용은 읽지 않는다. `COLLECTED`는 PASS가 아니며 누락/명령 실패도 JSON 안에 보존한다. 동일 출력 파일은 덮어쓰지 않는다.

## 3. 독립 재빌드 — 역할별 실행

ECU Pi:

```bash
cmake -S adaptive_ecu -B adaptive_ecu/build-handoff \
  -DCMAKE_BUILD_TYPE=Release -DECU_BUILD_TESTS=ON
cmake --build adaptive_ecu/build-handoff -j2
ctest --test-dir adaptive_ecu/build-handoff --output-on-failure
python3 -m venv .venv-handoff
.venv-handoff/bin/python -m pip install -r security/requirements.txt
.venv-handoff/bin/python -m pytest -p no:cacheprovider security/tests -q
```

대시보드 Pi:

```bash
cmake -S ivi_platform -B ivi_platform/build-handoff \
  -DCMAKE_BUILD_TYPE=Release -DIVI_BUILD_TESTS=ON \
  -DIVI_BUILD_QT_APP=ON -DIVI_BUILD_EXPERIMENT_TOOLS=ON
cmake --build ivi_platform/build-handoff -j2
ctest --test-dir ivi_platform/build-handoff --output-on-failure \
  --exclude-regex '^test_socketcan_receiver$'
test -x ivi_platform/build-handoff/ivi_dashboard
test -x ivi_platform/build-handoff/ivi_dashboard_experiment
```

각 단계가 실패하면 뒤 명령을 계속 실행하지 않고 오류를 가져온다. Qt가 없으면 CMake가 core만 빌드할 수 있으므로 **마지막 두 바이너리 검사까지 성공해야** 대시보드 빌드 성공이다. 제품 `ivi_dashboard`는 인증 유지, experiment 바이너리의 인증 OFF는 M5 격리 시험용이다. 이 단계에서는 실행·설치·서비스 교체를 하지 않는다. 실제 SocketCAN receiver 테스트는 vcan 시험 환경 준비 후 따로 실행하며 skip을 PASS로 세지 않는다.

### 먼저 가져올 결과

| 노드 | 반환할 자료 |
|---|---|
| ECU | `ECU-preflight.json`, CMake/빌드 오류 또는 성공 마지막 부분, CTest 전체 요약, Python pytest 요약 |
| IVI | `IVI-preflight.json`, CMake/빌드 오류 또는 성공 마지막 부분, CTest 전체 요약, 두 바이너리 검사 성공 여부 |
| 공통 | archive checksum `OK`, source checksum 실패가 있으면 해당 줄 |

## 4. 환경·빌드 확인 후 진행할 순서

1. 양측 실행 경로·현재 프로세스·기존 key 경로/접근 권한을 확인한 뒤 기존 송신기/수신기를 정상 종료한다. 무차별 `pkill`, 권한 완화, 기존 파일 삭제는 하지 않는다.
2. 이번 build-handoff의 **제품** ECU/대시보드로 정상 ADS1115 knob·0x100/0x102·UI LIVE/NORMAL을 확인한다. CRITICAL latch와 데이터 업데이트를 구분한다.
3. 정상 candump 원본, CAN 통계 전/후, 화면을 수집하고 100ms 주기를 분석한다. 날짜/run ID가 다른 새 파일을 쓴다. 데이터가 오지 않는 candump를 무한 대기시키지 말고 제한 시간 후 종료·실패 로그를 보존한다.
4. 정상 학습 capture/manifest를 수집한 뒤 IT-004 MAC 변조→75% 기준→위조100% 미게시→70% 정상 복구를 확인한다.
5. IDS rules+IF READY 후 IT-005 공격·0x200·AlertBanner·정상 복구를 확인한다.
6. M5 물리 12조합 파일럿→부하·시간·설정 calibration→새 run의 공식 1,200회와 별도 정상 FPR/ROC 평가를 진행한다.

실행 명령/안전 기준은 [CAN 통합](security-can-integration.md), [M5 하네스](m5-ablation-runner.md)를 따른다. 그 문서의 기존 `build` 경로는 이번 시험에서는 `build-handoff`, `.venv`는 `.venv-handoff`로 바꾼다. 정상 sender와 fixture를 동시에 실행하지 않는다. 회로가 두 Pi만 연결된 격리 시험버스인지 확인하기 전에는 공격 명령을 실행하지 않는다.

실제 로그가 반환되기 전에는 물리 단계 완료·성능 PASS·공식 결과를 기록하지 않는다.
