# CoPBit Q1~Q28 – Pre-IPCore Index v0.1

- Date: 2025-12-05
- Scope: CoPBit 메모리/버스 + PPU(Phase Processing Unit) Q-series 정리본
- 목적:
  - Q1~Q28까지 실험/노트/스크립트를 한 장에서 조망
  - “Pre-IPCore 패키지”의 기준 버전(v0.1) 정의
  - 이후 `CoPBit_Link_IP v0.x`, `CoPBit_PPU_Tile_IP v0.x` 설계의 레퍼런스로 사용

- 관련 디렉토리:
  - Notes: `CoPBit_Research/note/CoPBit_Qxx_*.md`
  - Python: `CoPBit_Research/python/copbit_qxx_*.py`
  - 결과 CSV/LOG: `CoPBit_Research/note/Qxx_*.log`, `Qxx_*.csv`, `Qxx_*.map` 등

---

## 0. 공통 가정 (Q-series 전체에 공통)

- 심볼 집합:  
  - M = 8 (3bit/sym) → CoPBit 3D 심볼 기본
- 채널:
  - AWGN only / mid-ISI (Channel-b 유사) 둘 다 사용
  - mid-ISI 조건에서는 RX FFE(DLL/PLL/PhaseLock) 포함
- Lane / Tile 구조:
  - 1 lane = 1 PAM/CoPBit 신호 경로
  - 1 tile = 1024 lanes (PPU 타일 기준)
- 정상 동작 조건 요약:
  - 메모리/버스: Pre-FEC BER + Q10/Q15 FEC 기준 만족
  - 위상:
    - 타일 내부 PhaseLock_std: θ_std_tile ≤ 1°
    - 타일 간 Kuramoto: drift_std ≤ 0.1°, θ_std_tile ≤ 0.5° 권장
  - SNR: Eb/N0 ≥ 16 dB 영역에서 “CoPBit 정상 영역”으로 간주

---

## 1. Q1~Q9 – 기본 컨셉/Constellation/쿠라모토

| ID  | Note 파일 (예)                      | 핵심 주제                                | 상태 |
|-----|-------------------------------------|-------------------------------------------|------|
| Q1  | `CoPBit_Q1_Constellation_v0.1.md`   | CoPBit 3D Constellation 정의 (M=8)        | 완료 |
| Q2  | `CoPBit_Q2_Kuramoto_v0.1.md`        | Kuramoto coupling 기본 수식/개념 정리     | 완료 |
| Q4  | `CoPBit_Q4_Kuramoto_Notes_v0.1.md`  | Kuramoto 동기화 조건/파라미터 정리       | 완료 |
| Q4' | `CoPBit_Q4_Kuramoto_Decode_Notes…`  | Kuramoto 상태에서 디코딩 관점 정리       | 완료 |
| Q5  | `CoPBit_Q5_BER_FEC_Notes_v0.1.md`   | BER ↔ FEC threshold mapping 기초          | 완료 |
| Q6  | `CoPBit_Q6_ComparePlan_v0.1.md`     | PAM4 vs CoPBit 비교 플랜                  | 완료 |
| Q8  | `CoPBit_Q8_Notes_v0.1.md`           | 채널/FFE/DLL 실험 플랜                    | 완료 |
| Q9  | `CoPBit_Q9_MPSK_Notes_v0.1.md`      | M-PSK 관점에서 CoPBit 해석 메모           | 완료 |

> 이 구간은 “개념·수식·비교전략” 레벨. 실제 수치/성능 검증은 Q10 이후에서 본격 진행.

---

## 2. Q10~Q16 – 메모리/버스 Pre-FEC + PhaseLock_std 기반

### 2.1 개요

- 목표:
  - PAM4 vs CoPBit(M=8)의 Pre-FEC BER, SNR gain, FEC 여유 마진 정량화
  - AWGN + mid-ISI 환경에서 FFE/DLL/PhaseLock_std 파라미터 스윕
  - pRef 기반 위상 잡음/흔들림에 대한 한계(θ_std 임계값) 확인

### 2.2 Q10~Q12 – 메모리/버스 기본 비교

