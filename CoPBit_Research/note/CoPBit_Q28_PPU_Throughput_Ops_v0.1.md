# CoPBit Q28 – PPU Throughput / Ops-per-Second 계산 v0.1

- Date: 2025-12-05
- Topic: CoPBit PPU (Phase Processing Unit) – Memory/Bus + 3D-연산 Throughput 정량화
- Related Notes:
  - CoPBit_Q19_PPU_Primitive_v0.1.md
  - CoPBit_Q22a_M8_midISI_FFE_LS_pRefPLL_v0.1.md
  - CoPBit_Q23a_PPU_Tile_AWGN_PhaseLock_v0.1.md
  - CoPBit_Q24a_PPU_3D_Add_AWGN_v0.1.md
  - CoPBit_Q24b_PPU_3D_Add_Truthcheck_v0.1.md
  - CoPBit_Q25a_PPU_3D_MAC_Truthcheck_v0.1.md
  - CoPBit_Q25b_PPU_3D_MAC_AWGN_Phase_v0.1.md
  - CoPBit_Q26a_TileKuramoto_LockMap_v0.1.md
  - CoPBit_Q27_PPU_Arch_Overview_v0.1.md

---

## 1. Scope & 공통 가정

본 노트에서는 Q27에서 정의한 PPU 타일 아키텍처를 바탕으로:

- **Memory/Bus Mode**: 시스템 대역폭 (Gb/s, GB/s, TB/s)
- **PPU Mode**: 3D-ADD/s, 3D-MAC/s (Ops-per-Second)

을 대표 심볼율 프로파일 2가지에 대해 정량화한다.

### 1.1. 공통 파라미터 (Q27 인용)

- 심볼 집합: M = 8 (3 bit/sym)
- 심볼당 비트수:  
  \[
    b_{\text{sym}} = 3 \ \text{bit/sym}
  \]
- Tile 당 lanes:
  \[
    N_{\text{lane}} = 1024
  \]
- 대표 심볼율 프로파일:
  - **Base**: \( R_{\text{sym}} = 16 \ \text{Gsym/s} \)
  - **Aggressive**: \( R_{\text{sym}} = 32 \ \text{Gsym/s} \)
- 대표 타일 수 프로파일:
  - 단일 타일: \( N_{\text{tile}} = 1 \)
  - 중규모 시스템 예: \( N_{\text{tile}} = 64 \)
- 위상/채널 동작 조건 (정상 영역):
  - \( E_b/N_0 \ge 16 \ \text{dB} \)
  - 타일 내부 PhaseLock_std: \( \theta_{\text{std,tile}} \le 1^\circ \)
  - 타일 간 Kuramoto: K ≈ 0.2, drift_std ≤ 0.1°, θ_std_tile ≤ 0.5° 권장

---

## 2. Memory/Bus Mode – 대역폭 계산

### 2.1. 일반식

- Per-lane raw bit-rate:
  \[
    R_{\text{bit,lane}} = R_{\text{sym}} \times b_{\text{sym}} 
    \quad [\text{Gb/s}]
  \]
- Tile raw bit-rate:
  \[
    R_{\text{bit,tile}} = R_{\text{bit,lane}} \times N_{\text{lane}}
    \quad [\text{Gb/s}]
  \]
- System raw bit-rate:
  \[
    R_{\text{bit,sys}} = R_{\text{bit,tile}} \times N_{\text{tile}}
    \quad [\text{Gb/s}]
  \]
- Byte 단위 변환:
  \[
    R_{\text{GB/s}} = \frac{R_{\text{bit}}}{8}, 
    \quad
    R_{\text{TB/s}} = \frac{R_{\text{bit}}}{8000}
  \]
- FEC 오버헤드를 고려한 실효 대역폭:
  - FEC 오버헤드 비율을 \( \text{OH}_{\text{FEC}} \) (예: 20% → 0.2)라 하면,
  \[
    R_{\text{eff}} 
      = R_{\text{bit,sys}} \times (1 - \text{OH}_{\text{FEC}}) 
      \quad [\text{Gb/s}]
  \]
  - Q10/Q15에서 얻은 Pre-FEC BER 기반으로 \( \text{OH}_{\text{FEC}} \) 결정 예정.

