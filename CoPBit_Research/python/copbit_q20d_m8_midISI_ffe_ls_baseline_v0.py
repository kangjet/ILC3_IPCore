#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CoPBit Q20d – M8 mid-ISI (Channel-b) + FFE-only baseline (LS) v0

단일-lane M8(8-PSK)을 mid-ISI(Channel-b 5-tap) + AWGN 채널에 통과시키고,
FFE-only(equalizer)로만 ISI를 보상했을 때의 BER vs Eb/N0 기준선을 만드는 스크립트.

- 채널: mid-ISI (Channel-b 5-tap, 정규화)
- 변조: M8 (8-PSK, 3 bit/symbol, Gray-ish mapping)
- EQ  : FFE-only (LS 고정 계수)
- 학습: 앞쪽 train_frac 구간에서 noise-free 채널 출력(x_chan)을 이용해 LS 학습

이 스크립트를 Q20c(PAM4)와 1:1로 비교해서,
mid-ISI + FFE-only 환경에서 "순수 M8"의 baseline을 잡는 용도로 사용.
추후 CoPBit(p_ref + Kuramoto) 적용 시, 여기서부터 gain을 보는 구조로 확장 예정.
"""

import argparse
import numpy as np

# =========================
#  M8 Mod/Demod (8-PSK)
# =========================

def m8_constellation():
    """
    8-PSK unit circle constellation.
    k = 0..7 에 대해 exp(j*2πk/8).

    별도의 스케일링 없이 평균 전력 Es ≈ 1.
    """
    k = np.arange(8, dtype=np.float64)
    phases = 2.0 * np.pi * k / 8.0
    points = np.exp(1j * phases)
    return points.astype(np.complex128)


M8_POINTS = m8_constellation()

# Gray-ish bit mapping (각 index k에 해당하는 3-bit 패턴)
# 원형 인접 심볼 간 Hamming 거리 1에 가깝도록 구성.
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
    """
    k: int array, shape (N,), 값은 {0..7}
    return: complex array, M8(8-PSK) 심볼
    """
    s = M8_POINTS[k]
    return s.astype(np.complex128)


def m8_demod(z):
    """
    z: complex array, equalized output
    return: k_hat: int array, 각 샘플에 대해 가장 가까운 M8 포인트 인덱스
    """
    z = z.astype(np.complex128)
    # (N,1) vs (1,8) broadcasting
    diff = z[:, None] - M8_POINTS[None, :]
    dist2 = np.abs(diff) ** 2
    k_hat = np.argmin(dist2, axis=1)
    return k_hat.astype(np.int64)


def m8_bit_errors(k, k_hat):
    """
    k, k_hat: int array, 값은 {0..7}
    3bit/심볼 기준으로 비트 에러 수 계산.
    """
    bits = M8_BITS[k]       # (N, 3)
    bits_hat = M8_BITS[k_hat]
    bit_err = np.not_equal(bits, bits_hat).sum()
    return bit_err, bits.size  # (에러 비트 수, 전체 비트 수)


# =========================
#  채널 / AWGN 유틸
# =========================

def get_mid_isi_channel():
    """
    Channel-b 5-tap mid-ISI 채널.
    Q13/Q14/Q20c에서 사용한 계수를 그대로 사용.
    norm(h)=1 이 되도록 정규화.
    """
    h = np.array(
        [0.04075696, 0.40756957, 0.81513915, 0.40756957, 0.04075696],
        dtype=np.float64,
    )
    h = h / np.linalg.norm(h)
    return h.astype(np.complex128)


def add_awgn(x, ebn0_db, bits_per_sym=3, rng=None):
    """
    x: complex baseband signal
    ebn0_db: Eb/N0 [dB]
    bits_per_sym: M8 = 3
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
#  FFE Equalizer (LS 고정)
# =========================

