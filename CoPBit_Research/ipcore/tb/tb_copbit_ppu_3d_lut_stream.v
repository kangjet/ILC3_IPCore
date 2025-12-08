// CoPBit PPU IPCore v0.1
// Core #8 – 3D-LUT stream core (handshake) truthcheck TB

`timescale 1ps/1ps

module tb_copbit_ppu_3d_lut_stream;

    localparam integer M      = 8;
    localparam integer WIDTH  = 3;
    localparam integer NLANES = 16;

    reg                      clk;
    reg                      rst_n;

    reg                      in_valid;
    wire                     in_ready;
    reg  [NLANES*WIDTH-1:0]  in_idx_flat;

    wire                     out_valid;
    reg                      out_ready;
    wire [NLANES*WIDTH-1:0]  out_idx_flat;

    integer vec;
    integer lane;
    integer err_cnt;
    integer wait_cycles;

    reg  [WIDTH-1:0] in_idx_arr [0:NLANES-1];
    reg  [WIDTH-1:0] out_idx_arr[0:NLANES-1];

    // DUT
    copbit_ppu_3d_lut_stream #(
        .M(M),
        .WIDTH(WIDTH),
        .NLANES(NLANES)
    ) dut (
        .clk        (clk),
        .rst_n      (rst_n),
        .in_valid   (in_valid),
        .in_ready   (in_ready),
        .in_idx_flat(in_idx_flat),
        .out_valid  (out_valid),
        .out_ready  (out_ready),
        .out_idx_flat(out_idx_flat)
    );

    // truth LUT (Core #6과 동일)
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

    task pack_input;
        integer i;
        begin
            for (i = 0; i < NLANES; i = i + 1) begin
                in_idx_flat[i*WIDTH +: WIDTH] = in_idx_arr[i];
            end
        end
    endtask

    task unpack_output;
        integer i;
        begin
            for (i = 0; i < NLANES; i = i + 1) begin
                out_idx_arr[i] = out_idx_flat[i*WIDTH +: WIDTH];
            end
        end
    endtask

    // 클럭 생성 (2ps 주기)
    initial begin
        clk = 1'b0;
        forever #1 clk = ~clk;
    end

    initial begin
        rst_n      = 1'b0;
        in_valid   = 1'b0;
        out_ready  = 1'b0;
        in_idx_flat = {NLANES*WIDTH{1'b0}};
        err_cnt    = 0;

        // 리셋
        #5;
        rst_n     = 1'b1;
        out_ready = 1'b1;

        $display("=== CoPBit PPU 3D-LUT stream core (handshake) test (M=%0d, NLANES=%0d) ===", M, NLANES);

        // vec = 0..M-1 에 대해 순차 스트림 테스트
        for (vec = 0; vec < M; vec = vec + 1) begin
            // 입력 패턴 준비
            for (lane = 0; lane < NLANES; lane = lane + 1) begin
                in_idx_arr[lane] = (vec + lane) % M;
            end
            pack_input();

            // in_ready 가 1이 될 때까지 대기
            @(posedge clk);
            while (!in_ready) begin
                @(posedge clk);
            end

            // 한 클럭 동안 in_valid 펄스
            in_valid = 1'b1;
            @(posedge clk);
            in_valid = 1'b0;

            // 최소 1클럭 이상 레이턴시를 허용하면서,
            // out_valid가 올라올 때까지 최대 4클럭까지 대기
            wait_cycles = 0;

            while (!out_valid && wait_cycles < 4) begin
                @(posedge clk);
                wait_cycles = wait_cycles + 1;
            end

            if (!out_valid) begin
                $display("[ERR] vec=%0d: timeout waiting out_valid (waited %0d cycles)", vec, wait_cycles);
                err_cnt = err_cnt + 1;
            end else begin
                // out_valid 가 1인 상태에서 출력 검증
                unpack_output();
                for (lane = 0; lane < NLANES; lane = lane + 1) begin
                    if (out_idx_arr[lane] !== lut3d_truth(in_idx_arr[lane])) begin
                        $display("[ERR] vec=%0d lane=%0d  in=%0d  out=%0d  exp=%0d",
                                 vec, lane, in_idx_arr[lane], out_idx_arr[lane],
                                 lut3d_truth(in_idx_arr[lane]));
                        err_cnt = err_cnt + 1;
                    end
                end
            end

            // 다음 vec 로 넘어가기 전에 한 클럭 정도 여유
            @(posedge clk);
        end

        if (err_cnt == 0) begin
            $display("[PASS] copbit_ppu_3d_lut_stream (handshake): all vectors OK (M=%0d, NLANES=%0d)", M, NLANES);
        end else begin
            $display("[FAIL] copbit_ppu_3d_lut_stream (handshake): op_error_3d_lut_stream = %0d", err_cnt);
        end

        #10;
        $finish;
    end

endmodule