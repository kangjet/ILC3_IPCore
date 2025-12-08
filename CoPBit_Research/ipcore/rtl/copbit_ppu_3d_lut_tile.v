// CoPBit PPU IPCore v0.1
// Core #7 – 3D-LUT tile core (M=8, NLANES=16)

`timescale 1ps/1ps

module copbit_ppu_3d_lut_tile #(
    parameter integer M      = 8,
    parameter integer WIDTH  = 3,
    parameter integer NLANES = 16
)(
    input  wire [NLANES*WIDTH-1:0] in_idx_flat,
    output wire [NLANES*WIDTH-1:0] out_idx_flat
);

    genvar g;
    generate
        for (g = 0; g < NLANES; g = g + 1) begin : GEN_LUT_LANES
            wire [WIDTH-1:0] in_lane;
            wire [WIDTH-1:0] out_lane;

            assign in_lane = in_idx_flat[(g+1)*WIDTH-1 : g*WIDTH];

            copbit_ppu_3d_lut_core #(
                .M(M),
                .WIDTH(WIDTH)
            ) u_lut_lane (
                .in_idx (in_lane),
                .out_idx(out_lane)
            );

            assign out_idx_flat[(g+1)*WIDTH-1 : g*WIDTH] = out_lane;
        end
    endgenerate

endmodule