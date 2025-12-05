# CoPBit Q19 – PPU Primitive 정의 v0.1

## 1. 목적

이 문서는 Q16~Q18 실험 결과를 바탕으로, **연산용 CoPBit PPU(Phase Processing Unit)의 기본 연산 프리미티브(primitive)**를 정의하는 것을 목표로 한다.

- Q16~Q17: AWGN + 공통 위상 잡음 + p_ref + Kuramoto PLL 실험  
- Q18      : Channel-b mid-ISI + 1-sps FFE-only 베이스라인 (PAM4 vs M8)

정리하면,

1. **AWGN + 위상잡음 환경에서 1개 p_ref + Kuramoto PhaseLock_std 모드만으로 multi-lane 공통 위상 락이 가능하다.**
2. **mid-ISI + 1-sps FFE-only 구조는 채널이 너무 강해 1e-3 BER을 만족하지 못하며, 이 구조로는 메모리/버스 채널을 커버하기 어렵다.**

따라서 Q19에서는 **연산용 PPU(초근거리, mid-ISI가 매우 약한 환경)**에 초점을 맞춰, CoPBit의 “한 타일(tile)”을 어떻게 정의할지 정리한다.

---

## 2. CoPBit PPU 타일 구조(예: 1024L Tile)

### 2.1 기본 파라미터

- Lane 수:  
  - \( N_\text{lane} = 1024 \) (한 타일 기준)
- 변조:  
  - 기본: **M8 (8-PSK, 3bit/sym)**  
  - 옵션: M16(16-QAM/16-APSK 등)로 확장 가능 (4bit/sym)
- 심볼 구조:  
  - 각 lane 심볼:  
    \[
    s_{i}[n] = A_{i}[n]\cdot e^{j(\phi_{i}[n] + \phi_\text{common}[n])}
    \]
  - 여기서 \(\phi_\text{common}[n]\)은 Q16~Q17에서 정의한 **공통 위상** (Kuramoto/PLL로 추적되는 축)

### 2.2 Lane 역할 분할 (PhaseLock_std 모드)

Q16~Q17, Q16c, Q16d, Q17a, Q17b 결과에 따르면:

- **p_ref lane이 1개만 있어도 Kuramoto + PhaseLock_std 조건을 만족**할 수 있다.
- p_ref lane을 여러 개로 늘려도, AWGN + 공통 위상 잡음 환경에서는 **BER 개선 폭이 크지 않다**는 것이 확인되었다.

따라서 PPU 한 타일에서는:

- \( N_\text{ref} = 1 \)  
- \( N_\text{data} = 1023 \)

구성을 기본 디폴트로 둔다.

- **Lane0**: p_ref lane
  - 고정된 8-PSK 인덱스 \(k_\text{ref}\) 사용
  - Q16~Q17에서와 같이, 공통 위상 \(\phi_\text{common}[n]\)을 추적하는 기준 축 역할
- **Lane1 ~ Lane1023**: data lane
  - 3bit/sym (M8) 또는 4bit/sym (M16) 데이터 심볼
  - PPU 연산에 사용하는 실제 “데이터 벡터”를 표현

---

## 3. PhaseLock_std 모드 – PPU용 운영 정의

Q16~Q17에서 테스트한 **PhaseLock_std 모드**를 PPU용으로 정리하면:

1. **위상 잡음 모델**  
   - 공통 위상 드리프트:  
     \[
     \phi_\text{common}[n] = \phi_\text{common}[n-1] + \Delta\phi[n]
     \]
     \[
     \Delta\phi[n] \sim \mathcal{N}(0, \sigma_\theta^2)
     \]
   - \(\sigma_\theta\)는 Q17a/Q17b에서 만든 **(θ_std_deg, Eb/N0, p_ref density) 지도**를 바탕으로 설계.

2. **PLL 업데이트 법칙 (total_err 기반)**  
   - p_ref lane 에러: \( e_\text{ref}[n] \)  
   - data lane 평균 에러: \( e_\text{data}[n] \)  
   - 혼합 에러:
     \[
     e_\text{total}[n] = (1-\alpha_\text{ref})\cdot e_\text{ref}[n] + \alpha_\text{ref}\cdot e_\text{data}[n]
     \]
   - 공통 위상 업데이트:
     \[
     \phi_\text{est}[n+1] = \phi_\text{est}[n] + \mu_\phi \cdot \Im\{e_\text{total}[n]\}
     \]
   - 여기서 \(\alpha_\text{ref}\)는 Q16~Q17에서 찾은 안정 영역 안에서 선택,  
     예: \(\alpha_\text{ref} \approx 0.3\) 근방.

3. **PPU PhaseLock_std 설계 원칙 (정리)**

- **원칙 1 – p_ref 최소 조건**:  
  - **1 lane p_ref + N data lane** 구조로도 Kuramoto PhaseLock_std를 만족할 수 있다.
- **원칙 2 – p_ref density 효과**:  
  - AWGN + 공통 위상 잡음 환경에서 p_ref lane 수를 2개, 8개 등으로 늘려도,  
    \(\text{BER} \approx 10^{-2} \sim 10^{-3}\) 수준에서는 성능 개선 폭이 크지 않다.  
  - 따라서 PPU에서는 **“1 p_ref per tile” 규칙**을 기본으로 삼는다.
