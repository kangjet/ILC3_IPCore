# ILC3_IPCore RTL v0.1 – README

ILC3 IPCore 1-lane / x8 RTL v0.1 상태를 정리한 레포용 README 초안이다.  
**목표:**  
- 현재 RTL/채널 테스트 환경을 v0.1 스냅샷으로 고정  
- 이후 특허·논문·Product Spec 문서에서 “참조 레포 버전”으로 사용할 수 있도록 기준점 제공

---

## 1. 디렉터리 구조 (v0.1 기준)

레포 루트: `ILC-4_CoPBit/ILC3_IPCore/rtl`

```text
rtl/
├── core/
│   ├── ilc3_tx_core.v          // ILC3 0-code Tx 코어 (심볼 → 파형 인터페이스)
│   ├── ilc3_rx_core.v          // ILC3 0-code Rx 코어 (채널 출력 → 심볼/에러)
│   ├── ilc3_ipcore_top.v       // 1-lane IPCore Top
│   └── ilc3_ipcore_x8_top.v    // x8 IPCore Top (8 lane 래핑)
└── sim/
    ├── ilc3_channel_model.v            // 간단 채널 + 노이즈 모델
    ├── tb_ilc3_loopback.v              // 구(舊) 단일 코어 루프백 TB (참고용)
    ├── tb_ilc3_loopback_noise.v        // 노이즈 포함 단일 코어 TB (참고용)
    ├── tb_ilc3_ipcore_loopback.v       // 1-lane IPCore Top 루프백 TB (clean/noise)
    └── tb_ilc3_ipcore_x8_loopback.v    // x8 IPCore Top 루프백 TB (clean/noise)
```

> 참고: `build/`, `ilc3_loop_*`, `ilc3_ipcore_loop_*` 바이너리는 시뮬 실행 시 생성되는 산출물로, v0.1 스냅샷에는 포함하지 않아도 됨.

---

## 2. 핵심 모듈 설명

### 2.1 `core/ilc3_tx_core.v`

- 입력:  
  - `clk`, `rst_n`  
  - `sym_in[1:0]`, `sym_valid`  
- 출력:  
  - `amp_out[AMP_WIDTH-1:0]`, `amp_valid`
- 기능:
  - 2-bit ILC3 심볼(0/1/2/3)을 내부 0-code 맵핑에 따라 진폭 코드로 변환
  - IPCore Top에서 lane 별 Tx 프론트엔드로 사용

### 2.2 `core/ilc3_rx_core.v`

- 입력:  
  - `clk`, `rst_n`  
  - `amp_in[AMP_WIDTH-1:0]`, `amp_valid`
- 출력:  
  - `sym_out[1:0]`, `sym_valid`  
  - (필요 시) 에러 카운터/상태 신호 확장 가능
- 기능:
  - 채널/ADC 출력에 해당하는 진폭 코드를 받아 2-bit ILC3 심볼로 판정
  - 0-code guard phase 구조를 RTL 수준에서 구현

### 2.3 `core/ilc3_ipcore_top.v` (1-lane)

- 1-lane IPCore를 위한 Top 래퍼
- 인터페이스(개략):
  - Tx 쪽: `tx_data[1:0]`, `tx_valid`, `tx_ready`
  - Rx 쪽: `rx_data[1:0]`, `rx_valid`, `rx_ready`
- 내부 구성:
  - `ilc3_tx_core` → `ilc3_channel_model` → `ilc3_rx_core`
- TB (`tb_ilc3_ipcore_loopback.v`)와 함께:
  - clean 채널에서 **심볼 0/1/2/3 루프백 PASS**
  - 노이즈 프리셋(lvl1, lvl_real)에서 에러 카운트/BER 거친 검증

### 2.4 `core/ilc3_ipcore_x8_top.v` (x8 lanes)

- 8 lane IPCore를 하나의 블록으로 묶는 Top
- 인터페이스(개략):
  - `tx_data[2*NUM_LANES-1:0]`, `tx_valid[NUM_LANES-1:0]`, `tx_ready[NUM_LANES-1:0]`
  - `rx_data[2*NUM_LANES-1:0]`, `rx_valid[NUM_LANES-1:0]`, `rx_ready[NUM_LANES-1:0]`
