# CoPBit 위상부 설계 요건 v0.1  
### (Q13d lane+drift 실험 + Q14 μ/φ 스윕 통합 정리)

작성일: 2025-12-03  
프로젝트: ILC-4_CoPBit / CoPBit_Research  
관련 스크립트: `copbit_q13d_lane_drift_adaptive_mu_v0.py`

---

## 기본 모드 정의 (PhaseLock_std)

PhaseLock_std: Channel-b (5-tap mid-ISI), M8 (8-PSK, 3bit/sym), L=64 lanes, drift_std ≈ 1°, FFE_len = 7 (train_frac = 0.2), μ_phase = 0.10, φ_max_deg = 10°, pre-FEC BER ≤ 1e-2 @ Eb/N0 ≈ 21 dB.

---

## 1. 목적

CoPBit M8 위상부(8-PSK, 3bit/sym)가 **실제 멀티레인 환경에서 어느 정도 드리프트·노이즈까지 안정적으로 위상 락이 가능한지**를 수치로 정의하고,  
그에 맞는 **Kuramoto 위상 루프 파라미터(μ_phase, φ_max_deg)** 및 **EQ 설정(FFE 길이, train 비율)** 의 **베이스라인 스펙**을 정리한다.

- Q13d: lane 수, drift 표준편차(σ_drift), Eb/N0, FFE 길이가 위상 락에 미치는 영향 평가
- Q14 : Q13d 결과를 바탕으로 **μ_phase / φ_max_deg** 스윕을 통해 설계용 **위상 루프 베이스라인** 선정

최종적으로, 메모리/IO 인터페이스용 CoPBit IP 설계 시 다음과 같은 질문에 바로 답할 수 있는 상태를 만드는 것이 목표다.

> “lane=64 기준, 채널-b급 ISI에서 드리프트가 σ≈1°이면, 어느 정도 Eb/N0에서 위상부 BER을 1e-2 이하로 잡을 수 있는가?”  
> “σ≈2° 수준의 열/공정 위상 드리프트를 허용하려면, μ와 φ_max를 어디까지 올려야 하고, 그때 BER 페널티는 어느 정도인가?”

---

## 2. 공통 실험 조건 (Q13d, Q14)

- 변조: **M8 (8-PSK, 3bit/sym)**  
  - 유닛 서클: `s_k = exp(j * 2πk / 8), k=0..7`
  - bit-fair AWGN 기준으로 Eb/N0 설정
- 채널: **Channel-b, 5탭 ISI**
  - 탭: `[0.05, 0.5, 1.0, 0.5, 0.05]`
  - 모든 실험에서 동일하게 사용
- 레인:
  - 기본: **L = 64 lanes**
  - 일부 실험에서 L = 16, 256 도 병행 (lane scaling 체크)
- 등화기(FFE):
  - Q13 초반 비교: **FFE length = 5 vs 7**, `train_frac = 0.2`
  - 최종 베이스라인: **FFE length = 7, train_frac = 0.2**
- Kuramoto 위상 루프:
  - 기본 업데이트:  
    `θ_next = θ + μ_phase * |err_phasor| * clip(∠err_phasor, ±φ_max_deg)`
  - **adaptive step**:  
    - |err_phasor|가 클수록 step ↑  
    - φ_max_deg로 한 스텝 최대 회전각 제한
  - Q13d: 주로 `μ_phase = 0.10`, `φ_max_deg = 10.0` 사용  
  - Q14 : `μ_phase ∈ {0.05, 0.10, 0.20}`, `φ_max_deg ∈ {5, 10, 20}` 스윕
- 드리프트:
  - lane별 독립적인 **가우시안 위상 드리프트**  
    `θ_drift ~ N(0, drift_std_deg^2)`  
  - Q13d: `drift_std_deg ∈ {0.25, 0.5, 1.0, 2.0, 3.0}`  
  - Q14 : 주요 관심 영역 **1.0° / 2.0°** 집중

---

## 3. Q13d 결과 요약 – Drift/Lane/EbN0 영향

### 3.1 FFE 길이 5 vs 7 (drift_std=0.25°, L=64)

