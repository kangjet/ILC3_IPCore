# CoPBit_Q9_MPSK_Notes_v0.1

CoPBit Q9 – M-PSK AWGN BER 패밀리 실험 정리 메모  
버전: v0.1  
스크립트: `CoPBit_Research/python/copbit_q9_mpsk_awgn_compare_v0.py`  
실행 일시: 2025-12-03

---

## 1. 실험 목적

- **M-PSK 패밀리의 이론적 베이스라인 확인**
  - M = 2(BPSK/NRZ), 4(QPSK), 8, 16(CoPBit 4bit와 동일 각도 간격) 에 대해
  - **AWGN-only, unit circle(Es=1)** 조건에서 **BER vs SNR(dB)** 곡선의 정성적 패턴 확인
- CoPBit 4bit(16-PSK 구조)가
  - **일반적인 M-PSK 이론과 일관된지 검증**
  - 이후 CoPBit 특유의 구조(Kuramoto, 멀티-lane, guard 등)를 얹기 위한 **기본 레퍼런스** 확보

---

## 2. 실험 조건

- 스크립트: `copbit_q9_mpsk_awgn_compare_v0.py`
- 공통 조건:
  - 심볼 수: `n_sym = 100000`
  - SNR 리스트 (Es/N0[dB]): `snr_list = [10, 12, 14, 16, 18, 20]`
  - M 리스트: `M_list = [2, 4, 8, 16]`
  - 랜덤 시드: `seed = 1`
- 변조/복조:
  - **M-PSK (unit circle)**
    - \( s_k = \exp(j \cdot 2\pi k / M),\; k = 0,\dots,M-1 \)
    - CoPBit Q1에서 정의한 16포인트 위상 간격(22.5°)과 동일한 각도 구조
  - 비트 매핑: 단순 binary (Gray 아님)
- 채널/노이즈:
  - **AWGN-only**
  - Es = 1 기준, Es/N0 = SNR(dB)
  - 각 성분(실/허수) 노이즈 분산: \( \sigma^2 = \frac{1}{2 \cdot EsN0} \)

---

## 3. 실험 결과 (로그 캡처)

실행 로그:

```text
=== CoPBit Q9 – M-PSK AWGN BER Family v0.1 ===
[Param] n_sym        = 100000
[Param] snr_list[dB] = [10.0, 12.0, 14.0, 16.0, 18.0, 20.0]
[Param] M_list       = [2, 4, 8, 16]
[Param] seed         = 1
------------------------------------------------------------
  SNR_dB       BER_M2       BER_M4       BER_M8      BER_M16
------------------------------------------------------------
    10.0    0.000e+00    1.095e-03    5.008e-02    1.793e-01
    12.0    0.000e+00    3.500e-05    1.811e-02    1.263e-01
    14.0    0.000e+00    0.000e+00    4.107e-03    7.825e-02
    16.0    0.000e+00    0.000e+00    4.033e-04    3.897e-02
    18.0    0.000e+00    0.000e+00    0.000e+00    1.297e-02
    20.0    0.000e+00    0.000e+00    0.000e+00    2.750e-03
------------------------------------------------------------
※ 주석
 - Es = 1 (unit circle) 기준 AWGN-only M-PSK BER 비교용 베이스라인.
 - SNR 인자는 Es/N0(dB)로 해석.
 - M=16은 CoPBit 4bit와 동일한 16포인트 등각 간격 위상 구조(단, 비트 라벨은 단순 binary).
 - 이후 필요 시 Eb/N0 변환, 채널(a/b/c) + EQ, CoPBit 특수 맵핑(Q1)으로 확장 가능.

 일단 CoPBit 철학 기준으로 대략 이렇게 정리 가능:
	•	M=2 (BPSK):
	•	NRZ/단일 bit 스트림, 최강의 robustness가 필요한 control/보안 채널
	•	M=4 (QPSK ≈ 2bit/심볼):
	•	“PAM4를 위상으로 바꾼 버전” 같은 포지션
	•	2bit/심볼이 필요하면서도, BER·전력·AFE 난이도에서 이득을 노릴 때
	•	M=8 (3bit/심볼):
	•	2bit payload + 1bit guard/coding
	•	혹은 3bit 풀 payload에서 고효율 모드 등
→ PAM4급 throughput에서 FEC/guard를 얹어 이득을 노리는 sweet spot 후보
	•	M=16 (4bit/심볼 = 지금 한 CoPBit 4bit):
	•	HBM/고속 IO에서 “4bit/심볼, 멀티-lane, Kuramoto, guard, FEC”까지 다 넣는 풀스펙 모드
	•	여기서는 단일 lane이 아니라 1024 lane 스케일에서의 병렬 이득이 핵심.
