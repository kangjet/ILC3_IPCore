# CoPBit Q13 – Lane Drift vs Kuramoto Phase-Lock 최종 정리 (Channel-b, M8, FFE)

## 0. Q13 계열 개요

- 대상: 강 ISI 채널 **b = [0.05, 0.5, 1.0, 0.5, 0.05]**
- 변조: **CoPBit-M8 (8-PSK, 3 bit/sym)**, unit circle
- 채널: Channel-b + AWGN, Eb/N0 basis (bit-fair)
- Equalizer: 심볼 레이트 **FFE** (LS 기반)
- 위상 락 구조: 다중 lane + 글로벌 위상 드리프트 + **Kuramoto 위상 동기(loop)**

**Q13 시리즈의 목적**

1. Channel-b + FFE만으로는 M8 위상 정보가 심하게 흐트러지는 상황에서,  
2. **멀티레인 Kuramoto 위상 락**이
   - lane 수(L),
   - 글로벌 위상 드리프트 표준편차(drift_std_deg),
   - SNR(Eb/N0)
   에 따라 **어디까지 BER을 끌어내릴 수 있는지**,
3. 그리고 Q13b → Q13c → Q13d로 갈수록  
   - (기본 Kuramoto) → (step 제한) → (adaptive-step + step 제한)  
   이 실제 **drift 허용 범위**를 얼마나 바꾸는지 보는 것.

---

## 1. 공통 파라미터 설정

- 채널: **Channel-b = [0.05, 0.5, 1.0, 0.5, 0.05]**
- 변조 / 노이즈
  - M8 (8-PSK), unit circle
  - Eb/N0 기반 bit-fair AWGN
- Lane 수
  - `L ∈ {4, 16, 64, 256}` (Q13d 확장에서는 L=16,64,256 중심)
- Drift
  - 글로벌 위상 random-walk
  - `drift_std_deg ∈ {0.25, 0.5, 1.0, 2.0, 3.0}` (Q13d 확장에서 0.25, 1.0, 2.0 집중)
- FFE
  - LS 기반 심볼 레이트 FFE
  - 보통 `ffe_len = 5` (Q13d 드리프트 실험에서는 `ffe_len = 7`이 sweet spot로 선택)
  - `train_frac = 0.2`
- Kuramoto 공통 구조
  - lane 별 수신 phasor: `z_n`
  - M8 GT 또는 slicer 기반 phasor: `s_hat`
  - 평균 phasor: `err_phasor = mean(z_n * conj(s_hat))`
  - `err = angle(err_phasor)`
  - 위상 추정: `phi_est ← phi_est + delta`

---

## 2. Q13b / Q13c / Q13d 차이 요약

### 2.1 Q13b – 기본 Kuramoto

- 스크립트: `copbit_q13_x16_eq_kuramoto_ber_v0.py` (x16 lanes 중심)
- 특징:
  - **고정 스텝** Kuramoto: `delta = mu_phase * err`
  - `phi_max_deg` 제한 없음 → 큰 error에서 과도한 step 가능
- 관찰:
  - drift_std가 작을 때(예: 0.25°~0.5°)는 문제 없이 락.
  - drift_std가 커질수록 (1° 이상) 일부 조합에서 **발산/진동** 현상.

### 2.2 Q13c – limited-step Kuramoto

- 스크립트: `copbit_q13c_lane_drift_limited_step_v0.py`
- 변경점:
  - Q13b에 **step limit** 추가:
    - `phi_max_deg`를 두고,
    - `delta = clamp(mu_phase * err, -phi_max_rad, +phi_max_rad)`
- 효과:
  - 큰 drift에서 한 번에 과도하게 회전하는 것 방지.
  - 그러나 drift_std가 1° 이상 영역에서,
    - 락 성공 케이스는 조금 더 안정적,
    - 하지만 **“안 되는 조합”이 “되는 조합”으로 바뀔 정도의 큰 확장은 아님**.

### 2.3 Q13d – adaptive + limited-step Kuramoto

- 스크립트: `copbit_q13d_lane_drift_adaptive_mu_v0.py`
- 변경점:
  - Q13c에 **adaptive-step** 추가:
    - `err_phasor = mean(z_n * conj(s_hat))`
    - `w = |err_phasor| ∈ [0, 1]` (phasor coherence)
    - `delta = mu_phase * w * err`, 이후 ±`phi_max_deg`로 clip
- 의미:
  - phasor coherence가 낮을수록(잡음/드리프트 심할수록) 자연스럽게 step을 줄여서 폭주 억제.
  - coherence가 높을 때는 w≈1이므로 Q13c와 비슷하게 동작.
