# CoPBit Q13d – x64 lanes, drift 0.25° adaptive Kuramoto 결과 정리 (Channel-b, M8, Eb/N0 basis)

## 1. 실험 설정

```bash
python copbit_q13d_lane_drift_adaptive_mu_v0.py   --n_sym 1000000   --ebn0_list "18,20,22,24"   --lanes_list "64"   --drift_list "0.25"   --ffe_len 5   --train_frac 0.2   --mu_phase 0.1   --phi_max_deg 10.0
```

- 실험명: CoPBit Q13d – lane & drift sweep for xN lanes M8 + Channel-b + FFE + adaptive + limited-step Kuramoto (Eb/N0 basis) v0.1  
- 심벌 수: `n_sym = 1,000,000`
- Eb/N0 리스트(dB): `[18, 20, 22, 24]`
- lane 수: `L = 64`
- drift 표준편차: `drift_std_deg = 0.25°`
- 채널: `channel b = [0.05, 0.5, 1.0, 0.5, 0.05]` (5-tap ISI)
- FFE:
  - 길이: `ffe_len = 5`
  - 학습 구간 비율: `train_frac = 0.2`
  - M8 기준 1회 LS 설계 후, 전체 실험에 공통 사용
- 변조: M8 (CoPBit 8-PSK, 3 bit/sym), unit circle
- 노이즈: Eb/N0 기반 bit-fair AWGN (Es/N0 = Eb/N0 × 3)
- Kuramoto 파라미터:
  - `mu_phase = 0.1` (base step, adaptive 전)
  - `phi_max_deg = 10.0°` (1-step 최대 위상 변경량 제한)

## 2. Kuramoto 업데이트 구조 (요약)

- 글로벌 공통 위상 추정치: `φ_est`
- 각 심벌 시각 n, lane l에 대해:
  - 관측 심벌: `z_n(l)` = FFE + 채널 b + AWGN + drift 적용 후 심벌
  - 글로벌 위상 제거: `z̃_n(l) = z_n(l) · e^{-j φ_est}`
  - M8 slicing: `s_hat(l) = slicer_M8(z̃_n(l))`
- error phasor 및 adaptive weight:
  - `err_phasor = mean_l( z_n(l) · s_hat(l)* )`
  - `err = angle(err_phasor)`
  - `w = |err_phasor| ∈ [0, 1]` (phasor coherence)
- adaptive + limited-step 업데이트:
  - `delta = μ_phase · w · err`
  - `delta ← clip(delta, ±phi_max_rad)`  
    (여기서 `phi_max_rad = phi_max_deg · π/180`)
  - `φ_est ← φ_est + delta`

## 3. 시뮬레이션 결과 (drift_std_deg = 0.25°, L = 64)

콘솔 출력:

```text
================ drift_std_deg = 0.25 deg =================
 n_lanes | EbN0_dB | BER_M8_base | BER_M8_kura(adapt)
------------------------------------------------------
     64 |    18.0 |   4.954e-01 |   4.092e-02
     64 |    20.0 |   5.347e-01 |   2.840e-02
     64 |    22.0 |   5.371e-01 |   2.069e-02
     64 |    24.0 |   4.807e-01 |   1.600e-02
------------------------------------------------------
```

표로 정리하면 아래와 같음.

| drift_std_deg | n_lanes | Eb/N0 [dB] | BER_M8_base | BER_M8_kura(adapt) |
|---------------|---------|-----------:|------------:|-------------------:|
| 0.25°         | 64      | 18.0       | 4.954e-01   | 4.092e-02          |
| 0.25°         | 64      | 20.0       | 5.347e-01   | 2.840e-02          |
| 0.25°         | 64      | 22.0       | 5.371e-01   | 2.069e-02          |
| 0.25°         | 64      | 24.0       | 4.807e-01   | 1.600e-02          |

## 4. 결과 해석 요약

- Base(FFE-only):
  - 모든 Eb/N0 구간에서 BER ≈ 0.48~0.54 수준으로, 사실상 랜덤 디코딩(≈0.5)에 가까운 난조 상태.
- Q13d Kuramoto(adaptive + limited-step) 적용 후:
  - 18 dB: BER ≈ **4.1e-2**
  - 20 dB: BER ≈ **2.8e-2**
  - 22 dB: BER ≈ **2.1e-2**
  - 24 dB: BER ≈ **1.6e-2**
- 정리:
  - 강 ISI 채널 b + drift_std_deg = 0.25° + 64 lanes 환경에서도,
    CoPBit-M8 + FFE + Q13d Kuramoto 조합은 **pre-FEC 기준 BER 1e-2 수준까지 실제로 도달** 가능.
  - 동일 조건에서 FFE-only는 완전 난조이므로,
    **위상 락 엔진(Kuramoto)이 없으면 CoPBit 운용이 불가능한 영역**을
    Q13d 구조가 실질 운용 가능 영역으로 변환해 주는 효과가 있음.

## 5. 추가 주석 및 향후 실험 메모

- 주석 (스크립트 출력에서):
  - 채널 b: `[0.05, 0.5, 1.0, 0.5, 0.05]` 5-tap ISI 채널.
  - M8: CoPBit 위상용 8-PSK (3bit/sym), unit circle, Eb/N0 기반 bit-fair AWGN.
  - Q13c 대비 변경점:
    - Kuramoto 위상 업데이트 스텝에 `|err_phasor|` 가중치를 곱해 **adaptive-step** 적용.
    - phasor 코히어런스가 낮을수록 step을 줄여서 **발산을 억제**.
    - `phi_max_deg`로 1-step 최대 변화를 제한해 **과도한 튐을 추가로 방지**.
  - lane 수 L을 늘리면 평균 phasor의 잡음이 줄어들어 `|err_phasor|`가 커지고,
    adaptive-step이 자연스럽게 더 큰 스텝으로 위상 락을 잡게 됨.
- 추가 스윕 시도 메모:
  - 아래와 같이 더 넓은 Eb/N0, lane, drift 스윕을 시도했으나, 메모리/시간 제약으로 프로세스가 kill 됨.
    ```bash
    python copbit_q13d_lane_drift_adaptive_mu_v0.py       --n_sym 1000000       --ebn0_list "12,14,16,18,20"       --lanes_list "64,256"       --drift_list "0.25,0.5"       --ffe_len 5       --train_frac 0.2       --mu_phase 0.1       --phi_max_deg 10.0
    # [1]+  Killed: 9
    ```
  - 향후에는 `n_sym`을 조금 줄이거나, Eb/N0/lane/drift 축을 나눠서 여러 번 실행하는 방식으로
    동일 실험을 분할 수행하는 것이 좋음.

