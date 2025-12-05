# CoPBit Q16 – 2-lane p_ref + data, AWGN + 공통 Phase-noise v0.1

## 1. 실험 목적

- 1-lane M8 + DD-PLL만으로는 CoPBit의 장점을 충분히 보여주기 어렵다.
- 최소 2-lane 구조:
  - Lane0: p_ref lane (고정 8-PSK index, 기준 위상축)
  - Lane1: data lane (3bit/sym 랜덤 M8)
- 공통 위상 노이즈(oscillator drift)를 걸어준 뒤,
  - (a) PLL 없음
  - (b) data-lane만 이용한 DD-PLL
  - (c) data + p_ref를 함께 사용하는 Kuramoto-style 위상락
- 위 3가지 케이스의 BER을 비교하여,
  - “어느 정도의 phase-noise 영역에서 p_ref lane이 필수적인지”
  - “2-lane 최소 모델에서 CoPBit의 위상 잠금 효과가 어느 정도인지”
  를 정량적으로 평가한다.

---

## 2. 기본 모드 정의 (PhaseLock_std 모드)

- **Modem**
  - 변조: M8 (8-PSK, 3bit/sym, unit circle)
  - Lane0 (p_ref):
    - 모든 심볼이 동일한 index `k_ref_const = 0` (각도 0°)
  - Lane1 (data):
    - 3bit/sym 랜덤 비트 → M8 index → 8-PSK 심볼
- **채널**
  - no-ISI, `h = [1]`
  - 공통 phase-noise (Wiener process):
    - 심볼당 위상 증가량 Δφ ~ N(0, σ²)
    - σ = `theta_std_deg` [deg]를 radian으로 변환 후 누적 (`phi_k = Σ Δφ_i`)
  - AWGN:
    - Eb/N0 기준 noise 추가
    - bits/sym = 3 (M8)
- **Rx 모드**
  - Mode #1: **No PLL**
    - data lane 수신 신호에 단순 8-PSK slicer 적용
  - Mode #2: **Data-DD only**
    - data lane만으로 DD-PLL 수행
    - 추정 위상 φ_k를 하나 두고, `err_data_phasor`로만 업데이트
  - Mode #3: **Data + p_ref Kuramoto**
    - 공통 위상 φ_k를 하나 두고,
    - p_ref lane + data lane의 에러 phasor를 섞어 업데이트
    - `total_err = (1-α)*err_ref + α*err_data`
    - α = `alpha_ref` (0.0 → ref-only, 1.0 → data-only)

---

## 3. 실험 설정 (Phase-noise Regime 스윕)

- 공통 설정
  - 심볼 수: n_sym = 200,000
  - Eb/N0 리스트: [8, 10, 12, 14, 16] dB (필요 시 [12, 14, 16]으로 subset)
  - bits/symbol: 3 (M8)
  - mu_phase: 0.05
  - seed: 1
- Phase-noise 표준편차 (θ_std_deg)
  - Regime A: 0° (no phase-noise)
  - Regime B: 1°
  - Regime C: 3°
  - Regime D: 5°
- alpha_ref (Regime별 기본값)
  - Regime A/B/C/D 초기 실험: alpha_ref = 0.3

---

## 4. θ_std_deg 스윕 결과 (예시)

### 4.1 Regime A – θ_std_deg = 0° (no phase-noise)

