# 수집 당시 인덱스 이력

이하 내용은 감사 보완 전 인덱스의 원문이다. 미시작·미완료·최신 표기는 당시 시점이며 현재 상태는 CHG-014와 상위 README를 따른다.

# 공식 물리 Ablation 본 실험

상태: C1 flooding 계획 번호 1~100 ECU 기록 수집 완료. 중복 7번 포함 101개 시도, 실행기 VALID 99개·INVALID 2개. 002·003 IVI 대조 완료. 다른 구성·공격 공식 시행은 미완료.

## 저장 규칙

- raw/<run-id>/ecu/ 및 ivi/: 수령 압축파일과 추출 원본. 실패·중단·INVALID도 보존하며 덮어쓰지 않는다. 제작 manifest·실행 버전·명령·환경·전후 CAN 및 qdisc 통계·종료코드·시작종료 시각을 수령 범위대로 연결한다.
- analysis/<run-id>/: ECU/IVI 프레임 대조, 부하, 탐지·차단·정상 전달 집계. 참조 수신기와 IVI 제품 판정을 구분한다.
- reports/<run-id>.md: 조건, 시도/유효/무효 횟수, 판정, 실패 원인, 근거 경로, 미수령 자료. 재실행은 새 ID로 남기고 무효 시행은 삭제하지 않는다.
- inventory.json: 수령 파일별 원래 위치·보존 경로·바이트 수·SHA256. 수령 파일은 아래 실행별 등록과 보고서에서 확인한다.
- 실행 중 RPi의 results/ 및 전송용 tmp/는 수집·전달 위치이며 최종 보존 위치는 이 디렉토리다.

raw/는 Git 제외 로컬 보존이다. Git push나 외부 백업이 완료됐다는 뜻이 아니다. 실제 키·토큰·접속 주소는 저장하지 않는다. 코드 및 가벼운 보고서의 커밋은 별도 사용자 지시에 따른다.

## 실행별 등록

| Run ID | 구성/공격 | 목표 | 상태 |
|---|---|---:|---|
| ABLATION-FORMAL-C1-FLOOD-001 | Config1 / flooding | 유효100회 | 7회 시도·공식유효6/100·무효1, 후속대기 |

실제 실행 이후 시도·유효·무효 건수와 수령 현황을 등록한다. 송신 오류0, 실제 부하조건 및 IVI 증거를 시행별로 확인하며 한 번의pilot통과로 전체반복을통과처리하지 않는다. 탐지율 등 수치의 분모를 반드시 기록한다.

## 선행 근거와 잔여 사항

[기존 pilot·통합시험·시행착오](../../ecu-ivi-integration-2026-10-03_04/README.md)는 별도 디렉토리에 유지한다. Config2 부하검증1회에서 ECU SPI2MHz·IVI SPI1MHz·CAN500kbps·ECU qlen10·flooding요청2800fps·3초로60% 및송신오류0을 확인했다. 다른공격·구성의공식조건은 실행전에 확정해 기록한다. Config3 정상구간IF_ANOMALY1건과IF단독공격탐지미입증은별도 잔여항목이다.

공식기준은 [TEST_PLAN](../../../../TEST_PLAN.md), 진행원본은 [CHG-014](../../../../aidlc/changes/CHG-014/aidlc-state.md)를 따른다.

[첫 실행 ECU 검토](../reports/ABLATION-FORMAL-C1-FLOOD-001.md)

[송신 큐 재시도 및 시행 재개 v5](../reports/TX-RETRY-V5.md): 로컬 74개 및 사용자 제공 Pi 74개 시험 통과. 후속 v6로 물리 수집 완료. 송신 오류 집계 의미 변경과 버전별 구분을 참조한다.

## 100회 수집 방식 정정

