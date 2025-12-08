// CoPBit PPU IPCore v0.1
// Core #8 – 3D-LUT stream core (M=8, NLANES=16, handshake)

`timescale 1ps/1ps

module copbit_ppu_3d_lut_stream #(
    parameter integer M      = 8,
    parameter integer WIDTH  = 3,
    parameter integer NLANES = 16
)(
    input  wire                     clk,
    input  wire                     rst_n,

    // 입력 스트림
    input  wire                     in_valid,
    output wire                     in_ready,
    input  wire [NLANES*WIDTH-1:0]  in_idx_flat,

    // 출력 스트림
    output wire                     out_valid,
    input  wire                     out_ready,
    output wire [NLANES*WIDTH-1:0]  out_idx_flat
);

    // 1-stage 파이프라인 레지스터
    reg [NLANES*WIDTH-1:0]  idx_reg;
    reg                     stage_valid;

    wire [NLANES*WIDTH-1:0] idx_lut_wire;

    // 입력 수락 조건:
    // - stage_valid == 0 이면 항상 수락 가능
    // - stage_valid == 1 이면서 같은 클럭에 out_ready == 1이면 새 입력으로 교체 가능
    assign in_ready = (!stage_valid) || (stage_valid && out_ready);

    // 타일 LUT 코어 재사용
    copbit_ppu_3d_lut_tile #(
        .M(M),
        .WIDTH(WIDTH),
        .NLANES(NLANES)
    ) u_lut_tile (
        .in_idx_flat (idx_reg),
        .out_idx_flat(idx_lut_wire)
    );

    assign out_valid    = stage_valid;
    assign out_idx_flat = idx_lut_wire;

    // 파이프라인/valid 레지스터
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            idx_reg     <= {NLANES*WIDTH{1'b0}};
            stage_valid <= 1'b0;
        end else begin
            // 입력 수락
            if (in_valid && in_ready) begin
                idx_reg     <= in_idx_flat;
                stage_valid <= 1'b1;
            end
            // 출력이 소비되고, 동시에 새 입력이 들어오지 않을 때 stage_valid clear
            else if (out_valid && out_ready && !in_valid) begin
                stage_valid <= 1'b0;
            end
        end
    end

endmodule