| ID   | Note                                  | Python                                  | 핵심 내용                                               | 상태 |
|------|---------------------------------------|-----------------------------------------|----------------------------------------------------------|------|
| Q10  | `CoPBit_Q10_EbN0_Notes_v0.1.md`       | (ILC3_PData 쪽 Q10 스크립트 기반)       | CoPBit Pre-FEC BER vs Eb/N0 관계 정의, FEC 기준 연계    | 완료 |
| Q11  | `CoPBit_Q11_Mode_Applications_v0.1.md`| -                                       | CoPBit 동작 모드(메모리/버스/PPU) 어플리케이션 맵       | 완료 |
| Q12  | `CoPBit_Q12_PAM4_M8_ChannelCompare…`  | `copbit_q18_pam4_vs_m8_midISI_ffe_only` | Channel-a/b/c에서 PAM4 vs M8 mid-ISI FFE-only 비교      | 완료 |

핵심 결론(요약):

- 동일 채널/FFE 조건에서 CoPBit(M8)가 PAM4 대비 **SNR 여유**를 확보하는 영역 존재.
- Q10 FEC 테이블과 조합 시, **ILC3/CoPBit 계열이 표준 PAM4 대비 유리한 동작점**을 가짐.

---

### 2.3 Q13~Q16 – PhaseLock_std / 다레인 영향

| ID     | Note 파일                                           | Python 파일                                         | 핵심 질문                                            | 상태 |
|--------|------------------------------------------------------|-----------------------------------------------------|------------------------------------------------------|------|
| Q13    | `CoPBit_Q13_Overview_v0.1.md`                        | -                                                   | Q13 시리즈 전체 플로우 개요                          | 완료 |
| Q13d   | `CoPBit_Q13d_drift_lane_scaling_summary_v0.1.md`     | `copbit_q13d_lane_drift_adaptive_mu_v0.py`          | Lane 수·drift·FFE 길이에 따른 BER scaling            | 완료 |
| Q13e   | `CoPBit_Q13e_drift2_tuning_v0.1.md`                  | (Q13e 관련 스크립트)                               | drift=2° class에서 μ/φ_max 튜닝                      | 완료 |
| Q14    | `CoPBit_Q14_mu_phi_drift_sweep_v0.1.md`              | `parse_q14_results_v0.py`                           | μ_phase, φ_max, drift의 3D 스윕 → 안정 파라미터 영역 | 완료 |
| Q15    | `CoPBit_Q15_M8_vs_PAM4_worklog_v0.1.md`              | `copbit_q15_m8_vs_pam4_eq_kura_ebn0_v0.py`          | Kuramoto+EQ 환경에서 M8 vs PAM4 재비교               | 완료 |
| Q16    | `CoPBit_Q16_2lane_pRef_AWGN_PhaseNoise_v0.1.md`      | `copbit_q16_2lane_pref_awgn_phase_v0.py`           | 2-lane pRef, AWGN+PhaseNoise에서 PhaseLock_std 한계   | 완료 |
| Q16b   | `CoPBit_Q16_2lane_vs_3lane_pRef_AWGN_PhaseNoise…`    | `copbit_q16b_3lane_2pref1data_awgn_phase_v0.py`     | 2lane pRef vs 3lane (2pref+1data) 구조 비교          | 완료 |
| Q16c   | `CoPBit_Q16c_MultiLane_pRef_AWGN_PhaseNoise_v0.1.md` | `copbit_q16c_multi_lane_pref_awgn_phase_v0.py`      | Multi-lane pRef(AWGN)에서 θ_std scaling               | 완료 |
| Q16d   | `CoPBit_Q16_PhaseLock_std_Summary_v0.1.md`           | `copbit_q16d_multi_lane_pref_midISI_phase_v0.py`    | mid-ISI 포함한 PhaseLock_std 종합 요약               | 완료 |

핵심 결론(요약):

- **θ_std ≤ 1°** 영역에서 CoPBit PhaseLock_std는 AWGN + mid-ISI 환경에서도 안정적으로 동작.
- lane 수 확장(2 → 1024) 시에도, pRef 구조/FFE 튜닝으로 θ_std 제어 가능.
- 이 조건을 Q22/Q23/Q25/Q26에서 **“정상 동작 표준 조건”**으로 채택.

---

## 3. Q17~Q22 – pRef/θ_map + 64-lane/멀티타일 준비

### 3.1 pRef 밀도 / θ_spread 맵

| ID   | Note 파일                                           | Python 파일                                        | 내용                                      | 상태 |
|------|------------------------------------------------------|----------------------------------------------------|-------------------------------------------|------|
| Q17a | `CoPBit_Q17a_PrefDensity_Theta_Map_v0.1.md`          | `copbit_q17a_pref_density_theta_ebn0_awgn_v0.py`   | pRef density vs θ_std vs Eb/N0 맵        | 완료 |
| Q17b | `CoPBit_Q17b_pRef_PhaseSpread_Summary_v0.1.md`       | `copbit_q17b_pref_phase_spread_awgn_v0.py`         | pRef에 따른 Phase spread 통계             | 완료 |