사용자 지시에 따라 INVALID도 계획 시행에 포함하고 자동 보충하지 않는다. 기존 유효100회 안내는 정정한다. [v6 동작과 002 제공 결과](../reports/CONTINUE-INVALID-V6.md)를 따른다. 기존 실행 원본과 판정은 유지한다.

[002·003 ECU 원본 검토](../reports/ABLATION-FORMAL-C1-FLOOD-002-003.md) — 원본 해시 확인, qdisc 증가 및 정상 전달 집계 차이 보존.

002·003 공통 CAN 구간 전부 일치, TX/RX 증가량 일치. 모든 94시도에 공격 내부 50% 이상 보고 확인. 종료코드·시각 한계는 [보고서](../reports/ABLATION-FORMAL-C1-FLOOD-002-003.md)에 보존했다.

## C1 fuzzy ECU 수집 완료

100회 실행기 VALID, 송신 오류0·qdisc drop 증가0. IVI 대조 완료. [검토 보고서](../reports/ABLATION-FORMAL-C1-FUZZY-001.md).

C1 fuzzy IVI 대조 완료: TX/RX284184 일치, 공통 프레임순서 전부 일치. OFF published 메시지는 process_result0에도 나타나므로 실제 UI 게시 판정에 단독 사용하지 않는다. 상세는 fuzzy 보고서를 참조한다.

## C1 replay ECU 수집 완료

100회 실행기 VALID, 송신오류0·qdisc drop 증가0. IVI 대조 완료. [보고서](../reports/ABLATION-FORMAL-C1-REPLAY-001.md).

C1 replay: TX/RX284518 일치, 공격278319건 모두 IVI process_result2. 화면별 렌더 여부와 구분한다.

## C1 spoofing ECU 수집 완료

100회 실행기 VALID·exit0. 정상3000/3000, 송신오류0·qdisc drop 증가0. IVI 대조 대기. [보고서](../reports/ABLATION-FORMAL-C1-SPOOF-001.md). Config1 네 공격 ECU 수집은 완료, spoofing 양측 판정은 미완료다.

## C1 spoofing IVI 대조 완료

IVI RX errors +1 및 일반프레임1건 차이. 시행60 공격 구간과 연관된 불일치를 별도 기록했다. 실행기100 VALID를 제품 무손실로 해석하지 않는다. [상세](../reports/ABLATION-FORMAL-C1-SPOOF-001.md). Config1 네 공격 대조 완료.

## C2 flooding ECU 수령

100회 VALID·exit0, syscall51건 복구, qdisc drop +83. 정상 기대3000/참조전달2967. IVI 및 부하 대조 대기. [보고서](../reports/ABLATION-FORMAL-C2-FLOOD-001.md).

C2 flooding IVI 대조 완료: TX/RX717287 일치, 100회 내부부하50% 이상, AUTH_TIMEOUT4·AUTH_ORPHAN6. 인증 가용성 저하를 결과로 보존한다. [보고서](../reports/ABLATION-FORMAL-C2-FLOOD-001.md).

## C2 fuzzy ECU 수령

100회 VALID·exit0, 송신오류0·qdisc drop 증가0. 다른 공격명 표시와 무작위 ID0x200 프레임은 IVI 대조 대상. [보고서](../reports/ABLATION-FORMAL-C2-FUZZY-001.md).

C2 fuzzy IVI 대조 완료: TX/RX290125 일치. 시행10·42의 fuzzy0x200이 경보2건으로 수락됨을 확인, 실제 IDS 탐지로 집계하지 않는다. [보고서](../reports/ABLATION-FORMAL-C2-FUZZY-001.md).

## C2 replay ECU 수령

100회 VALID·exit0, 송신오류0. 정상 참조전달2880/기대3000, 참조 attack_published116건으로 완전차단 판정 불가. IVI 대조 대기. [보고서](../reports/ABLATION-FORMAL-C2-REPLAY-001.md).

