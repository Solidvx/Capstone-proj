# IVI–ECU Capstone

RPi4 ECU와 IVI가 CAN으로 배터리 데이터·SecOC 인증·IDS 탐지·대시보드를 연결하는 프로젝트다. PC는 실험 제어와 로그 수집, Pi3는 CAN 공격 모듈을 담당한다.

## 소스와 규격

- `adaptive_ecu/`: ECU 실행 코드·센서 취득·배터리 계산·시험.
- `ivi_platform/`: SocketCAN·Qt Quick 대시보드·시험.
- `common/`: 양 노드 공통 프로토콜과 `testdata/`의 공개 시험 벡터.
- `security/`: Python SecOC·IDS·공격 및 실험 자동화 코드.
- `tools/`, `.github/`: 빌드·품질·배포 도구와 CI.
- [공식 문서](docs/README.md): ICD·요구사항·설계·시험 기준.

개인 질문·AI 지침·작업일지·인계 묶음·실험 결과 원본은 소스 저장소에 포함하지 않는다. 실제 키·장비 주소·센서 고유번호·로컬 측정 로그도 커밋하지 않는다. README와 공식 규격, 코드·시험·빌드 설정은 유지한다.

## Pi 설치

장비에서 전체 저장소를 받을 필요 없이 GitHub Actions의 `Local-quality baseline` 성공 실행에서 노드별 실행 패키지를 받을 수 있다. 이 artifact를 제공하는 형상에서 `runtime-ecu-linux-arm64`는 ECU, `runtime-ivi-linux-arm64`는 IVI에 전달한다. 각 ZIP 안의 `.tar.gz`와 `.sha256`를 함께 옮긴다. 패키지는 Debian 13 ARM64 대상이며 시스템 Qt·OpenSSL 등 공유 라이브러리는 별도로 필요하다. 기존 설치·측정 로그·키는 덮어쓰지 않는다.

설치용 실행 패키지와 개발 소스 묶음은 용도가 다르다. 실측 표시용 패키지에는 Python IDS·공격 실험·감독자 전체 설치가 포함되지 않는다.

## 개발 빌드와 시험

개발 환경에 CMake·C++17 컴파일러·OpenSSL·GoogleTest·Qt6와 Python 의존성을 준비한다.

```sh
cmake -S adaptive_ecu -B adaptive_ecu/build -DECU_BUILD_TESTS=ON
cmake --build adaptive_ecu/build -j2
ctest --test-dir adaptive_ecu/build --output-on-failure

cmake -S ivi_platform -B ivi_platform/build -DIVI_BUILD_QT_APP=ON
cmake --build ivi_platform/build -j2
ctest --test-dir ivi_platform/build --output-on-failure

python3 -m pytest security/tests ivi_platform/test tools/quality/tests tools/deployment/tests -q
```

Linux CAN 통합 시험은 설정된 가상 CAN 환경이 필요하다. 소스 존재·소프트웨어 시험·실제 센서 정확도·실물 디스플레이 인수는 각각 구분한다. 실제 SecOC 키는 ECU의 `--key`, IVI의 `--secoc-key`로 로컬 파일을 지정하고 Pi3에는 전달하지 않는다. session-v2는 양측에 명시적인 `--session-policy`를 지정한다.

## 선택형 단셀 실측 표시

ECU의 `adaptive_ecu`와 `physical_battery_worker`를 같은 `bin/`에 유지한다. 배포 예시 설정을 로컬 복사해 본인 DS18B20 번호·실물 션트값을 확인한다. 초기 SOC를 직접 지정하지 않을 때는 `unknown` 또는 아래의 명시적 참고 EKF 모드를 선택한다. 독립 용량 시험 근거가 없으면 SOH 설정은 `unknown`을 유지한다. IVI는 같은 형상의 일반 `ivi_dashboard`를 사용한다.

```sh
# ECU 패키지를 푼 폴더에서 실행
cp -n config/physical-battery.conf.example config/physical-battery.conf
./bin/adaptive_ecu --interface can0 --sensor-mode physical \
  --physical-config config/physical-battery.conf --protocol session-v2 \
  --session-policy config/session-v2-development.conf --key /etc/secoc/key.bin

# IVI 패키지를 푼 폴더에서 실행. 데스크톱 세션 환경이 필요하다.
QT_QPA_PLATFORM=wayland ./bin/ivi_dashboard --interface can0 \
  --protocol session-v2 --session-policy config/session-v2-development.conf \
  --secoc-key /etc/ivi/secoc.key
```

