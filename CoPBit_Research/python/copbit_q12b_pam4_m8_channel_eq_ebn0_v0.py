#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CoPBit Q12b – PAM4 vs CoPBit-M8 (8-PSK)
         over channel a/b/c + AWGN + FFE-EQ (Eb/N0 basis) v0.1

목적:
- Q12(v0.1)의 "채널 a/b/c + AWGN only" 베이스라인 위에,
  간단한 선형 FFE(equalizer)를 추가한 버전을 만든다.
- PAM4(2bit/심볼) vs CoPBit-M8(3bit/심볼, 8-PSK)에 대해
  각 채널 a/b/c에서
    - no-EQ BER
    - FFE-EQ 적용 BER
  을 Eb/N0 공정 기준으로 비교.

특징:
- 심볼 레이트 기준 5-tap 채널 a/b/c 사용 (ILC3/ILC4 계열과 동일).
- FFE는 심볼 도메인에서 L-tap (기본 7tap), 중앙 기준(L//2) 구조.
- FFE 계수는 노이즈 없는 채널 출력(y_ch_clean) + 원 심볼(x)을 이용해
  최소제곱(LS) 방식으로 한 번만 추정하고,
  같은 채널/스킴/조건에서 모든 Eb/N0에 공통 적용.
"""

import numpy as np
import argparse


# -----------------------------
# 채널 계수 정의 (a/b/c, 5-tap)
# -----------------------------
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
    y_real = np.real(y)

    diff = np.abs(y_real[:, None] - PAM4_LEVELS_NORM[None, :])
    idx_hat = np.argmin(diff, axis=1)  # shape (N_sym,)

    bits_hat = PAM4_BITS_TABLE[idx_hat]  # (N_sym, 2)
    return bits_hat.reshape(-1)


# -----------------------------
# M-PSK 변복조 (CoPBit-M8용)
# -----------------------------
def bits_to_int(bits, k):
    bits = np.asarray(bits, dtype=int)
    assert bits.size % k == 0
    b = bits.reshape(-1, k)
    weights = 1 << np.arange(k - 1, -1, -1, dtype=int)
    return (b * weights).sum(axis=1)


def int_to_bits(vals, k):
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
    theta = np.angle(y)
    theta = np.mod(theta, 2.0 * np.pi)

    step = 2.0 * np.pi / float(M)
    idx_hat = np.round(theta / step).astype(int) % M

    bits_hat = int_to_bits(idx_hat, k)
    return bits_hat


# -----------------------------
# 채널 통과 + FFE 설계/적용
# -----------------------------
def apply_channel(x, h):
    """
    x: (N_sym,) 실수/복소 심볼
    h: (L,)    채널 탭
    return: np.convolve(x, h, mode='same')
    """
    return np.convolve(x, h.astype(np.complex128), mode="same")


def design_ffe(y_tr, d_tr, L):
    """
    간단 LS 기반 심볼 레이트 FFE 설계.

    y_tr : (N_tr,) 채널 출력 (노이즈 없는 기준)
    d_tr : (N_tr,) 타겟 심볼 (PAM4 또는 M8 심볼)
    L    : FFE tap 수 (홀수 추천, 중앙 기준)

    return: (L,) FFE 계수 w (복소 가능)
    """
    y_tr = np.asarray(y_tr, dtype=np.complex128)
    d_tr = np.asarray(d_tr, dtype=np.complex128)
    N = y_tr.size
    assert d_tr.size == N
    assert L % 2 == 1, "FFE length L should be odd (center tap 존재)."

    half = L // 2
    # 가장자리 half 심볼은 버리고 중앙부만 사용
    N_eff = N - 2 * half
    if N_eff <= 0:
        raise ValueError("Training length too short for given FFE length.")

    X = np.zeros((N_eff, L), dtype=np.complex128)
    d_vec = np.zeros(N_eff, dtype=np.complex128)

    idx = 0
    for n in range(half, N - half):
        # y[n - half : n + half] → 길이 L
        X[idx, :] = y_tr[n - half : n + half + 1]
        d_vec[idx] = d_tr[n]
        idx += 1

    # 최소제곱 해: w = (X^H X)^(-1) X^H d
    w, *_ = np.linalg.lstsq(X, d_vec, rcond=None)
    return w  # shape (L,)


def apply_ffe(y, w):
    """
    y: (N,) 채널+노이즈 출력
    w: (L,) FFE 계수
    return: (N,) equalized 시퀀스 (same length)
    """
    return np.convolve(y, w, mode="same")


# -----------------------------
# 메인 루틴
# -----------------------------
def main():
    parser = argparse.ArgumentParser(
        description="CoPBit Q12b – PAM4 vs CoPBit-M8(8-PSK) over channel a/b/c + AWGN + FFE-EQ (Eb/N0 basis) v0.1"
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
        "--ffe_len",
        type=int,
        default=7,
        help="FFE tap 수 (홀수, default: 7)",
    )
    parser.add_argument(
        "--train_frac",
        type=float,
        default=0.2,
        help="FFE 학습에 사용할 training 심볼 비율 (0~1, default: 0.2)",
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
    L_ffe = args.ffe_len
    train_frac = args.train_frac
    rng = np.random.default_rng(args.seed)

    print("=== CoPBit Q12b – PAM4 vs CoPBit-M8 Channel+AWGN+FFE (Eb/N0 basis) v0.1 ===")
    print(f"[Param] n_sym          = {n_sym}")
    print(f"[Param] Eb/N0_list(dB) = {ebn0_list}")
    print(f"[Param] channels       = {ch_list}")
    print(f"[Param] ffe_len        = {L_ffe}")
    print(f"[Param] train_frac     = {train_frac}")
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

        # -----------------------
        # 1) PAM4용 비트/심볼/채널 출력/FFE 설계
        # -----------------------
        n_bits_pam4 = n_sym * bits_per_pam4
        bits_pam4 = rng.integers(0, 2, size=n_bits_pam4, dtype=int)
        x4 = pam4_mod(bits_pam4)  # (n_sym,) 실수

        x4_ch_clean = apply_channel(x4, h)  # 노이즈 없는 채널 출력

        # FFE 학습용 subset
        n_tr = int(n_sym * train_frac)
        if n_tr < L_ffe * 2:
            n_tr = L_ffe * 2 + 10  # 최소 길이 보정
            n_tr = min(n_tr, n_sym)

        y4_tr = x4_ch_clean[:n_tr]
        d4_tr = x4[:n_tr]  # 타겟은 원래 심볼

        w_ffe_pam4 = design_ffe(y4_tr, d4_tr, L_ffe)

        # -----------------------
        # 2) M8(=CoPBit-M8)용 비트/심볼/채널 출력/FFE 설계
        # -----------------------
        n_bits_m8 = n_sym * bits_per_m8
        bits_m8 = rng.integers(0, 2, size=n_bits_m8, dtype=int)
        x8 = mpsk_mod(bits_m8, M=8)  # unit circle 8-PSK

        x8_ch_clean = apply_channel(x8, h)

        n_tr_m8 = int(n_sym * train_frac)
        if n_tr_m8 < L_ffe * 2:
            n_tr_m8 = L_ffe * 2 + 10
            n_tr_m8 = min(n_tr_m8, n_sym)

        y8_tr = x8_ch_clean[:n_tr_m8]
        d8_tr = x8[:n_tr_m8]

        w_ffe_m8 = design_ffe(y8_tr, d8_tr, L_ffe)

        # -----------------------
        # 3) Eb/N0 sweep: no-EQ vs FFE-EQ BER
        # -----------------------
        print(" EbN0_dB | PAM4_noEQ  | PAM4_FFE   | M8_noEQ    | M8_FFE")
        print("-------------------------------------------------------------")

        for ebn0_db in ebn0_list:
            # PAM4: channel + noise
            y4_noisy = awgn_from_ebn0(x4_ch_clean, ebn0_db, bits_per_pam4, rng)

            # (a) no-EQ
            bits4_hat_noeq = pam4_demod(y4_noisy)
            ber_pam4_noeq = np.mean(bits4_hat_noeq != bits_pam4)

            # (b) FFE-EQ
            y4_eq = apply_ffe(y4_noisy, w_ffe_pam4)
            bits4_hat_ffe = pam4_demod(y4_eq)
            ber_pam4_ffe = np.mean(bits4_hat_ffe != bits_pam4)

            # M8: channel + noise
            y8_noisy = awgn_from_ebn0(x8_ch_clean, ebn0_db, bits_per_m8, rng)

            # (a) no-EQ
            bits8_hat_noeq = mpsk_demod(y8_noisy, M=8)
            ber_m8_noeq = np.mean(bits8_hat_noeq != bits_m8)

            # (b) FFE-EQ
            y8_eq = apply_ffe(y8_noisy, w_ffe_m8)
            bits8_hat_ffe = mpsk_demod(y8_eq, M=8)
            ber_m8_ffe = np.mean(bits8_hat_ffe != bits_m8)

            print(
                f"{ebn0_db:8.1f} | "
                f"{ber_pam4_noeq:10.3e} | {ber_pam4_ffe:10.3e} | "
                f"{ber_m8_noeq:10.3e} | {ber_m8_ffe:10.3e}"
            )

        print("-------------------------------------------------------------")
        print("")

    print("※ 주석")
    print(" - PAM4: 실수 4레벨 [-3,-1,1,3]/sqrt(5) Gray mapping + 5-tap 채널 a/b/c + AWGN.")
    print(" - CoPBit-M8: unit circle 8-PSK (3bit/심볼) + 동일 채널 + AWGN.")
    print(" - Eb/N0 기반 bit-fair 비교 (Es/N0 = Eb/N0 * k).")
    print(" - 이 스크립트는 채널 a/b/c 위에서")
    print("     · no-EQ BER")
    print("     · LS 기반 심볼 레이트 FFE 적용 BER")
    print("   을 한 번에 보는 Q12 확장 버전(v12b)이다.")
    print(" - FFE 길이/학습 비율(ffe_len/train_frac)을 조정하면서")
    print("   채널별로 어느 정도까지 ISI를 줄일 수 있는지 감을 잡는 용도.")


if __name__ == "__main__":
    main()