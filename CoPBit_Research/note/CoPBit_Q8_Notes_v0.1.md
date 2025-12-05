# CoPBit Q8 – x16 lanes 글로벌 드리프트 + Kuramoto 트래킹 노트 (v0.1)

## 1. 실험 개요

- 변조: 4bit / 심볼 CoPBit 16-PSK (Q1/Q3와 동일 맵핑)
- 구조: **x16 lanes**, 각 lane은 동일한 글로벌 위상 드리프트 φ[n]을 공유
- 채널 모델:
  - s_tx[n, l] : 16-PSK unit circle 심볼
  - φ[n]       : 심볼 간 랜덤 워크(global phase drift)
  - w[n, l]    : Es/N0 기준 복소 AWGN
  - 수신: `y[n, l] = e^{j φ[n]} · s_tx[n, l] + w[n, l]`
- 디코더:
  1. **Baseline**
     - 드리프트를 전혀 모른다고 가정
     - 각 lane을 독립 16-PSK로 보고, 최근접 위상 포인트로 하드 디코딩
  2. **x16 Kuramoto-style global phase tracking**
     - 모든 lane 관측 y[n, :]을 이용해 공통 φ[n]을 decision-directed 방식으로 추정
     - `y[n, l] · conj(s_hat[n, l])` 를 lane 평균해 φ_meas[n] 추정
     - `mu_phase` 로 1D Kuramoto-style 업데이트
     - φ_hat[n]으로 y[n, :]를 보정한 뒤 재디코딩

---

## 2. 실험 결과

### 2.1 Case A – drift_std_deg = 2.0, mu_phase = 0.05

```text
SNR_dB |  BER_base   |  BER_kura
--------------------------------
 10.0  |  4.748e-01 |  4.810e-01
 12.0  |  5.420e-01 |  5.446e-01
 14.0  |  5.091e-01 |  5.192e-01
 16.0  |  4.988e-01 |  4.975e-01
 18.0  |  5.011e-01 |  4.811e-01
 20.0  |  4.565e-01 |  4.389e-01
 	•	drift가 꽤 큰 상태(2°/step)에서 DD Kuramoto가 제대로 락을 못 잡는 상태.
	•	baseline과 Kuramoto 모두 BER ≈ 0.45~0.55 수준에서 머무름.
	•	“튜닝 안 된 Kuramoto + 너무 강한 드리프트”의 나쁜 예시로 보관.

⸻

2.2 Case B – drift_std_deg = 4.0, mu_phase = 0.05
SNR_dB |  BER_base   |  BER_kura
--------------------------------
 12.0  |  5.126e-01 |  5.144e-01
 14.0  |  5.340e-01 |  5.341e-01
 16.0  |  5.102e-01 |  5.069e-01
 18.0  |  4.995e-01 |  4.960e-01
	•	step당 4°/step 드리프트는 사실상 “락 불가 영역”.
	•	baseline / Kuramoto 모두 완전히 랜덤에 가까운 BER ≈ 0.5 근처.
	•	“멀티-lane Kuramoto도 감당 못 하는 수준의 극단 드리프트” 레퍼런스용.

⸻

2.3 Case C – drift_std_deg = 0.2, mu_phase = 0.1
SNR_dB |  BER_base   |  BER_kura
--------------------------------
 10.0  |  2.136e-01 |  3.943e-01
 12.0  |  2.608e-01 |  3.724e-01
 14.0  |  1.995e-01 |  8.087e-02
 16.0  |  3.688e-01 |  3.961e-02
 18.0  |  2.374e-01 |  1.397e-02
 20.0  |  1.237e-01 |  2.925e-03
 포인트: 저 SNR vs 고 SNR 영역이 완전히 갈라지는 예쁜 케이스.
	•	10, 12 dB:
	•	baseline이 오히려 더 낫고, Kuramoto는 결정을 믿고 업데이트하다가 스스로 더 망가짐.
	•	DD 위상 트래킹의 고전적인 “저 SNR 영역에서는 역효과” 구간.
	•	14 dB:
	•	base ≈ 0.20
	•	kura ≈ 8.1e-02 → 약 2.5× BER 개선
	•	16 dB:
	•	base ≈ 0.37
	•	kura ≈ 3.96e-02 → 약 10× BER 개선
	•	18 dB:
	•	base ≈ 0.237
	•	kura ≈ 1.40e-02 → ≈17× 개선
	•	20 dB:
	•	base ≈ 0.124
	•	kura ≈ 2.93e-03 → 40× 이상 개선

정리: drift_std_deg = 0.2°/step 조건에서
	•	baseline: 드리프트를 무시하므로 BER이 0.1~0.3 사이에서 바닥을 못 찍음
	•	x16 Kuramoto: SNR가 어느 정도 이상부턴 글로벌 위상이 lock 되면서
BER이 1e-2 ~ 1e-3 영역까지 자연스럽게 떨어짐

⸻

2.4 Case D – drift_std_deg = 1.0, mu_phase = 0.1
SNR_dB |  BER_base   |  BER_kura
--------------------------------
 18.0  |  3.904e-01 |  2.294e-01
 20.0  |  5.123e-01 |  4.268e-01
 22.0  |  4.407e-01 |  2.266e-03

	•	drift 1.0°/step은 꽤 강한 드리프트.
	•	18, 20 dB:
	•	둘 다 여전히 BER ≈ 0.2~0.5 수준, 제대로 락이 안 걸린 상태.
	•	22 dB:
	•	baseline: 여전히 BER ≈ 0.44 (거의 랜덤에 가까움)
	•	Kuramoto: BER ≈ 2.27e-03 까지 급락 (제대로 lock)

정리: drift_std_deg = 1°/step 같은 강한 드리프트에서도
	•	단순 16-PSK 디코더는 SNR를 아무리 올려도 BER ~0.4 근처에서 헤매지만
	•	x16 Kuramoto는 “충분히 높은 SNR”만 확보되면 global phase를 락시키고
BER을 1e-3 수준까지 복구할 수 있음.

⸻

3. 의미 정리 (v0.1)
	1.	글로벌 드리프트 환경에서의 한계
	•	4bit CoPBit 16-PSK는 global φ[n] drift가 존재하면
단일-lane 단순 디코더로는 SNR를 올려도 BER 바닥을 찍기 어렵다.
	2.	멀티-lane Kuramoto의 역할
	•	x16 lane 공동 관측을 사용하면:
	•	저 SNR 영역에서는 DD 특성상 오히려 악영향 가능
	•	그러나 일정 SNR 이상부터는 global phase lock 이 걸리면서
BER이 급격하게 내려간다.
	3.	CoPBit 멀티-lane 아키텍처의 메시지
	•	“단일 lane 4bit phase 시스템의 물리적 한계를,
lane 병렬 + Kuramoto-style phase coupling으로 돌파한다”는 그림을
수치로 보여 주는 첫 Q8 결과물.

⸻

4. 다음 단계 아이디어 (Q8 확장 방향)
	•	Q8a: 파일럿/Genie-aided Kuramoto 상한 성능
	•	앞부분 N_pilot 심볼은 참값 φ[n]으로 정렬 → 이론적 상한 BER.
	•	이후 payload 구간은 DD로 전환.
	•	Lane 수 스케일링:
	•	n_lanes = 1, 4, 16, 64에 대해 동일 drift/SNR에서 BER 비교.
	•	“lane 수 ↑ → Kuramoto 위상 추정 SNR ↑”를 수치로 확인.