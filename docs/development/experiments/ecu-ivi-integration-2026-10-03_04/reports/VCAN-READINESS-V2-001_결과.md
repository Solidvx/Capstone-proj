# VCAN-READINESS-V2-001

ECU RPi에서 v2 전달본을 빌드한 후 수행한 vcan pilot. 사용자 제공 빌드 출력은 Python 59 passed(26.77s), CTest 17/17(0.48s)이며 독립 로그 파일 수령과 구분한다. archive 원본과 내부 자료는 raw/VCAN-READINESS-V2-001에 보존했다. [분석](../analysis/vcan-readiness-v2-001.json).

Config 2·3 모두 COMPLETE, 8시행 VALID. manifest 결과 해시 각각 7개·9개 일치. 모든 시행 송신=자기 echo 관측, 송신 오류·관측 드롭 0. Config 3은 rules-only이며 IF는 NOT_RUN이다.

| 공격 | C2 주입 수 | C3 주입 수 | C3 경보 최초 관측 지연 |
|---|---|---|---|
| flooding | 7306 | 7202 | 0.645ms |
| fuzzy | 7291 | 7220 | 0.190ms |
| replay | 8016 | 7978 | 0.252ms |
| spoofing | 7241 | 7181 | 0.181ms |

각 공격 구간은 약 3초, 요청률 3000fps다. 위 지연은 ECU 자체 echo 주입 시각부터 참조 관측기의 경보 프레임 수신까지이며 IVI 화면 지연이나 물리 CAN 성능이 아니다. vcan의 프레임 수로 실제 점유율 50%를 합격 처리하지 않는다.

C2 replay 공격 게시 6건이 원장에 기록됐다. 과거 인증 수용인지 동일 payload와 정상 인증 결합인지 이번 원시 사건별 추가 분류 전이므로 기존 1건 분석을 자동 적용하지 않는다. C3 정상 전달 건수는 fuzzy 31, replay 32, spoofing 33으로 고정 기대량 30보다 크다. 경계 지연/원장 분모 확인 전 delivery_ratio를 정밀 성능 지표로 사용하지 않는다. VALID는 실험 수집 유효성으로만 해석한다.

다음은 물리 정상 fit/calibration/evaluation 세 구간 각 300초 수집과 독립 IF 평가다. IVI 준비 완료 확인 후 정상 송신을 시작한다. 공식 부하 인수·Config 3 물리 IF pilot·본 실험은 미완료다.
