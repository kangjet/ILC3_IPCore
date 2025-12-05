### Q13d – Drift 허용 범위 & Lane 스케일링 (Channel-b, M8, FFE=7, adaptive Kuramoto)

- 실험 조건  
  - 채널: Channel-b = [0.05, 0.5, 1.0, 0.5, 0.05] (강 ISI)  
  - 변조: CoPBit M8 (8-PSK, 3 bit/sym, unit circle)  
  - 등화기: FFE len=7, train_frac=0.2 (M8 기준 채널 b에서 LS 설계, 모든 실험 공통 사용)  
  - 위상 락: xN lanes(기본 64 lanes) + 글로벌 위상 random walk (drift_std_deg)  
    + adaptive + limited-step Kuramoto (|err_phasor| 가중치, φ_max = 10°)

- Eb/N0 vs BER (drift_std_deg = 0.25°, n_lanes = 64, FFE=7)  
  - pre-FEC 기준, Kuramoto 적용 시  
    - 18 dB: BER ≈ 2.5e-2  
    - 19 dB: BER ≈ 1.6e-2  
    - **20 dB: BER ≈ 1.0e-2 (1e-2 threshold 달성)**  
    - 21 dB: BER ≈ 5.7e-3  
    - 22 dB: BER ≈ 3.3e-3  

- Drift 허용 범위(22 dB, n_lanes = 64, FFE=7)  
  - drift_std_deg = 0.25°: BER ≈ 3.3e-3  
  - drift_std_deg = 0.5°: BER ≈ 3.5e-3  
  - drift_std_deg = 1.0°: BER ≈ 4.6e-3  
  - **drift_std_deg ≥ 2.0°: BER ≈ 4.4e-1 ~ 4.9e-1 (락 붕괴)**  
  → 실질적으로 **σ_drift ≲ 1°까지 안정적인 위상 락 가능**.

- Lane 스케일링 특성 (Eb/N0 = 20 dB, drift_std_deg = 0.25°, FFE=7)  
  - 16 lanes: BER ≈ 9.87e-3  
  - 64 lanes: BER ≈ 9.75e-3  
  - 256 lanes: BER ≈ 9.73e-3  
  → **16 lanes 이상에서 집단 위상 평균 효과가 포화**되고, BER은 거의 동일한 수준 유지.

- 요약 스펙(초안)  
  - Channel-b(강 ISI) 환경에서 CoPBit M8 + FFE(7-tap) + adaptive Kuramoto 위상 락 구조는  
    - pre-FEC BER 1e-2 기준으로,  
      - 요구 Eb/N0 ≈ 20 dB,  
      - 허용 글로벌 위상 드리프트 표준편차 σ_drift ≲ 1°,  
      - lane 수는 16 lanes 이상에서 BER 변화가 거의 없음.  
  - → 강 ISI 채널에서도 **실용적인 위상 락 기반 CoPBit 연산/통신 모드의 베이스라인**을 형성.

- 상세 실험 로그 및 표:  
  - `CoPBit_Q13d_drift_lane_scaling_summary_v0.1.md` 참조.