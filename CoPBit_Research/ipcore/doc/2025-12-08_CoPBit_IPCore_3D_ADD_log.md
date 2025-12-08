# 2025-12-08 CoPBit IPCore 3D-ADD 작업 로그

## 1. 날짜 및 목적

- 날짜: 2025-12-08
- 위치: `CoPBit_Research/ipcore`
- 목적:
  - CoPBit PPU용 **3D-ADD(index) IPCore v0.1**의 기본 연산 체인 구현 및 검증
  - 단일 레인 → 멀티 레인 타일 → 스트림 코어까지 **3단계 구조**를 Verilog + TB로 확정

---

## 2. 구현된 RTL 모듈 요약

### 2.1 Core #0 – 3D-ADD index core

- 파일: `rtl/copbit_ppu_3d_add_core.v`
- 모듈명: `copbit_ppu_3d_add_core`
- 파라미터:
  - `M = 8` (M8 3D 코어)
  - `WIDTH = 3` (`log2(M)`)
- 기능:
  - 입력: `a_idx`, `b_idx` ∈ {0..7}
  - 출력: `y_idx = (a_idx + b_idx) mod M`
- 구현:
  - `M == 2^WIDTH`인 경우:
    - 단순 3비트 덧셈 → 상위 캐리가 자동으로 잘려 `mod 8` 실현
  - 그 외 generic M 지원을 위한 `sum_full` 기반 (향후 확장용)

---

### 2.2 Core #1 – 3D-ADD tile core

- 파일: `rtl/copbit_ppu_3d_add_tile.v`
- 모듈명: `copbit_ppu_3d_add_tile`
- 파라미터:
  - `M = 8`
  - `WIDTH = 3`
  - `NLANES = 16`
- 기능:
  - 입력: packed bus
    - `a_idx_flat[NLANES*WIDTH-1:0]`
    - `b_idx_flat[NLANES*WIDTH-1:0]`
  - 출력:
    - `y_idx_flat[NLANES*WIDTH-1:0]`
  - 각 lane에 대해 `(a_idx + b_idx) mod 8`을 병렬 계산
- 구조:
  - `genvar g` + `for` generate
  - lane별로:
    - `a_lane = a_idx_flat[(g+1)*WIDTH-1 : g*WIDTH]`
    - `b_lane = b_idx_flat[(g+1)*WIDTH-1 : g*WIDTH]`
    - `copbit_ppu_3d_add_core` 인스턴스 후 결과를 `y_idx_flat`에 재매핑

---

### 2.3 Core #2 – 3D-ADD stream core

- 파일: `rtl/copbit_ppu_3d_add_stream.v`
- 모듈명: `copbit_ppu_3d_add_stream`
- 파라미터:
  - `M = 8`
  - `WIDTH = 3`
  - `NLANES = 16`
- 인터페이스:
  - 입력:
    - `clk`, `rst_n`
    - `in_valid`
    - `in_a_idx_flat[NLANES*WIDTH-1:0]`
    - `in_b_idx_flat[NLANES*WIDTH-1:0]`
  - 출력:
    - `out_valid`
    - `out_y_idx_flat[NLANES*WIDTH-1:0]`
- 동작:
  - `in_valid = 1`인 사이클에서 입력 타일을 내부 레지스터에 래치
    - `a_idx_reg`, `b_idx_reg`, `valid_reg`
  - 내부에서 `copbit_ppu_3d_add_tile` 사용
  - 다음 클럭에서:
    - `out_y_idx_flat <= y_idx_wire`
    - `out_valid <= valid_reg`
  - 결과적으로 **고정 1클럭 latency 스트림 코어** 완성

---

## 3. Testbench 및 시뮬레이션

### 3.1 TB – tile core

- 파일: `tb/tb_copbit_ppu_3d_add_tile.v`
- 모듈명: `tb_copbit_ppu_3d_add_tile`
- 테스트 방법:
  - 파라미터: `M=8`, `NLANES=16`
  - `(a_idx, b_idx) ∈ {0..7}×{0..7}` 패턴을 lane별/벡터별로 생성
  - truth 함수:
    - `add3d_truth(a, b) = (a + b) mod 8`
  - 모든 lane에 대해 `y_idx_flat`가 truth와 일치하는지 검사
