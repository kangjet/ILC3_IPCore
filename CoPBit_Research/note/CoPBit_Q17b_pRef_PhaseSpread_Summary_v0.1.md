# CoPBit Q17b – p_ref Phase Spread(spread8) Summary v0.1

## 0. 파일 정보

- 실험 로그 CSV  
  - `Q17b_pref_phase_spread_map.csv`
- 실험 이름  
  - Q17b: `p_ref phase spread (spread8) vs aligned p_ref`
- 목적  
  - Q17a에서 사용한 **단일 기준 위상 p_ref** 대신,  
    **위상을 서로 다르게 분산(spread)시킨 p_ref**를 사용했을 때
    PhaseLock_std 성능이 좋아지는지 / 달라지는지 확인.

---

## 1. 실험 개요

### 1.1 공통 설정

- 변조: M8 (3 bit / symbol)
- 심벌 수:  
  - `n_sym = 200000`
- 위상 노이즈 (공통 위상)  
  - Wiener process  
  - `theta_std_deg ∈ {1°, 3°, 5°}`
- Eb/N0:
  - `EbN0_dB ∈ {12, 14, 16}`
- 채널:
  - AWGN only (no-ISI, h = [1])  
- PLL 모드
  - **No PLL**: 각 data lane에 slicer만 적용 (공통 φ 추적 없음)
  - **Data-DD only**: data lane 에러만 평균해서 공통 φ 업데이트
  - **Data + p_ref**:  
    - p_ref lane 에러 + data lane 에러 혼합  
    - `total_err = (1-α)·err_ref + α·err_data`
    - `alpha_ref = 0.3`
- p_ref Phase spread 모드
  - `pref_mode = "spread8"`
  - p_ref lane들이 **8-way 균등 위상 분포**를 갖도록 배치  
    (예: 0°, 45°, 90°, …, 315° / 그 중 n_ref개 사용)

---

## 2. 파라미터 스윕 구조

CSV 컬럼:

- `n_sym, n_ref, n_data, theta_std_deg, ebn0_db, pref_mode, ber_noPLL, ber_DDonly, ber_DD_pRef`

스윕 조합:

- Lane 구조:
  - `(n_ref, n_data) = (1, 1)`  
  - `(n_ref, n_data) = (2, 1)`  
  - `(n_ref, n_data) = (8, 56)`  (총 64 lanes, Q13/Q14와 대응)
- 위상 노이즈 표준편차:
  - `theta_std_deg ∈ {1.0, 3.0, 5.0}`
- Eb/N0:
  - `EbN0_dB ∈ {12.0, 14.0, 16.0}`
- pref_mode:
  - 전부 `"spread8"` (위상 분산 p_ref)

---

## 3. 대표 결과 테이블 (요약)

### 3.1 (n_ref, n_data) = (1, 1), spread8

theta_std_deg = 1°

| Eb/N0(dB) | ber_noPLL | ber_DDonly        | ber_DD_pRef        |
|-----------|-----------|-------------------|--------------------|
| 12        | 0.492145  | 6.83e-04          | 6.23e-04           |
| 14        | 0.488738  | 5.67e-05          | 3.17e-05           |
| 16        | 0.474022  | 3.33e-06          | 1.17e-05           |

theta_std_deg = 3°

| Eb/N0(dB) | ber_noPLL | ber_DDonly | ber_DD_pRef |
|-----------|-----------|------------|-------------|
| 12        | 0.501218  | 0.476252   | 0.036203    |
| 14        | 0.508393  | 0.506513   | 0.030247    |
| 16        | 0.497545  | 0.496770   | 0.027153    |

theta_std_deg = 5°

| Eb/N0(dB) | ber_noPLL | ber_DDonly | ber_DD_pRef |
|-----------|-----------|------------|-------------|
| 12        | 0.510570  | 0.494013   | 0.149910    |
| 14        | 0.508365  | 0.511962   | 0.138897    |
| 16        | 0.509518  | 0.498308   | 0.136185    |

> **관찰:** θ_std_deg=1°/3°/5° 모두에서, `ber_DD_pRef` 값은  
> Q17a(단일 위상 p_ref) 결과와 사실상 동일 수준 (소수점 셋째 자리까지 거의 겹침).

---

### 3.2 (n_ref, n_data) = (2, 1), spread8

