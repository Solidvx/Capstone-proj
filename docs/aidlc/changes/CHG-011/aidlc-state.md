# CHG-011 — ECU ADS1115 제품 연결 (1단계)

- 요청과 결정: [spec](spec.md). 검증: [evidence](evidence.md).
- 대상 브랜치: `feat/ecu-ads1115-runtime` (기준 `develop` `4f2b836`), PR base `develop`.
- 상태(2026-10-03): 구현과 단위 시험 완료(CTest 16/16). ECU RPi 실장비에서 노브 30.00~41.99V 반영, 100ms 주기, MAC 101/101 확인. 0V 끝 잡음으로 송신 보류가 반복되어 ADS-5=B 끝점 허용을 추가했다(±16 적용 후 주기 100.0~100.1ms, Fail-safe WARNING→CRITICAL 확인). 장시간 대기 중 단발 오류가 나 1000회 재측정 후 ±32로 넓히고 오류 원인 로그(ADS-6)를 추가했다. `aeb39bb`에서 0V 끝 10분 정지 오류 0회, `0x101`/`0x103` 전이 프레임 확인. **ECU 단독 범위 완료.**
- 발견(미수정): ECU는 `0x102`·`0x103`이 SecOC counter를 공유하고 IVI는 인증 ID별로 판정해, Fail-safe 이벤트 간격이 약 10초를 넘으면 IVI가 `0x103`을 거부할 수 있다. ICD 명시가 필요한 계약 사안으로 IVI 담당과 합의 후 처리([evidence §5](evidence.md)). → 사용자 결정 B(인증 CAN ID별 독립)로 [CHG-012](../CHG-012/aidlc-state.md)에서 ICD v1.6과 ECU·Python을 수정했다.
- 변경: 공용 `LinuxI2cTransport`, 별도 스레드 `Ads1115AcquisitionWorker`/`Ads1115Acquirer`, 100ms 루프 판정 `HardwareSampleFeed`, `main` 연결과 `--i2c-device`, `SensorSimulator`의 POTENTIOMETER·setter 제거와 모드 이름 검증, 진단 도구의 전송부 공용화. ICD 변경 없음(byte 7 = 0).
- 설계값(모두 추가 측정 후 재검토): 결과 신선도 200ms(요청 간격 2회), 끝점 허용 ±32코드(약 4mV, ECU RPi 1대 실측: 0V 끝 100회+1000회, 3.3V 끝 100회).
- 후속 후보(추가): A0 입력 필터 커패시터 등 순간 잡음의 하드웨어 저감.
- 다음 행동: `develop` PR. SecOC counter 범위 합의. 이후 물리 `can0`으로 IVI와 IT-001·IT-003, counter 해결 후 IT-002.
- 후속 후보: 온도 입력 가변저항(A1), ICD §8 센서 상태 동시 전환, ECU 문서 Debian 13 표기.
