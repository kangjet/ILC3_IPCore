#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CoPBit Q10 – M-PSK AWGN BER vs Eb/N0 (bit-fair) v0.1

목적:
 - Q9에서 Es/N0 기준으로 본 M-PSK BER을
   Eb/N0 기준(비트 공정 비교)으로 다시 정리.
 - M = 2(BPSK/NRZ), 4(QPSK), 8, 16(CoPBit4와 동일 각도 간격)에 대해
   AWGN-only 환경에서 BER vs Eb/N0(dB) 비교.
 - PSK 심볼은 unit circle(Es=1) 기준.
   Eb = Es / k  (k = log2(M)) 이므로
   Es/N0(dB) = Eb/N0(dB) + 10*log10(k) 로 변환 후 시뮬.

사용 예시:

  # 기본 (n_sym=100k, Eb/N0=4~16 dB, M={2,4,8,16})
  python copbit_q10_mpsk_awgn_ebn0_compare_v0.py

  # Eb/N0 / M_list / seed 변경
  python copbit_q10_mpsk_awgn_ebn0_compare_v0.py \
    --n_sym 200000 \
    --ebn0_list 0,2,4,6,8,10,12 \
    --M_list 2,4,8,16 \
    --seed 2
"""

import argparse
import numpy as np


def parse_list_floats(s: str):
    return [float(x) for x in s.split(",") if x.strip()]


def parse_list_ints(s: str):
    return [int(x) for x in s.split(",") if x.strip()]


def bits_per_symbol(M: int) -> int:
    k = int(np.log2(M))
    if 2 ** k != M:
        raise ValueError(f"M={M} is not a power of 2 (only 2,4,8,16,... supported)")
    return k


def bits_to_indices(bits: np.ndarray, M: int) -> np.ndarray:
    """
    bits : shape (N, k), k = log2(M)
    단순 binary → integer (Gray 아님)
    """
    N, k = bits.shape
    if bits_per_symbol(M) != k:
        raise ValueError(f"bits.shape[1]={k} but log2(M)={bits_per_symbol(M)}")

    weights = (2 ** np.arange(k - 1, -1, -1, dtype=np.int64))[None, :]
    idx = (bits * weights).sum(axis=1).astype(np.int64)
    return idx


def indices_to_bits(idx: np.ndarray, M: int) -> np.ndarray:
    """
    idx : shape (N,)
    → bits: shape (N, k)
    단순 integer → binary (MSB first)
    """
    k = bits_per_symbol(M)
    N = idx.shape[0]
    bits_hat = np.zeros((N, k), dtype=np.int64)
    for j in range(k):
        shift = k - 1 - j
        bits_hat[:, j] = (idx >> shift) & 0x1
    return bits_hat


def mpsk_modulate(bits: np.ndarray, M: int) -> np.ndarray:
    """
    M-PSK 변조 (unit circle, Es = 1)
    - 심볼 인덱스 k = 0..M-1
    - 각도 θ_k = 2π k / M
    - 심볼 s_k = exp(j θ_k)
    CoPBit 16-PSK(Q1)와 동일한 각도 간격(22.5°) 구조.
    """
    idx = bits_to_indices(bits, M)
    theta = 2.0 * np.pi * idx / M
    s = np.exp(1j * theta)
    return s  # 평균 Es ≈ 1


def add_awgn_complex_esn0(x: np.ndarray, esn0_db: float, rng: np.random.Generator) -> np.ndarray:
    """
    Es = E[|x|^2] ~= 1 기준 AWGN 채널
    - EsN0_dB = 10 log10(Es / N0)
    - 각 실/허수 성분 분산: σ^2 = N0 / 2 = 1 / (2 * EsN0)
    """
    esn0 = 10.0 ** (esn0_db / 10.0)
    sigma = np.sqrt(1.0 / (2.0 * esn0))
    w = sigma * (rng.standard_normal(size=x.shape) + 1j * rng.standard_normal(size=x.shape))
    return x + w


def ber_between_bits(b_true: np.ndarray, b_hat: np.ndarray) -> float:
    if b_true.shape != b_hat.shape:
        raise ValueError(f"Shape mismatch: {b_true.shape} vs {b_hat.shape}")
    n_err = np.count_nonzero(b_true != b_hat)
    n_bits = b_true.size
    return float(n_err) / float(n_bits)


def main():
    parser = argparse.ArgumentParser(
        description="CoPBit Q10 – M-PSK AWGN BER vs Eb/N0 (bit-fair) v0.1"
    )
    parser.add_argument(
        "--n_sym",
        type=int,
        default=100000,
        help="Number of symbols per scheme (default: 100000)",
    )
    parser.add_argument(
        "--ebn0_list",
        type=str,
        default="4,6,8,10,12,14,16",
        help="Comma-separated Eb/N0(dB) list (default: '4,6,8,10,12,14,16')",
    )
    parser.add_argument(
        "--M_list",
        type=str,
        default="2,4,8,16",
        help="Comma-separated M list for M-PSK (default: '2,4,8,16')",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1,
        help="Random seed (default: 1)",
    )

    args = parser.parse_args()

    n_sym = args.n_sym
    ebn0_list = parse_list_floats(args.ebn0_list)
    M_list = parse_list_ints(args.M_list)
    seed = args.seed

    rng = np.random.default_rng(seed)

    print("=== CoPBit Q10 – M-PSK AWGN BER vs Eb/N0 (bit-fair) v0.1 ===")
    print(f"[Param] n_sym         = {n_sym}")
    print(f"[Param] Eb/N0_list(dB)= {ebn0_list}")
    print(f"[Param] M_list        = {M_list}")
    print(f"[Param] seed          = {seed}")
    print("------------------------------------------------------------")

    n_eb = len(ebn0_list)
    n_M = len(M_list)
    ber_table = np.zeros((n_M, n_eb), dtype=float)

    # 각 M에 대해 전체 비트를 한 번 생성해두고, Eb/N0만 바꿔가며 재사용
    for i, M in enumerate(M_list):
        k = bits_per_symbol(M)  # bits/symbol
        bits = rng.integers(0, 2, size=(n_sym, k), dtype=np.int64)
        x = mpsk_modulate(bits, M)  # Es ≈ 1

        for j, ebn0_db in enumerate(ebn0_list):
            # Es/N0(dB) = Eb/N0(dB) + 10*log10(k)
            esn0_db = ebn0_db + 10.0 * np.log10(k)
            y = add_awgn_complex_esn0(x, esn0_db, rng)

            # 디코더: 최근접 위상 포인트
            delta = 2.0 * np.pi / M
            ang = np.angle(y)
            ang = np.mod(ang, 2.0 * np.pi)
            k_hat = np.floor((ang + delta / 2.0) / delta).astype(np.int64) % M

            bits_hat = indices_to_bits(k_hat, M)
            ber = ber_between_bits(bits, bits_hat)
            ber_table[i, j] = ber

    # 결과 출력: Eb/N0 기준 행
    header_cols = ["EbN0_dB"] + [f"BER_M{M}" for M in M_list]
    col_widths = [8] + [12] * len(M_list)

    def fmt_row(values, widths):
        return " ".join(f"{v:>{w}}" for v, w in zip(values, widths))

    print(fmt_row(header_cols, col_widths))
    print("-" * (sum(col_widths) + len(col_widths) - 1))

    for j, ebn0_db in enumerate(ebn0_list):
        row_vals = [f"{ebn0_db:4.1f}"] + [f"{ber_table[i, j]:.3e}" for i in range(n_M)]
        print(fmt_row(row_vals, col_widths))

    print("-" * (sum(col_widths) + len(col_widths) - 1))
    print("※ 주석")
    print(" - PSK 심볼은 unit circle(Es=1) 기준이며, Eb = Es / k (k=log2(M))로 가정.")
    print(" - 따라서 Es/N0(dB) = Eb/N0(dB) + 10*log10(k) 변환 후 AWGN 적용.")
    print(" - 이 스크립트는 서로 다른 M에 대해 '비트당 에너지(Eb)'를 맞춘 공정 비교용 베이스라인.")
    print(" - M=16은 CoPBit 4bit와 동일한 16포인트 등각 간격 위상 구조(단, 비트 라벨은 단순 binary).")
    print(" - PAM4 비교는 Q6 (PAM4 vs CoPBit4 AWGN) 스크립트와 함께 해석하면 된다.")


if __name__ == "__main__":
    main()