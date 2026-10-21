# PHYSICAL-PILOT-IF-002 ECU 검토

ECU 자료 수령 및 manifest 9파일 SHA256 검증 완료. IVI 교차검증 대기.

Config 3 rules+if, 공격별 1회, 요청 1000fps·3초. 2026-10-04 08:05:33~08:06:11 KST. COMPLETE, exit 0. CLOCK 기록에서 SO_TIMESTAMPNS_NEW 적용 확인. 이전 baseline PERIOD_TOO_SHORT는 이번 4개 baseline에서 재발하지 않았다. 이것은 이번 실행 범위의 확인이며 장기 오탐 해결 확정은 아니다.

| 공격 | 판정 | 송신/관측 | 참조 수신기 공격 게시 | 정상 관측/전달 | 첫 주입 echo→경보 관측 |
|---|---|---|---|---|---|
| flooding | VALID | 2769/2769 | 0 | 30/30 | 0.784ms |
| fuzzy | VALID | 2659/2659 | 0 | 30/30 | 0.836ms |
| replay | VALID | 2876/2876 | 0 | 31/31 | 1.090ms |
| spoofing | VALID | 2755/2755 | 0 | 31/29 | 1.692ms |

전 시행 송신 오류·관측 drop 0. ECU TX 82581→94389, 증가 11808. CAN errors/dropped/bus-off 증가 0. 지연은 실행기 echo 및 경보 관측 기준으로 IVI 화면 지연이 아니다. replay 인증 거부 1438, spoofing MAC 거부 2. 참조 수신기 결과이며 IVI 제품 판정은 아직 NOT_RUN이다. normal_expected=30은 고정 기대값이라 31/30을 전달률 100% 초과 성과로 해석하지 않는다. spoofing 정상 프레임 2건 미전달은 IVI 로그와 대조할 항목이다.

중요: baseline_alerts=0은 모든 IDS 이상 로그가 0이라는 뜻이 아니다. spoofing baseline에는 IF_ANOMALY 1건이 존재한다. 이 이벤트는 attack_type=0으로 CAN 경보 송신 대상이 아니므로 baseline 중단 조건에 포함되지 않았다. 규칙 주기 오탐과 IF 이상 판단은 분리해 기록한다. 공격 창 내 if_events는 모두 0이며, 이번 4종 탐지는 규칙 경보로 확인됐다. IF 단독 공격 탐지 성능이 입증됐다고 주장하지 않는다.

원시 자료: ../raw/PHYSICAL-PILOT-IF-002/ecu/results/physical-pilot-if-002
집계: [ECU 분석 JSON](../analysis/physical-pilot-if-002-ecu.json)

다음은 IVI receiver·candump·점유율·통계 대조다. 고부하 ENOBUFS 및 공식 flooding 50% 조건은 별도 미해결이며 1200회 본 실험은 미실행이다.

## IVI 교차검증 완료

ECU 관측 11,790프레임이 IVI 캡처 앞부분과 순서·ID·payload 모두 일치한다. IVI 전체는 11,808프레임으로 ECU TX 및 IVI RX 증가량 11,808과 같다. 끝 18프레임은 ECU 참조 관측 종료 뒤 IVI에 남은 구간이며 prefix 비교에 포함하지 않았다. IVI 알려진 ID 필터 6,391프레임은 receiver FRAME과 모두 일치한다. CAN errors/dropped/bus-off 증가 0, candump/canbusload stderr 0바이트.

IVI 정상 BMS 인증 게시 312건, IDS 이벤트 게시 121건. replay COUNTER_BACKWARD 1,438건, spoofing MAC_FAIL 2건(counter 270,278) 확인. 두 MAC_FAIL은 ECU 참조와 동일 인증 프레임이다. 정상 원본과 인증 프레임 사이 주입된 위조 원본(c8be1068ffec4100)이 대기 원본이 되어, 정상 인증 프레임과 MAC이 맞지 않아 거부됐다. 따라서 정상 2건 미전달은 CAN 전송 누락으로 관측된 것이 아니라 공격 중 인증 짝 교란에 따른 가용성 영향이다. 위조 원본 수락으로 분류하지 않는다. 화면 렌더 확인은 별도 자료가 없다.

종료코드: candump 0, canbusload 0, dashboard 130. 대시보드 0으로 기록하지 않으며 사용자 전달로 시험 종료 후 Ctrl+C 수동 종료였음을 확인했다. 종료코드 130은 그대로 보존하며 이 종료코드만으로 시험 중 비정상 중단으로 판정하지 않는다. 점유율 최대 표시 24%로 공식 flooding 50% 조건 미달이다.

Config 3 기능 pilot 4종 완료 및 기존 주기 오탐의 이번 실행 재발 없음 확인. IF_ANOMALY 1건과 IF 단독 공격 탐지 미입증, 고부하 조건 미달은 그대로 보존한다. 본 실험 1,200회 인수 완료를 뜻하지 않는다.

[양측 대조 JSON](../analysis/physical-pilot-if-002-crosscheck.json)
