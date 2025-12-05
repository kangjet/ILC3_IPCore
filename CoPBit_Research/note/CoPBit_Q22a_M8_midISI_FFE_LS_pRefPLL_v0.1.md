# CoPBit Q22a – M8 mid-ISI + FFE(LS) + 공통 위상 노이즈 + p_ref PLL v0.1
- 날짜: 2025-12-05
- 태그: CoPBit, Q22a, mid-ISI, M8, FFE-LS, p_ref, PhaseLock_std, Memory/Bus

---

## 1. 목적

- **목표**  
  - Channel-b mid-ISI + FFE(LS) + AWGN 환경에서  
    **2-lane (1 p_ref + 1 data) CoPBit M8 링크의 위상 노이즈 내성**을 확인.
  - 특히,  
    - 심볼당 위상 랜덤 워크 표준편차 θ_std[deg] = 0, 1, 3, 5 조건에서  
    - `No PLL`, `Data-DD only`, `Data + p_ref` 구조의 BER을 비교.
  - 메모리/데이터버스 용 CoPBit에서  
    **“θ_std ≤ 1° 조건에서 p_ref 1개로 충분히 동작 가능한지”**를 확인하는 것이 핵심.

---

## 2. 실험 설정

### 2.1 스크립트 / 커맨드

- 스크립트:
  - `copbit_q22a_m8_midISI_pref_phase_ls_v0.py`

- 실행 커맨드 (예시):

```bash
python copbit_q22a_m8_midISI_pref_phase_ls_v0.py \
  --n_sym 200000 \
  --ebn0_list "12,14,16" \
  --theta_std_list "0,1,3,5" \
  --ffe_len 11 \
  --train_frac 0.5 \
  --mu_phase 0.05 \
  --alpha_ref 0.3 \
  --seed 1
```

### 2.2 공통 파라미터

- 심볼 수
  - `n_sym = 200000`
- 변조
  - `M8 (8-PSK)`, `BITS_PER_SYM = 3`
- Eb/N0 리스트
  - `[12, 14, 16] dB`
- 위상 노이즈 (Wiener, per-symbol 랜덤 워크)
  - `theta_std_list = [0, 1, 3, 5] (deg)`
  - `Δφ[n] ~ N(0, σ²)`, `σ = θ_std_deg × π/180`
  - `φ[n] = φ[n-1] + Δφ[n]`
- FFE(LS)
  - 공통 FFE, **data lane 기준** LS 고정 계수
  - `ffe_len = 11`
  - `train_frac = 0.5` (앞 50% 구간으로 LS 학습)
  - `ridge = 1e-6` (수치 안정성용 정규화 항)
- PLL
  - `mu_phase = 0.05`
  - `alpha_ref = 0.3`
  - `e_total = (1-α)·e_ref + α·e_data`
  - Lane0 = p_ref lane (`k_ref_const = 0`, 고정 8-PSK 심볼)
  - Lane1 = data lane (3bit/sym 랜덤)

### 2.3 채널 / 수신 구조

- 채널: Channel-b mid-ISI (실험 시점 기준)

```text
h_midISI = [0.05, 0.2, 0.5, 0.2, 0.05]
∑h = 1.0 (정규화)
```

- 수신 구조:

```text
Tx(M8, 2-lane: p_ref + data)
  → Channel-b mid-ISI
  → AWGN (Eb/N0 기반)
  → 공통 FFE(LS, data lane 기준 학습)
  → 공통 위상 노이즈 φ[n] (Wiener)
  → 2-lane 공통 PLL
      · No PLL      : slicer만
      · Data-DD only: data lane 에러만 반영
      · Data+p_ref  : p_ref + data 에러 혼합 (alpha_ref)
```

---

## 3. 결과 – θ_std 별 BER

### 3.1 θ_std = 0°  (위상 노이즈 없음, mid-ISI + FFE + AWGN만 존재)

> FFE(LS) + AWGN + mid-ISI 환경의 **“제대로 동작하는 baseline”** 확인용

```text
=== Q22a (theta_std_deg = 0.0) ===
===============================================================
 Eb/N0_dB |  BER_noPLL   |  BER_DDonly  |  BER_DD+pRef
---------------------------------------------------------------
     12.0 |     0.024165 |     0.026175 |     0.024843
     14.0 |     0.006470 |     0.007067 |     0.006645
     16.0 |     0.000880 |     0.001042 |     0.000945
---------------------------------------------------------------
```

