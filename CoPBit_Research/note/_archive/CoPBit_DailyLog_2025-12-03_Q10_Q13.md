# CoPBit Daily Log – 2025-12-03 (Q10 ~ Q13)

## 0. 개요

오늘 목표:

- CoPBit 위상 구조의 **기본 이론 한계**를 M-PSK 기준으로 다시 점검 (Q10, Eb/N0 기준).
- 5-tap ISI 채널(a/b/c)에서 **PAM4 vs CoPBit-M8(8-PSK)** 성능을  
  - EQ 미적용 (Q12),
  - FFE/EQ 적용 (Q12b),
  - FFE 파라미터 스윕 (Q12c) 으로 체계적으로 비교.
- 강 ISI 채널 b에서 **x16 lanes + FFE + Kuramoto 위상 락(Q13)** 를 적용했을 때
  - PAM4_FFE 와 CoPBit-M8_Kura 의 BER 관계,
  - Kuramoto 위상 추적이 어느 정도까지 유효한지 확인.

---

## 1. 오늘 실행한 스크립트 목록

1. `copbit_q10_mpsk_awgn_ebn0_compare_v0.py`
   - 목적: AWGN-only, Eb/N0 페어 조건에서 BPSK/QPSK/8-PSK/16-PSK BER 곡선 확인.
   - 파라미터:
     - `n_sym = 200000`
     - `Eb/N0_list = [0,2,4,6,8,10,12,14,16]`
     - `M_list = [2,4,8,16]`

2. `copbit_q12_pam4_m8_channel_ebn0_v0.py`
   - 목적: 채널 a/b/c 위에서 **PAM4 vs M8(CoPBit)**, FFE 없이(no-EQ) BER 비교.
   - 파라미터:
     - `n_sym = 100000`
     - `Eb/N0_list = [0,2,4,6,8,10,12,14,16]`
     - `channels = ['a','b','c']`

3. `copbit_q12b_pam4_m8_channel_eq_ebn0_v0.py`
   - 목적: 채널 a/b/c 위에서 FFE(EQ) ON 상태의 **PAM4 vs M8** BER 비교.
   - 파라미터(두 번 실행):
     - 1차: `n_sym=100000, ffe_len=7,  train_frac=0.2`
     - 2차: `n_sym=200000, ffe_len=9,  train_frac=0.3`
     - `Eb/N0_list = [0,2,4,6,8,10,12,14,16]`
     - `channels = ['a','b','c']`

4. `copbit_q12c_ffe_sweep_channel_eq_ebn0_v0.py`
   - 목적: **강 ISI(채널 b)** 에서 FFE 길이/학습비율 스윕으로 sweet spot 탐색.
   - 파라미터:
     - 1차: `n_sym=100000, Eb/N0_list=[4,6,8,10,12,14,16]`
     - 2차: `n_sym=200000, Eb/N0_list=[8,10,12,14,16]`
     - `channels = ['b']`
     - `ffe_len_list = [5,7,9,11]`
     - `train_frac_list = [0.1,0.2,0.3]`

5. `copbit_q13_x16_eq_kuramoto_ber_v0.py`
   - 목적: 채널 b + FFE + x16 lanes + 글로벌 위상 드리프트 + Kuramoto 위상 추적에서
     - `BER_PAM4_FFE` vs `BER_M8_base` vs `BER_M8_kura` 비교.
   - 파라미터:
     - 공통: `n_sym = 200000`, `n_lanes=16`, `channel='b'`
     - 케이스 A:
       - `Eb/N0_list = [4,6,8,10,12,14,16]`
       - `ffe_len=5, train_frac=0.2`
       - `drift_std_deg = 0.5`, `mu_phase = 0.1`
     - 케이스 B:
       - `Eb/N0_list = [8,10,12,14,16]`
       - `drift_std_deg = 0.5`, `mu_phase = 0.1` (범위만 축소)
     - 케이스 C:
       - `Eb/N0_list = [8,10,12,14,16]`
       - `drift_std_deg = 3.0`, `mu_phase = 0.05` (강한 드리프트 테스트)

---

## 2. 핵심 결과 스냅샷

### 2.1 Q10 – M-PSK AWGN (Eb/N0 basis)

