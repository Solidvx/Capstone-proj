# CHG-011 — ECU ADS1115 제품 연결 (1단계)

- 요청과 결정: [spec](spec.md). 검증: [evidence](evidence.md).
- 대상 브랜치: `feat/ecu-ads1115-runtime` (기준 `develop` `4f2b836`), PR base `develop`.
- 상태(2026-10-03): 구현과 단위 시험 완료(CTest 16/16). ECU RPi 실장비에서 노브 30.00~41.99V 반영, 100ms 주기, MAC 101/101 확인. 0V 끝 잡음으로 송신 보류가 반복되어 D5=B 끝점 ±16코드 허용을 추가했고, 적용 후 RPi 재시험과 Fail-safe 전이 확인 대기.
- 변경: 공용 `LinuxI2cTransport`, 별도 스레드 `Ads1115AcquisitionWorker`/`Ads1115Acquirer`, 100ms 루프 판정 `HardwareSampleFeed`, `main` 연결과 `--i2c-device`, `SensorSimulator`의 POTENTIOMETER·setter 제거와 모드 이름 검증, 진단 도구의 전송부 공용화. ICD 변경 없음(byte 7 = 0).
- 설계값(모두 추가 측정 후 재검토): 결과 신선도 200ms(요청 간격 2회), 끝점 허용 ±16코드(약 2mV, ECU RPi 1대·각 끝 100회 실측 근거).
- 다음 행동: ECU RPi에서 `--sensor-mode ads1115 --secoc on` 실행, 노브·주기·MAC 확인 결과를 evidence에 추가. 이후 IVI와 키 공유 후 IT-001·IT-003.
- 후속 후보: 온도 입력 가변저항(A1), ICD §8 센서 상태 동시 전환, ECU 문서 Debian 13 표기.
