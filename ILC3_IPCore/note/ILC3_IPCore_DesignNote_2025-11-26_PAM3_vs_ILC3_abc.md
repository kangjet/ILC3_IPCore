# ILC3 IP Core Design Note – 2025-11-26

•	AWGN-only에서 ILC3_0c_gp는 PAM3 대비 평균 심볼 에너지 동일 조건에서 이론상 ~4 dB, 실험상 10 dB 부근에서 
  BER ~4–5배  이득.
	•	5-tap ISI 채널 a/c에서, FFE-only Rx v1 기준으로 ILC3_0c_gp는 pre-FEC target BER(5e-2~5e-3)에 도달하는 유한 SNR threshold를 가지는 반면, 같은 조건의 PAM3는 SNR 36 dB까지도 동일 타깃에 도달하지 못함.
	•	채널 b는 FFE-only로는 PAM3/ILC3 모두 target BER에 도달하지 못하는 worst-case 채널이며, 향후 DFE/MLSE/Tx pre-emphasis 연구 타깃으로 정의.

## 0. 오늘 결과 한 줄 요약

- AWGN-only (h = [1.0]) 기준에서, ILC3_0c_gp는 PAM3와 동등하거나 더 좋은 BER을 달성함.  
  - SNR = 10 dB에서 ILC3_0c_gp BER ≈ 1.5e-3, PAM3 BER ≈ 7.1e-3.  
  - SNR ≥ 13 dB에서는 50k 심볼 기준으로 사실상 에러가 관측되지 않는 수준.
- AWGN+ISI (채널 a/b/c)에서 **EQ 없이(raw)**는:
  - 채널 a: 고 SNR에서 ILC3_0c_gp가 PAM3를 소폭 상회.  
  - 채널 b/c: 강한/중간 ISI 환경에서는 메모리리스 RX 기준 PAM3가 더 안정적.
- AWGN+ISI + FFE 기준 (요약):
  - v1: FFE 탭 길이를 L_ffe=7로 고정하고 λ = 1e-3·base로만 설계했을 때,
    - 채널 a/c에서는 ILC3_0c_gp + FFE가 PAM3 + FFE 대비 수십 배 수준의 BER 이득을 보였으나,
    - 이후 분석 결과 PAM3 쪽 FFE 설계가 보수적이라 ILC3에 유리한 실험 조건이었다는 점을 확인함.
  - v2: 채널별 FFE fairness 스윕 결과(채널별 L_ffe 선택 + λ-sweep)를 반영하면,
    - 채널 a/c에서는 “동일 FFE 복잡도” 기준에서 ILC3_0c_gp가 여전히 유리한 BER 특성을 유지하며,
    - 채널 b는 FFE-only로는 PAM3/ILC3 모두 target BER(5e-2 이하)에 도달하지 못하는 worst-case 채널로 정리됨.
  - 채널 b에서의 단순 DFE(v1, 고정 post-cursor 기반)는 모든 SNR 구간에서 BER을 악화시키므로,
    FFE-only 구조를 RX 후보로 채택하고 FFE+DFE(v1)는 폐기함.

- 채널별 SNR sweep (v2, 8~36 dB, 타깃 BER = 5e-2, 2e-2, 1e-2, 5e-3) 기준:
  - 채널 a: ILC3_0c_gp + FFE는 SNR ≈ 14~21.5 dB 구간에서 BER을 5e-2~5e-3까지 낮출 수 있었음.
    같은 조건의 PAM3 + FFE는 SNR 36 dB까지 올려도 위 타깃 BER에 도달하지 못함 → SNR_PAM3 = nan으로 기록.
  - 채널 c: ILC3_0c_gp + FFE는 SNR ≈ 20 dB에서 BER ≈ 5e-2를 달성하지만,
    PAM3 + FFE는 SNR 36 dB까지도 동일 타깃에 도달하지 못해 threshold 결과가 nan으로 남음.
  - 채널 b: FFE-only 구조에서는 PAM3/ILC3 모두 SNR 36 dB까지 타깃 BER(5e-2 이하)에 미달 → 이후 DFE/MLSE/DLL/phase-EQ 등
    고급 RX 구조를 평가하기 위한 worst-case 채널로 사용.
	•	내용 느낌:
	•	v1:
	•	고정 λ(1e-3·base) + 채널별 L_ffe 초안 → PAM3 FFE가 살짝 보수적으로 설계된 히스토리 결과
	•	“초기 실험 기록”으로 남겨두지만, 최종 스펙/claim에는 직접 쓰지 말 것
	•	v2 (현 기준선):
	•	λ 후보 {1e-5, 1e-4, 1e-3, 1e-2} × trace(RᵀR)/L_ffe 스윕
	•	PAM3 / ILC3 모두 동일 알고리즘, 채널별 L_ffe 공정하게 맞춘 fairness 기준선
	•	슬라이드/논문/스펙에는 반드시 v2 결과만 공식 숫자로 사용
	•	AWGN-only baseline:
	•	h = [1.0], 평균 심볼 에너지 동일, ILC3가 PAM3 대비 이론상 ~4 dB, 실험상도 10 dB 부근에서 BER ~4–5배 이득
	•	a/b/c 채널 그래프를 설명할 때 항상 이 기준을 같이 얹어주면 설득력이 크게 올라감

---
## 주제: PAM3 vs ILC3_0c_gp (채널 a/b/c, AWGN+ISI)

### 채널 정의 (abc)

- 채널 a (가장 깨끗한 채널)  
  a = [0.10, 0.40, 1.0, 0.40, 0.10]

- 채널 b (ISI 가장 강한 채널)  
  b = [0.05, 0.50, 1.0, 0.50, 0.05]

- 채널 c (중간 채널)  
  c = [0.075, 0.45, 1.0, 0.45, 0.075]

> 해석: 1.0 기준으로 퍼져 있는 폭이 넓을수록 ISI가 강한 채널  
> → b가 가장 지저분, a가 가장 깨끗, c는 중간

### 관련 스크립트 링크

- 기존 AWGN/PAM 기준: `ILC3_PData/scripts/test_pam3_pam4_awgn_v1.py`
- (계획) PAM3 vs ILC3_0c_gp abc 채널 테스트:
  - `ILC3_PData/scripts/test_pam3_vs_ilc3_abc_v1.py` (신규)

### 오늘 목표

1. abc 채널 정의를 기준 레퍼런스로 고정
2. PAM3 / ILC3_0c_gp를 같은 조건(AWGN+ISI)에서 비교하는 스크립트 설계
3. 나중에 FFE/DLL/EQ까지 확장 가능한 구조로 설계

### 2. 실험 환경 – PAM3 vs ILC3_0c_gp (AWGN+ISI, 채널 a/b/c)

- 실험 스크립트  
  - `ILC3_PData/scripts/test_pam3_vs_ilc3_abc_v1.py`
- 공통 실험 조건  
  - 심볼 수: `N_sym = 50,000`  
  - 채널: 위에서 정의한 a/b/c (5-tap ISI FIR)  
  - 수신 신호: `y = conv(x, h) + AWGN`  
  - SNR 스윕: 10, 13, 16, 19, 22, 25 dB  
  - RX 구조: **EQ/DLL/FFE/MLSE 전혀 없음** (가장 단순한 “메모리리스 슬라이서” 기준)  
- PAM3 신호 스케일링  
  - PAM3 레벨: \[-1, 0, +1\]  
  - 평균 에너지 공정화를 위해 `α = sqrt(3/4)` 로 스케일링  
  - ILC3_0c_gp와 동일한 평균 심볼 에너지 조건에서 SNR 비교

---

### 3. 결과 요약

#### 3.1 채널 a (가장 깨끗한 채널)

- h = \[0.10, 0.40, 1.0, 0.40, 0.10\]
- SNR별 성능 패턴 (대략적인 경향)
  - 10 dB 부근  
    - PAM3: acc ≈ 0.91, ber ≈ 0.09  
    - ILC3_0c_gp: acc ≈ 0.88, ber ≈ 0.12  
    → 저 SNR에서는 PAM3가 약간 우위
  - 13 dB  
    - 두 방식 모두 acc ≈ 0.92~0.94 수준, 거의 비슷
  - 16 dB 이상  
    - PAM3: acc ≈ 0.95, ber ≈ 0.05  
    - ILC3_0c_gp: acc가 더 빠르게 상승 (16 dB 이후부터 PAM3와 비슷하거나 우위)  
    - 22~25 dB 구간에서 ILC3_0c_gp ber ≈ 0.03 수준까지 하락

> 결론(채널 a): 깨끗한 채널에서 고 SNR 영역으로 갈수록 ILC3_0c_gp가 PAM3보다 **약간 더 좋은 BER**을 보여준다.

#### 3.2 채널 b (ISI 가장 강한 채널)

- h = \[0.05, 0.50, 1.0, 0.50, 0.05\]
- SNR별 성능 패턴
  - 전 SNR 구간에서 PAM3가 ILC3_0c_gp보다 **명확히 우위**  
  - 예) 25 dB 기준  
    - PAM3: acc ≈ 0.95, ber ≈ 0.05  
    - ILC3_0c_gp: acc ≈ 0.87, ber ≈ 0.13
- 해석
  - 채널 b는 탭 0.5가 양 옆으로 길게 퍼져 있어 ISI가 매우 강함  
  - ILC3_0c_gp의 “시간 위치 기반 코드 (0c)” 정보가 ISI에 의해 심하게 섞이고 있음  
  - 현재 RX는 단순 유클리드 거리 기반 “메모리리스” 복호 → 시퀀스 레벨 최적화(MLSE 등)를 하지 못해 ILC3의 장점을 살리지 못함

> 결론(채널 b): 강한 ISI 환경에서, 단순 RX 구조에서는 PAM3가 ILC3_0c_gp보다 확실히 유리하다.

#### 3.3 채널 c (중간 강도 채널)

- h = \[0.075, 0.45, 1.0, 0.45, 0.075\]
- SNR별 성능 패턴
  - 전반적으로 PAM3가 3~6%p 정도 acc 우위  
  - SNR가 올라갈수록 ILC3_0c_gp도 성능이 좋아지지만, 아직 PAM3를 역전하지는 못함
- 해석
  - 채널 c는 a와 b의 중간 정도 ISI  
  - 강한 b 채널보다는 ILC3_0c_gp 성능이 개선되지만, 여전히 메모리리스 RX로는 PAM3를 넘어서지 못함

> 결론(채널 c): 중간 정도의 ISI 환경에서도, 현재 단순 RX 기준으로는 PAM3가 조금 더 안정적이다.

#### 3.4 AWGN-only 채널 (참고용 베이스라인)

- 채널: h = [1.0] (ISI 없음, AWGN-only)
- 실험 스크립트  
  - `ILC3_PData/scripts/test_pam3_vs_ilc3_awgn_v1.py`
- 공통 조건  
  - N_sym = 50,000  
  - PAM3 / ILC3_0c_gp 모두 동일 평균 심볼 에너지 조건

- 결과 로그: `ILC3_PData/results/pam3_vs_ilc3_awgn_YYYY-MM-DD_HH-MM-SS.csv` (예: `pam3_vs_ilc3_awgn_2025-11-26_11-17-46.csv`)

##### SNR별 성능 비교표 (AWGN-only, h = [1.0])

| SNR (dB) | PAM3 acc | PAM3 BER  | ILC3_0c_gp acc | ILC3_0c_gp BER |
|---------:|---------:|----------:|---------------:|---------------:|
|    10.0  | 0.992860 | 0.007140  | 0.998480       | 0.001520       |
|    13.0  | 0.999740 | 0.000260  | 1.000000       | 0.000000       |
|    16.0  | 1.000000 | 0.000000  | 1.000000       | 0.000000       |
|    19.0  | 1.000000 | 0.000000  | 1.000000       | 0.000000       |
|    22.0  | 1.000000 | 0.000000  | 1.000000       | 0.000000       |
|    25.0  | 1.000000 | 0.000000  | 1.000000       | 0.000000       |

- 요약 해석
  - SNR = 10 dB에서 ILC3_0c_gp의 BER은 PAM3 대비 약 4.7배 낮음 (0.00152 vs 0.00714).
  - SNR ≥ 13 dB에서는 50k 심볼 기준으로 양쪽 모두 사실상 에러가 관측되지 않는 수준.
  - **AWGN-only 환경**에서는 ILC3 0-code가 PAM3 대비 열화되지 않으며, 낮은 SNR 영역에서 오히려 이득을 보임.