### 2.2. 수치 예시 – Raw bit-rate

#### (1) Base Profile – 16 Gsym/s

- Per-lane:
  \[
    R_{\text{bit,lane}} 
      = 16 \times 3 = 48 \ \text{Gb/s}
  \]
- Per-tile:
  \[
    R_{\text{bit,tile}} 
      = 48 \times 1024 = 49{,}152 \ \text{Gb/s}
      = 6{,}144 \ \text{GB/s}
      \approx 6.144 \ \text{TB/s}
  \]

- System (예: 64 tiles):
  \[
    R_{\text{bit,sys}} 
      = 49{,}152 \times 64 = 3{,}145{,}728 \ \text{Gb/s}
      = 393{,}216 \ \text{GB/s}
      \approx 393.216 \ \text{TB/s}
      \approx 0.39 \ \text{PB/s}
  \]

#### (2) Aggressive Profile – 32 Gsym/s

- Per-lane:
  \[
    R_{\text{bit,lane}} 
      = 32 \times 3 = 96 \ \text{Gb/s}
  \]
- Per-tile:
  \[
    R_{\text{bit,tile}} 
      = 96 \times 1024 = 98{,}304 \ \text{Gb/s}
      = 12{,}288 \ \text{GB/s}
      \approx 12.288 \ \text{TB/s}
  \]

- System (예: 64 tiles):
  \[
    R_{\text{bit,sys}} 
      = 98{,}304 \times 64 = 6{,}291{,}456 \ \text{Gb/s}
      = 786{,}432 \ \text{GB/s}
      \approx 786.432 \ \text{TB/s}
      \approx 0.79 \ \text{PB/s}
  \]

#### (3) 요약 표 (Raw, FEC 미고려)

| Profile         | \(R_{\text{sym}}\) (Gsym/s) | \(N_{\text{tile}}\) | System Raw (Gb/s) | System Raw (TB/s) | 비고                |
|----------------|------------------------------|---------------------|-------------------|-------------------|---------------------|
| Base-1tile     | 16                           | 1                   | 49,152            | 6.144             | 단일 타일           |
| Base-64tiles   | 16                           | 64                  | 3,145,728         | 393.216           | 중규모 CoPBit PPU   |
| Agg-1tile      | 32                           | 1                   | 98,304            | 12.288            | 단일 타일 고속 모드 |
| Agg-64tiles    | 32                           | 64                  | 6,291,456         | 786.432           | 공격적 프로파일     |

> 추후 Q28b에서: Q10/Q15 FEC 테이블을 사용해서  
> - \( \text{OH}_{\text{FEC}} \) 를 SNR/채널 조건별로 적용 → 실효 대역폭 \( R_{\text{eff}} \) 계산 예정.

---

## 3. PPU Mode – 3D-ADD / 3D-MAC Throughput

Q24/Q25에서 정의한 3D-ADD / 3D-MAC primitive를 기준으로,  
“lane-wise 3D 연산”의 초당 수행 횟수를 정의한다.

### 3.1. 3D-ADD Throughput

가정: 각 lane은 심볼 1개마다 3D-ADD 1회 수행 가능 (streaming).

- Per-lane 3D-ADD rate:
  \[
    R_{\text{3DADD,lane}} = R_{\text{sym}} \quad[\text{Op/s}]
  \]
- Tile 3D-ADD rate:
  \[
    R_{\text{3DADD,tile}} 
      = R_{\text{sym}} \times N_{\text{lane}} 
      \quad[\text{Op/s}]
  \]
- System 3D-ADD rate:
  \[
    R_{\text{3DADD,sys}} 
      = R_{\text{sym}} \times N_{\text{lane}} \times N_{\text{tile}} 
      \quad[\text{Op/s}]
  \]

TOp/s 단위로 환산하면:

\[
  R_{\text{3DADD,tile}}^{(\text{TOp/s})}
    = \frac{R_{\text{sym}} \times N_{\text{lane}}}{1000}
\]

#### 3.1.1. 수치 예시 – 3D-ADD

