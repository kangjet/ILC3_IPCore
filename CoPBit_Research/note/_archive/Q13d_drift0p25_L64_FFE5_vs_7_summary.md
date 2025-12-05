# Q13d – drift 0.25°, L=64, FFE=5 vs FFE=7 비교 요약 (CoPBit-M8 + Channel-b + Kuramoto)

## 1. 실험 개요

- 목적:
  - 강 ISI 채널 **b = [0.05, 0.5, 1.0, 0.5, 0.05]** 환경에서
    - CoPBit-M8 (8-PSK, 3 bit/sym, unit circle) 변조
    - 심볼 레이트 FFE + 멀티레인 Kuramoto 위상 락(Q13d: adaptive + limited-step)
  - 를 사용할 때,
    - **FFE tap 수(5 vs 7)**에 따라 pre-FEC BER floor가 어떻게 달라지는지 정량 비교.
  - 특히 drift=0.25°, L=64 조건에서 관측된 **BER ≈ 1×10⁻² floor의 원인이 Kuramoto 파라미터인지, FFE 구조인지**를 확인.

- 공통 조건:
  - 채널: 5-tap ISI channel-b = `[0.05, 0.5, 1.0, 0.5, 0.05]`
  - 변조: M8 (8-PSK, 3 bit/sym), unit circle
  - 노이즈: Eb/N0 기반 bit-fair AWGN (Es/N0 = Eb/N0 × 3)
  - lane 수: `L = 64`
  - drift: 글로벌 위상 random walk, `drift_std_deg = 0.25°`
  - Kuramoto(Q13d) 파라미터 (공통):
    - adaptive-step: `delta = mu_phase * |err_phasor| * err`
    - `mu_phase = 0.10`
    - `phi_max_deg = 10.0°` (1-step 최대 위상 변경량)
  - 심볼 수: `n_sym = 300,000` (각 Eb/N0 포인트)
  - FFE 설계:
    - `train_frac = 0.2` (전체 심볼 중 20%를 training 구간으로 사용)
    - M8 기준 1회 LS 설계 후 해당 run 전체에 공통 사용


## 2. FFE len = 5 결과 (baseline)

실행 커맨드(요지):

```bash
python copbit_q13d_lane_drift_adaptive_mu_v0.py   --n_sym 300000   --ebn0_list "20,22,24,26,28"   --lanes_list "64"   --drift_list "0.25"   --ffe_len 5   --train_frac 0.2   --mu_phase 0.10   --phi_max_deg 10.0   --seed 1
```

결과 (drift=0.25°, L=64, FFE=5):

| Eb/N0 (dB) | BER_M8_base | BER_M8_kura(adapt) |
|-----------:|------------:|-------------------:|
| 20         | 5.431e-01   | 2.833e-02 |
| 22         | 4.778e-01   | 2.067e-02 |
| 24         | 4.767e-01   | 1.593e-02 |
| 26         | 4.202e-01   | 1.317e-02 |
| 28         | 3.813e-01   | 1.144e-02 |

관찰:

- FFE-only (BER_base)는 **0.38~0.54** 수준으로 완전 난조.
- Kuramoto(Q13d) 적용 후에도:
  - 20~28 dB 전 구간에서 **BER ≈ (1.1~2.8)×10⁻²** 범위에 머무르며,
  - Eb/N0를 8 dB나 올려도 BER 감소 폭이 작음.
- ⇒ drift=0.25°, L=64, FFE=5 조건에서는
  - **pre-FEC floor ≈ 1×10⁻² 근처**가 형성되어 있고,
  - 단순 SNR 상승이나 μ/φ_max 튜닝만으로는 이 floor를 깨기 어렵다는 것이 Step1/Step2에서 확인됨.


## 3. FFE len = 7 결과 (개선안)

실행 커맨드(요지):