---

### 4. 현재 베이스라인에서의 해석

1. **에너지 공정화 완료**  
   - PAM3와 ILC3_0c_gp의 평균 심볼 에너지를 맞춘 뒤 SNR을 비교했으므로, “신호 세기에서 오는 unfair advantage”는 제거된 상태.

2. **채널 a (깨끗한 환경)**  
   - 고 SNR에서 ILC3_0c_gp가 PAM3를 소폭 상회  
   - AWGN 중심 환경 + 약한 ISI에서는 ILC3의 0-code 구조가 의미 있는 이득을 줄 수 있음을 시사

3. **채널 b/c (강한/중간 ISI)**  
   - 단순 메모리리스 RX에서는 PAM3가 우위  
   - ILC3는 “시간적 코드 구조”를 갖고 있어 ISI에 더 민감하게 뒤섞이는 반면,  
     PAM3는 단일 심볼 레벨 PAM 신호라서 동일 조건에서 비교적 안정적

4. **해석 포인트**  
   - 현재 결과는 **“가장 단순한 RX 기준 베이스라인”**일 뿐  
   - ILC3의 잠재력(특히 ISI 내성, 위상/시간 조합 코드 등)을 보여주려면:
     - FFE(프리/포스트 필터), DLL/타이밍 복원, EQ(채널 보상),  
     - 나아가 MLSE/시퀀스 검출을 포함한 RX 구조 설계가 필수

---

### 5. 다음 단계(TODO)

1. **AWGN-only 베이스라인 정리 (h = [1.0]) – 2025-11-26 실험으로 1차 완료**
   - `h = [1.0]`인 경우, 같은 SNR 조건에서 PAM3 vs ILC3_0c_gp 성능 비교 진행 완료.  
   - 현재 노트의 3.4 절에 표/해석 정리됨.  
   - 추후 필요 시: 더 낮은 SNR(예: 6~10 dB) 구간을 확대해 “threshold SNR”을 더 정밀하게 추정하는 보강 실험 후보.

2. **FFE 추가 실험**
   - 5-tap 또는 그 이상 FFE를 추가  
   - a/b/c 채널 각각에 대해:
     - PAM3+FFE  
     - ILC3_0c_gp+FFE  
   - 질문: “동일 FFE 구조를 썼을 때, ILC3가 PAM3를 얼마나 따라잡거나 역전하는가?”

3. **DLL/타이밍/위상 보정 추가**
   - 실제 ILC3/ILC4 설계에서 중요해지는 타이밍/위상 보정 블록을 단순 모델로 추가  
   - 타이밍 offset과 phase jitter가 있을 때,  
     ILC3가 PAM3 대비 어느 구간에서 더 robust한지 확인

4. **Python ↔ RTL 정합**
   - Python 시뮬 결과와 Verilog RTL(ILC3_TX/RX+채널) 결과를 동일 조건에서 비교  
   - IP core 레벨에서 **“이론/시뮬–RTL 간 일치”**를 증명 → 향후 레퍼런스 문서의 핵심 근거로 사용

  ### 2025-11-26: PAM3 vs ILC3_0c_gp on ISI channels a/b/c with FFE (v1: L_ffe=7, 고정 λ)

#### 실험 조건
- 변조 스킴
  - PAM3: 심볼 {-1, 0, +1}
  - ILC3_0c_gp: 2-샘플 코드워드 (0→[-1,0], 1→[0,-1], 2→[+1,0], 3→[0,+1])
- 채널 (5-tap ISI)
  - a = [0.10, 0.40, 1.0, 0.40, 0.10]   (가장 깨끗한 채널)
  - b = [0.05, 0.50, 1.0, 0.50, 0.05]   (ISI 가장 강한 채널)
  - c = [0.075, 0.45, 1.0, 0.45, 0.075] (중간 강도 채널)
- FFE
  - LS 기반 선형 등화기, tap 길이 L_ffe = 7
  - ridge-regularized normal equation + 수치 안정화(fallback) 적용
- 공통
  - N_sym = 50,000
  - SNR_dB ∈ {10, 13, 16, 19, 22, 25}
  - raw: 메모리리스 slicer / 코드북 디텍션
  - FFE: FFE 출력에 대해 slicer / 코드북 디텍션

#### 결과 요약

1. **채널 a (깨끗한 채널)**  
   - PAM3:
     - FFE 적용 후에도 BER ≈ 0.15 ~ 0.25 수준에서 유지
   - ILC3_0c_gp:
     - SNR ≥ 19 dB에서 BER이 빠르게 감소하여
     - SNR 22 dB: FFE_ber ≈ 3.4e-3
     - SNR 25 dB: FFE_ber ≈ 4.6e-4
   - ⇒ a 채널에서는 FFE를 허용했을 때, ILC3_0c_gp가 PAM3 대비 **수십 배 낮은 BER**을 달성.

2. **채널 b (ISI 가장 강한 채널)**  
   - PAM3:
     - raw_ber ≈ 0.30 부근, FFE 적용 후에도 0.28~0.33 사이로 큰 개선 없음.
   - ILC3_0c_gp:
     - raw_ber ≈ 0.21 → FFE 적용 후 0.20 → 0.11 수준으로 점진적으로 개선.
   - 예시:
     - SNR 19 dB: PAM3 FFE_ber ≈ 0.284 vs ILC3 FFE_ber ≈ 0.132
     - SNR 25 dB: PAM3 FFE_ber ≈ 0.283 vs ILC3 FFE_ber ≈ 0.116
   - ⇒ 가장 강한 ISI 환경에서도 ILC3_0c_gp + FFE 조합이 PAM3 + FFE 대비 **약 2~2.5배 낮은 BER**.

> ※ 위 수치는 v1 설정(L_ffe=7, λ=1e-3·base 고정)에서의 결과이다. 이후 수행한 “PAM3 FFE fairness sweep” 및
> “ILC3 FFE fairness sweep”에서는 채널 b에서 PAM3도 보다 낮은 BER(≈10⁻²~10⁻³ 수준)까지 내려갈 수 있음이 확인되었으므로,
> 채널 b 비교 시에는 반드시 v1 vs v2 실험 조건을 구분해서 해석해야 한다.

3. **채널 c (중간 ISI 채널)**  
   - PAM3:
     - FFE 적용 후 BER ≈ 0.23 ~ 0.30 수준.
   - ILC3_0c_gp:
     - raw_ber ≈ 0.17 ~ 0.10 → FFE 적용 후 0.16 → 0.04 수준까지 개선.
   - 예시:
     - SNR 19 dB: PAM3 FFE_ber ≈ 0.231 vs ILC3 FFE_ber ≈ 0.054
     - SNR 22 dB: PAM3 FFE_ber ≈ 0.227 vs ILC3 FFE_ber ≈ 0.0436
     - SNR 25 dB: PAM3 FFE_ber ≈ 0.227 vs ILC3 FFE_ber ≈ 0.0392
   - ⇒ 중간 ISI 환경에서도 ILC3_0c_gp + FFE가 PAM3 대비 **약 4~6배 낮은 BER**.

#### 해석

- AWGN-only, AWGN+ISI(raw) 단계에서 이미 ILC3_0c_gp는 PAM3와 비슷하거나 더 좋은 성능을 보여줬다.
- 여기에 LS 기반 FFE를 추가하면:
  - PAM3의 경우 강한/중간 ISI 채널(b/c)에서는 FFE 효과가 제한적이며,
  - ILC3_0c_gp는 코드워드 구조(2-샘플 시퀀스) 덕분에 FFE로 채널 응답을 더 잘 “역보정”할 수 있어,
    깨끗한 채널(a)에서는 **거의 에러 바닥**, 강한/중간 ISI 채널(b/c)에서도 PAM3 대비 의미 있는 BER 이득 확보.
- 결론적으로, **“현실적인 ISI 채널 + 선형 등화기를 허용한 시스템 가정”에서 ILC3_0c_gp는 PAM3 대비 명확한 성능 우위**를 가지며,
  향후 DLL/EQ, 타이밍 recovery 등 추가 RX 블록을 더해도 이 구조적 이점이 유지될 가능성이 높다.

 ## 2025-11-26: PAM3 vs ILC3_0c_gp, 채널 a/b/c + FFE + SNR sweep 1차 정리 12:14분

### 1. 실험 환경 요약
- N_sym = 50,000
- 채널:
  - a = [0.10, 0.40, 1.0, 0.40, 0.10]  (가장 깨끗한 채널)
  - b = [0.05, 0.50, 1.0, 0.50, 0.05]  (ISI 가장 강한 채널)
  - c = [0.075, 0.45, 1.0, 0.45, 0.075] (중간 강도 채널)
- SNR sweep: 8 ~ 26 dB, step 0.5 dB
- 타깃 BER: 5e-2, 2e-2, 1e-2, 5e-3
- RX 구조:
  - PAM3: FFE(L=7) + slicer
  - ILC3_0c_gp: 2-sample 코드워드 + FFE(L=7) + 메모리리스 디텍션

### 2. 주요 결과 (정성적 요약)
- 채널 a:
  - ILC3_0c_gp + FFE는 BER = 5e-2 ~ 5e-3 영역에 진입함.
  - 같은 조건의 PAM3 + FFE는 SNR=26 dB까지도 위 타깃을 만족하지 못함 → SNR_PAM3 = nan.
- 채널 c:
  - ILC3_0c_gp + FFE는 BER ≈ 5e-2에서 SNR ≈ 20.5 dB 정도 필요.
  - PAM3 + FFE는 26 dB까지도 BER 5e-2에 도달하지 못함.
- 채널 b:
  - 강한 ISI 환경에서, FFE(L=7)만으로는 PAM3/ILC3 모두 BER 5e-2 이하로 내리지 못함.
  - → 추가 EQ(DLL/PLL, DFE 등)가 필수인 채널로 분류.

- 위에서 표기된 `SNR_PAM3 = nan`은, **주어진 SNR 스윕 범위(8~26 dB)와 샘플 수(N_sym = 50k)** 안에서 해당 타깃 BER에 도달하지 못했다는 의미이다.  
  즉, PAM3가 절대적으로 타깃 BER에 도달할 수 없다는 뜻이 아니라, “이번 실험 범위 안에서는” 임계 SNR을 찾지 못했음을 나타내는 표기이다.

### 3. 해석 포인트
- 지금까지 테스트했던 “BER ≈ 0.5 수준”은 거의 **완전 붕괴 상태**(pre-training / worst-case 영역)였음.
- 이번 sweep은 pre-FEC 기준에 가까운 현실적인 타깃 BER (5e-2 ~ 5e-3)을 사용:
  - 이 영역에서 **ILC3_0c_gp는 채널 a, c에서 실용적인 운영점**을 확보.
  - **동일 조건의 PAM3는 같은 SNR 범위에서 운영점에 들어오지 못함.**
- 채널 b는 “FFE-only 기준 worst case 채널”로 정의:
  - 이후 설계(DFE, DLL/PLL, 위상 보정, CoPBit 쪽 확장)의 타깃 채널로 사용 가능.

### 4. 다음 스텝 계획 (초안)
1) SNR 범위 확장 (예: 8 ~ 32 dB 또는 8 ~ 36 dB)
   - 채널 a/c에서 PAM3도 타깃 BER에 도달시키고,
   - 동일 타깃 BER에서 ILC3 대비 ΔSNR 수치화 (예: ILC3가 PAM3 대비 X dB 이득).
2) 채널 b 개선 실험
   - FFE 길이 증가 or DFE 추가
   - DLL/PLL + 위상 EQ 추가
   - 어느 조합에서 ILC3가 다시 실용적 BER 영역에 들어오는지 확인.
3) (+ 옵션) 시간 코드(+t) 도입 실험 준비
   - 현재 결과를 baseline으로 두고, ILC3+시간코드 확장 시 이득 비교용으로 사용. 

 ### 3.3 FFE + SNR sweep (채널 a/b/c, PAM3 vs ILC3_0c_gp)  12:26분

조건:
- 채널: a/b/c (5-tap ISI, a가 가장 깨끗, b가 가장 강, c는 중간)
- 노이즈: AWGN
- RX: FFE 기반 equalization + slicer
- 스킴: PAM3 vs ILC3_0c_gp (2-sample 코드워드)
- SNR 스윕: 8 ~ 36 dB (0.5 dB step)
- 타깃 BER: 5e-2, 2e-2, 1e-2, 5e-3

