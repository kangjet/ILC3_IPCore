# CoPBit Q20 – 메모리/버스 채널 설계 로드맵 v0.1

## 1. 목적

Q16~Q19에서 다음이 확인되었다.

1. **연산용 PPU(초근거리, 약한 ISI, AWGN + 공통 위상잡음)**  
   - 1개 p_ref lane만으로도 Kuramoto PhaseLock_std 조건을 만족.
   - 1024L 타일 (1 p_ref + 1023 data) 구조로 PPU primitive 정의 가능.

2. **Channel-b mid-ISI + 1-sps FFE-only(Q18)**  
   - PAM4/M8 모두 BER ≈ 0.27 수준에서 플로어 발생.  
   - Eb/N0 10~28 dB를 올려도 1e-3 영역에 진입하지 못함.  
   - ⇒ 이 구조로는 **외부 메모리/버스 채널을 커버하기 어렵다**는 “실패 베이스라인”임.

Q20의 목표는:

- **CoPBit 메모리/버스 채널 구조를 설계 관점에서 정의**하고,
- **어떤 블록(EQ/FSE/DFE 등)이 추가되면 1e-3 수준(SDR/HBM급 pre-FEC 목표)에 접근 가능한지**를 로드맵 형태로 정리하는 것.

---

## 2. 타겟 채널 & 성능 목표

### 2.1 채널 모델

- 기준 mid-ISI 채널: Q18에서 사용한 Channel-b (5-tap, symbol-rate)  
  \[
  h_\text{b} = [0.05, 0.5, 1.0, 0.5, 0.05] / \sum
  \]
- 향후 확장:
  - 실제 패키지/PCB 기반 채널 임피던스 모델(S-parameter → 타임도메인)
  - HBM/GDDR7 레퍼런스 채널과 비슷한 ISI 강도/진폭을 갖는 모델

### 2.2 성능 목표

- **목표 BER (pre-FEC 기준)**  
  - 연산용 PPU: 1e-3 ~ 1e-4에서 충분 (초근거리, 내부 on-die 링크)  
  - 메모리/버스: 표준 DRAM/SerDes를 참고해  
    - **pre-FEC 1e-4 ~ 1e-5**,  
    - post-FEC 1e-12 수준을 장기 목표로 둔다.

- **비교 기준**
  - 동일 채널, 동일 대역폭/전력 조건에서  
    - PAM4 + 기존 EQ/FEC  
    vs  
    - CoPBit (M8 or M16) + PhaseLock_std + EQ/FEC

---

## 3. RX 구조 분리: EQ vs PhaseLock_std

Q18 결과는 “FFA-only 실패”를 보여줬고, 이걸 바탕으로 **역할 분리**가 명확해진다.

### 3.1 EQ 블록 (Amplitude/ISI 처리)

- 역할:
  - **진폭/ISI 보상** 담당
  - 채널-b 같은 강한 mid-ISI를 감당하는 전통적인 블록
- 후보 구조:
  - 1-sps FFE + DFE
  - 2-sps Fractionally-Spaced Equalizer(FSE) + DFE
  - Tomlinson-Harashima Precoding(THP) + Rx FFE
  - MLSE / BCJR 등 고급 탐색 기반 (연구용)

### 3.2 PhaseLock_std 블록 (Phase/Kuramoto 처리)

- 역할:
  - **위상 드리프트/위상 잡음 처리** 담당
  - Q16~Q17에서 테스트된 Kuramoto 스타일 PLL
- 입력:
  - EQ 후 복소 신호 \(z[n]\)
- 동작:
  - p_ref lane 1개 + data lane 에러 평균 → total_err  
  - PhaseLock_std 모드에 따라 공통 위상 \(\phi_\text{common}[n]\) 업데이트

### 3.3 설계 원칙

- **원칙 A – 직렬 구조**  
  - 채널 → EQ(FSE/DFE 등) → CoPBit PhaseLock_std → slicer
  - Q18의 “FFE-only 실패”는 **EQ만으로 mid-ISI를 다 못 잡는 구조**였다는 것을 의미.
