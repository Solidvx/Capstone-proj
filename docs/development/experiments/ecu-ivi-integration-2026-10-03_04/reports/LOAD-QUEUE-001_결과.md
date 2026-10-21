# LOAD-QUEUE-001 ECU 검토

2026-10-04 08:19:44~08:19:55 KST. Config2 flooding 3000fps 요청·3초, qlen100. INVALID/TX_ERRORS, exit2. manifest4파일 SHA256 검증 및 원본 보존 완료. IVI 결과 대기.

| 항목 | 이전 LOAD-DIAG-V3-001 qlen10 | 이번 qlen100 |
|---|---:|---:|
| 공격 송신 성공/관측 | 5425/5425 | 5445/5445 |
| 송신 오류 | 1828 | 1796 |
| 오류 종류 | ENOBUFS | 1796건 모두 errno105 ENOBUFS |
| 정상 관측/전달 | 15/2 | 23/19 |

단일 시행 비교이며 큐 확대가 지속적인 처리 한계를 해소했다는 근거는 없다. qdisc drop 증가1814(3778→5592), requeue 증가60, 종료 backlog0. 공격 송신 오류1796과 qdisc drop1814는 범위가 다른 계수이므로 동일시하지 않는다. ECU 전체 TX 증가5609, CAN errors/dropped/bus-off 증가0. 인터페이스 통계0으로 qdisc drop이 없었다고 해석하면 안 된다.

큐를 10으로 복구하도록 안내했으나 복구 후 출력은 아직 받지 않았다. 종료 시 backlog0은 공격 직후 배출 시간 계측을 대신하지 않는다. IVI 실제 점유율 및 프레임 대조는 자료 수령 후 수행한다. 같은 조건 재실행이나 큐 추가 확대는 진행하지 않는다.

## IVI 대조 완료

IVI 08H21M 자료를 대조했다. ECU 관측5607건이 IVI5609건의 prefix와 모두 일치. IVI RX77711→83320 증가5609는 ECU TX 증가5609와 일치한다. receiver164건은 알려진 CAN ID 필터 결과와 일치하며 정상 BMS 게시80건이다. 세 프로그램 종료코드 모두0, 두 수집 stderr0바이트, CAN 오류·drop·bus-off 증가0이다. 최대 점유율 표시는45%로 공식50% 미달이다.

결론: qlen100으로 변경해도 ENOBUFS1796 및 qdisc drop1814가 지속되고 실제부하45%에 머물렀다. 송신 성공한 구간의 양측 CAN payload 불일치는 없다. 큐 크기만으로 해결되지 않았으며 SPI/드라이버 처리 한계의 정확한 원인은 아직 확정하지 않는다. IVI 재시험은 바로 요청하지 않는다. qlen10 복구 확인과 하드웨어 허용 SPI 속도·드라이버 송신 경로 검토가 다음 단계다.

[대조 집계](../analysis/load-queue-001-crosscheck.json)