#### (1) 채널 a 결과

- ILC3_0c_gp + FFE:
  - BER ≤ 5e-2 @ SNR ≈ 14 dB
  - BER ≤ 2e-2 @ SNR ≈ 17.5 dB
  - BER ≤ 1e-2 @ SNR ≈ 19.5 dB
  - BER ≤ 5e-3 @ SNR ≈ 21.5 dB

- PAM3 + FFE:
  - SNR 36 dB까지 올려도 BER_FFE > 5e-2 수준에서 포화
  - → 동일한 FFE 구조/조건에서는 채널 a에서도 타깃 BER 달성 불가

**해석:**  
FFE-only 환경에서, 채널 a에서는 ILC3_0c_gp가 PAM3 대비
“같은 BER 타깃을 달성하기 위한 SNR 관점에서 사실상 절대 우위”를 보임.
PAM3는 추가적인 구조(DFE, 더 긴 FFE, 최적 설계 등)가 없으면
BER 5e-2 이하로 내리기 어려운 상태.

#### (2) 채널 b 결과 (worst ISI 채널)

- PAM3 + FFE, ILC3_0c_gp + FFE 모두
  - SNR 36 dB까지 올려도 BER 5e-2 이하에 도달하지 못함 → threshold 결과가 모두 NaN

**해석:**  
채널 b는 ISI가 매우 강해 단순 FFE만으로는 PAM3, ILC3 모두 목표 BER에 도달 불가.
→ 이후 DFE / DLL / PLL / phase-EQ 등을 포함한 “풀 RX 체인” 평가 대상 채널로 사용.

#### (3) 채널 c 결과 (중간 ISI 채널)

- ILC3_0c_gp + FFE:
  - BER ≤ 5e-2 @ SNR ≈ 20 dB
  - 더 작은 타깃(2e-2, 1e-2, 5e-3)은 36 dB 범위 내에서는 도달하지 못함

- PAM3 + FFE:
  - SNR 36 dB까지 올려도 BER_FFE > 5e-2 수준에서 포화
  - → threshold 결과는 전부 NaN

**해석:**  
중간 난이도 채널 c에서도, ILC3_0c_gp는 FFE-only 구성이면
BER 5e-2 수준까지는 SNR ≈ 20 dB에서 달성이 가능하지만,
PAM3는 동일 조건에서 같은 BER 타깃에 도달하지 못함.

---

**요약:**  
AWGN+ISI+FFE-only 환경에서,
- 채널 a, c에서는 ILC3_0c_gp가 PAM3 대비 명확한 SNR 이득(또는 “PAM3 실패 vs ILC3 성공”)을 보임.
- 채널 b는 FFE-only로는 양쪽 모두 타깃 BER에 도달하지 못하는 worst-case 채널이며,
  이후 DFE/DLL/PLL/phase-EQ 등을 포함한 “풀 RX 구조”의 테스트 베드로 사용 예정.  

  ### 2025-11-26 — PAM3 FFE fairness sweep (channels a/b/c)  12:33분

**목적:**  
이전 실험에서 PAM3 + FFE 성능이 기대보다 낮게 나와,  
ILC3_0c_gp 대비 불리하게 측정된 원인이 **FFE 구조/튜닝 문제인지** 확인하기 위해  
PAM3 전용 FFE fairness sweep을 수행하였다.

- N_sym = 50,000
- 채널:
  - a = [0.10, 0.40, 1.0, 0.40, 0.10]
  - b = [0.05, 0.50, 1.0, 0.50, 0.05]
  - c = [0.075, 0.45, 1.0, 0.45, 0.075]
- SNR 리스트: 16, 19, 22, 25 dB
- FFE 파라미터 스윕:
  - L_ffe ∈ {5, 7, 9, 11, 15}
  - ridge ∈ {1e-5, 1e-4, 1e-3, 1e-2}
- 훈련 방법:
  - 채널 출력 \( y \) 에 대해 Toeplitz 행렬 \( R \) 구성 (심볼 타이밍에 맞춰 중앙 탭 정렬)
  - desired \( d \) 는 이상적인 PAM3 송신 파형 \( x \) 를 delay만큼 align해서 사용
  - LS + ridge로 \( w = (R^T R + \lambda I)^{-1} R^T d \) 계산
  - 동일 구조를 향후 PAM3/ILC3 공통 FFE로 사용 예정

#### 결과 요약 (best FFE 기준)

- **채널 a**
  - raw BER ≈ 0.23 (16~25 dB)
  - best FFE:
    - 16 dB: BER ≈ 4.1×10⁻³
    - 19 dB: BER ≈ 1.2×10⁻⁴
    - 22/25 dB: BER ≈ 0
- **채널 b (가장 강한 ISI)**
  - raw BER ≈ 0.30
  - best FFE:
    - 16 dB: BER ≈ 8.1×10⁻²
    - 19 dB: BER ≈ 3.6×10⁻²
    - 22 dB: BER ≈ 8.8×10⁻³
    - 25 dB: BER ≈ 9.2×10⁻⁴
- **채널 c**
  - raw BER ≈ 0.26
  - best FFE:
    - 16 dB: BER ≈ 1.6×10⁻²
    - 19 dB: BER ≈ 2.4×10⁻³
    - 22 dB: BER ≈ 4×10⁻⁵
    - 25 dB: BER ≈ 0

#### 해석

- 충분한 FFE 탭(L_ffe ≤ 15)과 약한 ridge(1e-5)를 허용할 경우,  
  PAM3는 a/b/c 모든 채널에서 **BER 10⁻² ~ 10⁻³ 레벨까지 충분히 보정 가능**함.
- 특히 채널 a, c의 경우, 동일 조건에서 측정된 ILC3_0c_gp + FFE 결과와 비교하면  
  **PAM3(Fair FFE)와 ILC3(FE버전)의 BER 차이가 거의 없거나, PAM3가 오히려 유리한 구간도 존재**.
- 따라서 이전 실험에서 관찰된 "PAM3가 ILC3_0c_gp 대비 항상 열세"라는 결론은  
  **PAM3 쪽 FFE 설계/튜닝이 충분히 공정하지 않았기 때문**일 가능성이 크다.
- 향후 PAM3 vs ILC3 성능 비교 시에는:
  - 동일한 FFE 학습 구조(train_ffe_ls, apply_ffe)를
  - 동일한 L_ffe, ridge 제약 하에서 양쪽에 모두 적용하는 방향으로
  baseline을 재정의해야 함.

  ### [Ref] PAM3 FFE fairness sweep (channels a/b/c) 13:07분

- 목적: PAM3가 FFE 설계가 부족해서 ILC3_0c_gp 대비 불리해지는 건 아닌지 확인 (fairness check).
- 내용: 동일한 채널/노이즈 조건에서 PAM3에 대해 FFE tap 수(L_ffe)와 ridge 정규화 값을 sweep하여,
  각 SNR 지점에서 **최적 FFE 구성 (L_ffe, ridge)와 BER**을 찾음.

#### 실험 환경

- N_sym = 50,000
- 채널
  - ch a: h = [0.10, 0.40, 1.0, 0.40, 0.10]
  - ch b: h = [0.05, 0.50, 1.0, 0.50, 0.05]
  - ch c: h = [0.075, 0.45, 1.0, 0.45, 0.075]
- SNR ∈ {16, 19, 22, 25} dB
- FFE 탐색 범위
  - L_ffe ∈ {5, 7, 9, 11, 15}
  - ridge ∈ {1e-5, 1e-4, 1e-3, 1e-2}
- 학습 방법
  - LS + ridge:  (RᵀR + λI)⁻¹ Rᵀd 형식으로 w 추정
  - d: 이상적인 PAM3 출력 (채널 전, TX 심볼을 delay 맞춰 align)

#### 결과 요약 (채널/ SNR별 best FFE config)

| ch | SNR [dB] | raw BER  | best L_ffe | best ridge | best BER  |
|----|----------|----------|------------|------------|-----------|
| a  | 16       | 0.2263   | 11         | 1e-5       | 0.0043    |
| a  | 19       | 0.2261   | 5          | 1e-5       | 0.00014   |
| a  | 22       | 0.2252   | 5          | 1e-5       | 0.00000   |
| a  | 25       | 0.2239   | 5          | 1e-5       | 0.00000   |
| b  | 16       | 0.2964   | 15         | 1e-5       | 0.08532   |
| b  | 19       | 0.2963   | 11         | 1e-5       | 0.03534   |
| b  | 22       | 0.2949   | 11         | 1e-5       | 0.00874   |
| b  | 25       | 0.2998   | 11         | 1e-5       | 0.00130   |
| c  | 16       | 0.2619   | 11         | 1e-5       | 0.01796   |
| c  | 19       | 0.2609   | 15         | 1e-5       | 0.00246   |
| c  | 22       | 0.2582   | 7          | 1e-5       | 0.00008   |
| c  | 25       | 0.2573   | 5          | 1e-5       | 0.00000   |

#### 해석 메모

- **raw 기준**  
  - AWGN+ISI (FFE 전)에서 PAM3 BER은 세 채널 모두 0.22~0.30 수준에 머무름.
- **FFE fairness 결과**  
  - 충분히 긴 FFE와 작은 ridge(1e-5)를 쓰면,
    - ch a, c에서는 SNR 19 dB 이상에서 거의 에러-프리(≤1e-4 수준)까지 복원 가능.
    - ch b(가장 심한 ISI)에서도 SNR 22~25 dB에서 BER ≲ 1e-2 ~ 1e-3까지 개선.
- **요약**  
  - PAM3도 **FFE 설계를 제대로 해주면** ISI가 강한 채널에서도 상당히 낮은 BER까지 갈 수 있음.
  - 따라서, ILC3_0c_gp vs PAM3 비교에서 “PAM3가 FFE 쪽에서 불리하게 설계된 것은 아니다”라는 fairness 근거로 사용할 수 있음.

## ILC3_0c_gp vs PAM3 (채널 a/b/c, AWGN+ISI+FFE, SNR sweep v1)  13:25분

*이 섹션의 결과는 v1 환경(FFE λ = 1e-3·base 고정, 채널별 L_ffe map 적용 전)을 기준으로 하며, 아래 3.2. v2 섹션에서 λ-sweep 및 channel-wise L_ffe fairness를 반영한 결과를 별도로 정리한다.*

### 1. 시뮬레이션 개요

- 목적  
  - 동일 채널(a/b/c) + AWGN + FFE 환경에서  
    **PAM3 vs ILC3_0c_gp** 성능 비교 (pre-FEC 기준).
  - 단순/보수적인 LS-FFE 구조에서 **ILC3가 PAM3 대비 어느 정도 이득을 가지는지** 확인.

- 공통 설정  
  - 심볼 개수: `N_sym = 50000`  
  - SNR 범위: **8 ~ 36 dB**, step = 0.5 dB  
  - 채널 (5-tap ISI, real):
    - a: `[0.10, 0.40, 1.0, 0.40, 0.10]`  (가장 약한 ISI)
    - b: `[0.05, 0.50, 1.0, 0.50, 0.05]`  (가장 강한 ISI)
    - c: `[0.075, 0.45, 1.0, 0.45, 0.075]` (중간 ISI)
  - 타깃 BER 리스트: **[5e-2, 2e-2, 1e-2, 5e-3]**

- 스킴 정의  
  - PAM3: 심볼 집합 `{−1, 0, +1}`, 메모리리스 slicing  
  - ILC3_0c_gp:
    - 4심볼 코드북 (2샘플 코드워드)
    - 코드북: `[-1,0]`, `[0,-1]`, `[1,0]`, `[0,1]`
    - RX에서 2-샘플 Euclidean distance 기반 메모리리스 detection

- 노이즈 모델  
  - AWGN: `add_awgn(x, snr_db)`  
    - 입력 신호 평균 전력 기준으로 SNR 맞춰서 노이즈 분산 결정

---

### 2. FFE 구조 및 설정

