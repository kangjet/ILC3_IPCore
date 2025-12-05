# CoPBit Q16c – Multi-lane p_ref + data (AWGN + 공통 위상 노이즈) v0.1

## 1. 실험 목적

- CoPBit 다중 레인 구조에서 **p_ref lane 수(N_ref)** 를 바꿔 가며,
  공통 위상 노이즈(θ_std_deg) 환경에서:
  - No PLL
  - Data-DD only (data lane만 보고 PLL)
  - Data + p_ref (p_ref + data 혼합 에러)
  의 **BER 차이**를 확인.
- 특히 Q13/Q14의 64-lane Kuramoto 구조를  
  AWGN + phase-noise 기준으로 단순화한 **“최소 CoPBit PLL 모델”** 로 보고,
  “필요한 p_ref 밀도 vs θ_std_deg” 설계 근거를 확보하는 것이 목표.

---

## 2. 공통 파라미터

- 변조: M8 (8-PSK, 3bit/symbol)
- bits/symbol: 3
- 채널: no-ISI (h = [1])
- 공통 위상 노이즈:
  - Δφ ~ N(0, σ²), θ_std_deg = 3°
  - σ = θ_std_deg[deg] × π/180, 누적(Wiener process)로 φ[k] 생성
- AWGN: Eb/N0 basis, Es/No 변환 후 복소 가우시안 잡음 추가
- PLL 업데이트:
  - φ_hat ← φ_hat + μ_phase · e
  - e_ref  = angle(z_ref · conj(s_ref_const))
  - e_data = angle(z_data · conj(s_data_hat))
  - e_total = (1−α_ref)·mean(e_ref) + α_ref·mean(e_data)
- 파라미터:
  - n_sym = 200,000
  - Eb/N0_list = [12, 14, 16] dB
  - theta_std_deg = 3.0
  - mu_phase = 0.05
  - alpha_ref = 0.3  (0 → ref-only, 1 → data-only)
  - seed = 1

---

## 3. PLL 모드 정의

- **No PLL**
  - 각 data lane 별로 `z = y_noisy` 에 바로 8-PSK slicer 적용
  - 공통 위상 추적 없음
- **Data-DD only**
  - 모든 data lane의 결정 심볼 `s_data_hat` vs 보정 후 샘플 `z_data` 로
    위상 에러 e_data 추정
  - e_mean = mean(e_data), φ_hat ← φ_hat + μ_phase · e_mean
- **Data + p_ref**
  - p_ref lane:
    - `z_ref = y_ref_noisy · exp(-j φ_hat)`
    - 기준축 `s_ref_const` (고정 index)와 비교해 e_ref 추정
  - data lane:
    - `z_data = y_data_noisy · exp(-j φ_hat)`
    - slicer→s_data_hat 후 e_data 추정
  - 혼합 에러:
    - e_total = (1−α_ref)·mean(e_ref) + α_ref·mean(e_data)
    - φ_hat ← φ_hat + μ_phase · e_total

---

## 4. 실험 케이스

### 4.1 Case A – N_ref=1, N_data=1 (2-lane, Q16 대응)

- 구조: 1 p_ref + 1 data

| Eb/N0(dB) | BER_noPLL | BER_DDonly | BER_DD+pRef |
|-----------|-----------|-----------:|------------:|
| 12        | 0.502892  | 0.502435   | **0.038290** |
| 14        | 0.506680  | 0.526752   | **0.030457** |
| 16        | 0.495850  | 0.496502   | **0.026723** |

**코멘트**

- No PLL, Data-DD only 모두 BER ≈ 0.5 수준 → 공통 위상 노이즈에 완전히 깨짐.
- p_ref를 이용한 Data+pRef 모드는 같은 조건에서 **BER ≈ 2.7%~3.8%** 수준으로 회복.
- θ_std=3° 기준에서는, 2-lane 구조라도 “p_ref + PLL”이 있으면  
  사실상 **AWGN-limited 영역**까지 개선되는 것으로 볼 수 있음.

---

### 4.2 Case B – N_ref=2, N_data=1 (3-lane, Q16b 대응)

- 구조: 2 p_ref + 1 data

| Eb/N0(dB) | BER_noPLL | BER_DDonly | BER_DD+pRef |
|-----------|-----------|-----------:|------------:|
| 12        | 0.502870  | 0.496832   | **0.038587** |
| 14        | 0.499177  | 0.470420   | **0.031093** |
| 16        | 0.499032  | 0.488550   | **0.026295** |

