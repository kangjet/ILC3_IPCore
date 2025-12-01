`timescale 1ns/1ps
//======================================================
// ilc3_ipcore_x8_top.v
//  - ILC3 IPCore 1-lane을 8개 병렬로 묶은 x8 래퍼
//  - SoC/제품에서 바로 사용 가능한 형태의 포트 정의용 v0.1
//
//  - 특징
//    * lane 수 파라미터 (기본 8)
//    * 각 lane당 2bit 심볼 I/F (tx/rx)
//    * lane 별 err_cnt 출력
//    * 나중에 cfg 레지스터/테스트 모드/노이즈 모드 등을
//      이 top 기준으로 추가 정의 가능
//======================================================
module ilc3_ipcore_x8_top #(
    parameter integer NUM_LANES    = 8,
    parameter integer AMP_WIDTH    = 4,
    // 채널 파라미터 (지금은 공통 값, 필요 시 per-lane 파라미터로 확장)
    parameter integer CH_GAIN_NUM   = 1,
    parameter integer CH_GAIN_DEN   = 1,
    parameter integer CH_OFFSET     = 0,
    parameter integer CH_ADD_NOISE  = 0,   // 0=clean, 1/2/3 = lvl1/lvl2/lvl_real
    parameter integer CH_NOISE_LSB  = 1
)(
    input  wire                     clk,
    input  wire                     rst_n,

    //--------------------------------------------------
    // TX 쪽: SoC -> IPCore
    //  - tx_data : lane당 2bit, 총 2*NUM_LANES bit
    //  - tx_valid: lane별 valid
    //  - tx_ready: lane별 ready (backpressure)
    //--------------------------------------------------
    input  wire [2*NUM_LANES-1:0]   tx_data,
    input  wire [NUM_LANES-1:0]     tx_valid,
    output wire [NUM_LANES-1:0]     tx_ready,

    //--------------------------------------------------
    // RX 쪽: IPCore -> SoC
    //  - rx_data : lane당 2bit, 총 2*NUM_LANES bit
    //  - rx_valid: lane별 valid
    //  - rx_ready: lane별 ready
    //--------------------------------------------------
    output wire [2*NUM_LANES-1:0]   rx_data,
    output wire [NUM_LANES-1:0]     rx_valid,
    input  wire [NUM_LANES-1:0]     rx_ready

);

    //==================================================
    // 각 lane별 1-lane IPCore 인스턴스
    //  - 인덱스 i에 대해:
    //    * tx_data_lane[i] = tx_data[2*i +: 2]
    //    * rx_data_lane[i] = rx_data[2*i +: 2]
    //==================================================

    genvar i;
    generate
        for (i = 0; i < NUM_LANES; i = i + 1) begin : GEN_LANE
            // lane별 심볼 데이터 slice
            wire [1:0] tx_data_lane;
            wire [1:0] rx_data_lane;

            assign tx_data_lane      = tx_data[2*i +: 2];
            assign rx_data[2*i +: 2] = rx_data_lane;

            ilc3_ipcore_top #(
                .AMP_WIDTH    (AMP_WIDTH),
                .CH_GAIN_NUM  (CH_GAIN_NUM),
                .CH_GAIN_DEN  (CH_GAIN_DEN),
                .CH_OFFSET    (CH_OFFSET),
                .CH_ADD_NOISE (CH_ADD_NOISE),
                .CH_NOISE_LSB (CH_NOISE_LSB)
            ) u_ipcore_lane (
                .clk          (clk),
                .rst_n        (rst_n),

                .tx_sym_in    (tx_data_lane),
                .tx_sym_valid (tx_valid[i]),
                .tx_sym_ready (tx_ready[i]),

                .rx_sym_out   (rx_data_lane),
                .rx_sym_valid (rx_valid[i]),
                .rx_sym_ready (rx_ready[i])
            );
        end
    endgenerate

endmodule