전압·전류·온도는 센서값을 표시하고 근거 없는 SOC/SOH는 `--`로 표시한다. 이 모드는 측정·표시 연결이며 실셀 부하 차단·자동 checkpoint 복구·정확도 인수는 포함하지 않는다. 프로그램을 종료해도 저항 부하는 분리되지 않으므로 측정 종료 후 셀/부하를 분리한다. 기존 가변저항 모드는 유지한다.

실측 채널이 만료되면 해당 값을 즉시 무효화하고 입력 칸에 노란색과 `센서 입력 대기`를 표시한다. 사용자 알림과 이벤트는 이상이 2초 이상 지속될 때 한 번 표시하며, 짧은 정상/이상 반복은 같은 사건으로 유지한다. 세 채널이 5초 동안 정상이고 새 취득 순번도 확인돼야 회복을 한 번 기록한다. 초기 센서 준비는 고장으로 알리지 않는다. 닫은 알림은 같은 사건에서 다시 열지 않으며, 읽지 않은 알림은 회복 문구로 갱신한다. 이 정책은 센서 유효기간이나 SecOC 판정을 늘리지 않는다.

실행 예시의 취득 주기는 `period_ms=1000`, 전류 적분/수신 나이 상한은 `max_interval_ms=3000`이다. 기존 2초 취득 설정은 온도 변환 대기와 1초 보고 간격이 겹쳐 정상 표본도 다음 보고 전에 3초 상한을 넘길 수 있다. 기존 로컬 설정은 패키지를 갱신해도 자동 변경되지 않으므로 백업 후 취득 주기를 수정하고 ECU 프로그램을 재시작한다. 느린 읽기·전송 지연에 대한 장비 인수는 별도로 필요하다.

중앙 팝업은 배터리 탭에서만 표시한다. 보안·이벤트·설정 탭에서는 조작을 막지 않는 상단 알림을 6초간 표시한다. 알림을 닫거나 상단 알림이 사라져도 상태와 이벤트 기록은 유지한다.


## 단셀 SOC 자동 초기화·참고 EKF

`config/physical-battery.conf`의 `initial_soc_percent=auto-ekf-adi-liion-v1`로 선택한다. 기존 로컬 설정은 자동 변경하지 않으며 숫자0~100(명시 초기값+전류 누적), `unknown`(SOC미산정)도 유지한다. 새 SOC근거2를 사용하는 ECU·IVI는 같은 형상으로 함께 갱신해야 한다.

