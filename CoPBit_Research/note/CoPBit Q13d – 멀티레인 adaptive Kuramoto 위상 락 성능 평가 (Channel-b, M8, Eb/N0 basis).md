# CoPBit Q13d – 멀티레인 adaptive Kuramoto 위상 락 성능 평가 (Channel-b, M8, Eb/N0 basis)

## 1. 실험 개요

- 목적:
  - 강 ISI 채널 b 환경에서 CoPBit용 8-PSK(M8) + FFE + 멀티레인 Kuramoto 위상 락 구조가  
    **lane 수 / drift / Eb/N0**에 따라 어느 정도 BER을 달성할 수 있는지 정량 평가.
  - 특히 Q13b/Q13c에서 사용한 **고정 스텝 Kuramoto**를  
    **adaptive + limited-step** 형태로 바꿨을 때, 실제로 BER·운영 영역이 얼마나 달라지는지 확인.

- 공통 통신 설정:
  - 변조: 8-PSK (M8, 3 bit/sym), unit circle
  - 채널: 5-tap ISI, 채널 b = `[0.05, 0.5, 1.0, 0.5, 0.05]`
  - 등화기(FFE):
    - tap 수: `ffe_len = 5`
    - `train_frac = 0.2`
    - M8 기준으로 채널 b에 대해 1회 LS 설계 후, **모든 실험에서 동일 계수 재사용**
  - 노이즈: Eb/N0 기반 bit-fair AWGN  
    (Es/N0 = Eb/N0 × k, k = 3 bits/sym)
  - 멀티레인:
    - 기본: `L = 64` lanes
    - 일부 스윕: `L ∈ {4, 16, 64, 256}`
  - 드리프트:
    - 글로벌 위상 random walk
    - step 표준편차 = `drift_std_deg` [deg]

- Kuramoto 위상 락 구조:
  - 글로벌 공통 위상 추정치: φ_est
  - 각 심벌 시각 n에서, lane l에 대해
    - 관측 심벌:  
      `z_n(l)` = FFE + 채널 + AWGN + drift 적용 후 심벌
    - 글로벌 위상 제거:  
      `z̃_n(l) = z_n(l) · e^{-j φ_est}`
    - 각 레인 독립 8-PSK slicing → `s_hat(l)`
    - phasor error:
      - `err_phasor = mean_l( z_n(l) · s_hat(l)* )`
      - `err = angle(err_phasor)`
      - `w = |err_phasor| ∈ [0, 1]` (phasor coherence)

  - Q13d에서의 adaptive + limited-step 업데이트:
    - `delta = μ_phase · w · err`
    - `delta`를 ±`phi_max_deg` (rad로 변환) 범위로 clip
    - `φ_est ← φ_est + delta`

- 스크립트 대응:
  - Q13b: `copbit_q13b_lane_drift_sweep_v0.py`  
    (기본 Kuramoto, 고정 μ, step-limit 없음)
  - Q13c: `copbit_q13c_lane_drift_limited_step_v0.py`  
    (고정 μ + `phi_max_deg` 제한)
  - **Q13d: `copbit_q13d_lane_drift_adaptive_mu_v0.py`**  
    (adaptive-step + `phi_max_deg` 제한 = 본 문서 대상)


---

## 2. Q13d – adaptive + limited-step Kuramoto 설정

### 2.1. 공통 파라미터 (Q13d 전용)

- 심벌 수:
  - 기본 스윕: `n_sym = 100,000`
  - 고 SNR 정밀 측정: `n_sym = 1,000,000`
- Eb/N0 리스트:
  - 기본: `[10, 12, 14]` dB
  - 하이 SNR 스윕: `[18, 20, 22, 24]` dB
- lane 수:
  - 기본 스윕: `L ∈ {4, 16, 64, 256}`
  - 고정밀 실험: `L = 64`에 집중
- drift_std_deg:
  - `0.25°, 0.5°, 1.0°, 2.0°, 3.0°` 등
