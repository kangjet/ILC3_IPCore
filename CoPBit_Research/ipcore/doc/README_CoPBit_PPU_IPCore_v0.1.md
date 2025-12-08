---
## IPCore v0.1 baseline 요약

IPCore v0.1은 CoPBit PPU에서 사용할 **3D 인덱스 연산 primitive 세트**의  
최초 기준선(baseline) 버전으로, 다음 내용을 포함한다.

### 1) 연산 primitive 세트

- 도메인 파라미터
  - `M = 8`  (3비트 인덱스 공간, `0..7`)
  - `WIDTH = 3`  (`M=8`에 대응하는 인덱스 비트폭)
  - `NLANES = 16`  (타일/스트림 공통 lane 수)
- 제공 코어 (모두 `op_error = 0` 전수 검증 완료)
  - 3D-ADD
    - index  : `copbit_ppu_3d_add_core`
    - tile   : `copbit_ppu_3d_add_tile`
    - stream : `copbit_ppu_3d_add_stream`
  - 3D-MUL
    - index  : `copbit_ppu_3d_mul_core`
    - tile   : `copbit_ppu_3d_mul_tile`
    - stream : `copbit_ppu_3d_mul_stream`
  - 3D-LUT
    - index  : `copbit_ppu_3d_lut_core`
    - tile   : `copbit_ppu_3d_lut_tile`
    - stream : `copbit_ppu_3d_lut_stream`

이 세트는 CoPBit PPU 상위 라운드 함수(암호/필터/레이더 등)를 구성할 때  
공통으로 재사용되는 **3D 인덱스 ALU 기본 블록**으로 정의한다.

### 2) 인터페이스 및 파라미터 baseline

- 공통 파라미터
  - `M`, `WIDTH`, `NLANES` 정의 및 기본값은 본 문서의  
    “공통 파라미터 규칙” 절을 기준으로 한다.
- index core
  - 순수 조합 논리, 단일 인덱스 입·출력 (`*_idx`)
- tile core
  - `*_idx_flat` packed bus와 `NLANES` 파라미터를 사용
  - `generate for` 기반 lane 확장 구조를 공통 규칙으로 사용
- stream core
  - 공통 ready/valid 스트림 인터페이스:
    - 입력: `clk`, `rst_n`, `in_valid`, `in_ready`, `in_*_flat`
    - 출력: `out_valid`, `out_ready`, `out_*_flat`
  - 최소 1클럭 파이프라인 레이턴시를 갖는 1-stage 구조를 v0.1 표준으로 사용

향후 추가되는 모든 IPCore(3D-PHASE, REDUCE, ACCUM 등)는  
위 인터페이스/파라미터 규칙을 따르는 것을 원칙으로 한다.

### 3) v0.1에서 동결(freeze)하는 항목

- 모듈명
  - `copbit_ppu_3d_add_*`, `copbit_ppu_3d_mul_*`, `copbit_ppu_3d_lut_*`
- 포트 구성 및 의미
  - 각 코어의 포트 이름, 방향, ready/valid 시맨틱
- 기본 파라미터 조합
  - `M=8`, `WIDTH=3`, `NLANES=16` 구성을 v0.1의 공식 레퍼런스로 사용

이후 v0.2 이상 버전에서 기능 확장(추가 primitive, 라운드 함수, 키 스케줄 등)을  
진행하더라도, v0.1에서 정의한 IPCore primitive는 **호환성을 유지하는 기준선**으로 삼는다.


# CoPBit PPU IPCore v0.1 – 3D Index 연산 코어 개요

본 문서는 CoPBit PPU에서 사용되는 3D 인덱스 기반 IPCore의 공통 인터페이스 규칙과  
현재 구현된 3D-ADD 계열 코어 목록을 정리한다. 모든 코어는 향후 확장을 고려하여  
동일한 파라미터/신호 규칙을 따르는 것을 원칙으로 한다.

---

## 1. 공통 파라미터 규칙

- `M`  
  - 의미: 인덱스 공간의 크기 (예: M=8 → 0..7)  
  - 기본값: `8` (M8 3D 인덱스)

- `WIDTH`  
  - 의미: 인덱스를 표현하는 비트 폭 (`WIDTH = ceil(log2(M))`)  
  - 기본값: `3` (M=8일 때 3비트)

- `NLANES`  
  - 의미: 병렬 처리되는 레인(lane)의 개수  
  - 기본값: `16`

---

## 2. 스트림 인터페이스 규칙 (IPCore 표준)

스트림형 코어(예: `copbit_ppu_3d_add_stream`)는 다음 신호를 기본 인터페이스로 사용한다.

- 공통 제어
  - `clk` : 상승 에지 기준 동기 클럭
  - `rst_n` : 비동기 Low-active 리셋 (0 → 초기화, 1 → 동작)

- 입력 스트림
  - `in_valid` : 입력 데이터 유효 플래그
  - `in_ready` : 코어가 새로운 입력을 수락할 수 있음을 나타내는 플래그  
  - `in_*`     : 입력 데이터 버스 (예: `in_a_idx_flat`, `in_b_idx_flat`)