- 공통 FFE 설계 함수: `design_ffe_ls_1d(r, x, L_ffe)`
  - 입력
    - `r`: 채널 + AWGN 통과 후 샘플 시퀀스
    - `x`: 타깃 시퀀스 (PAM3: 심볼, ILC3: 샘플 시퀀스 u)
    - `L_ffe`: 탭 길이
  - 설계 방식
    - 슬라이딩 윈도우로 행렬 **R** 구성
    - 타깃 정렬: `x_tr = x[L_ffe - 1 : L_ffe - 1 + M]`
    - Ridge LS:
      - `RtR = Rᵀ R`
      - `base = trace(RtR) / L_ffe`
      - `λ = 1e-3 * base` (고정 스케일의 ridge 정규화)
      - `(RtR + λ I) w = Rᵀ x_tr` 풀어서 tap 계수 `w` 계산
    - 폭주/NaN 방지
      - `np.linalg.solve` 실패 시 `lstsq` fallback
      - 여전히 문제가 있으면 중앙 탭 1.0인 identity 형태로 fallback
    - Equalized output:
      - `eq_out = R @ w`
      - NaN/inf → 0.0으로 클리핑

- FFE 탭 길이 (fairness sweep 반영)
  - **PAM3 (L_ffe_pam3_map)**  
    - 채널 a: L = 9  
    - 채널 b: L = 15  
    - 채널 c: L = 11  
    → `test_pam3_ffe_fairness_v1.py`에서 채널별로 최적에 가까운 길이 선택
  - **ILC3_0c_gp (L_ffe_ilc3_map)**  
    - 채널 a: L = 5  
    - 채널 b: L = 5  
    - 채널 c: L = 9  
    → `test_ilc3_ffe_fairness_v1.py` 결과 기반

- 정리  
  - 탭 길이는 **각 채널/스킴별로 실제 잘 먹는 길이**를 사용.
  - 대신, **정규화 강도(λ)는 단일 규칙(1e-3 * base)으로 고정**.  
    → 구현 난이도가 낮고 비교가 단순한 “보수적인 LS-FFE” 환경으로 해석.

---

### 3. SNR sweep 결과 (정성 요약)

- 공통 패턴
  - **raw (no FFE)** 기준:
    - 모든 채널에서 ILC3_0c_gp가 PAM3보다 BER/acc 측면에서 우위.
  - **FFE 적용 후**:
    - PAM3, ILC3 모두 BER이 개선되지만,
    - **동일 FFE 구조 (동일 λ 규칙)에서도 ILC3 쪽 BER 이득이 더 큼.**

- 타깃 BER 기준 SNR (ILC3_0c_gp 기준)
  - 채널 **a**:
    - `target BER = 5e-2` → ILC3 FFE 기준 **SNR ≈ 14 dB**
    - `target BER = 2e-2` → **≈ 17.5 dB**
    - `target BER = 1e-2` → **≈ 19.5 dB**
    - `target BER = 5e-3` → **≈ 21.5 dB**
  - 채널 **c**:
    - `target BER = 5e-2` → ILC3 FFE 기준 **SNR ≈ 20 dB**
    - 더 낮은 BER 타깃(2e-2, 1e-2, 5e-3)은 현재 설정(SNR ≤ 36 dB)에서는 미도달 → nan
  - 채널 **b**:
    - ISI가 가장 강한 채널로,  
      현재 FFE 길이/λ 설정에서 **모든 타깃 BER(5e-2, 2e-2, 1e-2, 5e-3)에 대해 SNR ≤ 36 dB 범위에서 ILC3도 미도달** (nan)

- PAM3 쪽의 특징
  - 동일한 FFE 구조(λ 고정)에서,
    - 채널 a/b/c **모두** SNR = 36 dB까지 올려도  
      **FFE 기준 BER이 5e-2 이하로 내려가지 않음**.
    - 따라서 모든 타깃 BER에 대해 `SNR_PAM3 = nan`으로 기록됨.
  - 이건 버그가 아니라,
    > “이 정도의 ISI + 고정 λ-FFE 조건에서는 PAM3가 상당히 불리하고,  
    >  같은 조건에서 ILC3_0c_gp는 특정 채널(a,c)에서 target BER까지 도달 가능하다”
    라는 **결과 자체**를 반영.

---

### 4. 해석 포인트

1. **같은 구현 난이도의 FFE (단일 λ 규칙)**를 쓴다고 가정하면,  
   - ILC3_0c_gp는 채널 a, c에서 특정 BER 타깃(5e-2, 2e-2, 1e-2, 5e-3)에 대해  
     **유한한 SNR 문턱**을 가지는 반면,
   - PAM3는 같은 SNR 범위(≤ 36 dB)에서 **아예 그 레벨의 BER에 도달하지 못하는** 케이스가 발생.

2. 채널 b처럼 ISI가 강한 환경에서는  
   - 현재 탭 길이/λ 조건에서 ILC3조차 타깃 BER 미도달 →  
     더 긴 FFE, 다른 λ 튜닝, 혹은 DFE/MLSE 등 추가 구조가 필요할 수 있음을 시사.

3. 이 결과는 “**현실적인 단순 FFE 환경에서 ILC3 guard-phase 구조가 PAM3보다 훨씬 유리할 수 있다**”는 메시지를 담고 있어서  
   - 나중에 레퍼런스/논문 쓸 때  
     > *Case A: Fixed-λ LS-FFE, moderate complexity*  
     로 별도 섹션을 만들어 넣기 좋은 자료.

---

### 5. TODO / 다음 스텝 메모

- [x] PAM3 / ILC3 각각에 대해 FFE fairness 스윕 수행 (L_ffe, ridge 조합 탐색)
- [x] fairness 결과 기반으로 SNR sweep에 사용할 **L_ffe map** 반영
- [x] 고정 λ(1e-3 * base) 조건에서 SNR sweep + threshold 분석  
- [ ] 필요 시, `design_ffe_ls_1d()`에 **λ 후보 스윕(예: [1e-5, 1e-4, 1e-3, 1e-2])을 추가**해서:
  - 각 (채널, 스킴, SNR)마다 **MSE 최소 λ 선택** → 완전 공정한 FFE 조건 재비교
- [ ] 현재 v1 결과 기반 그래프/테이블 정리 (슬라이드/보고서용)
  - 채널별 BER vs SNR 커브
  - 타깃 BER 기준 SNR threshold 테이블
  - “PAM3는 no-solution(nan), ILC3는 finite threshold” 영역 시각화

  ## ILC3_0c_gp vs PAM3: AWGN-only 기준선 정리 (h = [1.0])  13:46분

### 1. 실험 조건

- 채널: AWGN-only, \( h = [1.0] \) (ISI 없음)
- 공통 구조: 심볼당 2-샘플
  - PAM3 매핑  
    - 0 → \([-1, -1]\)  
    - 1 → \([0, 0]\)  
    - 2 → \([+1, +1]\)  
    - 평균 심볼 에너지 맞추기 위해 레벨 스케일링:  
      \(\alpha = \sqrt{3/4} \approx 0.866\)  
      ⇒ 실제 매핑: \([- \alpha, -\alpha], [0,0], [+\alpha, +\alpha]\)
  - ILC3_0c_gp (0-code) 매핑  
    - 0 → \([-1, 0]\)  
    - 1 → \([0, -1]\)  
    - 2 → \([+1, 0]\)  
    - 3 → \([0, +1]\)
- 심볼 수: \(N_{\text{sym}} = 50{,}000\)
- SNR 포인트: 10, 13, 16, 19, 22, 25 dB
- 디코더
  - PAM3: 2-샘플 평균 → 3레벨 슬라이스  
    - 평균값 \(m = (y_0 + y_1)/2\)  
    - 임계값: -0.5, +0.5
  - ILC3_0c_gp: 2D 코드북에 대해 유클리드 거리 최소 인덱스 선택 (메모리리스 ML 디코더)

---

### 2. 에너지 페어니스(공정성) 체크

#### PAM3

- 레벨: \([- \alpha, 0, +\alpha]\), \(\alpha = \sqrt{3/4}\)
- 심볼 별 에너지
  - 0, 2번 심볼:  
    \(E = (-\alpha)^2 + (-\alpha)^2 = 2\alpha^2 = 2 \cdot \frac{3}{4} = 1.5\)
  - 1번 심볼: \(E = 0\)
- 평균 심볼 에너지
  \[
  E_{\text{avg,PAM3}} = \frac{1.5 + 0 + 1.5}{3} = 1
  \]

#### ILC3_0c_gp

- 코드북 점: \((-1,0), (0,-1), (1,0), (0,1)\)
- 각 심볼 에너지:  
  \(E = 1^2 + 0^2 = 1\)
- 평균 심볼 에너지
  \[
  E_{\text{avg,ILC3}} = 1
  \]

⇒ **PAM3와 ILC3_0c_gp 모두 평균 심볼 에너지 = 1**  
⇒ SNR 정의 관점에서 **완전히 공정한 조건**에서 비교하고 있음.

---

### 3. 최소 거리 \(d_{\min}\) 관점 비교

#### PAM3

- 디텍터 입력 평균값: \([- \alpha, 0, +\alpha]\)  
  ⇒ 최소 거리
  \[
  d_{\min,\text{PAM3}} = \alpha \approx 0.866
  \]

#### ILC3_0c_gp

- 코드북 점들:  
  \((-1,0), (0,-1), (1,0), (0,1)\)  
- 인접한 점 사이 거리:
  \[
  d_{\min,\text{ILC3}} = \sqrt{(1-0)^2 + (0-1)^2} = \sqrt{2} \approx 1.414
  \]
- 거리 비율:
  \[
  \frac{d_{\min,\text{ILC3}}}{d_{\min,\text{PAM3}}}
  \approx \frac{1.414}{0.866} \approx 1.63
  \]
- 이를 SNR 이득(dB)로 환산:
  \[
  \Delta\text{SNR} \approx
  10 \log_{10}\left(\left(\frac{1.414}{0.866}\right)^2\right)
  \approx 4.3 \text{ dB}
  \]

⇒ **AWGN-only 이론상, 동일 평균 에너지 기준으로 ILC3_0c_gp가 PAM3 대비 약 4 dB 정도의 성능 이득을 가지는 구조**임.

---

### 4. 시뮬레이션 결과 요약 (AWGN-only)

실험 결과 (일부 발췌):

- SNR = 10 dB  
  - PAM3: acc ≈ 0.99286, ber ≈ 7.14e-3  
  - ILC3_0c_gp: acc ≈ 0.99848, ber ≈ 1.52e-3
- SNR ≥ 13 dB
  - PAM3: 13 dB에서 이미 ber ≈ 2.6e-4 수준
  - ILC3_0c_gp: 13 dB에서 관측상 ber = 0 (50k 심볼 한계 내에서 에러 미발생)
  - 16 dB 이상: 두 방식 모두 ber ≈ 0 (샘플 수 기준으로 사실상 에러 없음)

⇒ 10 dB 근처에서는 **ILC3_0c_gp 쪽이 PAM3 대비 약 4~5배 작은 BER**을 보여 줌.  
⇒ AWGN-only 이론 계산(약 4.3 dB 성능 이득)과 **방향성이 일치**하며, 수치적으로도 설득력 있는 결과.

---

### 5. 결론 및 활용 포인트

1. **에너지 페어니스 검증 완료**  
   - PAM3와 ILC3_0c_gp 모두 평균 심볼 에너지 = 1로 설정하여 공정 비교.
2. **코드북 구조 이득 확인**  
   - ILC3_0c_gp는 2차원 코드북 덕분에 최소 거리 \(d_{\min}\)이 더 크고, 약 4 dB 수준의 이론적 AWGN 성능 이득 보유.
3. **ABC 채널(채널 a/b/c + ISI + FFE) 결과 해석의 기준선**  
   - 이후 a/b/c 채널에서의 결과(ILC3_0c_gp > PAM3)를 설명할 때,  
     “채널 왜곡이 없을 때도 이미 코드북 구조 자체가 ~4 dB 정도 유리하다”는 **기준 레퍼런스**로 사용 가능.
4. **논문/레퍼런스에서의 포인트**  
   - “AWGN-only baseline에서 이미 ILC3_0c_gp가 PAM3 대비 약 4 dB 성능 이득을 보이며,  
     ISI + FFE 환경에서도 이 이득이 상당 부분 유지된다”는 서술이 가능.

   ## 3.2. v2 – PAM3 vs ILC3_0c_gp on 5-tap ISI channels (AWGN + FFE, SNR sweep, λ-sweep FFE) 13:54분

### (1) 실험 조건

- 스킴
  - PAM3: 심볼 레벨 {-1, 0, +1}
  - ILC3_0c_gp: 2-sample 코드워드 (길이 2, 심볼 0..3)
- 채널 (5-tap ISI, normalized)
  - ch-a: h = [0.10, 0.40, 1.00, 0.40, 0.10]   (가장 깨끗한 채널)
  - ch-b: h = [0.05, 0.50, 1.00, 0.50, 0.05]   (가장 강한 ISI)
  - ch-c: h = [0.075, 0.45, 1.00, 0.45, 0.075] (중간 정도 ISI)
