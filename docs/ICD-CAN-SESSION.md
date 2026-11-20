# CAN 인증 세션 계약 — session-v2

2026-11-11 사용자 “추천한대로 해줘”로 상세 전환안의 제품 코드/문서 동시 전환을 승인했다. 본 문서는 [ICD](ICD.md)의 session-v2 프로파일 계약이다. legacy-v1과 자동 협상하거나 인증 실패 뒤 보안 OFF/구키로 복귀하지 않는다. 제품 연결/운영값/물리 장비 인수의 현재 상태는 CHG-029를 따른다.

## 1. ID와 기존 배치

|ID|방향|의미|DLC|
|---|---|---|---:|
|0x100/102|ECU→IVI|기존 BMS 원본/인증|8|
|0x101/103|ECU→IVI|기존 실제 전이 원본/인증|8|
|0x104/105|ECU→IVI|현재 위험 snapshot 원본/인증|8|
|0x200|ECU→IVI|기존 비인증 참고 경보. 안전 제어/인증 근거 아님|8|
|0x300|ECU→IVI|세션 REQUEST/OFFER/ACK|8|
|0x301|IVI→ECU|세션 CHALLENGE/CONFIRM/READY/RECEIPT|8|
|0x302/303|ECU→IVI/IVI→ECU|[인증 진단](ICD-CAN-DIAGNOSTIC.md)|8|

0x100~103의 바이트/스케일/엔디언과0x200 배치는 기존 ICD를 유지한다.0x100 byte7은 여전히 예약0이다. 센서 준비/오류는 인증된 NodeStatus로 전달하며 예약 바이트를 임의 재사용하지 않는다. 배터리·실제 전이·현재 상태의 인증 태그는4B, 세션 제어/진단은16B다.

## 2. 교환 제어 조각

byte0=`0x20|kind`,byte1=조각 번호0부터,byte2~3=transfer uint16 BE,byte4~7=본문4B. 모든 ID는 표준 데이터 프레임이다. 확장/RTR/error·DLC/버전/방향·번호 범위가 틀리면 받지 않는다.

|kind|본문|조각 수|
|---:|---|---:|
|0 REQUEST|0×4,transfer0|1|
|1 CHALLENGE|nonce_B16|4|
|2 OFFER|nonce_A16+tag_offer16|8|
|3 CONFIRM|tag_confirm16|4|
|4 ACK|tag_ack16|4|
|5 READY|tag_ready16|4|
|6 RECEIPT|현재 snapshot counter4 BE+tag_receipt16|5|

IVI가 교환마다 transfer와16B 난수를 선택한다. ECU는 새 교환에 새16B 난수로 답한다. transfer는 조립 식별자이며 보안 세션/재생 방지 식별자가 아니다. nonce는 운영 OS 암호학적 난수원이며 실패 시 대체값 없이 교환을 실패 처리한다. 시험에서만 공개 더미 공급자를 사용한다.

조립은 정해진 종류/transfer·최초 기산점에 고정한다. 같은 내용의 중복과 역순은 허용하고 같은 index의 다른 내용은 해당 조립을 폐기한다. 조각 성공만으로 인증 상태를 바꾸지 않는다. 단계/전체 교환·조립/재시도·완료 캐시·backoff·검증 횟수는 명시적 유한 설정이며 중복/오류/상태 변경이 기한/예산을 재충전하지 않는다. 수치의 운영 인수는 계측 후 수행한다.

## 3. 키·태그

공유키는32B이며 CAN으로 보내지 않는다. 문자열은 ASCII, NUL 없이 raw bytes로 결합한다.

```text
T = ASCII("CAPSTONE-CAN-SESSION") || 0x02 || 0x0300(BE2) || 0x0301(BE2)
    || transfer(BE2) || nonce_B16 || nonce_A16
PRK = HKDF-Extract-SHA256(nonce_B||nonce_A, SharedKey32)
K_role = HKDF-Expand-SHA256(PRK, ASCII(role)||T, 32)
role = offer / confirm / ack / data / ready / state-receipt / diag-ecu / diag-ivi
control_tag = HMAC-SHA256(K_role,T)[0:16]
data_MAC = HMAC-SHA256(K_data, original_CAN_ID(BE2)||counter(BE4)||payload8)[0:4]
receipt_tag = HMAC-SHA256(K_state-receipt,
                        T||0x0104(BE2)||state_counter(BE4)||state_payload8)[0:16]
session_id = SHA256(T)[0:16]  # 공개 교환 fingerprint, 키/키 해시가 아님
```

역할별 태그의 반사/이전 교환을 거부하며 constant-time 비교를 사용한다. 세션 키를 CAN/로그/checkpoint에 저장하지 않는다. 키 교체는 인증된 로컬 경계에서 한 번 수행하며 중복 확인이 counter/키를 초기화하지 않는다.16B 세션 태그가4B 데이터 MAC의 위조 저항을 늘린 것으로 설명하지 않는다.

## 4. 교환·현재 상태·송신 게이트