- Base (16 Gsym/s):
  - Per-tile:
    \[
      R_{\text{3DADD,tile}} 
        = \frac{16 \times 1024}{1000} \approx 16.384 \ \text{TOp/s}
    \]
  - 64 tiles:
    \[
      R_{\text{3DADD,sys}} 
        \approx 16.384 \times 64 \approx 1{,}048.576 \ \text{TOp/s}
        \approx 1.05 \ \text{P(3D-ADD)/s}
    \]

- Aggressive (32 Gsym/s):
  - Per-tile:
    \[
      R_{\text{3DADD,tile}} 
        = \frac{32 \times 1024}{1000} \approx 32.768 \ \text{TOp/s}
    \]
  - 64 tiles:
    \[
      R_{\text{3DADD,sys}} 
        \approx 32.768 \times 64 \approx 2{,}097.152 \ \text{TOp/s}
        \approx 2.10 \ \text{P(3D-ADD)/s}
    \]

### 3.2. 3D-MAC Throughput

Q25에서 정의한 3D-MAC은 대략적으로:

- MAC 길이 \( L_{\text{MAC}} \) 에 대해,
  - 1개의 3D-MAC ≈ \( L_{\text{MAC}} \) 번의 3D-멀티플라이 + (L_{\text{MAC}} - 1) 번의 3D-ADD 조합.
- Streaming 가정 시, lane 당 MAC 처리율은:
  \[
    R_{\text{3DMAC,lane}} 
      \approx \frac{R_{\text{sym}}}{L_{\text{MAC}}} \quad[\text{Op/s}]
  \]
- Tile / System:
  \[
    R_{\text{3DMAC,tile}} 
      \approx \frac{R_{\text{sym}}}{L_{\text{MAC}}} \times N_{\text{lane}}
  \]
  \[
    R_{\text{3DMAC,sys}} 
      \approx \frac{R_{\text{sym}}}{L_{\text{MAC}}} \times N_{\text{lane}} \times N_{\text{tile}}
  \]

TOp/s 단위로:

\[
  R_{\text{3DMAC,tile}}^{(\text{TOp/s})}
    \approx \frac{R_{\text{sym}} \times N_{\text{lane}}}{1000 \times L_{\text{MAC}}}
\]

#### 3.2.1. 수치 예시 – \( L_{\text{MAC}} = 4 \)

- Base (16 Gsym/s, L_MAC = 4):
  - Per-tile:
    \[
      R_{\text{3DMAC,tile}} 
        \approx \frac{16 \times 1024}{1000 \times 4}
        \approx 4.096 \ \text{TOp/s}
    \]
  - 64 tiles:
    \[
      R_{\text{3DMAC,sys}} 
        \approx 4.096 \times 64 \approx 262.144 \ \text{TOp/s}
        \approx 0.26 \ \text{P(3D-MAC)/s}
    \]

- Aggressive (32 Gsym/s, L_MAC = 4):
  - Per-tile:
    \[
      R_{\text{3DMAC,tile}} 
        \approx \frac{32 \times 1024}{1000 \times 4}
        \approx 8.192 \ \text{TOp/s}
    \]
  - 64 tiles:
    \[
      R_{\text{3DMAC,sys}} 
        \approx 8.192 \times 64 \approx 524.288 \ \text{TOp/s}
        \approx 0.52 \ \text{P(3D-MAC)/s}
    \]

#### 3.2.2. 요약 표 (L_MAC = 4)

| Profile       | \(R_{\text{sym}}\) (Gsym/s) | \(N_{\text{tile}}\) | 3D-ADD (TOp/s, sys) | 3D-MAC (TOp/s, sys, L=4) |
|--------------|------------------------------|---------------------|----------------------|--------------------------|
| Base-64tiles | 16                           | 64                  | ≈ 1,048.6            | ≈ 262.1                  |
| Agg-64tiles  | 32                           | 64                  | ≈ 2,097.2            | ≈ 524.3                  |

> 향후 Q28b에서:
> - “1 3D-MAC = k FLOPs” (예: k ≈ 6 또는 9) 가정을 두고,
> - GPU/NPU의 FP16/FP32 TFLOPS/ PFLOPS 수치와 직접 비교하는 테이블 추가 예정.

