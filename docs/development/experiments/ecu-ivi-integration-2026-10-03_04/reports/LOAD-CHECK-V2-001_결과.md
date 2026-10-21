# LOAD-CHECK-V2-001 IVI 결과

## ECU 추가 수령 후 최종 교차검증

[교차검증 JSON](../analysis/load-check-v2-001-crosscheck.json). ECU 원본 5,533프레임은 IVI 5,535프레임의 앞부분과 ID·payload·순서 전부 일치한다. IVI 끝의 정상 BMS·인증 한 쌍은 ECU 관측 종료 후 추가 기록이며 전체 원본 길이 일치라고 주장하지 않는다. ECU TX 증가 5,535는 IVI RX 증가 및 CAN 캡처 수와 일치한다. ECU manifest 결과 해시도 검증했다.

**공식 조건 인수 불가:** 공격 송신 성공/echo는 5,393/5,393이나 attack_tx_errors=1,871이다. 원본에는 OSError 클래스만 저장되어 errno가 없으므로 ENOBUFS 또는 SPI 병목으로 원인을 확정하지 않는다. 인터페이스 TX errors=0과 프로세스 send 실패는 다른 계층의 수치다. 정상 전달은 ECU 참조 원장 기준 공격 구간 1/30, 정상 원본 관측 13개다. 이는 정상 전달 저하 근거이며 IVI 화면 인수 수치와 구분한다.

현재 judge_trial은 attack_tx_errors를 결과에 기록하지만 INVALID 조건에 넣지 않는다. 따라서 원본 VALID·COMPLETE·exit 0을 그대로 보존하되 검토 판정은 NOT_ACCEPTED로 기록한다. 향후 판정기 보완과 errno 기록이 필요하다. 송신률만 올리는 재시험은 현재 증거로 정당화하지 않는다.

IVI TIMEOUT 레코드 10개도 모두 AUTH_TIMEOUT이다. FRAME 처리에서 발생한 2건을 합쳐 **AUTH_TIMEOUT 총 12건**, AUTH_ORPHAN 총 4건이다. 아래 초기 수령 표는 FRAME과 TIMEOUT을 분리한 수량이다. 최대 부하 45%는 50% 기준 미달이며 Config 3 준비와 별개로 공식 부하 조건은 미해결이다.

## IVI 최초 수령 기록

07H27M 전달 archive를 raw/LOAD-CHECK-V2-001/ivi에 보존했다. [분석](../analysis/load-check-v2-001-ivi.json). ECU 결과는 아직 미수령으로 양측 대조 및 실행 유효성 판정은 대기다.

| 항목 | 결과 |
|---|---|
| CAN 수신 | 5,535프레임, RX 전후 증가 5,535와 일치 |
| ID별 | flooding 0x000 5,393 / BMS 0x100 74 / 인증 0x102 68 |
| receiver FRAME | 142, CAN 필터 대상과 ID·payload·순서 일치, 전부 인증 ON |
| 인증 게시 | 62건 |
| 인증 관련 이상 | AUTH_ORPHAN 4건, AUTH_TIMEOUT 2건. 별도 TIMEOUT 레코드 10건은 상세 시점 대조 전 |
| 점유율 표시 | 07:24:37~40 KST에 22%, 45%, 45%, 23%. 최대 45% |
| flooding 관측 기간 | 첫~마지막 프레임 3.004649초 |
| CAN 오류 | 오류·드롭·bus-off 전후 증가 없음 |
| 종료 | dashboard/candump/canbusload 모두 0, 수집 stderr 둘 모두 비어 있음 |

점유율은 exact bitstuffing 모드의 초 단위 표시다. TC-SEC-005-d의 50% 조건은 이번에도 미충족이다. 이전 Config 2 13%보다 표시값은 높지만 송신률 설정도 달라 코드 수정만의 효과로 해석하지 않는다. 오류 통계 0을 애플리케이션 인증·정상 전달 무손실로 간주하지 않는다. AUTH_ORPHAN·AUTH_TIMEOUT을 MAC_FAIL로 기록하지 않는다.

다음은 기존 ECU results/load-check-v2-001 및 meta 수령·대조다. 큐 오류·실제 주입 수·ECU 정상 송신 원본·시험 종료 경계를 확인한 뒤 조정한다. 이번 상태만으로 송신률을 올리거나 본 실험 인수를 선언하지 않는다.
