# 물리 pilot 준비 — 아직 실행하지 않음

ECU 전달본 8a57f7f, IVI 004-verified를 사용한다. ECU는 can0 500kbps 및 기존 송신 프로세스 없음, canbusload 설치를 사용자 출력으로 확인했다. IVI는 실행 명령만 전달했으며 READY·캡처 시작 확인 대기다.

## 준비된 Config 1 실행 스크립트

[run_physical_pilot_c1.sh](../tools/run_physical_pilot_c1.sh)는 ECU의 전달본 루트에서 실행하는 보조 스크립트다. 인수 없이 실행하면 송신하지 않고 종료한다. 기존 결과 폴더가 있으면 덮어쓰지 않는다. --ivi-ready는 운영자가 실제 READY·캡처 시작을 확인했다는 표시이며 자동 원격 상태 검사가 아니다.

- 하네스 ID: PHYSICAL-PILOT-001, IVI ID: SECURITY-PILOT-OFF-001.
- Config 1: SecOC OFF, IDS 없음, constant 입력, 4공격 각 1시행, 요청 1000fps·공격 3초.
- 실행 전후 CAN 통계·시각·종료코드·패키지 목록을 별도 meta 폴더에 저장한다. stdout은 파일로 직접 기록해 tee 종료의 영향을 피한다.
- actual run 디렉터리는 하네스가 생성한다. 종료 뒤 원본·meta를 함께 수령한다.
- 이 스크립트는 물리 실행 검증 전이다. IVI나 CAN 설정을 변경하지 않는다.

로컬 Git Bash의 `bash -n` 문법 검사 통과, 인수 없는 실행은 송신 전 안내 후 종료함을 확인했다. 실제 RPi 송신·종료·파일 수집 동작은 미실행이다. 기존 summarize_live로 vcan 12행 집계를 재생성했고, 각 셀 valid=1·missing_to_100=99·official_verdict=NOT_RUN임을 확인했다. 결과는 [vcan 집계](../analysis/vcan-pilot-001-summary.json)에 보존한다.

## IVI 수령 자료와 검토 기준

| 자료 | 확인할 사항 |
|---|---|
| 실행 명령·manifest | 실험용 OFF 바이너리, run-id, 실제 소스/전달본 |
| receiver JSONL | secoc_on=false, 정상 수용 및 공격별 처리 결과 |
| 전체 candump | 오류 프레임 포함, ECU 공격 구간과 수집 구간 대조 |
| CAN 전후 통계·stderr | 오류·drop 증가 및 캡처 이상 |
| canbusload 기록 | 실행 옵션·버전·시간 기준, 완전한 공격 구간의 실측 부하 |
| 종료코드 | 사용자 중단·정상 종료 구분 |

관측 누락이나 오류 프레임을 파서가 지원하지 않으면 정상 데이터로 무시하지 않고 별도 해석한다. ECU own echo의 송신 귀속을 IVI 로그에서 직접 얻을 수 있다고 가정하지 않는다. 반복된 동일 payload는 순서와 구간을 함께 사용해 대조하고 귀속 불명은 미확정으로 남긴다.

1000fps는 pilot 시작 설정이다. vcan 실제 송신률도 설정값에 못 미쳤으므로 물리 버스 부하 50% 충족이나 목표 공격 강도 도달을 미리 선언하지 않는다. 물리 pilot에서 부하를 측정하고 본 실험 조건을 고정한다.

## 본 실험 전 남은 의사결정

EXQ-4=B는 Config 3의 규칙+IF 실행을 선택했다. 사용자의 IF 오탐 개선 보류는 이 선택을 자동으로 규칙 전용으로 바꾼 것이 아니다. 규칙 전용 pilot은 진행 가능하지만, 본 실험 전 정상 학습 자료와 IF 평가를 준비하거나 사용자가 명시적으로 실험 범위를 변경해야 한다. 이를 확정하기 전 1200회 전체 완료를 약속하지 않는다.

현재는 물리 Config 1 준비를 진행하고 Config 2·3은 각각 별도 IVI ON 인스턴스로 수행한다. 프로파일·MAC fixture 등 계획 잔여 항목은 별도로 유지한다.
