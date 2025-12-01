# ILC3_IPCore 문서 인덱스 v0.1

ILC3_IPCore 관련 docx 문서들의 **역할과 사용 용도**를 정리한 인덱스이다.  
특허/논문/파트너사 공유 시, 어떤 문서를 참조해야 할지 빠르게 찾기 위한 용도.

---

## 1. 알고리즘 & 링크 스펙 계열

### 1.1 `docs/ilc3_algorithm_link_spec_v1.0_2025-12-01.docx`

- 역할:  
  - Q10~Q20 링크 시뮬레이션 결과를 기반으로 한 **알고리즘/링크 스펙 정리본**.
  - AWGN + 채널 a/b/c, FFE-only 기준 pre-FEC / post-FEC BER–SNR 곡선 정리.
  - ILC3_0c_gp vs PAM4 간 **약 3 dB SNR 이득**을 수치로 확인.
- 사용처:
  - 특허 명세서의 “기술적 배경 / 성능 비교 그래프”.
  - 논문에서 성능 비교 섹션 (Simulation Results).

---

## 2. RTL 구조/검증 관련 문서

### 2.1 `docs/ILC3_IPCore_1lane_RTL_v0.1_Summary_ko.docx`

- 역할:
  - 1-lane IPCore RTL(v0.1)의 구조 요약 (Tx/Rx/Top, clean/noise TB 결과).
- 사용처:
  - RTL 구현 개요를 빠르게 설명해야 할 때.
  - 파트너사/엔지니어에게 1-lane 베이스라인 공유용.

### 2.2 `docs/ILC3_IPCore_1lane_x8_Architecture_v0.1_ko.docx`

- 역할:
  - 1-lane IPCore를 8 lane(x8)으로 확장하는 구조 설명.
  - lane별 인스턴스, 데이터/클럭 구조 개략.
- 사용처:
  - x8 확장 개념을 설명할 때, HBM/SoC 연계 설명 전에 보여주기 좋음.

### 2.3 `docs/ILC3_IPCore_Architecture_v0_1_fixed.docx`

- 역할:
  - 초기 Architecture v0.1 문서(수정본).  
  - 기본 블록 다이어그램, Tx/Rx 경로, 간단한 상태 설명 포함.
- 사용처:
  - 아키텍처 변천사(tracking)나, v0.2와의 차이를 보여줄 때 참고용.

### 2.4 `docs/ILC3_IPCore_Architecture_v0_2_KOR.docx`

- 역할:
  - 운영 모드(Normal / Training / Loopback 등), 상태/에러 신호 등을 포함한 **Architecture v0.2**.
- 사용처:
  - 실제 제품 사양 논의 시, 블록 I/F + 모드 정의 참고용.
  - 향후 레지스터 맵 정의의 출발점.

### 2.5 `docs/ILC3_IPCore_RTL_and_Channel_Verification_v1_0.docx`

- 역할:
  - **RTL & Channel Verification v1.0** 리포트.
  - 1-lane / x8 clean 채널 PASS 결과, lvl1/lvl_real 노이즈 모드에서의 거친 BER 테스트 포함.
- 사용처:
  - “시뮬레이션 검증이 어느 정도까지 끝났는지” 증명할 때.
  - 특허 첨부자료, 파트너사 기술 검토용.

---

## 3. RTL–알고리즘–제품 스펙 브리지 문서

### 3.1 `docs/ILC3_IPCore_v0.1_RTL_Architecture_and_LinkSpec.docx`

- 역할:
  - RTL 아키텍처와 링크 스펙(알고리즘)을 한 문서 안에서 연결.
  - “Q18/Q20 링크 스펙 ↔ IPCore RTL 구조”의 브리지 역할.
- 사용처:
  - 기술의 전체 흐름(알고리즘 → RTL → 링크 버짓)을 한 번에 설명해야 할 때.
  - 내부 리뷰/투자자용 기술 개요.

### 3.2 `docs/ILC3_x8_IPCore_Product_Spec_v0.1.docx`

- 역할:
  - **x8 IPCore Product Spec v0.1**.
  - 외부 인터페이스, lane 수, 데이터 폭, 목표 BER/SNR, HBM/SoC 연동 예시를 포함한 “제품용” 스펙.
- 사용처:
  - 실제 SoC/컨트롤러 벤더와 논의할 때 제공하는 1차 레퍼런스 스펙.
  - 투자/파트너 미팅에서 제품화 방향을 설명할 때.

---

## 4. README / 레포와의 연결

- `note/README_ILC3_IPCore_v0.1.md`
  - RTL 레포 구조(core/sim)와 TB, 채널 모델, 시뮬 커맨드를 설명.
  - 위 docx 문서들은 이 RTL 스냅샷(`ILC3_IPCore RTL v0.1`)을 기반으로 작성됨.

이 인덱스 문서의 버전:

- 문서명: `ILC3_IPCore_Docs_Index_v0.1.md`
- 역할:  
  - ILC3_IPCore 관련 모든 docx/README의 “카탈로그”  
  - 특허/논문/파트너 공유 시, 어떤 문서 조합을 패키지로 보낼지 결정하는 기준.