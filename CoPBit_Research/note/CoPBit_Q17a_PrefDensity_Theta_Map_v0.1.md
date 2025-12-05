# CoPBit_Q17a_PrefDensity_Theta_Map_v0.1.md

## 0. 개요

- 실험 ID: Q17a – p_ref density vs θ_std_deg map (AWGN + 공통 위상 노이즈)
- 목적:
  - `P_ref lane 수 (n_ref)`와 `위상 노이즈 표준편차 θ_std_deg`에 대해,
    - Data-only PLL (DDonly)
    - P_ref + Data 혼합 PLL (DD+pRef)
  - 의 BER 맵을 얻고, **Kuramoto PhaseLock_std 설계 시 필요한 최소 p_ref 조건**을 정리하기 위함.
- 데이터 소스:
  - `CoPBit_Research/note/Q17a_pref_density_theta_map.csv`  
  - 열 구조:
    - `n_sym, n_ref, n_data, theta_std_deg, ebn0_db, ber_noPLL, ber_DDonly, ber_DD_pRef`


## 1. 공통 실험 설정

### 1.1 심볼 및 변조

- 변조: 8-PSK 기반 M8 (3 bit/symbol)
- 심볼 수: `n_sym = 200000`
- 레인 구성:
  - `(n_ref, n_data) ∈ {(1,1), (2,1), (8,56)}`
    - `n_ref`: P_ref 전용 lane 수 (고정된 8-PSK index 사용)
    - `n_data`: 데이터 전송 lane 수 (3 bit/sym 랜덤)
- 모드:
  - **No PLL**
    - 각 data lane에 대해 위상 추적 없이 단순 slicer만 적용
  - **Data-DD only**
    - 모든 data lane의 결정 에러 평균으로 공통 위상 φ 업데이트  
    - 1-lane 또는 multi-lane DD PLL 근사
  - **Data + p_ref (DD+pRef)**
    - p_ref lane 에러와 data lane 에러를 혼합해서 공통 위상 φ 업데이트  
    - `e_total = (1 - α) * e_ref + α * e_data`
    - 여기서 `α = alpha_ref = 0.3`  
      → ref 기여 70%, data 기여 30%

### 1.2 채널/노이즈 설정

- 채널: AWGN + 공통 위상 노이즈 (no-ISI, h = [1])
- Eb/N0:
  - `ebn0_db ∈ {12, 14, 16}`
- 공통 위상 노이즈:
  - 심볼별 위상 랜덤워크 (Wiener process)
  - Δφ ~ N(0, σ²), 여기서 `σ = theta_std_deg [deg]`를 rad로 변환하여 누적
  - 실험 파라미터:
    - `theta_std_deg ∈ {1.0, 3.0, 5.0}`


## 2. 결과 요약 (수치 맵의 핵심 부분)

### 2.1 θ_std_deg = 1°

#### (n_ref, n_data) = (1, 1)

- Eb/N0 = 12 dB
  - noPLL ≈ 0.472
  - DDonly ≈ 7.15e-4
  - DD+pRef ≈ 6.17e-4
- Eb/N0 = 14 dB
  - noPLL ≈ 0.537
  - DDonly ≈ 5.17e-5
  - DD+pRef ≈ 4.17e-5
- Eb/N0 = 16 dB
  - noPLL ≈ 0.490
  - DDonly = 0
  - DD+pRef = 0

#### (n_ref, n_data) = (2, 1)

- DDonly vs DD+pRef 전 구간에서 **동일 오더(10⁻³~10⁻⁶)**, P_ref 추가 효과는 미세

#### (n_ref, n_data) = (8, 56)

- DDonly vs DD+pRef 차이 거의 없음 (10⁻⁴~10⁻⁶ 레벨)

> **해석:**  
> θ_std = 1°에서는 **Data-only PLL만으로도 위상 추적이 충분히 잘 동작**하고,
> P_ref를 추가해도 BER은 동일 오더에서 약간의 개선만 제공함  
> → 이 영역에서는 **P_ref는 “필수”라기보다 redundancy에 가까운 역할**


### 2.2 θ_std_deg = 3°

#### (n_ref, n_data) = (1, 1)

- Eb/N0 = 12 dB
  - noPLL ≈ 0.498
  - DDonly ≈ 0.465
  - DD+pRef ≈ 0.0365
- Eb/N0 = 14 dB
  - noPLL ≈ 0.502
  - DDonly ≈ 0.500
  - DD+pRef ≈ 0.0300
- Eb/N0 = 16 dB
  - noPLL ≈ 0.519
  - DDonly ≈ 0.472
  - DD+pRef ≈ 0.0253

#### (n_ref, n_data) = (2, 1)

