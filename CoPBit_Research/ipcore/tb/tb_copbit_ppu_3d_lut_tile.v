// CoPBit PPU IPCore v0.1
// Core #7 – 3D-LUT tile core truthcheck TB

`timescale 1ps/1ps

module tb_copbit_ppu_3d_lut_tile;

    localparam integer M      = 8;
    localparam integer WIDTH  = 3;
    localparam integer NLANES = 16;

    reg  [NLANES*WIDTH-1:0] in_idx_flat;
    wire [NLANES*WIDTH-1:0] out_idx_flat;

    integer vec;
    integer lane;
    integer err_cnt;

    reg  [WIDTH-1:0] in_idx_arr [0:NLANES-1];
    reg  [WIDTH-1:0] out_idx_arr[0:NLANES-1];

    // DUT
    copbit_ppu_3d_lut_tile #(
        .M(M),
        .WIDTH(WIDTH),
        .NLANES(NLANES)
    ) dut (
        .in_idx_flat (in_idx_flat),
        .out_idx_flat(out_idx_flat)
    );

    // truth LUT (Core #6과 동일한 매핑)
    function [WIDTH-1:0] lut3d_truth;
        input [WIDTH-1:0] x;
        begin
            case (x)
                3'd0: lut3d_truth = 3'd3;
                3'd1: lut3d_truth = 3'd0;
                3'd2: lut3d_truth = 3'd6;
                3'd3: lut3d_truth = 3'd1;
                3'd4: lut3d_truth = 3'd7;
                3'd5: lut3d_truth = 3'd2;
                3'd6: lut3d_truth = 3'd5;
                3'd7: lut3d_truth = 3'd4;
                default: lut3d_truth = {WIDTH{1'b0}};
            endcase
        end
    endfunction

    // packed bus <-> 배열 변환
    task pack_input;
        integer i;
        begin
            for (i = 0; i < NLANES; i = i + 1) begin
                in_idx_flat[i*WIDTH +: WIDTH] = in_idx_arr[i];
            end
        end
    endtask

    task unpack_output;
        integer i;
        begin
            for (i = 0; i < NLANES; i = i + 1) begin
                out_idx_arr[i] = out_idx_flat[i*WIDTH +: WIDTH];
            end
        end
    endtask

    initial begin
        err_cnt     = 0;
        in_idx_flat = {NLANES*WIDTH{1'b0}};

        $display("=== CoPBit PPU 3D-LUT tile truthcheck (M=%0d, NLANES=%0d) ===", M, NLANES);

        // vec = 0..M-1, lane = 0..NLANES-1 패턴
        for (vec = 0; vec < M; vec = vec + 1) begin
            // 입력 패턴 생성
            for (lane = 0; lane < NLANES; lane = lane + 1) begin
                in_idx_arr[lane] = (vec + lane) % M;
            end

            // 패킹 후 조합 논리 settle 대기
            pack_input();
            #1;

            // 출력 언패킹 및 검증
            unpack_output();

            for (lane = 0; lane < NLANES; lane = lane + 1) begin
                if (out_idx_arr[lane] !== lut3d_truth(in_idx_arr[lane])) begin
                    $display("[ERR] vec=%0d lane=%0d  in=%0d  out=%0d  exp=%0d",
                             vec, lane, in_idx_arr[lane], out_idx_arr[lane],
                             lut3d_truth(in_idx_arr[lane]));
                    err_cnt = err_cnt + 1;
                end
            end
        end

        if (err_cnt == 0) begin
            $display("[PASS] op_error_3d_lut_tile = 0 (M=%0d, NLANES=%0d)", M, NLANES);
        end else begin
            $display("[FAIL] op_error_3d_lut_tile = %0d", err_cnt);
        end

        #10;
        $finish;
    end

endmodule