# 논문 결과 재현

## 입력과 분모

이 디렉토리의 `raw`, `inventory.json`, `publication-policy.json`을 입력으로 사용한다. 이전 분석 파일을 정답으로 복사하지 않고 ECU 원장/프레임과 IVI candump/receiver/IDS 경보를 다시 대조한다. 키를 읽거나 CAN 송신을 하지 않는다. Python 표준 라이브러리만 필요하다.

저장소 루트에서 **존재하지 않는 출력 폴더**를 지정한다.

```text
python -m security.experiments.publication --base docs/development/experiments/physical-ablation-formal-2026-10-04 --policy docs/development/experiments/physical-ablation-formal-2026-10-04/publication-policy.json --out tmp/publication-rebuilt
```

보존된 결과는 [publication](publication/TABLES.md)에 있다. `provenance.json`에는 입력 원본별 SHA256, 정책/분석기 해시, Python 버전을 기록한다. `outputs-sha256.json`으로 출력 파일 변조를 확인한다. 생성 도중 실패한 폴더는 완성본으로 취급하지 않는다. 원본·기존 출력은 덮어쓰지 않는다.

## 출력 구조

- `cases/C{1,2,3}-{flooding,fuzzy,replay,spoofing}/`: 12조건 각각의 전체 시도 원장과 요약.
- `runs/<run-id>/`: 16번 실행의 버전·입력 해시·계측 구간·ECU/IVI 대조·경보 출처·Qt 경고.
- `summary.json`: 전체 시도, 계획 번호 최초 시도, 재시도, 채택 가능한 지연 부분집합을 구분.
- `TABLES.md`, `DELIVERY.md`: 논문 작성에 사용할 표. `attempt-counts.tex`는 LaTeX 표 소스이며 컴파일된 PDF를 뜻하지 않는다.
- `publication-policy.json`: 시도 선택 정책과 C3 구버전 지연 제외 이유. 실험 결과를 보고 탐지 임계를 재조정하지 않는다.

## 해석 규칙

계획 번호별 **최초 시도**를 기본 표본으로 사용하고 INVALID도 남긴다. C1 flooding 7번 재시도는 별도 보조 증거다. 전체 1,201시도와 계획 번호 1,200개를 혼용하지 않는다. C3 구버전과 v8의 소스 세트 해시/시계가 다르므로 지연·전달률을 하나로 합치지 않는다.

지연은 탐지된 VALID에 조건부이고 p95는 nearest-rank다. 미탐지·INVALID에 0ms를 대입하지 않는다. C1/C2는 IDS 비활성이라 탐지율을 0%로 표시하지 않는다. 탐지된 경보가 주입 공격 유형과 다른 라벨인 경우 탐지 여부와 유형 분류를 구분한다.

IVI 출처 연결은 순서·payload·ECU own echo를 사용한 관측상 대응이다. 키를 이용한 인증 재검증이 아니다. 같은 payload가 반복되며 프레임이 빠진 경우 빠진 개수는 확인해도 동일 바이트의 개별 프레임 식별은 모호할 수 있다. 공격 구간 시작 1초 이내 부하 상승은 기존 내부 1초 부하 표본만으로 보증하지 않는다.

## 과거 분석기와 재현 범위

`tools/legacy-analysis`에 임시 경로에 남아 있던 분석기 38개를 원본 바이트와 해시로 보존했다. 경로 고정·inventory 변경 코드가 있어 이력 확인용이다. 현재 재현 명령은 위 명령을 사용한다. 과거 보고서 숫자와 현재 집계가 다르면 원본을 바꾸지 않고 분모·구간·버전 차이를 확인한다.

통합/성능/IF 평가는 [별도 증거](../ecu-ivi-integration-2026-10-03_04/README.md)의 보존 도구와 보고서를 따른다. 물리 키가 필요한 인증 평가와 미수집 화면은 이 오프라인 도구로 재실행하거나 복원할 수 없다. [TC별 해석](METHODS-AND-TRACEABILITY.md)을 함께 사용한다.
