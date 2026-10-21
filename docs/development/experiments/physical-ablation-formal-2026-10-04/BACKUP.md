# 증거 백업·복구

원본은 두 실험 디렉토리의 `raw`와 inventory로 보존한다. 현재 로컬 복구 ZIP의 위치는 저장소 루트 `실험결과_백업파일/experiment-evidence-20261004-verified.zip`이며, 같은 폴더의 `.zip.manifest.json`을 함께 보관한다. 사용자는 ZIP·manifest와 최종 보고서를 Google Drive에 백업했다고 보고했다. 원격 사본의 재다운로드·해시는 직접 검증하지 않았다.

생성과 전 항목 검증은 표준 라이브러리 도구로 한다. 새 이름을 사용하며 기존 ZIP은 덮어쓰지 않는다.

```text
python -m security.experiments.evidence_bundle --out 실험결과_백업파일/experiment-evidence-NEW.zip
python -m security.experiments.evidence_bundle --verify 실험결과_백업파일/experiment-evidence-20261004-verified.zip
```

ZIP 내부 `BUNDLE-MANIFEST.json`은 모든 멤버의 경로·크기·SHA256을 가진다. 외부 `.zip.manifest.json`은 ZIP 전체 해시와 전 멤버 검증 결과를 가진다. 복사 후 같은 verify 명령으로 멤버 해시를 검증하고 ZIP 전체 SHA256도 비교한다.

포함 범위: 실험 원본·분석·보고서·도구·감사 기록과 관련 docs/plan 문서, security Python/JSON/요구 패키지 목록. 기존 archive 안의 실험 당시 소스/manifest는 보존한다. 전체 Git 저장소·운영 키·ECU의 실행 환경 자체를 백업했다는 뜻은 아니다. 커밋/원격 전송은 수행하지 않는다.

복구는 빈 별도 디렉토리에 일반 ZIP 도구로 해제한 뒤 manifest를 확인한다. 현재 작업 폴더 위에 덮어쓰지 않는다. 현재 문서가 생성 이후 변경되면 새 ZIP 이름으로 다시 생성한다. 검증 기록의 기준 시점을 따른다.

## 2026-10-05 중복 사본 정리

사용자 요청에 따라 `evidence-backups`의 동일 ZIP·manifest 두 파일을 삭제했다. 삭제 전 각각 `실험결과_백업파일`의 보관 사본과 SHA256이 일치하는지 확인했고, 삭제 후 보관 사본의 존재를 확인했다. ZIP 해시는 `eb59418f64d1f105580a125e10561c4b201c88d50abbe3cf4c06436e6554d070`이다. 원본 실험 자료와 최종 보고서는 유지했다.

감사 디렉토리의 `backup-receipt.json`에 있는 `evidence-backups` 경로는 생성 당시 위치를 기록한 역사 자료이며 현재 보관 위치는 위 안내를 따른다. 새 보고서는 기존 ZIP 이후 생성되어 사용자가 Google Drive에 별도로 백업했다고 확인했다.
