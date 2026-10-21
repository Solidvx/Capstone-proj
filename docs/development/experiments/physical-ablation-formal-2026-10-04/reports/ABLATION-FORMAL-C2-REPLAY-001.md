# ABLATION-FORMAL-C2-REPLAY-001 ECU 검토

상태: 원본·manifest·100시행 raw SHA256 검증 완료, IVI 대조 및 게시 출처 확인 완료. Config2 SecOC ON, v6, 요청1000fps, 공격3초/정상2초/후속1초. ECU 기록시각2026-10-04 18:59:51~19:10:14 KST.

- 계획1~100 모두 존재, 실행기 VALID100/INVALID0, exit0.
- 공격 송신287914 / own echo287914. 최종송신오류0, syscall오류0, 재시도0. 종료 경계 미호출5건.
- 정상 기대3000 / 참조관찰2998 / 참조전달2880. 기대대비120건 차이.
- 참조 attack_published116건: 완전 차단으로 보고할 수 없다. 실제 과거 인증쌍 수락인지 정상 인증프레임과 재전송 payload의 결합·출처 귀속 문제인지 raw/IVI 대조가 필요하다. IVI 제품 취약점으로 바로 확정하지 않는다.
- ECU TX 증가300318. CAN 오류·bus-off 증가0, qdisc dropped115→115 증가0, requeues15987→163579 증가147592, 종료backlog0. requeue는 고유프레임 손실 수와 동일하지 않다.

원본 raw/ABLATION-FORMAL-C2-REPLAY-001/ecu/에 보존, [집계](../analysis/ABLATION-FORMAL-C2-REPLAY-001/ecu-summary.json). 정상 전달 및 공격 게시 귀속을 IVI 수령 후 대조한다. 자동재시험이나 기존결과 변경 없음.

## IVI 교차검증 및116건 출처 (19H24M)

IVI candump/receiver300318프레임 순서·데이터 일치. ECU 관찰300314프레임은 IVI 앞부분과 전부 일치, 끝4건은 공통구간 밖. ECU TX증가=IVI RX증가300318. IVI RX errors 실제 파일은1→1(증가0), drop/bus-off증가0, 오류프레임0. 팀원 텍스트의11은 원본 통계1과 구분한다. 세 프로그램 종료코드0.

IVI 인증게시6200, COUNTER_BACKWARD143899, MAC_FAIL2, AUTH_ORPHAN56. 인증게시6200을 모두 정상 원본 출처로 가정하지 않는다.

참조 attack_published116건 전부를 프레임 순서로 IVI에 대응했다. 116건 모두 IVI 인증게시 및 source_data 일치. 인증 프레임은116건 모두 ECU 정상 송신(own=false), pending 원본은 공격 출처이며 payload가 최신 정상 BMS payload와116건 모두 동일하다. 따라서 과거 인증쌍의 replay 수락116건이 아니라 동일 payload 재전송이 새 정상 인증과 결합된 출처 귀속 사례다. 이를 재전송 counter 방어 실패116건 또는 새로운 위조값 수락116건으로 집계하지 않는다. 원래 attack_published 수치를 수정하지 않고 해석을 별도 보존한다.

[116건 대응 근거](../analysis/ABLATION-FORMAL-C2-REPLAY-001/attribution.json), [전체 대조](../analysis/ABLATION-FORMAL-C2-REPLAY-001/crosscheck.json). 정상 참조전달 감소는 이 출처 귀속 영향을 포함하므로 전부 정상 데이터 손실로 해석하지 않는다.

Qt 애니메이션 경고9회는 팀원 사후 메모이며 stdout/stderr 및 발생시각 미수집, 실제 화면 영향 미확인. 전후 시각은 저장시각이다. 원본 메모를 그대로 보존한다. C2 replay100회 수집·대조 완료, 추가 재시험 없이 다음 C2 spoofing으로 진행 가능하다.
