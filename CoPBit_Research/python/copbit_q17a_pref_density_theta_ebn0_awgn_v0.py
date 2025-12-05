#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CoPBit Q17a – p_ref density vs θ_std, Eb/N0 (AWGN + common phase-noise) v0

목적:
  - 64-lane CoPBit에서 p_ref lane 밀도(N_ref / (N_ref+N_data))에 따라
    공통 위상 노이즈(θ_std_deg)와 Eb/N0 조건에서 BER이 어떻게 변하는지 보는 실험.
  - Q16/Q16c(2-lane, 3-lane, 64-lane)에서 확인한
    "P_ref 1개로도 Kuramoto 락 조건 충족 가능"이라는 특성을
    AWGN-only 환경에서 지도(map) 형태로 정리하기 위한 베이스라인.

구조:
  - M8 (8-PSK, 3 bit/sym)
  - Lane 구조:
      · N_ref lanes : p_ref (고정 8-PSK 심볼, k_ref_const=0)
      · N_data lanes: data (랜덤 3bit/sym, M8)
  - 채널 : AWGN-only (no-ISI), 공통 위상 노이즈(Wiener process)
  - PLL 모드:
      * No PLL      : 위상 추적 없음 (각 data lane 독립 slicer)
      * Data-DD only: 모든 data lane의 결정 에러 평균으로 공통 φ 추적
      * Data+p_ref  : p_ref lane + data lane 에러를 alpha_ref 비율로 섞어서 공통 φ 추적

출력:
  - 각 (N_ref, N_data) 조합에 대해
    · θ_std_deg 리스트 × Eb/N0 리스트에 대한
      BER_noPLL, BER_DDonly, BER_DD+pRef 테이블 출력
  - 옵션:
    --csv_out 로 지정하면 CSV 파일로도 결과 저장
