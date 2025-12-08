// ============================================================
// File: rtl/copbit_ppu_3d_mul_core.v
// Desc: CoPBit PPU – 3D-MUL index core (y = (a * b) mod M)
// ============================================================
`timescale 1ns/1ps

module copbit_ppu_3d_mul_core #(
    parameter integer M     = 8,  // index space size (0..M-1)
    parameter integer WIDTH = 3   // index bit-width (log2(M))
)(
    input  wire [WIDTH-1:0] a_idx,  // multiplicand
    input  wire [WIDTH-1:0] b_idx,  // multiplier
    output wire [WIDTH-1:0] y_idx   // (a * b) mod M
);

    // 전체 곱 결과는 최대 2*WIDTH 비트
    localparam integer PW   = 2*WIDTH;
    localparam integer POW2 = (1 << WIDTH);

    // M이 2^WIDTH인 경우(예: M=8, WIDTH=3)에는 단순 비트 슬라이스로 mod 실현 가능
    localparam integer USE_POW2 = (M == POW2);

    wire [PW-1:0] prod_full;

    assign prod_full = a_idx * b_idx;

    generate
        if (USE_POW2) begin : GEN_POW2_MOD
            // M == 2^WIDTH → 상위 비트는 자동 버려지므로 하위 WIDTH비트만 사용
            assign y_idx = prod_full[WIDTH-1:0];
        end else begin : GEN_GENERIC_MOD
            // 일반 케이스 → `% M` 연산 사용
            wire [PW-1:0] prod_mod;
            assign prod_mod = prod_full % M;
            assign y_idx    = prod_mod[WIDTH-1:0];
        end
    endgenerate

endmodule
