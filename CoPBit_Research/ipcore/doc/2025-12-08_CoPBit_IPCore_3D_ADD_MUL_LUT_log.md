# 2025-12-08 – CoPBit PPU IPCore v0.1  
## 3D-ADD / 3D-MUL / 3D-LUT index/tile/stream 검증 로그

### 1. 작업 개요

- 목적:
  - CoPBit PPU IPCore v0.1의 기본 3D 연산 primitive 세트(ADD/MUL/LUT)에 대해  
    **index / tile / stream (handshake)** 전체 체인 설계 및 시뮬레이션 검증.
- 구성:
  - M = 8 (3bit index space, WIDTH = 3)
  - NLANES = 16 (tile/stream 병렬 lanes)
  - 모든 Core는 truth LUT 또는 수식 기반 전수검증(`op_error = 0`) 완료.

---

### 2. 디렉터리 구조 (요약)

- 루트: `CoPBit_Research/ipcore`
  - `rtl/`
    - `copbit_ppu_3d_add_core.v`
    - `copbit_ppu_3d_add_tile.v`
    - `copbit_ppu_3d_add_stream.v`
    - `copbit_ppu_3d_mul_core.v`
    - `copbit_ppu_3d_mul_tile.v`
    - `copbit_ppu_3d_mul_stream.v`
    - `copbit_ppu_3d_lut_core.v`
    - `copbit_ppu_3d_lut_tile.v`
    - `copbit_ppu_3d_lut_stream.v`
  - `tb/`
    - `tb_copbit_ppu_3d_add_core.v`
    - `tb_copbit_ppu_3d_add_tile.v`
    - `tb_copbit_ppu_3d_add_stream.v`
    - `tb_copbit_ppu_3d_mul_core.v`
    - `tb_copbit_ppu_3d_mul_tile.v`
    - `tb_copbit_ppu_3d_mul_stream.v`
    - `tb_copbit_ppu_3d_lut_core.v`
    - `tb_copbit_ppu_3d_lut_tile.v`
    - `tb_copbit_ppu_3d_lut_stream.v`
  - `doc/`
    - `README_CoPBit_PPU_IPCore_v0.1.md` (Core #0 ~ #8 설명 및 시뮬 명령 정리)

---

### 3. 3D-ADD Core 세트 결과

#### 3.1 index core – `copbit_ppu_3d_add_core`

- 기능: `(a_idx + b_idx) mod 8`
- 검증:
  ```bash
  iverilog -g2012 -o build_3d_add_core \
    tb/tb_copbit_ppu_3d_add_core.v \
    rtl/copbit_ppu_3d_add_core.v

  vvp build_3d_add_core