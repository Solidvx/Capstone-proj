# LOAD 진단 v3 인계

## 수정과 검증

LOAD-CHECK-V2-001의 send OSError 1,871건을 원인 분석할 수 있도록 errno를 원시 로그에 추가했다. 송신 일부가 성공해도 오류가 있으면 TX_ERRORS로 INVALID 판정한다. 기존 성공 건수·자기 echo·오류 원본은 보존한다. 부하율 또는 송신 상한을 올리지 않았다.

test_live_experiments.py 18 passed, 전체 security/tests 59 passed(WSL 8.79s). 부분 성공+실패의 무효 처리와 errno 105 보존을 검증했다. errno 105는 테스트 입력이며 실제 장비 오류 원인이 확인됐다는 뜻이 아니다.

패키지: tmp/load-diagnostic-v3/load-diagnostic-v3.tar.gz, v2 위에 적용하는 3파일 overlay. SHA256:

```text
7a1f4955c6db3008fd4e76104b7881adf1c4bf62bb3c17c490c3935a03fbbff3
```

## 적용

사용자가 패키지를 ECU 홈으로 전달한 뒤 실행한다. 송신기는 중지된 상태여야 한다. 백업 폴더가 이미 있으면 멈추며 기존 자료를 덮어쓰지 않는다.

```bash
cd ~/ablation-readiness-v2
sha256sum ~/load-diagnostic-v3.tar.gz
```

위 해시가 일치할 때만 다음 블록을 실행한다. 실패하면 뒤 명령은 실행되지 않는다.

```bash
mkdir backup-before-v3 &&
cp --parents security/experiments/live_trial.py security/experiments/live_ablation.py security/tests/test_live_experiments.py backup-before-v3/ &&
tar -xzf ~/load-diagnostic-v3.tar.gz &&
~/ablation-8a57f7f/.venv/bin/python -m pytest security/tests -q
```

ECU C++ 소스·바이너리는 바뀌지 않아 재빌드 불필요. 기존 results와 정상 fit/calibration/evaluation은 유지한다. 최종 source는 v2 + 진단 v3이며 이전 v2와 동일 버전으로 표시하지 않는다.

## 다음 물리 확인

IVI 새 인증 ON 인스턴스·candump·canbusload 준비 후 LOAD-DIAG-V3-001의 새 결과 폴더에서 config 2, flooding만 1회, rate 3000, duration 3으로 이전과 같은 조건을 재현한다. 물리 장비 실행은 사용자 담당이며 아직 실행하지 않았다. 오류가 재발하면 INVALID·exit 2가 올바른 결과다. errno별 수량, 실제 송신·자기 echo, 양측 CAN 통계, 점유율을 대조한 뒤 송신 큐·드라이버·장비 처리량 중 다음 조사 대상을 정한다. errno만으로 최종 하드웨어 병목을 확정하지 않는다.

반복을 무작정 늘리지 않는다. 이번 한 번은 기존 로그에서 누락된 오류 종류를 얻기 위한 진단이다. 정상 IF 평가를 반복할 필요는 없다. Config 3 및 본 실험은 공식 부하 조건이 충족된 뒤 진행한다. 부하 조건이 장비 한계로 불가능하다면 기준을 몰래 낮추지 않고 사용자에게 근거와 선택지를 제시한다.