예시 (채널-b, drift_std_deg=0.25, L=64):

| FFE_len | Eb/N0(dB) | BER_M8_base | BER_M8_kura(adapt) |
|--------:|----------:|------------:|--------------------:|
| 5       | 24        | 5.442e-01   | 1.597e-02           |
| 7       | 20        | 5.452e-01   | 9.784e-03           |
| 7       | 22        | 4.689e-01   | 3.273e-03           |
| 7       | 24        | 4.779e-01   | 9.629e-04           |
| 7       | 26        | 4.077e-01   | 2.604e-04           |

관찰:

- base(위상 락 전)는 항상 BER≈0.4–0.55 근처(완전 깨짐).
- **FFE=7** 로 바꾸면 모든 Eb/N0에서 **Kuramoto 적응 후 BER이 FFE=5보다 안정적**.
- 특히 **24 dB에서 1e-3 이하**, 26 dB에서 1e-4 수준까지 떨어짐.

⇒ **CoPBit 위상부 baseline EQ는 FFE_len = 7, train_frac = 0.2로 확정.**

---

### 3.2 Drift(σ) 스윕 @ Eb/N0 = 22 dB, L=64 (FFE=7, μ=0.10, φ_max=10°)

| drift_std_deg | BER_M8_base | BER_M8_kura(adapt) |
|--------------:|------------:|--------------------:|
| 0.25          | 4.708e-01   | 3.279e-03           |
| 0.50          | 4.733e-01   | 3.517e-03           |
| 1.00          | 5.273e-01   | 4.563e-03           |
| 2.00          | 4.947e-01   | 4.393e-01           |
| 3.00          | 5.013e-01   | 4.872e-01           |

관찰:

- **σ_drift ≤ 1°**: Eb/N0=22 dB에서 BER ≈ (3–5)e-3 → 충분히 안정적인 pre-FEC 수준.
- **σ_drift ≈ 2°**: 위상 루프가 거의 깨져서 BER ≈ 0.44 (락 실패).
- **σ_drift ≈ 3°**: 사실상 베이스라인 수준(≈0.48)으로 완전 붕괴.

⇒ **Q13 기준으로는 “실질 허용 drift 범위”를 σ ≈ 1° 근처로 보는 것이 타당.**  
   2° 이상은 별도의 강화된 위상 루프 설계/보정이 필요.

---

### 3.3 Eb/N0 스윕 (drift_std=0.25°, L=64, FFE=7, μ=0.10, φ_max=10°)

| Eb/N0(dB) | BER_M8_base | BER_M8_kura(adapt) |
|----------:|------------:|--------------------:|
| 18.0      | 4.750e-01   | 2.486e-02           |
| 19.0      | 4.825e-01   | 1.594e-02           |
| 20.0      | 5.505e-01   | 9.790e-03           |
| 21.0      | 4.745e-01   | 5.744e-03           |
| 22.0      | 5.284e-01   | 3.284e-03           |

- **1e-2 threshold** 기준:
  - **drift=0.25°** 에서는 **Eb/N0 ≈ 20 dB** 부근에서 1e-2를 처음으로 통과.
  - 22 dB에서는 충분히 마진 있는 3e-3 수준.

---

### 3.4 Drift=1°에서 Eb/N0 스윕 (L=64, FFE=7, μ=0.10, φ_max=10°)

| Eb/N0(dB) | BER_M8_base | BER_M8_kura(adapt) |
|----------:|------------:|--------------------:|
| 18.0      | 5.133e-01   | 2.890e-02           |
| 19.0      | 5.058e-01   | 1.897e-02           |
| 20.0      | 4.888e-01   | 1.213e-02           |
| 21.0      | 5.076e-01   | 7.523e-03           |
| 22.0      | 4.955e-01   | 4.563e-03           |
| 23.0      | 4.647e-01   | 2.757e-03           |

관찰:

- drift=1°에서도 **Eb/N0 ≥ 21 dB** 구간에서 BER ≤ 1e-2 달성.
- 20 dB에서는 약 1.2e-2 수준으로, **threshold 바로 위**에 위치.

