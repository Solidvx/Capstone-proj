# CHG-008 — ADS1115 실측 CAN 표시 진단

- 요청: 모의 BMS 화면 확인 후 가변저항 실측값부터 CAN/Qt로 확인하고 오류·복구 및 보안 시험으로 진행.
- 대상: `chore/ecu-m1-baseline`, 시작 HEAD f289395. 기존 dirty 문서·삭제·미추적 파일 보존.
- 범위 결정: 팀원 IVI는 공유한 소스 기준 미인증 BMS를 즉시 표시하며 센서 품질 계약을 지원하지 않는다. 기존 ICD byte 7을 바꾸지 않는 독립 진단을 우선 추가. 제품 main 연동·양측 품질 전환·SecOC는 미완료.
- 구현: `ads1115_sample.h`, Linux `tools/ads1115_can_smoke.cpp`, CMake target, 취득·오류·인코딩 시험.
- 실행·제약: [진단 절차](../../../development/playbooks/ads1115-can-smoke.md).
- 검증: [증거](evidence.md).
- 상태: 독립 진단 구현·Linux 빌드·CTest 14/14 통과. RPi/물리 CAN/Qt 실측과 제품 main 통합은 미완료, 사용자 실행 대기.

제품 계약·기존 main을 수정하지 않았다. 진단은 동기 I²C이며 정상 100ms 요청, 20ms 이상 결과 폐기, 최초/복구 새 유효 변환 3회 후 송신한다. 오류 중 무송신으로 이전 측정을 새 정상값으로 보내지 않는다. UI가 옛 값을 유지하는 한계가 있으므로 제품 센서 오류 처리 완료라고 판단하지 않는다.
