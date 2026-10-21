# ABLATION-FORMAL-C3-REPLAY-001 ECU 검토

archive·manifest·100개 raw SHA256 일치. 원본은 raw/ABLATION-FORMAL-C3-REPLAY-001/ecu에 보존. 시행1~100, 100 VALID, exit0. 메타 파일 읽기 확인.

공격송신/own echo286527일치, syscall/최종송신오류0, deadline미시도5. TX증가302236, qdisc dropped1801→1801 증가0, requeues증가146778. 참조정상 expected/seen3001, delivered2864, own payload게시137. 137모두auth_own=false이며 최신정상payload와동일: 재전송pending+정상인증 결합으로 분류, 과거인증쌍137건수락으로 해석하지 않음. IVI제품게시대조대기.

IDS 요약 및 창 정보: {"ids_results": {"START": 1, "CLOCK": 1, "NORMAL": 6487, "ANOMALY": 435971, "ALERT_SENT": 3041, "DIAGNOSTIC": 143265}, "published_own": 137, "published_own_auth_own": 0, "same_latest_normal": 137, "detected_trials": 100, "non30_expected": [{"trial": 10, "normal_expected": 31, "t_attack_start": 20063.682790345, "t_attack_end": 20066.737816477}]}

expected3001은실제수집창길이기반기대값이며 고정계획3000과구분. 원본수치를수정하지않음. 원본저장시각21:38:22~21:49:03 KST. IVI 원본대조전최종보안판정 보류.

## IVI 21H54M 원본 대조

원본 보존 및 해당 실행 inventory SHA256 검증 완료. TX/RX 증가량302236일치. ECU302220은IVI302236의 정확한prefix, 추가16프레임은ECU관측종료이후. receiver302236모두candump순서·내용일치. CAN오류프레임0, IVI오류/드롭/bus-off증가0. IDS송신3041은IVI경보3041과순서·내용일치.

IVI 인증게시6334, counter역행거부143202, AUTH_ORPHAN60. 참조own게시137모두IVI게시·source_data일치, auth_own=false/최신정상payload동일. 과거인증쌍수락137로해석하지않으며 정상새인증+재전송pending결합으로 구분. 전체게시6334를전부정상송신유래라하지않음.

프로그램3개exit0. dashboard.stderr의Qt경고25회원본확인, collector stderr빈파일. 화면미수집·경고시각미기록·화면영향미확인. 전후시각은기록저장시각. replay에flooding50%기준적용하지않음. 버전별시각계측차이와참조/제품구분유지.
