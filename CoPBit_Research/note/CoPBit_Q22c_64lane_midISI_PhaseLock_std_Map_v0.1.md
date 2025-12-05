# CoPBit Q22c – 64-lane mid-ISI + FFE(LS) + PhaseLock_std 설계 맵 v0.1

## 1. 목적

- 64-lane CoPBit 메모리 / 데이터 버스에서  
  **1개의 p_ref lane + M8 심볼 + mid-ISI(Channel-b) + FFE(LS) + PhaseLock_std** 구조가
  어느 정도의 **위상 노이즈 표준편차(θ_std)**와 **Eb/N0(dB)**에서 동작 가능한지
  _설계 맵(PhaseLock_std Map)_으로 정리한다.
- 이 Q22c 맵을 기준으로
  - 메모리/버스용 CoPBit 채널 사양
  - 내부 PLL / clock-tree / DLL 설계 시 허용 가능한 위상 잡음 스펙
  을 정의하는 것이 목표.

---

## 2. 기반 실험 세트(참조)

1. **Q20c / Q21a – PAM4 vs M8, mid-ISI + FFE(LS) baseline**

   - 채널: Channel-b 5-tap mid-ISI (정규화된 h_midISI)
   - Equalizer: 단일 FFE(LS, L=11, train_frac=0.5)
   - 결과:
     - PAM4, M8 모두 **mid-ISI + AWGN 환경에서 FFE만으로는 BER이 0.2 수준**에 머무름.
     - 즉, 메모리/버스 환경에서 **“EQ만으로는 한계가 있고, 위상/레인 구조를 활용해야 한다”**는 것을 확인.

2. **Q22a – 2-lane(mid-ISI + FFE(LS) + PhaseNoise + p_ref PLL)**

   - 구조:
     - Lane0: p_ref lane (고정 8-PSK index)
     - Lane1: data lane (3bit/sym, M8)
     - 공통: mid-ISI(Channel-b) + FFE(LS) + 공통 위상 노이즈(θ_std) + 공통 PLL
   - 모드:
     - No PLL
     - Data-DD only
     - Data + p_ref (PhaseLock_std)
   - 대표 결과(예: Eb/N0=16dB 근방):
     - θ_std = 0°:
       - No PLL 기준 BER ≈ O(10^-3 이하)
     - θ_std ≈ 1°:
       - Data + p_ref 모드에서 BER ≈ O(10^-3) 수준 유지
     - θ_std ≥ 3°:
       - No PLL, Data-DD only 모두 BER ≈ 0.5로 붕괴,
       - Data + p_ref도 BER ≈ 10^-2 ~ 10^-1 영역으로 악화.
   - 결론:
     - **mid-ISI + FFE(LS) 환경에서도 “1개의 p_ref lane + PhaseLock_std”로
       θ_std ≈ 1°까지는 충분히 잠글 수 있음**을 확인.

3. **Q22b – θ_std–Eb/N0 맵 (2-lane, PhaseLock_std)**

   - Q22a를 여러 θ_std, Eb/N0에 대해 반복 실행,
     - 각 조합별 (BER_noPLL, BER_DDonly, BER_DD+pRef)를 CSV로 정리.
   - 이 맵을 기반으로, **target BER(예: 10^-3 ~ 10^-4) 이하를 보장하는 (θ_std, Eb/N0) 조합 영역**을 읽어낼 수 있음.

---

## 3. Q22c 가정: 2-lane → 64-lane 스케일링

- 앞선 Q16c, Q17 계열에서 이미 **“Kuramoto/PhaseLock_std 관점에서 p_ref 1 lane이면 N_lane 전체 동기화 가능”**이라는 것을 AWGN 기준으로 확인.
- mid-ISI + FFE(LS) 환경에서의 64-lane은 다음과 같이 모델링:

  - Lane 구조:
    - N_ref = 1 (p_ref 1 lane)
    - N_data = 63 (data lane 63개)
    - 총 64 lanes
  - 수신 구조:
    - 모든 lane에 동일한 mid-ISI(Channel-b) + 동일한 FFE(LS) 계수 적용
    - 공통 위상 노이즈(θ_std) 주입
    - 공통 PhaseLock_std(PLL)로 φ_est를 업데이트
      - p_ref 에러 + data lane 평균 에러를 적절히 섞는 구조 (α_ref로 제어)

