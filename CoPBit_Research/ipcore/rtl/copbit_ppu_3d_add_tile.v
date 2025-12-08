// CoPBit PPU – 3D-ADD tile (index domain, M=8)
// NLANES개 lane을 동시에 (a_idx + b_idx) mod 8 처리
// v0.1 – pure combinational, no clk

`timescale 1ns/1ps

module copbit_ppu_3d_add_tile #(
    parameter integer M      = 8,
    parameter integer WIDTH  = 3,   // log2(M)
    parameter integer NLANES = 16
)(
    input  wire [NLANES*WIDTH-1:0] a_idx_flat,
    input  wire [NLANES*WIDTH-1:0] b_idx_flat,
    output wire [NLANES*WIDTH-1:0] y_idx_flat
);

    genvar g;
    generate
        for (g = 0; g < NLANES; g = g + 1) begin : gen_lane
            wire [WIDTH-1:0] a_lane;
            wire [WIDTH-1:0] b_lane;
            wire [WIDTH-1:0] y_lane;

            assign a_lane = a_idx_flat[ (g+1)*WIDTH-1 : g*WIDTH ];
            assign b_lane = b_idx_flat[ (g+1)*WIDTH-1 : g*WIDTH ];
            assign y_idx_flat[ (g+1)*WIDTH-1 : g*WIDTH ] = y_lane;

            copbit_ppu_3d_add_core #(
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