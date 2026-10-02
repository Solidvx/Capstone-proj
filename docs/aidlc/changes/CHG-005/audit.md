# CHG-005 검증

## 2026-09-25 — 시각적 핀 매핑 중심 재구성

사용자의 후속 요청에 따라 `컨버터O_배선완결판.html`의 어두운 배경·부품별 박스·색상별 신호 경로를 참고해 기존 연결 HTML을 재구성했다. 기존 파일은 `tmp/wiring_visual_20260925/before.html`에 보존했다. 검토 보고를 HTML에 넣지 않았으며 제품 코드·ICD·배선 원본은 변경하지 않았다.

- 전체 센서→ECU→LC→MCP→CAN→IVI→DSI 화면 경로, 센서 핀 배선, A/B SPI·INT, A/B 전원 분기, LC 실크, MCP 실크, 화면 연결, 노드 간 CAN의 **SVG 10개**를 작성했다. 전체 그림은 정보 흐름 요약이고 세부 그림은 실제 외부 선과 컨버터 내부를 구분한다.
- **표 11개**로 두 40핀 헤더, 센서, 신호, 전원, 모듈 단자, 화면, CAN 등을 연결한다. A/B 헤더 표의 80개 물리 핀과 기존 목적지 문자열을 보존했다. GPIO는 BCM 기준이며 전원/GND는 BCM 번호가 없음을 표시한다.
- 신호별 배선 ID·색상을 그림과 표에서 일치시켰다. 신호 강조 버튼, 구간 이동, 인쇄 스타일을 추가했다. 설명과 연결 조건은 해당 그림·표 아래에 배치하고 상단에는 통전 조건으로 이동하는 짧은 안내를 유지했다. 마지막 본문은 그림 6 CAN 구간이다.
- 기존 LC 모델/SPI 적합성 미확인, 단락·전압·납땜·역급전·전원 분리, Touch Display의 Pin 2/6 분배 조건, I²C 실제 취득 미구현과 실물 통합 미검증 범위를 유지했다. 화면 디자인 변경은 전기적 검증 완료를 의미하지 않는다.

검증:

1. `python -X utf8 tmp/check_wiring_visual.py` 통과: HTML 중첩·ID·링크, SVG XML 10개, 기존 80핀 표 보존, A/B 신호 10경로의 Pin/BCM/LC/채널/MCP 대응과 실제 화살표 방향, 전원·센서·화면·통전 조건, 그림 6 최종 구간.
2. `node --check tmp/wiring_visual_20260925/interaction.js` 통과. JavaScript 구문 검사이며 브라우저 클릭 시험은 아니다.
3. `python -X utf8 tmp/render_wiring_visual.py`로 SVG 10개를 PyMuPDF에서 PNG로 렌더링했다. 주요 도식을 직접 확인하고 LC 글자 겹침, MCP 방향 표기, 디스플레이 GND 선과 라벨 정렬을 수정했다. 센서 ADDR→GND 분기도 선으로 표시했다. 결과는 `tmp/wiring_visual_20260925/render/`에 있다.
4. `git diff --check` 통과. 저장소 docs/plan에 기존 HTML의 세부 앵커를 직접 참조하는 Markdown 링크는 발견하지 못했다.
5. 브라우저 연결은 `Browser is not available: iab`로 실패했다. HTML 전체 레이아웃·모바일·인쇄·강조 버튼의 실제 브라우저 실행은 미검증이다. SVG 렌더는 브라우저 전체 렌더를 대신하지 않는다. 실물 시험은 수행하지 않았다.

최종 HTML SHA-256: `1d9e9bfd2bdeab3bfc14429f1810b67221787a7ed1a31cafc8685a69f4e203c0`.

## 2026-09-25 — 재검토 및 조립 안내 보완

요청 범위는 기존 HTML의 전기적 안전 조건과 프로젝트 연결 경로 검토·보완이다. `chore/ecu-m1-baseline`의 제품 코드와 미커밋 HTML을 확인했다. 이전 수정과 별개로 현재 파일·사진·공식 자료를 다시 대조했다. 검토 보고는 이 파일에 두고 HTML에는 실제 조립 시 필요한 조건과 경로만 반영했다. 기존 사용자 변경·배선 원본·ICD·제품 코드는 수정하지 않았다.

