# CoPBit Q11 – Modulation Modes & Application Mapping v0.1

## 1. 목적

- Q9, Q10에서 얻은 **M-PSK AWGN BER vs Es/N0, Eb/N0** 결과를 기반으로,
- CoPBit가 지원할 수 있는 여러 **운용 모드(M=2/4/8/16)**를 정의하고,
- 각 모드의 **대략적인 Eb/N0 요구치**와 **적합한 적용 분야(HBM, GDDR, 6G, 보안 버스 등)**를 1장으로 정리한다.

---

## 2. Q10 기반 요약 – M별 Eb/N0 vs pre-FEC BER

Q10 실험( AWGN-only, unit circle, bit-fair Eb/N0 ) 결과를 기반으로,
각 M에 대해 **pre-FEC BER ≈ 10⁻², 10⁻³ 근처**의 Eb/N0 영역을 대략 추정하면 다음과 같다.

- **M = 2 (BPSK / NRZ)**
  - pre-FEC BER ≈ 10⁻²: Eb/N0 ≈ 4.5–5 dB
  - pre-FEC BER ≈ 10⁻³: Eb/N0 ≈ 7 dB 전후

- **M = 4 (QPSK)**
  - pre-FEC BER ≈ 10⁻²: Eb/N0 ≈ 5 dB 근처
  - pre-FEC BER ≈ 10⁻³: Eb/N0 ≈ 7 dB 전후

- **M = 8 (8-PSK)**
  - pre-FEC BER ≈ 10⁻²: Eb/N0 ≈ 8–9 dB
  - pre-FEC BER ≈ 10⁻³: Eb/N0 ≈ 10.5 dB 근처

- **M = 16 (16-PSK = CoPBit 4bit 베이스라인)**
  - pre-FEC BER ≈ 10⁻²: Eb/N0 ≈ 11.5–12 dB
  - pre-FEC BER ≈ 10⁻³: Eb/N0 ≈ 13.5 dB 근처

요약하면:

- **M이 커질수록**
  - 같은 Eb/N0에서 BER이 나빠지고,
  - 목표 BER(예: 10⁻², 10⁻³)을 만족시키기 위한 Eb/N0 요구치가 증가한다.
- 이는 **순수 AWGN M-PSK 이론과 일치하는 베이스라인**이다.
- 이후 실제 CoPBit 시스템에서는 여기에
  - 진폭 1레벨 구조,
  - Kuramoto 기반 위상 추적,
  - 멀티레인 동기화(예: 16/64/1024 lanes),
  - FEC 적용
  을 조합하여 “실제 요구 Eb/N0”를 설계하게 된다.

---

## 3. CoPBit 운용 모드 정의 (M=2/4/8/16)

아래 표는 CoPBit가 지원할 수 있는 **대표적인 위상 모드**를 요약한 것이다.  
(여기서 Eb/N0 값은 Q10 AWGN-only 기준의 **대략적인 목표점**이다.)

| 모드 이름            | M   | bit/심볼 | 대략 pre-FEC BER ≈ 10⁻²   | 특징/용도 힌트                         |
|----------------------|-----|----------|----------------------------|----------------------------------------|
| CoPBit-M2 (Control)  |  2  | 1 bit    | Eb/N0 ≈ 4.5–5 dB          | 초저 BER, 제어/메타데이터, 장거리용   |
| CoPBit-M4 (Balanced) |  4  | 2 bit    | Eb/N0 ≈ 5 dB              | 안정성+속도 균형, 일반 링크           |
| CoPBit-M8 (HBM용 후보)|  8 | 3 bit    | Eb/N0 ≈ 8–9 dB            | 고속 IO/메모리(PAM4 대체 후보)        |
| CoPBit-M16 (Full)    | 16  | 4 bit    | Eb/N0 ≈ 11.5–12 dB        | 초고속 단거리, Kuramoto+멀티레인+FEC 전제 |

