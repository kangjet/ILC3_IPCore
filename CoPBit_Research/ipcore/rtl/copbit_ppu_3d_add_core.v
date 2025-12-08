// CoPBit PPU – 3D-ADD core (index domain)
// (a + b) mod 8, a,b in {0..7}
// v0.1 – pure combinational, no channel/phase/noise

`timescale 1ns/1ps

module copbit_ppu_3d_add_core #(
    parameter integer M     = 8,   // 모듈 개수 (M8)
    parameter integer WIDTH = 3    // index bit width (log2(M))
)(
    input  wire [WIDTH-1:0] a_idx,
    input  wire [WIDTH-1:0] b_idx,
    output wire [WIDTH-1:0] y_idx
);

    // M = 8 이라면 3bit 더하기에서 캐리 비트는 자연스럽게 버려지므로
    // (a + b) mod 8 == (a + b)[2:0]
    // 일반 M에 대비하려면 아래와 같이 조건부 빼기 로직을 쓰면 됨.

generate
if (M == (1 << WIDTH)) begin : gen_pow2_mod
    assign y_idx = a_idx + b_idx;  // 상위 캐리는 자동으로 잘려서 mod 2^WIDTH
end else begin : gen_generic_mod
    wire [WIDTH:0] sum_full;
    assign sum_full = a_idx + b_idx;
    assign y_idx    = (sum_full >= M) ? sum_full - M : sum_full[WIDTH-1:0];
end
endgenerate

endmodule