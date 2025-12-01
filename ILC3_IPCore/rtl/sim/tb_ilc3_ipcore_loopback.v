`timescale 1ns/1ps
//======================================================
// tb_ilc3_ipcore_loopback.v
//  - ILC3 IPCore Top + 채널모델 통합 루프백 테스트
//  - 기능:
//      * 상위에서 0,1,2,3,0,1,2,3,... 패턴 송신
//      * ilc3_ipcore_top → ilc3_channel_model → ilc3_ipcore_top
//      * 수신 심볼을 FIFO에 저장된 기대값과 비교
//======================================================
module tb_ilc3_ipcore_loopback;

`ifndef TB_N_SYM
  `define TB_N_SYM 1024
`endif

`ifndef CH_ADD_NOISE
  `define CH_ADD_NOISE 0
`endif

    // 심볼 개수 (필요하면 1024 → 10000 등으로 쉽게 변경 가능)
    localparam integer N_SYM      = `TB_N_SYM;
    localparam integer AMP_WIDTH  = 4;

    //==================================================
    // Clock / Reset
    //==================================================
    reg clk;
    reg rst_n;

    initial begin
        clk = 0;
        forever #5 clk = ~clk;  // 100 MHz
    end

    initial begin
        rst_n = 0;
        #100;
        rst_n = 1;
    end

    //==================================================
    // 상위 심볼 인터페이스
    //==================================================
    reg  [1:0] tx_sym_in;
    reg        tx_sym_valid;
    wire       tx_sym_ready;

    wire [1:0] rx_sym_out;
    wire       rx_sym_valid;
    reg        rx_sym_ready;

    //==================================================
    // PHY 진폭 인터페이스 (IPCore ↔ 채널 모델)
    //==================================================
    wire signed [AMP_WIDTH-1:0] tx_amp_out;
    wire                        tx_amp_valid;
    wire                        tx_amp_ready;

    wire signed [AMP_WIDTH-1:0] ch_amp_mid;   // 채널 중간 노드
    wire                        ch_mid_valid;
    wire                        ch_mid_ready;

    //==================================================
    // DUT: ILC3 IPCore Top
    //==================================================
    ilc3_ipcore_top #(
        .AMP_WIDTH(AMP_WIDTH)
    ) u_ipcore (
        .clk          (clk),
        .rst_n        (rst_n),
        .cfg_enable   (1'b1),
        .cfg_test_mode(1'b0),

        // 상위 심볼 인터페이스
        .tx_sym_in    (tx_sym_in),
        .tx_sym_valid (tx_sym_valid),
        .tx_sym_ready (tx_sym_ready),

        .rx_sym_out   (rx_sym_out),
        .rx_sym_valid (rx_sym_valid),
        .rx_sym_ready (rx_sym_ready),

        // PHY 인터페이스
        .tx_amp_out   (tx_amp_out),
        .tx_amp_valid (tx_amp_valid),
        .tx_amp_ready (tx_amp_ready),

        .rx_amp_in    (ch_amp_mid),
        .rx_amp_valid (ch_mid_valid),
        .rx_amp_ready (ch_mid_ready),
        .status_err_cnt()
    );

    //==================================================
    // 채널 모델
    //  - 현재는 간단한 통과 + (옵션) 노이즈
    //  - ADD_NOISE 파라미터로 노이즈 on/off 제어
    //==================================================
    localparam integer CH_GAIN_NUM  = 1;
    localparam integer CH_GAIN_DEN  = 1;
    localparam integer CH_OFFSET    = 0;

    // 채널 노이즈 강도 (0=off, 1=level-1, 2=level-2, ...)
    // clean loopback 기본값은 0으로 두고,
    // 필요 시 이 값을 1, 2, ...로 바꿔서 노이즈 버전을 테스트한다.
    localparam integer CH_ADD_NOISE_PARAM = `CH_ADD_NOISE;

    ilc3_channel_model #(
        .AMP_WIDTH (AMP_WIDTH),
        .GAIN_NUM  (CH_GAIN_NUM),
        .GAIN_DEN  (CH_GAIN_DEN),
        .OFFSET    (CH_OFFSET),
        .ADD_NOISE (CH_ADD_NOISE_PARAM)
    ) u_ch (
        .clk          (clk),
        .rst_n        (rst_n),

        // 입력: IPCore TX 측
        .amp_in       (tx_amp_out),
        .amp_in_valid (tx_amp_valid),
        .amp_in_ready (tx_amp_ready),

        // 출력: IPCore RX 측
        .amp_out      (ch_amp_mid),
        .amp_out_valid(ch_mid_valid),
        .amp_out_ready(ch_mid_ready)
    );

    //==================================================
    // TX 쪽: 패턴 생성 + 심볼 FIFO 기록
    //==================================================
    reg [1:0] tx_sym_fifo [0:N_SYM-1];
    integer wptr;
    integer tx_idx;

    initial begin
        tx_sym_in   = 2'd0;
        tx_sym_valid= 1'b0;
        wptr        = 0;
        tx_idx      = 0;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tx_sym_in    <= 2'd0;
            tx_sym_valid <= 1'b0;
            wptr         <= 0;
            tx_idx       <= 0;
        end else begin
            // 현재 심볼이 accept된 경우 (valid & ready)
            if (tx_sym_valid && tx_sym_ready) begin
                wptr   <= wptr + 1;
                tx_idx <= tx_idx + 1;
            end

            // 아직 보낼 심볼이 남아 있고, 현재 valid가 비어 있는 경우 새 심볼 세팅
            if (!tx_sym_valid && (tx_idx < N_SYM)) begin
                // 0,1,2,3 반복 패턴
                tx_sym_in <= tx_idx[1:0];

                // FIFO 기록 (tx_idx 위치에 기대 심볼 저장)
                tx_sym_fifo[tx_idx] <= tx_idx[1:0];

                tx_sym_valid <= 1'b1;

                $display("[TX ] @%0t ns: tx_idx=%0d wptr=%0d sym=%0d",
                         $time, tx_idx, wptr, tx_idx[1:0]);
            end else if (tx_sym_valid && tx_sym_ready) begin
                // 방금 accept 된 직후에는 valid 내려줌
                tx_sym_valid <= 1'b0;
            end
        end
    end

    //==================================================
    // RX 쪽: 수신 심볼 비교 (scoreboard)
    //==================================================
    integer rx_idx;
    integer err_cnt;
    integer rptr;  // FIFO read pointer

    initial begin
        rx_sym_ready = 1'b1;  // 상위는 항상 수신 준비
        rx_idx       = 0;
        err_cnt      = 0;
        rptr         = 0;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rx_idx  <= 0;
            err_cnt <= 0;
            rptr    <= 0;
        end else begin
            if (rx_sym_valid && rx_sym_ready) begin
                // FIFO 기반 스코어보드: TX에서 기록한 순서대로 비교
                if (rptr < N_SYM) begin
                    $display("[CHK] @%0t ns: idx=%0d tx[%0d]=%0d rx=%0d",
                             $time, rx_idx, rptr, tx_sym_fifo[rptr], rx_sym_out);

                    if (rx_sym_out !== tx_sym_fifo[rptr]) begin
                        $display("[ERR] @%0t ns: idx=%0d expected=%0d, got=%0d",
                                 $time, rx_idx, tx_sym_fifo[rptr], rx_sym_out);
                        err_cnt <= err_cnt + 1;
                    end else begin
                        $display("[OK ] @%0t ns: idx=%0d sym=%0d",
                                 $time, rx_idx, rx_sym_out);
                    end

                    rptr <= rptr + 1;
                end

                rx_idx <= rx_idx + 1;
            end
        end
    end

    //==================================================
    // 시뮬레이션 종료 조건
    //==================================================
    initial begin
        // N_SYM 개 수신 완료까지 대기
        wait (rx_idx == N_SYM);
        #40;
        $display("======================================");
        $display("ILC3 IPCore Top loopback finished");
        $display("  N_SYM   = %0d", N_SYM);
        $display("  err_cnt = %0d", err_cnt);
        if (err_cnt == 0)
            $display("  RESULT  = PASS");
        else
            $display("  RESULT  = FAIL");
        $display("======================================");
        $finish;
    end

endmodule