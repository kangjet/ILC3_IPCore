`timescale 1ns/1ps
//======================================================
// ILC3 0-code TX core (simple reference)
// - 입력 심벌: 2비트 (0,1,2,3)
// - 각 심벌을 2샘플 시퀀스로 매핑
//   0 -> [-1,  0]
//   1 -> [ 0, -1]
//   2 -> [+1,  0]
//   3 -> [ 0, +1]
// - sym_in_ready = 1일 때만 새 심벌을 받음
// - amp_out_valid는 각 심벌당 2클럭 동안 1이 됨
//======================================================
module ilc3_tx_core #(
    parameter SYMB_WIDTH = 2,
    parameter AMP_WIDTH  = 4
) (
    input  wire                        clk,
    input  wire                        rst_n,

    // 심벌 입력 (TX 상위에서 들어오는 2비트 심벌)
    input  wire [SYMB_WIDTH-1:0]       sym_in,
    input  wire                        sym_in_valid,
    output wire                        sym_in_ready,

    // 아날로그(또는 DAC 입력) 쪽으로 나가는 진폭 신호
    output reg  signed [AMP_WIDTH-1:0] amp_out,
    output reg                         amp_out_valid,
    input  wire                        amp_out_ready
);

    // 내부 상태
    reg                     busy;      // 1이면 현재 심벌에 대한 샘플을 아직 내보내는 중
    reg                     samp_idx;  // 0 or 1 (첫 번째 샘플 / 두 번째 샘플)
    reg [SYMB_WIDTH-1:0]    cur_sym;   // 현재 출력 중인 심벌

    // busy가 0일 때만 새 심벌을 받을 수 있음
    assign sym_in_ready = ~busy;

    // TX 상태머신
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            busy          <= 1'b0;
            samp_idx      <= 1'b0;
            cur_sym       <= {SYMB_WIDTH{1'b0}};
            amp_out       <= {AMP_WIDTH{1'b0}};
            amp_out_valid <= 1'b0;
        end else begin
            // 기본값
            amp_out_valid <= 1'b0;

            if (!busy) begin
                // 현재 출력 중인 심벌이 없을 때: 새 심벌 수신
                if (sym_in_valid && sym_in_ready && amp_out_ready) begin
                    cur_sym  <= sym_in;
                    samp_idx <= 1'b0;
                    busy     <= 1'b1;
                    // 실제 샘플 출력은 다음 클럭부터 시작
                end
            end else begin
                // 현재 심벌에 대한 샘플을 내보내는 중
                if (amp_out_ready) begin
                    amp_out_valid <= 1'b1;
                    // 0-code 매핑
                    case (cur_sym)
                        2'd0: begin
                            if (samp_idx == 1'b0)
                                amp_out <= -1;  // 첫 샘플
                            else
                                amp_out <= 0;   // 두 번째 샘플
                        end
                        2'd1: begin
                            if (samp_idx == 1'b0)
                                amp_out <= 0;
                            else
                                amp_out <= -1;
                        end
                        2'd2: begin
                            if (samp_idx == 1'b0)
                                amp_out <= 1;
                            else
                                amp_out <= 0;
                        end
                        default: begin // 2'd3
                            if (samp_idx == 1'b0)
                                amp_out <= 0;
                            else
                                amp_out <= 1;
                        end
                    endcase

                    // 샘플 인덱스 및 busy 업데이트
                    if (samp_idx == 1'b1) begin
                        // 두 번째 샘플까지 다 보냈으면 다음 심벌을 받을 수 있음
                        busy     <= 1'b0;
                        samp_idx <= 1'b0;
                    end else begin
                        // 첫 샘플을 보냈으므로 다음 클럭에는 두 번째 샘플
                        samp_idx <= 1'b1;
                    end
                end
            end
        end
    end

endmodule