- 해석
  - θ = 0°에서는 **No PLL / Data-DD / Data+p_ref 모두 거의 동일한 성능**.
  - 16 dB에서 BER ≈ 8.8×10⁻⁴ ~ 1.0×10⁻³ 수준.
  - 즉, **mid-ISI + FFE(LS)만으로도 메모리/버스용에서 의미 있는 baseline**을 달성.

---

### 3.2 θ_std = 1°

```text
=== Q22a (theta_std_deg = 1.0) ===
===============================================================
 Eb/N0_dB |  BER_noPLL   |  BER_DDonly  |  BER_DD+pRef
---------------------------------------------------------------
     12.0 |     0.517397 |     0.584893 |     0.030160
     14.0 |     0.500415 |     0.548373 |     0.009817
     16.0 |     0.490127 |     0.491890 |     0.002112
---------------------------------------------------------------
```

- 핵심 포인트
  - **No PLL / Data-DD only**는 거의 완전히 깨져서 BER ~ 0.49~0.58 (랜덤 수준).
  - **Data + p_ref PLL**:
    - 12 dB: BER ≈ 3.0×10⁻²
    - 14 dB: BER ≈ 9.8×10⁻³
    - 16 dB: BER ≈ 2.1×10⁻³
  - 즉, **같은 θ_std = 1° 조건에서도 p_ref 1개만으로 mid-ISI + FFE 환경을 다시 “실용 영역”으로 복구**.

---

### 3.3 θ_std = 3°

```text
=== Q22a (theta_std_deg = 3.0) ===
===============================================================
 Eb/N0_dB |  BER_noPLL   |  BER_DDonly  |  BER_DD+pRef
---------------------------------------------------------------
     12.0 |     0.502205 |     0.495083 |     0.086100
     14.0 |     0.494510 |     0.495737 |     0.061820
     16.0 |     0.506477 |     0.472018 |     0.045332
---------------------------------------------------------------
```

- 해석
  - No PLL / Data-DD only: 여전히 **0.47~0.50 수준** (랜덤에 가깝게 망가짐).
  - Data + p_ref:
    - 12 dB: ≈ 8.6×10⁻²
    - 14 dB: ≈ 6.2×10⁻²
    - 16 dB: ≈ 4.5×10⁻²
  - θ = 3°에서는 p_ref가 있어도 **10⁻² 이하까지는 잘 못 떨어지고**,  
    **대략 10⁻¹~10⁻² 중간 정도에 머무는 수준**.

---

### 3.4 θ_std = 5°

```text
=== Q22a (theta_std_deg = 5.0) ===
===============================================================
 Eb/N0_dB |  BER_noPLL   |  BER_DDonly  |  BER_DD+pRef
---------------------------------------------------------------
     12.0 |     0.489127 |     0.492425 |     0.175465
     14.0 |     0.492063 |     0.493643 |     0.162365
     16.0 |     0.501453 |     0.496503 |     0.155225
---------------------------------------------------------------
```

- 해석
  - θ = 5°에서는 p_ref가 있어도 **BER ≈ 0.15~0.18 수준**에서 더 이상 내려가지 않음.
  - 이 영역은 사실상 **“위상 노이즈가 너무 심해서 1-lane p_ref PLL로는 메모리/버스 스펙에 적합하지 않은 구간”**으로 볼 수 있음.

---

## 4. 종합 해석 – 메모리/버스용 CoPBit 관점

1. **mid-ISI + FFE(LS) baseline (θ = 0°)**
   - 채널-b + FFE(LS)만 있을 때, 16 dB에서 BER ≈ 10⁻³ 수준 달성.  
   - 이미 **“메모리/버스용 equalized PAM 계열”과 동급 레벨의 기준선**.

2. **위상 노이즈 θ_std = 1°에서 p_ref 역할**
   - Data-DD only / No PLL는 완전 붕괴 (BER ~ 0.5).
   - 단일 p_ref lane 기반 PLL만 추가해도:
     - 12 dB → ≈ 3×10⁻²
     - 14 dB → ≈ 1×10⁻²
     - 16 dB → ≈ 2×10⁻³
   - 따라서, **“mid-ISI + FFE + θ_std ≈ 1° 공통 위상 노이즈”라는 꽤 빡센 조건에서도, CoPBit는 p_ref 1개로 충분히 PhaseLock_std(메모리/버스용) 수준 달성이 가능**하다고 볼 수 있음.

3. **위상 노이즈 허용 범위 (PhaseLock_std 관점)**
   - θ_std ≈ 1°: **실용 단계** (BER ~ 10⁻²~10⁻³)
   - θ_std ≈ 3°: p_ref 있어도 **10⁻¹~10⁻² 사이에 머무는 과도기 영역**
   - θ_std ≈ 5°: 메모리/버스 용도 기준으로는 **과도한 위상 난조** –  
     추가 설계(PLL 강화, 더 많은 p_ref, HW 스펙 업)가 필요할 영역