- **원칙 3 – EQ 한계 분리**:  
  - Channel-b mid-ISI + 1-sps FFE-only(Q18)에서 나타난 **BER ≈ 0.27 플로어**는  
    CoPBit/Kuramoto의 문제가 아니라, **FFE/EQ 구조 한계**라는 점을 분리해서 본다.

---

## 4. PPU 연산 모드 정의

CoPBit PPU 타일(1024L)은 다음 세 가지 용도로 사용 가능하다.

### 4.1 모드 A – 고전적 비트 연산 모드 (Deterministic)

- 각 데이터 lane은 3bit/sym(M8) 또는 4bit/sym(M16) 고정 심볼을 사용.
- PPU는 내부에서 이 lane들을 **논리 벡터/워드**로 취급:
  - 예시: 1024 lanes × 3bit = 3072bit 병렬 연산
- Kuramoto PhaseLock_std는 단순히 “위상 클럭 동기” 역할:
  - 위상 드리프트를 억제해 **심볼 에러율을 낮추는 클럭/위상 장치**로 사용.
- 이 모드에서는 기존 GPU/TPU 대비:
  - **연산 자체는 고전적**이지만,
  - **위상 축을 공짜로 하나 더 쓰는 것에 가까운 구조**로 해석 가능.

### 4.2 모드 B – 확률/Monte-Carlo 연산 모드 (Probabilistic)

- 일부 lane은 **확률 분포 샘플(예: random amplitude/phase)**를 인코딩.
- 나머지 lane은 고전적 상태(0/1/2/3) 또는 저차 심볼을 표현.
- 한 타일(1024L)을 반복 사용하면서:
  - 확률 연산, Monte-Carlo 시뮬레이션, stochastic gradient 등
  - **양자컴의 “확률 연산”과 유사한 역할**을 하는 모드로 동작시킬 수 있다.
- 핵심은:
  - Q16~Q17에서 확보한 **PhaseLock_std 안정 영역** 덕분에  
    다수 lane의 위상 상태를 **공통 기준 위상에 묶어둔 상태로, 확률 샘플을 안전하게 전달** 가능.

### 4.3 모드 C – 메모리/데이터버스 연계 모드

- PPU 타일 일부를 **메모리 인터페이스/데이터버스**로 직접 연결하는 모드.
- Q18의 결과를 반영하면:
  - mid-ISI가 강한 채널(예: 외부 PCB, 긴 라우팅)에서는  
    1-sps FFE-only로는 **PAM4나 M8 모두 1e-3을 만족하지 못함**.
  - 따라서 **PPU와 메모리/버스 사이에 별도의 고성능 EQ/FSE/DFE 프론트엔드가 필요**하다.
- 결론적으로:
  - PPU 코어(CoPBit 타일)는 **AWGN + 약한 ISI** 영역에 위치시키고,
  - 메모리/버스로 나가는 구간은 **전통적인 신호처리(EQ/FEC)**로 감싸는 구조가 자연스럽다.

---

## 5. Q18(FFE-only) 결과의 역할 정리

Q18 실험은 다음을 보여준다:

1. **Channel-b mid-ISI + 1-sps FFE-only 구조에서는**
   - PAM4, M8 모두 **BER ≈ 0.27 수준에서 플로어 발생**.
   - Eb/N0를 10~28 dB까지 올려도 BER가 거의 떨어지지 않는다.
2. **mu_ffe를 0.1까지 올린 경우**
   - Normalized LMS에서 `mu_eff`가 과도하게 커져 FFE 계수가 발산.
   - 디코드는 사실상 랜덤(≈0.5) 상태가 되고, 이는 채널이 아니라 알고리즘 폭발을 의미한다.
3. 따라서:
   - Q18은 “**이 mid-ISI 채널을 1-sps FFE-only로 해결할 수 없다**”는 **부정적 베이스라인** 역할을 한다.
   - CoPBit PPU의 성능 평가를 할 때,
     - **연산 코어 부분(AWGN + 약한 ISI)**과
     - **메모리/버스 채널(강한 ISI)**을 ***
     명확히 분리해서 설계해야 한다는 근거가 된다.

---

## 6. 요약

- **CoPBit PPU 타일(1024L)**은
  - \(N_\text{ref} = 1\) p_ref lane + \(N_\text{data} = 1023\) data lane 구성으로 충분하다.
- Q16~Q17, Q16c, Q16d, Q17a, Q17b 결과에 따르면
  - **1개의 p_ref만으로 Kuramoto PhaseLock_std 조건을 만족**할 수 있고,
  - p_ref를 여러 개로 늘려도 성능 이득은 제한적이다.
- Q18 결과는
  - “강한 mid-ISI + 1-sps FFE-only 구조는 메모리 채널에 부적합”이라는
  - **FFE-only 실패 베이스라인**으로 해석해야 하며,
  - CoPBit PPU 자체의 실현 가능성과는 별개 이슈임을 보여준다.
- 따라서,
  - **연산용 CoPBit PPU는 이미 AWGN + 공통 위상 잡음 환경에서 실현 가능한 수준**이 확보되었고,
  - 메모리/버스용 CoPBit 채널은 별도의 EQ/FSE 구조를 전제로 한 후속 설계 과제로 분리된다.