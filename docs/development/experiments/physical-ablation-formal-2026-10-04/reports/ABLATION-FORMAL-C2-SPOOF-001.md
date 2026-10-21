# ABLATION-FORMAL-C2-SPOOF-001 ECU 검토

ECU 원본·manifest·100시행 raw SHA256 검증 및 보존 완료. IVI 대조 완료. Config2 SecOC ON, v6, 요청1000fps·공격3초/정상2초/후속1초. ECU 기록시각2026-10-04 19:32:37~19:42:59 KST.

- 계획1~100 존재, 실행기 VALID100/INVALID0, exit0.
- 공격 송신277307 / own echo277307, 최종송신오류0·syscall오류0·재시도0. 종료 경계 미호출3건 별도 기록.
- 참조 수신기 attack_published0. IVI 제품 차단 판정은 수신 로그 대조 전 보류.
- 정상 기대3000 / 참조관찰2997 / 참조전달2759. 기대대비241건·관찰대비238건의 차이를 보존하며 원인을 확정하지 않는다.
- ECU TX증가289691, CAN 오류·bus-off 증가0. qdisc dropped115→115 증가0, requeues163579→169660 증가6081, backlog0.

[집계](../analysis/ABLATION-FORMAL-C2-SPOOF-001/ecu-summary.json). 원본 raw/ABLATION-FORMAL-C2-SPOOF-001/ecu/와 inventory에 보존. VALID를 정상전달100%로 해석하지 않는다. IVI 정상인증·거부·프레임대조 후 제품 결과를 판단한다.

## IVI 대조 및 게시 출처 (20H15M)

ECU TX증가=IVI RX증가=candump=receiver289691프레임. ECU 관찰289687은 IVI 앞부분과 ID/payload/순서 전부 일치, 마지막4프레임은 공통구간 밖의 BMS/인증2쌍이다. IVI CAN 오류·drop·bus-off 증가0, 오류프레임0, 세 종료코드0.

IVI 인증게시5954건. 공통구간5952건은 직전 pending BMS·인증 모두 ECU own=false이고 게시 source_data와 정상 원본이 모두 일치한다. 마지막2건도 정상payload이나 ECU own표식 대조 구간 밖이므로 출처 판정 범위를 구분한다. 위조payload가 IVI에 게시된 증거는 없다.

MAC_FAIL238건 모두 ECU own 위조pending에 정상 ECU 인증(own=false)이 도착한 경우다. 원본/인증 사이에 위조payload가 끼어들어 정상 인증과 불일치한 사례로 확인된다. 위조값 미게시와 정상전달 가용성 저하는 함께 기록한다. 전체 AUTH_TIMEOUT1건도 보존한다. 238건을 모든 주입277307프레임의1:1거부 수로 해석하지 않는다.

[출처 대응](../analysis/ABLATION-FORMAL-C2-SPOOF-001/attribution.json), [CAN 대조](../analysis/ABLATION-FORMAL-C2-SPOOF-001/crosscheck.json). Qt 애니메이션 경고 반복은 사후메모, 발생횟수·시각·화면영향·장시간 실행과의 인과관계 미확인이다. 전후시각은 저장시각으로 유지한다.

C2 네 공격100회씩 수집 및 양측 대조 완료. 실행기400 VALID와 실제 인증처리·경보입력·정상전달 영향은 별도 해석한다. 시험 중 코드·설정 변경이나 자동보충 재시험은 하지 않았다.
