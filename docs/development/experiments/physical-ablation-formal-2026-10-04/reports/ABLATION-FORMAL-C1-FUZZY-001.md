# ABLATION-FORMAL-C1-FUZZY-001 ECU 검토

상태: ECU 원본 수령·해시 검증 완료, IVI 교차검증 완료. Config1 SecOC OFF, v6, 요청1000fps, 공격3초/정상2초/후속1초, 계획100시행. ECU 기록 시각 2026-10-04 16:57:17~17:07:39 KST.

- 1~100번 누락 없이 실행기 VALID100 / INVALID0, exit0.
- 공격 송신277993 / own echo277993. 최종 송신 오류0, syscall 오류0, 재시도 복구0.
- 종료 경계 미호출4건은 별도 기록. 정상 기대3000 / 참조 수신·전달2999. 차이1건의 원인은 미확정이며 물리 손실로 단정하지 않는다.
- ECU TX 증가284184, CAN 오류·bus-off 증가0. qdisc dropped32→32 증가0, requeues545→2701 증가2156, 종료 backlog0.
- 참조 수신기 attack_published0, attack_parse_rejected276은 IVI 제품 판정이나 전체 공격 차단율이 아니다. 아래 IVI 관측 한계와 함께 해석한다.

원본은 raw/ABLATION-FORMAL-C1-FUZZY-001/ecu/에 보존하며 inventory SHA256으로 관리한다. [집계](../analysis/ABLATION-FORMAL-C1-FUZZY-001/ecu-summary.json). IVI 원본 대조와 제품 게시 판정 한계는 아래에 기록한다.

## IVI 교차검증 (17H13M)

IVI 원본 보존 및 inventory 등록 완료. ECU 관찰284182프레임은 IVI candump284184프레임의 앞부분과 CAN ID/payload/순서 모두 일치한다. IVI 끝의 추가2프레임은 공통 수집 구간 밖이며, IVI RX 증가284184=ECU TX 증가284184다. IVI CAN 오류·드롭·bus-off 증가0. receiver6884건은 candump의 대상 ID 필터 결과와 전부 일치한다. 대시보드/candump/canbusload 종료코드 모두0, 두 수집 stderr 빈 파일이다.

정상 기대 대비1건 차이는 시행4의 기대30/관찰29다. 전송된 프레임의 양측 불일치는 발견되지 않았으나 송신 주기·집계 창 등 세부 원인은 확정하지 않는다.

Fuzzy 공격 own 프레임 중 IVI 필터 대상은693건(ID256:131,257:145,258:125,259:138,512:154). OFF receiver는 전부 같은 published 메시지를 기록하지만 process_result=0에도 그 문구가 붙는다. 따라서 메시지 수를 실제 BMS 게시·화면 반영·공격 성공으로 집계하지 않는다. 참조 수신기의 파싱거부276건과도 로그 문구만으로 모순을 판정하지 않는다.

공격 창 내부 canbusload 표본 범위는1~21%다. flooding의50% 기준을 이번 fuzzy에 적용하지 않는다. 전후 시각 파일은 저장 시각이며 정확한 프로그램 시작·종료 시각은 미수집이다.

결론: C1 fuzzy 계획100회 수집과 전송 로그 대조 완료. 제품 공격 성공/실제 UI 반영 판정은 위 관측 한계를 유지한다. 추가 수집 없이 다음 구성된 시험으로 진행 가능하다. [교차검증 집계](../analysis/ABLATION-FORMAL-C1-FUZZY-001/crosscheck.json).
