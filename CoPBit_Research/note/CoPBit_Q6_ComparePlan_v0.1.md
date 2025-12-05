# CoPBit Q6 – PAM4 / ILC3 / CoPBit 4bit 비교 계획 v0.1

## 1. 목적

- 동일 채널 / 동일 EQ 조건에서
  - **PAM4**
  - **ILC3 (0c / guard phase 기반)**
  - **CoPBit 4bit phase-only (16-point)**
- 의 pre-FEC BER vs SNR 특성을 비교한다.
- 목표:
  - FEC 임계(pre-FEC BER ≤ 1e-2) 기준에서
    각 스킴의 **필요 SNR(dB)** 를 정량적으로 비교.
  - CoPBit가 PAM4 / ILC3 대비 어떤 포지션에 있는지 1차 감을 잡는다.

## 2. 채널 / 노이즈 환경

- 채널 모델: ILC3에서 사용한 3가지 ISI 채널 재사용
  - 채널 a: 가장 깨끗한 ISI (약한 ISI)
  - 채널 b: 가장 강한 ISI
  - 채널 c: 중간 수준 ISI
- 노이즈: AWGN
- 샘플 구조:
  - 심볼 수: `n_sym = 100k ~ 200k` (SNR 낮은 구간은 200k까지)
  - SNR 범위: 예) `SNR_dB = [10, 12, 14, 16, 18, 20]`  
    (필요하면 각 스킴별로 구간 조정)

## 3. 모뎀 구조

### 3.1 PAM4

- 맵핑: 심플 Gray 또는 기존 ILC3에서 사용하던 PAM4 맵핑
- 송신/수신:
  - TX: 4레벨 베이스밴드
  - 채널: a/b/c + AWGN
  - RX: 선형 FFE + slicer
- Equalizer:
  - 길이: 예) `L = 11` 탭
  - 학습 방식: 기존 ILC3 실험과 동일 (LMS / RLS / ridge 기반 등)

### 3.2 ILC3

- ILC3_0c / guard phase 기반 3레벨 스킴
- 기존 ILC3 실험에서 사용한 Rx 구조를 그대로 사용:
  - FFT / PLL / Kuramoto / FFE 등 포함된 세트
- 채널/노이즈 조건은 PAM4와 동일 (a/b/c + AWGN)

### 3.3 CoPBit 4bit (16-point phase-only)

- Constellation:
  - Q1에서 정의한 16-point phase 맵핑
- TX:
  - 4bit → 16-phase → 복소 심볼 송신
- 채널:
  - a/b/c 채널을 complex 도메인에 맞게 확장  
    (예: 실수 채널 계수를 complex 심볼의 I/Q에 동일하게 적용)
- RX:
  - 선형 FFE (complex 계수)
  - 위상 추출 후 최근접 phase 디코딩
  - (Kuramoto-aided 구조는 Q6B 이후로 확장 예정)

## 4. 실험 구성

- 공통 파라미터:
  - `n_sym = 100k` (필요 시 200k)
  - `SNR_dB = 10~20 dB 범위에서 2 dB 간격`
- 각 스킴별로 다음 값을 계산:
  - `acc` (symbol accuracy)
  - `ber` (bit error rate, pre-FEC)
- 결과는 JSON/CSV로 저장:
  - 예: `CoPBit_Research/data/q6_compare_{scheme}_chan{a/b/c}.json`

## 5. 결과 정리 계획

- 각 채널(a/b/c)에 대해:
  - `BER vs SNR` 그래프 1장씩
  - 곡선: PAM4 / ILC3 / CoPBit 4bit
  - FEC threshold line (BER = 1e-2) 표시
- 텍스트 요약:
  - 각 채널/스킴 별로
    - pre-FEC BER ≤ 1e-2 만족하는 최소 SNR (있다면) 정리
  - CoPBit가 어느 정도 SNR 영역에서 경쟁 가능한지 한 줄 요약

## 6. 구현 파일 계획

- Python:
  - `python/copbit_q6_compare_modems_v0.py`
    - 입력: `scheme = ["pam4", "ilc3", "copbit4"]`, `channel = "a"|"b"|"c"`
    - 출력: JSON with SNR–BER list
- 노트:
  - `note/CoPBit_Q6_Compare_Results_v0.1.md`
    - 실험 조건 요약 + 표/그래프 캡션 + 코멘트

# CoPBit Q6 – PAM4 / CoPBit4 AWGN BER Compare (v0.1) 메모

## 1. 실험 조건

- 스크립트: `copbit_q6_compare_modems_v0.py`
- 모드:
  - `pam4`: 2bit/심볼 4-PAM (Gray 매핑)
  - `copbit4`: 4bit/심볼 16-point 위상 모뎀 (16-PSK 스타일)
- 채널: AWGN-only (채널 a/b/c, ISI, FFE/EQ 없음)
- 공통 조건:
  - `n_sym = 100000`
  - `snr_list = [10,12,14,16,18,20]` dB
  - Es 기준으로 SNR 정의 (각 scheme에서 평균 심볼 에너지 동일)

## 2. 주요 결과

```text
SNR_dB |  BER_pam4   |  BER_copbit4
--------------------------------------
 10.0  |  5.887e-02  |  1.784e-01
 12.0  |  2.824e-02  |  1.271e-01
 14.0  |  9.470e-03  |  7.871e-02
 16.0  |  1.760e-03  |  3.804e-02
 18.0  |  1.500e-04  |  1.346e-02
 20.0  |  0.000e+00  |  2.628e-03

 	•	같은 Es/N0에서, 전 구간에서 BER_pam4 < BER_copbit4 로 관측됨.

3. 해석 포인트
	1.	심볼당 비트 수 차이 (2bit vs 4bit)
	•	PAM4: 2bit/심볼
	•	CoPBit4: 4bit/심볼
	•	같은 Es/N0에서, Eb/N0는
[
\frac{E_b}{N_0} = \frac{E_s}{k N_0}
]
로 정의되므로, k=4인 CoPBit4는 k=2인 PAM4에 비해
Eb/N0가 2배 낮음(약 −3 dB 페널티).
	2.	위상-only 16-PSK 구조의 거리 손해
	•	4-PAM은 1D에서 레벨 간 최소 거리 (d_{\min}=2)를 가짐.
	•	16-PSK는 unit circle 위에 촘촘히 배치되어, 같은 Es 조건에서
인접 위상 간 거리/각도 간격이 좁아 BER 면에서 불리함.
	•	이론적으로도 Es/N0 동일 조건에서 4-PAM vs 16-PSK 비교 시,
16-PSK의 BER가 더 나쁜 것이 자연스러운 결과임.
	3.	현재 Q6-v0.1이 의미하는 바
	•	“AWGN-only, Es/N0 동일, Kuramoto/tracking 없음”이라는 베이스라인에서는
CoPBit 4bit phase-only 스킴이 PAM4보다 BER이 불리하다는 것을 확인한 단계.
	•	이는 CoPBit 개념의 문제가 아니라,
아직 ‘CoPBit의 장점이 드러나는 채널/조건’을 반영하지 않은 초기 비교라는 점이 중요함.
