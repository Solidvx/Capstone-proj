# 한글 UI 글꼴

`NanumGothic-Regular.ttf`는 Google Fonts의 공개 원본을 수정하지 않고 포함했다. Linux 환경에 한글 시스템 글꼴이 없어도 Qt 앱에서 동일하게 읽을 수 있도록 실행 시 application font로 등록한다. 실행 중 글꼴을 다운로드하지 않는다.

- 원본: [Google Fonts / Nanum Gothic](https://github.com/google/fonts/tree/main/ofl/nanumgothic)
- 파일: [공식 TTF](https://raw.githubusercontent.com/google/fonts/main/ofl/nanumgothic/NanumGothic-Regular.ttf)
- 라이선스: [OFL.txt](OFL.txt), SIL Open Font License1.1. 원저작권/Reserved Font Name 조건을 보존한다. 파일을 수정하거나 이름을 바꾸지 않았다.
- 가져온 날:2026-11-11. 실제 파일 SHA-256은 [provenance.json](provenance.json).

폰트와 라이선스는 Qt resource에 함께 들어간다. `ivi_dashboard --font-license`로 원문을 출력할 수 있고 CMake install은 라이선스를 `share/licenses/ivi_dashboard/NanumGothic-OFL.txt`에도 설치한다. 바이너리/전달본 배포 시 이 라이선스를 함께 보존한다. 글꼴 단독 판매나 수정본의 Reserved Font Name 사용을 허용한다고 해석하지 않는다.