- 출력 스트림
  - `out_valid` : 출력 데이터 유효 플래그
  - `out_ready` : 출력을 소비 측에서 수락할 준비가 되었음을 나타내는 플래그  
  - `out_*`     : 출력 데이터 버스 (예: `out_y_idx_flat`)

### 2.1 핸드셰이크 동작 원칙

- 입력 수락 조건:
  - `in_valid = 1` 이고 `in_ready = 1` 인 클럭에서만 입력 데이터가 래치된다.
- 출력 소비 조건:
  - `out_valid = 1` 이고 `out_ready = 1` 인 클럭에서만 출력 데이터가 소비된 것으로 간주된다.
- 3D-ADD 스트림 코어(`copbit_ppu_3d_add_stream`)의 경우:
  - 내부 1-stage 파이프라인을 사용하며,
  - `in_valid & in_ready`로 입력이 수락된 후 **최소 1클럭 latency**를 갖는다.
  - back-pressure (`out_ready = 0`)에 따라 유효 데이터 유지 시간이 늘어날 수 있다.

---

## 3. 인덱스/타일 네이밍 규칙

3D 인덱스 기반 IPCore에서는 다음과 같은 네이밍 규칙을 따른다.

- 단일 인덱스 신호
  - `*_idx` : 단일 인덱스 (예: `a_idx`, `b_idx`, `y_idx`)  
  - 폭: `[WIDTH-1:0]`

- 타일(멀티레인) 인덱스 신호
  - `*_idx_flat` : NLANES개의 인덱스를 패킹한 버스  
  - 폭: `[NLANES*WIDTH-1:0]`  
  - lane g에 대한 인덱스 비트 범위:
    - `[(g+1)*WIDTH-1 : g*WIDTH]`

- 스트림형 입력/출력
  - 입력: `in_a_idx_flat`, `in_b_idx_flat`, ...  
  - 출력: `out_y_idx_flat`, ...

향후 3D-MUL, LUT, phase 코어 등에서도 동일 규칙을 준수한다.

---

## 4. 레이턴시 규칙

