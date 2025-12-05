# CoPBit Q10 – M-PSK AWGN BER vs Eb/N0 (bit-fair) v0.1

## 1. 실험 설정

- 스크립트: `CoPBit_Research/python/copbit_q10_mpsk_awgn_ebn0_compare_v0.py`
- 목적:
  - Q9(Es/N0 기준 M-PSK BER)의 결과를
  - **Eb/N0 기준(비트 공정 비교)**으로 다시 정리하기 위함.
- 변조 스킴:
  - M = 2, 4, 8, 16 (BPSK/NRZ, QPSK, 8-PSK, 16-PSK)
  - M=16은 CoPBit 4bit와 동일한 16포인트 등각 간격 위상 구조(단, 비트 라벨은 단순 binary).
- 채널:
  - AWGN-only, unit circle 심볼 (Es = 1)
  - Eb = Es / k (k = log2(M)) 가정
  - 따라서 **Es/N0(dB) = Eb/N0(dB) + 10·log10(k)** 변환 후 AWGN 인가
- 파라미터 예:
  - `n_sym = 200000`
  - `Eb/N0_list(dB) = [0, 2, 4, 6, 8, 10, 12, 14, 16]`
  - `M_list = [2, 4, 8, 16]`
  - `seed = 1`

## 2. 주요 결과 (Eb/N0 기준 BER 테이블)

```text
 EbN0_dB       BER_M2       BER_M4       BER_M8      BER_M16
------------------------------------------------------------
     0.0    7.816e-02    1.131e-01    2.027e-01    2.716e-01
     2.0    3.789e-02    5.529e-02    1.368e-01    2.274e-01
     4.0    1.278e-02    1.896e-02    8.011e-02    1.792e-01
     6.0    2.335e-03    3.465e-03    3.581e-02    1.272e-01
     8.0    2.100e-04    3.375e-04    1.080e-02    7.829e-02
    10.0    1.000e-05    2.500e-06    1.618e-03    3.793e-02
    12.0    0.000e+00    0.000e+00    1.400e-04    1.318e-02
    14.0    0.000e+00    0.000e+00    3.333e-06    2.576e-03
    16.0    0.000e+00    0.000e+00    0.000e+00    2.488e-04

    2.1 타깃 BER 기준 대략적인 Eb/N0
	•	pre-FEC BER ≈ 10⁻² 근처:
	•	M=2(BPSK/NRZ): Eb/N0 ≈ 4.5–5 dB
	•	M=4(QPSK):     Eb/N0 ≈ 5 dB
	•	M=8(8-PSK):    Eb/N0 ≈ 8–9 dB
	•	M=16(16-PSK):  Eb/N0 ≈ 11.5–12 dB
	•	pre-FEC BER ≈ 10⁻³ 근처:
	•	M=2: Eb/N0 ≈ 7 dB 전후
	•	M=4: Eb/N0 ≈ 7 dB 전후
	•	M=8: Eb/N0 ≈ 10.5 dB 근처
	•	M=16: Eb/N0 ≈ 13.5 dB 근처

→ M이 커질수록, 같은 Eb/N0에서 BER이 나빠지고
목표 BER을 만족시키기 위한 Eb/N0 요구치가 증가함을 확인.

3. CoPBit 관점에서의 해석
	1.	비트 공정 기준 베이스라인 확보
	•	서로 다른 M (=2,4,8,16)에 대해 “비트당 에너지(Eb)를 맞춘” 비교 결과를 확보.
	•	이후 CoPBit 4bit(16-PSK)를
	•	NRZ/BPSK, QPSK, 8-PSK와 동일 Eb/N0 축에서 비교할 수 있는 기준이 됨.
	•	PAM4 비교는 Q6 (PAM4 vs CoPBit4 AWGN) 결과와 함께 해석.
	2.	CoPBit 4bit(16-PSK)의 운용 Eb/N0 영역
	•	AWGN-only 기준:
	•	pre-FEC BER ≈ 10⁻² → Eb/N0 ≈ 12 dB 근처
	•	pre-FEC BER ≈ 10⁻³ → Eb/N0 ≈ 13.5 dB 근처
	•	이 값은 “순수 16-PSK” 기준이며,
실제 CoPBit 시스템에서는
	•	진폭 1레벨(amp constant) 구조에 따른 구현 이점,
	•	Kuramoto 기반 위상 추적,
	•	멀티레인 평균/동기화 효과,
	•	FEC 적용
등을 조합해 실질적인 시스템 이득을 설계하는 방향으로 해석 가능.
	3.	M 선택에 따른 적용 용도 구분의 기초
	•	Q10 결과를 기반으로 향후 다음과 같은 모드 분류가 가능:
	•	M=2: 초저 BER, 컨트롤/장거리용
	•	M=4: 중간 속도 + 안정성 위주 링크
	•	M=8: HBM / 고속 IO에서 PAM4 대체 후보(CoPBit 3bit 모드)
	•	M=16: CoPBit 4bit 모드 (단거리·고속 + Kuramoto + 멀티레인 + FEC 전제)
	•	이 모드 분류는 특허 명세서, 기술 개요, 사업계획서에서
“CoPBit 운용 모드 테이블” 작성 시 기초 데이터로 사용될 수 있다.