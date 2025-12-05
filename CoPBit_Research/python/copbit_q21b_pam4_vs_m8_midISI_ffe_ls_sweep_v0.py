#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CoPBit Q21b – PAM4 vs M8 mid-ISI (Channel-b) + FFE-only LS sweep (ffe_len, train_frac) v0

Q21a에서 단일 (ffe_len, train_frac) 조합으로 PAM4 vs M8 BER을 비교했다면,
Q21b는 여러 FFE 길이와 train_frac 조합을 스윕하면서
PAM4 / M8 각각의 BER을 표 형태로 뽑는 용도이다.

- 채널: mid-ISI (Channel-b 5-tap, norm=1) – Q13/Q14/Q20c/Q20d/Q21a와 동일
- 변조:
    · PAM4 (2 bit/sym, 1D 레벨 [-3, -1, +1, +3])
    · M8   (8-PSK, 3 bit/sym, unit circle)
- EQ  : FFE-only, LS 고정 계수
        (noise-free 채널 출력 x_chan 기준 LS 학습 후,
         같은 계수로 AWGN이 섞인 y에 적용)
- 스윕 파라미터:
    · ffe_len_list   = [7, 9, 11, 13]  (기본값)
    · train_frac_list = [0.3, 0.5, 0.8, 1.0] (기본값)
- 출력:
    (ffe_len, train_frac) 조합별 BER_PAM4, BER_M8 테이블
    옵션으로 CSV 파일 저장 가능 (--csv_out)
