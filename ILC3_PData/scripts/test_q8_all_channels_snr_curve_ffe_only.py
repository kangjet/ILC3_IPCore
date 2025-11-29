#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Q8: Channels a/b/c – PAM4 vs ILC3_0c_gp, FFE-only SNR curves
    h_a = [0.10  0.40  1.00  0.40  0.10]
    h_b = [0.05  0.50  1.00  0.50  0.05]
    h_c = [0.075 0.45  1.00  0.45  0.075]

- PAM4:       4-PAM levels [-3, -1, +1, +3]
- ILC3_0c_gp: 3-PAM levels [-1, 0, +1]  (guard phase는 여기서 진폭 성능만 비교)

SNR_dB sweep에서 FFE만 고정 조건으로
각 채널마다 PAM4+FFE, ILC3_0c_gp+FFE 성능을 비교하고 CSV로 저장.
"""

import numpy as np
from pathlib import Path
from datetime import datetime


# ---------------------------
# 채널 / 코드북 / 파라미터
# ---------------------------

H_A = np.array([0.10, 0.40, 1.00, 0.40, 0.10], dtype=float)
H_B = np.array([0.05, 0.50, 1.00, 0.50, 0.05], dtype=float)
H_C = np.array([0.075, 0.45, 1.00, 0.45, 0.075], dtype=float)

CHANNELS = [
    ("a", H_A),
    ("b", H_B),
    ("c", H_C),
]

PAM4_LEVELS = np.array([-3.0, -1.0, +1.0, +3.0], dtype=float)
ILC3_LEVELS = np.array([-1.0, 0.0, +1.0], dtype=float)

N_SYM = 200_000
SNR_LIST = [4.0, 6.0, 8.0, 10.0, 12.0, 14.0]

FFE_LEN = 11
FFE_RIDGE = 0.001


# ---------------------------
# 유틸 함수들
# ---------------------------

def design_ffe_mmse(h: np.ndarray, length: int, ridge: float = 0.0) -> np.ndarray:
    """
    T-spaced MMSE FFE 설계 (실수 채널 기준)
    h: 채널 임펄스 응답 (1D)
    length: FFE tap 길이 (홀수 권장)
    ridge: ridge regularization (λI)
    """
    h = np.asarray(h, dtype=float)
    L = length
    conv_len = len(h) + L - 1

    A = np.zeros((conv_len, L), dtype=float)
    for i in range(conv_len):
        for k in range(L):
            j = i - k
            if 0 <= j < len(h):
                A[i, k] = h[j]

    d = np.zeros(conv_len, dtype=float)
    center_idx = conv_len // 2
    d[center_idx] = 1.0

    ATA = A.T @ A
    if ridge > 0:
        ATA += ridge * np.eye(L)
    ATd = A.T @ d
    w = np.linalg.solve(ATA, ATd)
    return w


def add_awgn(x: np.ndarray, snr_db: float, rng: np.random.Generator) -> np.ndarray:
    """
    Es/N0 기반 실수 AWGN 추가.
    각 스킴별 Es(=E[x^2])를 이용해 같은 SNR_dB 조건 보장.
    """
    x = np.asarray(x, dtype=float)
    Es = np.mean(x ** 2)
    snr_lin = 10.0 ** (snr_db / 10.0)
    noise_var = Es / snr_lin
    noise = rng.normal(scale=np.sqrt(noise_var), size=x.shape)
    return x + noise


def pam4_hard_decision(y: np.ndarray):
    """PAM4: 최인접 레벨 slicing."""
    y = np.asarray(y, dtype=float)
    idx = np.argmin(np.abs(y[:, None] - PAM4_LEVELS[None, :]), axis=1)
    return idx


def ilc3_hard_decision(y: np.ndarray):
    """ILC3_0c_gp: 진폭 기준 3-PAM slicing."""
    y = np.asarray(y, dtype=float)
    idx = np.argmin(np.abs(y[:, None] - ILC3_LEVELS[None, :]), axis=1)
    return idx


def pam4_generate_symbols(n: int, rng: np.random.Generator):
    idx = rng.integers(low=0, high=4, size=n)
    x = PAM4_LEVELS[idx]
    return idx, x


def ilc3_generate_symbols(n: int, rng: np.random.Generator):
    idx = rng.integers(low=0, high=3, size=n)
    x = ILC3_LEVELS[idx]
    return idx, x


def apply_channel_and_ffe(x: np.ndarray, h: np.ndarray, w_ffe: np.ndarray) -> np.ndarray:
    """
    x -> 채널 h -> FFE w_ffe 까지 통과한 후의 시퀀스 (same 길이로 잘라줌)
    """
    y_ch = np.convolve(x, h, mode="same")
    y_eq = np.convolve(y_ch, w_ffe, mode="same")
    return y_eq


def run_pam4_with_ffe_only(h: np.ndarray,
                            w_ffe: np.ndarray,
                            snr_db: float,
                            n_sym: int,
                            rng: np.random.Generator):
    gt_idx, x = pam4_generate_symbols(n_sym, rng)
    y_eq_no_noise = apply_channel_and_ffe(x, h, w_ffe)
    y_eq = add_awgn(y_eq_no_noise, snr_db, rng)
    dec_idx = pam4_hard_decision(y_eq)
    acc = np.mean(dec_idx == gt_idx)
    ber = 1.0 - acc
    return acc, ber


def run_ilc3_with_ffe_only(h: np.ndarray,
                            w_ffe: np.ndarray,
                            snr_db: float,
                            n_sym: int,
                            rng: np.random.Generator):
    gt_idx, x = ilc3_generate_symbols(n_sym, rng)
    y_eq_no_noise = apply_channel_and_ffe(x, h, w_ffe)
    y_eq = add_awgn(y_eq_no_noise, snr_db, rng)
    dec_idx = ilc3_hard_decision(y_eq)
    acc = np.mean(dec_idx == gt_idx)
    ber = 1.0 - acc
    return acc, ber


# ---------------------------
# 메인 루프
# ---------------------------

def main():
    rng = np.random.default_rng(1234)

    print("Q8: Channels a/b/c – PAM4 vs ILC3_0c_gp, FFE-only SNR curves")
    print(f"N_sym   = {N_SYM}")
    print(f"SNR_dB  = {SNR_LIST}")
    print(f"FFE_LEN = {FFE_LEN}, FFE_RIDGE = {FFE_RIDGE}")
    print("")

    results = []

    for ch_name, h in CHANNELS:
        print(f"--- Channel {ch_name}: h = {h} ---")

        w_ffe = design_ffe_mmse(h, length=FFE_LEN, ridge=FFE_RIDGE)
        print(f"[FFE DESIGN] channel {ch_name}")
        print(f"w_ffe (len={len(w_ffe)}): {w_ffe}")
        print("")

        for snr_db in SNR_LIST:
            print(f"=== ch={ch_name}  SNR = {snr_db:.2f} dB ===")

            pam4_ffe_acc, pam4_ffe_ber = run_pam4_with_ffe_only(
                h=h,
                w_ffe=w_ffe,
                snr_db=snr_db,
                n_sym=N_SYM,
                rng=rng,
            )
            ilc3_ffe_acc, ilc3_ffe_ber = run_ilc3_with_ffe_only(
                h=h,
                w_ffe=w_ffe,
                snr_db=snr_db,
                n_sym=N_SYM,
                rng=rng,
            )

            print(f"PAM4 + FFE       : acc={pam4_ffe_acc:.6f}  ber={pam4_ffe_ber:.6f}")
            print(f"ILC3_0c_gp + FFE : acc={ilc3_ffe_acc:.6f}  ber={ilc3_ffe_ber:.6f}")
            print("")

            results.append(
                (
                    ch_name,
                    snr_db,
                    pam4_ffe_acc,
                    pam4_ffe_ber,
                    ilc3_ffe_acc,
                    ilc3_ffe_ber,
                )
            )

    # CSV 저장
    base_dir = Path(__file__).resolve().parents[1] / "results"
    base_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_path = base_dir / f"q8_all_channels_snr_curve_ffe_only_{ts}.csv"

    header = (
        "channel,snr_db,"
        "pam4_ffe_acc,pam4_ffe_ber,"
        "ilc3_ffe_acc,ilc3_ffe_ber\n"
    )
    with out_path.open("w", encoding="utf-8") as f:
        f.write(header)
        for (ch_name, snr_db,
             pam4_ffe_acc, pam4_ffe_ber,
             ilc3_ffe_acc, ilc3_ffe_ber) in results:
            f.write(
                f"{ch_name},{snr_db:.2f},"
                f"{pam4_ffe_acc:.6f},{pam4_ffe_ber:.6f},"
                f"{ilc3_ffe_acc:.6f},{ilc3_ffe_ber:.6f}\n"
            )

    print(f"[WRITE] {out_path}")


if __name__ == "__main__":
    main()