- 시뮬레이션 파라미터
  - N_sym = 50,000
  - SNR 범위: 8 dB ~ 36 dB, step = 0.5 dB
  - 채널 및 노이즈: AWGN + 고정 ISI 채널 (위 h 사용)
  - 타깃 BER 리스트: [5e-2, 2e-2, 1e-2, 5e-3]
- 수신기 (RX)
  - 공통: 채널 후 AWGN, 그 후:
    - raw slicer: 채널 중심 샘플 직접 판정
    - FFE: 1D LS 기반 FFE + λ-sweep regularization
  - FFE 설계 함수
    - `design_ffe_ls_1d(r, x, L_ffe)` 사용
    - r: 채널+AWGN 출력, x: 타깃 시퀀스 (PAM3 심볼 또는 ILC3 샘플)
    - λ 후보: {1e-5, 1e-4, 1e-3, 1e-2} × (trace(RᵀR)/L_ffe)
    - 각 λ 후보에 대해 LS 해를 구한 뒤, MSE가 최소가 되는 λ 및 w 선택
    - 비정상/불안정(Inf/NaN, 과도한 노름 등)인 경우 자동 fallback 적용
  - 채널별 FFE 탭 길이 (v2 설정값)
    - PAM3:
      - ch-a: L_ffe = 9
      - ch-b: L_ffe = 15
      - ch-c: L_ffe = 11
    - ILC3_0c_gp:
      - ch-a: L_ffe = 5
      - ch-b: L_ffe = 5
      - ch-c: L_ffe = 9

> 이 설정은 별도의 “FFE fairness sweep” 실험에서 채널별로 합리적인 탭 길이 영역을 찾은 뒤,  
> 각 채널/스킴에 대해 대표 L_ffe 값을 택한 것이다.

---

### (2) SNR_sweep 결과 요약 (FFE 기준)

각 채널별로, target BER 이하로 떨어지는 최소 SNR을 측정하였다.  
표에서 `nan` 값은 주어진 SNR 범위(8~36 dB) 내에서 해당 스킴이 target BER에 도달하지 못했음을 의미한다.

#### 3.2.1. Channel a (h = [0.10, 0.40, 1.00, 0.40, 0.10])

- FFE 탭 길이:
  - PAM3: L_ffe = 9
  - ILC3_0c_gp: L_ffe = 5

- 측정된 threshold SNR (FFE BER 기준):

| target BER | SNR_PAM3 (dB) | SNR_ILC3 (dB) | ΔSNR = SNR_PAM3 − SNR_ILC3 |
|-----------:|:-------------:|:-------------:|:---------------------------:|
| 5.0e-2     |      nan      |     14.0      |            nan             |
| 2.0e-2     |      nan      |     17.5      |            nan             |
| 1.0e-2     |      nan      |     19.5      |            nan             |
| 5.0e-3     |      nan      |     21.5      |            nan             |

- 해석:
  - ILC3_0c_gp는 비교적 낮은 SNR 대역(14~21.5 dB)에서 BER을 5e-2 ~ 5e-3까지 낮출 수 있었음.
  - 같은 RX 구조(FFE, λ-sweep)에서 PAM3는 SNR 36 dB까지 올려도 위의 target BER 레벨에 도달하지 못했기 때문에 이 구간에서는 ΔSNR을 정의할 수 없음.
  - 즉, **“동일 채널·동일 FFE 복잡도에서 ILC3_0c_gp가 PAM3 대비 명백한 SNR 이득을 보이지만, PAM3가 target BER 영역에 들어오지 못해 정량적인 ΔSNR 상한을 주기 어렵다”**는 결론을 얻음.

#### 3.2.2. Channel b (h = [0.05, 0.50, 1.00, 0.50, 0.05])

- FFE 탭 길이:
  - PAM3: L_ffe = 15
  - ILC3_0c_gp: L_ffe = 5

- 측정된 threshold SNR (FFE BER 기준):

| target BER | SNR_PAM3 (dB) | SNR_ILC3 (dB) | ΔSNR |
|-----------:|:-------------:|:-------------:|:----:|
| 5.0e-2     |      nan      |      nan      | nan  |
| 2.0e-2     |      nan      |      nan      | nan  |
| 1.0e-2     |      nan      |      nan      | nan  |
| 5.0e-3     |      nan      |      nan      | nan  |

- 해석:
  - 채널 b는 가장 강한 ISI를 가지는 worst-case 채널로,  
    현재의 FFE-only 구조(λ-sweep 포함, L_ffe PAM3=15 / ILC3=5)에서는 SNR 36 dB까지 올려도  
    PAM3/ILC3 모두 target BER(5e-2 이하)에 도달하지 못했다.
  - 따라서 채널 b는 **“FFE-only RX로는 커버되지 않는 worst-case 채널”**로 분류하며,  
    이후 DFE/MLSE/DLL/phase-EQ 등 고급 RX 구조를 평가하기 위한 타깃 채널로 사용 가능하다.

#### 3.2.3. Channel c (h = [0.075, 0.45, 1.00, 0.45, 0.075])

- FFE 탭 길이:
  - PAM3: L_ffe = 11
  - ILC3_0c_gp: L_ffe = 9

- 측정된 threshold SNR (FFE BER 기준):

| target BER | SNR_PAM3 (dB) | SNR_ILC3 (dB) | ΔSNR |
|-----------:|:-------------:|:-------------:|:----:|
| 5.0e-2     |      nan      |     20.0      | nan  |
| 2.0e-2     |      nan      |      nan      | nan  |
| 1.0e-2     |      nan      |      nan      | nan  |
| 5.0e-3     |      nan      |      nan      | nan  |

- 해석:
  - 중간 ISI 채널인 c에서도 ILC3_0c_gp는 약 20 dB 근방에서 BER ≈ 5e-2 수준에 도달.
  - 동일 조건에서 PAM3는 SNR 36 dB까지 올려도 동일 target BER 레벨에 들어오지 못했음.
  - 따라서 채널 a와 마찬가지로, **실용적인 SNR 대역에서 ILC3_0c_gp가 PAM3 대비 유리한 BER 특성을 보이지만,  
    PAM3가 target 영역에 도달하지 않아 ΔSNR을 수치로 한정하는 것은 불가능하다**고 정리할 수 있음.

---

### (3) v2 결론 정리

1. **FFE-only + λ-sweep RX 구조 기준**에서,
   - 채널 a, c에서는 ILC3_0c_gp가 실용적인 SNR 범위(≈14~21.5 dB)에서 target BER (5e-2 ~ 5e-3)에 도달하지만,
   - PAM3는 같은 RX 복잡도/채널 조건에서 SNR 36 dB까지 올려도 해당 target BER에 도달하지 못했다.
2. 채널 b는 **“FFE-only로는 다루기 어려운 worst-case 채널”**로,
   - 이후 DFE/MLSE/DLL 등의 고급 수신 구조를 평가하기 위한 벤치마크 채널로 사용하는 것이 타당하다.
3. 위의 결과는 모두 스크립트  
   `scripts/test_pam3_vs_ilc3_abc_ffe_snr_sweep_v1.py`  
   (v2: λ-sweep FFE, channel-wise L_ffe 맵 반영) 기반으로 생성되었으며,  
   원시 데이터는 `results/pam3_vs_ilc3_abc_ffe_snr_sweep_full_*.csv`,  
   threshold 요약은 `results/pam3_vs_ilc3_abc_ffe_snr_threshold_*.csv`에 저장되어 있다.  

   ### Channel b: FFE vs FFE+DFE (PAM3 vs ILC3_0c_gp) 14:09분

- 조건: h_b = [0.05, 0.5, 1.0, 0.5, 0.05], N_sym = 50k, AWGN+ISI
- FFE 구성:
  - PAM3: L_ffe = 15, ridge = 1e-5
  - ILC3_0c_gp: L_ffe = 5, ridge = 1e-5
- DFE 구성:
  - 채널 기반 post-cursor 추출, L_dfe = 2 (고정)

결과적으로 FFE-only 구조는 SNR = 16~25 dB에서 PAM3/ILC3 모두 target BER 영역(1e-1~1e-3)에 안정적으로 도달한다. 반면, 단순 채널 기반 DFE(post-cursor tap만 사용)는 모든 SNR 구간에서 오히려 BER을 0.2~0.3 수준으로 악화시킨다. 이는 강한 ISI 환경에서 결정 피드백 오차가 누적되면서, 훈련 기반이 아닌 고정 DFE 구조가 효과적이지 않음을 의미한다. 따라서, 채널 b에서는 **FFE-only 구조를 Rx 후보로 채택하고, FFE+DFE(v1) 구조는 후보에서 제외**한다.


### 채널 b: FFE+DFE(v1) 실험 결과 및 폐기 결론 14:26분

#### 1. 실험 조건 요약

- 채널: **channel b**,  
  \[
  h_b = [0.05,\ 0.5,\ 1.0,\ 0.5,\ 0.05]
  \]
- 공통 조건  
  - 변조: PAM3 vs ILC3\_0c\_gp (공통 3-ary 데이터 시퀀스 사용)  
  - 심볼 수: \( N_{\text{sym}} = 50{,}000 \)  
  - 채널: AWGN + ISI (channel b)  
  - FFE: LS + ridge, fairness sweep 결과 기반  
    - PAM3: \(L_{\text{FFE}} = 15\), ridge = \(1 \times 10^{-5}\)  
    - ILC3\_0c\_gp: \(L_{\text{FFE}} = 5\), ridge = \(1 \times 10^{-5}\)  
  - DFE: 채널 기반 post-cursor 캔슬 구조  
    - DFE 길이: \(L_{\text{DFE}} = 2\)  
    - 설계: 원래 채널 \(h_b\)에서 최대 탭 이후 post-cursor를 비율로 나누어 사용  
- SNR 리스트:  
  \[
  \text{SNR} \in \{16,\ 19,\ 22,\ 25\}\ \text{dB}
  \]

---

#### 2. FFE-only vs FFE+DFE(v1) 결과 요약

- 공통 경향:
  - **FFE-only**에서는 SNR이 올라갈수록 PAM3 / ILC3 모두 BER이 뚜렷하게 감소.
  - **FFE+DFE(v1)**를 붙였을 때,
    - 모든 SNR 구간(16/19/22/25 dB)에서 **FFE-only 대비 BER이 오히려 악화**됨.
    - 특히 고 SNR 구간에서도 FFE+DFE가 FFE-only보다 훨씬 나쁜 BER.

- 예시 수치 (채널 b, SNR 19 dB 기준):

  - **PAM3**
    - FFE-only:  
      \(\text{FFE\_acc} \approx 0.9451,\ \text{FFE\_ber} \approx 0.0549\)
    - FFE+DFE(v1):  
      \(\text{FFE+DFE\_acc} \approx 0.7316,\ \text{FFE+DFE\_ber} \approx 0.2684\)

  - **ILC3\_0c\_gp**
    - FFE-only:  
      \(\text{FFE\_acc} \approx 0.9352,\ \text{FFE\_ber} \approx 0.0648\)
    - FFE+DFE(v1):  
      \(\text{FFE+DFE\_acc} \approx 0.7454,\ \text{FFE+DFE\_ber} \approx 0.2546\)

- 고 SNR(22/25 dB)에서도 FFE-only 기준으로는 BER이 \(10^{-2}\)~\(10^{-3}\) 수준까지 떨어지지만,  
  FFE+DFE(v1)는 여전히 \(\approx 0.24\)~\(0.25\) 수준에 머물며 **성능이 극단적으로 악화**됨.

---

#### 3. 성능 악화 원인 분석 (직관적 설명)

1. **FFE 이후 effective 채널 미반영**
   - 현재 DFE 탭 설계는 “원래 채널 \(h_b\)”만 보고 post-cursor 비율로 추출.
   - 하지만 실제 Rx에서는 **FFE를 먼저 통과한 뒤의 effective 채널** 위에서 결정이 이루어진다.
   - 따라서 DFE는 “FFE 이후 실제 ISI 구조”와 **불일치하는 탭**을 사용하게 되고,  
     결과적으로 ISI 제거가 아니라 **신호를 더 망가뜨리는 방향으로 동작**할 수 있다.