요약:

- pRef density를 적절히 잡을 경우, θ_std를 1° 이하로 유지 가능한 Eb/N0, lane, tile 조건 정리.
- 이후 Q22/Q23의 θ-map 경계값 설정에 사용.

### 3.2 64-lane mid-ISI + FFE/PhaseLock_std

| ID   | Note 파일                                               | Python 파일                                            | 내용                                                    | 상태 |
|------|----------------------------------------------------------|--------------------------------------------------------|---------------------------------------------------------|------|
| Q20  | `CoPBit_Q20_MemBus_Channel_Roadmap_v0.1.md`              | `copbit_q20a_pam4_vs_m8_midISI_ffe_dfe_v0.py` 등      | Channel roadmap, PAM4 vs M8 eq baseline                 | 완료 |
| Q20c | `CoPBit_Q20c_PAM4_midISI_FFEonly_baseline_v0.1.md`       | `copbit_q20c_pam4_midISI_ffe_ls_baseline_v0.py`       | mid-ISI PAM4 FFE-only baseline                          | 완료 |
| Q20d | - (로그: `Q20d_m8_midISI_ffe11_tr0p5_ls.log`)           | `copbit_q20d_m8_midISI_ffe_ls_baseline_v0.py`         | 동일 조건 M8 baseline                                   | 완료 |
| Q21b | `CoPBit_Q21b_PAM4_vs_M8_midISI_FFE_LS_Sweep_16dB…`       | `copbit_q21b_pam4_vs_m8_midISI_ffe_ls_sweep_v0.py`    | 16 dB에서 PAM4 vs M8 FFE-LS sweep                       | 완료 |
| Q22a | `CoPBit_Q22a_M8_midISI_FFE_LS_pRefPLL_v0.1.md`           | `copbit_q22a_m8_midISI_pref_phase_ls_v0.py`           | FFE-LS + pRef PLL 환경에서 M8 성능                      | 완료 |
| Q22b | `CoPBit_Q22b_theta_ebn0_PhaseLock_map_v0.1.md`           | `copbit_q22b_m8_midISI_pref_phase_theta_ebn0_map_v0.py` + `Q22b_theta_ebn0_map.csv` | θ_std vs Eb/N0 map                                      | 완료 |
| Q22c | `CoPBit_Q22c_64lane_midISI_PhaseLock_std_Map_v0.1.md`    | (Q22c 관련 Python: Q22b map + 64-lane 실험)          | 64-lane mid-ISI 환경에서 PhaseLock_std map              | 완료 |

핵심 결론:

- 64-lane mid-ISI 조건에서도 **Eb/N0 ≥ 16 dB, θ_std ≤ 1°**이면 안정 동작.
- 이 결과가 PPU 타일(1024-lane) 설계의 기본 “메모리/버스 모드” 조건으로 사용됨.

---

## 4. Q23~Q26 – PPU 타일 / Kuramoto / 3D 연산 검증

### 4.1 Q23 – 1024-lane PPU 타일 (AWGN + PhaseLock_std)

| ID   | Note 파일                                     | Python 파일                                        | 요약                                          | 상태 |
|------|-----------------------------------------------|----------------------------------------------------|-----------------------------------------------|------|
| Q23a | `CoPBit_Q23a_PPU_Tile_AWGN_PhaseLock_v0.1.md` | `copbit_q23a_ppu_tile_awgn_phaseLock_v0.py`       | 1024-lane PPU 타일, AWGN+PhaseLock_std BER    | 완료 |
|      |                                               | 결과 CSV: `Q23b_ppu_theta_ebn0_map.csv`           | θ_std, Eb/N0에 따른 BER map                   | 완료 |

핵심 포인트:

- θ_std ≤ 1° 환경에서 1024-lane 타일도 메모리 모드 기준 BER 조건 만족.
- PPU 모드에서도 noPLL / DDonly / DD+pRef 동작 비교.

### 4.2 Q24 – 3D-ADD Truthcheck + AWGN

