# CoPBit Q13d – Drift 허용 범위 & Lane 스케일링 요약 (Channel-b, M8, FFE=7)

## 1. 공통 실험 조건

- 변조: 8-PSK (M8, 3 bit/sym), unit circle
- 채널: 5-tap ISI, Channel-b = [0.05, 0.5, 1.0, 0.5, 0.05]
- 등화기(FFE)
  - tap 수: **7**
  - train_frac = 0.2
  - M8 + 채널 b 기준으로 한 번 LS 설계 후, 동일 계수 사용
- Kuramoto 위상 추적 (Q13d 구조)
  - adaptive-step:
    - err_phasor = mean(z_n · s_hat*)
    - w = |err_phasor| (0..1, 코히어런스)
    - delta = μ_phase · w · err, |delta| ≤ phi_max_deg
  - μ_phase = 0.10
  - phi_max_deg = 10.0
- 멀티레인: lane 수는 실험에 따라 16 / 64 / 256
- 글로벌 위상 드리프트:
  - 각 심볼마다 random walk
  - step 표준편차 = drift_std_deg [deg]
- 노이즈: Eb/N0 기반 bit-fair AWGN (k = 3 bits/sym)
- 심볼 수: n_sym = 500,000
- 난수 시드: seed = 1

---

## 2. Drift 허용 범위 (Eb/N0 = 22 dB, L = 64, FFE=7)

### 2.1 실험 설정

```bash
python copbit_q13d_lane_drift_adaptive_mu_v0.py \
  --n_sym 500000 \
  --ebn0_list "22" \
  --lanes_list "64" \
  --drift_list "0.25,0.5,1.0,2.0,3.0" \
  --ffe_len 7 \
  --train_frac 0.2 \
  --mu_phase 0.10 \
  --phi_max_deg 10.0 \
  --seed 1
```

### 2.2 결과 요약 (Eb/N0 = 22 dB, n_lanes = 64)

| drift_std_deg [deg] | BER_M8_base | BER_M8_kura(adapt) |
|---------------------|-------------|---------------------|
| 0.25                | 4.708e-01   | **3.279e-03**       |
| 0.50                | 4.733e-01   | **3.517e-03**       |
| 1.00                | 5.273e-01   | **4.563e-03**       |
| 2.00                | 4.947e-01   | 4.393e-01           |
| 3.00                | 5.013e-01   | 4.872e-01           |

### 2.3 해석

- **drift_std_deg ≤ 1.0°**:
  - Kuramoto 적용 후 BER이 **3e-3 ~ 4.6e-3** 수준으로 매우 안정적.
  - 채널 b + 강 ISI + 드리프트 환경에서도, adaptive Kuramoto가 위상을 잘 락킹하고 있음을 의미.
- **drift_std_deg = 2.0° 이상**:
  - BER이 **~0.44 ~ 0.49** 수준으로 급격히 악화 → 사실상 위상락 실패 구간.
- 따라서, 이 조건(Eb/N0=22 dB, L=64, FFE=7, μ=0.1, phi_max=10°)에서
  - **실질적인 위상 드리프트 허용 범위는 σ_drift ≈ 1° 이하**로 보는 것이 타당.
  - 그 이상의 드리프트는 별도의 보정(예: 상위 PLL, 더 빠른 추적, μ/phi_max 조정)이 필요.

---

## 3. Lane 스케일링 (Eb/N0 = 20 dB, drift_std_deg = 0.25°)

### 3.1 실험 설정

```bash
python copbit_q13d_lane_drift_adaptive_mu_v0.py \
  --n_sym 500000 \
  --ebn0_list "20" \
  --lanes_list "16,64,256" \
  --drift_list "0.25" \
  --ffe_len 7 \
  --train_frac 0.2 \
  --mu_phase 0.10 \
  --phi_max_deg 10.0 \
  --seed 1
```

### 3.2 결과 요약 (Eb/N0 = 20 dB, drift_std_deg = 0.25°)

| n_lanes | BER_M8_base | BER_M8_kura(adapt) |
|---------|-------------|---------------------|
| 16      | 4.160e-01   | **9.871e-03**       |
| 64      | 5.126e-01   | **9.753e-03**       |
| 256     | 3.975e-01   | **9.729e-03**       |

### 3.3 해석

