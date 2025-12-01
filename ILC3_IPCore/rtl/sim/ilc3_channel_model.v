`timescale 1ns/1ps
//======================================================
// ilc3_channel_model.v
//  - ILC3 Simple Channel Model (IPCore용 정리 버전)
//  - TX amp_out → (GAIN / OFFSET / optional noise) → RX amp_in
//  - 현재 버전 특징:
//      * 1클럭 레지스터 파이프라인
//      * 선택적 채널 노이즈 (ADD_NOISE / NOISE_LSB로 제어)
//      * ADD_NOISE 값에 따라 4가지 프리셋:
//          - 0 : clean (노이즈 없음, 기능 검증용)
//          - 1 : lvl1 (스트레스 모드, 강한 노이즈)
//          - 2 : lvl2 (lvl1보다 더 강한 스트레스)
//          - 3 : lvl_real (실제 설계용 약한 노이즈 후보, 희박한 ±1 LSB kick)
//  - 핸드셰이크:
//      * amp_in_ready  : 항상 1 (백프레셔 없음)
//      * amp_out_ready : tb에서 1'b1로 묶어 사용 권장
//  - 실제 제품용 링크 버짓과 SNR↔BER 스펙은 Python(Q18/Q19/Q20) 결과를 사용하고,
//    본 채널 모델은 RTL/IPCore 레벨에서의 기능/신뢰성/스트레스 검증용으로 사용.
//======================================================
module ilc3_channel_model #(
    parameter integer AMP_WIDTH  = 4,
    parameter integer GAIN_NUM   = 1,   // 곱셈 분자
    parameter integer GAIN_DEN   = 1,   // 곱셈 분모 (0 금지)
    parameter integer OFFSET     = 0,   // DC 오프셋
    parameter integer ADD_NOISE  = 0,   // 0=clean, 1/2/3=noise presets
    parameter integer NOISE_LSB  = 1    // 노이즈 크기 (LSB 단위)
)(
    input  wire                         clk,
    input  wire                         rst_n,

    // 입력 측 (TX 쪽)
    input  wire signed [AMP_WIDTH-1:0]  amp_in,
    input  wire                         amp_in_valid,
    output wire                         amp_in_ready,

    // 출력 측 (RX 쪽)
    output reg  signed [AMP_WIDTH-1:0]  amp_out,
    output reg                          amp_out_valid,
    input  wire                         amp_out_ready
);

    //--------------------------------------------------
    // 채널은 내부에서 backpressure를 만들지 않음
    //--------------------------------------------------
    assign amp_in_ready = 1'b1;  // 항상 ready

    //--------------------------------------------------
    // 내부 연산용 확장 비트폭 + 디버그용 레지스터
    //--------------------------------------------------
    localparam integer W_EXT = AMP_WIDTH + 4;  // 여유 비트

    reg  signed [W_EXT-1:0] dbg_base_val;
    reg  signed [W_EXT-1:0] dbg_tmp_val;
    reg  signed [AMP_WIDTH-1:0] dbg_noise_val;

    // 포화(saturation) 한계값 (signed AMP_WIDTH 기준)
    localparam signed [W_EXT-1:0] MAX_POS = ( (1 <<< (AMP_WIDTH-1)) - 1 );
    localparam signed [W_EXT-1:0] MIN_NEG = - (1 <<< (AMP_WIDTH-1));

    //--------------------------------------------------
    // 메인 파이프라인: gain / offset / noise / saturate
    //  - 한 클럭 내에서 "현재 심볼"에 대한 계산을
    //    지역 변수로 처리한 뒤, 결과만 레지스터에 저장.
    //--------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            amp_out       <= {AMP_WIDTH{1'b0}};
            amp_out_valid <= 1'b0;
            dbg_base_val  <= '0;
            dbg_tmp_val   <= '0;
            dbg_noise_val <= {AMP_WIDTH{1'b0}};
        end else begin
            // 기본값: valid는 0으로 클리어
            amp_out_valid <= 1'b0;

            if (amp_in_valid && amp_out_ready) begin
                // ---- 지역 변수 (현재 심볼에만 해당) ----
                reg signed [W_EXT-1:0] base_val;
                reg signed [W_EXT-1:0] tmp_val;
                reg signed [AMP_WIDTH-1:0] noise_val;
                integer r;

                // 1) gain / offset 적용 (확장 비트폭에서 계산)
                base_val = ((amp_in * GAIN_NUM) / GAIN_DEN) + OFFSET;

                // 2) 기본 노이즈 = 0
                noise_val = {AMP_WIDTH{1'b0}};

                // 3) 노이즈 프리셋에 따른 랜덤 노이즈 생성
                if (ADD_NOISE != 0) begin
                    r = $urandom;

                    case (ADD_NOISE)
                        1: begin
                            // lvl1: 스트레스 모드 (강한 노이즈)
                            //  - 매 심볼마다 ±NOISE_LSB를 항상 더함
                            if (r[0])
                                noise_val =  $signed(NOISE_LSB);
                            else
                                noise_val = -$signed(NOISE_LSB);
                        end
                        2: begin
                            // lvl2: lvl1보다 더 강한 스트레스
                            //  - 매 심볼마다 ±2*NOISE_LSB를 항상 더함
                            if (r[0])
                                noise_val =  $signed(NOISE_LSB <<< 1);
                            else
                                noise_val = -$signed(NOISE_LSB <<< 1);
                        end
                        3: begin
                            // lvl_real: 실제 설계용 약한 노이즈 후보
                            //  - 대부분 0, 낮은 확률(예: 1/16)로 ±NOISE_LSB kick
                            if (r[5:0] == 6'd0) begin
                                if (r[6])
                                    noise_val =  $signed(NOISE_LSB);
                                else
                                    noise_val = -$signed(NOISE_LSB);
                            end
                            // else: noise_val = 0 유지
                        end
                        default: begin
                            // 그 외 값은 안전하게 no-noise
                            noise_val = {AMP_WIDTH{1'b0}};
                        end
                    endcase
                end

                // 4) 노이즈를 확장 비트폭으로 더하기
                tmp_val = base_val + {{(W_EXT-AMP_WIDTH){noise_val[AMP_WIDTH-1]}}, noise_val};

                // 5) 포화(saturation)를 거쳐 AMP_WIDTH로 잘라내기
                if (tmp_val > MAX_POS)
                    amp_out <= MAX_POS[AMP_WIDTH-1:0];
                else if (tmp_val < MIN_NEG)
                    amp_out <= MIN_NEG[AMP_WIDTH-1:0];
                else
                    amp_out <= tmp_val[AMP_WIDTH-1:0];

                // 6) 출력 valid 펄스
                amp_out_valid <= 1'b1;

                // 디버그용 레지스터에 현재 값 저장 (파형 보기용)
                dbg_base_val  <= base_val;
                dbg_tmp_val   <= tmp_val;
                dbg_noise_val <= noise_val;
            end
        end
    end

endmodule