- 추가 실험:
  - drift_std=0.25°, 1°, 2°에 대해
    - `mu_phase` (0.05, 0.1, 0.2),
    - `phi_max_deg` (5°, 10°, 20°),
    - `n_sym = 3e5 ~ 1e6`
    를 조합해 **1e-2 threshold**와 **실제 drift 허용 범위**를 정교하게 확인.

---

## 3. Q13d 주요 수치 결과 (요약)

### 3.1 drift_std = 0.25°, L=64, FFE=7 (강 ISI + drift, “쉬운” drift 영역)

- 조건:
  - `n_sym = 300000`
  - `Eb/N0_list = [20, 22, 24, 26]` dB
  - `lanes_list = [64]`
  - `drift_list = [0.25]`
  - `ffe_len = 7`, `mu_phase = 0.10`, `phi_max_deg = 10°`

- 결과 예시:

  | Eb/N0(dB) | BER_M8_base | BER_M8_kura(adapt) |
  |----------:|------------:|--------------------:|
  | 20        | 5.452e-01   | 9.784e-03           |
  | 22        | 4.689e-01   | 3.273e-03           |
  | 24        | 4.779e-01   | 9.629e-04           |
  | 26        | 4.077e-01   | 2.604e-04           |

- 해석:
  - base는 항상 ~0.45~0.55 수준 (거의 랜덤).
  - Kuramoto + FFE7는
    - **20 dB에서 이미 1e-2 이하**,  
    - 22 dB에서 3e-3대,
    - 24 dB 이상에서는 1e-3 미만.
  - drift_std=0.25° 구간은 Channel-b 기준으로  
    **CoPBit 위상락이 매우 여유 있게 작동하는 영역**.

---

### 3.2 drift_std = 1°, L=64, FFE=7, n_sym=1e6 (실제 spec 경계)

- 조건:
  - `n_sym = 1,000,000`
  - `Eb/N0_list = [18, 19, 20, 21, 22, 23]` dB
  - `lanes_list = [64]`
  - `drift_list = [1.0]`
  - `ffe_len = 7`, `mu_phase = 0.10`, `phi_max_deg = 10°`

- 결과:

  | Eb/N0(dB) | BER_M8_base | BER_M8_kura(adapt) |
  |----------:|------------:|--------------------:|
  | 18        | 5.133e-01   | 2.890e-02           |
  | 19        | 5.058e-01   | 1.897e-02           |
  | 20        | 4.888e-01   | 1.213e-02           |
  | 21        | 5.076e-01   | 7.523e-03           |
  | 22        | 4.955e-01   | 4.563e-03           |
  | 23        | 4.647e-01   | 2.757e-03           |

- 핵심 포인트:
  - drift_std=1°임에도, **n_sym=1e6** 기준에서
    - 18 dB: 2.9e-2 (3e-2 이내)
    - 19~20 dB: (1.9~1.2)e-2
    - 21 dB 이상: 1e-2 아래로 안정
  - → **“장기 수렴 기준으로도 락이 유지되는 drift=1° 한계선”**.

- 스펙 관점 요약:
  - Channel-b, FFE7, L=64, μ_phase=0.10, φ_max=10° 조건에서
    - drift_std ≈ 1°일 때,
      - **Eb/N0 ≈ 20.5 dB 이상**이면 pre-FEC **BER ≤ 1e-2** 가능.
      - 22 dB 이상에서는 BER ≈ 4.6e-3 수준으로 추가 마진 확보.

---

### 3.3 drift_std = 2°, L=64, FFE=7 – μ, φ_max 튜닝 결과

- 조건:
  - `n_sym = 5e5 ~ 1e6`
  - `drift_list = [2.0]`
  - μ_phase ∈ {0.02, 0.05, 0.10, 0.20}
  - φ_max_deg ∈ {5°, 10°, 20°}
  - Eb/N0 ∈ {20, 22} 또는 [18..23] 스윕

- 대표 결과 (예: μ=0.2, φ_max=10°, n_sym=5e5):

  | drift_std=2° | Eb/N0(dB) | BER_base | BER_kura(adapt) |
  |-------------:|----------:|---------:|-----------------:|
  |              | 20        | ≈ 0.495  | 1.288e-01        |
  |              | 22        | ≈ 0.489  | 6.604e-03        |

- 그러나 **n_sym=1e6, Eb/N0=[18..23]** 전체 스윕을 보면:
  - 일부 SNR 구간에서 좋아 보이는 값이 잠깐 나타나지만,
  - 전체 SNR 축에서 일관되게 1e-2 이하를 유지하지 못하고,
  - 구간에 따라 다시 0.2~0.5 수준으로 튀어 오르는 패턴 존재.
