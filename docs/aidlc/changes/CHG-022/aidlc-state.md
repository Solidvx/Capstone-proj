# CHG-022 상태 — 2026-10-21

소스 구현·로컬 검증 완료, 물리 조립·장비 파일럿 인수 대기. [요청](spec.md), [회로·실험 안내](../../../development/playbooks/three-node-hardware-experiment.md), [검증 증거](evidence.md).

- 시작 브랜치 feat/ecu-recovery-quality, HEAD 5b7e7ed. 시작부터 있던 dirty·미추적 변경을 보존했다. 커밋·push·전체 브랜치 병합은 하지 않았다.
- GitHub fetch 완료: origin/develop **76b56f4**(PR #26). 읽기용 스냅샷 `tmp/chg022-develop/`에 가져온 뒤 최신 ECU ADC capture·Fail-safe profile/시험과 보안 실험·IDS 관련 파일을 현재 작업본에 선별 반영했다. 기존 CMake 변경을 보존하고 대상만 추가했다.
- 최신 runtime의 커널 수신 시각·backpressure 처리·독립 IF 보정을 사용한다. 이전 고정 fixture와 제품 ECU 기반 live 경로를 구분한다.
- IDS·IVI 유형 번호/이름은 이미 일치했다. 미정의 Fail-safe reason=0 허용 차이를 IVI·Python 참조 수신기에서 수정했다. ICD 바이트·ID·API 변경 없음.
- `live_three_node`가 공격 Pi3에서 A의 제품 ECU/IDS, B의 실험 수신기를 소유·종료하며 12조건×100번호를 실행한다. 기대 유형·첫 유형·다중 유형·IVI 서비스 게시를 구분한다. 참조 방어 판정과 실제 IVI 판정을 동일시하지 않는다.
- 검증: ECU CTest 18/18, IVI core CTest 9/9. 최종 Python 전체 142 통과/3 Linux 조건 생략. 원격 성공·실패·로그 hash 검증·최종 게이트·신호 핸들러 복원을 포함한다. 상세 명령과 범위는 evidence 참조.
- 남은 장비 작업: E3P 실물 방향/연속성, 새 ADC 끝점·CAN 통신·SSH/sudo/원격 종료·Linux SocketCAN echo·Qt 화면 확인, 새 물리 12회 pilot 및 1,200회. 이 macOS에는 장비 연결과 Linux CAN이 없어 미실행이다. 새 스크립트의 실제 장비 준비 완료나 물리 합격을 주장하지 않는다.

## 2026-10-22 PR 준비 후속 상태

사용자가 커밋·push·PR 생성을 요청했다. 원래 dirty 작업본을 보존하고 최신 origin/develop 76b56f4에서 feat/three-node-campaign을 분리해 이번 변경만 이관한다. 기존 develop에 이미 있는 ECU 동기화 파일을 중복 반입하지 않는다. 사용자 screenshot에서 세 노드 상호 단발 0x123 송수신과 오류0을 확인했다. Pi3 최초 소스 배포 및 원격 실험은 아직 미실행이며 [설치 안내](../../../development/playbooks/attack-pi3-install.md)를 추가했다.

## 테스트360회 후속 작업

공식 실행을 보존한 별도 live_three_node_test360 스크립트와 시험·재현 안내를 추가했다. 관련36통과/1Linux생략. 실제 원격360회 실행은 미실시이며 원격 설정과 자료 준비가 필요하다.

## 테스트360 복구·재개 후속 작업

시험 목적에 맞춰 유형 불일치/미탐/개별 INVALID 계속, 제한 복구, 실패 attempt 보존, 완료 번호 재개 제외를 구현했다. ECU·IVI 수신 관찰과 종료 ACK를 추가했으며 테스트 전용 설정/HTML 절차를 갱신했다. 관련70통과/2Linux생략. 실제3노드에서 같은 버전 업데이트와 권한 준비 후 동작 인수가 필요하다.
# 연속 실행 전환 후속 — 2026-10-22

사용자 요청에 따라 구성·공격 조합별 30회 연속 실행으로 전환했다. 정상 360회는 12세션으로 실행하며 오류 시 완료 번호를 보존하고 실패 번호부터 제한 복구한다. 회차별 관찰기 ACK·수신·드롭 증거를 분리하고 모든 완료 행의 IVI 로그를 종료 후 확정한다. schema=test360-v3-continuous로 이전 독립 실행 결과와 재개를 혼합하지 않는다. 관련 pytest 74통과/2Linux생략. 실제 장비 실행은 미실행이다.

## PC 진행 전환 상태 — 2026-10-22

최신 origin/develop 0b99070에서 feat/pc-campaign 작업을 분리했다. pc_campaign이 PC에서 모든 원격 역할을 관리하며 can_attack_worker는 Pi3에서 키 없이 실제 SocketCAN 송신만 한다. replay는 관찰 raw/auth 쌍을 검증 없이 복사하고, 실제 인증은 ECU·IVI에 남긴다. IVI 게시와 ECU IDS 송신 로그를 대조하며 이전 공격자 참조 차단율·성공률·지연을 추정하지 않는다. 원본 IDS 로그까지 PC 결과 폴더에 수집한다.

SSH 선별 정리 도구는 기본 preview, --apply일 때만 해당 Pi3 키 권한과 파일을 제거한다. PC의 독립 키로 세 노드 접근을 검증하며 기존 authorized_keys를 백업한다. 관련91통과/2Linux생략. 실제 장비 실험·키 삭제는 수행하지 않았다. PC 접속·설정 파일·원격 권한·pilot 확인이 남아 있다. 변경 전후 Python3.9에서 동일한 기존 publication/file_digest 실패가 재현되며 이번 범위 밖으로 유지한다. 자세한 검증은 evidence와 PC 안내 참조.

## 분리 유형 물리360회 후속

isolated-v1 물리360회는 360 VALID, C3 네 공격 각30회 ECU/IVI MATCH로 완료.
PC 진행/키 없는 Pi3/CAN 공격 역할을 유지한다. 실제 화면·정상 오탐률·차단율은 별도 미검증.
원본 혼합 공격은 유지하며 분리 조건과 IDS 근거 규칙을 추가했다.
복구 소진 시 다음 조합 진행은 단위 시험 완료, 물리 오류 복구는 미검증.