- 대표 결과 (n_sym=200k, Eb/N0_list=0~16 dB):

  - BPSK(M=2), QPSK(M=4):
    - Eb/N0 ≈ 6 dB에서 이미 BER ≈ 10⁻³ 이하
    - 8 dB 이상에서는 사실상 error-free 수준
  - 8-PSK(M=8):
    - Eb/N0 = 8 dB   → BER ≈ 1.1×10⁻²
    - Eb/N0 = 10 dB  → BER ≈ 1.6×10⁻³
    - Eb/N0 = 12 dB  → BER ≈ 1.4×10⁻⁴
  - 16-PSK(M=16):
    - Eb/N0 = 8 dB   → BER ≈ 7.7×10⁻²
    - Eb/N0 = 10 dB  → BER ≈ 3.8×10⁻²
    - Eb/N0 = 12 dB  → BER ≈ 1.3×10⁻²
    - Eb/N0 = 14 dB  → BER ≈ 2.6×10⁻³

→ **동일 Eb/N0 기준에서, M이 클수록 요구 SNR이 급격히 증가**.  
→ CoPBit 4bit(16-PSK)는 “상당히 높은 SNR 영역에서만 의미 있는 BER”이 가능.

---

### 2.2 Q12 – PAM4 vs CoPBit-M8 (채널 a/b/c, no-EQ)

- 스크립트: `copbit_q12_pam4_m8_channel_ebn0_v0.py`
- 공통 경향:

  - 세 채널(a/b/c 모두)에서:
    - **PAM4_noEQ BER ≈ 0.18~0.23 수준에서 거의 평탄**
    - **M8_noEQ BER ≈ 0.24~0.32 수준에서 평탄**
  - Eb/N0가 올라가도 **ISI가 지배** → noise 감소 효과보다 **채널 메모리 효과가 더 큼**.

- 예: 채널 b (가장 강한 ISI) 결과 일부

  - Eb/N0=0 dB: PAM4 2.78e-1, M8 3.37e-1
  - Eb/N0=16 dB: PAM4 2.27e-1, M8 2.65e-1

→ **EQ 없이 ISI 채널에서 CoPBit 위상만 사용하는 것은 BER 측면에서 불리**.  
→ PAM4도 좋다고 할 수는 없지만, 같은 조건에서 항상 더 낮은 BER.

---

### 2.3 Q12b – PAM4 vs M8 + FFE (채널 a/b/c)

- 스크립트: `copbit_q12b_pam4_m8_channel_eq_ebn0_v0.py`

#### (1) 채널 a (가장 깨끗한 ISI)

- Eb/N0가 올라갈수록 FFE 효과가 명확:

  - PAM4_FFE:
    - 4 dB: ≈ 1.74e-1
    - 8 dB: ≈ 8.7e-2
    - 12 dB: ≈ 2.2e-2
    - 16 dB: ≈ 1.0e-3 수준
  - M8_FFE:
    - 4 dB: ≈ 2.46e-1
    - 8 dB: ≈ 1.2e-1
    - 12 dB: ≈ 2.7e-2
    - 16 dB: ≈ 1e-3 근처

→ 채널 a에서는 **FFE ON 기준으로 PAM4와 M8의 BER가 비슷한 오더**까지 내려옴.  
→ 다만, 여전히 low Eb/N0 영역에서 PAM4 우위.

#### (2) 채널 b (강 ISI)

- noEQ vs FFE 비교:

  - PAM4:
    - noEQ는 0.23 근처에서 거의 평탄.
    - FFE(ffe_len≈9, train_frac≈0.3) 적용 시, 16 dB 에서 ≈ 7.6e-2 수준까지 개선.
  - M8:
    - noEQ는 0.27~0.32 수준.
    - FFE 적용 후에도 여전히 PAM4보다 0.03~0.05 정도 더 높은 BER.

#### (3) 채널 c (중간 ISI)

- 경향은 채널 b와 유사하나, ISI 강도가 약간 약해져 전반적인 BER이 조금 더 낮음.
- 그래도 **PAM4_FFE가 항상 M8_FFE보다 유리**.

---

### 2.4 Q12c – 채널 b에서 FFE 파라미터 스윕