"""

import argparse
import csv
import numpy as np


# =========================
#  PAM4 Mod/Demod
# =========================

def pam4_levels():
    """PAM4 심볼 레벨 [-3, -1, +1, +3]."""
    return np.array([-3.0, -1.0, +1.0, +3.0], dtype=np.float64)


PAM4_LEVELS = pam4_levels()

PAM4_BITS = np.array([
    [0, 0],  # -3
    [0, 1],  # -1
    [1, 1],  # +1
    [1, 0],  # +3
], dtype=np.int64)


def pam4_mod(k):
    """k in {0,1,2,3} -> PAM4 심볼 레벨."""
    s = PAM4_LEVELS[k]
    return s.astype(np.float64)


def pam4_demod(z):
    """Nearest-neighbor PAM4 slicer."""
    z_real = np.real(z).astype(np.float64)
    z_real = z_real[:, None]          # (N, 1)
    lv = PAM4_LEVELS[None, :]         # (1, 4)
    dist2 = (z_real - lv) ** 2
    k_hat = np.argmin(dist2, axis=1)
    return k_hat.astype(np.int64)


def pam4_bit_errors(k, k_hat):
    bits     = PAM4_BITS[k]
    bits_hat = PAM4_BITS[k_hat]
    bit_err  = np.not_equal(bits, bits_hat).sum()
    return bit_err, bits.size


# =========================
#  M8 Mod/Demod (8-PSK)
# =========================

def m8_constellation():
    """8-PSK unit circle: exp(j*2πk/8), k=0..7."""
    k = np.arange(8, dtype=np.float64)
    phases = 2.0 * np.pi * k / 8.0
    points = np.exp(1j * phases)
    return points.astype(np.complex128)


M8_POINTS = m8_constellation()

M8_BITS = np.array([
    [0, 0, 0],  # k=0
    [0, 0, 1],  # k=1
    [0, 1, 1],  # k=2
    [0, 1, 0],  # k=3
    [1, 1, 0],  # k=4
    [1, 1, 1],  # k=5
    [1, 0, 1],  # k=6
    [1, 0, 0],  # k=7
], dtype=np.int64)


def m8_mod(k):
    """k in {0..7} -> 8-PSK 심볼."""
    s = M8_POINTS[k]
    return s.astype(np.complex128)


def m8_demod(z):
    """Nearest 8-PSK point demod."""
    z = z.astype(np.complex128)
    diff  = z[:, None] - M8_POINTS[None, :]
    dist2 = np.abs(diff) ** 2
    k_hat = np.argmin(dist2, axis=1)
    return k_hat.astype(np.int64)


def m8_bit_errors(k, k_hat):
    bits     = M8_BITS[k]
    bits_hat = M8_BITS[k_hat]
    bit_err  = np.not_equal(bits, bits_hat).sum()
    return bit_err, bits.size


# =========================
#  채널 / AWGN
# =========================

def get_mid_isi_channel():
    """
    Channel-b 5-tap mid-ISI 채널 (norm=1).
    Q13/Q14/Q20c/Q20d/Q21a와 동일 계수.
    """
    h = np.array(
        [0.04075696, 0.40756957, 0.81513915, 0.40756957, 0.04075696],
        dtype=np.float64,
    )
    h = h / np.linalg.norm(h)
    return h.astype(np.complex128)


def add_awgn(x, ebn0_db, bits_per_sym=2, rng=None):
    """
    Complex baseband AWGN 추가.
    Es/N0 = Eb/N0 * bits_per_sym.
    """
    if rng is None:
        rng = np.random.default_rng()
    x = x.astype(np.complex128)

    Es       = np.mean(np.abs(x) ** 2)
    ebn0_lin = 10.0 ** (ebn0_db / 10.0)
    esn0_lin = ebn0_lin * bits_per_sym
    N0       = Es / esn0_lin
    sigma    = np.sqrt(N0 / 2.0)

    n = sigma * (rng.normal(size=x.shape) + 1j * rng.normal(size=x.shape))
    return x + n


# =========================
#  FFE LS 학습 + BER 평가
# =========================

def ffe_train_and_eval_ls(
    k_tx,
    mod_fn,
    demod_fn,
    bit_err_fn,
    h,
    ebn0_db,
    ffe_len=11,
    train_frac=0.5,
    bits_per_sym=2,
    seed=1,
):
    """
    공통 FFE LS 학습 + BER 평가.

    - noise-free 채널 출력 x_chan 기준으로 LS 학습
    - 동일 계수로 AWGN이 섞인 y에 적용 후 BER 계산
    """
    rng = np.random.default_rng(seed)

    N = len(k_tx)
    s = mod_fn(k_tx)
    x_sym = s.astype(np.complex128)

    # mid-ISI 채널 통과 (noise-free)
    x_chan = np.convolve(x_sym, h, mode="same")

    # AWGN 추가
    y = add_awgn(x_chan, ebn0_db, bits_per_sym=bits_per_sym, rng=rng)

    L = ffe_len
    start = L - 1
    n_train = int(train_frac * N)
    if n_train <= start:
        n_train = start + 1

    # LS 학습용 입력/타겟
    x_nf = x_chan
    d_sym = x_sym

    scale = np.sqrt(np.mean(np.abs(x_nf) ** 2))
    if (not np.isfinite(scale)) or (scale < 1e-12):
        scale = 1.0
    x_norm = x_nf / scale
    d_norm = d_sym / scale

    T = n_train - start
    U = np.zeros((T, L), dtype=np.complex128)
    d_vec = np.zeros(T, dtype=np.complex128)

    idx = 0
    for n in range(start, n_train):
        if n - L >= -1:
            u = x_norm[n : n - L : -1]
        else:
            u = x_norm[max(0, n - L + 1) : n + 1][::-1]
        if len(u) < L:
            pad = np.zeros(L - len(u), dtype=np.complex128)
            u = np.concatenate([u, pad])
        U[idx, :] = u
        d_vec[idx] = d_norm[n]
        idx += 1

    with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
        R = U.conj().T @ U
        p = U.conj().T @ d_vec

    trace_R = np.real(np.trace(R))
    if (not np.isfinite(trace_R)) or (trace_R <= 0):
        # fallback: unit-tap(중앙) FFE
        w = np.zeros(L, dtype=np.complex128)
        w[L // 2] = 1.0 + 0j
    else:
        ridge = 1e-3 * (trace_R / L) + 1e-9
        R_reg = R + ridge * np.eye(L, dtype=np.complex128)
        w = np.linalg.solve(R_reg, p)

    # 학습된 w로 전체 시퀀스 equalize
    z_all = np.zeros(N, dtype=np.complex128)
    for n in range(start, N):
        if n - L >= -1:
            u = y[n : n - L : -1]
        else:
            u = y[max(0, n - L + 1) : n + 1][::-1]
        if len(u) < L:
            pad = np.zeros(L - len(u), dtype=np.complex128)
            u = np.concatenate([u, pad])
        u = u.astype(np.complex128)
        z_all[n] = np.vdot(w, u)

    k_tx_eff  = k_tx[start:]
    k_hat_eff = demod_fn(z_all[start:])

    bit_err, bit_total = bit_err_fn(k_tx_eff, k_hat_eff)
    ber = bit_err / bit_total
    return ber


# =========================
#  메인
# =========================

def parse_list_floats(s):
    return [float(v) for v in s.split(",") if v.strip() != ""]


def parse_list_ints(s):
    return [int(v) for v in s.split(",") if v.strip() != ""]


def main():
    parser = argparse.ArgumentParser(
        description="CoPBit Q21b – PAM4 vs M8 mid-ISI (Channel-b) + FFE-only LS sweep (ffe_len, train_frac) v0",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--n_sym", type=int, default=200000,
                        help="Number of symbols")
    parser.add_argument("--ebn0", type=float, default=16.0,
                        help="Eb/N0 in dB (single value for sweep)")
    parser.add_argument("--ffe_len_list", type=str, default="7,9,11,13",
                        help='FFE length list, e.g. "7,9,11,13"')
    parser.add_argument("--train_frac_list", type=str, default="0.3,0.5,0.8,1.0",
                        help='Training fraction list, e.g. "0.3,0.5,0.8,1.0"')
    parser.add_argument("--seed", type=int, default=1,
                        help="Random seed base")
    parser.add_argument("--csv_out", type=str, default="",
                        help="Optional CSV output path")
    args = parser.parse_args()

    n_sym = args.n_sym
    ebn0_db = args.ebn0
    ffe_len_list = parse_list_ints(args.ffe_len_list)
    train_frac_list = parse_list_floats(args.train_frac_list)
    seed = args.seed
    csv_out = args.csv_out

    print("=== CoPBit Q21b – PAM4 vs M8 mid-ISI (Channel-b) + FFE-only LS sweep v0 ===")
    print(f"[Param] n_sym          = {n_sym}")
    print(f"[Param] Eb/N0(dB)      = {ebn0_db}")
    print(f"[Param] ffe_len_list   = {ffe_len_list}")
    print(f"[Param] train_frac_list= {train_frac_list}")
    print(f"[Param] seed           = {seed}")
    print()

    h = get_mid_isi_channel()
    print(f"[Chan ] h_midISI (norm) = {np.round(h.real, 8)}")
    print("[Info ] FFE-only LS baseline sweep (PAM4 vs M8, single-lane, mid-ISI + AWGN)")
    print()

    rng = np.random.default_rng(seed)
    k_tx_pam4 = rng.integers(low=0, high=4, size=n_sym, dtype=np.int64)
    k_tx_m8   = rng.integers(low=0, high=8, size=n_sym, dtype=np.int64)

    results = []

    print("======================================================================")
    print(" ffe_len | train_frac |   BER_PAM4_FFE    |    BER_M8_FFE      ")
    print("----------------------------------------------------------------------")

    for L in ffe_len_list:
        for tr in train_frac_list:
            # PAM4
            ber_pam4 = ffe_train_and_eval_ls(
                k_tx=k_tx_pam4,
                mod_fn=pam4_mod,
                demod_fn=pam4_demod,
                bit_err_fn=pam4_bit_errors,
                h=h,
                ebn0_db=ebn0_db,
                ffe_len=L,
                train_frac=tr,
                bits_per_sym=2,
                seed=seed + L * 10 + int(tr * 100) + 1000,
            )
            # M8
            ber_m8 = ffe_train_and_eval_ls(
                k_tx=k_tx_m8,
                mod_fn=m8_mod,
                demod_fn=m8_demod,
                bit_err_fn=m8_bit_errors,
                h=h,
                ebn0_db=ebn0_db,
                ffe_len=L,
                train_frac=tr,
                bits_per_sym=3,
                seed=seed + L * 10 + int(tr * 100) + 2000,
            )

            print(f"{L:7d} | {tr:10.2f} | {ber_pam4:16.9f} | {ber_m8:16.9f}")

            results.append({
                "ffe_len": L,
                "train_frac": tr,
                "ber_pam4": ber_pam4,
                "ber_m8": ber_m8,
            })

    print("----------------------------------------------------------------------")

    if csv_out:
        fieldnames = ["ffe_len", "train_frac", "ber_pam4", "ber_m8"]
        with open(csv_out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in results:
                writer.writerow(row)
        print(f"[Info ] CSV saved to: {csv_out}")


if __name__ == "__main__":
    main()