> 참고:  
> - M=8은 “3bit 위상 모드”로, 비트당 에너지 공정 기준에서  
>   기존 PAM4(2bit 진폭 변조)보다 높은 차수 변조이지만,  
>   진폭 1레벨 + 위상 기반이라는 구조적 이점이 있다.  
> - CoPBit-M8을 HBM/DDR/GDDR급 고속 메모리 인터페이스에서  
>   “PAM4 대체 후보”로 제안하는 것이 자연스러운 스토리가 된다.

---

## 4. HBM / GDDR / 6G / 보안 버스 관점에서의 CoPBit 매핑 (초안)

### 4.1 HBM / GDDR / 고속 IO (PAM4 대체)

- 기존
  - HBM, GDDR, SerDes 계열 인터페이스는
  - **PAM4** + EQ(FFE/DFE) + 강력한 FEC 조합이 일반적.
- CoPBit 제안
  - **CoPBit-M8 (3bit 위상 모드)** 또는 CoPBit-M16 (4bit 모드)을 사용.
  - 진폭 변조 없이 **위상만으로 신호 공간을 확장**.
  - 장점 후보:
    - 파워/전압 스윙이 NRZ 수준(1레벨) → 드라이버/수신단 단순화·저전력 기대
    - Kuramoto 기반 멀티레인 위상 동기화 → 채널/드리프트에 강한 구조로 설계 가능
    - FEC와 결합 시, PAM4 대비 동일 BER에서 Eb/N0 이득 또는  
      동일 Eb/N0에서 BER/거리 이득을 목표로 할 수 있음.

### 4.2 6G / 무선 프론트홀/백홀

- 무선/프론트홀 환경에서는
  - 채널 페이딩, 위상 노이즈, CFO 등 **위상 관련 impairments**가 핵심.
- CoPBit-M4 / M8 / M16:
  - QPSK/8-PSK/16-PSK 계열 구조와 호환되면서,
  - Kuramoto 스타일의 “집단 위상 동기화”를 통해
    - 대규모 MIMO / 멀티캐리어 환경에서
    - 공통 위상 오프셋, 드리프트를 **집단 추정/보정**하는 구조로 해석 가능.
- CoPBit의 강점:
  - “Kuramoto = 많은 위상 오실레이터들의 동기화 모델”을  
    - 실제 통신/메모리 PHY에 매핑하는 **새로운 구조 제안**으로 어필 가능.

### 4.3 암호/보안 버스 (1024-lane CoPBit)

- 1024 lane CoPBit 위상 버스를 가정하면:
  - 각 lane이 **M-PSK 위상 심볼**을 실어 나르고,
  - 전체 1024개의 위상 패턴(3D 구형 위상 분포)을  
    - 암호 키, 난수, 마스크 패턴 등으로 활용 가능.
- 아이디어:
  - CoPBit-M2/M4 모드로 낮은 BER을 유지하면서,
  - 1024 lane × 시간 축으로 “3D 회전하는 위상 구(sphere)” 상에 키/토큰을 숨기는 구조.
- 이 때 Q10의 M-PSK Eb/N0 베이스라인은:
  - “보안 버스 하나당 허용 가능한 Eb/N0 조건에서  
     어느 정도 BER/오류율까지 FEC 없이 버틸 수 있는지”  
    를 정량적으로 설명하는 재료가 된다.

---

## 5. 향후 확장 (Q12 이후 아이디어)

1. **Q12: CoPBit-M8 vs PAM4 (채널 a/b/c + EQ + Eb/N0 기준)**
   - ILC3에서 사용했던 채널 a/b/c, FFE, DLL 등을 가져와서
   - PAM4 vs CoPBit-M8(3bit PSK) 비교 시뮬레이션 설계.

2. **Q13: CoPBit-M16 + 멀티레인 Kuramoto + FEC 가상 모델**
   - 16/64/1024 lanes에서,
   - Kuramoto 기반 위상 추적 + 단순 FEC 모델을 얹은 BER vs Eb/N0 곡선.

3. **Q14: “CoPBit 운용 모드 테이블” 특허/사업계획용 슬라이드**
   - 본 문서(Q11) 내용을 슬라이드 1~2장 구조로 재배열.

---