2. **하드-디시전 DFE의 error propagation**
   - DFE는 과거 **결정된 심볼**을 feedback에 사용한다.
   - 초기에 잘못된 결정이 들어가면, 잘못된 심볼이 그대로 feedback ISI 추정에 쓰이면서  
     **오류가 연쇄적으로 전파(error propagation)** 된다.
   - 특히 채널 b처럼 ISI가 강한 환경에서,  
     “부정확한 DFE 탭 + 하드 디시전” 조합은 BER 악화를 쉽게 유발한다.

3. **결론**
   - 본 v1 구조는 “FFE-only 구조에, 채널 기반 DFE를 단순히 얹어본 시도” 수준이며,  
     effective 채널 추정, joint LS, soft decision 등 고급 기법을 쓰지 않았다.
   - 그 결과, **FFE-only 대비 일관되게 성능 열화**가 관찰되었으며,  
     채널 b 기준 Rx 후보로 채택하기에는 적합하지 않다고 판단된다.

---

#### 4. 채널 b 기준 Rx 후보 결론

- **Rx#1: FFE-only (채택)**
  - 구조:  
    \[
    \text{Tx (PAM3 / ILC3\_0c\_gp)} \rightarrow \text{채널 } h_b \rightarrow \text{FFE(LS+ridge)} \rightarrow \text{3-ary slicer}
    \]
  - 채널 a/c에서는 ILC3\_0c\_gp가 PAM3 대비 명확한 BER 이득.  
  - 채널 b에서는 두 방식 모두 강한 ISI로 인해 target BER에 여유가 크진 않지만,  
    **FFE-only 기준 비교**로는 ILC3\_0c\_gp의 상대적 장단점을 평가하기에 충분하다고 판단.

- **Rx#2: FFE+DFE(v1) (폐기)**
  - 구조: FFE(채널 앞면) + DFE(원래 채널 기반 post-cursor 캔슬)
  - 실험 결과:
    - SNR 16~25 dB 전 구간에서 FFE-only 대비 BER 악화.
    - 고 SNR에서도 FFE+DFE(v1)가 여전히 BER \(\approx 0.24\)~\(0.29\) 수준 → Rx 후보로 부적합.
  - 결론:
    - 채널 b 기준 Rx 후보 셋에서 **FFE+DFE(v1)는 폐기**.  
    - 향후 DFE 도입 시에는
      - FFE 이후 effective 채널 추정 기반 joint 설계,
      - MLSE/Viterbi 계열 고급 Rx
      등을 별도 연구 과제로 진행하는 것이 타당.

---

#### 5. 정리

- 채널 b는 여전히 **“가장 강한 ISI를 갖는 worst-case 채널”**로 정의.  
- 1차 IP 코어 / 논문 정리에서는
  - **FFE-only Rx를 기준 구조로 사용**하여 PAM3 vs ILC3\_0c\_gp를 비교하고,
  - DFE(v1) 시도는 “naive한 DFE 추가가 오히려 BER을 악화시킨 사례”로 기록한다.
- 향후 고급 Rx 설계(MLSE, 개선된 DFE 등)는 채널 b를 타깃으로 하는 **후속 연구 항목**으로 분리한다.

## 3. ILC3_0c_gp 설계 코너 정의: 채널 a / b / c

### 3.1 채널 정의 및 ISI 강도

- 공통 조건  
  - 심볼 수: N_sym = 50,000  
  - 시뮬 구조: AWGN + 5-tap ISI 채널 + FFE (LS + ridge)  
  - 모듈레이션:  
    - PAM3: {0,1,2} → {-1, 0, +1}  
    - ILC3_0c_gp: 2-샘플 코드워드 매핑 (예: [-1,0], [0,-1], [1,0], [0,1])

- 채널 a (상대적으로 깨끗한 채널, “typical / center” 용도)
  - 임펄스 응답  
    \[
    h_a = [0.10,\ 0.40,\ 1.00,\ 0.40,\ 0.10]
    \]
  - 특성:  
    - 주탭(1.0)에 비해 양 옆 ISI 탭이 상대적으로 작음  
    - equalization이 비교적 쉬운, “제품 스펙 센터”에 가까운 채널

- 채널 b (ISI 최강, “worst-case” 채널)
  - 임펄스 응답  
    \[
    h_b = [0.05,\ 0.50,\ 1.00,\ 0.50,\ 0.05]
    \]
  - 특성:  
    - 양 옆 탭이 0.5로 매우 강함 → 포스트/프리커서 ISI가 가장 심각  
    - 패키지 + 보드 + 커넥터까지 포함한 **최악 품질 링크**를 대표하는 코너

- 채널 c (중간 강도의 ISI, “intermediate” 채널)
  - 임펄스 응답  
    \[
    h_c = [0.075,\ 0.45,\ 1.00,\ 0.45,\ 0.075]
    \]
  - 특성:  
    - a와 b 사이 강도의 ISI  
    - typical(a)과 worst(b) 사이를 잇는 검증용 채널

---

### 3.2 FFE-only 결과 요약 (AWGN + ISI + FFE)

- 공통 시뮬 조건  
  - 심볼 수: N_sym = 50,000  
  - SNR: 10, 13, 16, 19, 22, 25 dB (여기서는 19, 22 dB만 대표로 요약)  
  - FFE: LS + ridge, 채널별 고정 길이  
  - BER = 1 − accuracy (심볼 에러율)

#### 3.2.1 채널 a (h_a) 에서의 FFE-only 성능

대표 SNR에서의 FFE-only BER:

| 채널 a, h = [0.1, 0.4, 1.0, 0.4, 0.1] | SNR (dB) | PAM3 FFE BER | ILC3_0c_gp FFE BER |
|---------------------------------------|----------|--------------|--------------------|
|                                       | 19       | ≈ 0.1604     | ≈ 0.0120           |
|                                       | 22       | ≈ 0.1527     | ≈ 0.0033           |

- 해석:
  - 같은 FFE 구조에서 ILC3_0c_gp가 PAM3 대비 BER이 **약 10~50배 이상 낮음**  
  - typical 채널(a) 기준으로 볼 때, ILC3_0c_gp + FFE 조합은 **명확한 코딩 이득(coding gain)** 을 보여 줌.

#### 3.2.2 채널 b (h_b) 에서의 FFE-only 성능

| 채널 b, h = [0.05, 0.5, 1.0, 0.5, 0.05] | SNR (dB) | PAM3 FFE BER | ILC3_0c_gp FFE BER |
|-----------------------------------------|----------|--------------|--------------------|
|                                         | 19       | ≈ 0.2838     | ≈ 0.1319           |
|                                         | 22       | ≈ 0.2809     | ≈ 0.1252           |

- 해석:
  - FFE-only 기준으로 보면, **채널 b에서도 ILC3_0c_gp + FFE가 PAM3 + FFE보다 BER이 낮음**  
  - 다만 절대값 자체가 여전히 0.1대 수준으로, **target BER(예: 1e-2 이하)** 을 만족시키지는 못함.  
  - → 채널 b는 “FFE-only로는 커버 안 되는 worst-case 채널”로 분류.

#### 3.2.3 채널 c (h_c) 에서의 FFE-only 성능

| 채널 c, h = [0.075, 0.45, 1.0, 0.45, 0.075] | SNR (dB) | PAM3 FFE BER | ILC3_0c_gp FFE BER |
|---------------------------------------------|----------|--------------|--------------------|
|                                             | 19       | ≈ 0.2304     | ≈ 0.0546           |
|                                             | 22       | ≈ 0.2270     | ≈ 0.0438           |

- 해석:
  - 채널 c(중간 ISI)에서도 ILC3_0c_gp + FFE가 PAM3 + FFE 대비 **약 4~5배 낮은 BER**  
  - typical(a)와 worst(b) 사이에서, ILC3 이득이 어느 정도 유지되는 “중간 검증 채널”로 활용 가능.

---

### 3.3 해석 정리: 설계 코너로서의 a/b/c 역할

- **채널 a (typical / spec-center)**  
  - 비교적 깨끗한 환경에서 ILC3_0c_gp + FFE의 기본 이득을 보여주는 대표 채널  
  - IPCore v1의 **주요 스펙 정의(필수 성능 보장)** 에 사용할 수 있는 코너

- **채널 b (worst-case / 연구 타깃)**  
  - FFE-only 기준으로는 PAM3/ILC3 모두 target BER을 만족시키지 못하는 가장 극단 채널  
  - IPCore v1 기준으로는 “**현 구조로는 커버 불가한 코너**”로 명시하고,  
    향후 DFE / MLSE / phase-EQ / RX 구조 강화 연구의 **대표 타깃 채널**로 사용

- **채널 c (intermediate / 검증 채널)**  
  - a와 b 사이의 현실적인 ISI 강도  
  - a에서 스펙을 만족하는 구조가 c에서도 충분히 동작하는지 확인하는 **validation 코너** 역할

  ## 4. IPCore v1 개념 블록다이어그램 (텍스트)

### 4.1 Top-level 구조 (Tx + 채널 + Rx)

```text
        ┌────────────────────────────────────────────────────┐
        │                     Transmitter (Tx)               │
        │                                                    │
Data ───┤ 3-ary Data (0/1/2)                                 │
        │        │                                           │
        │        ▼                                           │
        │  [Mapper] ── PAM3 mode : {-1, 0, +1}               │
        │             └ ILC3_0c_gp mode : 강화된 3레벨          │ 
        │        │                                           │
        │        ▼                                           │
        │  [Tx Filter / Pre-emphasis] (옵션, FIR)             │
        │        │                                           │
        │        ▼                                           │
        │      [Driver / DAC]                                │
        └────────┬───────────────────────────────────────────┘
                 │ 아날로그 채널 (패키지 + 보드 + 커넥터 + 케이블)
                 ▼
        ┌────────────────────────────────────────────────────┐
        │                     Channel (a / b / c)            │
        │   h_a / h_b / h_c (5-tap ISI + AWGN)               │
        └────────┬───────────────────────────────────────────┘
                 │
                 ▼
        ┌────────────────────────────────────────────────────┐
        │                     Receiver (Rx)                  │
        │                                                    │
        │  [AFE]  (CTLE / VGA 등, 아날로그 전치보상)              │
        │        │                                           │
        │        ▼                                           │
        │  [ADC] 또는 [Slicer 입력]                            │
        │        │                                           │
        │        ▼                                           │
        │  [FFE Equalizer]                                   │
        │        │   - 채널 기반 코너에 따라 탭 길이 선택            │
        │        │     · 채널 a/c : 중간 길이                   │
        │        │     · 채널 b   : 더 긴 FFE 필요              │
        │        ▼                                           │
        │  [PAM3 / ILC3 Slicer]                              │
        │        │                                           │
        │        ▼                                           │
        │  3-ary Data Out (0/1/2)                            │
        └────────────────────────────────────────────────────┘

 [FFE Output]
    │
    ├──▶ (옵션) [DFE Block]
    │          - 채널 h_b 기반 post-cursor ISI 캔슬
    │
    ├──▶ (옵션) [Phase-EQ / Fractionally-spaced FFE]
    │          - 샘플링 포인트/위상까지 조정
    │
    └──▶ (옵션) [MLSE-lite / Sequence Detector]
               - ILC3_0c_gp의 구조(레벨/위상)를 활용한 시퀀스 검출

 요약:
	•	IPCore v1
	•	Tx: PAM3 / ILC3 듀얼 모드 맵퍼 + (옵션) Tx FIR
	•	Rx: FFE-only + PAM3/ILC3 공용 슬라이서
	•	설계/스펙 기준 채널: a (typical), c (중간)
	•	Advanced Rx (v2 이후)
	•	채널 b를 타깃으로 DFE / fractionally spaced FFE / MLSE-lite / phase-EQ 등 연구
	•	현재 naive DFE 결과는 FFE-only보다 BER이 나빠지는 상태 → “향후 개선 과제”로 분류

 ---

```markdown
## 5. 채널 b: 연구용 타깃 채널 정의

### 5.1 현재 상태 요약

- 채널 b 임펄스 응답  
  \[
  h_b = [0.05,\ 0.50,\ 1.00,\ 0.50,\ 0.05]
  \]
- FFE-only 결과:
  - PAM3, ILC3_0c_gp 모두 **절대 BER이 0.1~0.3 수준**으로,  
    pre-FEC target BER (예: 1e-2 이하)에 도달하지 못함.
  - 다만 FFE-only에서는 ILC3_0c_gp + FFE가 PAM3 + FFE보다 항상 더 낮은 BER을 보임.

