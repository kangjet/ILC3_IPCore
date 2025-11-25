`timescale 1ns/1ps

//======================================================
// ILC3 0-code TX/RX Loopback Simple Testbench
// - 0,1,2,3,0,1,2,3,... 고정 패턴
//======================================================
module tb_ilc3_loopback;

    // Clock / reset
    reg clk;
    reg rst_n;

    // TX interface
    reg  [1:0] sym_in;
    reg        sym_in_valid;
    wire       sym_in_ready;

    wire signed [3:0] amp_out;
    wire              amp_out_valid;
    reg               amp_out_ready;

    // RX interface
    wire signed [3:0] amp_in;
    wire              amp_in_valid;
    wire              amp_in_ready;

    wire [1:0] sym_out;
    wire       sym_out_valid;
    reg        sym_out_ready;

    // Loopback: TX -> RX
    assign amp_in       = amp_out;
    assign amp_in_valid = amp_out_valid;

    //==================================================
    // DUT instances
    //==================================================
    ilc3_tx_core #(
        .SYMB_WIDTH(2),
        .AMP_WIDTH (4)
    ) u_tx (
        .clk          (clk),
        .rst_n        (rst_n),
        .sym_in       (sym_in),
        .sym_in_valid (sym_in_valid),
        .sym_in_ready (sym_in_ready),
        .amp_out      (amp_out),
        .amp_out_valid(amp_out_valid),
        .amp_out_ready(amp_out_ready)
    );

    ilc3_rx_core #(
        .SYMB_WIDTH(2),
        .AMP_WIDTH (4)
    ) u_rx (
        .clk          (clk),
        .rst_n        (rst_n),
        .amp_in       (amp_in),
        .amp_in_valid (amp_in_valid),
        .amp_in_ready (amp_in_ready),
        .sym_out      (sym_out),
        .sym_out_valid(sym_out_valid),
        .sym_out_ready(sym_out_ready)
    );

    //==================================================
    // Clock generation (100 MHz)
    //==================================================
    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    //==================================================
    // Reset
    //==================================================
    initial begin
        rst_n = 1'b0;
        #40;
        rst_n = 1'b1;
    end

    //==================================================
    // Test pattern: 0,1,2,3,0,1,2,3, ...
    //==================================================
    localparam integer N_SYM = 32;

    reg [1:0] exp_sym [0:N_SYM-1];
    integer i;

    // TX->RX 검증용 심볼 FIFO (scoreboard)
    reg [1:0] tx_sym_fifo [0:N_SYM-1];
    integer wptr, rptr;

    initial begin
        for (i = 0; i < N_SYM; i = i + 1) begin
            exp_sym[i] = i[1:0];  // 0,1,2,3 반복
        end
    end

    // ready는 항상 1로
    initial begin
        amp_out_ready = 1'b1;
        sym_out_ready = 1'b1;
    end

   // RX 타이밍 정렬:
   //  - RX는 각 심벌의 두 번째 샘플이 들어오는 클럭에서 해당 심벌을 디코드한다.
   //  - TX 기준으로 보면, 심벌 k를 입력한 뒤 두 샘플이 지나서야 RX에서 k가 출력되므로
   //    심벌 인덱스 관점에서 항상 1심벌 파이프라인 레이턴시를 가진다.
   //  → 따라서 이 scoreboard에서는 rx_idx >= 1일 때 TX[rx_idx-1]를 기대값으로 사용한다.

    //==================================================
    // TX 드라이버
    //==================================================
    integer tx_idx;

    initial begin
        sym_in       = 2'd0;
        sym_in_valid = 1'b0;
        tx_idx       = 0;

        // 리셋 해제 대기
        wait(rst_n == 1'b1);
        @(posedge clk);

        sym_in_valid = 1'b1;
        sym_in       = exp_sym[0];

        forever begin
            @(posedge clk);
            if (sym_in_valid && sym_in_ready) begin
                // 현재 전송 중인 심볼을 FIFO에 기록 (scoreboard)
                if (wptr < N_SYM) begin
                    // TX → RX 디버그: 실제로 전송한 심볼 기록
                    $display("[TX ] @%0t ns: tx_idx=%0d wptr=%0d sym=%0d",
                             $time, tx_idx, wptr, sym_in);
                    tx_sym_fifo[wptr] = sym_in;
                    wptr = wptr + 1;
                end

                tx_idx = tx_idx + 1;
                if (tx_idx < N_SYM) begin
                    sym_in <= exp_sym[tx_idx];
                end else begin
                    sym_in_valid <= 1'b0;
                end
            end
        end
    end

    //==================================================
    // RX 체크
    //==================================================
    integer rx_idx;
    integer err_cnt;

    initial begin
        rx_idx  = 0;
        err_cnt = 0;
        wptr    = 0;
        rptr    = 0;
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            rx_idx  <= 0;
            err_cnt <= 0;
            rptr    <= 0;
        end else begin
            if (sym_out_valid && sym_out_ready) begin
                if (rx_idx < N_SYM) begin
                    // ILC3 RX는 1심볼 파이프라인 레이턴시를 가지므로,
                    // rx_idx >= 1일 때는 TX[rx_idx-1]와 매칭한다.
                    integer tx_idx_expect;
                    if (rx_idx == 0)
                        tx_idx_expect = 0;
                    else
                        tx_idx_expect = rx_idx - 1;

                    if (tx_idx_expect < N_SYM) begin
                        $display("[CHK] @%0t ns: idx=%0d tx[%0d]=%0d rx=%0d",
                                 $time, rx_idx, tx_idx_expect, tx_sym_fifo[tx_idx_expect], sym_out);

                        if (sym_out !== tx_sym_fifo[tx_idx_expect]) begin
                            $display("[ERR] @%0t ns: idx=%0d expected=%0d, got=%0d",
                                     $time, rx_idx, tx_sym_fifo[tx_idx_expect], sym_out);
                            err_cnt <= err_cnt + 1;
                        end else begin
                            $display("[OK ] @%0t ns: idx=%0d sym=%0d",
                                     $time, rx_idx, sym_out);
                        end
                    end else begin
                        $display("[WARN] @%0t ns: idx=%0d RX symbol with out-of-range TX index %0d, got=%0d",
                                 $time, rx_idx, tx_idx_expect, sym_out);
                        err_cnt <= err_cnt + 1;
                    end

                    rx_idx <= rx_idx + 1;
                    rptr   <= rptr + 1;  // rptr는 필요시 확장을 위해 유지
                end
            end
        end
    end

    //==================================================
    // 종료 조건
    //==================================================
    initial begin
        wait(rst_n == 1'b1);
        wait(rx_idx == N_SYM);
        #40;
        $display("======================================");
        $display("ILC3 0-code simple loopback finished");
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