- 결론:
  - drift_std ≈ 2°에서는
    - μ, φ_max를 조절해 **국지적으로는 락 비슷한 현상**이 보이지만,
    - **“spec 관점에서 안정적 1e-2 threshold”**로 인정하기 어렵다.
  - → Channel-b + 현재 구조 기준으로는 **2°는 out-of-spec drift**.

---

## 4. Lane 스케일링 효과 (L ∈ {16, 64, 256})

- 조건 예시 (drift_std=0.25°, Eb/N0=20 dB, FFE=7, μ=0.10, φ_max=10°):

  | L   | BER_M8_base | BER_M8_kura(adapt) |
  |----:|------------:|--------------------:|
  |  16 | ≈ 0.416     | 9.87e-03           |
  |  64 | ≈ 0.513     | 9.75e-03           |
  | 256 | ≈ 0.398     | 9.73e-03           |

- 관찰:
  - base BER는 lane 수에 따라 0.39~0.51 정도로 들쭉날쭉.
  - **Kuramoto BER는 L=16,64,256 모두 ≈ 1e-2 수준으로 거의 동일**.
- 해석:
  - lane 수가 커질수록 평균 phasor에서 **노이즈가 평균화**되어,
    - |err_phasor|가 커지고,
    - adaptive-step이 자연스럽게 “더 큰 유효 스텝”으로 위상 락을 잡는다.
  - L=16 → 64 → 256 으로 증가해도 **락이 깨지지 않고 오히려 더 안정**되는 패턴.
- 시스템 메시지:
  - CoPBit 멀티레인 구조는 **lane 수를 늘리는 것이 위상 정보 측면에서 오히려 유리**.
  - “1024-lane CoPBit bus” 같은 구조를 겨냥할 때,
    - Q13 계열 결과는 **Kuramoto-기반 global phase-lock이 lane 증가에 대해 잘 스케일링된다**는 근거가 된다.

---

## 5. Q13 최종 메시지 (Spec-Ready 문장)

1. **Phase-Lock 타깃 drift 범위**

   - Channel-b + FFE7 + CoPBit-M8 + Kuramoto(adaptive + step-limit) 구조에서,
   - **drift_std_deg ≲ 1°** 이면,
     - Eb/N0 ≥ ~20.5 dB에서 **pre-FEC BER ≤ 1e-2** 달성 가능 (L=64 기준).
   - **drift_std_deg ≈ 2°**에서는
     - μ/φ_max를 조절해도 **장기 기준 안정적 1e-2 threshold는 확보되지 않음**.
   - → 현 구조 기준 CoPBit phase-lock 아키텍처의 **1차 spec target**은  
     **σ_drift ≲ 1°**.

2. **Lane 스케일링**

   - drift_std ≤ 0.25°~0.5° 영역에서는,
     - lane 수를 16 → 64 → 256으로 늘려도
     - Kuramoto BER가 **1e-2 ~ 1e-1 수준으로 잘 유지**.
   - → 멀티레인 CoPBit에서 **lane을 크게 늘려도 global Kuramoto 락은 충분히 실현 가능**.

3. **Q13b → Q13c → Q13d의 의미**

   - Q13b: **기본 Kuramoto**만으로도 drift 0.25°~0.5°에서는 잘 동작.
   - Q13c: **step limit**로 과도한 회전을 막으며, 경계 drift에서 약간 안정화.
   - Q13d: **adaptive-step + step limit** 조합으로,
     - drift=0.25°에서는 Q13c와 비슷한 수준 유지,
     - drift=1°에서 Eb/N0~20.5 dB 이상에 대해 **1e-2 spec**을 명확히 확인,
     - drift=2° 이상에서는 **구조적 한계**를 드러냄.
   - 결과적으로,
     - **Q13d는 “CoPBit phase-lock이 실제 시스템에서 쓸 수 있는지”에 대한 베이스라인 spec을 제공**한다.

4. **향후 확장(Q14 이후 아이디어)**

   - drift 2° 이상 허용을 목표로 할 경우:
     - 2-stage 구조:
       - global Kuramoto (저속 드리프트용) + per-lane PLL/DLL (잔여 위상 보정)
     - frame 기반 재초기화 / pilot 삽입
     - 위상 양자화 + guard-phase 조합 등
   - Q13은 “현 구조의 물리적 한계”를 정의해줬고,  
     Q14 이후는 “이 한계를 넘기기 위한 구조 개선”을 설계하는 단계로 넘어갈 수 있다.

---