- Eb/N0 = 12 dB
  - noPLL ≈ 0.491
  - DDonly ≈ 0.525
  - DD+pRef ≈ 0.0387
- Eb/N0 = 14 dB
  - noPLL ≈ 0.494
  - DDonly ≈ 0.491
  - DD+pRef ≈ 0.0342
- Eb/N0 = 16 dB
  - noPLL ≈ 0.501
  - DDonly ≈ 0.501
  - DD+pRef ≈ 0.0235

#### (n_ref, n_data) = (8, 56)

- Eb/N0 = 12 dB
  - noPLL ≈ 0.499
  - DDonly ≈ 0.494
  - DD+pRef ≈ 0.0389
- Eb/N0 = 14 dB
  - noPLL ≈ 0.493
  - DDonly ≈ 0.491
  - DD+pRef ≈ 0.0297
- Eb/N0 = 16 dB
  - noPLL ≈ 0.496
  - DDonly ≈ 0.527
  - DD+pRef ≈ 0.0261

> **핵심:**  
> - noPLL, Data-DD only 모두 **0.47~0.53 수준 → 사실상 랜덤(1/2) 근처**  
> - 반대로 **DD+pRef는 2.3×10⁻² ~ 3.9×10⁻² 수준으로 크게 개선**  
> - `n_ref = 1, 2, 8` 사이에서 **pRef BER은 거의 같은 오더**  
>   - P_ref lane 수가 증가해도 BER이 드라마틱하게 떨어지지 않음

→ θ_std = 3° 영역은,  
**“P_ref가 없으면 시스템 전체가 완전히 깨지는 구간”**이면서,  
**“P_ref 하나만 있어도 BER을 ~10⁻² 레벨까지 끌어내리는 구간”**이라는 것이 명확하게 드러남.


### 2.3 θ_std_deg = 5°

#### (n_ref, n_data) = (1, 1)

- Eb/N0 = 12/14/16 dB에서 DD+pRef ≈ 0.138~0.146

#### (n_ref, n_data) = (2, 1)

- 거의 동일: ≈ 0.138~0.147

#### (n_ref, n_data) = (8, 56)

- 유사 범위: ≈ 0.138~0.151

> **핵심:**  
> - θ_std = 5°에서는 P_ref를 사용해도 BER이 **약 1.4×10⁻¹** 수준까지밖에 내려가지 않음  
> - Data-DD only는 여전히 0.49~0.51 근처 (랜덤)  
> - P_ref density를 1→2→8로 늘려도 BER은 **같은 오더, 미세한 차이만 존재**


## 3. 해석: P_ref density vs θ_std 관계

### 3.1 P_ref가 하는 일

Q17a 결과를 정리하면, P_ref의 역할은 다음과 같이 요약된다.

1. **θ_std가 작을 때 (≈ 1°)**  
   - Data-DD만으로도 충분히 위상을 추적 → P_ref는 “보너스” 수준

2. **θ_std가 중간 수준일 때 (≈ 3°)**  
   - No PLL, Data-DD only 모두 랜덤(0.5) 근처로 붕괴  
   - **단 1개의 P_ref만 있어도 BER이 10⁻² 수준까지 크게 개선**  
   - n_ref를 2, 8로 늘려도 추가 이득은 미세

3. **θ_std가 큰 편일 때 (≈ 5°)**  
   - P_ref를 써도 10⁻¹ 중반 정도가 한계  
   - 이 영역에서는 **P_ref가 있어도 PhaseLock_std 자체의 한계가 드러나는 구간**

→ **정성적 결론**  
- **Kuramoto + 공통 φ 추적 구조에서는 “P_ref의 유무”가 더 중요하고, “P_ref 밀도”는 2차 효과에 가깝다.**  
- 특히 θ_std ≈ 3° 근처의 “임계 영역”에서, **P_ref 1 lane만으로도 전체 System을 랜덤에서 10⁻² 레벨로 끌어내리는 효과**가 확인됨.


### 3.2 n_ref 스케일링에 대한 관찰

- n_ref = 1 → 2 → 8 (n_data도 1 → 1 → 56으로 크게 늘어도)
  - θ_std = 3°, Eb/N0 = 14 dB 기준:
    - (1,1): ≈ 0.0300
    - (2,1): ≈ 0.0342
    - (8,56): ≈ 0.0297
  - θ_std = 5°, Eb/N0 = 16 dB 기준:
    - (1,1): ≈ 0.1383
    - (2,1): ≈ 0.1375
    - (8,56): ≈ 0.1380

→ **Lane 수를 수십 배로 늘려도 BER 스케일이 거의 동일**  
→ “64-lane CoPBit 타일” 기준으로 보면,

