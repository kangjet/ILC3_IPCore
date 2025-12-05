# CoPBit Q20c – PAM4 mid-ISI FFE-only Baseline (Channel-b, Single-lane) v0.1

- **문서명**: `CoPBit_Q20c_PAM4_midISI_FFEonly_baseline_v0.1.md`  
- **실험 스크립트**: `copbit_q20c_pam4_midISI_ffe_ls_baseline_v0.py`  
- **목적**:  
  - Channel-b 5-tap mid-ISI + AWGN 채널에서 **단일-lane PAM4 + FFE-only** 구조의 BER vs Eb/N0 기준선 확보  
  - 이후 **M8/CoPBit, Kuramoto, p_ref, multi-lane 설계**와 비교할 때 쓰는 **메모리/버스용 PAM4 baseline** 정의

---

## 1. 채널/변조/시스템 설정

### 1.1 채널 – Channel-b mid-ISI (5-tap)

- 사용 채널 (ILC3/CoPBit Q13/Q14와 동일 계수):

\[
h_{\text{midISI}} = [0.04075696,\ 0.40756957,\ 0.81513915,\ 0.40756957,\ 0.04075696]
\]

- 특징:
  - 중앙 심볼에 에너지 집중, 양 옆으로 강한 ISI가 퍼져 있는 **mid-ISI 채널**
  - 메모리/버스 환경에서 “심하게 꼬인 라인”을 모델링

### 1.2 변조 – PAM4

- **PAM4 (Gray mapping, 2 bit/sym)**  
- 레벨: \([-3,\ -1,\ +1,\ +3]\)  
- 예시 맵핑(인덱스→비트→레벨):
  - 0 → 00 → -3  
  - 1 → 01 → -1  
  - 2 → 11 → +1  
  - 3 → 10 → +3  

### 1.3 잡음 및 Eb/N0 설정

- **AWGN 채널**
- Eb/N0 리스트:

\[
\text{Eb/N0}_{dB} = [8,\ 10,\ 12,\ 14,\ 16,\ 18,\ 20]
\]

- 관계:
  - \(\text{Es/N0} = \text{Eb/N0} \times \text{bits\_per\_sym} = \text{Eb/N0} \times 2\)
  - Es 기준으로 잡음 분산 계산 후 채널 출력에 AWGN 추가

### 1.4 Equalizer 구조 – FFE-only (LS 학습)

- 구조:
  - 단일-lane PAM4
  - **FFE-only (11-tap)**
  - DFE 없음, PLL 없음, Kuramoto/p_ref 없음

- 주요 파라미터:
  - `n_sym       = 200000`  
  - `ffe_len     = 11`  
  - `train_frac  = 0.5`  (앞 50% 심볼만 학습에 사용)  
  - `eq_mode     = "ls"`  
  - `dd_after_tr = False`  
  - `mu_ffe      = 0.001` (LS 모드에서는 의미 거의 없음, LMS용 파라미터)  
  - `w_clip      = 10.0` (LMS/NLMS일 때만 유효)  
  - `seed        = 1`  

- LS 학습 개념:

  1. 잡음 없는 채널 출력 \(x_{\text{chan}}\) 생성  
  2. 입력: \(x_{\text{real}} = \Re\{x_{\text{chan}}\}\), 타깃: \(d_{\text{real}} = \Re\{x_{\text{sym}}\}\)  
  3. 공통 스케일 정규화:
     - \(x_{\text{norm}} = x_{\text{real}} / \text{std}(x_{\text{real}})\)  
     - \(d_{\text{norm}} = d_{\text{real}} / \text{std}(x_{\text{real}})\)
  4. 학습 구간에 대해 입력 행렬 \(U\)와 타깃 벡터 \(d_{\text{vec}}\) 구성  
  5. Ridge-regularized LS 해:

\[
R = U^\top U,\quad p = U^\top d_{\text{vec}}
\]