## 6. Q13 관련 파일 매핑 (Scripts / Notes / Plots)

### 6.1 Python Scripts

| 파일명 | 경로 (상대) | 용도 |
|--------|-------------|------|
| `copbit_q13_x16_eq_kuramoto_ber_v0.py` | `CoPBit_Research/python/` | Q13b 성격의 **기본 Kuramoto + EQ** 실험. x16 lanes 기준으로 Kuramoto BER vs Eb/N0를 확인하는 초기 실험. |
| `copbit_q13b_lane_drift_sweep_v0.py` | `CoPBit_Research/python/` | Q13b: **기본 Kuramoto + drift sweep**. drift_std_deg와 lane 수에 따른 BER 변화를 1차로 스캔. |
| `copbit_q13c_lane_drift_limited_step_v0.py` | `CoPBit_Research/python/` | Q13c: **step-limit Kuramoto** 실험. `phi_max_deg`를 도입해 drifting 환경에서 과도한 회전을 막는 효과 확인. |
| `copbit_q13d_lane_drift_adaptive_mu_v0.py` | `CoPBit_Research/python/` | Q13d: **adaptive-step + step-limit Kuramoto** 최종 버전. drift_std, lane, Eb/N0, μ, φ_max 스윕을 통해 최종 spec용 데이터를 생성. |
| `copbit_q12c_ffe_sweep_channel_eq_ebn0_v0.py` | `CoPBit_Research/python/` | Q12c: 채널 b에 대한 **FFE 길이/파라미터 sweet spot 탐색** 용도. Q13에서 사용하는 FFE 설정(특히 FFE=7)을 결정할 때 참조. |

### 6.2 Note / Report Files

| 파일명 | 경로 (상대) | 내용 / 역할 |
|--------|-------------|-------------|
| `CoPBit_Q13d_lane_drift_adaptive_mu_v0.md` | `CoPBit_Research/note/` | Q13d 상세 노트. drift=0.25/0.5/1/2/3°, lane 스윕, μ/φ_max, Q13b/c와 비교 해석 포함. (현재 문서에서 세부 내용 기록 완료) |
| `Q13d_drift0p25_L64_FFE5_vs_7_summary.md` | `CoPBit_Research/note/` | drift=0.25°, L=64에서 **FFE 길이 5 vs 7** 비교 정리. FFE=7 선택의 근거 제공. |
| `copbit_q13d_lane64_drift0p25_1e6sym_results.md` | `CoPBit_Research/note/` | drift=0.25°, L=64, n_sym=1e6 장기 실험 결과 요약. 1e-2 threshold 및 고 Eb/N0 마진 확인용. |
| `copbit_Q10_Q13_summary.md` | `CoPBit_Research/note/` | Q10~Q13 흐름을 한 번에 보는 상위 요약. Q10(M-PSK AWGN baseline) → Q12(Channel-b FFE) → Q13(Drift + Kuramoto) 연결 스토리. |
| `CoPBit_Q10_EbN0_Notes_v0.1.md` | `CoPBit_Research/note/` | Q10: M8/M16 등 AWGN-only Eb/N0 vs BER baseline. Q13에서 **“드리프트 없이 최선의 BER”** 비교 기준 제공. |

### 6.3 Plot Files (PNG 등)

| 파일명 | 경로 (상대) | 그래프 내용 |
|--------|-------------|-------------|
| `Q13d_DriftStd_vs_BER_EbN0_22dB_L64_FFE7.png` | `CoPBit_Research/python/` | Eb/N0=22 dB, L=64, FFE=7에서 drift_std_deg (0.25~3°)에 따른 BER 곡선. **“1°까지 OK, 2°부터 무너짐”** 패턴을 직관적으로 보여줌. |
| `Q13d_EbN0_vs_BER_drift0p25_L64_FFE7.png` | `CoPBit_Research/python/` | drift_std=0.25°, L=64, FFE=7에서 Eb/N0 vs BER 곡선. **1e-2 threshold가 어디서 형성되는지** 시각화. |
| `Q13d_Lanes_vs_BER_EbN0_20dB_drift0p25_FFE7.png` | `CoPBit_Research/python/` | drift_std=0.25°, Eb/N0=20 dB, FFE=7에서 lane 수(L=16,64,256) vs BER. **lane 스케일링 효과** 시각화. |

> 위 파일들의 조합으로  
> - 특허/논문용: Q10/Q12/Q13 전체 그림,  
> - 투자/설명용: CoPBit가 drift+ISI에서도 어느 구간까지 “실제 사용 가능한 위상락 구조”인지  
> 를 스토리로 묶어서 제시할 수 있다.

---