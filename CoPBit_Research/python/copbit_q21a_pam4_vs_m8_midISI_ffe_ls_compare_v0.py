#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CoPBit Q21a – PAM4 vs M8 mid-ISI (Channel-b) + FFE-only baseline (LS) compare v0

단일-lane PAM4, 단일-lane M8(8-PSK)을 같은 mid-ISI(Channel-b 5-tap) + AWGN 채널에 통과시키고,
FFE-only(LS 고정 계수)로만 ISI를 보상했을 때의 BER vs Eb/N0 기준선을
한 스크립트에서 동시에 비교하는 용도.

- 채널: mid-ISI (Channel-b 5-tap, 정규화) – Q13/Q14/Q20c/Q20d와 동일 계수
- 변조:
    · PAM4 (2 bit/sym, 1D 레벨 [-3, -1, +1, +3])
    · M8   (8-PSK, 3 bit/sym, Gray-ish mapping)
- EQ  : 공통 FFE-only (LS 고정 계수, noise-free 채널 출력 기준 학습)
- 학습: 앞쪽 train_frac 구간에서 noise-free 채널 출력(x_chan)을 입력으로 쓰고,
        Tx 심볼을 타겟으로 LS 학습 후, 같은 계수로 AWGN 채널 출력(y)을 equalize.