```bash
python copbit_q13d_lane_drift_adaptive_mu_v0.py   --n_sym 300000   --ebn0_list "20,22,24,26"   --lanes_list "64"   --drift_list "0.25"   --ffe_len 7   --train_frac 0.2   --mu_phase 0.10   --phi_max_deg 10.0   --seed 1
```

결과 (drift=0.25°, L=64, FFE=7):

| Eb/N0 (dB) | BER_M8_base | BER_M8_kura(adapt) |
|-----------:|------------:|-------------------:|
| 20         | 5.452e-01   | 9.784e-03 |
| 22         | 4.689e-01   | 3.273e-03 |
| 24         | 4.779e-01   | 9.629e-04 |
| 26         | 4.077e-01   | 2.604e-04 |

관찰:

- FFE-only (BER_base)는 여전히 **0.40~0.55** 수준으로 난조이나,
- Kuramoto(Q13d) 적용 후 BER 곡선이 완전히 바뀜:
  - 20 dB에서 이미 **9.8×10⁻³ < 1×10⁻²**
  - 22 dB: **3.3×10⁻³**
  - 24 dB: **9.6×10⁻⁴**
  - 26 dB: **2.6×10⁻⁴**
- ⇒ FFE tap을 5→7로 늘리자마자,
  - **1×10⁻² 수준의 floor가 사라지고**,  
  - SNR 증가에 따라 **AWGN-like하게 10⁻² → 10⁻³ → 10⁻⁴로 자연스럽게 감소**하는 형태로 변함.


## 4. FFE=5 vs 7 직접 비교 (drift 0.25°, L=64, n_sym=3e5)

| Eb/N0 (dB) | FFE len | BER_M8_kura(adapt) |
|-----------:|--------:|-------------------:|
| 20         | 5       | 2.833e-02 |
| 20         | 7       | 9.784e-03 |
| 22         | 5       | 2.067e-02 |
| 22         | 7       | 3.273e-03 |
| 24         | 5       | 1.593e-02 |
| 24         | 7       | 9.629e-04 |
| 26         | 5       | 1.317e-02 |
| 26         | 7       | 2.604e-04 |

핵심 차이:

- **FFE=5 (symbol-rate 5tap):**
  - drift=0.25°, L=64, Q13d Kuramoto가 동작함에도
  - 20~28 dB 전 구간에서 **BER ≈ 1×10⁻²** 부근에 고정 → **error floor 지배 영역**
- **FFE=7 (symbol-rate 7tap):**
  - 같은 Kuramoto 파라미터, 같은 drift/L에서
  - 20 dB에서 **이미 9.8×10⁻³**, 24 dB에서 **~10⁻³**, 26 dB에서 **~10⁻⁴**
  - ⇒ **잔류 ISI 억제가 개선되면서 floor가 사라지고, SNR에 따른 정상적인 BER 감소가 회복됨.**


## 5. 1×10⁻² threshold 관점에서 본 “FFE 구조 변경 효과”

### 5.1. FFE len=5 (baseline)

- 테스트 범위: Eb/N0 = 20, 22, 24, 26, 28 dB
- 모든 포인트에서 `BER_M8_kura(adapt)`가 **1.1×10⁻² 이상**
  - 28 dB에서도 ≈1.1×10⁻²
- 따라서:
  - **drift=0.25°, L=64, FFE=5 환경에서는**  
    “pre-FEC BER = 1×10⁻²”를 만족하는 Eb/N0가 **테스트 범위(≤28 dB) 안에 존재하지 않음**.
  - 즉, **1×10⁻² threshold > 28 dB** (적어도 28 dB보다 높은 영역).

### 5.2. FFE len=7 (개선 구조)

- 테스트 범위: Eb/N0 = 20, 22, 24, 26 dB
- 20 dB에서 `BER_M8_kura(adapt) ≈ 9.8×10⁻³ < 1×10⁻²`
- 따라서:
  - **drift=0.25°, L=64, FFE=7 환경에서는**  
    pre-FEC BER = 1×10⁻²를 만족하는 Eb/N0가 **20 dB 이하에 존재**.
  - 즉, **1×10⁻² threshold ≤ 20 dB** (실제 임계점은 대략 19~20 dB 사이로 추정 가능).

