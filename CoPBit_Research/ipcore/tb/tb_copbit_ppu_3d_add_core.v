// Testbench for copbit_ppu_3d_add_core
// Q24b – PPU 3D-ADD truthcheck (no channel / no phase / no noise)

`timescale 1ns/1ps

module tb_copbit_ppu_3d_add_core;

    localparam integer M     = 8;
    localparam integer WIDTH = 3;

    reg  [WIDTH-1:0] a_idx;
    reg  [WIDTH-1:0] b_idx;
    wire [WIDTH-1:0] y_idx;

    integer i, j;
    integer err_cnt;

    // DUT
    copbit_ppu_3d_add_core #(
        .M(M),
        .WIDTH(WIDTH)
    ) dut (
        .a_idx(a_idx),
        .b_idx(b_idx),
        .y_idx(y_idx)
    );

    // truth function: (a + b) mod 8
    function [WIDTH-1:0] add3d_truth;
        input [WIDTH-1:0] a;
        input [WIDTH-1:0] b;
        reg   [WIDTH:0]   sum_full;
    begin
        sum_full = a + b;
        add3d_truth = sum_full[WIDTH-1:0];  // M=8 이라 그냥 3bit 사용
    end
    endfunction

    initial begin
        err_cnt = 0;

        $display("=== CoPBit PPU 3D-ADD truthcheck (M=%0d) ===", M);

        for (i = 0; i < M; i = i + 1) begin
            for (j = 0; j < M; j = j + 1) begin
                a_idx = i[WIDTH-1:0];
                b_idx = j[WIDTH-1:0];

                #1;  // 조그만 delta time

                if (y_idx !== add3d_truth(a_idx, b_idx)) begin
                    $display("MISMATCH: a=%0d b=%0d  got=%0d exp=%0d",
                             a_idx, b_idx, y_idx, add3d_truth(a_idx, b_idx));
                    err_cnt = err_cnt + 1;
                end
            end
        end

        if (err_cnt == 0) begin
            $display("[PASS] op_error_3d_add = 0 (all %0d combinations)", M*M);
        end else begin
            $display("[FAIL] op_error_3d_add = %0d / %0d", err_cnt, M*M);
        end

        $finish;
    end

endmodule