**코멘트**

- p_ref lane을 2개로 늘려도, θ_std=3°에서는  
  **BER_DD+pRef가 Case A와 거의 동일한 수준**에 머무름.
- 이 조건에서는 p_ref=1개만 있어도 위상추적 성능이 이미 충분하고,  
  p_ref를 2개로 늘려도 추가 이득이 미세한 수준이라는 것을 의미.

---

### 4.3 Case C – N_ref=8, N_data=56 (64-lane 근사)

- 구조: 8 p_ref + 56 data (총 64 lanes 근사 구조)

| Eb/N0(dB) | BER_noPLL | BER_DDonly | BER_DD+pRef |
|-----------|-----------|-----------:|------------:|
| 12        | 0.511040  | 0.528489   | **0.037096** |
| 14        | 0.490489  | 0.481028   | **0.029671** |
| 16        | 0.511546  | 0.499190   | **0.026522** |

**코멘트**

- lane 수를 64 근처까지 늘린 상태에서도,
  - No PLL, Data-DD only는 여전히 0.48~0.53 수준에서 헤맴.
  - Data+pRef는 **Eb/N0=12~16 dB에서 2.6~3.7% 수준**으로 안정.
- AWGN + θ_std=3° 환경에서는,
  - “64-lane CoPBit 구조에 대해 N_ref=8(12.5%) 정도면 충분히 안정된 공통 PLL”을 구현 가능.
  - 실제로는 N_ref를 더 줄여도(예: N_ref=1~2) 거의 비슷한 BER →  
    **p_ref 밀도는 이보다 훨씬 낮게 잡을 여지가 있음.**

---

## 5. 설계 관점 요약 (AWGN + θ_std=3° 기준)

1. **Data-DD only PLL는 공통 위상 노이즈에 거의 무력**  
   - N_data가 늘어도, 공통 φ를 제대로 잡지 못해 BER ≈ 0.5 근처.

2. **p_ref lane이 1개만 있어도 큰 개선**  
   - (1,1), (2,1), (8,56) 모든 케이스에서 Data+pRef BER이  
     거의 동일 수준(≈ 0.03)까지 떨어짐.
   - 이 구간에서는 위상 노이즈가 아니라 **AWGN이 지배적인 에러 소스**가 됨.

3. **AWGN 기준 CoPBit 설계 힌트 (초안)**  
   - θ_std_deg = 3°, Eb/N0≥12 dB 수준에서는  
     - CoPBit 64-lane 그룹당 **p_ref lane 1개만 두어도**  
       공통 위상 노이즈는 충분히 보정 가능할 것으로 추정.
   - 더 큰 θ_std_deg(예: 5°, 10°)에서는  
     - N_ref, α_ref, μ_phase를 조절하면서  
       “필요한 p_ref 밀도 vs θ_std_deg” 곡선을 얻을 수 있음.
   - 이 파일(Q16c v0.1)은 **AWGN + phase-noise 기준 교과서 모델**로 사용하고,  
     mid-ISI + EQ (Q13/Q14 채널-b 내부) 실험 결과와 연결해서  
     최종 CoPBit 설계 수식으로 확장할 계획.

---

## 6. 다음 단계 (Plan)

1. **AWGN 결과 고정**
   - Q16, Q16b, Q16c(멀티레인) 결과를 하나의 표로 통합해서  
     “AWGN + θ_std 기준 설계 포인트”로 고정.
2. **mid-ISI + EQ 환경으로 확장 (채널-b 내부)**
   - Q16_midISI / Q13 / Q14에서 썼던 mid-ISI(채널-b) + FFE 구조에  
     지금의 p_ref PLL 구조를 그대로 이식.
   - `(N_ref, N_data) = (1,1), (2,1), (8,56)` 정도만 우선 실행해  
     “ISI + EQ 잔차가 있을 때 p_ref가 어느 정도까지 버티는지”를 확인.
3. **최종 CoPBit 설계 수식 정리**
   - θ_std_deg, N_ref/N_total, Eb/N0, 채널-ISI 강도(채널-b/c)까지 포함해서  
     “주어진 채널/PLL 조건에서 필요한 p_ref 밀도”를 설계 수식 or 규칙으로 정리.