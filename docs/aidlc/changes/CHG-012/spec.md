# CHG-012 — SecOC RollingCounter 인증 CAN ID별 독립

요청(2026-10-03): CHG-011(브랜치 `feat/ecu-ads1115-runtime`, 별도 PR) 실장비 시험에서 발견한 counter 범위 차이를 사용자 결정 B로 해소하고 ICD 문구를 함께 명확히 한다.

배경: ECU `SecOcModule`과 Python 참조 `security/secoc_module.py`는 `0x102`와 `0x103`이 counter 하나를 공유했다. IVI `VehicleDataService`와 ECU IDS `runtime_detector.py`는 원본 CAN ID별 마지막 counter로 1~100 창을 판정한다. 그래서 두 Fail-safe 이벤트 사이에 `0x102`가 100회 넘게(약 10초 이상) 나가면 수신 측이 다음 `0x103`을 창 밖으로 거부하고, IDS는 COUNTER_WINDOW를 낼 수 있었다. ICD는 "인증 메시지마다 +1"만 정하고 범위를 명시하지 않았다.

결정 B: counter를 인증 CAN ID별로 독립시킨다. AUTOSAR SecOC의 Freshness Value ID별 관리와 같은 구성이며, 수신 측 두 곳(IVI·IDS)과 IVI 시험 벡터 스크립트가 이미 이 방식이라 송신 측만 고친다.

범위: ICD §1.4·§2.2~2.4 문구와 버전 v1.6, ECU `SecOcModule`(송신 counter는 인증 ID별, 검증 이력은 원본 ID별), Python 참조 모듈, 두 언어의 시험, SRS·SDD-IVI·TEST_PLAN의 ICD 참조 버전, SDD-ECU 송신 흐름도와 참조 목록, TEST_PLAN TC-SEC-003 추가 확인.

변경 없음: CAN ID·방향·DLC·바이트 배치·HMAC 입력·창 크기(1~100)·IVI 코드·IDS 코드.

계약 변경 절차: ICD 머리말에 따라 양측 합의 후 병합한다. IVI 담당이 이 변경의 PR을 리뷰·승인하는 것으로 합의를 기록한다.
