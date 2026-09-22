# CHG-003 감사 기록

## 계약 대조

- CAN ID `0x100`, `0x101`, `0x102`, `0x103`, `0x200`을 변경하지 않았다.
- 모든 Classic CAN payload는 8바이트로 처리한다.
- SecOC 입력은 `CAN_ID(2B BE) || rolling_counter(4B BE) || payload(8B)`이며 HMAC-SHA256 앞 4바이트를 비교한다.
- 테스트 더미 키는 ECU 시험과 같은 `00 01 ... 1f`이며 제품 키 파일은 추가하지 않았다.
- ECU BMS 예제 `96 BE 10 68 FF EC 41 00`과 counter 0의 MAC `D0 DD FC 05`를 회귀 시험에 사용했다.

## 보관본 처리

- 계획에 고정된 6개 파일의 SHA-256 일치를 확인했다.
- 과거 저장소 전체, `.git`, Android 자리표시자, 빌드 산출물은 반입하지 않았다.
- 과거 구현의 인증 전 게시, signed counter 비교, BMS 갱신 시 IDS 해제 동작은 현재 서비스에 반영하지 않았다.

## 완료 판정 제한

- P1~P3 core·Qt Debug/Release 빌드와 단위 시험만 이 호스트에서 통과로 판정한다.
- Homebrew Qt 6.11.2 앱 빌드, ViewModel 시험과 offscreen demo 렌더를 검증했다. 실제 Linux/RPi 화면 증거는 아니다.
- macOS에는 Linux SocketCAN/vcan이 없어 실제 수신·통합은 미실행이다.
- RPi4, 물리 `can0`, 성능, 장시간 안정성, CI는 P4~P6의 후속 증거가 필요하다.

## P3 정책 판단

- stale은 마지막 인증 성공 BMS 기준 300ms이며 Fail-safe·IDS 이벤트가 이 시각을 갱신하지 않는다.
- IDS 확인은 sequence가 일치할 때만 현재 경보를 닫아 새 경보와의 경쟁을 방지한다.
- ICD §8이 아직 활성 wire 계약이 아니므로 sensorState를 UI 모델에 준비하되 현행 byte 7은 해석하지 않았다.
- Qt T2→T3 측정은 host signal 구간으로 한정하고 CAN·scene graph·display 지연으로 확대하지 않았다.

## P2 정책 판단

- 공동 규약 Q4=A에 따라 데이터 ID별 pending 한 개, 최신 원본 교체, 인증 선도착 폐기를 적용했다. 다중 후보 큐는 추가하지 않았다.
- pending 100ms는 내부 raw/auth pair 보관 정책이다. ICD §2.5의 정상 인증 BMS 300ms stale 계약과 분리했다.
- MAC·counter 실패는 pending을 자동 소비하거나 counter를 갱신하지 않는다. 새 원본 또는 만료 시에만 pending이 교체·폐기된다.
- SecOC 연속 실패 단계는 ICD §2.5.2의 1~3/4~9/10회 이상을 따르며 IDS `0x200` wire 계약을 변경하지 않는다.
- 실제 Linux SocketCAN 오류 경로는 macOS 단위시험으로 대체 통과하지 않고 P4 vcan 미실행 범위로 유지한다.