- **원칙 B – 블록 디커플링**  
  - EQ 설계와 PhaseLock_std 설계를 논리적으로 분리:
    - EQ: “PAM4든 M8이든” 동일하게 채널을 평탄화
    - PhaseLock_std: **CoPBit만의 위상 자유도**를 활용해 PPU/버스에서 추가 이득 확보
- **원칙 C – PPU vs 메모리 분리**  
  - PPU 코어는 “AWGN + 약한 ISI” 가정으로 Q16~Q19 실험과 연결
  - 메모리/버스 구간은 **강한 ISI + EQ 중심 설계**로 따로 다룬다.

---

## 4. Q20 시리즈 실험 계획(스케치)

### 4.1 Q20a – EQ 개선 vs Q18 비교 (기초)

- 스크립트 예:
  - `copbit_q20a_pam4_vs_m8_midISI_ffe_dfe_v0.py`
- 내용:
  - Channel-b + 1-sps FFE + DFE(단일 레인) 구조
  - PAM4 vs M8 비교, BER vs Eb/N0
  - 목표: **FFE+DFE만으로 1e-3 근처까지 진입 가능한지 확인**

### 4.2 Q20b – FSE(2-sps) + DFE + CoPBit PhaseLock_std

- 스크립트 예:
  - `copbit_q20b_m8_midISI_fse2_dfe_phase_v0.py`
- 내용:
  - 2-sps FSE로 채널 대각화 + 간단한 DFE
  - 그 뒤에 Q16 스타일 PhaseLock_std 추가
  - 1 lane 기준으로 1e-3 목표 달성 여부 검증

### 4.3 Q20c – Multi-lane (1024L 타일 축소 버전, 예: 8L or 16L)

- 스크립트 예:
  - `copbit_q20c_multilane_midISI_fse_phase_v0.py`
- 내용:
  - N_lane = 8 또는 16으로 줄인 mini-tile
  - (N_ref=1, N_data=N_lane-1) 구성
  - FSE+PhaseLock_std가 multi-lane에서 얼마나 안정적으로 동작하는지 확인

### 4.4 Q20d – 메모리/버스 모드 vs PPU 모드 비교

- Q19에서 정의한 **PPU 타일**과,
- Q20b/c에서 나온 **메모리/버스 타일**을
- 동일한 M8/M16 심볼 구조/BER 목표로 나란히 정리.

---

## 5. 결론 및 방향성

1. **연산용 CoPBit PPU**  
   - Q16~Q19 결과로 봤을 때,
   - AWGN + 공통 위상 잡음 환경에서는  
     **1 p_ref + 다수 data lane 구조만으로 Kuramoto PhaseLock_std 구현 가능**.
   - 1024L 타일(1 p_ref + 1023 data) PPU primitive는 이미 정의 완료.

2. **메모리/버스용 CoPBit 채널**  
   - Q18은 “Channel-b mid-ISI + 1-sps FFE-only는 1e-3을 달성할 수 없다”는
     **부정적 베이스라인**을 제공한다.
   - 이 결과를 바탕으로,
     - EQ(FSE/DFE)와 PhaseLock_std를 독립적으로 설계하는 Q20 시리즈가 필요.
     - 최종적으로는 **PAM4/표준 DRAM 채널 대비 CoPBit의 장점**을
       BER vs Eb/N0, 레인 수, 전력, 면적 관점에서 정리하는 것이 목표다.

3. **비교의 방향성**  
   - 이제는 단순히 PAM4 vs M8 BER 비교보다는,
     - “**같은 채널 조건에서 필요한 EQ 복잡도와 PhaseLock_std 이득**”  
     - “**PPU(연산)와 메모리/버스(전송)의 역할 분담**”
   - 이 두 축으로 비교 방향을 전환하는 것이 자연스럽다.