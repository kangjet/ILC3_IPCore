# CoPBit Q27 – PPU 시스템 아키텍처 개요 v0.1

- Date: 2025-12-05
- Topic: CoPBit PPU (Phase Processing Unit) 시스템 레벨 아키텍처 정리
- Related Notes:
  - CoPBit_Q19_PPU_Primitive_v0.1.md
  - CoPBit_Q23a_PPU_Tile_AWGN_PhaseLock_v0.1.md
  - CoPBit_Q24a_PPU_3D_Add_AWGN_v0.1.md
  - CoPBit_Q24b_PPU_3D_Add_Truthcheck_v0.1.md
  - CoPBit_Q25a_PPU_3D_MAC_Truthcheck_v0.1.md
  - CoPBit_Q25b_PPU_3D_MAC_AWGN_Phase_v0.1.md
  - CoPBit_Q26a_TileKuramoto_LockMap_v0.1.md

---

## 1. PPU 타일 정의 (기본 단위)

- **Tile 구성**
  - Lanes: 1024 lanes / tile (M = 8, 3bit/sym)
  - Mode:
    - **Memory/Bus Mode**: M8 심볼을 메모리/버스 신호로 사용
    - **PPU Mode**: 동일 심볼을 3D 연산 primitive (3D-ADD / 3D-MAC)의 연산 단위로 사용
  - 내부 블록:
    - PhaseLock_std (p_ref 기반 위상 추적)
    - FFE/EQ (필요 시)
    - 3D-ADD / 3D-MAC 연산 블록
    - Mode MUX (Memory ↔ PPU 전환)

- **기본 스펙 (예시 @ 16 dB, θ_std ≤ 1°)**
  - Data path: 3 bit/sym × 1024 lanes
  - PPU 연산:
    - 3D-ADD: lane-wise 3D 벡터 덧셈
    - 3D-MAC: (3D-멀티플라이 + 3D-ACC) 구조

---

## 2. 위상 인프라: PhaseLock_std + Kuramoto

### 2.1. Tile 내부 PhaseLock_std

- 참조 레인: p_ref lane 1개 (또는 소수 레인)
- 기능:
  - 채널 / 위상 노이즈 / 공통 위상 변이를 보상
  - θ_std ≤ 1° 영역에서 메모리/버스 + PPU 모드 모두 안정 동작
- 조건 (Q22 / Q23 / Q25 결과 기반):
  - Eb/N0 ≥ 16 dB
  - θ_std_tile ≤ 1.0° (phase noise std)
  - M8 mid-ISI + FFE + PhaseLock_std 조합에서 BER이 FEC 전제 하에 충분히 낮음

### 2.2. Tile 간 Kuramoto coupling

- 구조:
  - 각 타일의 “중심 위상”을 노드로 보는 Kuramoto 네트워크
  - 결합 강도 K, 타일 간 주파수 드리프트 drift_std_deg, 타일별 θ_std_deg로 모델링
- 핵심 결과 (Q26a 요약):
  - K = 0.0: 어떤 타일 개수(64, 256)에서도 글로벌 락 실패
  - K = 0.1: 일부 조합에서만 lock, 양산 여유 거의 없음
  - **K = 0.2**:
    - drift_std ∈ {0.01, 0.05, 0.1} deg
    - theta_std ∈ {0.1, 0.3, 0.5} deg
    - → 64 ~ 256 tiles 모두 **글로벌 lock 100% 성공**
    - steady_sigma_deg ≈ 0.15° ~ 1.0°
  - K = 0.3: K=0.2보다 약간 더 타이트하나, 전력/루프 안정성 측면에서 K=0.2 전후가 현실적 타겟

---

## 3. Memory/Bus Mode vs PPU Mode 통합 구조

### 3.1. 공통 위상 인프라 공유

- 공통 인프라:
  - Tile 내부 PhaseLock_std
  - Tile 간 Kuramoto 네트워크 (K ≈ 0.2)
- 두 모드는 모두 동일한 위상 인프라 위에서 동작:
  - **Memory/Bus Mode**:
    - M8 심볼 → 메모리/버스 신호 (read/write)
    - 위상 인프라가 신호 무결성, BER 개선에 기여
  - **PPU Mode**:
    - 같은 심볼을 3D-ADD / 3D-MAC 연산 primitive로 해석
    - 글로벌 위상 동기화 덕분에 대규모 병렬 3D-연산 배열이 한 몸처럼 동작

### 3.2. Mode 전환 개념

- 타일 레벨:
  - MODE_SEL 플래그 (Memory / PPU)
  - 동일 IO/배선 위에서, 펌웨어/컨트롤러가 모드 스케줄링
- 시스템 레벨:
  - 특정 시간 슬롯은 “메모리 서비스”,
  - 다른 슬롯은 “PPU 연산”에 배정하는 식의 time-sharing 가능

---

## 4. Kuramoto 기반 PPU 스펙 요약 (Draft)

