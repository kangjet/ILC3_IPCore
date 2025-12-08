// CoPBit PPU IPCore v0.1
// Core #6 – 3D-LUT index core (M=8)

`timescale 1ps/1ps

module copbit_ppu_3d_lut_core #(
    parameter integer M     = 8,
    parameter integer WIDTH = 3
)(
    input  wire [WIDTH-1:0] in_idx,
    output reg  [WIDTH-1:0] out_idx
);

    // M=8, WIDTH=3 기준 고정 LUT (전단계에서는 permutation S-box로 사용)
    // 매핑: 0→3, 1→0, 2→6, 3→1, 4→7, 5→2, 6→5, 7→4
    // 추후 필요 시 M, 테이블 구조를 parameter로 확장 가능.

    always @* begin
        case (in_idx)
            3'd0: out_idx = 3'd3;
            3'd1: out_idx = 3'd0;
            3'd2: out_idx = 3'd6;
            3'd3: out_idx = 3'd1;
            3'd4: out_idx = 3'd7;
            3'd5: out_idx = 3'd2;
            3'd6: out_idx = 3'd5;
            3'd7: out_idx = 3'd4;
            default: out_idx = {WIDTH{1'b0}};
        endcase
    end

endmodule