# CoPBit Q25b – 1024-lane PPU 3D-MAC (M8) under AWGN + PhaseLock_std v0.1

## 1. 목적

- CoPBit PPU 타일(1024 lanes)에서 **3D-MAC 연산**이  
  - AWGN + 공통 위상 노이즈(θ_std)  
  - PhaseLock_std (p_ref + data 혼합 PLL)  
  환경에서 어느 정도 연산 에러율(**op_error_3d_mac**)을 가지는지 확인.
- Q23a (심볼 단위 BER 맵), Q24a (3D-ADD), Q25a (디지털 truthcheck)에 이어  
  **실제 채널 + 위상노이즈 조건에서의 3D-MAC 연산 안정성**을 검증하는 단계.

---

## 2. 시뮬레이션 설정

### 공통 설정

- CoPBit 모드: M8 (8-PSK 기반 3D 값)
- PPU 타일:
  - `n_lanes = 1024`
  - `pref_stride = 16`  
    → lane index % 16 == 0 인 lane 들이 p_ref lane  
    → p_ref lanes = 64, data lanes = 960
- 3D-MAC:
  - `mac_len = 4`  
    → 매 타임스텝마다 **data lane 4개**를 선택해서 3D-MAC 수행  
    - truth  : 송신 M8 인덱스들 합 mod 8  
    - impl   : 복조된 M8 인덱스들 합 mod 8  
    - `op_error_3d_mac = P(truth != impl)`
- 위상 추적 (PhaseLock_std):
  - `mu_phase = 0.05`
  - `alpha_ref = 0.3`  
    → phase_err = 0.7 * err_ref + 0.3 * err_data
- 채널:
  - AWGN only (mid-ISI 없음, 순수 AWGN)
  - 공통 위상 노이즈:
    - θ_std(deg) ∈ {0.0, 0.5, 1.0, 2.0}
    - 심볼마다 하나의 φ_noise ~ N(0, (θ_std·π/180)^2) 를 생성하여 모든 lane에 공통 적용
- Noise / SNR:
  - `Eb/N0(dB) ∈ {12, 14, 16}`
  - Es=1 기준, Eb/N0 ≈ Es/N0 로 간주 (M8)
- 난수:
  - `n_sym = 50000` (time steps)
  - `seed = 1`

- 실행 스크립트:
  - `CoPBit_Research/python/copbit_q25b_ppu_3d_mac_awgn_phase_v0.py`