- 스크립트: `copbit_q12c_ffe_sweep_channel_eq_ebn0_v0.py`
- 탐색 공간:
  - `ffe_len_list = [5,7,9,11]`
  - `train_frac_list = [0.1,0.2,0.3]`
  - `Eb/N0_list = [8,10,12,14,16]`
  - 채널 b 하나만 대상.

#### 관찰 요약

1. **PAM4_FFE**
   - ffe_len=5, train_frac=0.1~0.3 정도에서 이미 꽤 좋은 균형.
   - 16 dB 기준 BER:
     - ffe_len=5 → ≈ 7.3e-2
     - ffe_len=7~11 → 비슷하거나 살짝 더 나빠지는 정도.
   - ⇒ **과도하게 긴 FFE는 큰 이득 없이 복잡도만 증가**.

2. **M8_FFE**
   - 동일 FFE 파라미터에서 항상 PAM4보다 높은 BER.
   - ffe_len, train_frac를 키워도 PAM4 수준까지는 내려오지 않음.
   - 특히 8 dB 근처에서는 **FFE가 과적합/왜곡을 만들어 BER이 오히려 나빠지는 케이스도 존재**.

3. **Sweet spot**
   - Q13에 사용할 파라미터로:
     - `ffe_len = 5`, `train_frac = 0.2` 선택.
   - 이유:
     - PAM4 기준으로는 가장 단순하면서도 안정적으로 BER 개선.
     - M8 쪽은 어차피 PAM4를 역전하진 못하지만, multi-lane + Kuramoto 실험을 위한 “합리적인 EQ baseline” 용도로 충분.

---

### 2.5 Q13 – x16 lanes + FFE + Kuramoto (채널 b)

- 스크립트: `copbit_q13_x16_eq_kuramoto_ber_v0.py`
- 조건:
  - `n_sym=200000`, `n_lanes=16`, 채널 b.
  - FFE: `ffe_len=5`, `train_frac=0.2` (Q12c sweet spot).
  - PAM4: 단일 레인 기준, 채널 b + FFE 후 BER.
  - M8:
    - x16 lanes 모든 심볼에 대해 글로벌 드리프트 φ[n] 추가.
    - `BER_M8_base`: 드리프트 무시 (즉, 잘못된 위상 기준) 상태에서 독립 디코딩.
    - `BER_M8_kura`: Kuramoto-style 위상 추적 후 디코딩.

#### (A) drift_std_deg = 0.5, mu_phase = 0.1

- 결과(대표):

  - Eb/N0 = 8 dB:
    - PAM4_FFE ≈ 1.66e-1
    - M8_base  ≈ 4.55e-1
    - M8_kura  ≈ 4.37e-1  (개선 거의 없음)
  - Eb/N0 = 12 dB:
    - PAM4_FFE ≈ 1.00e-1
    - M8_base  ≈ 4.78e-1
    - M8_kura  ≈ 1.35e-1  (**강한 개선, ~3.4× BER 감소**)
  - Eb/N0 = 16 dB:
    - PAM4_FFE ≈ 5.7e-2
    - M8_base  ≈ 4.86e-1
    - M8_kura  ≈ 6.25e-2

→ 해석:

- **Kuramoto가 제대로 작동하는 SNR 영역(12~16 dB)에서는**
  - M8_base (사실상 랜덤에 가까운 상태)를  
    M8_kura ≈ 0.06~0.13 수준으로 강하게 끌어내림.
- 하지만, **PAM4_FFE와 비교하면 여전히 근소 열세 또는 비슷한 수준**:
  - 16 dB에서 PAM4_FFE ≈ 0.057 vs M8_kura ≈ 0.063.

#### (B) drift_std_deg = 3.0, mu_phase = 0.05

- 결과(대표):

  - Eb/N0 = 8~16 dB에서
    - M8_base, M8_kura 모두 ≈ 0.5 부근.
    - Kuramoto가 사실상 위상 락을 못 잡고 “랜덤 디코딩 수준”에 머무름.

→ 해석:

- **드리프트가 너무 크면(x16, drift_std_deg=3°)**  
  현재 구조의 Kuramoto 추적은 수렴이 어렵고, BER 개선도 거의 불가능.
- 이 영역은 “Kuramoto-only로는 감당 불가 → 추가 PLL / pilot / 계층적 위상 추적 설계가 필요한 영역”으로 분류 가능.

---

## 3. 오늘 정리한 인사이트

