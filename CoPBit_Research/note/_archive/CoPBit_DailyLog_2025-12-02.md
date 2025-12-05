# CoPBit Daily Log – 2025-12-02

## 1. 리포지토리 / 브랜치 상태

- Repo: `ILC-4_CoPBit`
- Branch: `copbit_q1_phase_overview`
- Today focus: **CoPBit 1-lane 4bit Phase Engine Q1~Q7 베이스라인 구축**

---

## 2. 신규/수정 파일

### 2.1 노트

- `CoPBit_Research/note/CoPBit_Overview_v0.1.md`  
  - CoPBit 개념 개요 정리 (위상 기반 3D/구형 16포인트, Kuramoto 병렬 위상 엔진 철학 등).
- `CoPBit_Research/note/CoPBit_Q3_PhaseBER_Notes_v0.1.md`  
  - Q3/Q5 관련 1-lane 4bit 위상 BER 실험 결과와 해석 정리.

### 2.2 파이썬 스크립트

- `CoPBit_Research/python/copbit_q2_kuramoto_demo_v0.py`
- `CoPBit_Research/python/copbit_q3_bit_mapping_demo_v0.py`
- `CoPBit_Research/python/copbit_q3_phase_decode_demo_v0.py`
- `CoPBit_Research/python/copbit_q3_phase_decode_sweep_v0.py`
- `CoPBit_Research/python/copbit_q4_kuramoto_demo_v0.py`
- `CoPBit_Research/python/copbit_q5_kuramoto_ber_v0.py`
- `CoPBit_Research/python/copbit_q6_compare_modems_v0.py`
- `CoPBit_Research/python/copbit_q7_guard_mode_ber_v0.py` (아이디어 실험 후 폐기 후보로 판정)

Git 커밋:

```bash
git commit -m "Add CoPBit Q1~Q7 1-lane phase demos and BER notes (2025-12-02)"
git push -u origin copbit_q1_phase_overview
```

---

## 3. Q1~Q7 실험 내용 요약

### Q1 – 16포인트 CoPBit 위상 맵핑 정의

- 4bit → 16포인트 균일 위상 (16-PSK 스타일) 맵핑 확정.
- 인덱스 k = 0..15 에 대해
  - `theta_k = 360/16 * k [deg]`
  - bit 패턴은 k의 4bit binary (0000~1111).
- 이 맵핑을 **CoPBit 1-lane 4bit 기본 심볼 집합**으로 채택.

핵심:  
- **Amp = 1 (unit circle)** 고정, 모든 정보는 위상에만 실림.  
- 이후 모든 실험(Q2~Q7)의 공통 기준.

---

### Q2 – Kuramoto 기반 클러스터 동기화 데모

- 파일: `copbit_q2_kuramoto_demo_v0.py`
- 16포인트를 4개 클러스터(각 4포인트)로 나누고, Kuramoto 형태의 위상 결합으로
  - 초기 위상 + 잡음 + 클러스터 결합 → 시간 경과 후 각 클러스터 위상이 하나의 평균 값으로 수렴하는지 확인.
- 결과:
  - 각 클러스터의 mean phase는 안정적으로 수렴.
  - cluster-wise order parameter R ≈ 0.999 수준으로 **강한 위상 동기화** 확인.
- 해석:
  - CoPBit 16포인트 위상 집합을 4개 클러스터로 쪼개고,  
    클러스터 내부를 Kuramoto로 묶으면 **집단 위상 기준(clock)** 을 만들 수 있다는 개념적 검증.

---

### Q3 – 1-lane 4bit 위상 디코딩 및 AWGN BER 베이스라인

#### Q3-1: 비트 매핑 왕복 체크

- 파일: `copbit_q3_bit_mapping_demo_v0.py`
- 4bit → index(0..15) → 4bit 로 왕복 변환이 완전히 일치하는지 확인.
- 결과:
  - 모든 (c,p)/bit 쌍이 완벽히 왕복, 맵핑 로직 이상 없음.

#### Q3-2: 단일 AWGN + phase noise 디코딩 실험

- 파일: `copbit_q3_phase_decode_demo_v0.py`
- 순수 위상 AWGN (σ_deg ≈ 5°) 조건에서
  - 심볼 정확도 ≈ 0.975
  - Bit BER ≈ 1.18e-2
- Kuramoto 보정 없이, **최근접 위상 디코더만 사용한 기본 성능**.

