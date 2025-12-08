// ============================================================
// File: tb/tb_copbit_ppu_3d_mul_tile.v
// Desc: Testbench for copbit_ppu_3d_mul_tile (M=8, NLANES=16)
// ============================================================
`timescale 1ns/1ps

module tb_copbit_ppu_3d_mul_tile;

    localparam integer M      = 8;
    localparam integer WIDTH  = 3;
    localparam integer NLANES = 16;

    reg  [NLANES*WIDTH-1:0] a_idx_flat;
    reg  [NLANES*WIDTH-1:0] b_idx_flat;
    wire [NLANES*WIDTH-1:0] y_idx_flat;

    integer lane;
    integer bit_idx;
    integer base;
    integer vec;
    integer err_cnt;

    reg [WIDTH-1:0] a_arr   [0:NLANES-1];
    reg [WIDTH-1:0] b_arr   [0:NLANES-1];
    reg [WIDTH-1:0] exp_y   [0:NLANES-1];
    reg [WIDTH-1:0] y_tmp;

    // DUT 인스턴스
    copbit_ppu_3d_mul_tile #(
        .M(M),
        .WIDTH(WIDTH),
        .NLANES(NLANES)
    ) dut (
        .a_idx_flat(a_idx_flat),
        .b_idx_flat(b_idx_flat),
        .y_idx_flat(y_idx_flat)
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
        $display("=== CoPBit PPU 3D-MUL tile truthcheck (M=%0d, NLANES=%0d) ===", M, NLANES);

        err_cnt = 0;
        a_idx_flat = {NLANES*WIDTH{1'b0}};
        b_idx_flat = {NLANES*WIDTH{1'b0}};

        // vec = 0..7에 대해 여러 패턴 생성
        for (vec = 0; vec < 8; vec = vec + 1) begin
            // 1) lane별 입력/기대값 계산
            for (lane = 0; lane < NLANES; lane = lane + 1) begin
                a_arr[lane] = (vec + lane)   % M;
                b_arr[lane] = (2*vec + lane) % M;
                exp_y[lane] = mul3d_truth(a_arr[lane], b_arr[lane]);
            end

            // 2) flat 버스에 패킹
            a_idx_flat = {NLANES*WIDTH{1'b0}};
            b_idx_flat = {NLANES*WIDTH{1'b0}};
            for (lane = 0; lane < NLANES; lane = lane + 1) begin
                base = lane * WIDTH;
                for (bit_idx = 0; bit_idx < WIDTH; bit_idx = bit_idx + 1) begin
                    a_idx_flat[base + bit_idx] = a_arr[lane][bit_idx];
                    b_idx_flat[base + bit_idx] = b_arr[lane][bit_idx];
                end
            end

            // 3) 조합논리 settle 대기
            #1;

            // 4) 결과 비교
            for (lane = 0; lane < NLANES; lane = lane + 1) begin
                base = lane * WIDTH;
                for (bit_idx = 0; bit_idx < WIDTH; bit_idx = bit_idx + 1) begin
                    y_tmp[bit_idx] = y_idx_flat[base + bit_idx];
                end
                if (y_tmp !== exp_y[lane]) begin
                    $display("MISMATCH: vec=%0d lane=%0d  a=%0d b=%0d got=%0d exp=%0d",
                             vec, lane, a_arr[lane], b_arr[lane], y_tmp, exp_y[lane]);
                    err_cnt = err_cnt + 1;
                end
            end
        end

        if (err_cnt == 0) begin
            $display("[PASS] op_error_3d_mul_tile = 0 (M=%0d, NLANES=%0d)", M, NLANES);
        end else begin
            $display("[FAIL] op_error_3d_mul_tile = %0d", err_cnt);
        end

        $finish;
    end

endmodule