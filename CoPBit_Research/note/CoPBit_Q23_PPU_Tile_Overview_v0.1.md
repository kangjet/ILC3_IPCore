# CoPBit Q23 – PPU용 1024-lane 타일 구조 개요 v0.1

## 1. 목적

- CoPBit를 **연산 프로세서(PPU: Phase Processing Unit)** 로 사용할 때의  
  기본 단위 블록을 **“1024-lane 타일(Tile)”** 로 정의하고,
- 이 타일 위에서
  - 메모리/버스 모드에서 정리한 **PhaseLock_std 조건**
  - M8 심볼 구조
  - P_ref lane 기반 위상 동기
  를 그대로 활용하면서,
- GPU/NPU와 비교 가능한 **연산 단위(3D 연산 primitive)** 를 정의하기 위한
  기반 스펙을 정리하는 것이 목표.

---

## 2. CoPBit PPU 개념 요약

- 기존 결과 (Q10~Q22):
  - M8 (3bit/sym) + Kuramoto/PhaseLock_std 구조로
    - **AWGN + mid-ISI(Channel-b)** 환경에서
    - **1개의 p_ref lane** 으로 **N-lane 전체 위상 잠금 가능**
    - 메모리/버스 모드에서 **θ_std ≤ 1° @ Eb/N0 ≥ 16 dB**면
      pre-FEC BER ≈ 10^-3 수준 달성 가능.
- PPU 관점:
  - 위 동일 조건이면, **메모리/버스와 동일한 채널 스펙 위에서  
    “연산 로직만 바꿔서” PPU로 운용 가능**.
  - 즉, “전송” 대신 “연산”을 수행하는 **3D 연산 primitive** 를 심볼 단위로 정의하면
    - 각 심볼 → 단순 비트가 아니라 **벡터/확률/위상 상태를 갖는 연산 단위** 로 사용.

---

## 3. 1024-lane 타일 구조 정의

### 3.1 타일 크기 및 레인 구성

- **타일 크기**:  
  - N_total = 1024 lanes
- **기본 모드 (PPU Tile v0.1 가정)**:
  - N_ref = 1 lane (글로벌 p_ref lane)
  - N_data = 1023 lanes (M8 data lanes)
- 레인 인덱스 예:
  - lane 0   : p_ref lane
  - lane 1~1023 : data lanes

> v0.1에서는 **“글로벌 p_ref = 1 lane” + PhaseLock_std** 를 기본으로 두고,  
> 추후(Q23b 이후)에 **“서브타일당 p_ref 1개(예: 32 lanes마다 1개)”** 구조도 비교 검토.

### 3.2 서브타일/그룹 구조 (논리적 뷰)

- 논리적으로는 1024 lanes를 K개의 그룹으로 나눠서 관리 가능:
  - 예) 32-lane 그룹 × 32개 = 1024 lanes
- v0.1 가정:
  - 물리 채널/PLL 기준으로는 **단일 p_ref lane** 으로 전체 잠금
  - **연산 로직 관점**에서만
    - 그룹별로 다른 데이터/연산을 할당 (예: 그룹별 다른 행렬, 벡터, 채널 등)

---

## 4. 채널 / EQ / PhaseLock_std 가정 (PPU 공통 베이스)

PPU 타일도 **메모리/버스와 동일한 채널/EQ 조건**을 기본으로 사용:

- **채널**
  - Channel-b mid-ISI (5-tap, 정규화된 h_midISI)
- **Equalizer**
  - FFE(LS), tap 길이 L ≈ 11, train_frac ≈ 0.5  
  - Q20c/Q21a/Q22a,b에서 검증한 **mid-ISI + FFE(LS) baseline** 재사용
- **PhaseLock_std (공통 PLL)**
  - 입력: p_ref lane 에러 + data lanes 평균 에러
  - 파라미터 예:
    - mu_phase ≈ 0.05
    - alpha_ref ≈ 0.3 (p_ref 쪽에 추가 가중)
- **기본 스펙 (메모리/버스 결과 재사용)**:
  - Eb/N0 ≥ 16 dB
  - 위상 노이즈 표준편차: θ_std ≤ 1.0°
  - 목표 pre-FEC BER: ≲ O(10^-3)

> 결론: **PPU 타일은 채널/PLL 스펙을 메모리/버스와 공유**하고,  
> 그 위에서 “전송 대신 연산”을 수행하는 구조로 설계.

---

## 5. PPU 타일 내 연산 모델 (v0.1 개념)