### 5.3. threshold shift 정리

- FFE len=5: `Eb/N0_1e-2 > 28 dB`
- FFE len=7: `Eb/N0_1e-2 ≤ 20 dB`

⇒ **FFE tap: 5 → 7로 구조만 변경했을 때,**  
drift=0.25°, L=64, Kuramoto(Q13d) 조건에서 **1×10⁻² threshold가 최소 8 dB 이상 개선**된 것으로 볼 수 있음.

즉,

> “동일한 CoPBit-M8 + Kuramoto 구조에서,  
>  채널 b에 대해 symbol-rate FFE 길이를 5tap에서 7tap으로 늘리면,  
>  pre-FEC BER = 1×10⁻²를 만족하는 Eb/N0 요구치는 28 dB 초과 → 20 dB 이하로  
>  **최소 8 dB 이상 개선**된다.”


## 6. 문서/특허/사업계획서에 바로 쓸 수 있는 요약 문장들

- **기술 요약용 문장:**
  - “강 ISI 채널 b 환경에서 CoPBit-M8(8-PSK) + adaptive Kuramoto 위상 락(Q13d)을 적용하더라도, symbol-rate FFE 길이가 5tap인 경우 pre-FEC BER이 10⁻² 수준에서 floor를 형성하여 28 dB 이상의 Eb/N0를 인가해도 큰 개선이 나타나지 않는다.”
  - “동일 조건에서 FFE tap 수를 7tap으로 확장하면 잔류 ISI가 크게 감소하면서 BER floor가 사라지고, 20 dB에서 이미 10⁻² 이하, 24 dB에서 10⁻³ 수준, 26 dB에서 10⁻⁴ 수준까지 BER이 개선된다.”
  - “따라서 제안하는 CoPBit-M8 + Kuramoto 위상 락 구조에서, 채널 b와 유사한 강 ISI 환경을 대상으로 할 경우 최소 7tap 이상의 symbol-rate FFE를 사용하는 것이 10⁻² 이하 pre-FEC BER 달성에 필수적인 설계 조건임을 확인하였다.”

- **threshold 개선 강조용 문장:**
  - “FFE 길이를 5tap에서 7tap으로 확장함으로써, drift=0.25°, 64 lanes 조건에서 pre-FEC BER = 1×10⁻²를 만족하기 위한 Eb/N0 요구치가 28 dB 초과에서 20 dB 이하로 이동하여, 최소 8 dB 이상의 SNR margin 절감 효과를 얻었다.”

- **Kuramoto 구조에 대한 해석 문장:**
  - “μ/φ_max 파라미터 튜닝 실험 결과, FFE=5tap 환경에서는 Kuramoto 스텝 크기를 조정해도 10⁻² floor를 유의미하게 낮추지 못하는 반면, FFE=7tap 환경에서는 동일 Kuramoto 설정으로도 10⁻³~10⁻⁴ 영역까지 BER이 자연스럽게 감소한다. 이는 Q13d Kuramoto 구조가 위상 락 측면에서는 충분한 성능을 가지며, 관측된 floor의 주된 원인이 FFE 길이 부족에 따른 잔류 ISI임을 시사한다.”


## 7. 다음 단계 메모

- FFE=7을 기준 구조로 고정한 뒤,
  - (1) Eb/N0를 18~21 dB 사이에서 더 촘촘히 스윕하여 정확한 1×10⁻² threshold 위치를 찾고,
  - (2) drift_std_deg를 0.25°→0.5°로 올렸을 때의 Eb/N0 margin 변화를 측정하면,
- “채널 b + CoPBit-M8 + Kuramoto(Q13d) + FFE=7” 구조에 대한
  - **실제 운영 가능 SNR vs drift 마진 맵**을 완성할 수 있다.
