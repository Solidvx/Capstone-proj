# 공식 문서

CAN·인증·API 계약은 ICD, 기능 요구는 SRS, 설계는 양측 SDD, 시험 기준은 TEST_PLAN을 따른다. 현재 구현은 해당 브랜치의 실제 소스와 시험으로 확인한다.

- [ICD](ICD.md): CAN/SecOC·서비스 API.
- [인증 세션](ICD-CAN-SESSION.md): session-v2 계약.
- [인증 진단](ICD-CAN-DIAGNOSTIC.md): 진단 메시지 계약.
- [SRS](SRS.md): 기능·비기능 요구사항.
- [ECU 설계](SDD-ECU.md)·[IVI 설계](SDD-IVI.md).
- [시험 계획](TEST_PLAN.md): 공식 시험과 합격 기준.
- [ADR](ADR.md): 채택한 설계 결정.
- [TARA](TARA.md): 위협·위험·완화책.
- [CI/CD 명세](CICD_SPEC.md): 품질·배포 기준.

개인·AI 작업기록과 실험 원본은 별도로 보관한다. 공개 프로토콜 시험 벡터는 `common/testdata/`에 있으며 양 노드와 Python 시험이 함께 사용한다.
