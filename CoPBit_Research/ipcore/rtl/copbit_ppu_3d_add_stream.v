`timescale 1ns/1ps

// CoPBit PPU – 3D-ADD stream core (index, M=8, handshake 포함)
// - NLANES개의 (a + b) mod M 연산을 병렬 처리
// - in_valid/in_ready, out_valid/out_ready 핸드셰이크 지원
// - 내부적으로 1-stage 파이프라인을 사용
module copbit_ppu_3d_add_stream #(
    parameter integer M      = 8,
    parameter integer WIDTH  = 3,
    parameter integer NLANES = 16
)(
    input  wire                    clk,
    input  wire                    rst_n,

    // 입력 스트림
    input  wire                    in_valid,
    output wire                    in_ready,
    input  wire [NLANES*WIDTH-1:0] in_a_idx_flat,
    input  wire [NLANES*WIDTH-1:0] in_b_idx_flat,

    // 출력 스트림
    output reg                     out_valid,
    input  wire                    out_ready,
    output reg  [NLANES*WIDTH-1:0] out_y_idx_flat
);

    // 파이프라인 스테이지 레지스터
    reg  [NLANES*WIDTH-1:0] a_idx_reg;
    reg  [NLANES*WIDTH-1:0] b_idx_reg;
    reg                     stage_valid;

    // 타일 코어 출력
    wire [NLANES*WIDTH-1:0] y_idx_wire;

    // 멀티레인 3D-ADD 타일 코어 재사용
    copbit_ppu_3d_add_tile #(
        .M(M),
        .WIDTH(WIDTH),
        .NLANES(NLANES)
    ) u_tile (
        .a_idx_flat(a_idx_reg),
        .b_idx_flat(b_idx_reg),
        .y_idx_flat(y_idx_wire)
    );

    // 입력 핸드셰이크:
    // - stage_valid=0 이면 언제든 수락 가능
    // - stage_valid=1 이고 out_ready=1이면, 같은 사이클에 소비+새 입력 덮어쓰기 허용
    assign in_ready = (~stage_valid) || (stage_valid && out_ready);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            a_idx_reg      <= {NLANES*WIDTH{1'b0}};
            b_idx_reg      <= {NLANES*WIDTH{1'b0}};
            stage_valid    <= 1'b0;
            out_valid      <= 1'b0;
            out_y_idx_flat <= {NLANES*WIDTH{1'b0}};
        end else begin
            // 입력 수락/스테이지 관리
            if (in_valid && in_ready) begin
                // 새 입력 수락
                a_idx_reg   <= in_a_idx_flat;
                b_idx_reg   <= in_b_idx_flat;
                stage_valid <= 1'b1;
            end else if (stage_valid && out_ready) begin
                // 기존 데이터가 소비되고, 새 입력은 없는 경우
                stage_valid <= 1'b0;
            end
            // 그 외에는 stage_valid 유지

            // 출력은 항상 현재 stage 기준
            out_y_idx_flat <= y_idx_wire;
            out_valid      <= stage_valid;
        end
    end

endmodule