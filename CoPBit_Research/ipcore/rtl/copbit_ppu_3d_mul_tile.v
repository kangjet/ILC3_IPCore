// ============================================================
// File: rtl/copbit_ppu_3d_mul_tile.v
// Desc: CoPBit PPU – 3D-MUL tile core (NLANES × (a * b) mod M)
// ============================================================
`timescale 1ns/1ps

module copbit_ppu_3d_mul_tile #(
    parameter integer M      = 8,
    parameter integer WIDTH  = 3,
    parameter integer NLANES = 16
)(
    input  wire [NLANES*WIDTH-1:0] a_idx_flat,
    input  wire [NLANES*WIDTH-1:0] b_idx_flat,
    output wire [NLANES*WIDTH-1:0] y_idx_flat
);

    genvar g;
    generate
        for (g = 0; g < NLANES; g = g + 1) begin : GEN_LANE
            wire [WIDTH-1:0] a_lane;
            wire [WIDTH-1:0] b_lane;
            wire [WIDTH-1:0] y_lane;

            // lane g에 대한 인덱스 슬라이스
            assign a_lane = a_idx_flat[(g+1)*WIDTH-1 : g*WIDTH];
            assign b_lane = b_idx_flat[(g+1)*WIDTH-1 : g*WIDTH];
            assign y_idx_flat[(g+1)*WIDTH-1 : g*WIDTH] = y_lane;

            // lane별 3D-MUL index core 인스턴스
            copbit_ppu_3d_mul_core #(
                .M(M),
                .WIDTH(WIDTH)
            ) u_core (
                .a_idx(a_lane),
                .b_idx(b_lane),
                .y_idx(y_lane)
            );
        end
    endgenerate

endmodule