```text
Eb/N0_dB |  BER_noPLL   |  BER_DDonly  |  BER_DD+pRef
------------------------------------------------------
   12.0  |  ~8.0e-05    |  ~9.5e-05    |  ~8.8e-05
   14.0  |  ~1.7e-06    |  ~1.7e-06    |  ~1.7e-06
   16.0  |     0        |     0        |     0

	•	요약:
	•	위상 노이즈가 없으면 No PLL / DDonly / DD+pRef는 모두 AWGN 한계에서 동일.
	•	2-lane p_ref 구조는 이 구간에서 장/단점 없이 “중립”.
4.2 Regime B – θ_std_deg = 1° (약한 phase-noise)

(실측 값 붙이기)
Eb/N0_dB |  BER_noPLL   |  BER_DDonly  |  BER_DD+pRef
------------------------------------------------------
   12.0  |  ~5.0e-01    |  ~5.7e-04    |  ~4.8e-04
   14.0  |  ~4.5e-01    |  ~4.2e-05    |  ~4.2e-05
   16.0  |  ~4.9e-01    |  ~1.7e-06    |  ~1.7e-06

	•	요약:
	•	No PLL: BER ~ 0.45~0.5 (위상 드리프트 때문에 거의 랜덤)
	•	Data-DD only:
	•	이미 BER ~ 10⁻⁴~10⁻⁶까지 잘 떨어지는 구간
	•	Data + p_ref:
	•	DD-only 대비 약간의 margin 향상
	•	해석:
	•	약한 phase-noise에서는 1-lane DD-PLL만으로도 충분히 위상 추적 가능.
	•	p_ref lane은 “필수”라기보다는, robust margin 확보용.
4.3 Regime C – θ_std_deg = 3° (중간~강한 phase-noise)

(실측 값 붙이기)
Eb/N0_dB |  BER_noPLL   |  BER_DDonly  |  BER_DD+pRef
------------------------------------------------------
   12.0  |  ~0.50       |  ~0.50       |  ~3.8e-02
   14.0  |  ~0.51       |  ~0.53       |  ~3.0e-02
   16.0  |  ~0.50       |  ~0.50       |  ~2.6e-02

	•	요약:
	•	No PLL / Data-DD only:
	•	Eb/N0를 올려도 BER ≈ 0.5 근처에서 수렴 → 완전 붕괴.
	•	Data + p_ref:
	•	같은 조건에서 BER ≈ 2~4%까지 복구.
	•	해석:
	•	이 구간은 “1-lane M8+PLL로는 아무것도 못하지만, 2-lane p_ref Kuramoto만 살아남는 영역”.
	•	실질적으로 CoPBit 위상-결합 구조가 반드시 필요해지는 임계 구간.

4.4 Regime D – θ_std_deg = 5° (강한 phase-noise)

(실측 값 붙이기)
Eb/N0_dB |  BER_noPLL   |  BER_DDonly  |  BER_DD+pRef
------------------------------------------------------
   12.0  |  ~0.49       |  ~0.49       |  ~0.149
   14.0  |  ~0.50       |  ~0.50       |  ~0.142
   16.0  |  ~0.50       |  ~0.51       |  ~0.136

	•	요약:
	•	No PLL / Data-DD only:
	•	여전히 랜덤 수준(0.5).
	•	Data + p_ref:
	•	13~15% 수준으로 znac한 개선이지만, 여전히 높은 BER floor.
	•	해석:
	•	2-lane 최소 모델로는 이 정도 phase-noise에서 완전한 락은 불가능.
	•	향후:
	•	lane 수 확장(예: 64L Kuramoto),
	•	mu_phase 및 에러 가중치 튜닝,
	•	guard-phase와 병행
을 통해 이 영역까지 끌어올 수 있을지 검토 필요.

5. θ=3°에서 alpha_ref 스윕 결과 (자동 생성 테이블)
	•	실험 커맨드:
ALPHA_LIST="0.0 0.1 0.3 0.5 0.8 1.0"

for A in $ALPHA_LIST; do
  python copbit_q16_2lane_pref_awgn_phase_v0.py \
    --n_sym 200000 \
    --ebn0_list "12,14,16" \
    --theta_std_deg 3.0 \
    --mu_phase 0.05 \
    --alpha_ref ${A} \
    --seed 1 \
    > ../note/Q16_theta3p0_alpha${A}.log
done

6. 설계 관점 정리
	1.	Regime A/B (θ_std_deg ≲ 1°)
	•	1-lane DD-PLL만으로 충분.
	•	CoPBit p_ref lane은 “필수”가 아닌, 안정 margin 확장 역할.
	2.	Regime C (θ_std_deg ≈ 3°)
	•	1-lane PLL 완전 붕괴(≈0.5).
	•	2-lane p_ref Kuramoto만 의미 있는 BER(2~4%)를 달성.
	•	“CoPBit 위상-결합 구조가 필요해지는 최소 phase-noise 스펙”으로 정의 가능.
	3.	Regime D (θ_std_deg ≳ 5°)
	•	2-lane만으로는 BER floor ≈ 0.14 수준.
	•	실제 CoPBit 64L/1024L 설계 시:
	•	lane 수 확장 + guard-phase + 최적 mu_phase/alpha_ref 조합으로
	•	이 영역까지 커버할 수 있는지 추가 검증 필요.