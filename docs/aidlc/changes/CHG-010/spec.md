# CHG-010 — IVI Debian 13·Qt 6.8 기준 통일

요청(2026-10-03): 실제 Node B RPi4 환경에 맞춰 IVI 플랫폼을 Debian 13 ARM64와 Qt 6.8로 통일하고, Qt CMake 정책 오류와 SocketCAN 미지원 환경의 시험 판정을 정리한다.

포함 범위:

- ADR-010, SDD-IVI, IVI 실행 계획과 AGENTS 스냅샷의 대상 플랫폼 동기화
- Qt 최소 버전 6.8과 `qt_standard_project_setup(REQUIRES 6.8)` 적용
- `IVI_REQUIRE_SOCKETCAN=1`일 때 SocketCAN 준비 실패를 FAIL로 강제
- Debian 13 RPi4 배포·설치·키 배치·preflight 파일을 `develop` 대상 PR에 포함
- Qt 포함 전체 CTest와 실제 `vcan0` 시험 결과 기록

제외 범위: CAN wire 계약 변경, 실제 SecOC 키 저장, MCP2515 물리 `can0` 통과 판정.

완료 조건: Debian 13 RPi4에서 Qt 버전과 커밋을 기록하고 `vcan0`을 올린 뒤 `IVI_REQUIRE_SOCKETCAN=1` 전체 CTest를 통과한다. PR base는 `develop`이다.
