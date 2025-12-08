// CoPBit PPU IPCore v0.1
// Core #6 – 3D-LUT index core truthcheck TB

`timescale 1ps/1ps

module tb_copbit_ppu_3d_lut_core;

    localparam integer M     = 8;
    localparam integer WIDTH = 3;

    reg  [WIDTH-1:0] in_idx;
    wire [WIDTH-1:0] out_idx;

    integer idx;
    integer err_cnt;

    // DUT
    copbit_ppu_3d_lut_core #(
        .M(M),
        .WIDTH(WIDTH)
    ) dut (
        .in_idx (in_idx),
        .out_idx(out_idx)
    );

    // truth LUT (연산 정의와 동일한 매핑)
    function [WIDTH-1:0] lut3d_truth;
        input [WIDTH-1:0] x;
        begin
            case (x)
                3'd0: lut3d_truth = 3'd3;
                3'd1: lut3d_truth = 3'd0;
                3'd2: lut3d_truth = 3'd6;
                3'd3: lut3d_truth = 3'd1;
                3'd4: lut3d_truth = 3'd7;
                3'd5: lut3d_truth = 3'd2;
                3'd6: lut3d_truth = 3'd5;
                3'd7: lut3d_truth = 3'd4;
                default: lut3d_truth = {WIDTH{1'b0}};
            endcase
        end
    endfunction

    initial begin
        err_cnt = 0;
        in_idx  = {WIDTH{1'b0}};

        $display("=== CoPBit PPU 3D-LUT truthcheck (M=%0d) ===", M);

        // 0..M-1 전체 인덱스 전수 검사
        for (idx = 0; idx < M; idx = idx + 1) begin
            in_idx = idx[WIDTH-1:0];
            #1; // 조합 논리 settle 대기

            if (out_idx !== lut3d_truth(in_idx)) begin
                $display("[ERR] idx=%0d  in=%0d  out=%0d  exp=%0d",
                         idx, in_idx, out_idx, lut3d_truth(in_idx));
                err_cnt = err_cnt + 1;
            end
        end

        if (err_cnt == 0) begin
            $display("[PASS] op_error_3d_lut = 0 (all %0d entries OK)", M);
        end else begin
            $display("[FAIL] op_error_3d_lut = %0d", err_cnt);
        end

        #10;
        $finish;
    end

endmodule