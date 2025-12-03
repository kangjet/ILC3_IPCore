#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CoPBit Q9 – M-PSK AWGN BER Family v0.1

목적:
 - M = 2(BPSK/NRZ), 4(QPSK), 8, 16(CoPBit4와 동일한 각도 간격) 에 대해
   AWGN-only 환경에서 BER vs SNR(dB) 비교.
 - Es = 1 (unit circle) 기준, SNR 인자는 Es/N0 로 해석.

사용 예시:

  # 기본 (n_sym=100k, SNR=10~20 dB, M={2,4,8,16})
  python copbit_q9_mpsk_awgn_compare_v0.py

  # 심볼 수/스킴/스니퍼 변경 예시
  python copbit_q9_mpsk_awgn_compare_v0.py \
    --n_sym 200000 \
    --snr_list 8,10,12,14,16,18,20 \
    --M_list 2,4,8,16 \
    --seed 1
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

    # weight: [2^(k-1), ..., 2^0]
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
    M-PSK 변조 (unit circle)
    - 심볼 인덱스 k = 0..M-1
    - 각도 θ_k = 2π k / M
    - 심볼 s_k = exp(j θ_k)
    CoPBit 16-PSK(Q1)와 동일한 각도 간격(22.5°) 구조.
    """
    idx = bits_to_indices(bits, M)
    theta = 2.0 * np.pi * idx / M
    s = np.exp(1j * theta)
    return s


def mpsk_demodulate(y: np.ndarray, M: int) -> np.ndarray:
    """
    최근접 위상 포인트 하드 디코딩:
      - angle -> [0, 2π) 로 정규화
      - 각도 간격 Δ = 2π / M
      - k_hat = round(angle / Δ) mod M
    """
    delta = 2.0 * np.pi / M
    ang = np.angle(y)
    # [0, 2π) 범위로
    ang = np.mod(ang, 2.0 * np.pi)
    k_hat = np.floor((ang + delta / 2.0) / delta).astype(np.int64) % M
    return k_hat


def add_awgn_complex(x: np.ndarray, snr_db: float, rng: np.random.Generator) -> np.ndarray:
    """
    Es = E[|x|^2] ~= 1 기준 AWGN 채널
    - SNR_dB = 10 log10(Es / N0)
    - 각 실/허수 성분 분산: σ^2 = N0 / 2 = 1 / (2 * EsN0)
    """
    esn0 = 10.0 ** (snr_db / 10.0)
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
        description="CoPBit Q9 – M-PSK AWGN BER Family v0.1"
    )
    parser.add_argument(
        "--n_sym",
        type=int,
        default=100000,
        help="Number of symbols per scheme (default: 100000)",
    )
    parser.add_argument(
        "--snr_list",
        type=str,
        default="10,12,14,16,18,20",
        help="Comma-separated SNR(dB) list for Es/N0 (default: '10,12,14,16,18,20')",
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
    snr_list = parse_list_floats(args.snr_list)
    M_list = parse_list_ints(args.M_list)
    seed = args.seed

    rng = np.random.default_rng(seed)

    print("=== CoPBit Q9 – M-PSK AWGN BER Family v0.1 ===")
    print(f"[Param] n_sym        = {n_sym}")
    print(f"[Param] snr_list[dB] = {snr_list}")
    print(f"[Param] M_list       = {M_list}")
    print(f"[Param] seed         = {seed}")
    print("------------------------------------------------------------")

    n_snr = len(snr_list)
    n_M = len(M_list)
    ber_table = np.zeros((n_M, n_snr), dtype=float)

    # 각 M에 대해 전체 비트를 한 번 생성해두고, SNR만 바꿔가며 재사용
    for i, M in enumerate(M_list):
        k = bits_per_symbol(M)
        # bits shape: (n_sym, k)
        bits = rng.integers(0, 2, size=(n_sym, k), dtype=np.int64)
        x = mpsk_modulate(bits, M)

        for j, snr_db in enumerate(snr_list):
            y = add_awgn_complex(x, snr_db, rng)
            k_hat = mpsk_demodulate(y, M)
            bits_hat = indices_to_bits(k_hat, M)
            ber = ber_between_bits(bits, bits_hat)
            ber_table[i, j] = ber

    # 결과 출력: SNR 기준으로 행을 정렬
    header_cols = ["SNR_dB"] + [f"BER_M{M}" for M in M_list]
    col_widths = [8] + [12] * len(M_list)

    def fmt_row(values, widths):
        return " ".join(f"{v:>{w}}" for v, w in zip(values, widths))

    print(fmt_row(header_cols, col_widths))
    print("-" * (sum(col_widths) + len(col_widths) - 1))

    for j, snr_db in enumerate(snr_list):
        row_vals = [f"{snr_db:4.1f}"] + [f"{ber_table[i, j]:.3e}" for i in range(n_M)]
        print(fmt_row(row_vals, col_widths))

    print("-" * (sum(col_widths) + len(col_widths) - 1))
    print("※ 주석")
    print(" - Es = 1 (unit circle) 기준 AWGN-only M-PSK BER 비교용 베이스라인.")
    print(" - SNR 인자는 Es/N0(dB)로 해석.")
    print(" - M=16은 CoPBit 4bit와 동일한 16포인트 등각 간격 위상 구조(단, 비트 라벨은 단순 binary).")
    print(" - 이후 필요 시 Eb/N0 변환, 채널(a/b/c) + EQ, CoPBit 특수 맵핑(Q1)으로 확장 가능.")
    

if __name__ == "__main__":
    main()