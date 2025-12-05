#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CoPBit Q20a – PAM4 vs M8 (Channel-b mid-ISI, FFE+DFE, NLMS) BER vs Eb/N0 v0.1

- Channel-b 5-tap mid-ISI (symbol-rate)
- 단일 레인 기준
- Tx: PAM4 (2bit/sym) vs M8(8-PSK, 3bit/sym)
- Rx: FFE + DFE (정규화 LMS, training 구간 + DD 모드)
- 목표: Q18의 "FFE-only 실패" 기준선에서, FFE+DFE로
        실제로 BER을 떨어뜨릴 수 있는지 보는 기초 실험
"""

import argparse
import numpy as np


# ===========================
# 유틸: Eb/N0 → AWGN 추가
# ===========================

def add_awgn(x, ebn0_db, bits_per_sym):
    """
    x: complex baseband sequence
    bits_per_sym: log2(M)
    """
    ebn0_lin = 10.0 ** (ebn0_db / 10.0)
    # 심볼 에너지
    Es = np.mean(np.abs(x) ** 2)
    # Eb = Es / k
    k = bits_per_sym
    Eb = Es / k
    N0 = Eb / ebn0_lin
    # complex AWGN: Re, Im 각각 N(0, N0/2)
    noise_var = N0 / 2.0
    n = np.sqrt(noise_var) * (np.random.randn(*x.shape) + 1j * np.random.randn(*x.shape))
    return x + n


# ===========================
# Mod / Demod: PAM4
# ===========================

# Gray mapping: 00→-3, 01→-1, 11→+1, 10→+3
PAM4_BITS2LEV = {
    (0, 0): -3.0,
    (0, 1): -1.0,
    (1, 1): +1.0,
    (1, 0): +3.0,
}
PAM4_LEV2BITS = {v: k for k, v in PAM4_BITS2LEV.items()}
PAM4_LEVELS = np.array(sorted(PAM4_LEV2BITS.keys()))  # [-3, -1, +1, +3]


def pam4_mod(bits):
    """
    bits: shape (N_bits,), 0/1
    return:
      s: complex symbols (real PAM4)
      idx: symbol index (0..3)
      bits_reshaped: (N_sym, 2)
    """
    assert bits.ndim == 1
    assert bits.size % 2 == 0
    bits_2 = bits.reshape(-1, 2)
    Nsym = bits_2.shape[0]
    s = np.zeros(Nsym, dtype=np.complex128)
    idx = np.zeros(Nsym, dtype=np.int64)
    for n in range(Nsym):
        b = tuple(bits_2[n].tolist())
        lev = PAM4_BITS2LEV[b]
        s[n] = lev + 0j
        idx[n] = np.where(PAM4_LEVELS == lev)[0][0]
    return s, idx, bits_2


def pam4_slicer(z):
    """
    z: complex equalized symbol(s), shape (N,)
    return:
      s_hat: complex symbols on PAM4 grid
      idx_hat: index 0..3
      bits_hat: (N,2) bit array
    """
    x = np.real(z)
    diff = np.abs(x - PAM4_LEVELS[:, None])
    idx_hat = np.argmin(diff, axis=0)
    lev_hat = PAM4_LEVELS[idx_hat]
    bits_hat = np.array([PAM4_LEV2BITS[lv] for lv in lev_hat], dtype=int)
    return lev_hat + 0j, idx_hat, bits_hat


# ===========================
# Mod / Demod: M8 (8-PSK)
# ===========================

# Gray-like 8-PSK mapping
# 000→0, 001→1, 011→2, 010→3, 110→4, 111→5, 101→6, 100→7
M8_BITS2IDX = {
    (0, 0, 0): 0,
    (0, 0, 1): 1,
    (0, 1, 1): 2,
    (0, 1, 0): 3,
    (1, 1, 0): 4,
    (1, 1, 1): 5,
    (1, 0, 1): 6,
    (1, 0, 0): 7,
}
M8_IDX2BITS = {v: k for k, v in M8_BITS2IDX.items()}

# 8-PSK constellation
M8_CONST = np.exp(1j * 2.0 * np.pi * np.arange(8) / 8.0)


def m8_mod(bits):
    """
    bits: shape (N_bits,)
    return:
      s: complex 8-PSK symbols
      idx: 0..7
      bits_reshaped: (N_sym, 3)
    """
    assert bits.ndim == 1
    assert bits.size % 3 == 0
    bits_3 = bits.reshape(-1, 3)
    Nsym = bits_3.shape[0]
    idx = np.zeros(Nsym, dtype=np.int64)
    s = np.zeros(Nsym, dtype=np.complex128)
    for n in range(Nsym):
        b = tuple(bits_3[n].tolist())
        k = M8_BITS2IDX[b]
        idx[n] = k
        s[n] = M8_CONST[k]
    return s, idx, bits_3


def m8_slicer(z):
    """
    z: complex equalized symbols (array)
    return:
      s_hat: complex symbols on 8-PSK grid
      idx_hat: 0..7
      bits_hat: (N_sym, 3)
    """
    ang = np.angle(z)
    ang = np.mod(ang, 2.0 * np.pi)
    k_hat = np.rint(ang / (2.0 * np.pi / 8.0)).astype(int) % 8
    s_hat = M8_CONST[k_hat]
    bits_hat = np.array([M8_IDX2BITS[int(k)] for k in k_hat], dtype=int)
    return s_hat, k_hat, bits_hat


# ===========================
# 채널: mid-ISI (Channel-b)
# ===========================

def get_mid_isi_channel():
    """
    Q18 / Q20에서 사용할 mid-ISI 채널-b 예시.
    심플하게 [0.05, 0.5, 1.0, 0.5, 0.05] 정규화 버전 사용.
    """
    h = np.array([0.05, 0.5, 1.0, 0.5, 0.05], dtype=np.float64)
    h = h / np.sum(h)
    return h.astype(np.complex128)


def apply_channel(x, h):
    """
    x: complex symbols
    h: complex taps
    return: y = x * h (symbol-rate), same length
    """
    y_full = np.convolve(x, h, mode="full")
    delay = (len(h) - 1) // 2
    start = delay
    end = start + len(x)
    return y_full[start:end]


# ===========================
# FFE + DFE (정규화 LMS 기반)
# ===========================

def lms_ffe_dfe_train(y, d, Lf, Lb, mu, n_train, w_init=None, b_init=None,
                      w_clip=1e3, eps=1e-8):
    """
    y: channel output (complex), length N
    d: desired symbols (complex), length N
    Lf: FFE length
    Lb: DFE length (0이면 DFE 없음)
    mu: base step size (NLMS에서 0<mu<2 추천)
    n_train: training 심볼 개수 (<= N)
    w_clip: weight 폭발 방지 클리핑 임계값
    eps: power regularization

    return:
      w: (Lf,) complex
      b: (Lb,) complex (Lb=0이면 빈 배열)
    """
    N = len(y)
    assert len(d) == N
    n_train = min(n_train, N)

    if w_init is None:
        w = np.zeros(Lf, dtype=np.complex128)
        w[Lf // 2] = 1.0 + 0j
    else:
        w = np.array(w_init, dtype=np.complex128)

    if Lb > 0:
        if b_init is None:
            b = np.zeros(Lb, dtype=np.complex128)
        else:
            b = np.array(b_init, dtype=np.complex128)
    else:
        b = np.zeros(0, dtype=np.complex128)

    n_start = Lf - 1

    for n in range(n_start, n_train):
        # FFE 입력
        u = y[n:n - Lf:-1] if Lf > 0 else np.zeros(0, dtype=np.complex128)
        if len(u) < Lf:
            u = np.pad(u, (0, Lf - len(u)), mode="constant")

        # DFE 피드백 (정답심볼 사용, decision-free)
        if Lb > 0:
            fb = []
            for k in range(1, Lb + 1):
                idx = n - k
                fb.append(d[idx] if idx >= 0 else 0.0 + 0j)
            fb = np.array(fb, dtype=np.complex128)
        else:
            fb = np.zeros(0, dtype=np.complex128)

        y_eq = np.dot(np.conjugate(w), u)
        if Lb > 0:
            y_eq -= np.dot(np.conjugate(b), fb)

        e = d[n] - y_eq

        # 입력 파워 기반 정규화 (NLMS)
        power = np.vdot(u, u).real
        if Lb > 0:
            power += np.vdot(fb, fb).real
        mu_eff = mu / (power + eps)

        w = w + mu_eff * e * np.conjugate(u)
        if Lb > 0:
            b = b - mu_eff * e * np.conjugate(fb)

        # 폭발 방지
        if (np.any(np.isnan(w)) or np.max(np.abs(w)) > w_clip or
            np.any(np.isnan(b)) or (Lb > 0 and np.max(np.abs(b)) > w_clip)):
            print(f"[WARN] FFE/DFE coeff exploded during training (n={n}). stop updates.")
            break

    return w, b


def ffe_dfe_detect(y, Lf, Lb, w, b, slicer_fn):
    """
    y: channel output (complex), length N
    w: (Lf,) FFE coeff
    b: (Lb,) DFE coeff (Lb=0이면 DFE 없음)
    slicer_fn: function(z_vec) -> (s_hat, idx_hat, bits_hat)
      - z_vec: shape (N_eff,) complex equalized symbols

    return:
      idx_hat_full: full-length array of detected symbol indices (0..M-1), invalid 부분은 -1
      bits_hat_full: (N_sym, k) int array, invalid 부분은 0, valid 범위는 나중에 잘라서 사용
      n_start: 유효한 detection 시작 인덱스 (Lf-1)
    """
    N = len(y)
    n_start = Lf - 1
    idx_hat_full = -1 * np.ones(N, dtype=int)
    bits_hat_list = []
    x_hat = np.zeros(N, dtype=np.complex128)

    for n in range(n_start, N):
        u = y[n:n - Lf:-1] if Lf > 0 else np.zeros(0, dtype=np.complex128)
        if len(u) < Lf:
            u = np.pad(u, (0, Lf - len(u)), mode="constant")

        if Lb > 0:
            fb = []
            for k in range(1, Lb + 1):
                idx = n - k
                fb.append(x_hat[idx] if idx >= 0 else 0.0 + 0j)
            fb = np.array(fb, dtype=np.complex128)
        else:
            fb = np.zeros(0, dtype=np.complex128)

        y_eq = np.dot(np.conjugate(w), u)
        if Lb > 0:
            y_eq -= np.dot(np.conjugate(b), fb)

        s_hat, idx_hat, bits_hat = slicer_fn(np.array([y_eq]))
        x_hat[n] = s_hat[0]
        idx_hat_full[n] = idx_hat[0]
        bits_hat_list.append(bits_hat[0])

    if len(bits_hat_list) == 0:
        bits_hat_full = np.zeros((N, 1), dtype=int)
    else:
        k = bits_hat_list[0].shape[0]
        bits_hat_full = np.zeros((N, k), dtype=int)
        for i, b_row in enumerate(bits_hat_list):
            bits_hat_full[n_start + i, :] = b_row

    return idx_hat_full, bits_hat_full, n_start


# ===========================
# 메인 루프
# ===========================

def run_q20a(args):
    np.random.seed(args.seed)

    ebn0_list = [float(s) for s in args.ebn0_list.split(",") if s.strip() != ""]
    h = get_mid_isi_channel()

    print("=== CoPBit Q20a – PAM4 vs M8 (Channel-b mid-ISI, FFE+DFE, NLMS) BER vs Eb/N0 v0.1 ===")
    print(f"[Param] n_sym          = {args.n_sym}")
    print(f"[Param] Eb/N0_list(dB) = {ebn0_list}")
    print(f"[Param] ffe_len        = {args.ffe_len}")
    print(f"[Param] dfe_len        = {args.dfe_len}")
    print(f"[Param] train_frac     = {args.train_frac}")
    print(f"[Param] mu_ffe         = {args.mu_ffe}")
    print(f"[Param] seed           = {args.seed}")
    print()
    print(f"[Chan ] h_midISI (norm) = {np.real(h)}")
    print("[Info ] FFE+DFE baseline (PAM4 vs M8, single-lane, NLMS)")
    print()
    print("==============================================================")
    print(" Eb/N0_dB |  BER_PAM4_FFE+DFE  |  BER_M8_FFE+DFE ")
    print("---------------------------------------------------------------")

    for ebn0_db in ebn0_list:
        # --- PAM4 ---
        bits_per_sym_pam4 = 2
        Nbits_pam4 = args.n_sym * bits_per_sym_pam4
        bits_tx_pam4 = np.random.randint(0, 2, Nbits_pam4, dtype=int)
        s_pam4, idx_pam4, bits_pam4_2 = pam4_mod(bits_tx_pam4)

        y_pam4 = apply_channel(s_pam4, h)
        y_pam4 = add_awgn(y_pam4, ebn0_db, bits_per_sym_pam4)

        n_train = int(args.train_frac * args.n_sym)
        w_pam4, b_pam4 = lms_ffe_dfe_train(
            y_pam4,
            s_pam4,
            Lf=args.ffe_len,
            Lb=args.dfe_len,
            mu=args.mu_ffe,
            n_train=n_train,
        )

        idx_hat_pam4, bits_hat_pam4, n_start_pam4 = ffe_dfe_detect(
            y_pam4,
            Lf=args.ffe_len,
            Lb=args.dfe_len,
            w=w_pam4,
            b=b_pam4,
            slicer_fn=pam4_slicer,
        )

        bits_tx_pam4_2d = bits_pam4_2
        bits_tx_valid_pam4 = bits_tx_pam4_2d[n_start_pam4:, :].reshape(-1)
        bits_hat_valid_pam4 = bits_hat_pam4[n_start_pam4:, :].reshape(-1)
        Nbits_valid_pam4 = min(len(bits_tx_valid_pam4), len(bits_hat_valid_pam4))
        if Nbits_valid_pam4 > 0:
            ber_pam4 = np.mean(
                bits_tx_valid_pam4[:Nbits_valid_pam4] != bits_hat_valid_pam4[:Nbits_valid_pam4]
            )
        else:
            ber_pam4 = 0.5

        # --- M8 ---
        bits_per_sym_m8 = 3
        Nbits_m8 = args.n_sym * bits_per_sym_m8
        bits_tx_m8 = np.random.randint(0, 2, Nbits_m8, dtype=int)
        s_m8, idx_m8, bits_m8_3 = m8_mod(bits_tx_m8)

        y_m8 = apply_channel(s_m8, h)
        y_m8 = add_awgn(y_m8, ebn0_db, bits_per_sym_m8)

        w_m8, b_m8 = lms_ffe_dfe_train(
            y_m8,
            s_m8,
            Lf=args.ffe_len,
            Lb=args.dfe_len,
            mu=args.mu_ffe,
            n_train=n_train,
        )

        idx_hat_m8, bits_hat_m8, n_start_m8 = ffe_dfe_detect(
            y_m8,
            Lf=args.ffe_len,
            Lb=args.dfe_len,
            w=w_m8,
            b=b_m8,
            slicer_fn=m8_slicer,
        )

        bits_tx_m8_2d = bits_m8_3
        bits_tx_valid_m8 = bits_tx_m8_2d[n_start_m8:, :].reshape(-1)
        bits_hat_valid_m8 = bits_hat_m8[n_start_m8:, :].reshape(-1)
        Nbits_valid_m8 = min(len(bits_tx_valid_m8), len(bits_hat_valid_m8))
        if Nbits_valid_m8 > 0:
            ber_m8 = np.mean(
                bits_tx_valid_m8[:Nbits_valid_m8] != bits_hat_valid_m8[:Nbits_valid_m8]
            )
        else:
            ber_m8 = 0.5

        print(f"{ebn0_db:10.1f} |   {ber_pam4:12.9f} |   {ber_m8:12.9f}")

    print("---------------------------------------------------------------")


def parse_args():
    p = argparse.ArgumentParser(
        description="CoPBit Q20a – PAM4 vs M8 (Channel-b mid-ISI, FFE+DFE, NLMS) BER vs Eb/N0 v0.1"
    )
    p.add_argument("--n_sym", type=int, default=200000,
                   help="number of symbols per simulation")
    p.add_argument("--ebn0_list", type=str, default="10,12,14,16,18,20,22",
                   help="comma-separated Eb/N0 list in dB, e.g. '10,12,14'")
    p.add_argument("--ffe_len", type=int, default=11,
                   help="FFE length (number of taps)")
    p.add_argument("--dfe_len", type=int, default=4,
                   help="DFE length (0이면 DFE 사용 안함)")
    p.add_argument("--train_frac", type=float, default=0.5,
                   help="fraction of symbols used for FFE/DFE training (0~1)")
    p.add_argument("--mu_ffe", type=float, default=0.2,
                   help="base step size for NLMS (0<mu<2 추천)")
    p.add_argument("--seed", type=int, default=1,
                   help="random seed")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_q20a(args)