- 내부 구성:
  - `GEN_LANE` generate 블록으로 1-lane IPCore를 8개 인스턴스
  - 채널 파라미터(`CH_GAIN_NUM/DEN`, `CH_OFFSET`, `CH_ADD_NOISE`, `CH_NOISE_LSB`)를 공통으로 각 lane에 전달
- TB (`tb_ilc3_ipcore_x8_loopback.v`)와 함께:
  - 8 lane 모두 clean 채널 루프백 PASS
  - lvl_real 노이즈 프리셋에서 x8 기준 BER 거친 검증 가능

### 2.5 `sim/ilc3_channel_model.v`

- 채널 + 노이즈 간단 모델
- 주요 파라미터:
  - `GAIN_NUM`, `GAIN_DEN`: 스케일링
  - `OFFSET`: DC 오프셋
  - `ADD_NOISE`: 노이즈 모드 선택 (0: clean, 1: lvl1, 2: lvl2, 3: lvl_real …)
  - `NOISE_LSB`: 노이즈 크기 단위
- lvl_real 모드(ADD_NOISE=3)는 RTL 기준으로 대략 **pre-FEC BER ~1e-2** 근처가 되도록 튜닝한 버전 (랜덤 kick 기반).

---

## 3. 대표 시뮬레이션 커맨드

### 3.1 공통 사항

- 작업 디렉터리:
  ```bash
  cd /Users/kangjet/ILC-4_CoPBit/ILC3_IPCore/rtl
  ```
- 사용 툴:
  - Icarus Verilog (`iverilog`, `vvp`)
- TB 내 매크로:
  - `tb_ilc3_ipcore_loopback.v`, `tb_ilc3_ipcore_x8_loopback.v` 상단에
    - `TB_N_SYM` (기본 1024)
    - `TB_CH_ADD_NOISE` (기본 0 – clean)
    - `TB_CH_NOISE_LSB` (기본 1)
  - 필요 시 `-DTB_N_SYM=...`, `-DTB_CH_ADD_NOISE=...` 형태로 override

> **주의:** 매크로 정의(`-D...`)는 `iverilog` 커맨드에서 **파일 리스트 뒤**에 두어야 정상 처리된다.

---

### 3.2 1-lane IPCore – clean 채널

```bash
cd /Users/kangjet/ILC-4_CoPBit/ILC3_IPCore/rtl

iverilog -g2012 -o ilc3_ipcore_loop_clean \
  core/ilc3_tx_core.v \
  core/ilc3_rx_core.v \
  core/ilc3_ipcore_top.v \
  sim/ilc3_channel_model.v \
  sim/tb_ilc3_ipcore_loopback.v

vvp ilc3_ipcore_loop_clean
```

- 기대 로그:
  - `N_SYM   = 1024`
  - `err_cnt = 0`
  - `RESULT  = PASS`

### 3.3 1-lane IPCore – 노이즈 lvl1 (스트레스용)

```bash
iverilog -g2012 -o ilc3_ipcore_loop_noise_lvl1 \
  core/ilc3_tx_core.v \
  core/ilc3_rx_core.v \
  core/ilc3_ipcore_top.v \
  sim/ilc3_channel_model.v \
  sim/tb_ilc3_ipcore_loopback.v \
  -DTB_CH_ADD_NOISE=1 \
  -DTB_N_SYM=10000

vvp ilc3_ipcore_loop_noise_lvl1
```

- 기대 로그(예시):
  - `N_SYM   = 10000`
  - `err_cnt ≈ 1500` 수준 (BER ≈ 1.5e-1)
  - 스트레스 테스트/디버그용 프리셋

### 3.4 1-lane IPCore – 노이즈 lvl_real (실제 설계용 약한 노이즈 후보)

```bash
iverilog -g2012 -o ilc3_ipcore_loop_noise_lvl_real \
  core/ilc3_tx_core.v \
  core/ilc3_rx_core.v \
  core/ilc3_ipcore_top.v \
  sim/ilc3_channel_model.v \
  sim/tb_ilc3_ipcore_loopback.v \
  -DTB_CH_ADD_NOISE=3 \
  -DTB_N_SYM=100000

vvp ilc3_ipcore_loop_noise_lvl_real
```

