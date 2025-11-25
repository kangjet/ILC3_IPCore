`timescale 1ns/1ps
//======================================================
// ILC3 Simple Channel Model
// - TX amp_out → (GAIN / OFFSET / 간단 노이즈) → RX amp_in
// - 현재 버전: 1클럭 레지스터링 + 선택적 ±1 LSB 노이즈
// - 핸드셰이크:
//    * amp_in_ready  : 항상 1 (백프레셔 없음)
//    * amp_out_ready : 상위에서 1로 묶어서 사용 (tb에서 1'b1)
//======================================================
module ilc3_channel_model #(
    parameter integer AMP_WIDTH  = 4,
    parameter integer GAIN_NUM   = 1,   // 곱셈 분자
    parameter integer GAIN_DEN   = 1,   // 곱셈 분모 (0 금지)
    parameter integer OFFSET     = 0,   // DC 오프셋
    parameter integer ADD_NOISE  = 0,   // 0이면 노이즈 없음, 1이면 ±NOISE_LSB
    parameter integer NOISE_LSB  = 1    // 노이즈 크기 (LSB 단위)
) (
    input  wire                        clk,
    input  wire                        rst_n,

    // 입력 측 (TX 쪽)
    input  wire signed [AMP_WIDTH-1:0] amp_in,
    input  wire                        amp_in_valid,
    output wire                        amp_in_ready,

    // 출력 측 (RX 쪽)
    output reg  signed [AMP_WIDTH-1:0] amp_out,
    output reg                         amp_out_valid,
    input  wire                        amp_out_ready
);

    // 이번 버전에서는 채널 내부에서 백프레셔를 만들지 않고 항상 ready=1
    assign amp_in_ready = 1'b1;

    // 내부 연산용 임시 변수 (넉넉히 16비트 사용)
    reg signed [15:0] tmp;
    integer           noise;

    // 포화 연산용 최대/최소 값
    localparam signed [AMP_WIDTH-1:0] MAX_POS = {1'b0, {(AMP_WIDTH-1){1'b1}}};     // 0...0111...
    localparam signed [AMP_WIDTH-1:0] MIN_NEG = {1'b1, {(AMP_WIDTH-1){1'b0}}};     // 1...0000...

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            amp_out       <= {AMP_WIDTH{1'b0}};
            amp_out_valid <= 1'b0;
        end else begin
            amp_out_valid <= 1'b0;  // 기본값

            if (amp_in_valid && amp_out_ready) begin
                // 1) 기본 스케일링
                tmp = amp_in * GAIN_NUM;
                if (GAIN_DEN != 0 && GAIN_DEN != 1)
                    tmp = tmp / GAIN_DEN;

                // 2) DC 오프셋
                tmp = tmp + OFFSET;

                // 3) 간단 노이즈 (옵션)
                noise = 0;
                if (ADD_NOISE != 0) begin
                    // 매우 간단한 ±NOISE_LSB 노이즈
                    noise = $random;
                    if (noise >= 0)
                        noise = +NOISE_LSB;
                    else
                        noise = -NOISE_LSB;
                    tmp = tmp + noise;
                end

                // 4) AMP_WIDTH 범위로 포화(saturation)
                if (tmp > MAX_POS)
                    amp_out <= MAX_POS;
                else if (tmp < MIN_NEG)
                    amp_out <= MIN_NEG;
                else
                    amp_out <= tmp[AMP_WIDTH-1:0];

                // 5) 출력 valid 펄스
                amp_out_valid <= 1'b1;
            end
        end
    end

endmodule