| 항목                         | 타겟 값 (예)                 | 근거(Q#)                            |
|-----------------------------|------------------------------|-------------------------------------|
| Tile 당 lanes               | 1024                         | 정의 (PPU tile primitive)          |
| 심볼당 비트수               | 3 bit (M8)                   | CoPBit 정의                        |
| 내부 PhaseLock_std θ_std    | ≤ 1.0°                       | Q22, Q23, Q25                       |
| Kuramoto 결합 강도 K       | ≈ 0.2                        | Q26a (64~256 tiles 전 영역 lock)    |
| 타일 간 drift_std (deg)     | ≤ 0.1°                       | Q26a 스윗 스팟                       |
| 타일 간 θ_std (deg)         | ≤ 0.5° (권장)                | Q26a, 충분한 여유                    |
| 지원 타일 수 (예시)         | 64 ~ 256 (확장 1024까지 가능) | Q26a 자기 평균화(Self-averaging)    |
| 동작 Eb/N0                 | ≥ 16 dB                      | Q22, Q23, Q25 (메모리/PPU 공통)      |

---

## 4.5 Throughput / Bandwidth 계산을 위한 파라미터 (Draft)

> 이 섹션은 후속 Q28(Throughput / Ops-per-Second 계산)을 위해 공통으로 사용할 파라미터 정의 초안이다.

- **기본 심볼/클럭 파라미터 (예시 값, 변경 가능)**
  - Per-lane 심볼율: \( R_{\text{sym}} \) [Gsym/s]
  - 내부 클럭 주파수: \( f_{\text{clk}} \) [GHz]
  - 심볼당 비트수: \( b_{\text{sym}} = 3 \) bit/sym (M8)
  - 타일당 lanes: \( N_{\text{lane}} = 1024 \)
  - 활성 타일 수: \( N_{\text{tile}} \) (예: 64, 256, 1024)

- **Memory/Bus Mode – 유효 대역폭 정의**
  - Per-lane raw bit-rate:
    - \( R_{\text{bit,lane}} = R_{\text{sym}} \times b_{\text{sym}} \) [Gb/s]
  - Tile raw bit-rate:
    - \( R_{\text{bit,tile}} = R_{\text{bit,lane}} \times N_{\text{lane}} \) [Gb/s]
  - System raw bit-rate:
    - \( R_{\text{bit,sys}} = R_{\text{bit,tile}} \times N_{\text{tile}} \) [Gb/s]
  - Pre-FEC BER: \( \text{BER}_{\text{pre}}(E_b/N_0, \theta_{\text{std}}) \)
  - Post-FEC residual BER (타겟):
    - \( \text{BER}_{\text{post}} \le 10^{-15} \) (예시)
  - 유효 대역폭(실효 throughput) 정의:
    - \( R_{\text{eff}} = R_{\text{bit,sys}} \times (1 - \text{FEC\_overhead}) \)
    - FEC 오버헤드는 Q10/Q15 계열 결과를 참조하여 결정

- **PPU Mode – 3D-연산 Throughput 정의**
  - 3D-ADD:
    - 1 심볼 주기당 lane-wise 3D 벡터 덧셈 1회 수행
    - Per-lane 3D-ADD rate:
      - \( R_{\text{3DADD,lane}} = R_{\text{sym}} \) [Op/s]
    - Tile 3D-ADD rate:
      - \( R_{\text{3DADD,tile}} = R_{\text{sym}} \times N_{\text{lane}} \) [Op/s]
  - 3D-MAC (MAC 길이 \( L_{\text{MAC}} \)):
    - MAC 길이: \( L_{\text{MAC}} \in \{3,4,\dots\} \)
    - 1 MAC 연산 ≒ \( L_{\text{MAC}} \) 번의 3D-멀티플라이 + (L_{\text{MAC}} - 1) 번의 3D-ADD로 모델링
    - Per-lane 3D-MAC rate (streaming 가정):
      - \( R_{\text{3DMAC,lane}} \approx \frac{R_{\text{sym}}}{L_{\text{MAC}}} \) [Op/s]
    - Tile 3D-MAC rate:
      - \( R_{\text{3DMAC,tile}} \approx \frac{R_{\text{sym}}}{L_{\text{MAC}}} \times N_{\text{lane}} \) [Op/s]
    - System 3D-MAC rate:
      - \( R_{\text{3DMAC,sys}} \approx \frac{R_{\text{sym}}}{L_{\text{MAC}}} \times N_{\text{lane}} \times N_{\text{tile}} \) [Op/s]
•	“대표 심볼율 프로파일: 16 Gsym/s (Base), 32 Gsym/s (Aggressive)”


- **Q28에서 할 일 (미리 정의)**
  - 위 파라미터에 구체적인 수치(예: \( R_{\text{sym}} = 16 \) Gsym/s, \( N_{\text{tile}} = 64 \) 등)를 대입,
    - Memory/Bus Mode: GB/s / TB/s 급 대역폭 수치화
    - PPU Mode: 3D-ADD/s, 3D-MAC/s를 FLOPS 유사 단위로 환산하여 기존 GPU/NPU와 비교
  - PhaseLock_std, Kuramoto 조건(Eb/N0 ≥ 16 dB, θ_std ≤ 1°)을 “정상 연산 조건”으로 명시

## 5. Q27 이후 로드맵 (아이디어)

- **Q28: Throughput / Ops-per-Second 계산**
  - 1 tile / N tiles 기준으로:
    - 메모리 모드: GB/s, pre/post-FEC BER 기반 실효 대역폭
    - PPU 모드: 3D-MAC/s, 3D-ADD/s 계산
- **Q29: Energy / Power Budget 개략 추정**
  - K, PhaseLock_std, FFE, 3D-MAC 연산당 에너지 가정 후,
    - 타일/시스템 레벨 Power Estimation
- **Q30: JEDEC-style “CoPBit PPU Phase Spec” 문서 초안**
  - 외부 공개/표준화를 염두에 둔 스펙 문서 골격

---