- 실행 예:
  ```bash
  (venv) python copbit_q25b_ppu_3d_mac_awgn_phase_v0.py \
    --n_sym 50000 \
    --ebn0_list "12,14,16" \
    --theta_std_list "0.0,0.5,1.0,2.0" \
    --n_lanes 1024 \
    --mac_len 4 \
    --mu_phase 0.05 \
    --alpha_ref 0.3 \
    --pref_stride 16 \
    --seed 1 \
    --csv_out "../Q25b_ppu_3d_mac_theta_ebn0_map.csv"
3. 결과 – θ_std vs Eb/N0 맵 (3D-MAC 연산 에러율)

CSV: CoPBit_Research/python/Q25b_ppu_3d_mac_theta_ebn0_map.csv 에 저장된 결과를 정리.

3.1 표: θ_std(deg) × Eb/N0(dB) → op_error_3d_mac
	•	op_error_3d_mac = 3D-MAC 연산에서 truth != impl 비율
θ_std (deg)
Eb/N0=12 dB
Eb/N0=14 dB
Eb/N0=16 dB
0.0
1.1324e-01
2.5920e-02
2.3800e-03
0.5
1.1638e-01
2.7080e-02
2.5800e-03
1.0
1.1976e-01
2.8040e-02
2.8800e-03
2.0
1.2812e-01
3.2060e-02
4.7400e-03

(소수 넷째자리 정도에서 반올림)

⸻

4. 해석
	1.	AWGN-only (θ_std=0.0)
	•	12 dB에서 3D-MAC 연산 에러율이 약 1.13×10^-1 수준.
	•	14 dB에서는 2.6×10^-2, 16 dB에서는 2.4×10^-3 수준.
	•	심볼 BER(Q23a)보다 다소 높은 에러율이지만, 3D-MAC이 여러 lane의 결과를 합산하는 연산임을 감안하면 자연스러운 수준.
	2.	위상 노이즈 증가에 따른 영향
	•	θ_std를 0 → 0.5 → 1.0 → 2.0°로 올리면,
	•	12 dB 기준: 약 0.113 → 0.116 → 0.120 → 0.128 로 완만하게 악화
	•	16 dB 기준: 약 2.38e-3 → 2.58e-3 → 2.88e-3 → 4.74e-3
	•	θ_std ≤ 1° 영역에서는 3D-MAC 연산이 비교적 안정적이고,
2°에서도 여전히 10^-2 ~ 10^-3 레벨에 머무름.
	3.	PPU 관점 요약
	•	1024-lane 타일에서 64 lane 정도를 p_ref로 쓰면서(16 lane당 1개)
PhaseLock_std(α_ref=0.3, mu_phase=0.05)를 적용한 경우,
	•	실질적으로 “심볼 연산 + 3D-MAC” 조합이 모두 정상 동작 가능한 수준의 에러율을 보여줌.
	•	특히 16 dB, θ_std ≤ 1° 영역에서는
	•	op_error_3d_mac ≈ (2.4 ~ 2.9) × 10^-3 수준
	•	이후 FEC나 상위 레벨에서의 반복 연산/재전송 구조를 고려하면
PPU 상에서의 3D 연산 primitive로 충분히 사용 가능한 스펙으로 해석 가능.

	4.	메모리/버스 파트와의 연결
	•	Q22b에서 확인한 PhaseLock_std θ_std 맵 (BER 기준) 과 비교하면,
	•	메모리/버스용 단일 심볼 판정에서도 θ_std ≤ 1° 영역이 실질적인 동작 영역이었고,
	•	PPU용 3D-MAC 연산도 같은 θ_std 영역에서 안정적으로 동작함.
	•	즉, 동일한 공정/PLL 스펙(θ_std ≤ 1°급)을 만족하면,
	•	CoPBit는 메모리 & 데이터버스뿐 아니라
	•	PPU 3D 연산(ADD/MAC)까지 같은 인프라에서 구동 가능하다는 일관된 그림이 만들어짐.

⸻

5. 결론 & Next Step 아이디어
	•	Q25b 결과로 확인된 것:
	1.	CoPBit PPU 타일(1024 lanes)에서 3D-MAC 연산이
AWGN + PhaseLock_std + 공통 위상노이즈 환경에서도 정상 동작한다.
	2.	θ_std가 01° 범위에서는 3D-MAC 에러율이 **수 퍼밀수 퍼센트 이하 영역**으로 유지되며,
메모리/버스 파트에서 요구되던 θ_std 스펙과 동일한 수준이다.
	3.	θ_std를 2°까지 올려도 16 dB 기준으로 10^-3~10^-2 사이에서 동작하여,
공정/PLL 여유를 조금 더 두더라도 PPU 연산으로서의 실현 가능성이 높다.
	•	다음 확장 후보:
	1.	mac_len을 4 → 8, 16 으로 키워서 벡터 연산 길이에 따른 에러율 스케일링 확인
	2.	pref_stride를 16 → 32, 64 로 늘려서
참조 lane 밀도를 줄였을 때 PPU 타일의 θ_std 허용 범위가 어떻게 변하는지 맵 추가
	3.	향후 Q26 이후에서:
	•	3D-MAC을 간단한 3D-MATMUL, 3D-CONV primitive로 확장
	•	PPU 1타일 당 Effective TOPS/W 혹은 “3D-OPS/W” 거친 산정으로 HW 성능 비교(기존 GPU/NPU 대비)

⸻

6. 로그 & CSV 위치
	•	로그:
	•	터미널 출력 복사하여:
CoPBit_Research/note/CoPBit_Q25b_PPU_3D_MAC_AWGN_PhaseLock_v0.1.md 에 정리
	•	CSV:
	•	CoPBit_Research/python/Q25b_ppu_3d_mac_theta_ebn0_map.csv
	•	헤더: EbN0_dB,theta_std_deg,mac_len,op_error_3d_mac

    