---

## 4. 정상 동작 조건 요약 (Throughput 유효 조건)

Q22 / Q23 / Q25 / Q26 결과를 종합하면, 위의 Throughput 수치는 다음 조건에서 “정상 유효값”으로 간주할 수 있다.

- 채널/위상 조건:
  - \( E_b/N_0 \ge 16 \ \text{dB} \)
  - Tile 내부 PhaseLock_std:
    - \( \theta_{\text{std,tile}} \le 1^\circ \) (AWGN + mid-ISI 환경)
  - Tile 간 Kuramoto:
    - 결합 강도 \( K \approx 0.2 \)
    - 타일 간 drift_std ≤ 0.1°
    - 타일 간 θ_std ≤ 0.5° (권장)
- 이 영역에서:
  - Memory/Bus Mode: FEC 적용 시 목표 BER (예: 10^-15) 도달 가능
  - PPU Mode: 3D-ADD / 3D-MAC truthcheck에서 0 error (Q24/Q25), AWGN+Phase 환경에서도 θ_std ≤ 1°에서 정상 동작 (Q25b, Q23a)

---

## 5. Q28 이후 To-do (Q28b / Q29 아이디어)

- **Q28b: GPU/NPU 대비 연산력 비교**
  - “1 3D-MAC = k FLOPs” 매핑 정의 (예: 3D-멀티플라이 ×3 + 3D-ADD ×2 → 5~6 FLOPs 등)
  - 위 표의 3D-MAC TOp/s를 TFLOPS/PFLOPS로 환산하여:
    - 대표 GPU (예: HBM3 + FP16/FP8/INT8)와 비교
    - CoPBit PPU의 강점이 드러나는 지점 정리

- **Q29: Energy / Power Budget**
  - 심볼당 에너지, 위상 루프(PhaseLock_std + Kuramoto), 3D-MAC 연산당 에너지 가정 후,
    - Tile / System 레벨 Power Estimation
    - “W/TB/s”, “W/P(3D-MAC)/s” 형태의 효율 지표 도출

- **Q30: JEDEC-style Spec 초안**
  - “동작 조건 (Eb/N0, θ_std, K, drift_std)” + “대역폭/연산력 스펙”을 한 장 표로 요약.
  - 외부 공개 / 표준화용 문서의 기반으로 활용.

## 6. GPU / NPU 대비 Back-of-Envelope 비교

여기서는 CoPBit PPU의 3D-MAC Throughput을 FLOPs-equivalent로 환산하여, 대표 GPU/NPU와 대략적인 스케일을 비교한다.

### 6.1. 3D-MAC → FLOPs 환산 가정

- 타일 수: \(N_{\text{tile}} = 64\)
- 타일당 lanes: \(N_{\text{lane}} = 1024\)
- 심볼율 프로파일:
  - Base: \(R_{\text{sym}} = 16 \ \text{Gsym/s}\)
  - Aggressive: \(R_{\text{sym}} = 32 \ \text{Gsym/s}\)
- 3D-MAC 길이: \(L_{\text{MAC}} = 4\)

Q28에서 계산된 시스템 레벨 3D-MAC Throughput (64 tiles 기준):

- Base: \(R_{\text{3DMAC,sys}} \approx 262.1 \ \text{TOp/s}\)
- Aggressive: \(R_{\text{3DMAC,sys}} \approx 524.3 \ \text{TOp/s}\)

1개의 3D-MAC이 실수 FLOPs로 어느 정도에 해당하는지에 대해서는 구현 방식에 따라 차이가 있지만, 다음과 같은 범위를 가정한다.

- **보수적 가정:** 1 3D-MAC ≈ 6 FLOPs  
  (예: 실수 곱 3개 + 실수 덧셈 3개 수준)
- **공격적 가정:** 1 3D-MAC ≈ 9 FLOPs  
  (3D-멀티플라이 내부 추가 연산까지 포함하는 경우)

### 6.2. CoPBit PPU ≈ TFLOPS / PFLOPS 스케일

