`timescale 1ns/1ps

module tb_copbit_ppu_3d_add_stream;

    localparam integer M      = 8;
    localparam integer WIDTH  = 3;
    localparam integer NLANES = 16;

    // DUT I/O
    reg                          clk;
    reg                          rst_n;
    reg                          in_valid;
    wire                         in_ready;
    reg  [NLANES*WIDTH-1:0]      in_a_idx_flat;
    reg  [NLANES*WIDTH-1:0]      in_b_idx_flat;
    wire                         out_valid;
    reg                          out_ready;
    wire [NLANES*WIDTH-1:0]      out_y_idx_flat;

    // 기대 출력값 (lane별)
    reg  [WIDTH-1:0] exp_y_arr [0:NLANES-1];

    integer err_cnt;
    integer vec;
    integer lane;
    integer bit_idx;
    integer base;

    reg [WIDTH-1:0] a_tmp;
    reg [WIDTH-1:0] b_tmp;
    reg [WIDTH-1:0] y_tmp;

    // DUT 인스턴스
    copbit_ppu_3d_add_stream #(
        .M(M),
        .WIDTH(WIDTH),
        .NLANES(NLANES)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .in_valid(in_valid),
        .in_ready(in_ready),
        .in_a_idx_flat(in_a_idx_flat),
        .in_b_idx_flat(in_b_idx_flat),
        .out_valid(out_valid),
        .out_ready(out_ready),
        .out_y_idx_flat(out_y_idx_flat)
    );

    // truth 함수: (a + b) mod 8
    function [WIDTH-1:0] add3d_truth;
        input [WIDTH-1:0] a;
        input [WIDTH-1:0] b;
        reg   [WIDTH:0]   sum_full;
    begin
        sum_full    = a + b;
        add3d_truth = sum_full[WIDTH-1:0];  // M=8, 단순 3bit
    end
    endfunction

    // 클럭 생성: 10ns period
    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    // 테스트 시나리오
    initial begin
        $display("=== CoPBit PPU 3D-ADD stream core (handshake) test (M=%0d, NLANES=%0d) ===", M, NLANES);

        // 초기화
        rst_n          = 1'b0;
        in_valid       = 1'b0;
        in_a_idx_flat  = {NLANES*WIDTH{1'b0}};
        in_b_idx_flat  = {NLANES*WIDTH{1'b0}};
        out_ready      = 1'b1;  // 이번 TB에서는 항상 소비 가능하게 둠
        err_cnt        = 0;

        // reset 펄스
        #20;
        rst_n = 1'b1;
        #20;

        // vec=0..7까지 여러 벡터를 순차 전송
        for (vec = 0; vec < 8; vec = vec + 1) begin
            // 1) 입력 타일 + 기대값 세팅
            in_a_idx_flat = {NLANES*WIDTH{1'b0}};
            in_b_idx_flat = {NLANES*WIDTH{1'b0}};
            for (lane = 0; lane < NLANES; lane = lane + 1) begin
                a_tmp = (vec + lane)   % M;
                b_tmp = (2*vec + lane) % M;
                exp_y_arr[lane] = add3d_truth(a_tmp, b_tmp);

                base = lane * WIDTH;
                for (bit_idx = 0; bit_idx < WIDTH; bit_idx = bit_idx + 1) begin
                    in_a_idx_flat[base + bit_idx] = a_tmp[bit_idx];
                    in_b_idx_flat[base + bit_idx] = b_tmp[bit_idx];
                end
            end

            // 2) in_ready가 1인 상태에서 in_valid 1사이클 펄스
            @(posedge clk);
            // 혹시라도 향후 back-pressure TB에서 in_ready가 0일 수 있으니 체크
            if (!in_ready) begin
                // in_ready가 0이면 1이 될 때까지 대기
                while (!in_ready) @(posedge clk);
            end
            in_valid = 1'b1;
            @(posedge clk);
            in_valid = 1'b0;

            // 3) 1클럭 뒤에 out_valid=1 이고 값이 맞는지 확인
            @(posedge clk);
            if (!out_valid) begin
                $display("ERROR: vec=%0d 에서 out_valid가 1이 아님", vec);
                err_cnt = err_cnt + 1;
            end else begin
                for (lane = 0; lane < NLANES; lane = lane + 1) begin
                    base = lane * WIDTH;
                    for (bit_idx = 0; bit_idx < WIDTH; bit_idx = bit_idx + 1) begin
                        y_tmp[bit_idx] = out_y_idx_flat[base + bit_idx];
                    end
                    if (y_tmp !== exp_y_arr[lane]) begin
                        $display("MISMATCH: vec=%0d lane=%0d  got=%0d exp=%0d",
                                 vec, lane, y_tmp, exp_y_arr[lane]);
                        err_cnt = err_cnt + 1;
                    end
                end
            end
        end

        if (err_cnt == 0) begin
            $display("[PASS] copbit_ppu_3d_add_stream (handshake): all vectors OK (M=%0d, NLANES=%0d)", M, NLANES);
        end else begin
            $display("[FAIL] copbit_ppu_3d_add_stream (handshake): err_cnt=%0d", err_cnt);
        end

        $finish;
    end

endmodule