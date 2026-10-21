# ABLATION-FORMAL-C2-FLOOD-001 ECU 검토

원본 수령 및 manifest·100개 시행 raw SHA256 검증 완료. IVI 대조 완료, 인증 가용성 저하 관측. Config2 SecOC ON, v6, 요청2800fps, 공격3초/정상2초/후속1초. ECU 기록시각2026-10-04 18:15:14~18:25:49 KST.

- 계획1~100번 모두 존재, 실행기 VALID100/INVALID0, exit0.
- 공격 송신704701 / own echo704701. 최종 송신오류0, syscall 오류51, 재시도 복구51프레임. 종료 경계 미호출2건 별도 기록.
- 정상 기대3000 / 참조 관찰2993 / 참조 전달2967. 기대 대비33건, 관찰 대비26건의 전달 차이가 있다. 실제 IVI 인증·게시 결과와 구분하고 대조 전 원인을 확정하지 않는다.
- ECU TX 증가717287, CAN 오류·bus-off 증가0. qdisc dropped32→115 증가83, requeues6193→9929 증가3736, backlog0.

VALID는 수집 유효성으로 정상 전달100%나 제품 합격이 아니다. qdisc 증가를51건 복구와 단순 동일시하거나 실제 CAN 손실로 바로 해석하지 않는다. IVI 수신·오류·인증 및 공격별 부하50% 조건을 후속 대조한다.

원본 raw/ABLATION-FORMAL-C2-FLOOD-001/ecu/ 및 inventory에 보존. [집계](../analysis/ABLATION-FORMAL-C2-FLOOD-001/ecu-summary.json). 추가 재시험은 수행하지 않았다.

## IVI 교차검증 18H30M

IVI717287프레임=ECU TX 증가717287=IVI RX 증가717287. ECU 관찰717281프레임은 IVI 앞부분과 ID/payload/순서 전부 일치하며 IVI 끝6프레임은 공통 구간 밖이다. receiver12586프레임은 candump 대상 ID 필터와 전부 일치한다. CAN 오류프레임0, IVI RX errors는 누적1→1로 이번 증가0, drop·bus-off 증가0. 세 종료코드0.

전체 receiver 정상 BMS pending6303, 인증 게시6277, AUTH_ORPHAN6, AUTH_TIMEOUT4. 타임아웃은 FRAME 이외 이벤트도 포함한다. 공격 창을 ECU 수신시각과 일치 프레임 순서로 대응하면 pending2993, IVI 인증게시2968, orphan6이다. 참조2967과 IVI2968은 처리시점·타이머가 다른 수신기 집계이므로 동일시하지 않는다. 정상 기대3000 대비 공격 창 게시 차이가 있으며 CAN 전송 후 손실 증거는 없지만 인증 처리 가용성 저하가 관측된다. 송신 큐 드롭+83 및 미전송·타이밍 원인을 하나로 확정하지 않는다.

100개 시행 모두 공격 내부 canbusload1초 보고에서50% 이상 표본이 존재한다. 전체3초 내내50%임을 의미하지 않는다. [교차검증](../analysis/ABLATION-FORMAL-C2-FLOOD-001/crosscheck.json), [공격 창별 IVI 집계](../analysis/ABLATION-FORMAL-C2-FLOOD-001/ivi-attack-windows.json).

전후 시각 파일은 저장 시각이며 정확한 프로그램 시작·종료 시각이 아니다. ECU 실행기100 VALID는 유지하며 인증 timeout/orphan을 실험 결과로 보존한다. 무조건 정상 전달100% 또는 SecOC로 flooding 차단 성공이라고 보고하지 않는다. 추가 보충시험 없이 다음 C2 fuzzy 수집으로 진행 가능하다.