자동 모드는 공개된 [Analog Devices typical Li-ion 예제곡선 Table 1](https://www.analog.com/en/resources/design-notes/characterizing-a-lithiumion-li-cell-for-use-with-an-opencircuitvoltage-ocv-based-fuel-gauge.html)을 사용하는 단셀1상태 EKF다. 우리 셀의 특성 측정값이나 가장 유사하다고 검증한 곡선이 아니며 정확도는 미검증이다. 센서 전압·전류·온도는 계속 실측값을 사용한다. 기존 가상10직렬/50Ah EKF와 분리한다.

처음에는 센서 측정 배선을 유지한 채 저항 부하를 분리하고 전압이 안정되도록 기다린다. |전류|≤20mA·전압 변동폭≤10mV가60초 이상 이어지면 초기 SOC를 추정한다. 이 후보 조건이 충분한 실제 OCV 휴지시간이라는 보장은 없으며 변동/공백이 있으면 안정 확인을 다시 시작한다. 전압3.0~4.25V는 후보 모델의 입력 범위이며 보호 임계가 아니다. 모델 입력 범위를 벗어나면 SOC를 미산정으로 내리고 안정 확인부터 다시 시작한다. 곡선 끝점의0/100% 표시도 실제 방전/완충 확인이 아니다.

IVI는 초기 잔량 확인 중 안내를 표시하고, 초기화 후에는 잔량 게이지를 표시한다. 그 뒤 저항을 연결해 방전하면서 실측 전류를 누적한 예측을 확인할 수 있다. 전압 보정은 다음 안정 창에서만 적용하고 부하 중 전압을 그대로 OCV로 사용하지 않는다. ECU 로그의 `soc_basis=2`, `soc_update`(waiting-rest/initialized/predicted/corrected/held-gap), `soc_covariance`로 실행 경로를 구분한다. 이 공분산은 후보 모델의 내부 상태이며 실셀 SOC 오차 보증값이 아니다.

프로그램을 재시작하면 다시 자동 초기화한다. 실측 EKF 영속 복구·셀 교체 자동 인식·온도/내부저항 보정·부하 차단은 포함하지 않는다. SOH는 별도의 용량 시험 근거가 있어야 표시한다. 프로그램 정지와 실제 저항 부하 분리는 별개다.

### 실측 용량으로 SOH 측정·적용

`bin/measure_physical_capacity.py`는 실행 패키지에 포함되는 표준 Python3 도구다. 센서나 CAN을 다시 열지 않고 **정지한 ECU의 계측 로그**에서 지정한 시작/종료 취득순번 사이의 실제 전류 적분값을 읽는다. 방전Ah에서 선언한 허용 범위의 충전 잡음Ah를 차감한 사용 가능 용량을 기준 용량과 비교한다. SOC 변화나 참고 OCV 곡선을 SOH의 용량 근거로 사용하지 않는다.

실제 용량 시험은 같은 셀을 확인된 완충 상태에서 시작해 해당 셀/부하/온도의 확인된 방전 종료 조건까지 측정해야 한다. 임의의 전압을 방전 종료값으로 정하거나 0V까지 방전하지 않는다. 현재 회로·도구는 저항을 자동 분리하지 않는다. 셀의 종료 조건과 수동 부하 분리 절차를 확인하기 전에는 실제 시험을 시작하지 않는다. 구매 셀의 공개 페이지에서는 정확한 종료 조건을 확인하지 못했으며, 프로그램의 SOC 입력 범위3.0~4.25V는 그 조건을 대신하지 않는다.

새 ECU의 `PHYSICAL_SAMPLE`은 실행 식별자·Linux boot 시계·설정SHA256·전기 취득시각과 실제 충전/방전 적분값을 기록한다. 시험할 셀에 사용할 원래 설정, 시작/종료 순번, 셀/시험 라벨, 독립적으로 확인한 종료 조건의 출처·종료 전압, 전압 비교/충전 잡음 허용량을 도구에 명시한다. `--full-discharge-confirmed`는 동일 셀의 실제 완충~방전 종료 구간을 운영자가 확인했다는 뜻이며 소프트웨어가 이를 자동 검증했다는 의미가 아니다.

```bash
python3 bin/measure_physical_capacity.py --help
```

도구는 동일 실행·시계·설정, 연속 취득/시각, 전압·전류·온도 정상, 관찰 공백 없음, 선언한 범위를 넘는 충전 없음, 마지막 실측 전압과 확인한 종료점의 일치를 검사한다. 구형 로그, 누락/역순/오류/혼합 기록, 부분 시험을 전체 시험으로 확인하지 않은 입력은 결과로 적용하지 않는다. 오류 후 임계만 늘려 결과를 통과시키지 않는다.

성공하면 새로운 출력 폴더에 `report.json`과 `physical-battery.with-soh.conf`를 만든다. 원래 설정은 덮어쓰지 않는다. 새 설정에는 측정한 용량과 시험 식별정보만 반영하며 센서·SOC 설정을 유지한다. 같은 셀로 정상 ECU를 실행할 때 `--physical-config`에 이 새 파일을 지정하면 기존 인증 CAN 종류9의 SOH필드/근거1로 송신되고 IVI에 표시된다. 셀을 바꾸면 이전 셀의 용량 결과를 재사용하지 않는다. 측정 용량/기준 용량 원비율은 보고서에 보존하고 화면만0~100%로 제한한다. 실제 센서 보정·셀 특성·정확도는 별도 검증이며 결과의 `physical_accuracy_verified`는false다.

## 센서 알림·회복을 직접 확인하기

현재 실측 전달 경로에서는 센서 입력 오류/회복과 연결 대기/재연결을 확인한다. 실제 셀의 과열/저잔량 보호는 아직 미구성이므로 실셀을 가열하거나 방전 끝까지 보내 UI 경고를 유도하지 않는다. 보안 프로그램/공격 노드의 실제 탐지·거부 인수도 별도로 구분한다.

배선을 바꾸는 대신, 실제 센서로 이어지는 **시험용 읽기 경로**를 잠시 숨겨 동일 ECU 프로세스의 오류/회복을 확인할 수 있다. 아래는 ECU 런타임 폴더에서 기존 ECU를 종료한 뒤 사용한다. 기존 설정·시스템 장치·키는 수정하지 않는다. 시험 폴더가 이미 있으면 덮어쓰지 않으며 다른 이름을 사용한다.

```sh
python3 - <<'PY'
from pathlib import Path
root = Path.cwd()
source = root / 'config/physical-battery.conf'
lines = source.read_text().splitlines()
values = dict(line.split('=', 1) for line in lines if line and not line.startswith('#'))
test = root / 'tmp/ui-sensor-check'
test.mkdir(parents=True, exist_ok=False)
(test / 'temperature').symlink_to(values['w1_root'], target_is_directory=True)
(test / 'electrical').symlink_to(values['i2c_device'])
replacements = {'w1_root': str(test / 'temperature'), 'i2c_device': str(test / 'electrical')}
config = test / 'physical.conf'
config.write_text('\n'.join(key + '=' + replacements[key] if key in replacements else line
    for line in lines for key in [line.partition('=')[0]]) + '\n')
print('시험 설정:', config)
PY

./bin/adaptive_ecu --interface can0 --sensor-mode physical \
  --physical-config "$PWD/tmp/ui-sensor-check/physical.conf" \
  --protocol session-v2 --session-policy config/session-v2-development.conf \
  --key /etc/secoc/key.bin
```

IVI는 일반 실측 수신으로 켜둔다. 정상 전압·전류·온도를 확인한 뒤 **다른 ECU 터미널의 같은 런타임 폴더**에서 아래 두 명령을 하나씩 실행한다. 첫 명령 후 알림을 확인하고 나서 두 번째를 실행한다.

```sh
# 온도 읽기 실패: 2초 지속 확인 뒤 센서 알림, 온도는 --
mv tmp/ui-sensor-check/temperature tmp/ui-sensor-check/temperature.off

# 실제 온도 읽기 복구: 새 3회 확인 + 5초 연속 정상 뒤 회복 기록
mv tmp/ui-sensor-check/temperature.off tmp/ui-sensor-check/temperature
```

배터리 탭에서 알림을 닫지 않았다면 회복 문구로 바뀐 뒤 닫을 수 있어야 한다. 오류 중 닫았다면 같은 오류에서 다시 열리지 않고 회복은 이벤트에 기록돼야 한다. 회복 후 이벤트 탭에서 같은 시험을 반복하면 중앙 팝업 대신 6초 상단 알림이 나타나고 스크롤·탭 조작이 가능해야 한다. 전압/전류 읽기는 같은 방식으로 `electrical`↔`electrical.off`를 변경해 확인한다. 이 시험은 실제 측정값을 읽다가 경로만 끊으며 가상 측정값을 만들지 않는다. 실제 배선 단선 인수와는 구분한다. 종료할 때 두 경로를 복구하고 ECU를 중지한 뒤 원래 설정으로 다시 실행한다.

ECU 프로그램을 중지했다 다시 실행하면 연결 대기→새 인증 연결→새 측정값 확인을 별도로 볼 수 있다. 단순 재연결을 센서 회복이나 실제 배터리 정상 복귀로 해석하지 않는다.

화면 모양만 확인하는 기존 `./bin/ivi_dashboard --demo SCENARIO`에는 `normal`, `warning`(작업 복구 실패 경고), `critical`(저잔량 위험), `shutdown`(과열 보호), `ids`(Flooding)가 있다. IVI에서 실행 중인 일반 대시보드를 종료한 뒤 같은 Wayland 환경에서 사용하며, 상단에 **화면 시연 · 가상 데이터**로 표시한다. 이 고정 화면은 센서/CAN/보호 알고리즘·회복 전이를 검증하지 않는다. 같은 앱 실행 중 실제 입력 오류→회복은 위 시험, 가상 배터리 보호 전이는 해당 단위/제품 시험으로 확인한다.