theta_std_deg = 1°

| Eb/N0(dB) | ber_noPLL | ber_DDonly        | ber_DD_pRef        |
|-----------|-----------|-------------------|--------------------|
| 12        | 0.487617  | 5.72e-04          | 5.42e-04           |
| 14        | 0.460250  | 4.67e-05          | 4.00e-05           |
| 16        | 0.466233  | 0.0              | 0.0                |

theta_std_deg = 3°

| Eb/N0(dB) | ber_noPLL | ber_DDonly | ber_DD_pRef |
|-----------|-----------|------------|-------------|
| 12        | 0.492557  | 0.495652   | 0.039442    |
| 14        | 0.476040  | 0.513638   | 0.030703    |
| 16        | 0.504423  | 0.503130   | 0.028685    |

theta_std_deg = 5°

| Eb/N0(dB) | ber_noPLL | ber_DDonly | ber_DD_pRef |
|-----------|-----------|------------|-------------|
| 12        | 0.499917  | 0.496582   | 0.145837    |
| 14        | 0.495522  | 0.502888   | 0.145377    |
| 16        | 0.502902  | 0.497180   | 0.137713    |

> **관찰:** `(1,1)` 케이스와 거의 같은 수치.  
> p_ref lane를 2개로 늘렸지만, θ_std_deg ≤ 5° 영역에서는  
> BER 측면에서 큰 추가 이득은 보이지 않음.

---

### 3.3 (n_ref, n_data) = (8, 56), spread8

theta_std_deg = 1°

| Eb/N0(dB) | ber_noPLL   | ber_DDonly          | ber_DD_pRef         |
|-----------|-------------|---------------------|---------------------|
| 12        | 0.526180    | 5.28e-04            | 5.17e-04            |
| 14        | 0.530524    | 4.68e-05            | 4.60e-05            |
| 16        | 0.508111    | 5.48e-06            | 5.06e-06            |

theta_std_deg = 3°

| Eb/N0(dB) | ber_noPLL | ber_DDonly | ber_DD_pRef |
|-----------|-----------|------------|-------------|
| 12        | 0.512808  | 0.512441   | 0.036222    |
| 14        | 0.509830  | 0.512544   | 0.031500    |
| 16        | 0.491117  | 0.515677   | 0.028370    |

theta_std_deg = 5°

| Eb/N0(dB) | ber_noPLL | ber_DDonly | ber_DD_pRef |
|-----------|-----------|------------|-------------|
| 12        | 0.502132  | 0.501146   | 0.146048    |
| 14        | 0.499511  | 0.508640   | 0.139831    |
| 16        | 0.495589  | 0.490054   | 0.141509    |

> **관찰:** `(8,56)` 구조(총 64 lanes)에서도 `ber_DD_pRef` 값 패턴은  
> `(1,1)`, `(2,1)` 케이스와 거의 동일.  
> lane 수가 64로 늘어도 **θ_std_deg와 Eb/N0에 대한 p_ref 효과는 동일한 스케일**로 유지됨.

---

## 4. Q17a (aligned p_ref) vs Q17b (spread8 p_ref) 비교 요약

Q17a 결과(단일 기준 위상 p_ref)와 Q17b 결과(phase spread `spread8`)를 비교하면:

- θ_std_deg = 1°:
  - Q17a, Q17b 모두 `BER_DD_pRef ≈ 10^-3 ~ 10^-6` 수준.
  - phase-spread 적용 여부에 따른 차이는 **소수점 3~4째 자리 이하** 수준.
- θ_std_deg = 3°:
  - Q17a: `BER_DD_pRef ≈ 0.036 / 0.030 / 0.028` (Eb/N0 = 12,14,16 dB)  
  - Q17b: `BER_DD_pRef ≈ 0.0362 / 0.0302 / 0.0272` 등으로 **사실상 동일**.
- θ_std_deg = 5°:
  - Q17a, Q17b 모두 `BER_DD_pRef ≈ 0.14 ~ 0.15` 레벨에서 거의 겹침.
- `(n_ref, n_data)`가 `(1,1) → (2,1) → (8,56)`으로 변해도:
  - Q17a vs Q17b 비교 시 **p_ref phase spread에 의한 추가 이득은 관측되지 않음**.

