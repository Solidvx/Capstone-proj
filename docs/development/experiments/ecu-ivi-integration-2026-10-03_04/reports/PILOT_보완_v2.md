# 물리 pilot 후속 보완 v2

## 완료 범위와 남은 조건

Config 1·2 물리 pilot 대조 후 사용자가 송신률 부족·IF 오탐 개선을 승인했다. 기존 원본 로그와 결과는 변경하지 않았다. 이번 변경은 미커밋 작업트리 소스이며 이전 8a57f7f 전달본과 동일하지 않다.

| 문제 | 변경 | 검증과 한계 |
|---|---|---|
| 목표 1000fps 대비 약 500fps, flooding 부하 13% | socket timeout 대신 select의 sub-ms 수신 대기 사용. 송신·로그 처리 시간을 다음 간격 안에 포함. 늦은 스케줄의 따라잡기 burst 없음 | 모의 시계 회귀 통과. 실제 RPi 처리량·50% 부하 달성은 미확인 |
| IF 학습과 실행 특징 분포 차이 | 정상 학습 벡터를 RuntimeDetector와 같은 프레임 처리·만료 경계로 생성, 평가와 동일한 50ms timer tick 재현 | 학습/평가 벡터 일치 회귀 통과. 실제 live 이벤트 시각·지터 차이는 여전히 물리 검증 필요 |
| 기본 IF contamination 5%만으로 FPR 보장 불가 | 별도 정상 보정 세트에서 이상 점수 순위 ceil((n+1)×0.99)로 임계 설정. 최종 평가 자료는 임계 설정에 사용하지 않음 | 보정 표본 최소 99개 필요, 운영 절차는 300초 수집. 1%는 보정 정책이며 실측 보장 아님 |
| 합성 자료를 물리 준비로 오인할 위험 | physical IF 실행에 --calibrate 필수. fit/calibration/evaluation 동일 내용 및 환경 혼합 거부 | 물리 정상 학습·보정·평가 3회가 별도로 필요 |

ICD·규칙 임계·송신률 상한 5000fps·시간 상한·격리 버스 확인은 유지했다. IF의 wire score 매핑도 유지하며, 모델 판단에서 보정 임계를 뺀다. IF 단독 이상은 기존대로 비귀속 로그이고 ICD 공격 종류를 임의로 만들어 송신하지 않는다.

## 독립 합성 평가

[결과 JSON](../analysis/pilot-readiness-v2-synthetic.json), [재현 스크립트](../tools/validate_pilot_readiness.py).

각 300초. fit seed 9001, calibration seed 9002, evaluation seeds 9003~9005. 보정 297벡터, 순위 296, 임계 0.10238147831723865. 명시적인 합성 더미 키로 SecOC를 생성하고 평가했다. 원래 16/108 결과는 다른 자료·설정의 과거 결과로 보존하며 같은 실험의 직접 전후 수치로 주장하지 않는다.

| 독립 평가 | 오탐 창/완전한 창 | 오탐률 |
|---|---|---|
| 9003 | 4/298 | 1.34% |
| 9004 | 0/298 | 0% |
| 9005 | 1/298 | 0.34% |

모두 정상 오탐 5% 조건에 들었다. 보정 후 명백한 이상 특징 벡터가 양의 anomaly를 내는 회귀도 추가했다. 이는 실제 4공격 탐지율 검증을 대신하지 않는다. 로컬 WSL은 vcan0가 없고 vcan 인터페이스 생성도 Unknown device type으로 실패했다. 그러므로 이번 소스의 실제 SocketCAN 송수신 검증은 ECU에서 수행한다.

## 전달과 다음 실행 순서

패키지: 저장소 루트 tmp/pilot-readiness-v2-handoff/pilot-readiness-v2.tar.gz. 포함된 HANDOFF-MANIFEST.json은 기준 HEAD, WORKTREE-SNAPSHOT-NOT-COMMIT 표기 및 개별 파일 SHA256을 제공한다. 기존 ECU 디렉토리는 보존하고 새 ~/ablation-readiness-v2에 압축을 푼다. 기존 가상환경을 그대로 참조할 수 있다.

```bash
mkdir ~/ablation-readiness-v2
tar -xzf ~/pilot-readiness-v2.tar.gz -C ~/ablation-readiness-v2
cd ~/ablation-readiness-v2
~/ablation-8a57f7f/.venv/bin/python -m pytest security/tests -q
cmake -S adaptive_ecu -B adaptive_ecu/build -DECU_BUILD_TESTS=ON
cmake --build adaptive_ecu/build -j2
ctest --test-dir adaptive_ecu/build --output-on-failure
```

이후 순서는 아래와 같다. 동시에 여러 송신기를 실행하지 않는다.

1. ECU의 vcan0에서 수정 실행기 Config 2 및 Config 3 규칙 전용 pilot을 확인한다. IF 인수는 아래 물리 정상 자료 평가로 별도 수행한다. 아직 물리 버스에 새 소스를 투입하지 않는다.
2. 물리 정상 인증 송신을 유지한 동안 수신 전용 can_capture로 fit/calibration/evaluation을 각각 300초 수집한다. 세 폴더 모두 --normal을 명시하고 새 폴더를 사용한다. 실제 실행 시간을 충분히 확보하며 중간 ECU 재시작을 섞지 않는다.
3. 독립 evaluation에 evaluate_normal을 실행한다. rules+IF 5% 이하, 최소 100창, 빈 창 0을 확인한다. 실패 결과를 삭제하거나 평가 자료로 임계를 재조정하지 않는다.
4. IVI 새 ON 인스턴스와 candump·canbusload가 준비되면 flooding 1회만 rate 3000, duration 3으로 부하 확인한다. 3000은 후보 설정이며 부하 보장이 아니다. 큐 오류·드롭·정상 baseline 실패 시 유효 시험으로 세지 않는다. IVI 종료·수집 구간도 대조한다.
5. 부하 조건 충족과 정상 IF 평가를 확인한 뒤 Config 3 규칙+IF 4종 각 1회 및 IVI 경보를 검증한다. 최종 동일 부하·IDS 설정으로 공식 세 구성 각 100회를 새 run으로 실행한다. 기존 pilot 결과를 공식 표본으로 섞지 않는다.

정상 캡처 한 회의 명령 형식(ECU의 별도 SSH 창, 송신이 먼저 동작 중이어야 함):

```bash
~/ablation-8a57f7f/.venv/bin/python -m security.experiments.can_capture --channel can0 --environment physical --duration 300 --normal --out results/normal-fit-v2
```

같은 방식으로 별도 구간을 normal-calibration-v2, normal-evaluation-v2에 수집한다. 평가 명령:

```bash
sudo ~/ablation-8a57f7f/.venv/bin/python -m security.experiments.evaluate_normal results/normal-evaluation-v2 --train results/normal-fit-v2 --calibrate results/normal-calibration-v2 --key /etc/secoc/key.bin --out results/normal-evaluation-v2-report.json
```

Config 3의 실행기에는 --train results/normal-fit-v2 --calibrate results/normal-calibration-v2를 전달한다. --rules-only는 IF 인수 완료를 뜻하지 않는다. 물리 시험은 사용자·IVI 담당자의 READY 확인 후 단계별로 시작한다.
