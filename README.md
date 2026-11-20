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
