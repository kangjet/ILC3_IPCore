# CoPBit Q25a – PPU 3D-MAC truthcheck (no channel / no phase / no noise) v0.1

## 1. 목적

- Q24b에서 검증한 3D-ADD primitive  
  \[
    \text{ADD3D}(a, b) = (a + b) \bmod M
  \]
  를 여러 번 체인으로 연결했을 때,

  \[
    y_{\text{MAC}} = (a_0 + a_1 + \dots + a_{K-1}) \bmod M
  \]

  를 계산하는 **3D-MAC primitive**가  
  - 논리적인 ground truth와 100% 일치하는지
  - 채널/위상/노이즈/PLL 없이 “순수 디지털 연산” 관점에서 문제 없는지

  를 검증하는 것이 목표.

- 이 결과는 이후 Q25b/Q26에서  
  **AWGN + 위상 노이즈 + PhaseLock_std가 포함된 PPU 3D-MAC** 성능 실험의
  “디지털 코어 baseline”으로 사용됨.

---

## 2. 시뮬레이션 설정

- 스크립트:  
  - `CoPBit_Research/python/copbit_q25a_ppu_3d_mac_truthcheck_v0.py`

- 기본 파라미터:
  - Modulation: `M = 8` (M8)
  - MAC 길이: `mac_len = K`
    - random 테스트: `K = 4`
    - full 테스트: `K = 3`
  - 채널/위상/노이즈:
    - **모두 OFF**
    - no channel / no phase / no noise / no PLL / no FFE / no DFE

- 3D-ADD / 3D-MAC 정의

  - 3D-ADD truth:
    \[
      \text{ADD3D\_truth}(a, b) = (a + b) \bmod M
    \]

  - 3D-ADD 구현 (옵션 A = truth와 동일한 디지털 정의):
    \[
      \text{ADD3D\_impl}(a, b) = (a + b) \bmod M
    \]

  - 3D-MAC truth:
    \[
      \text{MAC3D\_truth}(\mathbf{a}) = \left(\sum_{k=0}^{K-1} a_k\right) \bmod M
    \]

  - 3D-MAC 구현:
    - 3D-ADD primitive를 체인으로 연결:
      \[
        \text{MAC3D\_impl}(\mathbf{a}) =
        (((a_0 + a_1) \bmod M + a_2) \bmod M + \dots + a_{K-1}) \bmod M
      \]

- 평가 메트릭:
  - 연산 에러율:
    \[
      \text{op\_error\_3d\_mac} =
        \frac{\#\{\mathbf{a} : \text{MAC3D\_impl}(\mathbf{a}) \neq \text{MAC3D\_truth}(\mathbf{a})\}}
             {\#\{\mathbf{a}\}}
    \]
  - Confusion Matrix:
    - rows: truth_idx (0..M-1)
    - cols: impl_idx (0..M-1)

---

## 3. 결과 – random 모드 (K = 4, n_samples = 100000)

### 3.1 실행 커맨드

```bash
cd /Users/kangjet/ILC-4_CoPBit/CoPBit_Research/python

python copbit_q25a_ppu_3d_mac_truthcheck_v0.py \
  --mode random \
  --mac_len 4 \
  --n_samples 100000 \
  --seed 1 \
  --show_confmat

 3.2 로그 요약
[Param] mode      = random
[Param] M         = 8
[Param] mac_len   = 4
[Param] n_samples = 100000
[Param] seed      = 1

==============================================================
  Metric             |  Value
--------------------------------------------------------------
  op_error_3d_mac    |  0.000000
--------------------------------------------------------------

[Confusion Matrix] rows = truth_idx(0..M-1), cols = impl_idx(0..M-1)
0 |  12500      0      0      0      0      0      0      0
1 |      0  12568      0      0      0      0      0      0
2 |      0      0  12414      0      0      0      0      0
3 |      0      0      0  12401      0      0      0      0
4 |      0      0      0      0  12325      0      0      0
5 |      0      0      0      0      0  12681      0      0
6 |      0      0      0      0      0      0  12768      0
7 |      0      0      0      0      0      0      0  12343

	•	op_error_3d_mac = 0.0
	•	Confusion Matrix:
	•	완전 대각선 (truth == impl)
	•	각 truth index에 대해 샘플 수가 약 1.25만 근처로 분포 → 랜덤 입력이 균일하게 잘 생성된 것도 확인.

4. 결과 – full 모드 (K = 3, 모든 조합 전수 검사)

4.1 실행 커맨드
python copbit_q25a_ppu_3d_mac_truthcheck_v0.py \
  --mode full \
  --mac_len 3 \
  --M 8 \
  --show_confmat

[Param] mode      = full
[Param] M         = 8
[Param] mac_len   = 3

==============================================================
  Metric             |  Value
--------------------------------------------------------------
  op_error_3d_mac    |  0.000000
--------------------------------------------------------------

[Confusion Matrix] rows = truth_idx(0..M-1), cols = impl_idx(0..M-1)
0 |     64      0      0      0      0      0      0      0
1 |      0     64      0      0      0      0      0      0
2 |      0      0     64      0      0      0      0      0
3 |      0      0      0     64      0      0      0      0
4 |      0      0      0      0     64      0      0      0
5 |      0      0      0      0      0     64      0      0
6 |      0      0      0      0      0      0     64      0
7 |      0      0      0      0      0      0      0     64

	•	M = 8, K = 3 → 총 조합 수:
[
8^3 = 512
]
	•	각 truth index(0..7)마다 정확히 64개 조합이 존재 →
Confusion Matrix 대각선 값이 전부 64로 동일.
	•	op_error_3d_mac = 0.0
→ 모든 입력 조합에서 구현이 truth와 1:1로 일치.

⸻

5. 해석 및 결론
	1.	3D-ADD primitive (Q24b) + 체인 구조로 만든 3D-MAC(Q25a) 는
	•	random 테스트 (K=4, n=100k)
	•	full 테스트 (K=3, M^K=512 조합 전수)
에서 모두 op_error_3d_mac = 0를 달성.
	2.	Confusion Matrix가 두 케이스 모두 완전한 단위 행렬 형태(대각선 100%) 이므로
	•	구현된 mac3d_impl()이
[
(a_0 + a_1 + \dots + a_{K-1}) \bmod 8
]
라는 수학적 정의와 완전히 일치함을 확인.
	3.	이 결과는:
	•	PPU의 기본 3D 연산 primitive(3D-ADD + 3D-MAC) 가
	•	채널/위상/노이즈가 없을 때,
	•	순수 디지털 관점에서 버그 없이 동작한다는 것을 의미.
	4.	따라서 Q25 이후 단계(Q25b/Q26 등)에서는
	•	AWGN
	•	위상 노이즈 (θ_std)
	•	PhaseLock_std (p_ref 레인 기반)
을 포함시켜,
	•	PPU 3D-MAC 연산 BER vs. Eb/N0, θ_std, mac_len 맵을 그리는 방향으로 진행하면 됨.

6. 다음 로드맵 (초안)
	•	Q25b:
	•	AWGN + PhaseLock_std 포함한 PPU 3D-MAC 실험
	•	입력: M8, mac_len = 4 (기본), 1024-lane tile
	•	출력: op_error_3d_mac(Eb/N0, θ_std, mac_len)
	•	결과: Q25b_ppu_3d_mac_theta_ebn0_map.csv 형태
	•	Q26 (후보):
	•	3D-MAC을 여러 번 반복한 “작은 3D-Matrix-Vector MAC” 구조 정의
	•	PPU vs GPU/NPU와 비교할 때 사용할 “기본 연산 블록” 정의