# RPi Ablation 준비 및 실행 기록

근거 구분: 아래 빌드·설치 결과는 사용자가 대화에 전달한 터미널 출력이다. vcan 실행 원장·manifest·패키지 목록은 별도 원본 파일로 수령했다. 터미널 원문 파일까지 수령했다고 주장하지 않는다.

## 현재 실행 환경 (이하 기존 명령은 과거 이력)

현재 ECU 작업 위치는 ~/ablation-readiness-v2이며 v2에 load-diagnostic-v3 및 ids-timestamp-v4를 적용했다. Python은 ~/ablation-8a57f7f/.venv/bin/python을 재사용한다. 사용자 출력 기준 RPi Python66개 통과, CTest17개는 C++ 변경 전 해당 빌드 증거다. runtime.py 적용해시는 PHYSICAL-PILOT-IF-002 manifest와 대조했다.

ECU SPI2MHz·IVI SPI1MHz·CAN500kbps·ECU qlen10. 부하 조건은 요청2800fps·공격3초·baseline2초·post1초를 Config2 1회에서 검증했다. 공식1,200회는 미실행이며 다른 공격/구성에 대한 적용률과 결과 판정은 구분한다. Config3은 기존 fit/calibration 자료를 사용하며 IF 정상구간1건 이상 및 단독공격탐지 미입증이 남아 있다.

최신 결과와 실패 이력은 [대표 목차](../README.md)의 최신 전체 위치와 시행착오 요약을 따른다. 공식실행 시 새run ID와 디렉토리, 시행별 부하·송신오류·IVI 증거를 보존한다.

## 버전과 환경 (초기 이력)

- ECU 기존 통합시험 소스: develop 9568d907d1c57271a19eb986b23638b5eec70c1a.
- 새 실행기: 8a57f7f의 git archive, ECU의 별도 `~/ablation-8a57f7f`에 압축 해제. 기존 작업 폴더를 덮어쓰지 않음.
- 전달 압축파일 SHA256: b4ab7f8b39f2eda5abc0f18e54d3a85613fd9feafcabf3f8240f3702149881d3. 사용자가 ECU에서 일치 확인.
- RPi aarch64, Python 3.13.5. CMake 출력의 GCC 12.4.0, OpenSSL 3.5.6, GTest 1.15.0.
- CTest 17/17 통과. 시스템 Python pytest는 sklearn 미설치로 54통과/1실패. 전용 .venv에 requirements 설치 후 55/55 통과(24.49초).
- vcan0 활성화 확인. 이 단계에서 물리 can0로 실험 송신하지 않음.
- 설치 패키지 원본: `../raw/VCAN-PILOT-001/results/pilot-python-packages.txt`.

## 실행한 준비 명령

```bash
cd ~/ablation-8a57f7f
cmake -S adaptive_ecu -B adaptive_ecu/build -DECU_BUILD_TESTS=ON
cmake --build adaptive_ecu/build -j2
ctest --test-dir adaptive_ecu/build --output-on-failure
python3 -m venv .venv
.venv/bin/python -m pip install -r security/requirements.txt
.venv/bin/python -m pytest security/tests -q
```

## vcan pilot 실행

각 구성에서 공식 공격 4종을 각 1회, 공격 구간 3초, 요청 rate 1000fps로 실행했다. 기본 baseline 2초·post 1초, 센서 constant다. 실측 송신 건수와 설정 rate를 구분한다. 하네스가 소유한 ECU/IDS 프로세스를 시작·회수하며 IVI 제품은 이 pilot에 참여하지 않는다.

```bash
.venv/bin/python -m security.experiments.live_ablation --channel vcan0 --environment vcan --config 1 --trials 1 --rate 1000 --duration 3 --ecu adaptive_ecu/build/adaptive_ecu --run-id VCAN-PILOT-001 --out results/vcan-pilot-001-c1
sudo .venv/bin/python -m security.experiments.live_ablation --channel vcan0 --environment vcan --config 2 --trials 1 --rate 1000 --duration 3 --key /etc/secoc/key.bin --ecu adaptive_ecu/build/adaptive_ecu --run-id VCAN-PILOT-001 --out results/vcan-pilot-001-c2
sudo .venv/bin/python -m security.experiments.live_ablation --channel vcan0 --environment vcan --config 3 --rules-only --trials 1 --rate 1000 --duration 3 --key /etc/secoc/key.bin --ecu adaptive_ecu/build/adaptive_ecu --run-id VCAN-PILOT-001 --out results/vcan-pilot-001-c3
```

위 명령은 수행 이력이다. 재실행 시 새 run-id·출력 폴더를 사용한다. 키 내용·해시는 보존하지 않는다. Config 3 rules-only는 pilot 범위이며 IF 학습·오탐 검증을 대신하지 않는다.

결과와 replay 관측 한계는 [pilot 보고서](VCAN-PILOT-001_결과.md)에 기록했다. 후속 물리 시행은 [공식 실행 플레이북](../../../playbooks/live-security-validation.md)의 pilot·버스 점유율·IVI 증거 인수 조건을 따른다.