IVI CHALLENGE→ECU OFFER→IVI CONFIRM→ECU ACK→IVI READY→ECU 최신 STATE/인증→IVI 상태 반영/RECEIPT→ECU 일반 송신 순서다. ECU 먼저 시작 시 제한된 REQUEST로 IVI 교환을 요청한다.

새 미인증 교환과 기존 활성 세션을 분리한다. 인증 전에는 기존 유효 세션을 보존한다. ECU는 CONFIRM 검증, IVI는 ACK 검증에서 새 키·세대/큐로 전환한다. ECU는 그때 구세션 일반 송신을 닫고 READY 및 최신 상태 receipt 전까지 일반 송신을 보류한다. 인증 후 교환 실패에 구키/구번호로 돌아가지 않는다. 로컬 계산/보호 판단은 계속한다.

0x104:byte0=상태0~3,byte1=사유 존재0/1,byte2=사유,byte3~7=0. 사유 부재는byte2=0. 사유가 있으면 NORMAL=5/6,WARNING=1/3/7,CRITICAL=2,SHUTDOWN=4만 허용한다. 사유 부재에서 상태를 정상으로 추론하지 않는다. 초기 NORMAL의 사유는 없음이다. 기존0x101 Reason=0은 여전히 거부한다.

0x105는MAC4+counter4 BE다. snapshot은 실제 전이 콜백/알림을 새로 만들지 않는다. 현재 SOC/온도는0x100에서 받으며 과거 사건 값으로 꾸미지 않는다. STATE/RECEIPT 유실은 같은 건을 같은 번호로 제한 재시도한다. 확인 대기 중 실제 상태가 바뀌면 새 번호의 최신 snapshot으로 교체하고 예전 receipt로 송신을 열지 않는다. payload가 다시 같아져도 번호가 다른 별도 건이다.

receipt는 상태가 정렬 큐에서 반영된 뒤 생성한다. ACK/READY/상태 확인은 새 BMS 수신·입력 준비·배터리 정상 복귀의 증명이 아니다. 프로그램 복구와 실제 위험 정상 복귀는 분리한다. 일반 송신 재개 이후 실제 새 전이는0x101/103을 사용하며 매 전이마다 게이트를 다시 닫지 않는다.

## 5. 전역 counter·수신/반영

0x100/101/104는 세션 내 전역 uint32 순번을 공유하고 송신 쌍/번호 발급을 직렬화한다.0부터 시작하며0xFFFFFFFF 다음에는 래핑하지 않고 새 인증 세션이 필요하다. 최초 수신0~99,이후 마지막 반영 번호보다1~100 증가만 허용한다. 같은 세션에서 past/동일 번호는 재생이다. 진단 순번은 별도이며 이 번호를 소비하지 않는다.

MAC에 성공한 완성 쌍만 의미/창 검사를 거쳐 유한 정렬 큐에 넣는다. 첫 입장부터 제한 대기 후 번호순 반영하고 누락 번호를 무한 대기하지 않는다. 기한 정각에는 기존 batch 반영을 새 입력보다 먼저 처리한다. 늦은 작은 번호는 과거로 되돌리지 않는다. 중복은 기한을 늘리지 않는다.

일반 BMS 공간과 전이/현재 상태용 보호 공간을 구분한다. 일반 공간 포화는 새 BMS만 거부한다. 보호 공간 포화 또는 미반영된 같은 번호의 인증 상충은 수신 세션 실패로 처리하고 미반영 큐를 버리되 기존 표시/위험은 보존한다. 상태가 미수신됐다는 사실을 정상 상태 확인으로 바꾸지 않는다. 제한된 새 세션 수립으로 복구한다.

원본/auth 후보 수·쌍 기한·MAC 작업량도 유한 설정이다. 재생된 인증이 다음 동일 payload의 정상 원본을 소모하지 않게 한다. 미완성/모호한 짝을 특정 공격 차단 완료로 표시하지 않는다. 여러 원본이 같은 절단MAC에 일치하면 도착 순서로 골라 정상 처리하지 않는다.

원본 수신·인증 수신·검증 완료·정렬 후 반영 시각은 따로 기록한다. 실제 도착과 처리 대기 시각을 혼동하지 않는다. 정상 데이터 신선도는 새 유효 수신 번호의 실제 도착 시각이며 중복/실패/큐 flush로 연장하지 않는다. 전체 수신→화면 지연에 정렬 대기를 포함하고 기존 평균50ms/최대100ms 기준을 완화하지 않는다.

## 6. 운영·호환/인수

ECU/IVI/IDS·참조/실험 도구를 같은 프로파일로 배포한다. legacy-v1은 과거 실험 재현에 명시적으로 선택하며 자동fallback에 쓰지 않는다. 세션 변경 시 예전 키/수신 후보/정렬 큐를 섞지 않는다. 배선 단절은 연결 대기/복구이며 그 사실만으로 ECU 프로그램을 재시작하지 않는다.