#### Q3-3: σ 스윕 BER 실험

- 파일: `copbit_q3_phase_decode_sweep_v0.py`
- `sigma_list = [3,4,5,6,8] deg` 에 대해 BER 측정.

예시 (n_sym = 50000):

| σ [deg] | Sym Acc | Bit BER    |
|---------|---------|-----------:|
| 3       | 0.9997  | 1.5e-4     |
| 4       | 0.9947  | 2.57e-3    |
| 5       | 0.9752  | 1.17e-2    |
| 6       | 0.9404  | 2.83e-2    |
| 8       | 0.8410  | 7.44e-2    |

- 이 결과는 `CoPBit_Research/note/CoPBit_Q3_PhaseBER_Notes_v0.1.md`에 정리.

해석:

- 단순 위상 AWGN 비트 에러 특성을 정량화.
- CoPBit 4bit 1-lane이 **위상 노이즈 σ 기준 어느 정도까지 FEC로 커버 가능한지** 감을 잡는 단계.

---

### Q4 – Kuramoto Cluster Demo (정성적 동기화 확인)

- 파일: `copbit_q4_kuramoto_demo_v0.py`
- 역할:
  - Q2 개념을 확장하여, 시간에 따른 클러스터 mean phase 궤적 및 최종 상태를 그림으로 확인.
- 출력:
  - `CoPBit_Q4_kuramoto_cluster_means.png`
  - `CoPBit_Q4_kuramoto_final_phases_polar.png`
- 결과:
  - 노이즈/초기 위상 차이가 있어도, 클러스터별 위상은 안정적으로 락(lock)되는 것을 확인.
- 의미:
  - Kuramoto 기반 위상 동기화 메커니즘이 **CoPBit 4bit/16포인트에서 구조적으로 동작 가능**하다는 정성적 증거.

---

### Q5 – AWGN + ISI + Kuramoto-aided BER (v0.1 베이스라인)

- 파일: `copbit_q5_kuramoto_ber_v0.py`
- 채널 모델:
  - `y[n] = s[n] + alpha * s[n-1] + w[n]`
    - `alpha = isi_alpha` (예: 0.3)
    - `w[n]`: Es/N0 기반 복소 AWGN
- 디코더:
  - **BER_base**: 단순 최근접 16-위상 디코더
  - **BER_kura**: `kuramoto_cluster_refine()` 로 클러스터 mean 위상 보정 후 재디코딩
- FEC 가정:
  - 실제 FEC는 돌리지 않고,  
    pre-FEC BER ≤ 1e-2 이면 "강한 FEC로 커버 가능 영역"이라고 표시.

#### 관찰 결과

- ISI=0.3, 0.4, 다양한 SNR에서 측정했지만,
  - `BER_kura`가 `BER_base`보다 눈에 띄게 좋아지지 않음 (오히려 더 나쁜 구간 다수).
- ISI=0 (순수 AWGN)에서도,
  - SNR=19 dB 부근에서야 1e-2 근처/이하가 나오는 수준.

#### 결론 (오늘 버전 v0.1 기준)

- 현재 Kuramoto-aided 구현은
  - **“집단 위상 동기화”를 BER 개선으로 직접 연결시키는 구조가 아직 미흡**.
  - 단순 cluster mean 보정만으로는 실질적인 SNR 이득이 거의 없음.

- 그래서 Q5에 대해 메모:
  - **"Q5 구조는 베이스라인으로 유지하되, Kuramoto를 채널/위상 추정 쪽에 더 깊게 녹이는 Q5' 또는 Q5v2가 필요"**
  - → 내일 이후에 **CoPBit는 “amp=1” 구조라는 점**을 반영한 새로운 Es/N0 세팅/모델링이 필요.

---

### Q6 – PAM4 vs CoPBit4 AWGN-only 비교 (v0.1)

- 파일: `copbit_q6_compare_modems_v0.py`
- 내용:
  - 기존 4-레벨 PAM4와 CoPBit 4bit/16위상(16-PSK 스타일)을 **동일 AWGN 채널**에서 비교.
- 결과 예시:

| SNR[dB] | BER_pam4 | BER_copbit4 |
|---------|---------:|------------:|
| 10      | 5.887e-02 | 1.784e-01 |
| 12      | 2.824e-02 | 1.271e-01 |
| 14      | 9.470e-03 | 7.871e-02 |
| 16      | 1.760e-03 | 3.804e-02 |
| 18      | 1.500e-04 | 1.346e-02 |
| 20      | 0.0      | 2.628e-03 |

