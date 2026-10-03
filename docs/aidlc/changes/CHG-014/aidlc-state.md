# CHG-014 상태

- 소프트웨어 구현·호스트 검증 완료: 정상 캡처·IF 평가, 실시간 시험 하네스, MAC 변조 fixture, Fail-safe 프로파일, ADC 원시 측정, 증거 집계. Python 55/55, ECU 17/17.
- 실시간 실행 인수 미완료: WSL vcan 모듈 부재로 RPi pilot 필요. 하네스는 참조 수신기 관측이며 IVI 제품 인수와 구분한다.
- 발견: 독립 합성 IF smoke 오탐 16/108창(14.81%)으로 5% 기준 미달. 규칙은 0/108. 임계 미조정, 실측 평가 대기.
- 실제 물리 시험: 사용자 실행·로그 전달 대기. 구현 완료와 최종 인수를 구분한다.
- IVI 시험 전용 OFF·로그 구현: 사용자 결정에 따라 IVI 담당자 소관, 인계 명세 작성 완료.
- 기존 EXQ-11: [draft PR #24](https://github.com/Solidvx/Capstone-proj/pull/24), base develop. 자동 병합하지 않았다.
- [요구](spec.md) · [검증](evidence.md) · [실행 절차](../../../development/playbooks/live-security-validation.md)
