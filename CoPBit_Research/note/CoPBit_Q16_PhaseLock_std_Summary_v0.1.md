# CoPBit Q16 – Kuramoto PhaseLock_std에서 P_ref의 역할 및 실험 요약 v0.1

## 0. 목적

본 메모는 Q16 계열 실험(Q16, Q16b, Q16c, Q16d)을 기준으로,

- **Kuramoto 스타일 공통 PLL(PhaseLock_std)** 에서  
  **P_ref lane(위상 기준 레인)** 이 어떤 역할을 하는지,
- P_ref의 **최소 필요 개수**와 **성능 한계(BER floor)** 를  
  정리하기 위한 요약 문서이다.

핵심 질문:

1. P_ref lane이 없을 때(CoPBit 1-lane M8) 시스템은 어떻게 붕괴하는가?
2. P_ref lane이 1개만 있어도 충분한가?  
   (N_ref = 1 vs 2 vs 8 비교)
3. AWGN-only vs Channel-b mid-ISI + FFE 환경에서  
   P_ref가 만들어 주는 **BER 레벨**은 어디까지인가?

---

## 1. 공통 구조 – PhaseLock_std (Kuramoto 스타일)

### 1.1. 기본 모델

- **Lane 구성**
  - `N_ref` lanes  : P_ref lane (모든 심볼이 같은 8-PSK index, k_ref_const)
  - `N_data` lanes : Data lane (3 bit/sym, M8)

- **위상 노이즈**
  - 모든 lane에 **공통 위상 노이즈** φ(t) 적용
  - Wiener process:
    - Δφ ~ N(0, σ²), σ = θ_std_deg[deg] → rad 변환
    - φ[n] = Σ Δφ

- **PLL 업데이트(PhaseLock_std)**

  각 심볼 시점 n에서

  - P_ref 측 error:
    - `e_ref` = angle( z_ref · conj(s_ref_const) )  
    - (N_ref lane 평균 → e_ref_mean)
  - Data 측 error:
    - `e_data` = angle( z_data · conj(s_data_hat) )  
    - (N_data lane 평균 → e_data_mean)
  - 혼합:
    - `e_total = (1 - α_ref) * e_ref_mean + α_ref * e_data_mean`
    - φ_hat[n+1] = φ_hat[n] + μ_phase · e_total

- **PLL 모드**
  - **No PLL**: φ_hat = 0 (위상 추적 없음, slicer only)
  - **Data-DD only**: α_ref = 1.0 (data만 보고 업데이트)
  - **Data + p_ref (PhaseLock_std)**: 0 < α_ref < 1 (실험에서는 α_ref = 0.3)

---

## 2. Q16 / Q16b – 2·3-lane (AWGN + 공통 위상 노이즈)

### 2.1. Q16: 2-lane (1 p_ref + 1 data), no-ISI + AWGN

- 파라미터(대표):
  - n_sym = 200k, Eb/N0 = 12,14,16 dB
  - θ_std_deg ∈ {0°, 1°, 3°, 5°}
  - μ_phase = 0.05, α_ref = 0.3
  - 채널: h = [1] (no-ISI), FFE: 사용하지 않음 (ffe_len=1, train_frac=1, mu_ffe=0)

#### (1) θ_std_deg = 0° (위상 노이즈 없음)

- No PLL, Data-DD only, Data+p_ref 모두  
  BER ≈ 10⁻⁴ ~ 0 수준으로 동일
- **결론**: 위상 노이즈 없는 환경에서는 P_ref 효과 없음 (당연).

#### (2) θ_std_deg = 1°

- No PLL:
  - BER_noPLL ≈ 0.45 ~ 0.50 (거의 완전 붕괴)
- Data-DD only / Data+p_ref:
  - Eb/N0 = 12 dB 에서
    - BER_DDonly ≈ 5.7×10⁻⁴
    - BER_DD+pRef ≈ 4.8×10⁻⁴
  - Eb/N0 ≥ 14 dB 에서는 둘 다 ≈ 10⁻⁵ 수준

⇒ θ_std_deg이 작을 때는 **data-only PLL도 충분히 동작**하며,  
p_ref는 **소폭의 마진 개선** 정도.

#### (3) θ_std_deg = 3°

- No PLL / Data-DD only:
  - BER ≈ 0.50 수준 → 완전 붕괴 상태 유지
- Data + p_ref:
  - Eb/N0 = 12 dB → BER ≈ 0.0380
  - Eb/N0 = 14 dB → BER ≈ 0.0300
  - Eb/N0 = 16 dB → BER ≈ 0.0264

⇒ **위상 노이즈가 커지면 (θ_std≈3°)**  
data-only PLL은 수렴에 실패(0.5 근처),  
반면, **p_ref 하나만으로도** BER을 3~4% 수준까지 살려낸다.

#### (4) θ_std_deg = 5°

- No PLL / Data-DD only:
  - 여전히 0.49~0.51 수준 (붕괴)