즉, **동일한 위상으로 정렬된 p_ref (aligned p_ref)**와  
**위상을 분산시킨 p_ref (spread8)** 사이에,  
본 실험 범위(θ_std_deg ≤ 5°, AWGN-only)에서는  
**BER 성능 차이가 거의 없다**고 정리할 수 있다.

---

## 5. 설계 관점에서의 해석

### 5.1 CoPBit PhaseLock_std 관점 정리

1. **PhaseLock_std의 핵심은 “p_ref 유무”이지, “p_ref 사이의 위상 분산”이 아니다.**
   - p_ref가 존재하는 것만으로도, 위상 추적에 필요한 “기준 축”이 형성된다.
   - p_ref 위상을 여러 개로 분산(spread)시켜도,  
     현재 실험 조건에서는 추가적인 평균화 이득이 거의 보이지 않는다.

2. **한 개의 p_ref lane만 있어도 충분한 Kuramoto/PLL 기준 축 역할 수행**
   - `(1,1)` 구조에서 이미 `BER_DD_pRef`는 Q17a와 동일 수준으로 낮아진다.
   - `(2,1)`, `(8,56)`로 p_ref를 늘려도 θ_std_deg ≤ 5° 영역에서는
     **추가적인 BER 이득이 거의 없음**.

3. **p_ref phase spread는 “필수 기능”이 아니라 “옵션 기능”**
   - 특수한 상황(매우 큰 θ_std_deg, 비가우시안 위상 노이즈, 비선형 채널 등)에서  
     spread8이 의미를 가질 가능성은 남아있지만,
   - 현재 기준 AWGN + moderate phase-noise 영역에서는  
     **aligned p_ref 설계가 가장 단순하고 성능도 충분**.

---

## 6. Q17b에서의 결론 정리 (v0.1)

- Q17a: **aligned p_ref** (모든 p_ref lane이 같은 기준 위상)
- Q17b: **spread8 p_ref** (p_ref lane마다 서로 다른 균등 분포 위상)

Q17a vs Q17b 비교 결과:

1. **θ_std_deg ≤ 5°, AWGN-only 환경에서는**
   - p_ref 위상을 spread 시키더라도 **PhaseLock_std 성능은 거의 동일**.
   - 즉, **p_ref phase spread는 필수적인 설계 요소가 아니다.**

2. **CoPBit 설계 가이드라인 (Q17b 기준 v0.1)**

   - 기본 설계:
     - `N_ref`는 **최소 1 lane**이면 충분 (PhaseLock_std 관점).
     - p_ref 위상은 **단일 기준 위상(aligned)**로 두어도 무방.
   - phase spread:
     - `pref_mode = spread8`은 “추가 옵션”으로 두고,
     - 실제 하드웨어 구현에서는 complexity/area를 고려해
       **굳이 phase spread를 강제할 필요는 없음**.

3. **향후 확장 방향**
   - 더 강한 위상 노이즈(θ_std_deg >> 5°),  
     or **mid-ISI + EQ + phase-noise 동시 존재 환경**에서  
     spread8의 의미를 재검증 (Q16d 확장 케이스와 연결).
   - non-Gaussian 위상 노이즈 모델, jitter + DCD + ISI 복합 채널에서도  
     phase-spread p_ref가 도움이 되는지 별도 실험 필요.

---

## 7. 향후 문서 연결

- Q17a: `CoPBit_Q17a_pRef_Density_Theta_Map_v0.1.md`  
  → p_ref **갯수(density)** vs θ_std_deg 맵
- Q17b: `CoPBit_Q17b_pRef_PhaseSpread_Summary_v0.1.md` (본 문서)  
  → p_ref **phase spread** vs aligned p_ref 비교
- Q16: `CoPBit_Q16_PhaseLock_std_Summary_v0.1.md`  
  → 2-lane / 3-lane / 64-lane 축소 모델에서  
     p_ref가 PhaseLock_std BER 바닥을 어떻게 결정하는지 요약

이들 세 문서가 합쳐져서:

> **“CoPBit PhaseLock_std 설계 공식:  
> p_ref 갯수, 위상 노이즈 세기, Eb/N0 조건에서  
> 필요한 최소 p_ref density와 성능 바닥 (BER_floor)”**

를 정의하는 근거 데이터 세트가 된다.

---