1. **Q10: 기본 위상 변조 이론 정리**
   - Eb/N0 기준에서 M-PSK의 BER 곡선을 확보 →  
     CoPBit 8-PSK/16-PSK가 “얼마나 높은 SNR을 요구하는지” 명확하게 수치화.
   - **M=8**: BER 10⁻²를 목표로 하면 Eb/N0 ≈ 8 dB 이상 필요.
   - **M=16**: 같은 BER 목표로 8-PSK보다 **몇 dB 높은 Eb/N0**가 필요.

2. **Q12: ISI 채널에서 CoPBit 단일 레인 한계**
   - ISI 채널 a/b/c 위에서 no-EQ 조건에서는  
     PAM4와 M8 모두 “BER 평탄 영역(≈ 0.18~0.32)”에 갇힘.
   - FFE/EQ를 써도:
     - 채널 a처럼 “상대적으로 깨끗한 ISI”에서는 M8이 PAM4와 비슷한 수준까지 접근.
     - 강 ISI(b)에서는 PAM4_FFE가 항상 M8_FFE 보다 낫거나 비슷하고,  
       M8이 “우위”를 보이는 영역은 없음.

3. **Q12c: FFE sweet spot**
   - **강 ISI(b)** 기준:
     - `ffe_len=5, train_frac=0.2` 정도가 단순성과 성능 모두 괜찮은 sweet spot.
     - FFE를 더 길게 가져가도, M8에게 특별한 이득은 없고  
       오히려 학습 난이도/과적합 가능성만 증가.

4. **Q13: 멀티레인 + Kuramoto의 역할**
   - x16 lanes, drift_std_deg=0.5 정도의 **중간 수준 드리프트** 에서는:
     - Kuramoto 위상 추적이 **M8_base의 완전 붕괴(BER≈0.48)** 를  
       M8_kura ≈ 0.06~0.13 수준으로 안정화시켜 줌.
     - 그러나, 같은 조건에서 PAM4_FFE 도 이미 0.06~0.10 수준이므로  
       “CoPBit-M8이 확실히 이긴다”라고 말할 수 있는 구간은 아직 없음.
   - drift_std_deg=3.0처럼 **아주 강한 드리프트** 에서는:
     - Kuramoto만으로는 수렴 불가 → BER ≈ 0.5 유지.
     - 이 영역은 **PLL / pilot 기반 보조 루프, 또는 lane 그룹 단위의 계층적 Kuramoto 설계**가 필수.

5. **오늘까지의 결론 (1-lane + x16-lane 기준)**
   - 현재 구조/파라미터에서는:
     - **“CoPBit 위상만으로, PAM4+FFE를 압도하는 시나리오”는 아직 안 나옴.**
     - 대신, CoPBit-M8은
       - “위상 드리프트가 존재하는 환경에서 **멀티레인 Kuramoto를 붙이면**  
         완전히 망가질 BER을 10⁻¹ ~ 10⁻² 수준으로 유지시킬 수 있다”는  
         **위상-복원/추적 능력 데모**로 보는 것이 타당.

---

## 4. 다음 스텝 아이디어

1. **Q13b (파라미터 튜닝)**
   - mu_phase, drift_std_deg, n_lanes (x16→x64→x256…) 를 스윕해서:
     - “lane 수 증가 vs 위상 락 성능” 관계,
     - “Kuramoto가 진짜로 lane 수에 비례하여 이득을 주는지” 정량화.

2. **Q13c (계층적 위상 추적 구조)**
   - 1024 lane을 예로:
     - 32-lane 그룹 단위로 Kuramoto 1차 추적,
     - 그룹 센터끼리 2차 Kuramoto/PLL,
     - 마지막에 전체 global 위상을 복원하는 계층형 구조 실험.

3. **Q14 (PAM4 vs CoPBit 하이브리드)**
   - 진폭+위상 조합 (예: 2-level AMP + 8-PSK 위상) 등,
   - “진폭은 최소, 위상은 M을 줄인 상태”의 하이브리드 스킴을 설계해서
     - PAM4와의 실질적인 트레이드오프,
     - 회로 복잡도 vs BER vs SNR 관점에서 “CoPBit가 유리한 sweet spot” 찾기.

---

_작성일: 2025-12-03 (CoPBit_Research, Q10~Q13 정리)_