"""

import argparse
import csv
import numpy as np

# ---------------------------------
# 기본 설정
# ---------------------------------
BITS_PER_SYM = 3  # M8 (3 bit / symbol)


# ---------------------------------
# 파라미터 파싱 유틸
# ---------------------------------
def parse_float_list(s: str):
    return [float(x) for x in s.split(",") if x.strip() != ""]


def parse_int_list(s: str):
    return [int(x) for x in s.split(",") if x.strip() != ""]


# ---------------------------------
# 비트 <-> 심볼 인덱스
# ---------------------------------
def bits_to_ints(bits, k: int = BITS_PER_SYM):
    bits = bits.reshape(-1, k)
    vals = np.zeros(bits.shape[0], dtype=int)
    for i in range(k):
        vals = (vals << 1) | bits[:, i]
    return vals


def ints_to_bits(vals, k: int = BITS_PER_SYM):
    vals = np.array(vals, dtype=int).reshape(-1)
    bits = np.zeros((vals.shape[0], k), dtype=int)
    for i in range(k - 1, -1, -1):
        bits[:, i] = vals & 1
        vals >>= 1
    return bits.reshape(-1)


# ---------------------------------
# M8 (8-PSK) 맵핑
# ---------------------------------
def m8_constellation():
    """
    index k=0..7 → 8-PSK on unit circle: exp(j*2πk/8)
    """
    k = np.arange(8)
    return np.exp(1j * 2 * np.pi * k / 8.0)


def map_ints_to_m8(sym_idx):
    const = m8_constellation()
    return const[sym_idx]


def slicer_m8(z):
    """
    복소 샘플 z를 가장 가까운 8-PSK 포인트 index로 양자화
    """
    z = np.asarray(z)
    angles = np.angle(z)
    angles = np.where(angles < 0, angles + 2 * np.pi, angles)
    k_hat = np.round(angles * 8.0 / (2 * np.pi)) % 8
    return k_hat.astype(int)


# ---------------------------------
# AWGN (Eb/N0 기준) – 다차원 지원
# ---------------------------------
def add_awgn(x, ebn0_db, bits_per_sym: int = BITS_PER_SYM):
    """
    x: shape (n_sym,) 또는 (n_lane, n_sym) 복소 시퀀스
    """
    x = np.asarray(x)
    ebn0_lin = 10.0 ** (ebn0_db / 10.0)
    es = np.mean(np.abs(x) ** 2)  # 평균 심볼 에너지
    n0 = es / (bits_per_sym * ebn0_lin)
    sigma2 = n0 / 2.0
    noise = np.sqrt(sigma2) * (
        np.random.randn(*x.shape) + 1j * np.random.randn(*x.shape)
    )
    return x + noise


# ---------------------------------
# 공통 위상 노이즈 (Wiener process)
# ---------------------------------
def generate_common_phase_noise(n_sym, theta_std_deg: float):
    """
    공통 위상 노이즈: Δφ ~ N(0, σ^2), σ[deg]를 rad로 변환 후 누적 (Wiener)
    """
    sigma = theta_std_deg * np.pi / 180.0
    dphi = np.random.randn(n_sym) * sigma
    phi = np.cumsum(dphi)
    return phi  # length n_sym


# ---------------------------------
# 한 번의 실험 (단일 설정) 실행
# ---------------------------------
def run_single_config(
    n_sym: int,
    ebn0_list,
    theta_std_deg: float,
    mu_phase: float,
    alpha_ref: float,
    n_ref: int,
    n_data: int,
    rng: np.random.Generator,
):
    """
    단일 (theta_std_deg, N_ref, N_data)에 대해
    Eb/N0 리스트를 돌면서 BER_noPLL, BER_DDonly, BER_DD+pRef를 계산.
    """

    const = m8_constellation()
    k_ref_const = 0
    s_ref_const = const[k_ref_const]

    # -------------------------
    # Tx 심볼 생성 (data lanes)
    # -------------------------
    n_bits = n_sym * BITS_PER_SYM

    if n_data > 0:
        tx_bits_data = rng.integers(0, 2, size=(n_data, n_bits), dtype=int)
        tx_ints_data = np.stack(
            [bits_to_ints(tx_bits_data[i], k=BITS_PER_SYM) for i in range(n_data)],
            axis=0,
        )  # (n_data, n_sym)
        s_data = map_ints_to_m8(tx_ints_data)  # (n_data, n_sym)
    else:
        tx_bits_data = np.zeros((0, n_bits), dtype=int)
        s_data = np.zeros((0, n_sym), dtype=np.complex128)

    # p_ref lanes: 고정 심볼 시퀀스
    if n_ref > 0:
        s_ref = np.full((n_ref, n_sym), s_ref_const, dtype=np.complex128)  # (n_ref, n_sym)
    else:
        s_ref = np.zeros((0, n_sym), dtype=np.complex128)

    ber_no_pll_list = []
    ber_dd_only_list = []
    ber_pref_list = []

    for ebn0 in ebn0_list:
        # -------------------------
        # AWGN 채널
        # -------------------------
        if n_ref > 0:
            y_ref_noisy = add_awgn(s_ref, ebn0)
        else:
            y_ref_noisy = np.zeros_like(s_ref)

        if n_data > 0:
            y_data_noisy = add_awgn(s_data, ebn0)
        else:
            y_data_noisy = np.zeros_like(s_data)

        # -------------------------
        # 공통 위상 노이즈 (AWGN 이후에 곱해줌 – 선형 시스템과 교환 가능)
        # -------------------------
        phi_noise = generate_common_phase_noise(n_sym, theta_std_deg)  # (n_sym,)
        phasor = np.exp(1j * phi_noise)  # (n_sym,)

        if n_ref > 0:
            y_ref_phase = y_ref_noisy * phasor
        else:
            y_ref_phase = np.zeros_like(y_ref_noisy)

        if n_data > 0:
            y_data_phase = y_data_noisy * phasor
        else:
            y_data_phase = np.zeros_like(y_data_noisy)

        # -------------------------
        # No PLL: 각 data lane에 대해 그냥 slicer
        # -------------------------
        if n_data > 0:
            k_hat_no = slicer_m8(y_data_phase)  # (n_data, n_sym)
            bits_hat_no = np.stack(
                [ints_to_bits(k_hat_no[i], k=BITS_PER_SYM) for i in range(n_data)],
                axis=0,
            )  # (n_data, n_bits)
            ber_no = np.mean(bits_hat_no != tx_bits_data)
        else:
            ber_no = 0.0

        # -------------------------
        # Data-DD only: 모든 data lane 에러 평균으로 φ 추적
        # -------------------------
        phi_hat_dd = 0.0
        bits_hat_dd = np.zeros_like(tx_bits_data, dtype=int)

        if n_data > 0:
            for i in range(n_sym):
                # 공통 φ_hat로 모든 data lane 보정
                z_dd = y_data_phase[:, i] * np.exp(-1j * phi_hat_dd)  # (n_data,)
                k_dec = slicer_m8(z_dd)  # (n_data,)
                s_dec = const[k_dec]     # (n_data,)
                e = np.angle(z_dd * np.conjugate(s_dec))  # (n_data,)
                e_mean = np.mean(e)
                phi_hat_dd += mu_phase * e_mean

                # 비트 복원
                bits_block = np.stack(
                    [ints_to_bits(k_dec[j], k=BITS_PER_SYM) for j in range(n_data)],
                    axis=0,
                )  # (n_data, BITS_PER_SYM)
                bits_hat_dd[:, i * BITS_PER_SYM : (i + 1) * BITS_PER_SYM] = bits_block

            ber_dd = np.mean(bits_hat_dd != tx_bits_data)
        else:
            ber_dd = 0.0

        # -------------------------
        # Data + p_ref: p_ref + data 에러 혼합
        # -------------------------
        phi_hat_pref = 0.0
        bits_hat_pref = np.zeros_like(tx_bits_data, dtype=int)

        if n_data > 0:
            for i in range(n_sym):
                # p_ref 측 에러
                if n_ref > 0:
                    z_ref = y_ref_phase[:, i] * np.exp(-1j * phi_hat_pref)  # (n_ref,)
                    e_ref = np.angle(z_ref * np.conjugate(s_ref_const))     # (n_ref,)
                    e_ref_mean = np.mean(e_ref)
                else:
                    e_ref_mean = 0.0

                # data 측 에러
                z_data = y_data_phase[:, i] * np.exp(-1j * phi_hat_pref)  # (n_data,)
                k_data_hat = slicer_m8(z_data)
                s_data_hat = const[k_data_hat]
                e_data = np.angle(z_data * np.conjugate(s_data_hat))      # (n_data,)
                e_data_mean = np.mean(e_data)

                # p_ref vs data 혼합
                e_total = (1.0 - alpha_ref) * e_ref_mean + alpha_ref * e_data_mean
                phi_hat_pref += mu_phase * e_total

                bits_block_pref = np.stack(
                    [ints_to_bits(k_data_hat[j], k=BITS_PER_SYM) for j in range(n_data)],
                    axis=0,
                )
                bits_hat_pref[:, i * BITS_PER_SYM : (i + 1) * BITS_PER_SYM] = bits_block_pref

            ber_pref = np.mean(bits_hat_pref != tx_bits_data)
        else:
            ber_pref = 0.0

        ber_no_pll_list.append(ber_no)
        ber_dd_only_list.append(ber_dd)
        ber_pref_list.append(ber_pref)

    return ber_no_pll_list, ber_dd_only_list, ber_pref_list


# ---------------------------------
# 메인 Q17a 실행
# ---------------------------------
def run_q17a(args):
    ebn0_list = parse_float_list(args.ebn0_list)
    theta_list = parse_float_list(args.theta_list)

    if args.nref_list is not None and args.ndata_list is not None:
        nref_list = parse_int_list(args.nref_list)
        ndata_list = parse_int_list(args.ndata_list)
        if len(nref_list) != len(ndata_list):
            raise ValueError("nref_list와 ndata_list 길이가 다릅니다.")
        nd_configs = list(zip(nref_list, ndata_list))
    else:
        # 기본: 64-lane 기준 3가지 조합
        nd_configs = [(1, 1), (2, 1), (8, 56)]

    rng = np.random.default_rng(args.seed)

    print("=== CoPBit Q17a – p_ref density vs θ_std, Eb/N0 (AWGN + common phase-noise) v0 ===")
    print(f"[Param] n_sym          = {args.n_sym}")
    print(f"[Param] Eb/N0_list(dB) = {ebn0_list}")
    print(f"[Param] theta_list(deg)= {theta_list}")
    print(f"[Param] mu_phase       = {args.mu_phase}")
    print(f"[Param] alpha_ref      = {args.alpha_ref}  (0→ref-only, 1→data-only)")
    print(f"[Param] bits/symbol    = {BITS_PER_SYM}")
    print(f"[Param] seed           = {args.seed}")
    print("")
    print("[Info ] 채널: no-ISI (h=[1]), 공통 위상 노이즈 + AWGN")
    print("[Info ] PLL:")
    print("        - No PLL      : 각 data lane에 slicer만 적용 (공통 φ 추적 없음)")
    print("        - Data-DD only: 모든 data lane 에러 평균으로 공통 φ 추적")
    print("        - Data+p_ref  : p_ref + data 에러를 alpha_ref 비율로 섞어 공통 φ 추적")
    print("")
    print(f"[Info ] N_ref / N_data 조합 목록: {nd_configs}")
    print("")

    csv_rows = []

    for (n_ref, n_data) in nd_configs:
        print(f"=== Q17a – Config: N_ref = {n_ref}, N_data = {n_data} (총 lanes={n_ref + n_data}) ===")
        print("")

        for theta in theta_list:
            ber_no_list, ber_dd_list, ber_pref_list = run_single_config(
                n_sym=args.n_sym,
                ebn0_list=ebn0_list,
                theta_std_deg=theta,
                mu_phase=args.mu_phase,
                alpha_ref=args.alpha_ref,
                n_ref=n_ref,
                n_data=n_data,
                rng=rng,
            )

            print(f"[theta_std_deg = {theta:.2f} deg] (N_ref={n_ref}, N_data={n_data})")
            print("===============================================================")
            print(" Eb/N0_dB |  BER_noPLL   |  BER_DDonly  |  BER_DD+pRef       ")
            print("---------------------------------------------------------------")
            for eb, b0, b1, b2 in zip(ebn0_list, ber_no_list, ber_dd_list, ber_pref_list):
                print(f"{eb:9.1f} | {b0:12.6f} | {b1:12.6f} | {b2:12.6f}")
                csv_rows.append(
                    {
                        "n_sym": args.n_sym,
                        "n_ref": n_ref,
                        "n_data": n_data,
                        "theta_std_deg": theta,
                        "ebn0_db": eb,
                        "ber_noPLL": b0,
                        "ber_DDonly": b1,
                        "ber_DD_pRef": b2,
                    }
                )
            print("---------------------------------------------------------------")
            print("")

        print("")

    # CSV 저장 옵션
    if args.csv_out:
        fieldnames = [
            "n_sym",
            "n_ref",
            "n_data",
            "theta_std_deg",
            "ebn0_db",
            "ber_noPLL",
            "ber_DDonly",
            "ber_DD_pRef",
        ]
        with open(args.csv_out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in csv_rows:
                writer.writerow(row)
        print(f"[INFO] CSV 결과가 '{args.csv_out}' 파일로 저장되었습니다.")


# ---------------------------------
# main
# ---------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="CoPBit Q17a – p_ref density vs θ_std, Eb/N0 (AWGN + common phase-noise) v0"
    )
    parser.add_argument("--n_sym", type=int, default=200000)
    parser.add_argument("--ebn0_list", type=str, default="12,14,16")
    parser.add_argument("--theta_list", type=str, default="1,3,5")
    parser.add_argument("--mu_phase", type=float, default=0.05)
    parser.add_argument("--alpha_ref", type=float, default=0.3)
    # N_ref / N_data 리스트를 직접 지정하고 싶으면 사용 (예: "1,2,8" / "1,1,56")
    parser.add_argument("--nref_list", type=str, default=None)
    parser.add_argument("--ndata_list", type=str, default=None)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument(
        "--csv_out",
        type=str,
        default="",
        help="CSV 결과를 저장할 파일 경로 (옵션)",
    )
    args = parser.parse_args()

    run_q17a(args)


if __name__ == "__main__":
    main()