⇒ **“σ_drift ≈ 1° 환경에서는 Eb/N0 ≈ 21 dB 이상이면 위상부 BER 1e-2 이하 달성”**  
   라는 경험적 스펙을 설정 가능.

---

### 3.5 Lane scaling (drift=0.25°, Eb/N0=20 dB, FFE=7)

| n_lanes | Eb/N0(dB) | BER_M8_kura(adapt) |
|--------:|----------:|--------------------:|
| 16      | 20.0      | 9.871e-03           |
| 64      | 20.0      | 9.753e-03           |
| 256     | 20.0      | 9.729e-03           |

관찰:

- lane 수를 16 → 64 → 256으로 올려도 **BER는 거의 동일**.
- 이는 **Kuramoto에서 사용하는 평균 phasor가 이미 L=16 수준에서도 충분한 코히어런스를 갖고 있음**을 시사.
- 더 높은 lane 수는 drift 추정의 분산을 줄여줄 수 있지만, **실질적인 BER 개선은 미미**.

⇒ CoPBit 인터페이스를 **수백~수천 lane으로 확장해도 Kuramoto 위상부가 “lane 수” 때문에 깨지지는 않는다**는 근거.

---

## 4. Q14 결과 – μ_phase / φ_max 스윕과 베이스라인 선택

Q13d에서 **(μ_phase=0.10, φ_max=10°)** 가 drift=0.25°~1°에서 잘 동작하는 것을 확인했다.  
Q14에서는 설계를 조금 더 체계화하기 위해, 아래와 같이 스윕을 수행했다.

- drift_std_deg ∈ {1.0, 2.0}
- μ_phase ∈ {0.05, 0.10, 0.20}
- φ_max_deg ∈ {5, 10, 20}
- Eb/N0(dB) ∈ {18, 20, 22}
- 기타 조건: L=64, FFE_len=7, train_frac=0.2

결과는 `CoPBit_Q14_mu_phi_drift_sweep_summary.csv` 에 집계되어 있고, 여기서는 **디자인 관점에서 중요한 패턴**만 정리한다.

### 4.1 Drift = 1° 구간 (주력 스펙 존)

- 대부분의 (μ, φ) 조합에서 **조금만 Eb/N0를 올리면** 1e-2 이하 BER 달성 가능.
- 특히, **μ=0.10, φ_max=10°** 조합은
  - 이미 Q13d에서 검증된 값이고,
  - Q14에서도 drift=1°에서 **Eb/N0 ≈ 21 dB 이상**이면 BER ≤ 1e-2 영역에 안정적으로 진입.

⇒ **drift=1°를 타겟으로 하는 기본 설계에서는 (μ=0.10, φ_max=10°)를 베이스라인으로 채택.**

### 4.2 Drift = 2° 구간 (확장 스펙 존)

- drift=2°에서는, **μ가 너무 작으면(0.05) 위상 락이 거의 잡히지 않음** (BER≈0.5).
- μ를 0.20까지 올리면:
  - 예시: μ=0.20, φ_max=10°  
    - Eb/N0=20 dB → BER ≈ 0.13  
    - Eb/N0=22 dB → BER ≈ 6.6e-03 (1e-2 이하)
- 다만 n_sym=1e6 기준으로 **Eb/N0에 따라 BER이 요동치는 구간**도 있어,
  - drift=2°는 “**강화 모드/캐리브레이션 모드**” 정도의 위치로 보는 것이 설계상 안전.

⇒ 설계 관점:

- **표준 동작 모드**: σ_drift ≈ 1° 이하  
  - μ=0.10, φ_max=10°  
  - Eb/N0 ≥ 21 dB → BER ≤ 1e-2
- **확장/캐리브레이션 모드**: σ_drift ≈ 2°  
  - μ≈0.20, φ_max≈10° 이상  
  - Eb/N0를 22 dB 이상으로 끌어올리면 1e-2 근처까지 수렴 가능 (대신 안정성/진동 검증 필요)

---

## 5. CoPBit 위상부 설계 요건 (v0.1 제안)

Q13 + Q14 결과를 바탕으로, **실제 IP 스펙 문장**으로 쓸 수 있는 형태로 요약하면:

1. **채널 조건**
   - 대상 채널: mid-ISI 수준의 **5-tap Channel-b** 등화 후 환경.
   - 위상부 스펙은 “FFE_len=7, train_frac=0.2” RX EQ를 전제.

2. **위상 드리프트 허용 범위**
   - **정규분포 기준 σ_drift ≤ 1°** (lane별 독립 드리프트)에서
     - Eb/N0 ≥ 21 dB (M8, 3bit/sym, bit-fair)일 때
     - **위상부 pre-FEC BER ≤ 1e-2** 달성.
   - σ_drift ≈ 0.25° ~ 0.5°인 경우
     - Eb/N0 ≈ 20 dB에서 이미 **1e-2 이하**.
     - 22 dB에서는 **3e-3 수준**으로 충분한 FEC 마진 확보.

3. **Kuramoto 위상 루프 파라미터 (베이스라인 모드)**
   - μ_phase = **0.10**
   - φ_max_deg = **10°**
   - adaptive step: `Δθ ∝ μ_phase · |err_phasor| · clip(∠err_phasor)`
   - lane 수 L은 16~256에서 성능 변화가 미미하므로,  
     **L≥16이면 본 베이스라인 파라미터를 그대로 사용 가능.**

4. **확장 모드 (고 drift 환경용 튜닝 포인트)**
   - σ_drift ≈ 2° 수준에서:
     - μ_phase를 **0.20** 근방까지 올리고,
     - Eb/N0 ≥ 22 dB일 때 1e-2 근처까지 수렴하는 조합이 존재.
   - 다만 BER 변동성이 커지고 일부 Eb/N0에서 발산하는 경향이 있어,
     - **“self-calibration / training 모드”** 또는
     - **온도/공정 모니터링 기반 재-락 절차**와 함께 사용하는 것이 바람직.

5. **Lane scaling**
   - L=16, 64, 256 실험에서:
     - drift=0.25°, Eb/N0=20 dB 기준 BER≈1e-2로 **거의 동일**.
   - ⇒ 위상부 설계 시 **lane 수는 코히어런스 향상보다는 통계 평균 안정성을 높이는 역할** 정도로 간주 가능.
   - CoPBit 1024-lane 이상으로 확장해도, Kuramoto 위상부는 **lane 수 때문에 오히려 깨질 가능성은 낮다**는 근거 확보.

---

## 6. 파일/스크립트 맵

이 문서와 연결되는 실제 코드/로그/자료:

- **스크립트**
  - `CoPBit_Research/python/copbit_q13d_lane_drift_adaptive_mu_v0.py`
    - Q13d, Q14 모든 실험의 공통 드라이버.
    - lane 수, drift_std_deg, Eb/N0, μ_phase, φ_max_deg를 인자로 받아 BER 계산.
- **노트/결과 정리**
  - `CoPBit_Research/note/CoPBit_Q13d_lane_drift_adaptive_mu_v0.1.md`
    - Q13d 상세 로그/표/그래프 설명.
  - `CoPBit_Research/note/CoPBit_Q14_mu_phi_drift_sweep_summary.csv`
    - Q14 μ/φ/drift/EbN0 스윕 결과 집계 테이블.
  - `CoPBit_Research/note/CoPBit_Q14_mu_phi_drift_baseline_v0.1.docx`
    - Q14 베이스라인을 문서 형식으로 정리한 버전.
- **그래프 예시 (이미 생성된 경우)**
  - `Q13d_EbN0_vs_BER_drift0p25_L64_FFE7.png`
  - `Q13d_DriftStd_vs_BER_EbN0_22dB_L64_FFE7.png`
  - `Q13d_Lanes_vs_BER_EbN0_20dB_drift0p25_FFE7.png`

이 문서(`CoPBit 위상부 설계 요건 v0.1`)는 위 파일들을 상위 개념으로 묶는 **요약 스펙 시트**이며,  
향후 CoPBit 정식 데이터시트/특허 명세서 작성 시 **“Phase-Lock Design Requirements” 섹션의 초안**으로 사용할 수 있다.
