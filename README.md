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

ECU의 `adaptive_ecu`와 `physical_battery_worker`를 같은 `bin/`에 유지한다. 배포 예시 설정을 로컬 복사해 본인 DS18B20 번호·실물 션트값을 확인한다. 초기 SOC·용량 시험 근거가 없으면 예시의 `unknown`을 유지한다. IVI는 같은 형상의 일반 `ivi_dashboard`를 사용한다.

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

실측 채널이 만료되면 해당 값은 즉시 `--`가 된다. 사용자 알림과 이벤트는 이상이 2초 이상 지속될 때 한 번 표시하며, 짧은 정상/이상 반복은 같은 사건으로 유지한다. 세 채널이 5초 동안 정상이고 새 취득 순번도 확인돼야 회복을 한 번 기록한다. 초기 센서 준비는 고장으로 알리지 않는다. 닫은 알림은 같은 사건에서 다시 열지 않으며, 읽지 않은 알림은 회복 문구로 갱신한다. 이 정책은 센서 유효기간이나 SecOC 판정을 늘리지 않는다.

실행 예시의 취득 주기는 `period_ms=1000`, 전류 적분/수신 나이 상한은 `max_interval_ms=3000`이다. 기존 2초 취득 설정은 온도 변환 대기와 1초 보고 간격이 겹쳐 정상 표본도 다음 보고 전에 3초 상한을 넘길 수 있다. 기존 로컬 설정은 패키지를 갱신해도 자동 변경되지 않으므로 백업 후 취득 주기를 수정하고 ECU 프로그램을 재시작한다. 느린 읽기·전송 지연에 대한 장비 인수는 별도로 필요하다.

중앙 팝업은 배터리 탭에서만 표시한다. 보안·이벤트·설정 탭에서는 조작을 막지 않는 상단 알림을 6초간 표시한다. 알림을 닫거나 상단 알림이 사라져도 상태와 이벤트 기록은 유지한다.