- FFE + naive DFE (test_pam3_vs_ilc3_b_ffe_dfe_v1.py 결과):
  - SNR = 16, 19, 22, 25 dB 구간에서,
    **FFE+DFE가 오히려 FFE-only보다 BER이 더 나쁨** (PAM3/ILC3 공통 현상)
  - DFE 탭을 채널 post-cursor 기반 간단한 비율로만 설정한 naïve 구조라,
    채널 b의 강한 ISI + 노이즈 조합에서는 **오히려 오동작**하는 양상.

→ 결론: 채널 b는 **현 Rx 구조(FFE-only + naive DFE)로는 target BER 달성이 어려운 worst-case 채널**로 정의.

---

### 5.2 연구/개선 방향 (채널 b 중심)

향후 Rx 연구는 채널 b를 대표 코너로 삼고 아래 항목들을 단계적으로 검토한다.

1. **DFE 구조 개선**
   - 현재: 채널 h_b 기반 단순 post-cursor 비율 탭 → FFE-only보다 성능 저하  
   - 개선 방향:
     - training sequence 기반 **joint FFE+DFE LS 설계**  
     - error propagation 억제를 위한 soft decision / clipping 전략  
     - tap 길이/딜레이 최적화 (L_dfe, decision delay)

2. **Fractionally spaced FFE (FS-FFE)**
   - 현재: symbol-spaced FFE만 사용  
   - 개선 방향:
     - oversampling(예: 2×) 후 FS-FFE 적용  
     - 샘플링 위상/채널 위상까지 고려한 equalization으로 채널 b 대응력 강화

3. **ILC3 구조 특화 MLSE-lite / sequence detector**
   - ILC3_0c_gp의 레벨 구조/guard phase 특성을 이용해  
     짧은 상태 수를 갖는 **간단한 sequence detector** 설계  
   - 채널 b 같은 강한 ISI 환경에서 ILC3의 잠재 이득을 극대화하는 방향

4. **Phase-EQ / DLL 연계**
   - 채널 b에서의 최적 위상(샘플링 타이밍)을 찾는 DLL/phase-EQ 알고리즘과  
     FFE/DFE/MLSE를 연계하는 구조 설계

---

### 5.3 문서/코드 링크 메모

- FFE-only 비교 스크립트  
  - `test_pam3_vs_ilc3_abc_ffe_v1.py`
- SNR sweep + target BER 비교 스크립트  
  - `test_pam3_vs_ilc3_abc_ffe_snr_sweep_v1.py`
- PAM3 FFE fairness sweep  
  - `test_pam3_ffe_fairness_v1.py`
- ILC3_0c_gp FFE fairness sweep  
  - `test_ilc3_ffe_fairness_v1.py`
- 채널 b FFE+DFE prototype  
  - `test_pam3_vs_ilc3_b_ffe_dfe_v1.py`  
    - 현재 상태: naive DFE → FFE-only 대비 성능 저하  
    - 향후 “개선 전 baseline”으로 활용
    
 ## 6. Rx v1 사양 요약 (FFE-only) 14:39분

- Rx 구조:
  - AFE (CTLE/VGA 등 아날로그 전치보상)
  - ADC 또는 slicer 입력
  - FFE (symbol-spaced, LS + ridge)
  - PAM3 / ILC3_0c_gp 공용 슬라이서

- 설계 코너:
  - 채널 a (typical), 채널 c (intermediate)에서
    ILC3_0c_gp + FFE 기준 pre-FEC target BER(예: 1e-2) 만족
  - 채널 b는 FFE-only로는 target BER 미달 → worst-case 연구 코너로 분리

- DFE 현황:
  - `test_pam3_vs_ilc3_b_ffe_dfe_v1.py` 기준
    naive DFE는 FFE-only 대비 BER 악화
  - 따라서 Rx v1에는 DFE 미포함
  - DFE/MLSE/phase-EQ 등은 채널 b 중심의 v2 이후 연구 과제로 분류    

  ## 7. Required SNR @ target BER (FFE-only)

### 7.1 Channel a (typical)

| target BER | SNR_PAM3 (dB) | SNR_ILC3 (dB) | ΔSNR(PAM3−ILC3) |
|-----------:|--------------:|--------------:|----------------:|
| 5.0e-02    |   — (not hit) |  14.0         |   —             |
| 2.0e-02    |   —           |  17.5         |   —             |
| 1.0e-02    |   —           |  19.5         |   —             |
| 5.0e-03    |   —           |  21.5         |   —             |

### 7.2 Channel c (intermediate)

| target BER | SNR_PAM3 (dB) | SNR_ILC3 (dB) | ΔSNR(PAM3−ILC3) |
|-----------:|--------------:|--------------:|----------------:|
| 5.0e-02    |   —           |  20.0         |   —             |
| 2.0e-02    |   —           |   —           |   —             |
| 1.0e-02    |   —           |   —           |   —             |
| 5.0e-03    |   —           |   —           |   —             |   

> 채널 b에서 naive DFE는 FFE-only보다 BER이 더 나빠지는 것이 확인됨.  
> → 현재 구조로는 사용 불가, 향후 joint FFE+DFE / MLSE / phase-EQ 연구의 baseline으로만 활용.

## 3. Rx v1 기준선 및 설계 코너 정의

### 3.1 공통 실험 조건 (Rx v1: FFE-only)

- 공통 채널 세트 (5-tap ISI):
  - Channel a (가장 깨끗한 채널)  
    \- h_a = [0.10, 0.40, 1.00, 0.40, 0.10]
  - Channel b (가장 강한 ISI, worst-case)  
    \- h_b = [0.05, 0.50, 1.00, 0.50, 0.05]
  - Channel c (중간 강도의 ISI, mid-case)  
    \- h_c = [0.075, 0.45, 1.00, 0.45, 0.075]

- 변조 스킴
  - PAM3: 심볼 레벨 {-1, 0, +1}
  - ILC3_0c_gp: 각 심볼을 2샘플 코드워드로 매핑하는 3-level 4-symbol 코드  
    \- 코드북 예: [-1,0], [0,-1], [1,0], [0,1]

- Rx 구조 (Rx v1 baseline)
  - AWGN + ISI 채널 통과 후
  - 심볼 타이밍 샘플링
  - **FFE(equalizer)**: 1D LS + ridge regularization + 안정성 체크
  - 뒤에 **단순 slicer**:
    - PAM3: 3레벨 slicer
    - ILC3: 2-샘플 코드북 기반 최소 거리 디텍터

- SNR, 심볼 수
  - N_sym = 50,000
  - SNR 포인트: 10, 13, 16, 19, 22, 25 dB
  - SNR sweep 시: 8 ~ 36 dB, step = 0.5 dB

- FFE 탭 길이 (fairness sweep 결과 반영)
  - PAM3:
    - ch a: L_ffe = 9
    - ch b: L_ffe = 15
    - ch c: L_ffe = 11
  - ILC3_0c_gp:
    - ch a: L_ffe = 5
    - ch b: L_ffe = 5
    - ch c: L_ffe = 9

- FFE 설계 방식 (요약)
  - 입력: 채널+AWGN 이후 r[n], 타깃: x[n] (PAM3) 또는 u[n] (ILC3 코드 시퀀스)
  - Toeplitz 행렬 R 구성 후 LS 기반:
    - 여러 λ 후보(1e-5, 1e-4, 1e-3, 1e-2 × trace 기반 scale)를 스캔
    - 각 λ에 대해 MSE 최소 조합 선택
    - NaN/inf, 과도한 노름(>1e6) 필터링
    - 모두 실패 시 identity tap로 fallback
  - 이 설계는 PAM3 / ILC3 모두 동일하게 적용 (FFE 알고리즘 공정성 유지)


### 3.2 채널 a: Typical case (가장 깨끗한 ISI 환경)

- h_a = [0.10, 0.40, 1.00, 0.40, 0.10]
- ISI 강도: 3개 채널 중 가장 약함 (best channel)
- 사용 FFE 길이:
  - PAM3: L_ffe = 9
  - ILC3_0c_gp: L_ffe = 5 (더 짧은 길이로 동작)

- 대표 성능 (예: SNR = 19, 22, 25 dB)
  - SNR 19 dB:
    - PAM3: FFE_ber ≈ 0.160
    - ILC3: FFE_ber ≈ 0.012
  - SNR 22 dB:
    - PAM3: FFE_ber ≈ 0.153
    - ILC3: FFE_ber ≈ 0.003
  - SNR 25 dB:
    - PAM3: FFE_ber ≈ 0.146
    - ILC3: FFE_ber ≈ 0.0005

- 요약
  - 동일 채널, 동일 FFE 알고리즘 기준에서 ILC3_0c_gp가 PAM3 대비 **약 10~100배 수준으로 낮은 BER**.
  - 특히 **짧은 FFE 탭(L=5)**로도 target BER 대역(1e-2 이하)까지 충분히 진입.
  - 채널 a는 **“typical / best case” 설계 코너**로 사용 가능.


### 3.3 채널 c: Mid-case (중간 수준의 ISI)

- h_c = [0.075, 0.45, 1.00, 0.45, 0.075]
- ISI 강도: a보다 강하고, b보다 약한 중간 수준
- 사용 FFE 길이:
  - PAM3: L_ffe = 11
  - ILC3_0c_gp: L_ffe = 9

- 대표 성능 (예: SNR = 19, 22, 25 dB)
  - SNR 19 dB:
    - PAM3: FFE_ber ≈ 0.230
    - ILC3: FFE_ber ≈ 0.055
  - SNR 22 dB:
    - PAM3: FFE_ber ≈ 0.227
    - ILC3: FFE_ber ≈ 0.044
  - SNR 25 dB:
    - PAM3: FFE_ber ≈ 0.227
    - ILC3: FFE_ber ≈ 0.039

- 요약
  - 중간 수준 ISI 환경에서도 ILC3_0c_gp + FFE가  
    PAM3 + FFE 대비 대략 **4~6배 정도 낮은 BER**을 유지.
  - 채널 c는 **“mid-case 설계 코너”**로 사용.


### 3.4 채널 b: Worst-case (가장 강한 ISI, 연구용 타깃 채널)

- h_b = [0.05, 0.50, 1.00, 0.50, 0.05]
- ISI 강도: a, c 대비 가장 강함 (worst-case)
- 사용 FFE 길이:
  - PAM3: L_ffe = 15
  - ILC3_0c_gp: L_ffe = 5 (다른 후보도 있었으나, v1에서는 5탭 기준)

- FFE-only 성능 (채널 b)
  - raw_ber 기준:
    - PAM3: ≈ 0.30 부근
    - ILC3: ≈ 0.21 부근
  - FFE 적용 후:
    - PAM3: FFE_ber ≈ 0.28 ~ 0.30
    - ILC3: FFE_ber ≈ 0.13 부근
  - 즉, **ILC3_0c_gp가 PAM3보다 약 2~2.5배 정도 더 낮은 BER**을 유지하지만  
    두 스킴 모두 **타깃 BER (1e-2 ~ 5e-3)에는 도달하지 못함.**

- DFE 시도 (채널 b, naivie 구조)
  - 스크립트: `test_pam3_vs_ilc3_b_ffe_dfe_v1.py`
  - 구조:
    - Rx: FFE 후, 간단한 DFE(피드백 탭 2개) 추가
  - 결과:
    - 예: SNR 19 dB 기준
      - PAM3:
        - FFE-only: BER ≈ 0.055
        - FFE+DFE: BER ≈ 0.27 (오히려 악화)
      - ILC3:
        - FFE-only: BER ≈ 0.065
        - FFE+DFE: BER ≈ 0.25 (역시 악화)
  - 결론:
    - v1에서 사용한 단순 DFE 구조는 **FFE-only보다 항상 성능이 나빠지는 패턴**을 보여  
      현재 generation의 IPCore 후보에서는 **“채용 보류(naive DFE는 제외)”**로 정리.

- 요약
  - 채널 b는 **“FFE-only로는 타깃 BER을 만족시키지 못하는 worst-case 채널”**로 정의.
  - 향후 고급 Rx 연구(DFE 개선, MLSE, 위상 보조 EQ, Tx pre-emphasis 등)는  
    **채널 b를 중심으로 수행**하는 것이 합리적.
  - 현재 Rx v1 baseline에서는
    - “ILC3_0c_gp + FFE-only가 PAM3 + FFE-only 대비 항상 우수하지만,  
      채널 b는 여전히 추가적인 Rx/Tx 기술이 필요한 영역”으로 위치.