4. **설계 관점 정리**
   - 근거리 메모리/버스/PPU 인터커넥트용 CoPBit에서:
     - 하드웨어 PLL + 클럭 설계로 residual θ_std를 **~1° 이하**로 잡는 것이  
       현실적인 타깃으로 설정 가능.
     - 이때, p_ref lane 1개만 추가해도 mid-ISI + AWGN 환경에서  
       **“메모리/버스용 BER 요구 (pre-FEC 10⁻³~10⁻⁴ 수준) 근처까지 끌어올릴 수 있는 구조”**라는 것을 Q22a가 보여줌.
## 4. θ_std 미세 스윕 @ 16 dB (Q22a_thetaFine_16dB.log)

### 4.1 실험 조건 정리

- 시뮬 이름: Q22a – M8 mid-ISI + FFE(LS) + 공통 위상 노이즈 + p_ref PLL
- 채널: mid-ISI (Channel-b 축약형)
  - h_midISI (norm) = [0.05, 0.2, 0.5, 0.2, 0.05]
- 변조: 단일 lane M8 (8-PSK, 3 bit/sym)
  - Lane0: p_ref lane (고정 8-PSK index)
  - Lane1: data lane (3bit/sym 랜덤 데이터)
- Rx 구조:
  1) mid-ISI + AWGN
  2) 공통 FFE (M8 기준, LS 고정 계수)
  3) 공통 위상 노이즈 (Wiener process, θ_std_deg)
  4) 공통 PLL (NoPLL / Data-DD only / Data+p_ref 비교)
- 공통 파라미터:
  - n_sym      = 500,000
  - Eb/N0_list = [16 dB] (고정)
  - theta_std_deg sweep = [0.0, 0.2, 0.5, 0.8, 1.0, 1.2, 1.5, 2.0]
  - ffe_len    = 11
  - train_frac = 0.5
  - mu_phase   = 0.05
  - alpha_ref  = 0.3  (0 → p_ref-only, 1 → data-only)
  - seed       = 1

### 4.2 결과 표 (Eb/N0 = 16 dB 고정)

| θ_std_deg | BER_noPLL | BER_Data-DD only | BER_Data+p_ref |
|:---------:|----------:|-----------------:|---------------:|
| 0.0       | 0.000796  | 0.000947         | 0.000807       |
| 0.2       | 0.468736  | 0.001018         | 0.000923       |
| 0.5       | 0.471627  | 0.001217         | 0.001101       |
| 0.8       | 0.503039  | 0.001729         | 0.001538       |
| 1.0       | 0.473557  | 0.002569         | 0.002208       |
| 1.2       | 0.478852  | 0.321099         | 0.003005       |
| 1.5       | 0.478531  | 0.491445         | 0.005102       |
| 2.0       | 0.505451  | 0.496043         | 0.012035       |

### 4.3 해석 포인트

1. **No PLL (위상 추적 없음)**
   - θ_std_deg ≥ 0.2°부터 바로 BER ≈ 0.47~0.50 수준으로 **완전히 깨진 상태**.
   - mid-ISI + AWGN + 위상 드리프트 환경에서, 위상 추적이 없으면 사실상 random guess 상태가 됨.

2. **Data-DD only (데이터 레인만 보고 PLL)**
   - θ_std_deg ≤ 0.8° 구간: BER ≈ 1e-3 ~ 2e-3 수준으로 그럭저럭 동작.
   - θ_std_deg = 1.0°에서는 BER ≈ 2.57e-3.
   - θ_std_deg = 1.2°에서 **갑자기 BER ≈ 0.32**로 튀면서 PLL이 불안정/슬립 구간에 진입.
   - θ_std_deg ≥ 1.5°에서는 다시 BER ≈ 0.49~0.50 → 사실상 lock 실패.

3. **Data + p_ref (p_ref + data 혼합 에러로 PLL)**
   - θ_std_deg = 0.0°: BER ≈ 8e-4 로 NoPLL/데이터 only와 거의 동일(위상 노이즈가 없으니 당연).
   - θ_std_deg = 0.2° ~ 1.0°:
     - BER 범위: **9.23e-4 ~ 2.21e-3**.
     - 특히 0.2°~0.8° 구간에서는 **1e-3 레벨 근처**에서 안정적으로 유지.
   - θ_std_deg = 1.2°:
     - Data-DD only는 이미 0.32로 붕괴했지만,
     - Data+p_ref는 여전히 BER ≈ 3.0e-3 수준으로 **락 유지**.
   - θ_std_deg = 1.5° ~ 2.0°:
     - BER ≈ 5.1e-3 → 1.2e-2 수준으로 서서히 열화되지만,
     - 여전히 NoPLL(≈0.5)나 Data-DD only(≈0.49) 대비 **압도적으로 우수**.