- Data + p_ref:
  - Eb/N0 = 12 dB → BER ≈ 0.149
  - Eb/N0 = 16 dB → BER ≈ 0.136

⇒ 위상 노이즈가 아주 큰 경우에도  
**p_ref가 있으면, 완전 붕괴(0.5) → 0.14~0.15 수준까지 복구** 가능.

---

### 2.2. Q16b: 3-lane (2 p_ref + 1 data), no-ISI + AWGN

- 설정은 Q16과 동일, P_ref lane만 2개로 증가.
- 대표 결과 (θ_std_deg = 1°, 3°, 5°):

  - θ_std_deg = 1°:
    - Data-DD only, Data+2pRef 모두 ≈ 5×10⁻⁴ 수준
  - θ_std_deg = 3°:
    - Data+2pRef: Eb/N0 = 16 dB에서 BER ≈ 0.0288
    - (2-lane Q16: ≈ 0.0264) → **거의 동일**
  - θ_std_deg = 5°:
    - Data+2pRef: BER ≈ 0.15~0.16
    - (2-lane Q16: ≈ 0.14~0.15) → **근소 차이**

**정리**

- p_ref lane을 **1개 → 2개**로 늘려도  
  **BER 수준은 거의 동일 (차이는 10⁻³ 단위)**.
- 즉, **위상 추적 관점에서 “anchor”는 1개로 이미 충분한 상태**이며,  
  2개 이상은 평균 에러 분산을 약간 줄여주는 **안정성/마진** 정도의 효과.

---

## 3. Q16c – Multi-lane (N_ref, N_data), AWGN + 공통 위상 노이즈

- 예: (N_ref, N_data) = (1,1), (2,1), (8,56)
- θ_std_deg = 3°, μ_phase = 0.05, α_ref = 0.3

대표 결과(θ_std_deg=3°, Eb/N0 = 12~16 dB):

- **N_ref = 1, N_data = 1**
  - BER_DD+pRef ≈ 0.038
- **N_ref = 2, N_data = 1**
  - BER_DD+pRef ≈ 0.039
- **N_ref = 8, N_data = 56**
  - BER_DD+pRef ≈ 0.037~0.038

**정리**

- Lane 수를 **극단적으로 늘려도** (8 ref + 56 data)  
  p_ref lane 수를 1→2→8로 바꾸는 것에 따른 BER 차이는  
  **0.037~0.039 사이의 아주 작은 변동**에 그친다.
- 즉, **공통 위상 노이즈 모델** 하에서는  
  **“클러스터당 최소 1개의 P_ref anchor”** 만 있어도  
  Kuramoto/PLL이 제 역할을 충분히 수행한다고 볼 수 있다.

---

## 4. Q16d – Multi-lane + Channel-b mid-ISI + MMSE-FFE

### 4.1. FFE-only baseline (P_ref = 0, θ_std = 0°)

- Channel-b mid-ISI (5-tap, Q13/Q14 계열) + **block-MMSE FFE (M8 기준)**.
- 설정 예:
  - ffe_len = 11, mu_ffe(ridge) = 0.003, train_frac = 1.0
  - n_ref = 0, n_data = 1, θ_std_deg = 0°, μ_phase = 0

결과:

```text
Eb/N0_dB |  BER_noPLL   |  BER_DDonly  |  BER_DD+pRef
-----------------------------------------------------
  8–20 dB |  ≈ 0.273–0.280 (세 모드 동일)

	•	No PLL / Data-DD only / Data+pRef 모두 동일 (P_ref=0이므로 의미 없음).
	•	이 값(≈0.273)은 Channel-b mid-ISI + FFE(M8)의 intrinsic BER floor 로 해석.

4.2. P_ref 포함(θ_std_deg > 0°)

예: N_ref = 1, N_data = 1, θ_std_deg = 1°, 3°, 5°
(ffe_len = 7, mu_ffe(ridge) = 0.003, train_frac = 0.5, μ_phase=0.05, α_ref=0.3)
	•	Data-DD only / No PLL:
	•	Eb/N0 = 1216 dB에서도 여전히 **0.460.50** 수준 → 붕괴 상태.
	•	Data + p_ref (PhaseLock_std):
	•	θ_std_deg = 1°:
	•	BER_DD+pRef ≈ 0.287 ~ 0.286
	•	θ_std_deg = 3° / 5°:
	•	BER_DD+pRef ≈ 0.285~0.289 근처

또 다른 조합들:
	•	(N_ref, N_data) = (2,1), (8,56) 에서도
	•	BER_DD+pRef ≈ 0.285~0.288 수준으로 수렴.

이를 FFE-only floor(≈0.273) 과 비교하면:
	•	P_ref + PhaseLock_std가 완전 붕괴(0.5) 를 막고
	•	시스템을 “mid-ISI + FFE floor(≈0.27x)” 근처로 붙잡아 두는 역할을 수행.

중요 포인트
	•	mid-ISI가 강한 환경에서는,
M8 기준 FFE가 완벽히 ISI를 제거하지 못해
애초에 BER floor ≈ 0.27 이 존재.
	•	P_ref는 이 floor 아래로 더 내려가게 만들지는 못하지만,
	•	위상 붕괴 상태(0.5) → floor 근처(0.27x)로 되살리는 역할.
	•	N_ref를 1→2→8로 늘려도
floor 근처에서의 BER은 0.285 ± 0.003 안에 머물며,
추가 P_ref 수는 BER에 큰 영향을 주지 않는다.

⸻

5. 결론 – Kuramoto PhaseLock_std에서 P_ref의 “핵심 역할”

5.1. 기능적 정의

실험 결과들을 종합하면, CoPBit Q16 계열에서 P_ref lane의 역할은:

“Kuramoto/PhaseLock_std가 위상 붕괴를 막고,
시스템을 채널/FFE가 허용하는 BER floor 근처로 유지하도록
잡아주는 global phase anchor”

라고 정리할 수 있다.
	•	AWGN-only 환경:
	•	θ_std_deg가 작으면(pure AWGN) P_ref의 영향 거의 없음.
	•	θ_std_deg ≥ 3° 수준의 위상 노이즈에서는
	•	NoPLL / Data-DD only: BER ≈ 0.5 (완전 붕괴)
	•	Data+pRef: BER ≈ 0.03~0.15로, 실질적인 에러율을 수십 배 낮춤.
	•	mid-ISI + FFE 환경(Channel-b):
	•	본질적 floor ≈ 0.273이 존재.
	•	P_ref가 있으면:
	•	NoPLL / Data-DD only 붕괴(0.5)를 막고,
	•	항상 floor 근처(0.27x)로 되돌려 놓는다.

5.2. P_ref 개수에 대한 설계 룰

현재 공통 위상 노이즈 모델 + Q16c/Q16d 기준:
	1.	N_ref = 1 vs 2 vs 8
	•	BER 차이는 10⁻³ 수준 이하로 매우 작다.
	•	즉, “anchor 개수 1개면 충분” 하다는 쪽으로 해석 가능.
	2.	64-lane / 1024-lane 확장 관점에서의 가이드라인(초안)
	•	기본 룰(PhaseLock_std):
	•	각 Kuramoto 클러스터(예: 64 lanes)당 P_ref 최소 1 lane
	•	나머지 lanes는 data lane으로 모두 사용.
	•	추가 P_ref lanes:
	•	위상 노이즈가 극단적으로 크거나,
	•	일부 lane의 SNR이 현저히 낮은 경우
마진/안정성 확보용 옵션으로만 고려.

	3.	설계 문장 예시
	•	“CoPBit Kuramoto PhaseLock_std 구조에서,
공통 위상 노이즈(Wiener process) 하의 multi-lane M8 시스템은
클러스터당 하나의 P_ref lane만으로도 위상 붕괴를 방지하고,
채널/FFE가 허용하는 BER floor에 근접한 성능을 확보할 수 있다.”

	추가로, 실험 결과를 요약하면 다음과 같이 정리할 수 있다: “CoPBit PhaseLock_std 구조에서는 (1) 클러스터당 최소 1개의 P_ref lane만으로도 Kuramoto 위상 락 조건을 충족하고, (2) 그 상태에서 달성 가능한 최소 BER 수준은 채널 + EQ(예: Channel-b mid-ISI + FFE) 조합이 만드는 intrinsic floor로 결정된다.”

⸻

6. 향후 정리 방향 (Q17 이후 아이디어용 메모)
	1.	θ_std_deg–Eb/N0–N_ref 설계 맵
	•	θ_std_deg ∈ {1°, 3°, 5°, 7°, 10°}
	•	Eb/N0 ∈ {12, 14, 16, 18 dB}
	•	(N_ref, N_data) = (1, 63), (2, 62), (4, 60), (8, 56) 등
→ “P_ref 밀도 vs 허용 위상 노이즈 범위” 표 작성.
	2.	부분 공통 위상 노이즈 / 클러스터 구조
	•	1024 lanes를 16개의 64-lane 타일로 나누고,
	•	타일별로 독립적인 θ(t)를 부여한 뒤,
	•	각 타일당 P_ref = 1인 구조 테스트.
	3.	PAM4 + CoPBit 혼합 아키텍처
	•	Channel-b mid-ISI 환경에서
	•	“기존 PAM4 + DLL/EQ” vs “M8+P_ref+Kuramoto” vs “ILC3/ILC4”
비교표에 Q16 결과를 직접 넣어,
“위상 축을 추가했을 때의 보상(benefit)” 을 시각화.

이 문서는 Q16/Q16b/Q16c/Q16d 실험 기반으로,
Kuramoto PhaseLock_std에서 P_ref의 존재 의미와 최소 개수를 정리한 v0.1 버전이다.
향후 Q17 이후 실험에서는 이 요약을 “PhaseLock_std 설계 기반선(base-line spec)”으로 활용하면 된다.