\[
R_{\text{reg}} = R + \lambda I,\quad
w = R_{\text{reg}}^{-1} p
\]

     - \(\lambda = 10^{-3} \cdot \text{trace}(R)/L + 10^{-9}\)  
     - 수치가 완전히 망가질 경우에는 **중앙 탭=1, 나머지 0인 단위 임펄스 FFE**로 폴백
  6. 학습된 \(w\)를 전체 시퀀스에 적용 → equalized 심볼 \(z_{\text{all}}\)에서 앞부분 버리고 BER 계산

---

## 2. BER vs Eb/N0 결과 (Q20c PAM4 LS-FFE Baseline)

### 2.1 실행 커맨드

```bash
python copbit_q20c_pam4_midISI_ffe_ls_baseline_v0.py \
  --n_sym 200000 \
  --ebn0_list "8,10,12,14,16,18,20" \
  --ffe_len 11 \
  --train_frac 0.5 \
  --eq_mode ls \
  --seed 1
```

### 2.2 결과 테이블

| Eb/N0 (dB) | BER_PAM4_FFE |
|-----------:|-------------:|
| 8.0        | 0.224031202  |
| 10.0       | 0.218773439  |
| 12.0       | 0.216138307  |
| 14.0       | 0.214380719  |
| 16.0       | 0.212948147  |
| 18.0       | 0.212380619  |
| 20.0       | 0.211830592  |

- Eb/N0 ↑ 해도 BER이 **0.224 → 0.212** 수준에서 천천히만 감소  
- 20 dB에서조차 **BER ≈ 0.21** 수준으로 바닥 형성

---

## 3. 해석 – “FFE-only 구조의 하드 캡”

### 3.1 구조적 한계

- 조건:
  - 단일-lane PAM4  
  - Channel-b mid-ISI (강한 ISI)  
  - FFE-only(11-tap) + AWGN, DFE/PLL/Kuramoto 없음  

- 관찰:
  - SNR을 크게 높여도 **ISI가 완전히 풀리지 않음**  
  - 이 결과는 채널이 가진 강한 자기 간섭 때문에,  
    **선형 FFE 한 개로는 메모리/버스 mid-ISI 채널을 “깨끗한 1e-3 레벨”까지 정리하는 건 사실상 불가능**하다는 것을 보여줌

### 3.2 ILC3 쪽과의 개념적 차이

- ILC3에서의 PAM4 실험은:
  - Fractional EQ, 여러 보정 블록, 경우에 따라 DFE/PLL/FEC를 염두  
  - “통신 채널 기준 BER vs SNR” 느낌에 가깝게 설계

- Q20c의 PAM4 baseline은:
  - **메모리/버스 mid-ISI 채널에서, “딱 FFE 하나”만 넣었을 때 한계**를 보는 실험  
  - CoPBit/PPU/멀티-lane 설계와 비교할 때  
    “가장 단순한 PAM4 baseline”으로 쓰는 용도

### 3.3 이 baseline의 역할

- 앞으로 이 표는 다음 비교의 기준축으로 사용:

1. **동일 채널 + 동일 FFE 구조에서**
   - 1-lane PAM4 vs 1-lane M8/CoPBit 비교  
   - “진폭만 쓰는 방식”과 “복소 평면(진폭+위상)까지 쓰는 방식”의 차이 수치화

2. **동일 mid-ISI 채널 + FFE + Kuramoto/p_ref 추가**
   - 현재까지 정리된 `PhaseLock_std`와 연결  
   - mid-ISI 환경에서도 **p_ref + Kuramoto**가 어느 정도까지 도움을 줄 수 있는지 평가

---

## 4. 한 줄 요약

> **Q20c 결론**: Channel-b mid-ISI + AWGN 환경에서 단일-lane PAM4에 11-tap FFE-only(LS 학습)를 적용하면, Eb/N0를 20 dB까지 올려도 BER은 약 0.21 정도에서 바닥을 형성한다.  
> 이 값은 “메모리/버스용 mid-ISI 채널에서 단순 PAM4+FFE-only 구조가 가지는 구조적 하드 캡”이며, 이후 M8/CoPBit 및 Kuramoto 기반 위상 동기화 구조와의 성능 비교를 위한 **기준선(baseline)**으로 사용된다.
