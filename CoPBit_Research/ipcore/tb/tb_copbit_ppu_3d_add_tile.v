// Testbench for copbit_ppu_3d_add_tile
// NLANES개의 lane을 동시에 (a+b) mod 8 검증

`timescale 1ns/1ps

module tb_copbit_ppu_3d_add_tile;

    localparam integer M      = 8;
    localparam integer WIDTH  = 3;
    localparam integer NLANES = 16;

    wire [NLANES*WIDTH-1:0] a_idx_flat;
    wire [NLANES*WIDTH-1:0] b_idx_flat;
    wire [NLANES*WIDTH-1:0] y_idx_flat;

    integer i, lane;
    integer err_cnt;

    reg  [WIDTH-1:0] a_idx_arr [0:NLANES-1];
    reg  [WIDTH-1:0] b_idx_arr [0:NLANES-1];
    wire [WIDTH-1:0] y_idx_arr [0:NLANES-1];

    genvar g;
    generate
        for (g = 0; g < NLANES; g = g + 1) begin : gen_flat_map
            assign a_idx_flat[(g+1)*WIDTH-1 : g*WIDTH] = a_idx_arr[g];
            assign b_idx_flat[(g+1)*WIDTH-1 : g*WIDTH] = b_idx_arr[g];
            assign y_idx_arr[g] = y_idx_flat[(g+1)*WIDTH-1 : g*WIDTH];
        end
    endgenerate

    // DUT
    copbit_ppu_3d_add_tile #(
        .M(M),
        .WIDTH(WIDTH),
        .NLANES(NLANES)
    ) dut (
        .a_idx_flat(a_idx_flat),
        .b_idx_flat(b_idx_flat),
        .y_idx_flat(y_idx_flat)
    );

    // truth function: (a + b) mod 8
    function [WIDTH-1:0] add3d_truth;
        input [WIDTH-1:0] a;
        input [WIDTH-1:0] b;
        reg   [WIDTH:0]   sum_full;
    begin
        sum_full     = a + b;
        add3d_truth  = sum_full[WIDTH-1:0];  // M=8 고정
    end
    endfunction

    initial begin
        err_cnt     = 0;

        $display("=== CoPBit PPU 3D-ADD tile truthcheck (M=%0d, NLANES=%0d) ===", M, NLANES);

        // 간단한 패턴: i를 기준으로 lane마다 다른 (a,b) 생성
        // 예: a_lane = (i + lane) mod 8, b_lane = (2*i + lane) mod 8
        for (i = 0; i < 16; i = i + 1) begin
            for (lane = 0; lane < NLANES; lane = lane + 1) begin
                a_idx_arr[lane] = (i + lane)   % M;
                b_idx_arr[lane] = (2*i + lane) % M;
            end

            #1; // delta

            for (lane = 0; lane < NLANES; lane = lane + 1) begin
                reg [WIDTH-1:0] a_l;
                reg [WIDTH-1:0] b_l;
                reg [WIDTH-1:0] y_l;
                reg [WIDTH-1:0] y_exp;

                a_l   = a_idx_arr[lane];
                b_l   = b_idx_arr[lane];
                y_l   = y_idx_arr[lane];
                y_exp = add3d_truth(a_l, b_l);

                if (y_l !== y_exp) begin
                    $display("MISMATCH: i=%0d lane=%0d  a=%0d b=%0d  got=%0d exp=%0d",
                             i, lane, a_l, b_l, y_l, y_exp);
                    err_cnt = err_cnt + 1;
                end
            end
        end

        if (err_cnt == 0) begin
            $display("[PASS] op_error_3d_add_tile = 0 (M=%0d, NLANES=%0d)", M, NLANES);
        end else begin
            $display("[FAIL] op_error_3d_add_tile = %0d", err_cnt);
        end

        $finish;
    end

endmodule