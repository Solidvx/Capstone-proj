# Node B IVI 구현 경계

이 디렉터리는 ADR-010에 따라 Ubuntu 22.04, C++17, SocketCAN, Qt 6 Quick/QML로 구현할 Node B 제품 경계다.

2026-09-22 현재 제품 소스·CMake·시험은 없고 이 README만 있다. [IVI 계획](../plan/IVI.md)의 P1에서 이전 작업 폴더의 검토된 C++/QML 파일만 선택 이관한다. Android/HIDL/AIDL/Kotlin 파일, 빌드 산출물, 비밀키는 반입하지 않는다.

구현 구조와 API는 [SDD-IVI](../docs/SDD-IVI.md), CAN/SecOC 계약은 [ICD](../docs/ICD.md), 합격 기준은 [TEST_PLAN](../docs/TEST_PLAN.md)을 따른다.
