#!/usr/bin/env python3
"""
CoPBit Q24a – 1024-lane PPU 3D phase-add primitive (AWGN + common phase noise)

목표
-----
- 1024-lane CoPBit PPU 타일에서 가장 기본적인 3D 위상 연산 primitive를 정의하고,
  AWGN + 공통 위상 노이즈(theta_std) 환경에서의 연산 에러율(Operation Error Rate)을 측정한다.

연산 primitive (phase-add)
--------------------------
- 입력 심볼 인덱스: a_idx, b_idx ∈ {0..7}  (M8, 3bit/sym)
- 이상적인 연산:
    z_idx_ideal = (a_idx + b_idx) mod 8
- 실제 PPU 연산 모델:
    1) a_idx, b_idx → M8 컨스텔레이션 매핑 (복소수)
    2) AWGN 채널 + 공통 위상 노이즈 통과
    3) y_z = y_a * y_b  (phase add)
    4) M8 slicer로 z_idx_hw 판정
    5) OpError = P[z_idx_hw != z_idx_ideal]

출력
----
- 각 theta_std_deg, Eb/N0 조합에 대해 Operation Error Rate를 출력
- 또한 CSV 파일 `Q24a_ppu_3d_add_theta_ebn0_map.csv`로 저장
"""

import argparse
import numpy as np
from math import pi


# -----------------------------------------------------------------------------
# 유틸 함수들
# -----------------------------------------------------------------------------

def parse_list_of_floats(s: str):
    return [float(x.strip()) for x in s.split(',') if x.strip()]


def m8_constellation(idx: np.ndarray) -> np.ndarray:
    """M8 (8-PSK) 컨스텔레이션 매핑.

    idx: 정수 배열, 값 ∈ {0..7}
    return: 동일 shape 의 복소수 배열 (단위 에너지)
    """
    idx = np.asarray(idx, dtype=int)
    phases = 2.0 * pi * idx / 8.0
    return np.exp(1j * phases)


def awgn_mpsk(x: np.ndarray, ebn0_db: float, bits_per_sym: int, rng: np.random.Generator) -> np.ndarray:
    """M-PSK용 AWGN 채널 (단위 에너지 심볼 가정).

    - x: 입력 심볼 (복소수), 평균 에너지 ~= 1
    - ebn0_db: Eb/N0 [dB]
    - bits_per_sym: 심볼당 비트 수 (M8 → 3)
    """
    ebn0_lin = 10.0 ** (ebn0_db / 10.0)
    esn0_lin = ebn0_lin * bits_per_sym
    # 복소 AWGN: 각 성분 분산 = N0/2 = 1 / (2 * Es/N0)
    noise_var = 1.0 / (2.0 * esn0_lin)
    noise = np.sqrt(noise_var) * (rng.normal(size=x.shape) + 1j * rng.normal(size=x.shape))
    return x + noise


def apply_common_phase_noise(x: np.ndarray, theta_std_deg: float, rng: np.random.Generator) -> np.ndarray:
    """공통 위상 노이즈 적용.

    - x: (n_sym, n_lanes) 또는 동일 shape 의 복소 배열
    - theta_std_deg: 위상 노이즈 표준편차 [deg]
    - 모든 lane에 대해 심볼 시간마다 동일한 θ[n]을 곱해줌 (타일 공통 위상 잡음 모델)
    """
    if theta_std_deg == 0.0:
        return x

    theta_std_rad = theta_std_deg * pi / 180.0
    # 심볼 시간별 공통 위상 노이즈 (shape: (n_sym, 1))
    if x.ndim == 1:
        n_sym = x.shape[0]
        theta = rng.normal(loc=0.0, scale=theta_std_rad, size=(n_sym,))
        phase = np.exp(1j * theta)
        return x * phase
    else:
        n_sym = x.shape[0]
        theta = rng.normal(loc=0.0, scale=theta_std_rad, size=(n_sym, 1))
        phase = np.exp(1j * theta)
        return x * phase


def slicer_m8(y: np.ndarray) -> np.ndarray:
    """8-PSK slicer: arg(y)를 8 영역으로 나누어 인덱스로 매핑."""
    # angle ∈ (-pi, pi]
    ang = np.angle(y)
    # [0, 2pi) 로 변환 후 8분할
    ang = np.mod(ang, 2.0 * pi)
    idx = np.floor(8.0 * ang / (2.0 * pi)).astype(int)
    # 안전을 위해 mod 8
    return np.mod(idx, 8)


# -----------------------------------------------------------------------------
# 메인 시뮬레이션 루프 (Q24a)
# -----------------------------------------------------------------------------