프로그램 재시작 예고/ACK는 [인증 진단 계약](ICD-CAN-DIAGNOSTIC.md)을 따른다. ACK가 없어도 제한 대기 뒤 진행하되 실제 시도 기록/이전 프로세스 회수가 필요하다. 첫 부팅 의도, checkpoint/운영 시간값, 물리 CAN·UI/프로세스 인수는 문서 승인만으로 완료되지 않는다. 공격 노드의 버스 송신을 막거나 모든 DoS/키 유출을 해결하는 계약이 아니다.

## 7. IVI C++ Service/transport 확장

기존 ICD §3의 legacy API와 구분하는 session-v2 확장이다. `Clock`은 같은 호스트의 `steady_clock`이다. 아래 실제 선언은 `ivi_platform/service/vehicle_data_service.h`, frame/정책 선언은 `common/`을 따른다.

|API|계약|
|---|---|
|`enableSession(SecOcKey, ExchangeLimits, now)`|시작 때 한 번만 선택한다. 이미 session 또는 legacy key가 있으면 false. 유한 설정/시각이 잘못되면 예외. transport 복구나 UI 동작으로 이 API를 재호출해 번호를 초기화하지 않는다.|
|`processSessionFrame(Frame, received_at, now)`|프레임/실제 수신 시각을 넘긴다. 기본 처리 시각은 서비스 소유 lock을 얻은 뒤 읽으며 오래된 수신 시각과 혼동하지 않는다. 시험에서만 명시적인 동일 시계 기준 now를 주입한다.|
|`pollSession(now)`|프레임이 없는 동안에도 단계·정렬·재연결 기한을 진행한다. 수신 공백은 counter reset이나 ECU 프로세스 재시작 사유가 아니다.|
|`SessionServiceResult`|`result`(Ignored/Pending/Published/Rejected)와 `outgoing`(양방향 제어/진단 프레임)을 반환한다. 호출자가 실제 송신 결과를 처리한다. 반환/커널 송신 수락은 상대 수신 확인이 아니다.|
|기존 `processFrame`/`setSecOcKey`|session-v2를 선택한 서비스는 legacy 처리로 우회하지 않는다. `processFrame`은 Ignored, legacy key 재설정은 오류다.|
|`SocketCanReceiver::sendControl(id,payload8)`|IVI→ECU0x301/303만 전송한다. 닫힌 socket/잘못된 방향/비차단 송신 실패는 false. 숨은 retry나 번호 rollback을 하지 않는다.|

서비스 snapshot은 기존 값에 다음을 추가한다.

|필드|의미|
|---|---|
|`session_protocol`, `session_generation`|선택한 프로파일과 현재 로컬 인증 세대. 세대는 wire 세션 식별값이나 ECU 재시작 횟수와 다르다.|
|`connection_stage`|waiting/authenticating/synchronizing/waiting-data/connected/fault. 인증/상태 확인만으로 connected가 되지 않으며 새 정상 BMS가 필요하다.|
|`session_bms_ready`|현재 세션에서 정상 BMS를 반영했는지. 새 세대/수신 세션 실패 시 false. 마지막 표시값/위험 상태는 보존한다.|
|`fail_safe_known`|인증된 전이/현재 snapshot으로 위험 상태를 확인했는지. 단순 BMS 수신은 확인 근거가 아니다.|
|`authenticated_diagnostic`, `diagnostic_revision`|새로 검증한 진단과 로컬 갱신 번호. 동일 인증 중복은 새 상태/신선도 갱신이 아니며 제한된 receipt 재응답만 허용한다.|
|`last_rejection_message`|마지막 검증 거부/만료 원인을 후속 정상 게시 메시지와 분리해 보존한다. 단순 만료/불완전 쌍을 MAC_FAIL/특정 공격 차단으로 바꾸지 않는다.|
|`security_observation_ready`|필요한 IDS 관찰 품질/지속 상태를 확인했는지. 세션 수립/BMS 수신만으로 true가 아니며 연결 전은 확인 중으로 표시한다.|
|`snapshot_revision`|통지할 때 소유 lock 안에서 증가하는 로컬 번호. Qt에 늦게 도착한 이전 통지가 최신 값/위험을 되돌리지 못하게 한다. wire 순번과 다르다.|

`t1_received_ns`는 실제 원본 수신 시각의 ns 값을 보존한다. 정렬/검증 때문에 처리 시각으로 덮지 않는다. `t2_published_ns`는 검증·정렬·반영 뒤 서비스에서 읽고 T3/UI 시각과 구분한다. 보호 상태 snapshot은 측정 sequence를 증가시키거나 새 센서값 수신을 꾸미지 않는다. 새 세션과 연결 복구는 배터리 정상 복귀를 뜻하지 않는다.

NodeStatus의 입력 품질은 snapshot.sensor_state로 전달하지만 기존0x100 byte7을 바꾼 것으로 해석하지 않는다. 사건/거부 귀속·관찰 상태 controller와 전체 복구 단계/장기 이력의 실제 연결은 CHG-029 인수 증거로 별도 판단한다.