- 실행 커맨드:

```bash
cd CoPBit_Research/ipcore

iverilog -g2012 -o build_3d_add_tile \
  tb/tb_copbit_ppu_3d_add_tile.v \
  rtl/copbit_ppu_3d_add_tile.v \
  rtl/copbit_ppu_3d_add_core.v

vvp build_3d_add_tile
	•	주요 결과 로그:
=== CoPBit PPU 3D-ADD tile truthcheck (M=8, NLANES=16) ===
[PASS] op_error_3d_add_tile = 0 (M=8, NLANES=16)
tb/tb_copbit_ppu_3d_add_tile.v:94: $finish called at 16000 (1ps)
→ op_error_3d_add_tile = 0 확인 (16레인 타일 코어 논리 검증 완료)

3.2 TB – stream core
	•	파일: tb/tb_copbit_ppu_3d_add_stream.v
	•	모듈명: tb_copbit_ppu_3d_add_stream
	•	테스트 방법:
	•	파라미터: M=8, NLANES=16
	•	vec = 0..7에 대해:
	•	lane별 입력:
	•	a_lane = (vec + lane)   mod 8
	•	b_lane = (2*vec + lane) mod 8
	•	기대값:
	•	exp_y = (a_lane + b_lane) mod 8
	•	절차:
	1.	입력 타일 셋업 (in_a_idx_flat, in_b_idx_flat)
	2.	in_valid 1클럭 펄스
	3.	1클럭 뒤 out_valid가 1인지 확인
	4.	각 lane별 out_y_idx_flat를 기대값과 비교
	•	실행 커맨드:
  cd CoPBit_Research/ipcore

iverilog -g2012 -o build_3d_add_stream \
  tb/tb_copbit_ppu_3d_add_stream.v \
  rtl/copbit_ppu_3d_add_stream.v \
  rtl/copbit_ppu_3d_add_tile.v \
  rtl/copbit_ppu_3d_add_core.v

vvp build_3d_add_stream

	•	주요 결과 로그:
=== CoPBit PPU 3D-ADD stream core test (M=8, NLANES=16) ===
[PASS] copbit_ppu_3d_add_stream: all vectors OK (M=8, NLANES=16)
tb/tb_copbit_ppu_3d_add_stream.v:127: $finish called at 275000 (1ps)

→ 모든 테스트 벡터에서 lane별 결과 일치, 1클럭 latency 스트림 코어 검증 완료

4. 오늘 작업의 의미
	•	CoPBit PPU용 3D-ADD(index) 연산 체인을 다음 3단계로 완성:
	1.	논리 코어: (a + b) mod 8 (Core #0)
	2.	멀티레인 타일 코어: NLANES=16 병렬 연산 (Core #1)
	3.	스트림 코어: clk/rst_n + in_valid → 1클럭 뒤 out_valid 구조 (Core #2)
	•	각 단계는 별도의 TB + iverilog/vvp로 독립 검증:
	•	op_error_3d_add = 0
	•	op_error_3d_add_tile = 0
	•	copbit_ppu_3d_add_stream: all vectors OK
	•	이로써:
	•	CoPBit IPCore v0.1에서 M8 3D-ADD 기본 연산 블록이
	•	실질적인 하드웨어 구현 + 테스트 수준까지 확정됨
	•	향후:
	•	동일 패턴으로 3D-MUL, LUT, phase 관련 코어 설계 가능
	•	stream 코어에 in_ready/out_ready를 추가해 **PPU 전체 스트림 인터페이스(백프레셔 지원)**로 확장 예정

5. 다음 작업 후보 (TODO 메모)
	•	copbit_ppu_3d_add_stream에 in_ready/out_ready 추가:
	•	AXI-Stream 스타일의 풀 스트림 인터페이스로 확장
	•	NLANES 스케일 검증:
	•	NLANES = 32, 64 등으로 tile/stream TB 재실행
	•	3D-ADD IPCore 블록을 특허 명세서/기술 문서의 **실시예(예시 회로)**로 반영:
	•	index-domain 3D-ADD 연산, 멀티레인 구조, 스트림 파이프라인 구조를 하나의 예시로 정리