| ID   | Note 파일                                     | Python 파일                                    | 요약                                         | 상태 |
|------|-----------------------------------------------|------------------------------------------------|----------------------------------------------|------|
| Q24a | `CoPBit_Q24a_PPU_3D_Add_AWGN_v0.1.md`         | `copbit_q24a_ppu_3d_add_awgn_v0.py`           | AWGN/Phase 환경에서 3D-ADD BER/θ-map         | 완료 |
| Q24b | `CoPBit_Q24b_PPU_3D_Add_Truthcheck_v0.1.md`   | `copbit_q24b_ppu_3d_add_truthcheck_v0.py`     | 채널/위상/노이즈 0인 경우 Truthcheck = 0 error | 완료 |

결론:

- 로직 레벨(Truthcheck)에서 3D-ADD는 **완전 정합 (error 0)** 확인.
- 채널+위상 노이즈가 있어도 θ_std ≤ 1° 영역에서는 실용적인 BER/동작 보장.

### 4.3 Q25 – 3D-MAC Truthcheck + AWGN/Phase

| ID   | Note 파일                                         | Python 파일                                        | 요약                                                | 상태 |
|------|---------------------------------------------------|----------------------------------------------------|-----------------------------------------------------|------|
| Q25a | `CoPBit_Q25a_PPU_3D_MAC_Truthcheck_v0.1.md`       | `copbit_q25a_ppu_3d_mac_truthcheck_v0.py`         | MAC_len=3/4, full/random 모드 truthcheck = 0 error   | 완료 |
| Q25b | `CoPBit_Q25b_PPU_3D_MAC_AWGN_Phase_v0.1.md`       | `copbit_q25b_ppu_3d_mac_awgn_phase_v0.py`         | AWGN + θ_std 스윕에서 3D-MAC BER/성능               | 완료 |
|      |                                                   | 결과 CSV: `Q25b_ppu_3d_mac_theta_ebn0_map.csv`    | θ_std ≤ 1°에서 PPU 3D-MAC 정상 동작 확인            | 완료 |

결론:

- 3D-MAC primitive도 3D-ADD와 동일하게 **로직 레벨 완전 정합**.
- θ_std ≤ 1°, Eb/N0 ≥ 16 dB 조건이면 1024-lane 타일에서 MAC 연산도 안정.

### 4.4 Q26 – Tile 간 Kuramoto Lock Map

| ID   | Note 파일                                         | Python 파일                                      | 요약                                                    | 상태 |
|------|---------------------------------------------------|--------------------------------------------------|---------------------------------------------------------|------|
| Q26a | `CoPBit_Q26a_TileKuramoto_LockMap_v0.1.md`        | `copbit_q26a_ppu_tile_kura_lock_v0.py`          | 타일 수 vs Kuramoto coupling K vs drift_std lock map    | 완료 |
|      |                                                   | 결과 CSV: `Q26a_ppu_tile_kura_lock_map.csv`     | 기본 타일 수 케이스                                    | 완료 |
|      |                                                   | 결과 CSV: `Q26a_ppu_tile_kura_lock_map_256tiles.csv` | 256 타일까지 확장 맵                                   | 완료 |

핵심 결론:

- 타일 수가 증가할수록 Kuramoto lock이 오히려 더 안정해지는 영역 존재.
- K ≈ 0.2, drift_std ≤ 0.1° 조건에서 256 tiles까지 lock 유지 가능.
- “멀티타일 PPU 시스템”에서 **타일 간 θ_std ≤ 0.5° 권장** 조건 도출.

---

## 5. Q27~Q28 – PPU 아키텍처 / Throughput & GPU/NPU 비교

### 5.1 Q27 – PPU Architecture Overview

| ID   | Note 파일                                 | 내용                                           | 상태 |
|------|-------------------------------------------|------------------------------------------------|------|
| Q27  | `CoPBit_Q27_PPU_Arch_Overview_v0.1.md`    | PPU 타일 구조, Link/PPU 모드, 3D-연산 배치 개요 | 완료 |

- CoPBit를 다음 두 가지 IP 축으로 분리/정의:
  - **CoPBit_Link_IP**: 메모리/버스 PHY + Equalizer + PhaseLock
  - **CoPBit_PPU_Tile_IP**: 3D-ADD/3D-MAC 연산 타일
- 타일/레인 구조, Kuramoto 네트워크, pRef 배치 개념을 한 장에 정리.

### 5.2 Q28 – PPU Throughput / Ops-per-Second & GPU/NPU 비교

| ID   | Note 파일                                       | 내용                                                   | 상태 |
|------|-------------------------------------------------|--------------------------------------------------------|------|
| Q28  | `CoPBit_Q28_PPU_Throughput_Ops_v0.1.md`         | CoPBit 메모리/버스 대역폭 + 3D-ADD/3D-MAC TOp/s 계산   | 완료 |

