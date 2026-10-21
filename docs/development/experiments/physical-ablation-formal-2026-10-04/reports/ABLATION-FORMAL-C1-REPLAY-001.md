# ABLATION-FORMAL-C1-REPLAY-001 ECU 검토

ECU 원본·manifest 및 시행 raw 해시 확인 완료. IVI 교차검증 완료. Config1 SecOC OFF, v6, 요청1000fps, 공격3초/정상2초/후속1초. ECU 기록 시각2026-10-04 17:23:02~17:33:25 KST.

- 시행1~100 누락 없음, VALID100/INVALID0, exit0.
- 공격 송신278319 / own echo278319, 최종송신오류0·syscall오류0·재시도0.
- 종료 경계 미호출3건 별도 기록. 정상 기대3000 / 참조 수신·전달2999. 차이1건 원인은 아직 미확정.
- 참조 수신기는 replay278319건 게시 기록. 이는 IVI 제품 및 실제 화면 반영 판정과 구분한다.
- ECU TX 증가284518, CAN 오류·bus-off 증가0. qdisc dropped32→32 증가0, requeues2701→4292 증가1591, backlog0.

원본 raw/ABLATION-FORMAL-C1-REPLAY-001/ecu/와 inventory에 보존했다. [ECU 집계](../analysis/ABLATION-FORMAL-C1-REPLAY-001/ecu-summary.json). 아래에 IVI 대조 결과를 기록한다.

## IVI 교차검증 (17H38M)

IVI candump284518=ECU TX 증가284518=IVI RX 증가284518. ECU 관찰284517프레임은 IVI 앞부분과 ID/payload/순서 모두 일치하며 끝1프레임은 공통 수집 구간 밖이다. receiver284518프레임도 candump와 일치한다. IVI CAN 오류·drop·bus-off 증가0, 세 프로그램 종료코드0. 전후시각은 기록 저장 시각이며 정확한 프로그램 시작·종료 시각으로 사용하지 않는다.

ECU own 표식으로 대응한 replay278319프레임(모두0x100)은 IVI에서 모두 process_result=2와 OFF 게시 메시지를 기록했다. 예시 source_data도 재전송 payload와 일치한다. SecOC OFF 수신 경로에서 재전송 데이터가 수락·게시된 증거이며 실제 물리 화면의 각 갱신을 보장하지 않는다. fuzzy의 모호한 메시지 단독 판정과 구분한다.

정상 기대 대비1건 차이는 시행5(기대30/참조관찰29)다. 전송 후 양측 로그 손실 근거는 없지만 개별 부족 원인은 미확정이다. 공격 내부 점유율 보고1~22%이며 flooding50% 기준을 적용하지 않는다.

계획100회 기록·원본 보존·양측 교차검증 완료. 다음 C1 spoofing 수집으로 진행할 수 있다. [교차검증](../analysis/ABLATION-FORMAL-C1-REPLAY-001/crosscheck.json).
