`timescale 1ns/1ps
//======================================================
// tb_ilc3_ipcore_x8_loopback.v
//  - ilc3_ipcore_x8_top용 간단 루프백 테스트벤치 v0.1
//  - clean 채널에서 8 lane 모두 PASS 확인
//======================================================
module tb_ilc3_ipcore_x8_loopback;

`ifndef TB_N_SYM
  `define TB_N_SYM 1024
`endif

`ifndef TB_CH_ADD_NOISE
  `define TB_CH_ADD_NOISE 0
`endif

`ifndef TB_CH_NOISE_LSB
  `define TB_CH_NOISE_LSB 1
`endif

// 심볼 개수 파라미터 (테스트 심볼 수)
localparam integer N_SYM = `TB_N_SYM;

localparam integer NUM_LANES    = 8;
localparam integer AMP_WIDTH    = 4;

// 채널 파라미터 (top과 이름 맞추기)
localparam integer CH_GAIN_NUM   = 1;
localparam integer CH_GAIN_DEN   = 1;
localparam integer CH_OFFSET     = 0;
localparam integer CH_ADD_NOISE  = `TB_CH_ADD_NOISE;   // 0=clean (default), can be overridden by -DTB_CH_ADD_NOISE
localparam integer CH_NOISE_LSB  = `TB_CH_NOISE_LSB;   // can be overridden by -DTB_CH_NOISE_LSB

    //-----------------------------
    // 클럭/리셋
    //-----------------------------
    reg clk;
    reg rst_n;

    initial clk = 1'b0;
    always #10 clk = ~clk;   // 50MHz (20ns period)

    //-----------------------------
    // x8 IPCore I/F 신호
    //-----------------------------
    reg  [2*NUM_LANES-1:0] tx_data;
    reg  [NUM_LANES-1:0]   tx_valid;
    wire [NUM_LANES-1:0]   tx_ready;

    wire [2*NUM_LANES-1:0] rx_data;
    wire [NUM_LANES-1:0]   rx_valid;
    reg  [NUM_LANES-1:0]   rx_ready;

    reg  [31:0]            err_cnt [0:NUM_LANES-1];
    integer                rx_idx  [0:NUM_LANES-1];

    //-----------------------------
    // DUT: ilc3_ipcore_x8_top
    //-----------------------------
 ilc3_ipcore_x8_top #(
    .NUM_LANES    (NUM_LANES),
    .AMP_WIDTH    (AMP_WIDTH),
    .CH_GAIN_NUM  (CH_GAIN_NUM),
    .CH_GAIN_DEN  (CH_GAIN_DEN),
    .CH_OFFSET    (CH_OFFSET),
    .CH_ADD_NOISE (CH_ADD_NOISE),
    .CH_NOISE_LSB (CH_NOISE_LSB)
) dut (
    .clk      (clk),
    .rst_n    (rst_n),
    .tx_data  (tx_data),
    .tx_valid (tx_valid),
    .tx_ready (tx_ready),
    .rx_data  (rx_data),
    .rx_valid (rx_valid),
    .rx_ready (rx_ready)
);

// RX 쪽 심볼 인덱스 및 에러 카운터 관리
integer lane_idx;
integer lane_r;

initial begin
    for (lane_r = 0; lane_r < NUM_LANES; lane_r = lane_r + 1) begin
        err_cnt[lane_r] = 0;
        rx_idx[lane_r]  = 0;
    end
end

always @(posedge clk) begin
    if (!rst_n) begin
        for (lane_idx = 0; lane_idx < NUM_LANES; lane_idx = lane_idx + 1) begin
            err_cnt[lane_idx] <= 0;
            rx_idx[lane_idx]  <= 0;
        end
    end else begin
        for (lane_idx = 0; lane_idx < NUM_LANES; lane_idx = lane_idx + 1) begin
            if (rx_valid[lane_idx] && rx_ready[lane_idx]) begin
                // 기대 심볼: 0,1,2,3 반복 (rx_idx의 하위 2비트)
                if (rx_data[2*lane_idx +: 2] !== rx_idx[lane_idx][1:0]) begin
                    err_cnt[lane_idx] <= err_cnt[lane_idx] + 1;
                end
                rx_idx[lane_idx] <= rx_idx[lane_idx] + 1;
            end
        end
    end
end

    //-----------------------------
    // 테스트 시퀀스
    //-----------------------------
    integer i;
    integer lane;
    integer sym_idx;
    integer total_err;

    initial begin
        // 초기값
        rst_n    = 1'b0;
        tx_data  = {2*NUM_LANES{1'b0}};
        tx_valid = {NUM_LANES{1'b0}};
        rx_ready = {NUM_LANES{1'b1}};   // 항상 ready로 두고 시작

        // 현재 테스트 파라미터 출력 (디버그용)
        $display("[TB x8] N_SYM=%0d CH_ADD_NOISE=%0d CH_NOISE_LSB=%0d",
                 N_SYM, CH_ADD_NOISE, CH_NOISE_LSB);

        // 리셋
        repeat (5) @(posedge clk);
        rst_n = 1'b1;
        repeat (2) @(posedge clk);

        // 심볼 전송: 0,1,2,3 반복 패턴 (모든 lane 동일)
        for (sym_idx = 0; sym_idx < N_SYM; sym_idx = sym_idx + 1) begin
            for (i = 0; i < NUM_LANES; i = i + 1) begin
                // lane i 에 같은 심볼 패턴 브로드캐스트
                tx_data[2*i +: 2] = sym_idx[1:0];
            end
            tx_valid = {NUM_LANES{1'b1}};
            @(posedge clk);
            // 현재 구조에서는 backpressure 안 쓰는 걸 전제로, tx_ready는 체크 안 함
        end

        // TX 정지
        tx_valid = {NUM_LANES{1'b0}};
        tx_data  = {2*NUM_LANES{1'b0}};

        // 파이프라인 flush 여유
        repeat (50) @(posedge clk);

        // 에러 합산
        total_err = 0;
        for (lane = 0; lane < NUM_LANES; lane = lane + 1) begin
            total_err = total_err + err_cnt[lane];
        end

        // 결과 출력
        $display("======================================");
        $display("ILC3 IPCore x8 Top loopback finished");
        $display("  NUM_LANES = %0d", NUM_LANES);
        $display("  N_SYM     = %0d", N_SYM);
        for (lane = 0; lane < NUM_LANES; lane = lane + 1) begin
            $display("  lane %0d err_cnt = %0d", lane, err_cnt[lane]);
        end
        $display("  total_err = %0d", total_err);
        if (total_err == 0)
            $display("  RESULT    = PASS");
        else
            $display("  RESULT    = FAIL");
        $display("======================================");

        $finish;
    end

endmodule