C2 replay IVI 대조 완료: TX/RX300318일치. 참조게시116건 모두 동일payload 공격원본+새 정상인증 결합, IVI게시일치. 과거인증 replay수락으로 집계하지 않는다. [보고서](../reports/ABLATION-FORMAL-C2-REPLAY-001.md).

## C2 spoofing ECU 수령

100회 VALID·exit0, 공격참조게시0, 정상참조전달2759/기대3000. IVI 대조 대기. [보고서](../reports/ABLATION-FORMAL-C2-SPOOF-001.md).

C2 spoofing 대조 완료: TX/RX289691 일치, 공통 인증게시5952 정상출처 확인·IVI전체5954. MAC_FAIL238은 위조pending+정상인증 결합. C2 네 공격 수집·대조 완료. [보고서](../reports/ABLATION-FORMAL-C2-SPOOF-001.md).

## C3 flooding 중단 / v7 송신 오류 처리

[중단 근거 및 보완](../reports/ABLATION-FORMAL-C3-FLOOD-001.md). 사용자 터미널 근거만 확보, 양측 archive 대조와 Pi 적용은 대기.

## C3 flooding 002 중단 / v8

[시간 만료·수신 시각 집계 보완](../reports/ABLATION-FORMAL-C3-FLOOD-002.md). Linux88개 통과, Pi 적용·원본 대조 대기. 기존 C3 전달률은 재분석 전 확정 보류.

## C3 flooding ECU 전체 수령

001~003 archive/manifest/raw 해시 확인, 시행1~100(98 VALID/2 INVALID) 보존. [003 ECU 검토](../reports/ABLATION-FORMAL-C3-FLOOD-003.md). 002 전달률1초과는 재분석 대상, 003 IDS 송신실패6건에도 완료. IVI 원본 대조 대기.

## C3 flooding 양측 원본 검토 완료

21H10M보존·inventory1309파일 해시 검증. 세 실행 TX/RX 증가량 일치, 공통 CAN 및 receiver일치. 송신경보64/2214/684건 모두 IVI도달. 003 Fuzzy683/Flooding1. 98 VALID/2 INVALID는 실행기 상태이며 002의 전달률 계측결함은 별도 보류. [003 최종 교차검토](../reports/ABLATION-FORMAL-C3-FLOOD-003.md). 다음 수집 대상 C3 fuzzy100회, 기존 원본/버전 구분 유지.

## C3 fuzzy ECU 수령

[ECU 검토](../reports/ABLATION-FORMAL-C3-FUZZY-001.md):100 VALID, 송신/echo276704일치, 송신오류0·qdisc증가0, 참조 정상전달3000/3000. IVI대조대기.

## C3 fuzzy 양측 검토 완료

[보고서](../reports/ABLATION-FORMAL-C3-FUZZY-001.md): TX/RX292233일치, 실제IDS경보3001도달·fuzzy주입경보2분리. Qt경고4원본보존, 화면미수집. 다음수집 C3 replay.

## C3 replay ECU 검토

[보고서](../reports/ABLATION-FORMAL-C3-REPLAY-001.md):100 VALID·송신오류0·own게시137건출처분리. IVI대조대기.

## C3 replay 교차검토 완료

[보고서](../reports/ABLATION-FORMAL-C3-REPLAY-001.md): TX/RX302236일치, IDS경보3041도달, 게시137원본출처구분. Qt경고25보존. 다음수집 C3 spoofing.

## C3 spoofing ECU 수령

[보고서](../reports/ABLATION-FORMAL-C3-SPOOF-001.md):100 VALID, 송신오류0·qdisc증가0·참조공격게시0. 마지막IVI대조대기.

## 마지막 C3 spoofing IVI 검토

[보고서](../reports/ABLATION-FORMAL-C3-SPOOF-001.md): IDS3033도달, 공통게시6120정상출처. IVIRX오류+1·위조프레임2부족 예외보존. 12조합수집·개별검토완료, 최종통합분석은남음.
