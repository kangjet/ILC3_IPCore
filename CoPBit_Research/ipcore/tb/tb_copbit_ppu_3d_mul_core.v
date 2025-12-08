// ============================================================
// File: tb/tb_copbit_ppu_3d_mul_core.v
// Desc: Testbench for copbit_ppu_3d_mul_core (M=8, WIDTH=3)
// ============================================================
`timescale 1ns/1ps

module tb_copbit_ppu_3d_mul_core;

    localparam integer M     = 8;
    localparam integer WIDTH = 3;

    reg  [WIDTH-1:0] a_idx;
    reg  [WIDTH-1:0] b_idx;
    wire [WIDTH-1:0] y_idx;

    integer i, j;
    integer err_cnt;

    // DUT 인스턴스
    copbit_ppu_3d_mul_core #(
        .M(M),
        .WIDTH(WIDTH)
    ) dut (
        .a_idx(a_idx),
        .b_idx(b_idx),
        .y_idx(y_idx)
    );

    // truth 함수: (a * b) mod 8
    function [WIDTH-1:0] mul3d_truth;
        input [WIDTH-1:0] a;
        input [WIDTH-1:0] b;
        integer prod;
    begin
        prod        = a * b;
        mul3d_truth = prod % M;
    end
    endfunction

    initial begin
        $display("=== CoPBit PPU 3D-MUL truthcheck (M=%0d) ===", M);

        err_cnt = 0;

        // (a,b) ∈ {0..7} × {0..7} 전수 검사
        for (i = 0; i < M; i = i + 1) begin
            for (j = 0; j < M; j = j + 1) begin
                a_idx = i[WIDTH-1:0];
                b_idx = j[WIDTH-1:0];

                #1;  // 조합 논리 settle

                if (y_idx !== mul3d_truth(a_idx, b_idx)) begin
                    $display("MISMATCH: a=%0d b=%0d  got=%0d exp=%0d",
                             a_idx, b_idx, y_idx, mul3d_truth(a_idx, b_idx));
                    err_cnt = err_cnt + 1;
                end
            end
        end

        if (err_cnt == 0) begin
            $display("[PASS] op_error_3d_mul = 0 (all %0d combinations)", M*M);
        end else begin
            $display("[FAIL] op_error_3d_mul = %0d (out of %0d combinations)", err_cnt, M*M);
        end

        $finish;
    end

endmodule