### 4.4 CoPBit PhaseLock_std 관점에서 정리

- **PhaseLock_std(16 dB, mid-ISI, LS FFE)** 를 “BER ≈ 1e-3 레벨 유지 가능한 θ_std 범위”로 정의하면:
  - θ_std_deg ≈ **0.5° 부근**에서 BER ≈ 1.1e-3.
  - θ_std_deg ≈ 0.8°에서 BER ≈ 1.5e-3.
  - ⇒ 실질적인 **“1e-3급 안전 영역”은 θ_std_deg ≈ 0.5°~0.7° 근방**으로 보는 것이 합리적.
- **θ_std_deg ≈ 1.0°**에서는 BER ≈ 2.2e-3 수준:
  - 여전히 실용적인 메모리/버스 관점에서 “사용 가능한 영역”이지만,
  - “1e-3 strict spec” 보다는 살짝 위에 올라간 값.
- Data-DD only vs Data+p_ref 비교:
  - θ_std_deg ≥ 1.2°에서 Data-DD only PLL은 사실상 붕괴(0.32 → 0.49),
  - 반면 Data+p_ref는 θ_std_deg = 1.2°에서 BER ≈ 3.0e-3로 **아직도 CoPBit로 쓸 수 있는 레벨**.
  - ⇒ **“Kuramoto + p_ref 한 축만으로도, mid-ISI + FFE + AWGN 환경에서 위상 노이즈 허용 범위를 1°대 초반까지 밀어 올려 준다”**고 해석 가능.

### 4.5 설계 관점 요약 (PPU / 메모리 & 버스용 CoPBit)

- 이 테스트는 **“PPU/메모리 환경에서, CoPBit lane이 mid-ISI + FFE 조건에서도 θ_std 몇 도까지 버티는가?”**를 보는 실험.
- 16 dB, mid-ISI, FFE(LS 고정) 환경에서:
  - **p_ref 1 lane + data 1 lane 구조만으로도**:
    - θ_std ≲ 0.7° → BER ≲ 1e-3
    - θ_std ≲ 1.0° → BER ≲ 3e-3
    - θ_std ≲ 2.0° → BER ≲ 1.2e-2
- 이는:
  - PPU(초근거리, 짧은 인터커넥트)를 가정하면,
  - **실제 설계에서 θ_std를 0.5°~1° 영역에 집어넣을 수만 있다면, CoPBit 메모리/버스 모드도 충분히 실현 가능한 수준**임을 보여 줌.
- 한 줄 요약:
  > “mid-ISI + FFE + AWGN 환경에서도, **단 1개의 p_ref lane 기준축만으로** Kuramoto 스타일 CoPBit 위상 잠금이 0.5°~1° 수준의 위상 노이즈를 견딜 수 있다는 것을 Q22a가 정량적으로 보여준다.”


## 5. 메모 / 다음 스텝 아이디어

- **단계별 정리 포인트**
  1. Q20c/Q21 계열: PAM4 vs M8, mid-ISI + FFE baseline 정리 (메모리/버스용 기준선).
  2. Q22a: baseline 위에 공통 위상 노이즈 + 2-lane(p_ref + data) CoPBit 구조를 올려서  
     θ_std vs BER 맵을 확인.
  3. 이 결과를 기반으로 **“CoPBit PhaseLock_std 모드”에서의 설계 조건**:
     - θ_std (residual) ≤ 1°
     - Eb/N0 ~ 16 dB 근방 → BER ~ 10⁻³
     - p_ref density: 최소 1 lane 기준으로도 충분 (multi-lane에서도 p_ref = 1로 설계 가능)

- **다음 가능한 실험/정리**
  - “Q22a_thetaFine(16 dB) 결과를 바탕으로, 다른 Eb/N0 (예: 14 dB, 18 dB)에서도 θ_std 세부 스윕을. 
     수행해 θ_crit.(Eb/N0) 맵을 확장.”
  - 64-lane 확장(Q13/Q14 스타일)으로, N_lane → ∞에서  
    **p_ref 1개 vs 다수 p_ref 비교**를 재확인.
  - 이 결과를 종합해서 `CoPBit_PhaseLock_std_Mode_v0.x` 설계 문서에  
    **“메모리/버스용 CoPBit 권장 스펙 (θ_std, Eb/N0, p_ref density)”**를 표 형태로 정리.