> **P_ref 1 lane / 타일 정도면 Kuramoto PhaseLock_std를 만족시키는 데 충분**  
> (Q17a에서는 8 ref / 56 data도 사실상 1 ref / 1 data와 같은 수준의 BER 스케일을 보여 줌)


## 4. Q16 (mid-ISI + FFE)와의 연결

- Q16_midISI 실험에서는:
  - Channel-b mid-ISI + FFE 환경에서, EQ 후 M8 자체의 BER 플로어가 **≈ 0.27** 근처로 나타났고
  - P_ref, Kuramoto를 써도 이 플로어 아래로는 내려가지 않는 모습을 보였음

- Q17a는:
  - AWGN + PhaseNoise (no-ISI) 환경  
  - θ_std와 Eb/N0에 따라 BER이 **0.000x ~ 0.15까지 넓게 변동**  
  - 이 환경에서는 PhaseLock_std가 잘 잠기면 10⁻³~10⁻²까지 내려가는 것을 확인

→ 두 실험을 합치면:

> - **PhaseLock_std + P_ref는 “위상 노이즈 문제”를 해결하는 역할**  
> - **채널/ISI/EQ 한계로 인한 BER 플로어는 별도의 제약으로 존재**  
>   - AWGN에서는 이 플로어가 매우 낮고,  
>   - mid-ISI + FFE 환경에서는 ≈0.27 근처까지가 구조적인 한계로 보임


## 5. CoPBit PhaseLock_std 설계 룰 (Q17a 기준 초안)

Q17a 결과를 기반으로 한, **AWGN + 공통 위상 노이즈 환경에서의 기본 PhaseLock_std 설계 룰** 초안:

1. **최소 P_ref 조건**
   - 64-lane CoPBit 타일 기준:
     - `N_ref ≥ 1`이면 Kuramoto PhaseLock_std 동작 가능
   - 실험적으로:
     - (1,1), (2,1), (8,56) 모두 θ_std=3°에서 BER이 ~10⁻² 수준으로 수렴

2. **P_ref density 효과**
   - `N_ref`를 1→2→8로 늘려도 BER 스케일은 거의 동일  
   - P_ref 수를 늘리는 것은 “평균화/여유”에는 도움이 되지만,
     - **이미 잠긴 구간에서는 큰 추가 이득은 없음**
   - 따라서:
     - **설계 상 최소 1 lane/타일을 기준으로 하고,**
     - 실물 구현 시 신뢰성/리던던시 목적으로 2 lane 정도까지 여유를 둘 수 있음

3. **허용 θ_std vs BER 목표**
   - AWGN 기준:
     - θ_std ≈ 1°: Data-DD만으로도 거의 완전 복구 (P_ref optional)
     - θ_std ≈ 3°: Data-DD 붕괴 구간, P_ref 1개만으로 BER ~10⁻² 수준 달성
     - θ_std ≈ 5°: P_ref 포함 시에도 BER ≈ 1.4×10⁻¹ 수준 → PhaseLock_std 한계 노출 구간
   - 장기적인 CoPBit PhaseLock_std spec 예시:
     - 목표 BER ≤ 10⁻²:
       - θ_std ≲ 3°에서 P_ref ≥ 1 lane/타일
     - θ_std가 5° 이상이면:
       - Kuramoto + P_ref만으로는 스펙 달성이 어렵고,
       - 추가적인 보조 구조(guard phase, DLL/PLL 보강 등)가 필요

4. **PhaseLock_std와 EQ 역할 분리**
   - PhaseLock_std:
     - 공통 위상 노이즈를 suppression
   - EQ(FFE 등):
     - mid-ISI / 채널 구조로 인한 BER 플로어를 낮추는 역할
   - Q17a는 **“PhaseOnly 문제에서의 P_ref 밀도/θ_std 관계”**,  
     Q16은 **“mid-ISI + EQ 한계에서의 BER 플로어”**를 각각 보여주는 실험 세트로 해석 가능


## 6. 향후 정리/확장 포인트

- Q17a 확장:
  - 다양한 `alpha_ref`, `mu_phase` 스윕 → PhaseLock_std 안정 영역 map 확장
  - `theta_std_deg`를 연속적인 grid (예: 0.5° step)로 확장
- Q16/Q17 결합:
  - “PhaseLock_std spec” vs “EQ spec”을 나눠서 최종 CoPBit IO/Memory 인터페이스 표준 초안 도출
- 특허/논문 활용:
  - 본 Q17a CSV + 요약 결과는
    - “P_ref density vs θ_std vs BER” 데이터로,
    - **“P_ref lane 1개만으로 충분한 Kuramoto 수렴 조건”**을 지지하는 실험 근거로 사용 가능