- 이 값은 **단순 16-PSK vs 4-PAM** AWGN 비교이기 때문에,
  - CoPBit의 본질(amp=1, 위상만 사용, 전력/레이어 구조 차이)을 반영한 공정 비교라고 보기는 어려움.

핵심 메모:

- **오늘 결론**:  
  - “PAM4 vs CoPBit4”를 단순 동일 Es/N0 + AWGN 기준으로 바로 비교하는 것은  
    CoPBit가 원래 목표로 하는 영역(저전력, 위상 병렬 연산, Kuramoto 기반 엔진)과는 다름.
  - 따라서 **Q6 결과는 “간단한 참고용 그래프” 정도로만 보류**하고,  
    추후 CoPBit용 SNR/에너지 모델링을 새로 짜야 함.

---

### Q7 – 2bit + Guard 아이디어 실험 (폐기 후보)

- 파일: `copbit_q7_guard_mode_ber_v0.py`
- 아이디어:
  - 4bit 중 2bit만 payload로 쓰고, 나머지 2bit/클러스터를 guard/중복으로 써서 BER을 내릴 수 있는지 확인.
- 결과:
  - 고 SNR에서 **4bit 모드보다 조금 나은 구간**도 있으나,
  - 전체적으로 기대만큼의 강한 이득을 보여주지 못하고 구조도 불명확.
- 오늘 판단:
  - Q7은 **"실험해 봤고, 현재 버전은 폐기 후보"**로 노트에 남기고,  
    메인 CoPBit 로드맵에서는 우선 제외.

---

## 4. 오늘 개념 정리 포인트

1. **CoPBit는 Amp=1 레벨(상수 진폭) 기반 위상 엔진**  
   - 기존 PAM4는 4개 진폭 레벨을 사용하지만,  
     CoPBit는 **진폭을 거의 쓰지 않고 위상만으로 4bit 표현**을 지향.
   - 따라서 SNR/Es 설정, 채널 모델링, 비교 기준이 기존 PAM 계열과 다르게 잡혀야 함.

2. **Kuramoto는 “집단 위상 동기화 엔진”으로 쓰고 싶다**  
   - 오늘까지는 simple cluster mean 보정으로만 사용했지만,
   - 앞으로는
     - 위상 추정 / tracking
     - ISI/채널 보정과 연동
   - 쪽으로 더 깊이 녹여야 의미 있는 BER 이득 가능.

3. **1-lane 4bit CoPBit를 먼저 확실히 잡고 간다**  
   - 오늘 Q1~Q7로 **기본 위상 맵핑 + AWGN/ISI + Kuramoto 데모 + PAM4 비교 + guard 아이디어**까지 1차 스캔 완료.
   - 내일 이후는
     - Q5 구조 재설계 (Kuramoto + 채널 추정 결합)
     - CoPBit 용 SNR/에너지 정의 정교화
     - “PAM4 vs CoPBit”를 공정하게 비교할 수 있는 프레임 재구성
   - 쪽으로 이어갈 예정.

---

## 5. 내일 이후 To-Do (초안)

1. **Q5 정교화 (CoPBit 4bit 1-lane BER 재설계)**  
   - CoPBit의 amp=1 특성을 반영한 SNR/Es 모델링 재정의.
   - Kuramoto를 “집단 위상 동기화 + 채널/ISI 보정”으로 연결하는 구조 재설계.
   - 목표:  
     - `BER_kura`가 `BER_base` 대비 **명확한 이득**을 보이도록 세팅.

2. **PAM4 / ILC3 / CoPBit 공정 비교 프레임 구상**  
   - 동일 전력/대역폭/복잡도 기준에서,
   - 어느 축(스루풋, 전력, BER, FEC 마진 등)에서 CoPBit가 강점인지 명확히 정리.

3. **장기 로드맵 메모**  
   - 1-lane 정리 후 → xN-lane 병렬 CoPBit (1024 lane etc.)  
   - 암호/보안, PPU, 온디바이스 연산 등 응용 아이디어는 **별도 노트로 분리** 예정.

---

_작성: 2025-12-02, CoPBit Q1~Q7 1-lane phase demo 정리용 일일 로그._
