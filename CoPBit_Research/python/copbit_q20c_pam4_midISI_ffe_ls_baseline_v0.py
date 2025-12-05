#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CoPBit Q20c – PAM4 mid-ISI (Channel-b) + FFE-only baseline (LMS / NLMS / LS) v0

단일-lane PAM4를 mid-ISI(Channel-b 5-tap) + AWGN 채널에 통과시키고,
FFE-only(equalizer)로만 ISI를 보상했을 때의 BER vs Eb/N0 기준선을 만드는 스크립트.

- 채널: mid-ISI (Channel-b 5-tap, 정규화)
- 변조: PAM4 (Gray mapping, 2 bit/symbol)
- EQ  : FFE-only (LMS / NLMS / LS 선택 가능, 기본은 NLMS)
- 학습: 앞쪽 train_frac 구간에서만 Tx 심볼을 기준으로 학습 (decision-directed OFF 기본)

이 스크립트를 기준선으로 고정해 두고,
추후 M8/CoPBit, Kuramoto, p_ref 등을 같은 채널/EQ 구조에 얹어서 비교하는 용도로 사용.
"""

import argparse
import numpy as np


# =========================
#  PAM4 Mod/Demod
# =========================

def pam4_gray_levels():
    """
    PAM4 Gray mapping 레벨 테이블.
    인덱스 k=0..3 에 대해:
        0 -> 00 -> -3
        1 -> 01 -> -1
        2 -> 11 -> +1
        3 -> 10 -> +3
    평균 전력 1이 되도록 정규화.
    """
    levels = np.array([-3.0, -1.0, +1.0, +3.0], dtype=np.float64)
    # 평균 전력으로 정규화 (Es = 1)
    Es = np.mean(levels ** 2)
    levels_norm = levels / np.sqrt(Es)
    return levels_norm


PAM4_LEVELS = pam4_gray_levels()


def pam4_mod(k):
    """
    k: int array, shape (N,), 값은 {0,1,2,3}
    return: complex array, PAM4 심볼 (실수축 사용, imag=0)
    """
    s = PAM4_LEVELS[k]
    return s.astype(np.complex128)


def pam4_demod(z):
    """
    z: complex array, equalized output
    return: k_hat: int array, 각 샘플에 대해 가장 가까운 PAM4 레벨 인덱스
    """
    z_real = z.real
    diff = z_real[:, None] - PAM4_LEVELS[None, :]
    dist2 = diff ** 2
    k_hat = np.argmin(dist2, axis=1)
    return k_hat.astype(np.int64)


def pam4_bit_errors(k, k_hat):
    """
    k, k_hat: int array, 값은 {0,1,2,3}
    Gray mapping 기준으로 2bit/심볼의 비트 에러 수 계산.
    매핑:
        0 -> 00
        1 -> 01
        2 -> 11
        3 -> 10
    """
    sym2bits = np.array([
        [0, 0],  # 0
        [0, 1],  # 1
        [1, 1],  # 2
        [1, 0],  # 3
    ], dtype=np.int64)

    bits = sym2bits[k]       # (N, 2)
    bits_hat = sym2bits[k_hat]
    bit_err = np.not_equal(bits, bits_hat).sum()
    return bit_err, bits.size  # (에러 비트 수, 전체 비트 수)


# =========================
#  채널 / AWGN 유틸
# =========================

def get_mid_isi_channel():
    """
    Channel-b 5-tap mid-ISI 채널.
    Q13/Q14에서 사용한 계수를 그대로 사용.
    이미 정규화된 상태이지만, 안전하게 한 번 더 norm=1로 맞춰준다.
    """
    h = np.array(
        [0.04075696, 0.40756957, 0.81513915, 0.40756957, 0.04075696],
        dtype=np.float64,
    )
    h = h / np.linalg.norm(h)
    return h.astype(np.complex128)


def add_awgn(x, ebn0_db, bits_per_sym=2, rng=None):
    """
    x: complex baseband signal
    ebn0_db: Eb/N0 [dB]
    bits_per_sym: PAM4 = 2
    rng: np.random.Generator
    return: y = x + n (complex AWGN)
    """
    if rng is None:
        rng = np.random.default_rng()

    Es = np.mean(np.abs(x) ** 2)
    ebn0_lin = 10 ** (ebn0_db / 10.0)
    esn0_lin = ebn0_lin * bits_per_sym  # Es/N0 = Eb/N0 * (bits_per_sym)

    N0 = Es / esn0_lin
    sigma = np.sqrt(N0 / 2.0)

    n = sigma * (rng.normal(size=x.shape) + 1j * rng.normal(size=x.shape))
    return x + n


# =========================
#  FFE Equalizer (LMS / NLMS / LS)
# =========================

def ffe_train_and_eval_with_index(
    k_tx,
    h,
    ebn0_db,
    ffe_len=11,
    mu_ffe=0.001,
    train_frac=0.5,
    eq_mode="nlms",
    bits_per_sym=2,
    seed=1,
    dd_after_train=False,
    w_clip=10.0,
):
    """
    k_tx: int array, Tx PAM4 심볼 인덱스 (0..3), len = N

    eq_mode:
      - "nlms": NLMS 기반 적응형 FFE
      - "lms" : LMS 기반 적응형 FFE
      - "ls"  : noise-free 채널 출력에 대해 LS/MMSE 방식으로 FFE 계수 고정 학습
    """
    rng = np.random.default_rng(seed)

    N = len(k_tx)
    x_sym = pam4_mod(k_tx)  # complex PAM4 심볼

    # 채널 통과 (noise-free 기준 신호)
    x_chan = np.convolve(x_sym, h, mode="same")

    # AWGN 추가 (평가용 입력)
    y = add_awgn(x_chan, ebn0_db, bits_per_sym=bits_per_sym, rng=rng)

    L = ffe_len
    start = L - 1
    n_train = int(train_frac * N)
    if n_train <= start:
        n_train = start + 1

# =========================
    #  FFE 계수 학습
    # =========================
    if eq_mode == "ls":
        # LS/MMSE 스타일 학습: noise-free x_chan을 입력, x_sym(real)을 타겟으로 사용
        # 수치 안정성을 위해 실수 도메인에서 Ridge-regularized LS를 수행한다.
        # (추가) x_chan / x_sym 을 같은 스케일로 정규화해서 R, p 계산 시 overflow 방지.
        x_real = x_chan.real
        d_real = x_sym.real

        # 공통 스케일 (표준편차 기반)
        scale = np.std(x_real)
        if not np.isfinite(scale) or scale < 1e-12:
            scale = 1.0

        x_norm = x_real / scale
        d_norm = d_real / scale

        T = n_train - start
        U = np.zeros((T, L), dtype=np.float64)      # 실수 행렬
        d_vec = np.zeros(T, dtype=np.float64)       # 실수 타겟

        idx = 0
        for n in range(start, n_train):
            # 입력 벡터 u: 채널 출력 x_chan의 최근 L개(real) → 정규화된 x_norm 사용
            u = x_norm[n : n - L : -1] if n - L >= -1 else x_norm[max(0, n - L + 1) : n + 1][::-1]
            if len(u) < L:
                pad = np.zeros(L - len(u), dtype=np.float64)
                u = np.concatenate([u, pad])
            U[idx, :] = u
            d_vec[idx] = d_norm[n]
            idx += 1

        # (U^T U + λI)^{-1} U^T d  형태의 ridge-regularized LS 해
        # 수치 안정성을 위해 trace 기반 ridge + errstate 로 워닝 억제
        with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
            R = U.T @ U
            p = U.T @ d_vec

        trace_R = np.trace(R)
        if (not np.isfinite(trace_R)) or (trace_R <= 0):
            # 비정상적인 경우: 단위 임펄스 FFE로 fallback
            w = np.zeros(L, dtype=np.complex128)
            w[L // 2] = 1.0 + 0j
        else:
            ridge = 1e-3 * (trace_R / L) + 1e-9  # Q20c에서는 약간 강한 ridge 사용
            R_reg = R + ridge * np.eye(L, dtype=np.float64)
            w_real = np.linalg.solve(R_reg, p)
            w = w_real.astype(np.complex128)


    else:
        # NLMS/LMS 기반 적응형 FFE
        w = np.zeros(L, dtype=np.complex128)
        center = L // 2
        w[center] = 1.0 + 0j

        for n in range(start, N):
            u = y[n : n - L : -1] if n - L >= -1 else y[max(0, n - L + 1) : n + 1][::-1]
            if len(u) < L:
                pad = np.zeros(L - len(u), dtype=np.complex128)
                u = np.concatenate([u, pad])
            u = u.astype(np.complex128)

            z = np.vdot(w, u)

            if n < n_train:
                d = x_sym[n]
            else:
                if not dd_after_train:
                    continue
                k_hat_dd = pam4_demod(z.reshape(1,))
                d = pam4_mod(k_hat_dd)[0]

            e = d - z

            if eq_mode == "nlms":
                norm_u2 = np.vdot(u, u).real + 1e-8
                mu_eff = mu_ffe / norm_u2
            else:
                # "lms"
                mu_eff = mu_ffe

            w = w + mu_eff * e * np.conjugate(u)

            norm_w = np.linalg.norm(w)
            if norm_w > w_clip:
                w *= (w_clip / norm_w)

    # =========================
    #  학습된 w로 전체 시퀀스 equalize 후 BER 계산
    # =========================
    z_all = np.zeros(N, dtype=np.complex128)
    for n in range(start, N):
        u = y[n : n - L : -1] if n - L >= -1 else y[max(0, n - L + 1) : n + 1][::-1]
        if len(u) < L:
            pad = np.zeros(L - len(u), dtype=np.complex128)
            u = np.concatenate([u, pad])
        u = u.astype(np.complex128)
        z_all[n] = np.vdot(w, u)

    # BER 계산 (앞쪽 start 심볼은 버리고 비교)
    k_tx_eff = k_tx[start:]
    k_hat_eff = pam4_demod(z_all[start:])

    bit_err, bit_total = pam4_bit_errors(k_tx_eff, k_hat_eff)
    ber = bit_err / bit_total
    return ber


# =========================
#  메인 루프
# =========================

def parse_ebn0_list(s):
    return [float(v) for v in s.split(",") if v.strip() != ""]


def main():
    parser = argparse.ArgumentParser(
        description="CoPBit Q20c – PAM4 mid-ISI (Channel-b) + FFE-only baseline (LMS / NLMS / LS) v0",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--n_sym", type=int, default=200000,
                        help="Number of PAM4 symbols")
    parser.add_argument("--ebn0_list", type=str, default="8,10,12,14,16,18,20",
                        help='Comma-separated Eb/N0 list in dB, e.g. "8,10,12,14"')
    parser.add_argument("--ffe_len", type=int, default=11,
                        help="FFE length (number of taps)")
    parser.add_argument("--mu_ffe", type=float, default=0.001,
                        help="LMS / NLMS step size for FFE (lms/nlms 모드에서 사용)")
    parser.add_argument("--train_frac", type=float, default=0.5,
                        help="Training fraction (0~1)")
    parser.add_argument("--eq_mode", type=str, choices=["lms", "nlms", "ls"], default="nlms",
                        help="Equalizer adaptation mode (lms/nlms: adaptive, ls: noise-free LS training)")
    parser.add_argument("--dd_after_train", action="store_true",
                        help="Enable decision-directed updates after training (lms/nlms 모드에서만 의미 있음)")
    parser.add_argument("--w_clip", type=float, default=10.0,
                        help="Weight norm clipping threshold (lms/nlms 모드에서만 사용)")
    parser.add_argument("--seed", type=int, default=1,
                        help="Random seed")
    args = parser.parse_args()

    n_sym = args.n_sym
    ebn0_list = parse_ebn0_list(args.ebn0_list)
    ffe_len = args.ffe_len
    mu_ffe = args.mu_ffe
    train_frac = args.train_frac
    eq_mode = args.eq_mode
    dd_after_train = args.dd_after_train
    w_clip = args.w_clip
    seed = args.seed

    print("=== CoPBit Q20c – PAM4 mid-ISI (Channel-b) + FFE-only baseline (LMS / NLMS / LS) v0 ===")
    print(f"[Param] n_sym       = {n_sym}")
    print(f"[Param] Eb/N0_list  = {ebn0_list}")
    print(f"[Param] ffe_len     = {ffe_len}")
    print(f"[Param] train_frac  = {train_frac}")
    print(f"[Param] mu_ffe      = {mu_ffe}")
    print(f"[Param] eq_mode     = {eq_mode}")
    print(f"[Param] dd_after_tr = {dd_after_train}")
    print(f"[Param] w_clip      = {w_clip}")
    print(f"[Param] seed        = {seed}")
    print()

    h = get_mid_isi_channel()
    print(f"[Chan ] h_midISI (norm) = {np.round(h.real, 8)}")
    print("[Info ] FFE-only baseline (PAM4, single-lane, mid-ISI + AWGN)")
    print()

    # Tx 심볼 인덱스 고정 (모든 Eb/N0에서 동일 시퀀스 사용)
    rng_tx = np.random.default_rng(seed)
    k_tx = rng_tx.integers(low=0, high=4, size=n_sym, dtype=np.int64)

    print("===============================================================")
    print(" Eb/N0_dB |  BER_PAM4_FFE  ")
    print("---------------------------------------------------------------")

    for ebn0_db in ebn0_list:
        ber = ffe_train_and_eval_with_index(
            k_tx=k_tx,
            h=h,
            ebn0_db=ebn0_db,
            ffe_len=ffe_len,
            mu_ffe=mu_ffe,
            train_frac=train_frac,
            eq_mode=eq_mode,
            bits_per_sym=2,
            seed=seed + int(ebn0_db * 10),  # Eb/N0별로 noise seed 살짝 변경
            dd_after_train=dd_after_train,
            w_clip=w_clip,
        )
        print(f"{ebn0_db:10.1f} | {ber:14.9f}")

    print("---------------------------------------------------------------")


if __name__ == "__main__":
    main()