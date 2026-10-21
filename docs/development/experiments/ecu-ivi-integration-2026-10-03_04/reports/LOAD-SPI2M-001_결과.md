# LOAD-SPI2M-001 ECU 검토

SPI2MHz 적용값 기록 확인. Config2 flooding, 요청3000fps·3초, qlen10. 2026-10-04 08:34:07~08:34:18 KST. 원본 보존 및 manifest4파일 SHA256 검증 완료.

| 항목 | 1MHz qlen10 LOAD-DIAG-V3-001 | 2MHz qlen10 이번 실행 |
|---|---:|---:|
| 공격 송신 성공/관측 | 5425/5425 | 7299/7299 |
| 공격 송신 오류 | 1828 | 12 |
| 정상 관측/전달 | 15/2 | 23/10 |

이번 오류12건 모두 errno105 ENOBUFS. 판정 INVALID/TX_ERRORS·exit2 유지. ECU TX증가7457, qdisc drop증가36, requeue64, 종료backlog0. qdisc36과 공격송신오류12는 다른 범위의 계수다. CAN errors/dropped/bus-off 증가0, 참조rx_dropped0.

SPI 변경 뒤 송신량 증가·오류 감소가 관측되었으나 단일 실행이며 재부팅도 동반되어 SPI 단독 인과를 확정하지 않는다. 정상 프레임 전달 저하와 qdisc drop이 남아 있으므로 해결 완료가 아니다. IVI 실제 점유율과 양측 payload 대조는 수령 대기. 부하50% 달성은 아직 확인되지 않았다. 동일조건 재실행·추가 SPI 상향은 보류한다.

## IVI 교차검증 완료

08H36M 자료: ECU7455 관측은 IVI7457의 prefix와 모두 일치. IVI RX83320→90777 증가7457은 ECU TX증가와 일치. receiver FRAME158건은 알려진ID 필터와 일치한다. BMS 인증게시71, AUTH_TIMEOUT11(일반10+WARNING1), AUTH_ORPHAN1. CAN errors/drop/bus-off 증가0, 수집stderr0, 세 프로그램 종료코드0.

canbusload exact bitstuffing의 08:34:14/15/16 표시값은 각각61%/62%/56%. 50% 이상 부하는 관측됐으나 송신오류12 및 qdisc drop36으로 실행INVALID 판정은 유지한다. 부하 수치 조건 관측과 전체 시행 유효성은 구분한다. 주입 요청3000fps를 조금 낮춰 50% 이상과 송신오류0을 동시에 만족하는지 확인할 여지는 생겼다. 다음 비교 후보는2600fps·3초·동일 SPI2MHz/qlen10이며 달성 보장은 아니다. IVI SPI1MHz 및 CAN500kbps 유지. 정상 ECU 송신 손실도 함께 평가하며 공격기 오류만0으로 숨기지 않는다.

[양측 대조 집계](../analysis/load-spi2m-001-crosscheck.json)