- Kuramoto 파라미터:
  - `mu_phase = 0.1` (base step, adaptive 전)
  - `phi_max_deg = 10.0` (1-step 최대 위상 변경량 제한; rad로 변환 후 clip)

### 2.2. 업데이트 규칙 (요약)

1. lane별 slicing:
   - `z̃_n(l) = z_n(l) · e^{-j φ_est}`
   - `s_hat(l) = slicer_M8(z̃_n(l))`

2. error phasor 및 adaptive weight:
   - `err_phasor = mean_l( z_n(l) · s_hat(l)* )`
   - `err = angle(err_phasor)`
   - `w = |err_phasor| ∈ [0, 1]`

3. adaptive + step-limit:
   - `delta = μ_phase · w · err`
   - `delta ← clip(delta, ±phi_max_rad)`  (여기서 `phi_max_rad = phi_max_deg · π/180`)
   - `φ_est ← φ_est + delta`


---

## 3. 실험 결과

### 3.1. drift_std_deg = 0.25°, n_lanes = 64 (Q13d 핵심 케이스)

#### 3.1.1. n_sym = 1e5, Eb/N0 = 12~20 dB 예비 스윕 (대략적 추세)

- FFE-only (Base):
  - BER ≈ 0.45 ~ 0.55 (강 ISI + drift로 거의 난조 상태)
- Kuramoto(Q13d) 적용 후 대략:
  - 12 dB: BER ≈ 1.3e-1
  - 14 dB: BER ≈ 9.0e-2
  - 16 dB: BER ≈ 6.0e-2
  - 18 dB: BER ≈ 4.1e-2
  - 20 dB: BER ≈ 2.8e-2

→ `drift_std_deg = 0.25°` 정도로 관리되면,  
   64 lanes + adaptive Kuramoto 구조에서 **Eb/N0를 올릴수록 안정적으로 BER이 감소**하는 패턴이 명확하게 나타남.

#### 3.1.2. n_sym = 1e6, Eb/N0 = 18, 20, 22, 24 dB 정밀 측정

실제 로그:

```text
n_sym = 1_000_000
Eb/N0_list = [18.0, 20.0, 22.0, 24.0]
n_lanes = 64
drift_std_deg = 0.25

 n_lanes | EbN0_dB | BER_M8_base | BER_M8_kura(adapt)
------------------------------------------------------
     64 |    18.0 |   4.954e-01 |   4.092e-02
     64 |    20.0 |   5.347e-01 |   2.840e-02
     64 |    22.0 |   5.371e-01 |   2.069e-02
     64 |    24.0 |   4.807e-01 |   1.600e-02
------------------------------------------------------
	•	Base(FFE-only)는 여전히 약 0.48~0.54 수준의 랜덤 디코딩(≈0.5)에 가까움.
	•	Kuramoto(Q13d) 적용 후:
	•	18 dB: BER ≈ 4.1e-2
	•	20 dB: BER ≈ 2.8e-2
	•	22 dB: BER ≈ 2.1e-2
	•	24 dB: BER ≈ 1.6e-2

→ 강 ISI + drift + 멀티레인 환경에서도, drift_std_deg가 0.25° 수준이면
CoPBit-M8 + FFE + Q13d Kuramoto 조합이 pre-FEC 기준 BER 1e-2 수준까지 실제로 내려갈 수 있음을 확인.

⸻

3.2. drift_std_deg = 0.5° (기본 운영 후보 영역, n_sym = 1e5)

아래 결과는 copbit_q13d_lane_drift_adaptive_mu_v0.py 기본 스윕 로그에서 발췌.
================ drift_std_deg = 0.50 deg =================
 n_lanes | EbN0_dB | BER_M8_base | BER_M8_kura(adapt)
------------------------------------------------------
      4 |    10.0 |   4.827e-01 |   5.326e-01
      4 |    12.0 |   4.812e-01 |   4.573e-01
      4 |    14.0 |   4.420e-01 |   4.433e-01
     16 |    10.0 |   5.077e-01 |   5.427e-01
     16 |    12.0 |   4.796e-01 |   1.357e-01
     16 |    14.0 |   4.648e-01 |   9.289e-02
     64 |    10.0 |   3.930e-01 |   3.721e-01
     64 |    12.0 |   4.718e-01 |   1.339e-01
     64 |    14.0 |   5.051e-01 |   9.240e-02
    256 |    10.0 |   5.079e-01 |   1.865e-01
    256 |    12.0 |   4.825e-01 |   1.338e-01
    256 |    14.0 |   3.462e-01 |   9.225e-02
------------------------------------------------------
	•	drift_std_deg = 0.5°에서:
	•	lane 수가 충분히 크고(Eb/N0도 12 dB 이상)일 때
	•	Base는 여전히 0.35~0.50 수준의 난조
	•	Kuramoto(adapt)는 1.8e-1 ~ 9e-2 정도까지 BER을 크게 낮춤
	•	다만 4 lanes, 낮은 Eb/N0 조합 등에서는 여전히 락 실패/불안정 영역이 존재.

⸻

3.3. drift_std_deg = 1.0° (경계 영역)
================ drift_std_deg = 1.00 deg =================
 n_lanes | EbN0_dB | BER_M8_base | BER_M8_kura(adapt)
------------------------------------------------------
      4 |    10.0 |   5.398e-01 |   4.957e-01
      4 |    12.0 |   4.986e-01 |   5.175e-01
      4 |    14.0 |   5.475e-01 |   3.470e-01
     16 |    10.0 |   5.164e-01 |   5.319e-01
     16 |    12.0 |   5.509e-01 |   4.756e-01
     16 |    14.0 |   5.320e-01 |   4.106e-01
     64 |    10.0 |   4.775e-01 |   4.770e-01
     64 |    12.0 |   4.682e-01 |   5.286e-01
     64 |    14.0 |   5.057e-01 |   4.715e-01
    256 |    10.0 |   4.903e-01 |   4.333e-01
    256 |    12.0 |   5.384e-01 |   4.448e-01
    256 |    14.0 |   4.642e-01 |   3.392e-01
------------------------------------------------------
	•	특징:
	•	4 lanes, 14 dB에서 Base 0.5475 → Kuramoto 0.3470 수준으로 한 번 튀는 개선 존재.
	•	그러나 전체적으로 보면:
	•	어떤 조합은 조금 좋아지고,
	•	어떤 조합은 거의 비슷하거나 더 나빠짐.
	•	정성적으로:
	•	drift_std_deg = 1°는 “조건부 운영 가능” 경계 영역.
	•	adaptive-step이 있어도, Q13c(고정 μ + step-limit) 대비 운영 영역이 크게 넓어졌다고 보긴 어려움.

⸻

3.4. drift_std_deg = 2.0° (한계 영역 근처)
================ drift_std_deg = 2.00 deg =================
 n_lanes | EbN0_dB | BER_M8_base | BER_M8_kura(adapt)
------------------------------------------------------
      4 |    10.0 |   4.973e-01 |   4.972e-01
      4 |    12.0 |   5.290e-01 |   4.800e-01
      4 |    14.0 |   5.086e-01 |   5.079e-01
     16 |    10.0 |   4.921e-01 |   5.052e-01
     16 |    12.0 |   4.807e-01 |   5.142e-01
     16 |    14.0 |   4.721e-01 |   5.068e-01
     64 |    10.0 |   5.231e-01 |   4.918e-01
     64 |    12.0 |   5.086e-01 |   5.231e-01
     64 |    14.0 |   5.283e-01 |   4.893e-01
    256 |    10.0 |   5.353e-01 |   5.386e-01
    256 |    12.0 |   5.110e-01 |   5.197e-01
    256 |    14.0 |   5.089e-01 |   4.810e-01
------------------------------------------------------
	•	대부분 조합에서:
	•	BER_base ≈ 0.48~0.53
	•	BER_kura(adapt)도 거의 같은 범위
	•	전체적으로 랜덤 디코딩 수준(≈0.5)에서 크게 벗어나지 못하는, 락 실패 영역으로 해석하는 것이 타당.

⸻

3.5. drift_std_deg = 3.0° (no-lock 영역)
================ drift_std_deg = 3.00 deg =================
 n_lanes | EbN0_dB | BER_M8_base | BER_M8_kura(adapt)
------------------------------------------------------
      4 |    10.0 |   5.080e-01 |   5.001e-01
      4 |    12.0 |   4.877e-01 |   4.951e-01
      4 |    14.0 |   4.851e-01 |   4.951e-01
     16 |    10.0 |   5.152e-01 |   5.124e-01
     16 |    12.0 |   5.096e-01 |   5.070e-01
     16 |    14.0 |   4.948e-01 |   5.276e-01
     64 |    10.0 |   4.981e-01 |   4.933e-01
     64 |    12.0 |   5.037e-01 |   4.975e-01
     64 |    14.0 |   4.995e-01 |   4.908e-01
    256 |    10.0 |   5.211e-01 |   5.030e-01
    256 |    12.0 |   5.174e-01 |   4.973e-01
    256 |    14.0 |   5.010e-01 |   5.088e-01
------------------------------------------------------
	•	drift_std_deg가 3° 수준까지 커지면:
	•	lane 수, Eb/N0, adaptive-step, φ_max 제한을 모두 써도 구조적으로 락이 안 잡히는 no-lock zone.
	•	BER이 0.5 근처에 고정.

⸻

4. Q13b/Q13c와 비교한 패턴 해석

4.1. drift_std_deg = 0.25° ~ 0.5° (실질 운영 영역)
	•	Q13b/Q13c (고정 μ + step-limit)와 Q13d(adaptive μ)를 비교하면:
	•	drift_std_deg ≤ 0.5° + L ≥ 16 + Eb/N0 ≥ 12 dB 구간에서
	•	BER_kura는 대략 1.3e-1 ~ 9e-2 수준까지 안정적으로 내려감.
	•	Q13d의 adaptive-step은 이 영역에서:
	•	|err_phasor| ≈ 1에 가까워져서
	•	w ≈ 1 → 사실상 고정 μ와 유사한 동작을 보임.
	•	따라서:
	•	이미 Kuramoto가 잘 락을 잡는 “좋은 환경”에서는
	•	Q13b/Q13c vs Q13d 성능 차이는 미세.
	•	운영 스펙 관점에서는:
	•	drift_std_deg ≤ 0.5° 정도로 관리할 수 있다면,
Q13b/C/D 모두 실용적인 phase-lock 엔진으로 볼 수 있음.

4.2. drift_std_deg = 1.0° (경계 영역)
	•	1° 영역에서 adaptive-step 효과:
	•	일부 조합(예: 4 lanes, 14 dB)에서 뚜렷한 BER 개선이 보이지만,
	•	전 영역에 걸쳐 “안전 운영 구간”이 생겼다고 보긴 어려움.
	•	정리:
	•	drift_std_deg = 1°는
	•	lane 수, Eb/N0, 초기 조건, 난수에 따라
	•	“락이 잘 잡히는 케이스”와
	•	“락이 깨지는 케이스”가 섞여 나오는 borderline zone.
	•	adaptive-step은:
	•	락이 되는 케이스에서 급격한 폭주를 어느 정도 제어해 주지만,
	•	Q13c 대비 drift 허용 마진을 크게 확장시키는 수준까지는 아님.

4.3. drift_std_deg ≥ 2° (한계 / no-lock 영역)
	•	drift_std_deg가 2° 이상으로 커지면:
	•	대부분 조합에서 BER_kura(adapt) ≈ BER_base ≈ 0.48~0.54
	•	구조적으로 락이 깨져서, 사실상 랜덤 디코딩 수준.
	•	결론:
	•	Kuramoto 위상 락만으로는 drift_std_deg ≥ 2° 영역을 커버하기 어렵고,
	•	이 구간은 CoPBit 멀티레인 Kuramoto 아키텍처의 한계 영역으로 보는 것이 타당.

⸻

5. Q13 계열 전체 관점에서의 결론
	1.	운영 가능 영역 (실질 phase-lock zone)
	•	조건:
	•	drift_std_deg ≲ 0.5°
	•	n_lanes ≥ 16, Eb/N0 ≥ 12 dB
	•	이때:
	•	Base(FFE-only) 대비 Kuramoto(Q13b/c/d) 모두
	•	BER을 1.3e-1 ~ 9e-2 (또는 0.25°/고 SNR에서는 1e-2 수준)까지 크게 개선.
	•	강 ISI 채널 b에서도 CoPBit 위상 락 구조의 실효성을 확인.
	2.	경계 영역 (borderline zone)
	•	조건:
	•	drift_std_deg ≈ 1°
	•	특징:
	•	lane 수와 Eb/N0, 난수에 따라:
	•	어떤 조합에서는 의미 있는 BER 개선,
	•	어떤 조합에서는 거의 이득이 없거나 오히려 애매.
	•	adaptive-step(Q13d)는:
	•	폭주 제어에는 도움을 주지만,
	•	Q13c 대비 확실한 “마진 확장”까지는 증명되지 않음.
	3.	한계 / no-lock 영역
	•	조건:
	•	drift_std_deg ≥ 2°
	•	특징:
	•	lane↑, Eb/N0↑, adaptive-step, φ_max 모두 투입해도
	•	BER ≈ 0.5 수준에 머무르는 락 실패 영역.
	•	여기서는:
	•	추가 PLL/DLL,
	•	pilot-based tracking,
	•	phase quantization 구조 변경 등
	•	추가적인 위상 제어 메커니즘이 필요.
	4.	요약 메시지
	•	Q12c(FFE sweet spot) + Q13b/c/d를 통합해서 보면:
	•	**“강 ISI + 멀티레인 CoPBit에서, drift_std_deg가 0.25~0.5° 이하로 관리되는 환경”**이
1차적인 CoPBit phase-lock 아키텍처의 타깃 운영 영역.
	•	Q13d의 adaptive-step은:
	•	이미 락이 잘 되는 영역에서는 Q13c와 거의 동일한 성능,
	•	drift가 커지는 경계/한계 영역에서는 폭주 완화 정도의 부가 효과 수준으로 정리 가능.

⸻

6. 후속 아이디어 및 다음 스텝
	1.	Q13d 파라미터 확장
	•	phi_max_deg 스윕:
	•	예: 3°, 5°, 10° 등으로
	•	“보수적인 step-limit vs 수렴 속도” 트레이드오프 맵 확보.
	•	lane 수 확장:
	•	512, 1024 lanes 등 coarse 테스트로
	•	극단적인 멀티레인 환경에서 Kuramoto가 어디까지 버티는지 확인.
	2.	시스템 레벨 연결
	•	실제 CoPBit IO-bus에서 허용 가능한
	•	**위상 wander 스펙(drift_std_deg)**를 역산.
	•	이를 패키지/클럭/온도 조건과 연결:
	•	장기적으로는 “시스템 요구사항” 스펙 문서 초안과 연결 가능.
	3.	PAM4 대비 비교 그림
	•	동일 채널 b + 동일 FFE 구성에서:
	•	PAM4_FFE vs CoPBit_M8_Kuramoto(Q13b/c/d)를 한 그림에 올려서,
	•	“PAM4 동일 채널에서 CoPBit가 언제 이득을 줄 수 있는가”를
SNR–drift–lane 3축 중 2D 슬라이스(예: SNR–drift, SNR–lane)로 시각화.
	•	이 결과는 추후 ILC3/ILC4/CoPBit 비교 및 특허·사업계획서 자료의 핵심 그래프로 활용 가능.