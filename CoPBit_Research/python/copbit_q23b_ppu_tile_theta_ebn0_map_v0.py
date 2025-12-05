#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CoPBit Q23b – 1024-lane PPU 타일 (AWGN) θ_std–Eb/N0 맵 생성 v0

목적:
 - Q23a와 동일한 1024-lane PPU 타일 + AWGN + 공통 위상 노이즈 환경에서
 - PhaseLock_std 유무와 상관없이, 타일이 언제부터 깨지기 시작하는지
   (θ_std, Eb/N0에 따른 BER_noPLL 맵) 를 CSV로 정리.

주의:
 - 여기서는 mid-ISI가 없는 AWGN-only + 공통 θ_noise 환경만 다룸.
 - PhaseLock_std는 Q23a에서 이미 "θ_std ≤ 2° 영역은 문제 없음"을 확인했으므로,
   Q23b는 주로 "BER_noPLL 기준으로 타일이 깨지는 경계"를 보는 용도.
"""

import argparse
import csv
import os
import numpy as np


def parse_list_f(s: str):
    return [float(x.strip()) for x in s.split(",") if x.strip() != ""]


def m8_constellation(idx: np.ndarray) -> np.ndarray:
    """
    8-PSK 심볼 맵핑: index 0..7 -> unit circle 위의 8점
    """
    phase = 2.0 * np.pi * idx / 8.0
    return np.exp(1j * phase)


def awgn_mpsk(y_tx: np.ndarray, ebn0_db: float, bits_per_sym: int, rng: np.random.Generator):
    """
    M-PSK 용 AWGN 채널.
    입력:
      y_tx        : (n_sym, n_lanes) complex, |s|=1
      ebn0_db     : Eb/N0 [dB]
      bits_per_sym: log2(M)
    출력:
      y_rx = y_tx + n, n ~ CN(0, sigma^2)
    """
    ebn0_lin = 10.0 ** (ebn0_db / 10.0)
    # Es = 1 (unit power), Eb = Es / bits_per_sym
    # SNR_symbol = Es / N0 = ebn0_lin * bits_per_sym
    snr_sym_lin = ebn0_lin * bits_per_sym
    # complex AWGN: sigma^2 = Es / (2 * SNR_symbol)
    noise_var = 1.0 / (2.0 * snr_sym_lin)
    sigma = np.sqrt(noise_var)
    noise = sigma * (rng.standard_normal(size=y_tx.shape) +
                     1j * rng.standard_normal(size=y_tx.shape))
    return y_tx + noise


def apply_common_phase_noise(y: np.ndarray, theta_std_deg: float, rng: np.random.Generator):
    """
    공통 위상 노이즈: 각 심볼마다 동일한 φ_noise가 모든 lane에 적용.
    y: (n_sym, n_lanes)
    """
    if theta_std_deg <= 0.0:
        return y
    theta_std_rad = np.deg2rad(theta_std_deg)
    n_sym = y.shape[0]
    # (n_sym, 1) -> broadcast to all lanes
    phi_noise = rng.normal(loc=0.0, scale=theta_std_rad, size=(n_sym, 1))
    phase_rot = np.exp(1j * phi_noise)
    return y * phase_rot


def slicer_m8(y: np.ndarray) -> np.ndarray:
    """
    8-PSK slicer: y -> index 0..7
    """
    phase = np.angle(y)
    step = 2.0 * np.pi / 8.0
    idx = np.round(phase / step).astype(int) % 8
    return idx


def simulate_ppu_tile_noPLL(
    n_sym: int,
    n_lanes: int,
    ebn0_db: float,
    theta_std_deg: float,
    seed: int = 1,
) -> float:
    """
    1024-lane PPU 타일 + AWGN + 공통 θ_noise 환경에서
    PhaseLock 없이(noPLL) 단순 8-PSK slicer만 사용했을 때의 BER 측정.
    """
    rng = np.random.default_rng(seed + int(ebn0_db * 10) + int(theta_std_deg * 100))

    bits_per_sym = 3  # M8 (8-PSK)

    # 1) 심볼 생성: lane0은 p_ref (index 0 고정), 나머지는 0..7 랜덤
    # shape = (n_sym, n_lanes)
    tx_idx = rng.integers(low=0, high=8, size=(n_sym, n_lanes), dtype=int)
    tx_idx[:, 0] = 0  # p_ref lane

    # 2) M8 맵핑
    tx_sym = m8_constellation(tx_idx)

    # 3) AWGN 채널
    y = awgn_mpsk(tx_sym, ebn0_db=ebn0_db, bits_per_sym=bits_per_sym, rng=rng)

    # 4) 공통 위상 노이즈 적용
    y = apply_common_phase_noise(y, theta_std_deg=theta_std_deg, rng=rng)

    # 5) noPLL: 바로 slicer
    rx_idx = slicer_m8(y)

    # 6) BER 계산 (심볼 기준 에러율)
    n_err = np.count_nonzero(rx_idx != tx_idx)
    ber = n_err / tx_idx.size

    return float(ber)


def main():
    parser = argparse.ArgumentParser(
        description="CoPBit Q23b – 1024-lane PPU 타일 (AWGN) θ_std–Eb/N0 맵 생성 v0"
    )
    parser.add_argument(
        "--n_sym", type=int, default=20000,
        help="심볼 수 (기본: 20000)"
    )
    parser.add_argument(
        "--n_lanes", type=int, default=1024,
        help="PPU 타일 lane 수 (기본: 1024)"
    )
    parser.add_argument(
        "--ebn0_list", type=str, default="8,10,12,14,16",
        help='Eb/N0 리스트 (콤마 구분, 예: "8,10,12,14,16")'
    )
    parser.add_argument(
        "--theta_std_list", type=str, default="0.0,1.0,2.0,3.0,5.0,7.0,10.0",
        help='θ_std(deg) 리스트 (콤마 구분, 예: "0.0,1.0,2.0,3.0,5.0,7.0,10.0")'
    )
    parser.add_argument(
        "--seed", type=int, default=1,
        help="난수 시드 (기본: 1)"
    )
    parser.add_argument(
        "--csv_out", type=str, default=None,
        help="결과 CSV 경로 (기본: 이 스크립트와 같은 폴더의 Q23b_ppu_theta_ebn0_map.csv)"
    )

    args = parser.parse_args()

    ebn0_list = parse_list_f(args.ebn0_list)
    theta_list = parse_list_f(args.theta_std_list)

    if args.csv_out is None:
        # 스크립트 폴더 기준으로 저장
        base_dir = os.path.dirname(os.path.abspath(__file__))
        csv_out = os.path.join(base_dir, "Q23b_ppu_theta_ebn0_map.csv")
    else:
        csv_out = args.csv_out

    print("=== CoPBit Q23b – 1024-lane PPU 타일 (AWGN) θ_std–Eb/N0 맵 v0 ===")
    print(f"[Param] n_sym        = {args.n_sym}")
    print(f"[Param] n_lanes      = {args.n_lanes}")
    print(f"[Param] Eb/N0_list   = {ebn0_list}")
    print(f"[Param] theta_std(deg)= {theta_list}")
    print(f"[Param] seed         = {args.seed}")
    print()
    print("결과: BER_noPLL 기준 (PhaseLock_std 유무와 상관없이 타일 자체의 한계 구간 파악용)")
    print()

    rows = []
    header = ["theta_std_deg", "ebn0_db", "ber_noPLL"]

    print("==============================================================")
    print(" theta_std | Eb/N0_dB |  BER_noPLL")
    print("--------------------------------------------------------------")

    for theta in theta_list:
        for ebn0 in ebn0_list:
            ber = simulate_ppu_tile_noPLL(
                n_sym=args.n_sym,
                n_lanes=args.n_lanes,
                ebn0_db=ebn0,
                theta_std_deg=theta,
                seed=args.seed,
            )
            rows.append({
                "theta_std_deg": theta,
                "ebn0_db": ebn0,
                "ber_noPLL": ber,
            })
            print(f"{theta:9.3f} | {ebn0:7.1f} | {ber:10.6f}")
        print("--------------------------------------------------------------")

    # CSV 저장
    os.makedirs(os.path.dirname(csv_out), exist_ok=True)
    with open(csv_out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print()
    print(f"[Info ] CSV saved to: {csv_out}")


if __name__ == "__main__":
    main()