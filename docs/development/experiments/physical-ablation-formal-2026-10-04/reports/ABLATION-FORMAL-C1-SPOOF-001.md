# ABLATION-FORMAL-C1-SPOOF-001 ECU 검토

상태: ECU 원본 수령 및 manifest·시행 raw SHA256 검증 완료. IVI 대조 완료: 수신 오류·프레임 차이 발견.

Config1 SecOC OFF, v6, 요청1000fps, 공격3초/정상2초/후속1초. ECU 기록 시각2026-10-04 17:44:56~17:55:19 KST.

- 계획1~100번 모두 존재, 실행기 VALID100/INVALID0, 종료코드0.
- 공격 송신278232 / own echo278232. 최종송신오류0, syscall오류0, 재시도0, 종료 경계 미호출0.
- 정상 기대3000 / 참조 관찰3000 / 참조 전달3000.
- 참조 수신기 공격 게시278232건. IVI 제품·화면 반영 판정과 구분하며 양측 대조 전 확정하지 않는다.
- ECU CAN TX 증가284430, CAN 오류·bus-off 증가0. qdisc dropped32→32 증가0, requeues4292→6193 증가1901, 종료 backlog0.

원본: raw/ABLATION-FORMAL-C1-SPOOF-001/ecu/. [집계](../analysis/ABLATION-FORMAL-C1-SPOOF-001/ecu-summary.json). 모든 원본은 inventory로 관리하며 IVI 결과 수령 후 교차검증한다.

## IVI 교차검증 18H08M

IVI 일반 데이터284429프레임, 오류프레임1건. ECU TX 증가284430 대비 IVI RX 증가284429로1건 적고 IVI RX errors0→1이다. candump 오류 원문은 (1791103868.103903) can0 20000004#0001000000000000. stderr 빈 파일과 CAN error frame 부재는 같은 의미가 아니다. 세 프로그램 종료코드는0이다.

ECU 관찰284429와 IVI 일반284429는 단순 동일하지 않다. ECU 순서에서 위조0x100 payload c8be1068ffec4100 한 건을 제거하면 IVI 마지막 추가1건을 제외한 전체 순서와 정확히 일치한다. 최초 구별 가능한 불일치 인덱스169254는 시행60 공격 창이다. 반복 payload 때문에 정확히 어느 반복 프레임이 빠졌는지는 고유하게 특정할 수 없다. 오류프레임도 인접 구간에 기록되며 원인 하드웨어 부품까지 확정하지 않는다.

receiver284429는 candump 일반 프레임과 ID/payload/순서 전부 일치한다. 실행기100회 VALID는 유지하되 시행60에 IVI 수신 오류·손실 관측을 별도 표시한다. 전체 무손실 또는 모든 시험 합격으로 보고하지 않는다. 원본 변경이나 자동 보충 재시험은 하지 않는다. 전후 시각은 저장 시각이고 프로그램 정확한 시작·종료 시각은 미수집이다.

[대조 집계](../analysis/ABLATION-FORMAL-C1-SPOOF-001/crosscheck.json). 원본·오류프레임 모두 inventory로 보존했다. Config1 네 공격 기록 수집 및 대조 완료, spoofing 시행60의 관측 한계를 포함한다.