- `copbit_ppu_3d_add_core` (Core #0: scalar index core)
  - 조합 논리(combinational), 별도 클럭/valid 없음

- `copbit_ppu_3d_add_tile` (Core #1: tile core)
  - 조합 논리(combinational), 입력 타일 → 출력 타일 즉시 반영

- `copbit_ppu_3d_add_stream` (Core #2: stream core, handshake 지원)
  - 최소 1클럭 latency
  - `in_valid & in_ready`로 입력 수락 후,  
    내부 파이프라인 및 back-pressure 상태(`out_ready`)에 따라  
    1클럭 이상 지연된 시점에 `out_valid`와 출력 타일이 유효해진다.

---

## 5. 현재 구현된 IPCore 코어 목록 (3D-ADD / 3D-MUL 계열)

| Core ID | 모듈명                       | 타입      | 인터페이스               | 기능 설명                                       |
|--------:|-----------------------------|-----------|--------------------------|-------------------------------------------------|
| 0       | `copbit_ppu_3d_add_core`    | scalar    | 조합논리                 | 단일 인덱스에 대해 `(a_idx + b_idx) mod 8`      |
| 1       | `copbit_ppu_3d_add_tile`    | tile      | 조합논리 (타일 인덱스)   | NLANES개의 레인에 대해 병렬 3D-ADD              |
| 2       | `copbit_ppu_3d_add_stream`  | stream    | clk + ready/valid 스트림 | 1-stage 파이프라인 3D-ADD 타일 스트림 코어      |
| 3       | `copbit_ppu_3d_mul_core`    | scalar    | 조합논리                 | 단일 인덱스에 대해 `(a_idx * b_idx) mod 8`      |
| 4       | `copbit_ppu_3d_mul_tile`    | tile      | 조합논리 (타일 인덱스)   | NLANES개의 레인에 대해 병렬 3D-MUL              |
| 5       | `copbit_ppu_3d_mul_stream`  | stream    | clk + ready/valid 스트림 | 1-stage 파이프라인 3D-MUL 타일 스트림 코어      |

※ 향후 3D-MUL, LUT, phase 관련 IPCore 역시 상기 규칙과 표 형식을 따라  
 Core ID, 모듈명, 타입, 인터페이스, 기능 설명을 추가한다.

## Core #0 – 3D-ADD index core (Q24b)

### 개요

- 모듈명: `copbit_ppu_3d_add_core`
- 기능: `(a_idx + b_idx) mod 8`, `a_idx, b_idx ∈ {0..7}`
- 파라미터:
  - `M = 8` (기본 M8 3D 코어)
  - `WIDTH = 3` (index 비트폭, `log2(M)`)

M이 2의 거듭제곱(`M == 2^WIDTH`)일 때, 상위 캐리 비트가 자동으로 잘려서 `mod 2^WIDTH`가 되므로, `M=8` 기본 코어는 단순 3비트 더하기로 구현된다. 추후 M≠2^WIDTH 실험을 위해 generic mod 로직도 RTL에 포함되어 있다.

### RTL 파일

- 경로: `CoPBit_Research/ipcore/rtl/copbit_ppu_3d_add_core.v`

핵심 구현 아이디어:

- pow2 케이스:
  - `assign y_idx = a_idx + b_idx;`  
    → 상위 캐리 제거로 자연스럽게 `(a + b) mod 2^WIDTH`
- generic 케이스:
  - `sum_full = a_idx + b_idx;`
  - `y_idx = (sum_full >= M) ? sum_full - M : sum_full[WIDTH-1:0];`

### Testbench

- 모듈명: `tb_copbit_ppu_3d_add_core`
- 경로: `CoPBit_Research/ipcore/tb/tb_copbit_ppu_3d_add_core.v`

테스트 방법:

- `M = 8` 고정
- `(a_idx, b_idx) ∈ {0..7} × {0..7}` 전체 64개 조합에 대해 전수 검사
- truth 함수:  
  - `add3d_truth(a, b) = (a + b) mod 8`
- `y_idx !== add3d_truth(a, b)` 인 경우를 모두 카운트 후 `err_cnt`로 집계

### 시뮬레이션 방법 (iverilog)

아래 명령을 `CoPBit_Research/ipcore` 루트에서 실행:

```bash
iverilog -g2012 -o build_3d_add_core \
  tb/tb_copbit_ppu_3d_add_core.v \
  rtl/copbit_ppu_3d_add_core.v

vvp build_3d_add_core
```

예상 출력:

```text
=== CoPBit PPU 3D-ADD truthcheck (M=8) ===
[PASS] op_error_3d_add = 0 (all 64 combinations)
tb/tb_copbit_ppu_3d_add_core.v:65: $finish called at 64000 (1ps)
```

위 결과를 기준으로, CoPBit PPU IPCore v0.1의 **3D-ADD index core(Q24b)**는 논리적으로 완전 검증됨(`op_error_3d_add = 0`)을 확인했다.

---
## Core #1 – 3D-ADD tile core (index, M=8)

### 개요

- 모듈명: `copbit_ppu_3d_add_tile`
- 기능: NLANES개의 lane에 대해 `(a_idx + b_idx) mod 8`을 병렬 계산  
- 파라미터:
  - `M      = 8` (기본 M8 3D 코어)
  - `WIDTH  = 3` (index 비트폭, `log2(M)`)
  - `NLANES = 16` (동시에 처리하는 lane 수)

각 lane은 `copbit_ppu_3d_add_core`를 재사용하며, `a_idx_flat / b_idx_flat / y_idx_flat`
packed bus를 lane별 3비트 조각으로 나누어 매핑한다.

### RTL 파일

- 경로: `CoPBit_Research/ipcore/rtl/copbit_ppu_3d_add_tile.v`

핵심 구현 아이디어:

- `NLANES`개의 lane에 대해 `generate for` 루프를 사용
- 각 lane에 대해:
  - `a_idx_flat[(g+1)*WIDTH-1 : g*WIDTH]` → `a_lane`
  - `b_idx_flat[(g+1)*WIDTH-1 : g*WIDTH]` → `b_lane`
  - `y_lane` → `y_idx_flat[(g+1)*WIDTH-1 : g*WIDTH]`
- 내부에서는 Core #0인 `copbit_ppu_3d_add_core`를 그대로 인스턴스

### Testbench

- 모듈명: `tb_copbit_ppu_3d_add_tile`
- 경로: `CoPBit_Research/ipcore/tb/tb_copbit_ppu_3d_add_tile.v`

테스트 방법:

- `M = 8`, `NLANES = 16` 고정
- `a_idx_arr[lane]`, `b_idx_arr[lane]` 배열로 각 lane의 입력을 설정
- 간단한 패턴:
  - `a_lane = (i + lane)   mod 8`
  - `b_lane = (2*i + lane) mod 8`
- truth 함수:
  - `add3d_truth(a, b) = (a + b) mod 8`
- 모든 `i` 반복과 모든 `lane`에 대해:
  - `y_idx_arr[lane]`와 `add3d_truth(a_lane, b_lane)`를 비교
  - 불일치 시 `err_cnt` 증가

### 시뮬레이션 방법 (iverilog)

아래 명령을 `CoPBit_Research/ipcore` 루트에서 실행:

```bash
iverilog -g2012 -o build_3d_add_tile \
  tb/tb_copbit_ppu_3d_add_tile.v \
  rtl/copbit_ppu_3d_add_tile.v \
  rtl/copbit_ppu_3d_add_core.v

vvp build_3d_add_tile
```

예상 출력:

```text
=== CoPBit PPU 3D-ADD tile truthcheck (M=8, NLANES=16) ===
[PASS] op_error_3d_add_tile = 0 (M=8, NLANES=16)
tb/tb_copbit_ppu_3d_add_tile.v:94: $finish called at 16000 (1ps)
```

위 결과를 기준으로, CoPBit PPU IPCore v0.1의 3D-ADD tile core는
NLANES=16 구성에서 논리적으로 완전 검증(op_error_3d_add_tile = 0)되었음을 확인했다.

---
## Core #2 – 3D-ADD stream core (index, M=8)

### 개요

- 모듈명: `copbit_ppu_3d_add_stream`
- 기능: `clk` 기반 1-stage 파이프라인 스트림 코어 (ready/valid 핸드셰이크 지원)  
  - `in_valid/in_ready`와 함께 들어온 `(in_a_idx_flat, in_b_idx_flat)` 타일을
  - **최소 1클럭 지연** 후 `(a + b) mod 8` 결과 타일로 출력
- 파라미터:
  - `M      = 8`
  - `WIDTH  = 3`
  - `NLANES = 16`

입력은 `NLANES × 3bit` 인덱스 타일(`in_a_idx_flat`, `in_b_idx_flat`)이고,
출력은 동일한 형태의 인덱스 타일(`out_y_idx_flat`)이다. 내부에서 Core #1인
`copbit_ppu_3d_add_tile`를 재사용하며, 스트림 인터페이스는 `in_valid/in_ready`,
`out_valid/out_ready` 규칙을 따른다.

### RTL 파일

- 경로: `CoPBit_Research/ipcore/rtl/copbit_ppu_3d_add_stream.v`

핵심 동작:

- 내부 1-stage 파이프라인 레지스터:
  - `a_idx_reg`, `b_idx_reg`, `stage_valid`
- 입력 핸드셰이크:
  - `in_valid = 1` 이고 `in_ready = 1` 인 클럭에서만
    `in_a_idx_flat`, `in_b_idx_flat`이 `a_idx_reg`, `b_idx_reg`에 래치되고,
    `stage_valid`가 1로 설정된다.
  - `in_ready`는 `stage_valid == 0`이거나,  
    `stage_valid == 1`이면서 동일 클럭에서 `out_ready == 1`인 경우에 1이 된다.
- 출력 핸드셰이크:
  - `out_valid`는 `stage_valid`를 반영한다.
  - `out_y_idx_flat`는 항상 현재 `a_idx_reg`, `b_idx_reg`에 대해
    타일 코어가 계산한 `y_idx_wire`를 출력한다.
  - `out_valid = 1` 및 `out_ready = 1`인 클럭에서 출력 데이터가 소비되며,
    동시에 새 입력이 들어오지 않으면 `stage_valid`가 0으로 떨어진다.
- 결과적으로, 입력이 수락된 시점( `in_valid & in_ready` )으로부터
  **최소 1클럭 후**에 `out_valid`와 출력 타일이 유효해지며,
  `out_ready`에 따라 유효 데이터 유지 시간이 늘어날 수 있다.

### Testbench

- 모듈명: `tb_copbit_ppu_3d_add_stream`
- 경로: `CoPBit_Research/ipcore/tb/tb_copbit_ppu_3d_add_stream.v`

테스트 방법:

- `M = 8`, `NLANES = 16`
- `vec = 0..7`에 대해, lane별로:
  - `a_lane = (vec + lane)   mod 8`
  - `b_lane = (2*vec + lane) mod 8`
  - 기대값: `exp_y = (a_lane + b_lane) mod 8`
- TB 동작:
  1. 각 `vec`에 대해 입력 타일을 `in_a_idx_flat`, `in_b_idx_flat`에 세팅
  2. `out_ready`는 1로 유지하여 항상 출력 소비 가능 상태로 둔다.
  3. `in_ready`가 1인 것을 확인한 뒤, `in_valid`를 1클럭 펄스로 인가
  4. 1클럭 뒤에 `out_valid == 1`인지 확인하고,
     각 lane에 대해 `out_y_idx_flat`이 기대값과 일치하는지 검사
- 향후 `out_ready`를 0/1로 토글하여 back-pressure 상황에서의 동작도
  동일 TB 구조 위에 시나리오를 추가하는 방식으로 검증 가능하다.

### 시뮬레이션 방법 (iverilog)

아래 명령을 `CoPBit_Research/ipcore` 루트에서 실행:

```bash
iverilog -g2012 -o build_3d_add_stream \
  tb/tb_copbit_ppu_3d_add_stream.v \
  rtl/copbit_ppu_3d_add_stream.v \
  rtl/copbit_ppu_3d_add_tile.v \
  rtl/copbit_ppu_3d_add_core.v

vvp build_3d_add_stream
```

예상 출력:

```text
=== CoPBit PPU 3D-ADD stream core (handshake) test (M=8, NLANES=16) ===
[PASS] copbit_ppu_3d_add_stream (handshake): all vectors OK (M=8, NLANES=16)
tb/tb_copbit_ppu_3d_add_stream.v:138: $finish called at 275000 (1ps)

위 결과를 기준으로, CoPBit PPU IPCore v0.1의 3D-ADD stream core는
NLANES=16 구성에서 ready/valid 핸드셰이크를 사용하는 1-stage 파이프라인
스트림 코어로서 완전 검증되었음을 확인했다.
```

## Core #3 – 3D-MUL index core (index, M=8)

### 개요

- 모듈명: `copbit_ppu_3d_mul_core`
- 기능: 단일 인덱스에 대해 `(a_idx * b_idx) mod 8` 연산 수행
- 파라미터:
  - `M      = 8`
  - `WIDTH  = 3`

입력 `a_idx`, `b_idx`는 각각 3비트 인덱스(`0..7`)이고,  
출력 `y_idx`는 `(a_idx * b_idx) mod 8` 결과를 3비트 인덱스로 표현한다.

`M = 8`, `WIDTH = 3`인 경우, 내부적으로는 2*WIDTH 비트 곱 결과를 만든 뒤  
하위 3비트만 사용함으로써 `(a * b) mod 8`을 실현한다.  
향후 `M ≠ 2^WIDTH` 실험을 위해 generic `% M` 모듈로 확장 가능한 형태로 작성되어 있다.

### RTL 파일

- 경로: `CoPBit_Research/ipcore/rtl/copbit_ppu_3d_mul_core.v`

핵심 동작:

- 전체 곱:
  - `prod_full = a_idx * b_idx;`  // 폭은 2*WIDTH 비트
- pow2 케이스(`M == 2^WIDTH`):
  - `assign y_idx = prod_full[WIDTH-1:0];`
  - 상위 비트를 버림으로써 자연스럽게 `mod 2^WIDTH`를 만족
- generic 케이스(`M != 2^WIDTH`) 대비:
  - `prod_mod = prod_full % M;`
  - `assign y_idx = prod_mod[WIDTH-1:0];`

### Testbench

- 모듈명: `tb_copbit_ppu_3d_mul_core`
- 경로: `CoPBit_Research/ipcore/tb/tb_copbit_ppu_3d_mul_core.v`

테스트 방법:

- `M = 8`, `WIDTH = 3`
- `(a_idx, b_idx) ∈ {0..7} × {0..7}` 전체 64개 조합에 대해 전수 검사
- truth 함수:
  - `mul3d_truth(a, b) = (a * b) mod 8`
- `y_idx !== mul3d_truth(a, b)` 인 경우를 모두 카운트 후 `err_cnt`로 집계

### 시뮬레이션 방법 (iverilog)

아래 명령을 `CoPBit_Research/ipcore` 루트에서 실행:

```bash
iverilog -g2012 -o build_3d_mul_core \
  tb/tb_copbit_ppu_3d_mul_core.v \
  rtl/copbit_ppu_3d_mul_core.v

vvp build_3d_mul_core

예상 출력:
=== CoPBit PPU 3D-MUL truthcheck (M=8) ===
[PASS] op_error_3d_mul = 0 (all 64 combinations)
tb/tb_copbit_ppu_3d_mul_core.v:67: $finish called at 64000 (1ps)

위 결과를 기준으로, CoPBit PPU IPCore v0.1의 3D-MUL index core는
M=8 구성에서 논리적으로 완전 검증(op_error_3d_mul = 0)되었음을 확인했다.


Core #4 – 3D-MUL tile core (index, M=8)

개요
	•	모듈명: copbit_ppu_3d_mul_tile
	•	기능: NLANES개의 lane에 대해 (a_idx * b_idx) mod 8을 병렬 계산
	•	파라미터:
	•	M      = 8
	•	WIDTH  = 3
	•	NLANES = 16

입력은 NLANES × 3bit 인덱스 타일(a_idx_flat, b_idx_flat)이고,
출력은 동일한 형태의 인덱스 타일(y_idx_flat)이다.

각 lane은 Core #3인 copbit_ppu_3d_mul_core를 재사용하며,
a_idx_flat / b_idx_flat / y_idx_flat packed bus를 lane별 3비트 조각으로 나누어 매핑한다.

RTL 파일
	•	경로: CoPBit_Research/ipcore/rtl/copbit_ppu_3d_mul_tile.v

핵심 동작:
	•	NLANES개의 lane에 대해 generate for 루프 사용
	•	각 lane g(0..NLANES-1)에 대해:
	•	a_lane = a_idx_flat[(g+1)*WIDTH-1 : g*WIDTH]
	•	b_lane = b_idx_flat[(g+1)*WIDTH-1 : g*WIDTH]
	•	y_lane를 계산 후 y_idx_flat[(g+1)*WIDTH-1 : g*WIDTH]에 패킹
	•	lane별로 copbit_ppu_3d_mul_core를 인스턴스하여 동일 연산을 병렬 수행

Testbench
	•	모듈명: tb_copbit_ppu_3d_mul_tile
	•	경로: CoPBit_Research/ipcore/tb/tb_copbit_ppu_3d_mul_tile.v

테스트 방법:
	•	M = 8, NLANES = 16 고정
	•	vec = 0..7에 대해, lane별 입력 패턴을 생성:
	•	a_lane = (vec + lane)   mod 8
	•	b_lane = (2*vec + lane) mod 8
	•	기대값: exp_y = (a_lane * b_lane) mod 8
	•	위 패턴을 a_idx_flat, b_idx_flat에 패킹한 후,
조합 논리가 settle 된 시점에서 y_idx_flat을 unpack하여 lane별로 비교
	•	불일치 시 err_cnt 증가

시뮬레이션 방법 (iverilog)

아래 명령을 CoPBit_Research/ipcore 루트에서 실행:

iverilog -g2012 -o build_3d_mul_tile \
  tb/tb_copbit_ppu_3d_mul_tile.v \
  rtl/copbit_ppu_3d_mul_tile.v \
  rtl/copbit_ppu_3d_mul_core.v

vvp build_3d_mul_tile

예상 출력:
=== CoPBit PPU 3D-MUL tile truthcheck (M=8, NLANES=16) ===
[PASS] op_error_3d_mul_tile = 0 (M=8, NLANES=16)
tb/tb_copbit_ppu_3d_mul_tile.v:100: $finish called at 8000 (1ps)

위 결과를 기준으로, CoPBit PPU IPCore v0.1의 3D-MUL tile core는
NLANES=16 구성에서 논리적으로 완전 검증(op_error_3d_mul_tile = 0)되었음을 확인했다.

Core #5 – 3D-MUL stream core (index, M=8)

개요
	•	모듈명: copbit_ppu_3d_mul_stream
	•	기능: clk 기반 1-stage 파이프라인 스트림 코어 (ready/valid 핸드셰이크 지원)
	•	in_valid/in_ready와 함께 들어온 (in_a_idx_flat, in_b_idx_flat) 타일을
	•	최소 1클럭 지연 후 (a_idx * b_idx) mod 8 결과 타일로 출력
	•	파라미터:
	•	M      = 8
	•	WIDTH  = 3
	•	NLANES = 16

입력은 NLANES × 3bit 인덱스 타일(in_a_idx_flat, in_b_idx_flat)이고,
출력은 동일한 형태의 인덱스 타일(out_y_idx_flat)이다.
내부에서 Core #4인 copbit_ppu_3d_mul_tile를 재사용하며,
스트림 인터페이스는 in_valid/in_ready, out_valid/out_ready 규칙을 따른다.

RTL 파일
	•	경로: CoPBit_Research/ipcore/rtl/copbit_ppu_3d_mul_stream.v

핵심 동작:
	•	내부 1-stage 파이프라인 레지스터:
	•	a_idx_reg, b_idx_reg, stage_valid
	•	입력 핸드셰이크:
	•	in_valid = 1 이고 in_ready = 1 인 클럭에서만
in_a_idx_flat, in_b_idx_flat이 a_idx_reg, b_idx_reg에 래치되고,
stage_valid가 1로 설정된다.
	•	in_ready는 stage_valid == 0이거나,
stage_valid == 1이면서 동일 클럭에서 out_ready == 1인 경우에 1이 된다.
	•	출력 핸드셰이크:
	•	out_valid는 stage_valid를 반영한다.
	•	out_y_idx_flat는 항상 현재 a_idx_reg, b_idx_reg에 대해
타일 코어가 계산한 y_idx_wire를 출력한다.
	•	out_valid = 1 및 out_ready = 1인 클럭에서 출력 데이터가 소비되며,
동시에 새 입력이 들어오지 않으면 stage_valid가 0으로 떨어진다.
	•	결과적으로, 입력이 수락된 시점(in_valid & in_ready)으로부터
최소 1클럭 후에 out_valid와 출력 타일이 유효해지며,
out_ready에 따라 유효 데이터 유지 시간이 늘어날 수 있다.

Testbench
	•	모듈명: tb_copbit_ppu_3d_mul_stream
	•	경로: CoPBit_Research/ipcore/tb/tb_copbit_ppu_3d_mul_stream.v

테스트 방법:
	•	M = 8, NLANES = 16
	•	vec = 0..7에 대해, lane별로:
	•	a_lane = (vec + lane)   mod 8
	•	b_lane = (2*vec + lane) mod 8
	•	기대값: exp_y = (a_lane * b_lane) mod 8
	•	TB 동작:
	1.	각 vec에 대해 입력 타일을 in_a_idx_flat, in_b_idx_flat에 세팅
	2.	out_ready는 1로 유지하여 항상 출력 소비 가능 상태로 둔다.
	3.	in_ready가 1인 것을 확인한 뒤, in_valid를 1클럭 펄스로 인가
	4.	1클럭 뒤에 out_valid == 1인지 확인하고,
각 lane에 대해 out_y_idx_flat이 기대값과 일치하는지 검사
	•	향후 out_ready를 0/1로 토글하여 back-pressure 상황에서의 동작도
동일 TB 구조 위에 시나리오를 추가하는 방식으로 검증 가능하다.

시뮬레이션 방법 (iverilog)

아래 명령을 CoPBit_Research/ipcore 루트에서 실행:

iverilog -g2012 -o build_3d_mul_stream \
  tb/tb_copbit_ppu_3d_mul_stream.v \
  rtl/copbit_ppu_3d_mul_stream.v \
  rtl/copbit_ppu_3d_mul_tile.v \
  rtl/copbit_ppu_3d_mul_core.v

vvp build_3d_mul_stream

예상 출력:
=== CoPBit PPU 3D-MUL stream core (handshake) test (M=8, NLANES=16) ===
[PASS] copbit_ppu_3d_mul_stream (handshake): all vectors OK (M=8, NLANES=16)
tb/tb_copbit_ppu_3d_mul_stream.v:141: $finish called at 275000 (1ps)

위 결과를 기준으로, CoPBit PPU IPCore v0.1의 3D-MUL stream core는
NLANES=16 구성에서 ready/valid 핸드셰이크를 사용하는 1-stage 파이프라인
스트림 코어로서 완전 검증되었음을 확인했다.

## Core #6 – 3D-LUT index core (index, M=8)

### 개요

- 모듈명: `copbit_ppu_3d_lut_core`
- 기능: 단일 인덱스에 대해 고정 3D-LUT 매핑 수행  
  - 예시 매핑 (M=8, WIDTH=3 기준):  
    - `0 → 3`, `1 → 0`, `2 → 6`, `3 → 1`, `4 → 7`, `5 → 2`, `6 → 5`, `7 → 4`
- 파라미터:
  - `M      = 8`
  - `WIDTH  = 3`

입력 `in_idx`는 3비트 인덱스(`0..7`)이고,  
출력 `out_idx`는 LUT 테이블에서 정의한 3비트 인덱스 값을 반환한다.  
현재 버전은 `M=8` 고정 permutation S-box 형태로 사용하며,  
향후 필요 시 LUT 테이블을 파라미터/메모리 기반으로 확장할 수 있다.

### RTL 파일

- 경로: `CoPBit_Research/ipcore/rtl/copbit_ppu_3d_lut_core.v`

핵심 동작:

- 조합 논리 `always @*` 블록과 `case` 문으로 LUT 매핑 구현
- `in_idx` 값에 따라 미리 정의된 3비트 인덱스를 `out_idx`에 할당
- 범위를 벗어나는 경우(`default`)에는 0으로 처리

### Testbench

- 모듈명: `tb_copbit_ppu_3d_lut_core`
- 경로: `CoPBit_Research/ipcore/tb/tb_copbit_ppu_3d_lut_core.v`

테스트 방법:

- `M = 8`, `WIDTH = 3`
- `in_idx = 0..7` 전체 인덱스에 대해 전수 검사 수행
- truth 함수:
  - `lut3d_truth(x)`는 RTL과 동일한 LUT 매핑(0→3, 1→0, …, 7→4)을 반환
- Testbench는 각 `in_idx`에 대해:
  - `out_idx !== lut3d_truth(in_idx)` 인 경우 에러로 카운트(`err_cnt`)
  - 최종적으로 `op_error_3d_lut = err_cnt`를 출력

### 시뮬레이션 방법 (iverilog)

아래 명령을 `CoPBit_Research/ipcore` 루트에서 실행:

```bash
iverilog -g2012 -o build_3d_lut_core \
  tb/tb_copbit_ppu_3d_lut_core.v \
  rtl/copbit_ppu_3d_lut_core.v

vvp build_3d_lut_core

예상 출력:
 === CoPBit PPU 3D-LUT truthcheck (M=8) ===
[PASS] op_error_3d_lut = 0 (all 8 entries OK)
tb/tb_copbit_ppu_3d_lut_core.v:69: $finish called at 18 (1ps)

## Core #7 – 3D-LUT tile core (index, M=8)

### 개요

- 모듈명: `copbit_ppu_3d_lut_tile`
- 기능: NLANES개의 lane에 대해 고정 3D-LUT 매핑을 병렬 계산  
- 파라미터:
  - `M      = 8`
  - `WIDTH  = 3`
  - `NLANES = 16`

입력은 `NLANES × 3bit` 인덱스 타일(`in_idx_flat`)이고,  
출력은 동일한 형태의 인덱스 타일(`out_idx_flat`)이다.  
각 lane은 Core #6인 `copbit_ppu_3d_lut_core`를 재사용하며,  
`in_idx_flat / out_idx_flat` packed bus를 lane별 3비트 조각으로 나누어 매핑한다.

### RTL 파일

- 경로: `CoPBit_Research/ipcore/rtl/copbit_ppu_3d_lut_tile.v`

핵심 동작:

- `NLANES`개의 lane에 대해 `generate for` 루프 사용
- 각 lane g(0..NLANES-1)에 대해:
  - `in_lane  = in_idx_flat[(g+1)*WIDTH-1 : g*WIDTH]`
  - `out_lane`를 계산 후 `out_idx_flat[(g+1)*WIDTH-1 : g*WIDTH]`에 패킹
- lane별로 `copbit_ppu_3d_lut_core`를 인스턴스하여 동일 LUT 매핑을 병렬 수행

### Testbench

- 모듈명: `tb_copbit_ppu_3d_lut_tile`
- 경로: `CoPBit_Research/ipcore/tb/tb_copbit_ppu_3d_lut_tile.v`

테스트 방법:

- `M = 8`, `NLANES = 16` 고정
- `vec = 0..7`에 대해, lane별 입력 패턴을 생성:
  - `in_lane = (vec + lane) mod 8`
  - 기대값: `exp_y = LUT(in_lane)` (Core #6과 동일 매핑)
- 위 패턴을 `in_idx_flat`에 패킹한 후,  
  조합 논리가 settle 된 시점에서 `out_idx_flat`을 unpack하여 lane별로 비교
- 불일치 시 `err_cnt` 증가

### 시뮬레이션 방법 (iverilog)

아래 명령을 `CoPBit_Research/ipcore` 루트에서 실행:

```bash
iverilog -g2012 -o build_3d_lut_tile \
  tb/tb_copbit_ppu_3d_lut_tile.v \
  rtl/copbit_ppu_3d_lut_tile.v \
  rtl/copbit_ppu_3d_lut_core.v

vvp build_3d_lut_tile
예상 출력:

=== CoPBit PPU 3D-LUT tile truthcheck (M=8, NLANES=16) ===
[PASS] op_error_3d_lut_tile = 0 (M=8, NLANES=16)
tb/tb_copbit_ppu_3d_lut_tile.v:106: $finish called at 18 (1ps)


Core #8 – 3D-LUT stream core (index, M=8)

개요
	•	모듈명: copbit_ppu_3d_lut_stream
	•	기능: clk 기반 1-stage 파이프라인 스트림 코어 (ready/valid 핸드셰이크 지원)
	•	in_valid/in_ready와 함께 들어온 in_idx_flat 타일을
	•	최소 1클럭 지연 후 LUT 매핑 결과 타일로 출력
	•	파라미터:
	•	M      = 8
	•	WIDTH  = 3
	•	NLANES = 16

입력은 NLANES × 3bit 인덱스 타일(in_idx_flat)이고,
출력은 동일한 형태의 인덱스 타일(out_idx_flat)이다.
내부에서 Core #7인 copbit_ppu_3d_lut_tile를 재사용하며,
스트림 인터페이스는 in_valid/in_ready, out_valid/out_ready 규칙을 따른다.

RTL 파일
	•	경로: CoPBit_Research/ipcore/rtl/copbit_ppu_3d_lut_stream.v

핵심 동작:
	•	내부 1-stage 파이프라인 레지스터:
	•	idx_reg, stage_valid
	•	입력 핸드셰이크:
	•	in_valid = 1 이고 in_ready = 1 인 클럭에서만
in_idx_flat이 idx_reg에 래치되고, stage_valid가 1로 설정된다.
	•	in_ready는 stage_valid == 0이거나,
stage_valid == 1이면서 동일 클럭에서 out_ready == 1인 경우에 1이 된다.
	•	출력 핸드셰이크:
	•	out_valid는 stage_valid를 반영한다.
	•	out_idx_flat는 항상 현재 idx_reg에 대해
타일 코어가 계산한 LUT 결과(idx_lut_wire)를 출력한다.
	•	out_valid = 1 및 out_ready = 1인 클럭에서 출력 데이터가 소비되며,
동시에 새 입력이 들어오지 않으면 stage_valid가 0으로 떨어진다.
	•	결과적으로, 입력이 수락된 시점(in_valid & in_ready)으로부터
최소 1클럭 후에 out_valid와 출력 타일이 유효해지며,
out_ready에 따라 유효 데이터 유지 시간이 늘어날 수 있다.

Testbench
	•	모듈명: tb_copbit_ppu_3d_lut_stream
	•	경로: CoPBit_Research/ipcore/tb/tb_copbit_ppu_3d_lut_stream.v

테스트 방법:
	•	M = 8, NLANES = 16
	•	vec = 0..7에 대해, lane별로:
	•	in_lane = (vec + lane) mod 8
	•	기대값: exp_y = LUT(in_lane) (Core #6과 동일 매핑)
	•	TB 동작:
	1.	각 vec에 대해 입력 타일을 in_idx_flat에 세팅
	2.	out_ready는 1로 유지하여 항상 출력 소비 가능 상태로 둔다.
	3.	in_ready가 1인 것을 확인한 뒤, in_valid를 1클럭 펄스로 인가
	4.	1클럭 뒤에 out_valid == 1인지 확인하고,
각 lane에 대해 out_idx_flat이 기대값과 일치하는지 검사
	•	향후 out_ready를 0/1로 토글하여 back-pressure 상황에서의 동작도
동일 TB 구조 위에 시나리오를 추가하는 방식으로 검증 가능하다.

시뮬레이션 방법 (iverilog)

아래 명령을 `CoPBit_Research/ipcore` 루트에서 실행:

예상 출력:

```text
=== CoPBit PPU 3D-LUT stream core (handshake) test (M=8, NLANES=16) ===
[PASS] copbit_ppu_3d_lut_stream (handshake): all vectors OK (M=8, NLANES=16)
tb/tb_copbit_ppu_3d_lut_stream.v:158: $finish called at 61 (1ps)
```

---
## IPCore v0.1 상태 요약

현재까지 완료된 CoPBit PPU IPCore v0.1 primitive:

| Core ID | 이름            | 타입    | 기능                     |
|--------:|----------------|--------|--------------------------|
| 0       | 3D-ADD index   | index  | `(a + b) mod 8`          |
| 1       | 3D-ADD tile    | tile   | 16-lane `(a + b) mod 8`  |
| 2       | 3D-ADD stream  | stream | ready/valid 1-stage      |
| 3       | 3D-MUL index   | index  | `(a * b) mod 8`          |
| 4       | 3D-MUL tile    | tile   | 16-lane `(a * b) mod 8`  |
| 5       | 3D-MUL stream  | stream | ready/valid 1-stage      |
| 6       | 3D-LUT index   | index  | 고정 permutation LUT      |
| 7       | 3D-LUT tile    | tile   | 16-lane LUT              |
| 8       | 3D-LUT stream  | stream | ready/valid 1-stage      |
 