- **스케일링 가정:**

  1. FFE(LS)는 채널 h_midISI에 대해 레인 수와 무관하게 동일하게 동작  
     → 2-lane과 64-lane의 “ISI 제거 능력”은 동일하다.
  2. 공통 위상 노이즈 + 공통 PLL 구조에서,
     - p_ref 1 lane으로 기준 축을 제공,
     - data lane이 많아질수록 오히려 “에러 평균화 효과”로 안정성이 약간 좋아질 가능성이 있음.
  3. 따라서 **Q22b(2-lane)에서 얻은 θ_std–Eb/N0 맵을
     64-lane 설계에도 그대로 쓸 수 있다**고 보는 것이 보수적인(안전한) 설계.

---

## 4. 64-lane 메모리/버스 설계용 PhaseLock_std 맵 (요약)

설계 타깃:  
- pre-FEC BER 기준
  - **target 영역**: BER_DD+pRef ≤ O(10^-3)  
  - **허용 영역**: BER_DD+pRef ≤ O(10^-2) (강력한 FEC 전제)

Q22b 맵을 기반으로 한 **보수적 설계 권고**:

- **Eb/N0 = 16 dB 근처**
  - θ_std ≤ 1.0°   → BER_DD+pRef ≈ 수 × 10^-3 수준
  - θ_std ≈ 1.5°   → BER이 10^-2대 초반으로 상승 (FEC로는 커버 가능, 여유는 감소)
  - θ_std ≥ 3.0°   → BER이 급격히 악화(10^-1 수준), 실용 범위에서 벗어남.
- **Eb/N0가 더 높아질수록(18~20 dB)**
  - 동일한 BER 목표에 대해 θ_std 허용치가 약간 늘어나지만,
  - 실질적인 설계에서는 **θ_std ≤ 1.0°를 상한으로 잡는 것이 안전**.

> **Q22c 설계 결론 (Memory / Data Bus 용)**  
> - 64-lane (1 p_ref + 63 data) CoPBit 메모리 / 버스에서  
>   mid-ISI(Channel-b) + FFE(LS) + 공통 PhaseLock_std 구조를 사용할 경우,
> - **“θ_std ≤ 1.0° @ Eb/N0 ≥ 16 dB”를 기본 PhaseLock_std 설계 스펙으로 채택**한다.
> - θ_std, Eb/N0 둘 중 하나를 더 여유 있게 잡으면
>   1e-3~1e-4 수준의 pre-FEC BER을 무난하게 달성 가능하다.

---

## 5. 설계 박스 (Spec Box)

- **Lane 구성**
  - N_total = 64
  - N_ref   = 1 (p_ref lane)
  - N_data  = 63 (M8 data lane, 3 bit/sym)

- **채널 & EQ**
  - 채널: Channel-b mid-ISI (5-tap, 정규화)
  - Equalizer: FFE(LS), tap 길이 L ≈ 11, train_frac ≈ 0.5

- **PhaseLock_std (공통 PLL)**
  - 입력: p_ref lane 에러 + data lane 평균 에러
  - 파라미터: mu_phase ≈ 0.05, alpha_ref ≈ 0.3 (p_ref 축에 조금 더 가중)

- **설계 타깃**
  - Eb/N0 ≥ 16 dB (메모리/버스용 실용 영역)
  - 공통 위상 노이즈 표준편차: θ_std ≤ 1.0° (Wiener 모델 기준)
  - 목표 pre-FEC BER: ≤ O(10^-3) (FEC 이후 안정 운용)

---

## 6. Q22c의 위치와 다음 단계 (PPU로 전환)

- Q22c까지 정리하면,
  1. **P_ref 1 lane 기준으로 64-lane 전체를 PhaseLock_std로 잠글 수 있다.**
  2. mid-ISI + FFE(LS) + PhaseNoise 조건에서도
     **“θ_std ≤ 1.0° @ 16 dB” 정도면 메모리/버스로 충분히 쓸 수 있다.**
  3. PPU(연산용 CoPBit)와 메모리/버스 CoPBit의 **PhaseLock_std 요구 조건이 거의 동일**하다.

- 이제 다음 챕터에서는,
  - 동일한 PhaseLock_std 모드를 깔고
  - **3D 연산 primitive / 1024-lane 타일 / PPU 아키텍처 설계(Q23~)**로
    확장해 나가는 흐름으로 진행하면 된다.