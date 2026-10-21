# ABLATION-FORMAL-C3-SPOOF-001 ECU 검토

archive·manifest·100개 raw SHA256 검증 완료, 원본은 raw/ABLATION-FORMAL-C3-SPOOF-001/ecu에 보존. 시행1~100누락/중복없음,100 VALID·exit0. 메타파일읽기확인,21H54M replay와별개 실행.

공격송신/own echo275374일치. syscall/최종송신오류0, deadline미시도0. 참조정상expected3000/seen3001/delivered2802, 공격게시0. expected는주기기반기대값이며실제프레임수와동일개념아님. 3001관측의경계조건은 IVI대조시구분하고수치를덮어쓰지않음. 제품차단율/정상가용성은IVI대조전확정하지않음.

ECU TX증가291061, qdisc dropped1801→1801(증가0), requeues증가7256. CAN오류증가0. 시각기록2026-10-04 22:00:00~22:10:42 KST.

IDS 요약: {"ids_results": {"START": 1, "CLOCK": 1, "NORMAL": 9309, "ANOMALY": 278694, "ALERT_SENT": 3033, "DIAGNOSTIC": 275573}, "alert_types": {"4": 3026, "3": 7}, "detected_trials": 100, "rule_events": 278694, "if_events": 0, "ratios_over_one": [], "ids_process_log": ""}

IVI원본미수령. 최종12개조합통합분석은마지막IVI대조후진행. 기존실행버전차이·INVALID·C3flood002집계결함은그대로보존한다.

## IVI 22H37M 대조 완료 — 수신 예외 포함

원본 archive 및 파일 보존·해시검증 완료. ECU TX증가291061, IVI RX증가291059(2부족), IVI RX errors1→2(+1), candump오류프레임1: (1791119104.051850) can0 20000004#0001000000000000. 무오류·무손실 시험으로 표기하지 않는다. receiver291059 데이터프레임은IVI candump와전부일치.

ECU관측291045중 시행47 부근 위조0x100 payload c8be1068ffec4100 두개를 제외하면291043프레임이IVI prefix와순서·내용일치. 이후IVI끝16프레임은ECU관측범위밖. 동일payload반복이므로 부족한개수/종류는확인하지만 개별동일프레임의정확한식별은모호할수있다. 근본원인은자료만으로확정하지않는다. ECU실행기100 VALID는외부IVI수신오류를포괄하지않으므로수신예외를별도플래그한다.

IDS송신3033건전부IVI0x200과순서·내용일치. IVI전체인증게시6128, 공통구간6120모두pending정상ECU·auth정상ECU·source_data일치. 끝8게시출처는ECU대조범위밖. MAC_FAIL199건모두위조pending+정상auth결합. 공통구간위조payload인증게시증거없음, 정상인증가용성저하와구분.

프로그램3개exit0, Qt경고원본21회, candump/canbusload stderr빈파일. 화면미수집·경고화면영향미확인, before/after저장시각은프로그램정확한시작종료시각이아님. 추가재시험은자동으로진행하지않음.

12개조합원본수집및개별교차검토완료. 논문최종통합분석은버전별시각기준·INVALID·C3flood002전달률결함·외부수신예외·경보출처·분모를구분하여진행해야한다.