### 발견 사항과 반영

| 중요도 | 확인한 문제/제한 | HTML 반영 |
|---|---|---|
| 높음 | 보유 LC의 사진에는 HV/LV·채널·103 저항·3단자 소자가 보이나 정확한 모델/회로/정격은 불명확하다. 유사 MOSFET I²C 변환 회로 자료를 이 보드의 SPI 적합성 증거로 사용할 수 없다. | 미확인 LC의 GPIO 연결·통전 보류를 경로 앞에 명시. SPI 입력 3개/출력 1개, 별도 INT의 방향, 부팅/전원 차단, 속도·파형 조건을 추가. 사용자에게 제품명/구매 링크를 요청했으며 현재 미응답. 대체 부품을 확정·구매한 것으로 기록하지 않는다. |
| 높음 | ADS1115 헤더는 사진상 분리돼 있다. 브레드보드 레일·납땜 상태·Pi 방향은 도식만으로 검사할 수 없다. | 헤더 납땜·핀 밀림·5공 묶음·레일 분리·무전원 단락 검사와 전압계 리드/모드 안내를 연결 경로 앞에 추가. 단락 판정에 임의의 보편 저항값을 제시하지 않음. |
| 높음 | 화면까지의 안내에 보유 7인치 Touch Display 2 연결이 빠져 있었다. 기본 전원 하우징은 Pin 2·4·6 자리를 차지하며 2·6이 CAN 전원과 중복된다. | Node B에 1:1 GPIO 분배/패스스루 부품을 추가 준비하는 조건으로 Pin 2 빨강 5V, Pin 6 검정 GND, RPi4 DISPLAY의 15핀↔15핀 FFC 매핑을 추가. 커넥터 겹쳐 끼우기 금지, 디스플레이 전원 J1과 MCP 종단 J1 구분, 정격/전체 부하 확인. 기본 CAN 핀은 변경하지 않았다. |
| 중간 | H–L 약 60Ω만으로 전체 회로가 안전하다고 오해할 수 있다. | 종단 확인과 전원 단락 검사를 구분. J3에 쇼트 점퍼 금지, 세 번째 노드가 붙어도 종단은 두 개만 유지. |
| 기능 | 현재 기본 코드의 ADS1115 모드는 저장된 `adc_data_`를 반환한다. 배선만으로 실제 ADC→Qt 갱신이 완성되지 않는다. | 실제 I²C 취득/main 결합, I²C1/0x48/A0, SPI0/CE0/GPIO25, 크리스털 실물별 확인과 양쪽 CAN 500000 bit/s 조건을 경로에 연결. 물리 양방향 CAN과 ICD 애플리케이션 메시지 구현을 구분. |

### 근거

