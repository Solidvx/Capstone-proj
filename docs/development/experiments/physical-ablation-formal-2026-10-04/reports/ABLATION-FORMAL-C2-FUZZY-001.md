# ABLATION-FORMAL-C2-FUZZY-001 ECU 검토

상태: ECU 원본 수령·manifest 및 시행 raw SHA256 검증 완료, IVI 교차검증 완료. Config2 SecOC ON, v6, 요청1000fps, 공격3초/정상2초/후속1초. ECU 기록시각2026-10-04 18:35:15~18:45:35 KST.

- 계획1~100번 모두 존재, 실행기 VALID100/INVALID0, exit0.
- 공격 송신277757 / own echo277757. 최종 송신오류0·syscall오류0·재시도0. 종료 경계 미호출2건 별도 보존.
- 정상 기대3000 / 참조 관찰·전달2999. 차이1건 원인 미확정.
- 참조 공격게시0·파싱거부275는 IVI 제품 차단율이 아니다.
- ECU TX 증가290125, CAN 오류·bus-off 증가0. qdisc dropped115→115 증가0, requeues9929→15987 증가6058, backlog0.

## 대시보드 다른 공격명 표시

사용자는 fuzzy 도중 flooding/spoofing 등 공격명이 표시됐다고 보고했다. build_frame(fuzzy)는 11비트 ID와8바이트 payload를 무작위 생성한다. 실제 ECU own 수신에 ID0x200이 154건 존재한다. 이 프레임들이 경고 처리 경로에 들어갔을 가능성을 후속 IVI 대조 대상으로 남긴다. 실제 IVI 실행 소스·receiver·화면 기록 확인 전 정상 IDS가 다른 공격을 탐지했다고 결론내리지 않는다. 이번 config2에는 IDS 실행을 요청하지 않았다.

[ID0x200 프레임](../analysis/ABLATION-FORMAL-C2-FUZZY-001/fuzzy-id-200.json), [ECU 집계](../analysis/ABLATION-FORMAL-C2-FUZZY-001/ecu-summary.json). 원본 raw/ABLATION-FORMAL-C2-FUZZY-001/ecu/에 보존. IVI 원본 수령 후 전송·인증·경고 표시를 대조한다.

## IVI 대조 및 경보 출처 확정 (18H53M)

ECU TX 증가290125=IVI RX 증가290125=IVI candump290125. ECU 관찰290121은 IVI 앞부분과 ID/payload/순서 전부 일치, 마지막4건은 공통 구간 밖. receiver13059프레임은 CAN 대상ID 필터와 전부 일치한다. IVI 오류프레임0, RX errors 누적1→1 증가0, drop/bus-off 증가0, 세 종료코드0.

정상 BMS pending6184·인증게시6184. 무작위 입력에 대한 invalid BMS131, invalid Fail-safe144, BMS AUTH_ORPHAN124, Fail-safe AUTH_ORPHAN138, invalid IDS152, IDS event published2. 서로 다른 처리 종류를 통합 차단율로 집계하지 않는다.

0x200 경보2건은 ECU own fuzzy 입력에 payload가 유일하게 일치한다.

- 시행10: 0410dd8488fefa46 → IVI IDS event published/process_result2. 팀원 확인 화면명 Flooding, candump시각18:36:17.958241.
- 시행42: 0369b3c5eaa5db70 → IVI IDS event published/process_result2. 팀원 확인 화면명 Spoofing, candump시각18:39:34.868091.

154개0x200 중152형식거부·2게시. 이는 실제 IDS 탐지2건이 아니라 fuzzy 생성 프레임이 경보 입력으로 수락된 사례다. IDS 탐지율 분자에서 제외하고 경보 경로의 비인증 입력 수락으로 별도 보고한다. 팀원은004 코드에서0x200이SecOC인증대상이 아니며 경보는 사용자확인 전까지 유지된다고 확인했다. 이 코드/UI 설명은 팀원 제공 근거, payload·시행대응은 로컬 원본 대조 근거로 구분한다. ICD나 시험 중 구현은 변경하지 않았다.

[경보 출처](../analysis/ABLATION-FORMAL-C2-FUZZY-001/alert-attribution.json), [전체 대조](../analysis/ABLATION-FORMAL-C2-FUZZY-001/crosscheck.json). 정상 기대와 참조관찰1건 차이의 개별 원인은 미확정이나 전송된 프레임의 양측 불일치는 없다. 전후시각은 저장시각으로 유지한다. C2 fuzzy 수집·대조 완료, 재시험 없이 다음 C2 replay로 진행 가능하다.