- 기대 로그(예시):
  - `N_SYM   = 100000`
  - `err_cnt ≈ 1.0e3 ~ 2.0e3` 수준 (BER ≈ 1e-2)
  - Q18/Q20에서 사용한 **pre-FEC BER ≈ 1e-2** 근처와 대응시키기 위한 RTL 채널 프리셋

---

### 3.5 x8 IPCore – clean 채널

```bash
iverilog -g2012 -o ilc3_ipcore_x8_loop_clean \
  core/ilc3_tx_core.v \
  core/ilc3_rx_core.v \
  core/ilc3_ipcore_top.v \
  core/ilc3_ipcore_x8_top.v \
  sim/ilc3_channel_model.v \
  sim/tb_ilc3_ipcore_x8_loopback.v

vvp ilc3_ipcore_x8_loop_clean
```

- 기대 로그:
  - `NUM_LANES = 8`
  - `N_SYM     = 1024`
  - `lane 0..7 err_cnt = 0`
  - `RESULT    = PASS`

### 3.6 x8 IPCore – 노이즈 lvl_real

```bash
iverilog -g2012 -o ilc3_ipcore_x8_loop_noise_lvl_real \
  core/ilc3_tx_core.v \
  core/ilc3_rx_core.v \
  core/ilc3_ipcore_top.v \
  core/ilc3_ipcore_x8_top.v \
  sim/ilc3_channel_model.v \
  sim/tb_ilc3_ipcore_x8_loopback.v \
  -DTB_CH_ADD_NOISE=3 \
  -DTB_N_SYM=100000

vvp ilc3_ipcore_x8_loop_noise_lvl_real
```

- 기대 로그(오늘 최종 상태 기준):
  - `NUM_LANES = 8`
  - `N_SYM     = 100000`
  - `lane 0..7 err_cnt = 0` (현재 튜닝 상태)
  - 현재 lvl_real 튜닝은 “RTL 상에서 대략 1e-2 근처를 목표로 하는 후보”이며,  
    채널 모델/파라미터 조정에 따라 추후 재조정 가능.

---

## 4. v0.1 스냅샷 의미

이 README와 함께 다음이 준비되면, 이를 **“ILC3_IPCore RTL v0.1 스냅샷”**으로 정의할 수 있다.

1. `core/` + `sim/` RTL 소스
2. 본 README (`README_ILC3_IPCore_v0.1.md`)
3. 시뮬 바이너리/로그 예시 (옵션):
   - `ilc3_ipcore_loop_clean`, `_noise_lvl1`, `_noise_lvl_real`
   - `ilc3_ipcore_x8_loop_clean`, `_noise_lvl_real`
   - 각 실행 로그를 `/logs/rtl_v0.1/` 등으로 모아두면 좋음

이 스냅샷은 이후 문서들에서 다음과 같이 인용할 수 있다.

- **“ILC3 IPCore RTL & Channel Verification v1.0”**:  
  > 실험/검증에 사용된 RTL은 `ILC3_IPCore RTL v0.1` 스냅샷을 기반으로 함.
- **“ILC3 x8 IPCore Product Spec v0.1”**:  
  > 블록 다이어그램 및 I/F 정의는 `ILC3_IPCore RTL v0.1` 구현을 기준으로 작성됨.

---

## 5. 다음 단계와 연계

Step 1 (본 README 정리) 이후의 자연스러운 다음 단계는:

1. **Product Spec v0.2**에서:
   - 운영 모드 (Normal / Training / BIST/Loopback) 정리
   - 에러/상태 레지스터 개념 추가
   - HBM/SoC 연동 예시 다이어그램 보강

2. **Master Reference Package** 구성:
   - 링크 시뮬(Q18/Q19/Q20) 결과 CSV/MD
   - `ILC3 IPCore RTL & Channel Verification v1.0` docx
   - `ILC3 x8 IPCore Product Spec v0.1/0.2` docx
   - 본 README

이렇게 묶으면, 특허·논문·파트너사 공유용 레퍼런스 패키지로 바로 활용 가능하다.