- 실물: `하드웨어 정보/`의 MCP2515·ADS1115·가변저항·컨버터 앞뒤·디스플레이 라벨 사진. MCP 크리스털 `8.000`, 모듈 J1/J3, 디스플레이 7인치 Touch Display 2 확인. 회로도·실측은 확보하지 못했다.
- [Raspberry Pi GPIO](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#gpio-and-the-40-pin-header): 물리 핀과 BCM 구분, 3.3V GPIO. 기존 40핀 표와 SPI/I²C 대응 대조.
- [Microchip MCP2515 DS20001801J](https://ww1.microchip.com/downloads/en/DeviceDoc/MCP2515-Stand-Alone-CAN-Controller-with-SPI-20001801J.pdf), Table 13-1: SCK/CS/SI의 VIH 최소 0.7VDD, SO·INT의 출력 전압 조건. 5V 구동의 입력 HIGH 보장값은 3.5V이므로 Pi 3.3V 직결을 보장할 수 없고 SO/INT도 보호 없이 직결하지 않는다. K판 주소는 이번 조회에서 실패하여 접근 가능한 제조사 J판을 확인했다.
- [NXP TJA1050](https://www.nxp.com/docs/en/data-sheet/TJA1050.pdf): 정상 공급 4.75~5.25V. 트랜시버 자체 보호 기능을 모듈 전체/브레드보드 보호로 확대하지 않는다.
- [Nexperia AN10441](https://assets.nexperia.com/documents/application-note/AN10441.pdf): MOSFET 기반 I²C 레벨 변환의 적용 범위. 보유품과 유사해 보인다는 것은 추론이며 칩 모델/회로 동일성을 확정하지 않았다.
- [TI ADS1115](https://www.ti.com/lit/ds/symlink/ads1115.pdf): 입력 GND~VDD, PGA 범위와 실제 입력 한계의 구분, 미사용 AIN/ALRT 처리. 기존 A1/A2/A3/ALRT 무연결은 유지 가능. 보호 다이오드의 절대 최대치를 정상 사용 기준으로 쓰지 않는다.
- [Touch Display 2 공식 조립](https://www.raspberrypi.com/documentation/accessories/touch-display-2.html#connect-to-a-5-inch-or-7-inch-touch-display-2): 7인치/RPi4의 15핀↔15핀 FFC, 접점 방향, Pin 2/6 전원. 추가 분배는 기존 CAN 배선과 동시에 쓰기 위한 문서상 구성 조건이며 실물 보유·정격 확인 전이다.
- 프로젝트: `docs/SDD-ECU.md` 센서 설계, `docs/ICD.md`, `plan/detail/common/02_통합시험.md`, 의사결정 기록의 실물 사양, `adaptive_ecu/main.cpp`와 `sensor_simulator.cpp`.

### 검증과 남은 범위

- `python -X utf8 tmp/check_safety_review.py` 통과: HTML 태그 중첩·ID·내부/로컬 링크, SVG 9개 XML, A/B 신호 경로, 기존 28개 노드 내부 경로와 노드 간 3선, 그림 6 종료.
- `python -X utf8 tmp/verify_wiring_20260925.py` 통과: 수정 전 12개 표 그대로 보존, A/B 각각 Pin 1~40, ECU 11개/IVI 9개 물리 Pin–GPIO 대응, SVG 도형 위치 보존, 신규 조립 조건과 그림 6 이후 본문 없음. 수정 전 HTML은 무시 경로 `tmp/wiring_review_20260925/before.html`에 보존했다.
- `git diff --check` 통과. 미추적 HTML은 별도 파서 검사로 확인했다. HTML SHA-256: `68cd26b93599a3110ba6f2f8f8cddc7cca91e7fe36d0bb2d7f278c43eeb43343`.
- 브라우저 렌더는 미검증: CUA Chrome 열기에서 `Browser is not available: chrome`; 전체 브라우저 인벤토리도 비어 있었다. 정적 구조 검사 통과를 시각적 검증으로 대체하지 않는다.
- 하드웨어 접근이 없어 전압·부하·단락·SPI 파형/속도·ADC·can0·양방향 실통신·Touch Display/Ubuntu 구동을 수행하지 않았다. 이 문서는 안전 인증이나 즉시 통전 허가가 아니다. 정확한 LC 사양과 실제 배선 측정이 선행되어야 한다.

## ECU ↔ IVI 노드 간 매핑 강조

사용자 요청으로 맨 앞에 A-RPi4↔A-LC↔A-MCP↔CAN↔B-MCP↔B-LC↔B-RPi4 전체 경로와 H/H·L/L·GND/GND 3행 대응표를 배치했다. 기존 선형 구간의 노드 간 3행은 새 표로 옮기고 이동 링크로 대체했다. GND 레일의 각 Pi Pin6 참조, 노드별 전원 분리, J1 종단과 연결 순서를 같은 화면에 표시했다. 검토 보고는 HTML에 재삽입하지 않았다. 정적 검사로 28개 노드 내부 경로+3개 노드 간 연결, 핀/단자 대응, 링크/HTML/SVG, 그림6 종료를 확인했다. 실물 검증 상태는 변경되지 않았다.

## 검토 기록과 배선 안내 분리

사용자 요청으로 배선 HTML의 전기적 검토 결과·판정표·검토 근거·인수 절차를 제거했다. 전압/방향/전원 분리/센서 입력 범위와 사용할 컨버터의 SPI 지원 조건은 해당 연결 경로 옆의 실행 안내로 반영했다. 검토의 한계와 운용 미확인 상태는 이 audit 및 aidlc-state에 유지한다. 삭제가 전기적 검증 완료를 의미하지 않는다. `tmp/check_safety_review.py`로 검토 섹션 제거, 기존 A/B 핀 매핑, HTML 구조·링크·SVG와 그림 6 종료를 재검사했다.

공식 검토 근거: [MCP2515](https://www.microchip.com/content/dam/mchp/documents/APID/ProductDocuments/DataSheets/MCP2515-Family-Data-Sheet-DS20001801K.pdf), [TJA1050](https://www.nxp.com/docs/en/data-sheet/TJA1050.pdf), [AN10441](https://assets.nexperia.com/documents/application-note/AN10441.pdf), [ADS1115](https://www.ti.com/lit/ds/symlink/ads1115.pdf), [Raspberry Pi](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html).

## 전기적 안전성 재검토

- 사용자 요청에 따라 shared MCP2515·컨버터 앞뒤 사진을 재판독. 4개 3단자 소자와 103 저항 표기는 확인했으나 MOSFET 모델 및 SPI 정격은 판독 불가. 제품명/링크를 요청했다.
- Microchip MCP2515 DS20001801K Table 13-1, NXP TJA1050, Nexperia AN10441, TI ADS1115, Raspberry Pi 공식 자료를 조회. 5V MCP SPI 입력 VIH 최소 0.7VDD, TJA1050 공급 4.75~5.25V, ADS 입력 GND~VDD 근거를 반영했다. AN10441은 유사 I²C 회로의 설명이며 보유 컨버터 인증 근거로 사용하지 않았다.
- 모든 LC 경유 경로를 조건부로 명시하고 선호한 A/B 선형 SVG에도 조건 표시. INT의 출력 방식, SO high-impedance, Pi 입력 방향, CS 비활성, 역급전과 전원 순서·전류 제한·부하·전압/타이밍 측정·CAN 종단·센서 범위·기능 인수 조건을 문서화했다.
- `python tmp/check_safety_review.py`로 HTML 구조, 로컬 링크, SVG 9개, 전기 검토표의 5개 핀/채널, 31개 경로, 조건부 그림 2개, 그림 6 이후 삭제 상태 검사. 실물 전압/파형/부하/통신과 브라우저 렌더는 미검증. 제품 코드·ICD·기존 배선 원본은 수정하지 않았다.

## 최종 범위 축소

사용자 요청으로 HTML은 “그림 6 · 두 노드 사이: 신호 2선 + 접지 1선”까지 유지하고 이후 개별 선 체크표·STEP 01~11·사진·시험 안내·푸터를 삭제했다. 앞부분의 삭제 구간 앵커 링크와 후속 STEP 안내도 제거했다. `python tmp/trim_wiring.py`로 HTML 태그 중첩, 중복 ID, 남은 내부 링크, SVG XML 및 그림 6 이후 본문 부재를 확인했고 `git diff --check`를 통과했다. 아래 기록의 56행 체크표·내장 사진·문서 크기는 축소 전 상태의 이력이다.

- 기존 HTML의 물리 핀/SPI 채널과 새 표 대조. LC#1=SCK/SI/CS/SO, LC#2=INT 유지.
- shared 사진 4장을 직접 판독. MCP 초록 종단 J1과 H/L 옆 J3 구분, ADS 분리 헤더, 가변저항 VCC/OUT/GND 확인.
- Raspberry Pi 공식 GPIO 자료 및 TI ADS1115 자료로 3.3V/입력 한계 확인. 출처는 HTML에 연결.
- HTMLParser 검사: 단계 앵커 11개, 링크 21개, 내장 이미지 4개, 로컬 경로/앵커 오류 0건. 외부 링크는 자료 확인 시 접근했다.
- `git diff --check` 통과. 사진 내장으로 HTML 크기는 약 7.5MB다. 외부 라이브러리 없이 열람 가능.
- 기존 배선 원본·제품 코드·계약은 수정하지 않았다. 13개 CTest 통과는 사용자가 제공한 f289395 로그이며 이 작업에서 재실행하지 않았다.
- 물리 배선·전압·CAN·ADC 취득은 미검증. 실제 OS/overlay에 맞춰 설정하도록 조건을 명시했다.

- Edge headless 화면 캡처는 GPU 프로세스 오류로 실패했다. 브라우저에서의 실제 렌더링은 검증하지 못했다.

## 사용자 후속 요청 — 매핑표 우선 배치

HTML 맨 앞에 ECU 9행·센서 7행·IVI 9행·CAN 노드 간 연결 6행의 독립 매핑표를 추가했다. 출발 물리 핀→레일/컨버터 채널→도착 핀을 명시하고 각 표 바로 아래에 이유를 설명했다. 전원 분배 개념도, GPIO/물리 핀 구분과 중복 표기 설명을 추가했다. HTMLParser로 매핑표 4개, 선행 배치, 모든 내부 앵커/로컬 링크를 재검사했고 통과했다. 브라우저 렌더 검증의 기존 한계는 유지한다.

## 그림·개별 선 상세화

사용자 후속 요청으로 SVG 6장(40핀 헤더, SPI/INT 경로, 전원 분기, 센서, 컨버터 실크 배열, CAN 종단)과 한 행당 한 선인 56행 연결표를 추가했다. 기존 통합 표와 동일 회로임을 명시했다. HTML 내부 링크/앵커, SVG XML 6개, 개별 선 56행과 배치 순서 검사 통과. 브라우저 렌더 검증 한계는 유지하며 실물 측정을 대신하지 않는다.

## 부품 전체 관계와 RPi4 Pin / GPIO 동시 표기

선형 경로도 후속 요청: 사용자가 선호한 A/B 신호 SVG 두 장을 복제하지 않고 최상단으로 이동했다. 전원·GND·센서·CAN 노드 간 연결도 시작→레일/직결→목적지의 31행으로 펼쳤다. 레일의 Pi 입력선은 한 번만 연결하고 목적지별로 분기함을 설명했다. 기존 40핀 지도와 56가닥 체크표를 유지했다. 정적 검사에서 최상단 그림 배치, 31행 수, 기존 핀 매핑·SVG·링크 검사를 통과했다. 브라우저 렌더와 실물 배선의 미검증 범위는 유지한다.

후속 수정: 최상단에 ECU와 IVI 각각 2×20 물리 헤더 형태의 배선표를 추가했다. 40개 핀 모두 물리 번호와 GPIO 또는 전원 기능을 표시하고 사용 핀 옆에 레일·컨버터 LV/HV 채널·최종 모듈까지의 경로를 붙였다. 신호 5개씩은 별도의 ① Pi → ② LV / 내부 / ③ HV → ④ MCP 표로 연결할 점퍼선 두 가닥을 구분했다. 센서부터 IVI까지 표에는 직접 배선과 소프트웨어 처리의 차이를 명시했다. 확장한 `tmp/check_dashboard.py`로 두 헤더의 1~40 순서, 10개 신호 경로의 Pin/GPIO/LC/LV/HV/단자 대응 및 최상단 배치를 검사했다.

문서 첫 화면에 가변저항·ADS1115·ECU/IVI 라즈베리파이·각 노드의 레벨 컨버터 2개·MCP2515를 이름으로 구분한 전체 관계도를 추가했다. ECU 11행과 IVI 9행의 통합 매핑표는 물리 Pin, BCM GPIO, 경유 부품과 채널, 도착 부품과 핀, 신호 방향을 별도 열로 표시한다. 노드별 신호 그림은 Pi→LV→HV→MCP 경로와 SO/INT 역방향을 표시하며 컨버터 내부 구간과 실제 점퍼선을 구분한다. 센서 OUT→A0 및 노드 간 H/H·L/L·GND 연결을 별도로 강조했다.

`python tmp/check_dashboard.py` 통과: SVG XML 9개, ECU/IVI 표의 물리 Pin·GPIO 대응 20행, 개별 선 체크박스 56개, 중복 ID·내부 앵커·로컬 링크와 최상단 배치 검사. `git diff --check` 통과. Edge headless 재시도도 GPU 프로세스 오류로 실패하여 화면 렌더링과 실제 하드웨어 배선은 미검증이다.