- Base (16 Gsym/s, 64 tiles):

  \[
    R_{\text{3DMAC,sys}} \approx 262.1 \ \text{TOp/s}
  \]

  - 1 3D-MAC = 6 FLOPs 가정:
    \[
      \approx 1.57 \ \text{PFLOPS}
    \]
  - 1 3D-MAC = 9 FLOPs 가정:
    \[
      \approx 2.36 \ \text{PFLOPS}
    \]

- Aggressive (32 Gsym/s, 64 tiles):

  \[
    R_{\text{3DMAC,sys}} \approx 524.3 \ \text{TOp/s}
  \]

  - 1 3D-MAC = 6 FLOPs 가정:
    \[
      \approx 3.15 \ \text{PFLOPS}
    \]
  - 1 3D-MAC = 9 FLOPs 가정:
    \[
      \approx 4.72 \ \text{PFLOPS}
    \]

따라서 64 tiles 기준 CoPBit PPU는:

- Base 프로파일: \(\approx 1.6 \sim 2.4 \ \text{PFLOPS}\)
- Aggressive 프로파일: \(\approx 3.1 \sim 4.7 \ \text{PFLOPS}\)

정도의 FP16-equivalent 연산 스케일을 갖는 것으로 볼 수 있다.

### 6.3. 대표 GPU / NPU와의 비교

- **NVIDIA H100**: FP16/BF16 Tensor 성능이 대략 \(\sim 1 \ \text{PFLOPS}\) 수준으로 알려져 있다. [oai_citation:3‡TechRadar](https://www.techradar.com/pro/musk-says-xai-will-have-50-million-h100-equivalent-nvidia-gpus-by-2030-but-at-what-cost?utm_source=chatgpt.com)  
  - CoPBit PPU (64 tiles, 16 Gsym/s): \(\approx 1.6 \sim 2.4 \ \text{PFLOPS}\)  
    → H100 대비 대략 1.6~2.4배 스케일
  - CoPBit PPU (64 tiles, 32 Gsym/s): \(\approx 3.1 \sim 4.7 \ \text{PFLOPS}\)  
    → H100 대비 대략 3~5배 스케일

- **Google TPU v4**: bfloat16 기준 약 275 TFLOPS 수준. [oai_citation:4‡elprocus.com](https://www.elprocus.com/google-tpu-v4/?utm_source=chatgpt.com)  
  - CoPBit PPU (64 tiles, 32 Gsym/s, 3.1~4.7 PFLOPS eq.)는 TPU v4 대비 대략 11~17배 수준의 FLOPs-equivalent 스케일.

- **NVIDIA Blackwell (GB300 등)**: 단일 GPU가 최대 20 PFLOPS급 AI 성능을 제공한다고 알려져 있다 (FP4/FP8 및 sparsity 포함). [oai_citation:5‡The Verge](https://www.theverge.com/news/631835/nvidia-blackwell-ultra-ai-chip-gb300?utm_source=chatgpt.com)  
  - CoPBit PPU (64 tiles, Aggressive): \(\approx 3.1 \sim 4.7 \ \text{PFLOPS}\)  
    → GB300 대비 대략 15~25% 레벨의 FLOPs-equivalent 스케일.

물론 위 비교는:

- GPU/NPU의 FLOPs는 실수 행렬 연산(FP16/FP8 등)을 기준으로 한 값이고,  
- CoPBit PPU의 값은 3D-MAC을 FLOPs로 환산한 **Back-of-Envelope** 수준의 비교라는 점에서,  
정밀한 벤치마크라기보다는 **연산 스케일**을 감 잡기 위한 참고용으로 해석해야 한다.

### 6.4. 메모리/버스 스케일과의 결합

앞서 16 Gsym/s / 32 Gsym/s, 64 tiles 기준으로:

- 16 Gsym/s: \(\approx 0.39 \ \text{PB/s}\) Raw  
- 32 Gsym/s: \(\approx 0.79 \ \text{PB/s}\) Raw

PB/s급 메모리/버스 대역폭과, PFLOPS급 3D-MAC 연산을 동일 구조 안에서 제공한다는 점이 CoPBit PPU의 핵심 포인트가 된다.