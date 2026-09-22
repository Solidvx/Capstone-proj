# CHG-002 검증 기록

## 계약 판단

- CAN ID `0x100/101/102/103/200`, DLC, payload, HMAC 입력, rolling counter 규칙은 변경하지 않았다.
- ICD §3의 Android HIDL API만 ADR-010에 맞는 프로세스 내부 C++ Service API로 대체했다.
- ICD §8 sensorState는 양 노드 동시 전환 전 목표 상태로 유지했다.

## 실행 결과

- `git diff --check`: 통과
- 변경·추가 Markdown 37개 상대 링크 검사: 깨진 링크 0건. 구조 안내의 하드웨어 JPG 7개 링크를 실제 `shared/` 경로로 정정
- 변경·추가 Markdown 코드 펜스 검사: 불균형 0건
- SRS `FR-IVI-001~008`: 8개 ID 존재 확인
- TEST_PLAN `TC-IVI-001~008`: 8개 ID 존재 확인
- Android 현행 표현 검사: 공식 요구·시험과 공동 매핑의 HIDL/Binder/StateFlow 경로 제거. ADR·changelog·superseded 안내의 역사 표현은 보존

제품 코드가 아직 없고 이번 변경은 P0 문서 기준 고정이므로 CMake/CTest와 장비 시험은 실행 대상이 아니다.