def run_q24a(n_sym: int,
             ebn0_list,
             theta_std_list,
             n_lanes: int,
             seed: int = 1,
             csv_path: str = "Q24a_ppu_3d_add_theta_ebn0_map.csv"):
    rng = np.random.default_rng(seed)

    print("=== CoPBit Q24a – 1024-lane PPU 3D phase-add (AWGN + common phase noise) v0 ===")
    print(f"[Param] n_sym        = {n_sym}")
    print(f"[Param] Eb/N0_list   = {ebn0_list}")
    print(f"[Param] theta_std(deg)= {theta_std_list}")
    print(f"[Param] n_lanes      = {n_lanes}")
    print(f"[Param] seed         = {seed}\n")

    print("[Info ] PPU 3D primitive: z = a (+) b  (M8 index domain)")
    print("        - a_idx, b_idx ∈ {0..7} (M8, 3bit/sym)")
    print("        - ideal:   z_idx_ideal = (a_idx + b_idx) mod 8")
    print("        - actual:  y_z = y_a * y_b (complex multiply → phase add)")
    print("        - OpError = P[z_idx_hw != z_idx_ideal]\n")

    results = []  # (theta_std_deg, ebn0_db, op_error)

    for theta_std_deg in theta_std_list:
        print(f"=== Q24a (theta_std_deg = {theta_std_deg:.3f}) ===")
        print("==============================================================")
        print(" Eb/N0_dB |  OpError_3D_Add ")
        print("--------------------------------------------------------------")

        for ebn0_db in ebn0_list:
            # 1) 입력 심볼 생성 (a, b)
            a_idx = rng.integers(0, 8, size=(n_sym, n_lanes), dtype=int)
            b_idx = rng.integers(0, 8, size=(n_sym, n_lanes), dtype=int)
            z_idx_ideal = (a_idx + b_idx) % 8

            # 2) M8 컨스텔레이션 매핑
            s_a = m8_constellation(a_idx)
            s_b = m8_constellation(b_idx)

            # 3) AWGN 채널 통과
            y_a = awgn_mpsk(s_a, ebn0_db, bits_per_sym=3, rng=rng)
            y_b = awgn_mpsk(s_b, ebn0_db, bits_per_sym=3, rng=rng)

            # 4) 공통 위상 노이즈 적용
            y_a = apply_common_phase_noise(y_a, theta_std_deg, rng)
            y_b = apply_common_phase_noise(y_b, theta_std_deg, rng)

            # 5) PPU 3D phase-add 연산 (복소수 곱셈)
            y_z = y_a * y_b

            # 6) slicer + OpError 계산
            z_idx_hw = slicer_m8(y_z)
            n_err = np.count_nonzero(z_idx_hw != z_idx_ideal)
            total = z_idx_ideal.size
            op_error = n_err / float(total)

            results.append((theta_std_deg, ebn0_db, op_error))
            print(f"{ebn0_db:10.1f} |   {op_error: .9f}")

        print("--------------------------------------------------------------\n")

    # CSV 저장
    if csv_path:
        import csv
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["theta_std_deg", "ebn0_db", "op_error_3d_add"])
            for theta_std_deg, ebn0_db, op_error in results:
                writer.writerow([theta_std_deg, ebn0_db, op_error])
        print(f"[Info ] Saved operation error map to '{csv_path}'")


# -----------------------------------------------------------------------------
# 엔트리 포인트
# -----------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="CoPBit Q24a – 1024-lane PPU 3D phase-add primitive (AWGN + common phase noise)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--n_sym", type=int, default=50000,
                        help="number of symbols per lane")
    parser.add_argument("--ebn0_list", type=str, default="12,14,16",
                        help="comma-separated Eb/N0 list in dB (e.g. '12,14,16')")
    parser.add_argument("--theta_std_list", type=str, default="0.0,1.0,2.0,3.0,5.0",
                        help="comma-separated theta_std list in degrees (e.g. '0.0,1.0,2.0')")
    parser.add_argument("--n_lanes", type=int, default=1024,
                        help="number of parallel lanes (PPU tile size)")
    parser.add_argument("--seed", type=int, default=1,
                        help="random seed")
    parser.add_argument("--csv_out", type=str, default="Q24a_ppu_3d_add_theta_ebn0_map.csv",
                        help="CSV output path for operation error map")

    args = parser.parse_args()

    ebn0_list = parse_list_of_floats(args.ebn0_list)
    theta_std_list = parse_list_of_floats(args.theta_std_list)

    run_q24a(
        n_sym=args.n_sym,
        ebn0_list=ebn0_list,
        theta_std_list=theta_std_list,
        n_lanes=args.n_lanes,
        seed=args.seed,
        csv_path=args.csv_out,
    )


if __name__ == "__main__":
    main()
