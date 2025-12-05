## 2. BER vs SNR 결과

### 2.1 ISI α = 0.3, n_sym = 100k

명령:
```bash
python copbit_q5_kuramoto_ber_v0.py \
  --n_sym 100000 \
  --snr_list 10,12,14,16,18 \
  --isi_alpha 0.3 \
  --fec_threshold 1e-2
 SNR [dB]
BER_base
BER_kura
FEC_OK_base
FEC_OK_kura
10
2.564e-01
3.005e-01
False
False
12
2.457e-01
2.951e-01
False
False
14
2.393e-01
2.928e-01
False
False
16
2.348e-01
2.924e-01
False
False
18
2.379e-01
2.952e-01
False
False

 2.2 ISI α = 0.3, n_sym = 200k

명령:
python copbit_q5_kuramoto_ber_v0.py \
  --n_sym 200000 \
  --snr_list 10,12,14,16,18 \
  --isi_alpha 0.3 \
  --fec_threshold 1e-2

SNR [dB]
BER_base
BER_kura
FEC_OK_base
FEC_OK_kura
10
2.564e-01
3.008e-01
False
False
12
2.452e-01
2.962e-01
False
False
14
2.380e-01
2.921e-01
False
False
16
2.363e-01
2.930e-01
False
False
18
2.380e-01
2.950e-01
False
False

2.3 ISI α = 0.4, n_sym = 200k
명령:
python copbit_q5_kuramoto_ber_v0.py \
  --n_sym 200000 \
  --snr_list 10,12,14,16,18 \
  --isi_alpha 0.4 \
  --fec_threshold 1e-2
 SNR [dB]
BER_base
BER_kura
FEC_OK_base
FEC_OK_kura
10
2.952e-01
3.168e-01
False
False
12
2.954e-01
3.139e-01
False
False
14
2.985e-01
3.100e-01
False
False
16
3.035e-01
3.097e-01
False
False
18
3.083e-01
3.104e-01
False
False

 ## 2. 이 숫자들의 의미 정리

### 2.1 가장 먼저 보이는 것

- **BER_base ≈ 0.24~0.3**  
- **BER_kura ≈ 0.29~0.31 (항상 더 나쁨)**  
- SNR 10~18 dB 어디에서도 **1e-2 임계치 근처에도 못 감**  
- ISI를 **전혀 보상하지 않은 상태에서** “순수 위상 + 최근접 디코더”만 쓰고 있기 때문에,
  사실상 심볼의 4개 레벨이 **ISI에 의해 뒤섞인 상태에서 억지로 phase만 보고 찍는 구조**야.

즉, 이 Q5 실험은:

> **“AWGN + 꽤 강한 1-tap ISI(α=0.3~0.4)를 걸어놓고, 아무 EQ 없이 CoPBit 위상만으로 억지 디코딩하면 얼마나 망가지는지 보는 케이스”**

에 가깝고,  
지금 단계에서는 “실용 링크”가 아니라 “ISI + naive decoder의 한계”를 보는 **네거티브 베이스라인**이라고 보면 돼.

같은 조건으로 16QAM, PAM4 돌려도  
**EQ 없이 0.25~0.3 수준 BER** 나오는 건 이상한 게 아니고,  
지금 스크립트 구조 자체가 일부러 그 정도로 빡빡한 채널을 줘놓은 상태.

### 2.2 왜 Kuramoto 쪽이 더 나쁜가?

지금 Q5의 Kuramoto 부분은:

1. **일단 baseline 하드 결정**으로 k_hat을 뽑은 다음  
2. 그 결과를 기반으로 클러스터별 mean phase를 계산하고  
3. 그 mean을 빼고 다시 4포인트에 맞춰 재디코딩

이라는 “After-the-fact 보정” 구조라서,

- baseline BER가 이미 0.24~0.3로 **꽤 망가진 상태**  
- 이 잘못된 결정이 클러스터 mean 계산에 그대로 들어감  
- 결과적으로 **“잘못된 방향으로 위상 shift”**가 걸려서 BER이 더 나빠지는 상황

이 되는 거라서,  
지금 Q5 구현은 **“Kuramoto 아이디어의 맛보기 근사”**일 뿐,  
Q4에서 했던 **연속시간 Kuramoto 동역학 기반의 진짜 동기 PLL 구조**는 아니라서,  
**Kuramoto의 잠재력**을 여기서 보고 있다고 보긴 어려워.

요약하면:

> Q5 결과 = “ISI + naive phase decoder + naive cluster mean 보정”은  
> CoPBit를 살려주는 구조가 아니다 → EQ/추가 설계가 필수.

### 2.3 FEC 관점에서의 결론

- 우리가 정한 pre-FEC BER 임계 `1e-2` 기준에서 보면  
  **어느 SNR에서도 FEC 커버 영역에 들어가지 않는다.**
- 따라서 **“CoPBit 1-lane + 위상만 보는 naive 디코더 + ISI α=0.3/0.4”** 조건은  
  FEC를 얹는다고 해도 지금 그대로 실용 수준으로 쓰기 어렵다는 게 명확하게 드러난 셈.

이걸 노트에 한 줄로 요약하면:

> “Q5 실험은 ‘ISI가 있는 실제 채널에서 아무 EQ 없이 CoPBit 4bit를 쓸 경우 BER이 어디까지 망가지나’ 보는 네거티브 케이스이고, Kuramoto를 단순 cluster mean 보정으로만 쓰면 오히려 BER이 악화된다는 점을 확인하였다. 즉, ISI 보상(EQ/DFE) 또는 Kuramoto를 포함한 보다 정교한 위상 추적 구조가 필수이다.”

---

## 3. 지금 단계에서의 포지셔닝

지금까지 CoPBit 실험 흐름은 이렇게 정리할 수 있어:

1. **Q1~Q3**  
   - 4bit(16포인트) 위상 맵핑 / 디코딩 구조  
   - 단순 위상 잡음(AWGN in angle) 환경에서 **BER ~1e-2** 도달 가능함을 확인  
2. **Q4**  
   - Kuramoto 클러스터 동기화가  
     “동일 클러스터 안의 위상들을 얼마나 잘 모아주는지(집단 위상 R≈1)” 확인  
   - 여기까지는 **“순수 위상 + Kuramoto 자체는 잘 동작한다”** 수준  
3. **Q5**  
   - 이제 실제 채널 스타일(AWGN + ISI)로 한 스텝 더 간 것  
   - **EQ 없는 상태** + **naive Kuramoto-mean 보정**으로는
     FEC 임계에 도달 불가, Kuramoto도 오히려 BER 악화  
   - 이게 보여주는 메시지는:
     - CoPBit도 결국 **PAM4/ILC3/16QAM과 마찬가지로 채널 EQ/DFE 설계가 빠지면 답이 없다**  
     - Kuramoto를 쓰려면 “Q4 스타일 동역학 + EQ/메모리 구조”까지 같이 붙여야 진짜 힘을 발휘한다는 것

그래서 Q5는 “망한 실험”이 아니라,  
**“CoPBit + ISI 채널에서 필요한 블록들을 정확히 확인해 준 체크포인트”**라고 보면 딱 좋아.

---

### 다음 스텝에 대한 제안 (간단 요약)

- 이 Q5 결과는 md에 **그대로 ‘네거티브 베이스라인’으로 기록**해 두고,
- 다음 Q6에서는 선택지 두 개 중 하나:

1. **EQ를 붙인 CoPBit vs PAM4/ILC3 비교**  
   - ILC3에서 썼던 a/b/c 3-tap 채널 그대로 가져와서  
   - FFE or 간단 DFE를 추가한 상태에서  
   - PAM4 / ILC3 / CoPBit 4bit를 **동일 조건**으로 비교  
2. **Kuramoto 동역학 + 채널 메모리 결합 쪽을 먼저 파고들기**  
   - 지금 Q5의 ‘사후 cluster mean’ 구조 대신,  
   - Q4에서 쓰던 Kuramoto 업데이트를 시퀀스 전체에 적용하면서 ISI까지 포함하는 쪽으로 확장

둘 중 어디부터 할지는 전략 문제.

## Q5-AWGN Baseline (isi_alpha = 0.0)

실험 조건:
- CoPBit 4bit / 16-point phase constellation (Q1/Q3 맵핑)
- 채널: AWGN only (ISI 없음, `isi_alpha = 0.0`)
- 디코더:
  - BER_base  : 최근접 위상 디코더 (Kuramoto 보정 없음)
  - BER_kura  : Kuramoto-style cluster mean 보정 후 재디코딩 (참고용, AWGN에서는 비권장)
- 심볼 수: `n_sym = 200000`
- FEC 임계: pre-FEC BER ≤ 1e-2 를 “강 FEC로 커버 가능” 구간으로 정의

실행 명령 예:
```bash
python copbit_q5_kuramoto_ber_v0.py \
  --n_sym 200000 \
  --snr_list 17,18,19 \
  --isi_alpha 0.0 \
  --fec_threshold 1e-2

  SNR[dB]
BER_base
BER_kura
FEC_OK_base
FEC_OK_kura
17.0
2.428e-02
2.262e-01
False
False
18.0
1.336e-02
2.225e-01
False
False
19.0
6.365e-03
2.212e-01
True
False