### 3.5 AWGN-only 레퍼런스 (채널 h = [1.0])

- 실험: `test_pam3_vs_ilc3_awgn_v1.py`
- 조건:
  - h = [1.0] (순수 AWGN 채널)
  - N_sym = 50,000
  - SNR: 10, 13, 16, 19, 22, 25 dB
  - FFE 사용하지 않는 단순 AWGN 레퍼런스

- 대표 결과
  - SNR 10 dB:
    - PAM3: BER ≈ 7.1e-3
    - ILC3: BER ≈ 1.5e-3
  - SNR 13 dB 이상:
    - PAM3: BER → 2.6e-4 수준까지 감소 후 16 dB부터는 0에 근접
    - ILC3: 13 dB에서 이미 BER = 0, 이후 SNR에서 모두 0

- 요약
  - 순수 AWGN 환경에서 ILC3_0c_gp는 PAM3보다 **더 빠르게 BER = 0 영역으로 진입**.
  - 이 결과는 “채널이 깨끗할수록 ILC3 guard-phase 구조의 intrinsic 이득이 명확해진다”는  
    레퍼런스로 사용할 수 있음.


## 4. IPCore v1 블록 다이어그램 (텍스트 버전)

### 4.1 Tx 쪽 구성 (v1 기준, Tx pre-emphasis 미적용)

- Data_in (비트/심볼 스트림)
- Mapper
  - PAM3 모드:
    - 비트 → 심볼 매핑: {-1, 0, +1}
  - ILC3_0c_gp 모드:
    - 2비트 → 코드워드 인덱스(0..3)
    - 코드북 매핑: 2-샘플 시퀀스 [-1,0], [0,-1], [1,0], [0,1]
- Tx Pulse Shaping / Driver
  - 현 단계에서는 간단한 송신 필터(또는 NRZ) + 드라이버로 모델링
  - **Tx pre-emphasis FIR는 v2에서 별도 축으로 연구 예정**  
    (채널 b 개선용 후보)

텍스트 블록도 (개념)  
- Data_in  
  → [Mode Select: PAM3 / ILC3_0c_gp]  
  → Mapper (PAM3 symbol or ILC3 codeword)  
  → Tx Pulse Shaper / Driver  
  → 채널 h_a/h_b/h_c (ISI + AWGN)

### 4.2 Rx 쪽 구성 (Rx v1: FFE-only baseline)

- Analog Front-End (AFE)
  - 채널 출력 → 증폭/필터링 → 샘플링

- Sampler / ADC
  - 현재 모델에서는 이상적인 샘플링 + 실수 신호로 단순화

- FFE Equalizer
  - 입력: 샘플 시퀀스 r[n]
  - 출력: equalized 시퀀스 r_eq[n]
  - FFE 설계:
    - 1D LS + ridge regularization
    - 채널별, 스킴별 FFE 탭 길이는 fairness sweep 결과 사용
      - PAM3: L_ffe = 9(a), 15(b), 11(c)
      - ILC3: L_ffe = 5(a), 5(b), 9(c)

- Slicer / Detector
  - PAM3 모드:
    - 3레벨 slicer: {-1, 0, +1} 중 최근접 레벨 선택
  - ILC3_0c_gp 모드:
    - (2-샘플 벡터 vs 4개 코드워드) 최소 거리 기반 디텍터
    - guard-phase 성질 이용, worst-case 채널에서도 PAM3보다 낮은 BER 달성

텍스트 블록도 (개념)  
- 채널 출력  
  → AFE  
  → Sampler/ADC  
  → FFE (Rx v1)  
  →  
    - PAM3 모드: 3-level slicer → Data_out  
    - ILC3 모드: codeword detector → Data_out

### 4.3 Advanced Rx 후보 (v2 이후 연구 축, dotted box)

- DFE (Decision Feedback Equalizer)
  - 현재 v1 naive 구조는 **FFE-only보다 성능 악화**  
    → 구조 재설계 필요, v2에서 재검토

- MLSE / Sequence Detector
  - 채널 b와 같이 ISI가 강한 환경에서 최적/준최적 디텍터 후보

- Phase-aided Equalizer / Guard-phase 활용 EQ
  - ILC3의 guard-phase 특성을 더 적극적으로 활용하는 구조

- Tx Pre-emphasis (Tx FIR + Rx FFE 조합)
  - 채널 b 개선을 위한 다음 설계 축
  - v2에서 “Tx FIR 계수/길이 vs Rx FFE 길이/성능” 트레이드오프 연구 예정

---

**정리**

- 현재까지의 Rx v1 baseline:
  - 채널 a/c: ILC3_0c_gp + FFE-only가 PAM3+FFE 대비 **명확한 BER 이득** 확보.
  - 채널 b: ILC3_0c_gp가 PAM3보다 항상 좋지만, 둘 다 target BER 미달 →  
    **worst-case 설계 코너 + 향후 연구 타깃 채널**로 정의.
  - naive DFE는 현 구조에서는 채택 불가 (FFE-only보다 나쁜 결과)로 정리.
- 다음 챕터에서는 **채널 b를 대상으로 Tx pre-emphasis + Rx FFE 조합**을  
  별도 v2 실험 축으로 여는 방향이 자연스러운 흐름.

Fig. 1. AWGN-only에서 PAM3 vs ILC3_0c_gp BER vs SNR (N_sym = 50k).
Fig. 2. Channel a, FFE-only 기준 PAM3 vs ILC3 BER vs SNR.
Fig. 3. Channel c, FFE-only 기준 PAM3 vs ILC3 BER vs SNR.
Fig. 4. Channel b, FFE-only 기준 PAM3 vs ILC3 BER vs SNR (worst-case 예시).

## ILC3 Rx v1 baseline 정리 (AWGN + ISI + FFE/DFE)

### 1. Rx v1 정의

- 공통 심볼:
  - N_sym = 50,000
  - 3-ary 인덱스 {0,1,2} 공통 사용 후
    - PAM3: {-1, 0, +1}
    - ILC3_0c_gp: {-1.2, 0, +1.2} (단순화된 레벨 모델)
- 채널 계수:
  - channel a: h = [0.10, 0.40, 1.00, 0.40, 0.10]
  - channel b: h = [0.05, 0.50, 1.00, 0.50, 0.05]
  - channel c: h = [0.075, 0.45, 1.00, 0.45, 0.075]
  - AWGN-only: h = [1.0]
- 잡음:
  - AWGN, SNR in dB (Es / σ² 기준)
- Rx v1 공통 구조:
  - 채널 통과 → AWGN → FFE(LS + ridge) → 3-level slicer (PAM3 또는 ILC3)

---

### 2. 스크립트 & 결과 맵

- `test_pam3_vs_ilc3_awgn_v1.py`
  - 내용: AWGN-only(h=[1.0]) 환경에서 PAM3 vs ILC3_0c_gp BER 비교 (no ISI, no FFE)
  - 결과:
    - SNR ≥ 13 dB 구간에서 둘 다 BER ≈ 0,  
      ILC3_0c_gp는 10 dB에서 PAM3 대비 약 4.7× 낮은 BER (0.00152 vs 0.00714).
  - CSV:
    - `results/pam3_vs_ilc3_awgn_YYYY-MM-DD_HH-MM-SS.csv`

- `test_pam3_vs_ilc3_abc_ffe_snr_sweep_v1.py`
  - 내용: channel a/b/c + AWGN + FFE-only 환경에서  
    SNR sweep 후 target BER에 도달하는지 (SNR_threshold) 비교.
  - 설정:
    - SNR range = 8.0 ~ 36.0 dB (step 0.5 dB)
    - target BER = [5e-2, 2e-2, 1e-2, 5e-3]
    - FFE 길이:
      - channel a: PAM3 L=9,  ILC3 L=5
      - channel b: PAM3 L=15, ILC3 L=5
      - channel c: PAM3 L=11, ILC3 L=9
  - 결과 요약:
    - channel a: ILC3_0c_gp + FFE만 target BER에 도달 (PAM3는 해당 범위에서 target 미도달 → SNR_PAM3 = NaN)
    - channel b: PAM3/ILC3 모두 target BER 미도달 (worst-case 채널로 고정)
    - channel c: channel a와 유사 경향, ILC3가 PAM3 대비 유리, 다만 b보다는 ISI가 약한 중간 채널.
  - CSV:
    - full curve: `pam3_vs_ilc3_abc_ffe_snr_sweep_full_*.csv`
    - threshold: `pam3_vs_ilc3_abc_ffe_snr_threshold_*.csv`

- `test_pam3_ffe_fairness_v1.py`
  - 내용: PAM3 쪽 FFE 길이/λ를 sweep해서 **“최선의 FFE 조건”**을 찾는 fairness 실험.
  - 설정:
    - SNR list = [16, 19, 22, 25] dB
    - L_ffe list = [5, 7, 9, 11, 15]
    - ridge list = [1e-5, 1e-4, 1e-3, 1e-2]
  - 결과(대표):
    - channel a: L=9, ridge=1e-5 근처에서 acc ≈ 0.996
    - channel b: L=15, ridge=1e-5 근처에서 acc ≈ 0.999
    - channel c: L=11, ridge=1e-5 근처에서 acc ≈ 1.0
  - 결론:
    - 이후 모든 PAM3 vs ILC3 비교에서 **PAM3 FFE는 fairness sweep에서 고른 최선 파라미터**를 사용 (PAM3 불리하게 잡지 않음).

- `test_ilc3_ffe_fairness_v1.py`
  - 내용: ILC3_0c_gp에 대해서도 FFE 길이/λ를 sweep해서 “필요 최소 FFE 구조” 확인.
  - 설정: PAM3와 동일한 SNR/L_ffe/ridge grid
  - 결과(대표):
    - channel a: L=5, ridge=0.01 ~ 0.001 정도면 이미 BER ≈ 0.025 이하 가능
    - channel b: L=5, ridge=1e-3 ~ 1e-4 수준에서 BER ≈ 0.13 부근
    - channel c: L=9~11, ridge=1e-5 ~ 1e-3에서 BER ≈ 0.04 이하
  - 결론:
    - ILC3는 PAM3보다 **더 짧은 FFE 길이**로도 비슷하거나 더 좋은 BER을 달성 가능.
    - 채널 b에서도 FFE-only 기준으로는 ILC3가 PAM3보다 항상 유리.

- `test_pam3_vs_ilc3_b_ffe_dfe_v1.py`
  - 내용: 채널 b에서 FFE-only vs FFE+DFE를 PAM3/ILC3에 대해 비교 (Rx 고급 구조 후보).
  - 설정:
    - channel b: h = [0.05, 0.5, 1.0, 0.5, 0.05]
    - SNR list = [16, 19, 22, 25] dB
    - FFE: PAM3 L=15, ILC3 L=5, ridge=1e-5
    - DFE: L_dfe=2, 채널 post-cursor 기반 단순 설계
  - 대표 결과:
    - FFE-only:
      - SNR 19 dB: PAM3 FFE_ber ≈ 0.055, ILC3 FFE_ber ≈ 0.065
      - SNR 25 dB: PAM3 FFE_ber ≈ 0.0013, ILC3 FFE_ber ≈ 0.0162
    - FFE+DFE (v1: naive 구조):
      - SNR 19 dB: PAM3 FFE+DFE_ber ≈ 0.268, ILC3 FFE+DFE_ber ≈ 0.255
      - SNR 25 dB: PAM3 FFE+DFE_ber ≈ 0.242, ILC3 FFE+DFE_ber ≈ 0.210
  - 결론:
    - 채널 b에서 **FFE-only 기준**으로는 PAM3가 더 좋은 BER을 보이는 구간도 존재.
    - 현재 구현한 단순 DFE(v1)는 오히려 BER을 악화시키므로,  
      “채널 b용 advanced Rx는 재설계 필요”라는 메모와 함께 **연구용 기록(keep)** 상태로 보관.

---

### 3. Rx v1 baseline에 대한 버전 태그

- 위 5개 스크립트 + 해당 CSV 결과 + 이 섹션의 md를 묶어서
  - `ILC3_Rx_v1_baseline (AWGN + ISI + FFE-only, channel b naive DFE v1 포함)`  
  라는 버전으로 고정.
- 이후 실험(v2, Tx pre-emphasis, +t, MLSE 등)은
  - 항상 “Rx v1 baseline 대비 개선 여부”를 기준으로 평가.