핵심 수치 (64 tiles 기준):

- 타일 파라미터:
  - N_lane = 1024
  - R_sym Base = 16 Gsym/s, Agg = 32 Gsym/s
  - L_MAC = 4

1) **Memory/Bus Raw BW**

- 16 Gsym/s:
  - 1 tile ≈ 6.144 TB/s
  - 64 tiles ≈ 0.39 PB/s
- 32 Gsym/s:
  - 1 tile ≈ 12.288 TB/s
  - 64 tiles ≈ 0.79 PB/s

2) **3D-ADD / 3D-MAC Throughput (64 tiles)**

- 3D-ADD:
  - 16 Gsym/s: ≈ 1.05 P(3D-ADD)/s
  - 32 Gsym/s: ≈ 2.10 P(3D-ADD)/s
- 3D-MAC (L=4):
  - 16 Gsym/s: ≈ 0.26 P(3D-MAC)/s
  - 32 Gsym/s: ≈ 0.52 P(3D-MAC)/s

3) **FLOPs-equivalent (1 3D-MAC = 6~9 FLOPs 가정)**

- 16 Gsym/s, 64 tiles:
  - ≈ 1.6 ~ 2.4 PFLOPS
- 32 Gsym/s, 64 tiles:
  - ≈ 3.1 ~ 4.7 PFLOPS

→ 64 tiles 기준으로 이미 **H100급(≈1 PFLOPS)**을 넘어서는 스케일  
→ 256 tiles, 512 tiles, 1024 tiles로 확장 시 Blackwell-class 이상의 이론적 연산력 가능.

---

## 6. Pre-IPCore 결론 및 다음 챕터

### 6.1 Pre-IPCore 레벨에서의 결론

1. **메모리/버스 측면**
   - CoPBit(M=8) 링크는 PAM4 대비 **동일 채널에서 더 낮은 BER 또는 SNR 이득** 확보 가능.
   - mid-ISI + FFE + PhaseLock_std 환경에서도 **Eb/N0 ≥ 16 dB, θ_std ≤ 1°** 조건이면
     - Pre-FEC BER + FEC 테이블 기준을 만족.
   - 멀티타일(64~256 tiles)까지 고려했을 때, **PB/s급 대역폭**을 구현 가능한 수준.

2. **PPU(3D 연산) 측면**
   - 3D-ADD / 3D-MAC primitive:
     - 채널/위상/노이즈 없는 Truthcheck 환경에서 **연산 오차 0** 확인 (Q24/Q25).
   - AWGN + PhaseNoise + mid-ISI 환경에서도,
     - 1024-lane 타일 기준, θ_std ≤ 1° 영역에서 정상 동작.
   - 64 tiles 기준:
     - 3D-MAC 연산은 **1.6~4.7 PFLOPS-equivalent** 스케일.
     - 메모리/버스와 동일 구조 위에서 연산·전송 결합 가능.

3. **Kuramoto + Multi-Tile**
   - Kuramoto coupling (K ≈ 0.2)과 적절한 drift_std 관리로,
     - 타일 수가 많아질수록 lock이 더 안정되는 Sweet spot 존재.
   - 256 tiles까지의 lock map에서,
     - 타일 간 θ_std ≤ 0.5° 유지 가능한 조건 확인.

4. **종합**
   - CoPBit는 **“Memory/Bus + PPU(3D)”**를 동시에 만족하는 아키텍처로,
     - 이론/시뮬레이션 레벨에서 **Pre-IPCore 검증 단계는 사실상 완료**된 상태.
   - 다음 단계는 ILC3처럼:
     - `CoPBit_Link_IP v0.1`
     - `CoPBit_PPU_Tile_IP v0.1`
     로 나누어 실제 RTL/IPCore 설계로 들어가는 챕터.

### 6.2 다음 챕터 제안 (Post-Q28)

1. `CoPBit_PreIPCore_Q1_Q28_v0.1` Git 태그/패키지 생성
2. 새 브랜치:
   - `copbit_link_ip_v0`
   - `copbit_ppu_ip_v0`
3. 문서:
   - `ILC3_IPCore_Docs_Index_v0.1.md` 스타일로
   - `CoPBit_IPCore_Docs_Index_v0.1.md` 추가
4. 우선순위:
   - 시장/표준 관점: `CoPBit_Link_IP v0.1` 먼저
   - CoPBit 아이덴티티(3D 연산) 강조: `CoPBit_PPU_Tile_IP v0.1` 병렬 진행 가능

---