Q20c (PAM4 mid-ISI FFE-only LS)와 Q20d (M8 mid-ISI FFE-only LS)를
하나로 합쳐서 돌리는 “비교 스크립트”라고 보면 된다.
"""

import argparse
import numpy as np


# =========================
#  PAM4 Mod/Demod
# =========================

def pam4_levels():
    """
    PAM4 심볼 레벨 (일반적인 [-3, -1, +1, +3] 매핑).
    Es는 스케일링 없이 이 값들 기준.
    """
    return np.array([-3.0, -1.0, +1.0, +3.0], dtype=np.float64)


PAM4_LEVELS = pam4_levels()

# Gray 매핑 비트 패턴 (k=0..3)
PAM4_BITS = np.array([
    [0, 0],  # -3
    [0, 1],  # -1
    [1, 1],  # +1
    [1, 0],  # +3
], dtype=np.int64)


def pam4_mod(k):
    """
    k: int array, {0,1,2,3}
    return: float array, PAM4 symbol levels
    """
    s = PAM4_LEVELS[k]
    return s.astype(np.float64)


def pam4_demod(z):
    """
    z: complex or real array, equalized output
    return: k_hat in {0..3}, nearest neighbor demod
    """
    z_real = np.real(z).astype(np.float64)
    z_real = z_real[:, None]  # (N,1)
    lv = PAM4_LEVELS[None, :]  # (1,4)
    dist2 = (z_real - lv) ** 2
    k_hat = np.argmin(dist2, axis=1)
    return k_hat.astype(np.int64)


def pam4_bit_errors(k, k_hat):
    bits = PAM4_BITS[k]
    bits_hat = PAM4_BITS[k_hat]
    bit_err = np.not_equal(bits, bits_hat).sum()
    return bit_err, bits.size  # (에러 비트 수, 전체 비트 수)


# =========================
#  M8 Mod/Demod (8-PSK)
# =========================

def m8_constellation():
    """
    8-PSK unit circle constellation.
    k = 0..7, exp(j*2πk/8).
    """
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
    diff = z[:, None] - M8_POINTS[None, :]
    dist2 = np.abs(diff) ** 2
    k_hat = np.argmin(dist2, axis=1)
    return k_hat.astype(np.int64)


def m8_bit_errors(k, k_hat):
    bits = M8_BITS[k]
    bits_hat = M8_BITS[k_hat]
    bit_err = np.not_equal(bits, bits_hat).sum()
    return bit_err, bits.size


# =========================
#  채널 / AWGN 유틸
# =========================

def get_mid_isi_channel():
    """
    Channel-b 5-tap mid-ISI 채널.
    Q13/Q14/Q20c/Q20d와 동일 계수를 사용.
    norm(h)=1 로 정규화.
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
    bits_per_sym: PAM4=2, M8=3
    rng: np.random.Generator
    return: y = x + n (complex AWGN)
    """
    if rng is None:
        rng = np.random.default_rng()

    x = x.astype(np.complex128)
    Es = np.mean(np.abs(x) ** 2)
    ebn0_lin = 10.0 ** (ebn0_db / 10.0)
    esn0_lin = ebn0_lin * bits_per_sym  # Es/N0 = Eb/N0 * (bits_per_sym)

    N0 = Es / esn0_lin
    sigma = np.sqrt(N0 / 2.0)

    n = sigma * (rng.normal(size=x.shape) + 1j * rng.normal(size=x.shape))
    return x + n


# =========================
#  Generic FFE Equalizer (LS 고정)
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
    공통 FFE LS 학습 + BER 평가 함수.

    k_tx       : int array, Tx 심볼 인덱스
    mod_fn     : k -> complex/real 심볼 (PAM4 or M8)
    demod_fn   : z -> k_hat
    bit_err_fn : (k, k_hat) -> (bit_err, bit_total)
    h          : mid-ISI 채널 계수 (complex 1D)
    ebn0_db    : Eb/N0 [dB]
    bits_per_sym: 변조별 비트 수 (PAM4=2, M8=3)
    """
    rng = np.random.default_rng(seed)

    N = len(k_tx)
    s = mod_fn(k_tx)  # Tx 심볼 (real or complex)
    x_sym = s.astype(np.complex128)

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

    # 공통 스케일 (복소 norm 기준)
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
            u = x_norm[n : n - L : -1]  # 뒤에서 앞으로
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
        R = U.conj().T @ U   # (L,L)
        p = U.conj().T @ d_vec  # (L,)

    trace_R = np.real(np.trace(R))
    if (not np.isfinite(trace_R)) or (trace_R <= 0):
        # 비정상적인 경우: 단위 임펄스 FFE로 fallback
        w = np.zeros(L, dtype=np.complex128)
        w[L // 2] = 1.0 + 0j
    else:
        ridge = 1e-3 * (trace_R / L) + 1e-9  # Q20 계열과 비슷한 수준의 ridge
        R_reg = R + ridge * np.eye(L, dtype=np.complex128)
        w = np.linalg.solve(R_reg, p)

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
    k_hat_eff = demod_fn(z_all[start:])

    bit_err, bit_total = bit_err_fn(k_tx_eff, k_hat_eff)
    ber = bit_err / bit_total
    return ber


# =========================
#  메인 루프
# =========================

def parse_ebn0_list(s):
    return [float(v) for v in s.split(",") if v.strip() != ""]


def main():
    parser = argparse.ArgumentParser(
        description="CoPBit Q21a – PAM4 vs M8 mid-ISI (Channel-b) + FFE-only LS baseline compare v0",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--n_sym", type=int, default=200000,
                        help="Number of symbols")
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

    print("=== CoPBit Q21a – PAM4 vs M8 mid-ISI (Channel-b) + FFE-only LS baseline compare v0 ===")
    print(f"[Param] n_sym       = {n_sym}")
    print(f"[Param] Eb/N0_list  = {ebn0_list}")
    print(f"[Param] ffe_len     = {ffe_len}")
    print(f"[Param] train_frac  = {train_frac}")
    print(f"[Param] seed        = {seed}")
    print()

    h = get_mid_isi_channel()
    print(f"[Chan ] h_midISI (norm) = {np.round(h.real, 8)}")
    print("[Info ] FFE-only baseline (PAM4 vs M8, single-lane, mid-ISI + AWGN, LS 고정 계수)")
    print()

    # 공통 Tx 심볼 인덱스 시퀀스 (PAM4/M8 각각 별도)
    rng = np.random.default_rng(seed)
    k_tx_pam4 = rng.integers(low=0, high=4, size=n_sym, dtype=np.int64)
    k_tx_m8   = rng.integers(low=0, high=8, size=n_sym, dtype=np.int64)

    print("==============================================================")
    print(" Eb/N0_dB |  BER_PAM4_FFE      |  BER_M8_FFE        ")
    print("--------------------------------------------------------------")

    for ebn0_db in ebn0_list:
        # PAM4
        ber_pam4 = ffe_train_and_eval_ls(
            k_tx=k_tx_pam4,
            mod_fn=pam4_mod,
            demod_fn=pam4_demod,
            bit_err_fn=pam4_bit_errors,
            h=h,
            ebn0_db=ebn0_db,
            ffe_len=ffe_len,
            train_frac=train_frac,
            bits_per_sym=2,
            seed=seed + int(ebn0_db * 10) + 1000,  # 노이즈 시드 분리
        )
        # M8
        ber_m8 = ffe_train_and_eval_ls(
            k_tx=k_tx_m8,
            mod_fn=m8_mod,
            demod_fn=m8_demod,
            bit_err_fn=m8_bit_errors,
            h=h,
            ebn0_db=ebn0_db,
            ffe_len=ffe_len,
            train_frac=train_frac,
            bits_per_sym=3,
            seed=seed + int(ebn0_db * 10) + 2000,
        )

        print(f"{ebn0_db:10.1f} | {ber_pam4:16.9f} | {ber_m8:16.9f}")

    print("--------------------------------------------------------------")


if __name__ == "__main__":
    main()