- **Kuramoto ON (adaptive)**:
  - lane 수를 16 → 64 → 256으로 증가시켜도 BER은 **≈ 1e-2 근처에서 거의 동일**.
  - 이 실험 조건(Eb/N0=20 dB, drift=0.25°, FFE=7, μ=0.1)에서는
    - 이미 16 lanes 수준에서 집단 평균 효과가 충분히 확보되어 있고,
    - 64/256 lanes로 늘려도 추가적인 BER 개선은 거의 없는 **포화 구간**임을 시사.
- **Base(FFE-only)**는 lane 수에 따라 값이 꽤 요동치지만,
  - Kuramoto가 글로벌 위상 정보를 평균해 버리기 때문에,
  - 최종 BER은 lane 수에 **매우 둔감한 구조**로 동작하고 있음.

---

## 4. 요약 – Q13d 기준 위상락 스펙 문장 (초안)

이번 Q13d + FFE=7 실험(채널 b, M8, CoPBit Kuramoto 기준)에서 얻은 정리:

1. **1e-2 threshold (pre-FEC 기준)**  
   - drift_std_deg = 0.25°, L=64, FFE=7, μ=0.1, phi_max=10° 조건에서
   - Eb/N0를 스윕한 결과,
     - 19 dB → BER ≈ 1.6e-2
     - **20 dB → BER ≈ 9.8e-3 (처음으로 1e-2 아래 진입)**
   - → “이 구조에서 pre-FEC BER 1e-2를 달성하기 위한 요구 Eb/N0는 **약 20 dB** 수준”

2. **Drift 허용 범위 (Eb/N0 = 22 dB, L=64 기준)**  
   - drift_std_deg ≤ 1.0°: BER ≈ 3e-3 ~ 4.6e-3 (안정적 위상락)
   - drift_std_deg ≥ 2.0°: BER ≈ 0.44 이상 (위상락 붕괴)
   - → “글로벌 위상 드리프트 표준편차 약 **1° 이하**에서 안정적인 Kuramoto 위상락 동작”

3. **Lane 스케일링 특성 (Eb/N0 = 20 dB, drift=0.25°)**  
   - L = 16 / 64 / 256 모두에서 BER ≈ 1e-2
   - → “해당 조건에서는 약 16 lanes 수준에서 이미 집단 평균 효과가 포화되어,
         lane 수를 더 늘려도 BER은 거의 개선되지 않는 구간”

---

## 5. 향후 확장 아이디어 (메모)

- Drift 허용 범위를 다른 SNR 포인트(예: threshold+1 dB, threshold+3 dB)에서 재측정해,
  - (Eb/N0, drift_std_deg) 2D 맵 형태의 “위상락 안정 영역도(stability map)” 작성 가능.
- Lane 스케일링은 더 낮은 SNR(예: 18 dB)이나 더 큰 drift에서 돌려 보면,
  - 멀티레인 효과가 BER에 다시 강하게 나타나는 지점을 찾을 수 있음.
- 향후 CoPBit 하드웨어 아키텍처 문서에서,
  - “필요 Eb/N0 (1e-2 기준) vs 허용 drift 범위 vs lane 수”를 한 장 그림으로 요약하면,
  - 실제 시스템 스펙/칩 요구사항으로 바로 연결 가능.

- (KOR) Channel-b(강 ISI) 환경에서 CoPBit M8(8-PSK) + FFE(7-tap) + 64-lane adaptive Kuramoto 위상 락 구조는,
  글로벌 위상 드리프트 표준편차 σ_drift ≲ 1° 조건에서 pre-FEC BER 1e-2를 기준으로
  요구 Eb/N0 ≈ 20 dB (22 dB에서 BER ≈ 3e-3) 수준의 성능을 달성한다.

- (ENG) In the strong-ISI Channel-b environment, the CoPBit M8 (8-PSK) + 7-tap FFE + 64-lane adaptive Kuramoto 
  phase-lock architecture achieves a pre-FEC BER of 1e-2 at Eb/N0 ≈ 20 dB 
  (reaching BER ≈ 3e-3 at 22 dB), provided that the global phase drift standard deviation 
  satisfies σ_drift ≲ 1°.

  - Q13d Kuramoto 안정 영역(초안 스펙):

  - 목표 pre-FEC BER: 1e-2
  - 요구 Eb/N0: 약 20 dB 이상
  - 허용 글로벌 위상 드리프트: σ_drift ≲ 1°
  - lane 수: 16 ~ 256 범위에서 BER은 거의 동일(≈1e-2 수준) → 16 lanes 이상에서 집단 위상 평균 효과 포화