#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CoPBit Q12 – PAM4 vs CoPBit-M8 (8-PSK) over channel a/b/c + AWGN (Eb/N0 basis) v0.1

목적:
- M-PSK AWGN 베이스(Q9/Q10) 위에 채널 a/b/c(5-tap ISI)를 얹어서,
  PAM4(2bit/심볼) vs CoPBit-M8(3bit/심볼, 8-PSK) BER을 Eb/N0 공정 기준으로 비교한다.
- EQ는 일단 제외한 v0.1 베이스라인 (AWGN + ISI-only).
  → 이후 Q12b에서 FFE/EQ 추가 예정.

사용 예:
  python copbit_q12_pam4_m8_channel_ebn0_v0.py

  # Eb/N0 범위 넓게 + 채널 a/b/c 모두
  python copbit_q12_pam4_m8_channel_ebn0_v0.py \
    --n_sym 200000 \
    --ebn0_list 0,2,4,6,8,10,12,14,16 \
    --channels a,b,c
"""

import numpy as np
import argparse


# -----------------------------
# 채널 계수 정의 (a/b/c, 5-tap)
# -----------------------------
# ILC3/ILC4에서 사용하던 5-tap ISI 계수 재사용
CH_TAPS = {
    "a": np.array([0.10, 0.40, 1.00, 0.40, 0.10], dtype=float),  # 가장 깨끗한 채널
    "b": np.array([0.05, 0.50, 1.00, 0.50, 0.05], dtype=float),  # 가장 강한 ISI
    "c": np.array([0.075, 0.45, 1.00, 0.45, 0.075], dtype=float) # 중간 채널
}


# -----------------------------
# 유틸: Eb/N0 기반 AWGN 추가
# -----------------------------
def awgn_from_ebn0(x, ebn0_db, bits_per_sym, rng):
    """
    x         : 입력 심볼 시퀀스 (실수 또는 복소)
    ebn0_db   : Eb/N0 [dB]
    bits_per_sym : 심볼당 비트 수 (PAM4=2, M8=3)
    rng       : np.random.Generator

    Es는 입력 시퀀스의 평균 에너지로 계산.
    N0 = Es / (Es/N0), Es/N0 = Eb/N0 * k (k=bits_per_sym)
    복소 AWGN: n = sqrt(N0/2)*(n_r + j n_i)
    """
    x = x.astype(np.complex128)
    Es = np.mean(np.abs(x) ** 2)

    k = float(bits_per_sym)
    ebn0_lin = 10.0 ** (ebn0_db / 10.0)
    esn0_lin = ebn0_lin * k

    N0 = Es / esn0_lin
    sigma = np.sqrt(N0 / 2.0)

    noise = sigma * (rng.standard_normal(size=x.shape) +
                     1j * rng.standard_normal(size=x.shape))
    return x + noise


# -----------------------------
# PAM4 변복조 (Gray mapping)
# -----------------------------
# 레벨: [-3, -1, +1, +3] / sqrt(5)  → Es ≈ 1로 정규화
PAM4_LEVELS = np.array([-3.0, -1.0, 1.0, 3.0], dtype=float)
PAM4_LEVELS_NORM = PAM4_LEVELS / np.sqrt(5.0)

# Gray mapping: 00→-3, 01→-1, 11→+1, 10→+3
PAM4_BITS_TABLE = np.array([
    [0, 0],  # -3
    [0, 1],  # -1
    [1, 1],  # +1
    [1, 0],  # +3
], dtype=int)


def pam4_mod(bits):
    """
    bits: (N_bits,) 0/1 배열, N_bits는 짝수.
    return: (N_sym,) 실수 PAM4 심볼 (정규화)
    """
    bits = np.asarray(bits, dtype=int)
    assert bits.ndim == 1
    assert bits.size % 2 == 0

    b = bits.reshape(-1, 2)
    b1 = b[:, 0]
    b0 = b[:, 1]

    # 조건별 레벨 할당
    levels = np.empty(b.shape[0], dtype=float)
    # 00 -> -3
    mask = (b1 == 0) & (b0 == 0)
    levels[mask] = PAM4_LEVELS_NORM[0]
    # 01 -> -1
    mask = (b1 == 0) & (b0 == 1)
    levels[mask] = PAM4_LEVELS_NORM[1]
    # 11 -> +1
    mask = (b1 == 1) & (b0 == 1)
    levels[mask] = PAM4_LEVELS_NORM[2]
    # 10 -> +3
    mask = (b1 == 1) & (b0 == 0)
    levels[mask] = PAM4_LEVELS_NORM[3]

    return levels


def pam4_demod(y):
    """
    y: (N_sym,) 실수 또는 복소 (실수 축 위주) 관측 샘플
    return: (N_bits,) 0/1 배열 (원래 비트열 복원)
    """
    y = np.asarray(y)
    # 복소라면 실수부만 사용
    y_real = np.real(y)

    # 각 샘플에 대해 가장 가까운 PAM4 레벨 인덱스
    diff = np.abs(y_real[:, None] - PAM4_LEVELS_NORM[None, :])
    idx_hat = np.argmin(diff, axis=1)  # shape (N_sym,)

    bits_hat = PAM4_BITS_TABLE[idx_hat]  # (N_sym, 2)
    return bits_hat.reshape(-1)


# -----------------------------
# M-PSK 변복조 (CoPBit-M8용)
# -----------------------------
def bits_to_int(bits, k):
    """
    bits: (N*k,) 0/1 → (N,) 정수 [0..2^k-1]
    """
    bits = np.asarray(bits, dtype=int)
    assert bits.size % k == 0
    b = bits.reshape(-1, k)
    # MSB-first binary → 정수
    # 예: [b3 b2 b1 b0] → b3*8 + b2*4 + b1*2 + b0
    weights = 1 << np.arange(k - 1, -1, -1, dtype=int)
    return (b * weights).sum(axis=1)


def int_to_bits(vals, k):
    """
    vals: (N,) 정수 → (N*k,) 비트
    """
    vals = np.asarray(vals, dtype=int)
    N = vals.size
    bits = np.zeros((N, k), dtype=int)
    for i in range(k):
        shift = k - 1 - i
        bits[:, i] = (vals >> shift) & 1
    return bits.reshape(-1)


def mpsk_mod(bits, M):
    """
    bits: (N_bits,) 0/1 배열
    M   : PSK 차수 (예: 8)
    return: (N_sym,) 복소 심볼, unit circle (Es ≈ 1)
    """
    k = int(np.log2(M))
    assert 2 ** k == M, "M must be power of 2"
    sym_idx = bits_to_int(bits, k)  # [0..M-1]
    theta = 2.0 * np.pi * sym_idx.astype(float) / float(M)
    x = np.exp(1j * theta)
    return x


def mpsk_demod(y, M):
    """
    y: (N_sym,) 복소 관측 샘플
    M: PSK 차수
    return: (N_bits,) 복원 비트열 (binary labeling 기준)
    """
    k = int(np.log2(M))
    # angle in [0, 2π)
    theta = np.angle(y)
    theta = np.mod(theta, 2.0 * np.pi)

    step = 2.0 * np.pi / float(M)
    idx_hat = np.round(theta / step).astype(int) % M  # [0..M-1]

    bits_hat = int_to_bits(idx_hat, k)
    return bits_hat


# -----------------------------
# 채널 통과 함수
# -----------------------------
def apply_channel(x, h):
    """
    x: (N_sym,) 실수/복소 심볼
    h: (L,)    채널 탭
    return: np.convolve(x, h, mode='same')
    """
    return np.convolve(x, h.astype(np.complex128), mode="same")


# -----------------------------
# 메인 루틴
# -----------------------------
def main():
    parser = argparse.ArgumentParser(
        description="CoPBit Q12 – PAM4 vs CoPBit-M8(8-PSK) over channel a/b/c + AWGN (Eb/N0 basis) v0.1"
    )
    parser.add_argument(
        "--n_sym",
        type=int,
        default=100000,
        help="심볼 수 (각 스킴별 심볼 개수, default: 100000)",
    )
    parser.add_argument(
        "--ebn0_list",
        type=str,
        default="0,2,4,6,8,10,12,14,16",
        help="Eb/N0[dB] 리스트 (콤마 구분, default: '0,2,4,6,8,10,12,14,16')",
    )
    parser.add_argument(
        "--channels",
        type=str,
        default="a,b,c",
        help="사용할 채널 세트 (예: 'a', 'a,b', 'a,b,c')",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1,
        help="난수 시드 (default: 1)",
    )

    args = parser.parse_args()

    n_sym = args.n_sym
    ebn0_list = [float(x) for x in args.ebn0_list.split(",") if x.strip() != ""]
    ch_list = [c.strip() for c in args.channels.split(",") if c.strip() != ""]
    rng = np.random.default_rng(args.seed)

    print("=== CoPBit Q12 – PAM4 vs CoPBit-M8 Channel+AWGN (Eb/N0 basis) v0.1 ===")
    print(f"[Param] n_sym          = {n_sym}")
    print(f"[Param] Eb/N0_list(dB) = {ebn0_list}")
    print(f"[Param] channels       = {ch_list}")
    print(f"[Param] seed           = {args.seed}")
    print("")

    bits_per_pam4 = 2
    bits_per_m8 = 3

    for ch_name in ch_list:
        if ch_name not in CH_TAPS:
            print(f"[WARN] Unknown channel '{ch_name}' – skip.")
            continue

        h = CH_TAPS[ch_name]
        print(f"--- Channel {ch_name} (taps = {h.tolist()}) ---")
        print(" EbN0_dB | BER_pam4    | BER_m8(CoPBit) ")
        print("-----------------------------------------")

        for ebn0_db in ebn0_list:
            # PAM4
            n_bits_pam4 = n_sym * bits_per_pam4
            bits_pam4 = rng.integers(0, 2, size=n_bits_pam4, dtype=int)
            x4 = pam4_mod(bits_pam4)  # (n_sym,)

            x4_ch = apply_channel(x4, h)
            y4 = awgn_from_ebn0(x4_ch, ebn0_db, bits_per_pam4, rng)
            bits4_hat = pam4_demod(y4)

            ber_pam4 = np.mean(bits4_hat != bits_pam4)

            # CoPBit-M8 (8-PSK, 3bit/심볼)
            n_bits_m8 = n_sym * bits_per_m8
            bits_m8 = rng.integers(0, 2, size=n_bits_m8, dtype=int)
            x8 = mpsk_mod(bits_m8, M=8)

            x8_ch = apply_channel(x8, h)
            y8 = awgn_from_ebn0(x8_ch, ebn0_db, bits_per_m8, rng)
            bits8_hat = mpsk_demod(y8, M=8)

            ber_m8 = np.mean(bits8_hat != bits_m8)

            print(f"{ebn0_db:8.1f} | {ber_pam4:10.3e} | {ber_m8:14.3e}")

        print("-----------------------------------------")
        print("")

    print("※ 주석")
    print(" - PAM4: 실수 4레벨 [-3,-1,1,3]/sqrt(5) Gray mapping + 5-tap 채널 a/b/c + AWGN.")
    print(" - CoPBit-M8: unit circle 8-PSK (3bit/심볼) + 동일 채널 + AWGN.")
    print(" - Eb/N0 기반으로 비트당 에너지 공정 비교를 수행 (Es/N0 = Eb/N0 * k).")
    print(" - v0.1에서는 EQ/FFE 없이 순수 채널+AWGN만 반영된 베이스라인.")
    print("   → 이후 Q12b에서 FFE/EQ 추가, Kuramoto 멀티레인 보정과의 결합 등 확장 예정.")


if __name__ == "__main__":
    main()