### 5.1 심볼/레인 단위 정보량

- 각 lane: M8 → 심볼당 3 bit-equivalent
- 1024 lanes 전체:
  - 1 심볼 타이밍에서 **3 × 1024 = 3072 bit-equivalent** 상태를 다룸
- 하지만 CoPBit PPU에서는 단순 비트 스트림이 아니라,
  - **“진폭 + 위상 조합” = 3D 상태** 로 해석:
    - 예) (amp, phase, lane index) → 3D 좌표계 상 연산 primitive 적용

### 5.2 3D 연산 primitive의 기본 방향성

v0.1에서 상정하는 PPU용 3D primitive 예:

1. **CoP-ADD (Coherent Phase Add)**  
   - 여러 lanes의 위상/진폭 상태를 **벡터 합** 형태로 합산 후,
   - 다시 M8 상태로 정규화/양자화하는 연산.

2. **Prob-Update (확률 벡터 업데이트)**  
   - 각 lane의 심볼을 **확률 분포(예: 8상태 분포)** 로 해석하고,
   - 간단한 확률 갱신 규칙 (Bayes-like update or weighted sum)을 적용.

3. **Phase-Logic / Phase-Gate**  
   - 특정 위상 영역을 논리 ‘0/1/2/3’ 등으로 맵핑하고,
   - **위상 차이를 이용한 논리 연산** (예: phase-majority, phase-XOR 유사 연산).

> Q23 이후 단계에서 위 세 가지 축을 조합해  
> “CoPBit 전용 연산 ISA” 같은 개념을 설계할 수 있음.

---

## 6. PPU 모드 vs 메모리/버스 모드

동일한 1024-lane 타일에서 모드는 크게 두 가지:

1. **MemBus Mode (이미 정리 완료 영역)**
   - 목적: 데이터 전송/저장
   - 성능 지표: BER vs Eb/N0, FEC 여유, 위상 노이즈 허용치
   - Q20~Q22 결과:
     - PhaseLock_std + θ_std ≤ 1° @ 16 dB → 실용적인 메모리/버스 스펙 가능.

2. **PPU Mode (Q23 이후 타겟)**
   - 목적: 연산(계산) 수행
   - 성능 지표:
     - **연산 정확도 (operation error rate)**
     - **연산량/초 (ops/s, bit-op/s, lane-op/s 등)**
     - 에너지/연산 (J/op, J/bit-op)
   - 채널/PLL 스펙은 MemBus Mode와 동일하게 두고,
     - “데이터를 얼마나 멀리/정확하게 보낼 수 있나” 대신  
     - “타일 내에서 3D 연산 primitive를 얼마나 많이, 정확하게 수행할 수 있나”로 관점 전환.

---

## 7. Q23 로드맵 (다음 스텝)

Q23 계열을 PPU 설계/실험 챕터로 두고, 단계별 목표를 정리:

1. **Q23a – PPU 타일 위상 잠금 검증 (AWGN 기준)**  
   - 스크립트 예: `copbit_q23a_ppu_tile_awgn_phaseLock_v0.py`
   - 내용:
     - 1024-lane AWGN 채널 + PhaseLock_std
     - p_ref 1 lane으로 1024 lanes 전체가 안정적으로 잠기는지 확인
     - lane 수 증가에 따른 위상 추정 noise scaling 체크

2. **Q23b – mid-ISI + FFE(LS) 환경에서 PPU 타일 위상 잠금 재검증**
   - Q22c의 **64-lane mid-ISI + FFE + PhaseLock_std 맵**을  
     1024-lane 타일까지 확장해서 문제 없는지 확인.

3. **Q23c – 첫 3D 연산 primitive (CoP-ADD or Prob-Update) 정의 및 성능 측정**
   - 한 타일(1024 lanes) 기준:
     - 심볼당 연산량
     - 연산 에러율 vs BER의 관계
     - GPU/NPU와의 “연산 단위 비교 지표” 잡기.

---

## 8. 요약

- 이 노트(Q23 PPU Tile Overview)는
  - **1024-lane PPU 타일**의 구조와 채널/PLL 스펙을  
    기존 **메모리/버스 결과(Q20~Q22)** 와 연결해서 정의하고,
  - 이후 Q23a~Q23c에서
    - 위상 잠금 검증
    - mid-ISI + FFE 환경 확장
    - 3D 연산 primitive 설계/성능 평가
    로 진행하기 위한 **출발점 역할**을 한다.