def ffe_train_and_eval_m8_ls(
    k_tx,
    h,
    ebn0_db,
    ffe_len=11,
    train_frac=0.5,
    bits_per_sym=3,
    seed=1,
):
    """
    k_tx: int array, Tx M8 심볼 인덱스 (0..7), len = N

    eq_mode = "ls" 전용:
      - noise-free 채널 출력 x_chan을 입력, Tx 심볼 x_sym을 타겟으로 사용.
      - 복소 LS + ridge regularization 으로 FFE 계수 고정.
      - 이후 AWGN이 추가된 y에 같은 w를 적용해 BER 계산.
    """
    rng = np.random.default_rng(seed)

    N = len(k_tx)
    x_sym = m8_mod(k_tx)  # complex M8 심볼

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
    #  FFE 계수 LS 학습 (noise-free x_chan 기준)
    # =========================
    x_nf = x_chan  # noise-free 채널 출력
    d_sym = x_sym  # 타겟 심볼

    # 공통 스케일 (복소 -> 절대값 기반)
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
        # 입력 벡터 u: 채널 출력 x_norm의 최근 L개 (복소)
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

    # (U^H U + λI)^{-1} U^H d  형태의 ridge-regularized LS 해
    with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
        R = U.conj().T @ U   # (L,L) Hermitian
        p = U.conj().T @ d_vec  # (L,)

    trace_R = np.real(np.trace(R))
    if (not np.isfinite(trace_R)) or (trace_R <= 0):
        # 비정상적인 경우: 단위 임펄스 FFE로 fallback
        w = np.zeros(L, dtype=np.complex128)
        w[L // 2] = 1.0 + 0j
    else:
        ridge = 1e-3 * (trace_R / L) + 1e-9  # Q20d에서는 약간 강한 ridge 사용
        R_reg = R + ridge * np.eye(L, dtype=np.complex128)
        w = np.linalg.solve(R_reg, p)  # (L,)

    # =========================
    #  학습된 w로 전체 시퀀스 equalize 후 BER 계산
    # =========================
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
        z_all[n] = np.vdot(w, u)  # w^H u

    # BER 계산 (앞쪽 start 심볼은 버리고 비교)
    k_tx_eff = k_tx[start:]
    k_hat_eff = m8_demod(z_all[start:])

    bit_err, bit_total = m8_bit_errors(k_tx_eff, k_hat_eff)
    ber = bit_err / bit_total
    return ber


# =========================
#  메인 루프
# =========================

def parse_ebn0_list(s):
    return [float(v) for v in s.split(",") if v.strip() != ""]


def main():
    parser = argparse.ArgumentParser(
        description="CoPBit Q20d – M8 mid-ISI (Channel-b) + FFE-only baseline (LS) v0",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--n_sym", type=int, default=200000,
                        help="Number of M8 symbols")
    parser.add_argument("--ebn0_list", type=str, default="8,10,12,14,16,18,20",
                        help='Comma-separated Eb/N0 list in dB, e.g. "8,10,12,14"')
    parser.add_argument("--ffe_len", type=int, default=11,
                        help="FFE length (number of taps)")
    parser.add_argument("--train_frac", type=float, default=0.5,
                        help="Training fraction (0~1)")
    parser.add_argument("--seed", type=int, default=1,
                        help="Random seed")
    args = parser.parse_args()

    n_sym = args.n_sym
    ebn0_list = parse_ebn0_list(args.ebn0_list)
    ffe_len = args.ffe_len
    train_frac = args.train_frac
    seed = args.seed

    print("=== CoPBit Q20d – M8 mid-ISI (Channel-b) + FFE-only baseline (LS) v0 ===")
    print(f"[Param] n_sym       = {n_sym}")
    print(f"[Param] Eb/N0_list  = {ebn0_list}")
    print(f"[Param] ffe_len     = {ffe_len}")
    print(f"[Param] train_frac  = {train_frac}")
    print(f"[Param] seed        = {seed}")
    print()

    h = get_mid_isi_channel()
    print(f"[Chan ] h_midISI (norm) = {np.round(h.real, 8)}")
    print("[Info ] FFE-only baseline (M8, single-lane, mid-ISI + AWGN)")
    print()

    # Tx 심볼 인덱스 고정 (모든 Eb/N0에서 동일 시퀀스 사용)
    rng_tx = np.random.default_rng(seed)
    k_tx = rng_tx.integers(low=0, high=8, size=n_sym, dtype=np.int64)

    print("===============================================================")
    print(" Eb/N0_dB |  BER_M8_FFE     ")
    print("---------------------------------------------------------------")

    for ebn0_db in ebn0_list:
        ber = ffe_train_and_eval_m8_ls(
            k_tx=k_tx,
            h=h,
            ebn0_db=ebn0_db,
            ffe_len=ffe_len,
            train_frac=train_frac,
            bits_per_sym=3,
            seed=seed + int(ebn0_db * 10),  # Eb/N0별로 noise seed 살짝 변경
        )
        print(f"{ebn0_db:10.1f} | {ber:14.9f}")

    print("---------------------------------------------------------------")


if __name__ == "__main__":
    main()