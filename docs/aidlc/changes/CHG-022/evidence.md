# CHG-022 검증·원격 코드 반영 근거

2026-10-21, macOS arm64 / AppleClang 21 / Python 3.9. 시작 HEAD `5b7e7ed`, 브랜치 `feat/ecu-recovery-quality`.

## 최신 원격 확인

`git fetch origin develop` 성공. 원격 기준은 `76b56f4de899098aeac6833bec84dba656b9cc17`(PR #26 merge). 처음 .git 쓰기 제한으로 실패한 뒤 승인된 sandbox escalation으로 fetch했다. 현재 브랜치를 전환·병합하지 않았다. `git archive origin/develop`를 `tmp/chg022-develop/`에 풀어 실제 파일을 대조했다.

현재 작업본에 선별 반영한 원격 변경:

- ECU: `ads1115_capture.cpp`, `failsafe_demo_fast.csv`와 manifest, `test_failsafe_profile.cpp`, 대응 CMake target. 기존 task_recovery 수정은 보존했다.
- IDS: runtime·IF·README, 커널 수신 시각·송신 backpressure·독립 정상 보정, 대응 회귀시험.
- 실험: can_capture/evaluate_normal, live_ablation/live_receiver/live_trial/summarize_live, 이에 연결된 mac_fixture/measure_runtime_fpr/analyze_adc와 시험. train_model API 변경에 필요한 score_ids_captures와 원격 시험에 연결된 합성 집계 환경 분리도 반영했다.
- 이외 원격 문서·과거 결과·무관한 구현 전체를 현재 브랜치로 덮어쓰지 않았다. 원격 CHG-019와 현재 사용자 CHG-019는 다른 작업 기록이므로 원격 것을 복사하지 않았다.

원격 live_ablation은 제품 ECU·IDS를 공격과 같은 호스트에서 실행한다. 이번 live_three_node는 공격·참조 관측을 RPi3, 제품 ECU·IDS를 A, 실제 IVI 실험 수신기를 B로 분리한다. 기존 collect·captured_replay·judge_trial을 재사용한다. 공격량 제한, 자기 echo, INVALID 보존·고정 계획 번호를 유지한다.

## 정합 점검 결과

| 항목 | 발견·조치 |
|---|---|
| IDS 코드→IVI 이름 | ICD 1/2/3/4와 일치. 파서 4종 시험 추가 |
| 생성 공격→IDS | 고정 fixture 공격기와 live 공격기의 실제 생성 payload로 기대 코드 시험. Replay는 수용된 signed pair의 counter 재사용 |
| 다중 경보 | 고속/미정의 ID는 Fuzzy·Flooding 동시 발화 가능. 첫 유형·전체 유형·기대 유형을 별도 계측 |
| Fail-safe 사유0 | ICD 사유표는1..7, IDS는0 거부. IVI·Python 참조 파서는0 허용하던 drift를 거부로 맞춤 |
| 탐지와 게시 | 아무 경보·기대 유형·IVI 서비스 게시를 구분. 실제 UI 픽셀·참조 수신기의 방어 판정은 별도 |
| 원격 종료 | stdin EOF·종료 신호·최대 수명에 따른 소유 process group 정리. 로컬 POSIX 자식 종료 시험 |
| 과거 실험 | 원격 자료에서 최초1200 중1196 VALID/4 INVALID, 재시도 포함1201시도 기록을 확인. 이번 장비/코드의 실측값으로 재사용하지 않음 |

## 실행한 검증

초기 기본 Python에는 pytest/sklearn이 없었다. `tmp/chg022-venv`에 현재 requirements를 설치한 뒤 검증했다. 시스템 Python 패키지는 변경하지 않았다.

```sh
MPLCONFIGDIR=tmp/chg022-mpl tmp/chg022-venv/bin/python -m pytest security/tests -q
```

최종 전체 회귀(`-q -rs`, `tmp/chg022-final-pytest.log`): **142 passed, 3 skipped**. 생략은 macOS에 없는 Linux MSG_CONFIRM/AF_CAN 관련 시험이다. matplotlib의 PyparsingDeprecationWarning 1건은 기존 그림 시험 의존성 경고다. 원격 시험의 Linux 전용 ENOBUFS 숫자105 하드코딩은 `errno.ENOBUFS`로 바꿔 플랫폼별 errno를 정확히 사용했다.

이후 성공한 원격 시행/IVI 게시 대응/원시 hash 변조 거부 및 pilot cleanup 완료 게이트를 보강하고 아래 집중 시험을 실행했다. 마지막 수정 후 동일 집중 시험을 다시 실행했다.

```sh
tmp/chg022-venv/bin/python -m pytest security/tests/test_live_three_node.py security/tests/test_three_node.py -q
```

**10 passed**. 실제 CAN 없이 12조건×100회의 orchestration, 기대 유형/다중 유형, 원격 수명, 실패 시 cleanup, 변조 로그 거부를 검증했다. 모의1200 예약은 물리1200 실행이 아니다.

```sh
cmake -S ivi_platform -B tmp/chg022-ivi-build -DIVI_BUILD_QT_APP=OFF
cmake --build tmp/chg022-ivi-build -j2
ctest --test-dir tmp/chg022-ivi-build --output-on-failure
```

**IVI 9/9 통과**. Qt 앱/화면은 제외한 코어 시험.

초기 ECU configure는 GTest 미설치로 실패했다. 공식 GoogleTest v1.15.2를 tmp에 받아 빌드·설치하고 저장소 CMake의 find_package에 임시 prefix를 전달했다.

```sh
cmake -S adaptive_ecu -B tmp/chg022-ecu-build -DECU_BUILD_TESTS=ON -DCMAKE_PREFIX_PATH="$PWD/tmp/chg022-gtest-install"
cmake --build tmp/chg022-ecu-build -j2
ctest --test-dir tmp/chg022-ecu-build --output-on-failure
```

**ECU 18/18 통과**, 제품 실행파일 빌드 성공. 새 ADC capture target은 Linux 전용이므로 macOS에서 빌드/실측하지 않았다. Git diff whitespace·새 Python AST·JSON·문서 상대 링크/펜스도 확인한다.

## 미실행 범위

실제 RPi3/4·CAN0·vcan·SSH/sudo 권한·원격 Pi 프로세스 종료·버스 부하·ADC 입력·Qt 렌더링·12회 물리 pilot·1,200회 물리 실행은 이 macOS 환경에서 미실행이다. 원격 supervisor 로컬 시험을 실제 SSH 단절 시험으로 표현하지 않는다. 명령 인수와 장비별 키·정상 학습/보정 경로는 사용자가 실제 배치에 맞춰 설정해야 한다.

E3P 구매 페이지 자동 접근은 실패했다. 실물 헤더 방향·동일 번호 연속성·기계적 간섭은 전원 투입 전 확인한다. CAN 보드의16MHz·3.3V 로직·선택 DIP와 ADC0x48은 [배선 안내](../../../development/playbooks/three-node-hardware-experiment.md)의 제조사 자료를 근거로 한다.

제조사 CAN V1.2 회로도를 고해상도 렌더링하여 PGND와 GND-T의 1MΩ/1nF 결합을 확인했다. 초기 공통 GND 연결 설명을 정정했으며 최종 안내는 H/L 신호선 연결과 PGND 별도 보호 접지 경계로 구분한다.

## 요구별 완료 감사

| 사용자 요구 | 현재 증거 | 판정 |
|---|---|---|
| 1. 공격 RPi3 분리 방법 | 배선 안내의 노드 역할·5개 SPI/INT 신호·변환기2개·8MHz overlay | 안내 완료; 실물 조립은 사용자 단계 |
| 2. 새 회로 구성 방법 | 사용자 구매 SKU와 제조사 CAN 회로/Seeed 자료, CAN/ADC 핀·DIP·전원·PGND·종단저항·부팅 절차 | 안내 완료; E3P 실물 방향과 통신 실측은 확인 대상 명시 |
| 3. ECU 공격과 IVI 유형 일치 점검·수정 | 실제 공격 생성→runtime 코드 시험, IVI 4종 코드/이름 시험, undefined reason0 수정, 기대/첫/다중/게시 계측 | 소스·로컬 검증 완료; 물리 화면 미실행 |
| 4. 기존 1200회 일괄 실행 스크립트 | live_three_node + settings template + 재현 명령, 12조건×100 예약 시험·성공/실패/원장 hash 시험 | 스크립트·재현 절차 완료; 장비 pilot/공식 실행은 사용자 단계 |
| 최신 develop ECU 확인·가져오기 | fetch SHA76b56f4, 별도 스냅샷 대조·관련 코드 선별 반영, ECU18·IVI9·Python142 회귀 | 완료 |
| 사용자 작업·계약 보존 | 기존 dirty 변경 유지, 전체 merge/reset/stage/commit/push 없음; ICD 수정 없음 | 보존 |

최종 문서4개의 상대 링크·코드 펜스 검사와 `git diff --check` 통과. 실제 장비·CAN·화면·1200회의 새 실측을 수행했다고 표시하지 않는다.

## 회로 안내 가독성 보완 (2026-10-21)

사용자의 그림 중심 안내 요청에 따라 기존 배선 문서에 전체 구성·ECU/ADC 연결·공격 노드 신호선·공격 노드 전원선 SVG 4장을 추가했다. 물리/BCM/P 표기, LV 전원과 LV1 신호 구분, 조립 순서, 전원 투입 전 체크리스트를 보완했다. 상세 핀 대응은 접을 수 있도록 구분했다. 그림은 실물 장착 방향을 보증하지 않는 연결 개념도이며 E3P 실물 확인 경계를 유지했다.

문서 상대 링크·4개 SVG XML/title·코드 펜스·접기 태그·노드별 기존 overlay 보존을 Python으로 검사하여 통과했다. Quick Look으로 4장을 렌더링하고 전체 도형·한글·연결선·라벨을 육안 확인했다. Quick Look의 가로 그림 썸네일 잘림은 임시 정사각 캔버스로 확인했으며, 원본은 본문용 가로 비율을 유지한다. `git diff --check` 통과. 이번 보완은 문서와 그림만 변경했으며 물리 회로 검증은 수행하지 않았다.


## 3노드 HTML 배선 지도 (2026-10-22)

사용자가 지정한 `하드웨어 정보/` 폴더의 기존 HTML 형식을 참조해 `ECU_IVI_RPi3_3노드_배선가이드.html`을 추가했다. 기존 파일은 수정하지 않았다. ECU·IVI의 헤더 연결과 공격 Pi3의 직접 SPI/INT 배선을 구분하고, 5개 인라인 SVG·노드별 40핀 표·DSI 화면 전원·종단저항·9개 체크 항목·인쇄 기능을 포함했다. 화면의 세대와 3핀 커넥터 형식은 미확인으로 명시했다.

검증: HTML 상대 링크/앵커/고유 ID/표 행/5개 SVG/9개 체크 항목 검사 통과, `node --check /tmp/wiring-script.js` 통과. Quick Look 첫 화면 렌더링과 한글·목차·전체 그림 표시를 육안 확인했다. 추가 구간 렌더링은 자동 승인 검토의 사용량 제한으로 실행되지 않았다. 브라우저 UI 접근은 승인되지 않아 체크박스·인쇄의 실제 클릭 동작과 전체 페이지/모바일/인쇄 출력은 미검증이다. 물리 회로 동작 검증을 대신하지 않는다.


### HTML 조립 순서 중심 재작성

사용자 가독성 피드백에 따라 사진/전체도 중심 본문을 9단계 조립 순서로 바꿨다. 출발 단자와 도착 단자를 23개 연결 행으로 분리했고, Pi3 신호 5개는 각각 점퍼선 두 가닥을 따로 표시했다. 전체 배선도·40핀 표·설정은 선택형 접기 영역으로 이동했다. 밝은 배경과 큰 단자명, 단계별 체크를 적용했다. 9단계/23연결/ID 중복/앵커/상대 링크 검사 통과. 변경된 화면의 브라우저 렌더링은 별도 확인 대상이며 기존 버전 미리보기 결과를 새 화면 검증으로 취급하지 않는다.

## 노드별 소프트웨어 설정 HTML (2026-10-22)

사용자 H–L 약60Ω 확인 이후의 설정 절차를 `하드웨어 정보/ECU_IVI_RPi3_소프트웨어_설정가이드.html`로 작성했다. 22단계에 실행 노드·명령·확인 결과·중지 조건을 표시했다. ECU/IVI 16MHz CE1과 Pi3 8MHz CE0, ADC 사용자 공간 소유, 기존 IVI 배포 fragment의 8MHz 차이, 실제 소스 미전달 경계, Qt6.8/키/원격 pilot 준비를 분리했다. 기존 하드웨어 HTML과 상호 연결했다.

검증: 40개 명령/설정 블록 중 셸 명령의 bash -n 검사, JavaScript node --check, ID/앵커/상대 링크 검사 및 git diff --check 통과. Quick Look으로 첫 화면 렌더링과 제목·단계·목차 가독성을 확인했다. 명령은 실제 main.cpp·CMake·배포 스크립트·live_three_node CLI와 대조했다. 실제 Pi 설치/재부팅/CAN/Qt/키/SSH/실험은 실행하지 않았다. 전체 페이지·복사 버튼·인쇄 상호작용은 브라우저에서 미검증이다.

## PR 분리 검증 — 2026-10-22

최신 origin/develop `76b56f4`에서 `feat/three-node-campaign` 작업본을 분리했다. 이번 PR은 기존 develop의 ECU/IDS 동기화를 그대로 사용하고, 3노드 실행·remote_process·유형 계측·사유0 검증과 관련 문서만 추가한다. 원래 작업본의 복구/품질/성능 변경, 이전 HTML, 장비 주소가 포함된 사용자 스크린샷은 포함하지 않는다.

- Python 직접 영향 회귀: `python -m pytest security/tests/test_three_node.py security/tests/test_live_three_node.py security/tests/test_live_experiments.py security/tests/test_ablation_lifecycle.py security/tests/test_ablation_resume.py security/tests/test_pilot_readiness.py -q` → **47 passed, 2 skipped** (Linux 전용).
- 전체 Python: `python -m pytest security/tests -q` → **146 passed, 3 skipped, 1 failed**. 실패는 변경하지 않은 `test_publication.py::test_recovery_archive_verifies_contents_and_never_overwrites`; 로컬 Python3.9.6에서 `hashlib.file_digest`가 없다. `origin/develop` 원본 evidence_bundle.create를 독립 실행해 동일 오류를 재현했다. 이번 수정의 회귀 실패로 숨기거나 전체 통과로 표시하지 않는다. 배포 대상 Python 버전에서 전체 재검증이 필요하다.
- IVI: 새 외부 빌드 폴더에 `cmake -S ivi_platform -B <build> -DIVI_BUILD_TESTS=ON -DIVI_BUILD_QT_APP=OFF`, build, CTest → **9/9 통과**.
- 두 Python CLI `--help` 통과. 변경 문서 상대 링크와 `git diff --check` 통과. 키/장비 주소/스크린샷/빌드 산출물 포함 여부 점검.
- 사용자 제공 화면: ECU·IVI·Pi3의 단발0x123 각 송신을 다른 두 노드가 수신, 표시 오류0 확인. 장시간/고부하/IDS/Qt 실제 게시/원격 supervisor/12회 pilot/1,200회 검증으로 확대 해석하지 않는다.

## 360회 테스트 실행기 후속 검증

`live_three_node_test360` 진입점을 추가하고 공유 실행기에서 30회 고정 test360 단계로 실행한다. 기존 CLI의 pilot1회/official100회와 공식 pilot 게이트는 유지한다. 결과 stage 표시, 12조건×30회 예약, 기존 출력 거부, 시험 버스 확인, ERROR/INTERRUPTED 후 조건 중단, INVALID의 비성공 종료, 테스트 결과의 공식 pilot 대체 거부를 검증했다.

실행: `python -m pytest security/tests/test_live_three_node_test360.py security/tests/test_live_three_node.py security/tests/test_three_node.py security/tests/test_live_experiments.py -q` → **36 passed, 1 skipped** (Linux 전용). macOS 로컬 모의 시험이며 실제360회는 수행하지 않았다.

## 테스트360 오류 처리·재개 후속 검증 (2026-10-22)

- 테스트 전용 독립 360번호 실행, 실패 attempt 보존, 최대2회 복구, 완료 번호 건너뛰기, 소스·설정 변경/미봉인/종료 불명 시 재개 거부를 추가했다. 기존1,200회 연속 실행 계약은 보존했다.
- ECU·IVI 전체 CAN 수신 관찰기, phase ACK, 원격 소유 프로세스 종료 ACK, CAN 상태 확인/실패 인터페이스 제한 복구를 추가했다. IVI 유형 판정은 종료 후 로그 drain까지 기다린다.
- 검증: macOS/Python3.9.6에서 `python -m pytest security/tests/test_live_three_node.py security/tests/test_live_three_node_test360.py security/tests/test_test360_observers.py security/tests/test_three_node.py security/tests/test_live_experiments.py security/tests/test_ablation_lifecycle.py security/tests/test_ablation_resume.py -q` → 70 passed, 2 skipped (Linux 조건).
- 시험 범위: 360개 고유 번호, INVALID 계속, 재시도 예산/실패 보존, 재개 중복 방지, 종료 불명 차단, 잘못된 설정·저장 오류 차단, 원격 수신 없는 echo 거부, 늦게 도착한 IVI 로그 반영, 관찰기 phase 경계/EOF, 실패 CAN만 reset, 정식1,200회 유지. CLI help와 diff 공백 검사 통과.
- 실장비 SSH·sudo·SocketCAN·관찰기 부하 및 360회는 미실행. payload 일치는 송신자 인증이 아니며 baseline과 동일한 replay의 고유 도착을 보장하지 않는다. 독립 trial 시작/IDS 재학습 비용 때문에 정식 연속시험과 합산하지 않는다.
