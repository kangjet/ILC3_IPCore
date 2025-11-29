#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Q6: Channel b – PAM4 vs ILC3_0c_gp with FFE, and PAM4+DFE (SNR sweep)
    h_b = [0.05 0.5  1.   0.5  0.05]

- PAM4: 4-PAM levels [-3, -1, +1, +3]
- ILC3_0c_gp: 3-PAM levels [-1, 0, +1]  (guard phase는 여기서는 진폭 성능만 비교)

SNR_dB sweep, FFE 고정, DFE 고정 조건에서
PAM4+FFE, PAM4+FFE+DFE, ILC3_0c_gp+FFE 성능 비교하고 CSV로 저장.
"""

import numpy as np
from pathlib import Path
from datetime import datetime


# ---------------------------
# 기본 설정
# ---------------------------

# 채널 b (가장 센 ISI 채널)
H_B = np.array([0.05, 0.5, 1.0, 0.5, 0.05], dtype=float)

# 코드북
PAM4_LEVELS = np.array([-3.0, -1.0, +1.0, +3.0], dtype=float)
ILC3_LEVELS = np.array([-1.0, 0.0, +1.0], dtype=float)

# 실험 파라미터 (Q5와 일관되게 맞추는 용도)
N_SYM = 200_000
SNR_LIST = [8.0, 10.0, 12.0]
FFE_LEN = 11
FFE_RIDGE = 0.001
DFE_LEN = 5
DFE_RIDGE = 0.0001
TRAIN_FRAC = 0.25  # DFE 학습에 사용하는 심볼 비율


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
    # convolution matrix A (conv(h, w))
    A = np.zeros((conv_len, L), dtype=float)
    for i in range(conv_len):
        for k in range(L):
            j = i - k
            if 0 <= j < len(h):
                A[i, k] = h[j]
    # desired impulse: 중앙 샘플만 1
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
    """ILC3_0c_gp: 진폭 기준 3-PAM slicing (guard phase는 이후 FEC/논리 단계에서 반영)."""
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


def design_pam4_dfe(z: np.ndarray,
                    x_train: np.ndarray,
                    dfe_len: int,
                    ridge: float,
                    train_frac: float,
                    levels: np.ndarray,
                    rng: np.random.Generator):
    """
    간단한 decision-feedback equalizer 설계 (PAM4 전용).
    구조:
        x_hat[n] ≈ c0 * z[n] + Σ_{m=1..M} b_m * x[n-m]

    학습 구간에서는 ground-truth x_train을 그대로 피드백에 사용해서
    선형 회귀로 c0, b_m 추정.
    """
    N = len(x_train)
    N_train = int(N * train_frac)
    if N_train <= dfe_len + 10:
        N_train = N - dfe_len - 1

    # 학습용 샘플 인덱스
    idx_start = dfe_len
    idx_end = N_train
    num_samples = idx_end - idx_start
    if num_samples <= 0:
        raise ValueError("Not enough samples for DFE training")

    # 회귀 행렬 H 및 타겟 t 구성
    # r_n = [z[n], x[n-1], x[n-2], ..., x[n-dfe_len]]
    # t_n = x[n]
    H = np.zeros((num_samples, 1 + dfe_len), dtype=float)
    t = np.zeros(num_samples, dtype=float)

    for i, n in enumerate(range(idx_start, idx_end)):
        # feedforward 입력
        H[i, 0] = z[n]
        # feedback 입력 (ground-truth 심볼)
        for k in range(1, 1 + dfe_len):
            H[i, k] = x_train[n - k]
        t[i] = x_train[n]

    # ridge regression
    A = H.T @ H
    if ridge > 0:
        A += ridge * np.eye(A.shape[0])
    b = H.T @ t
    w = np.linalg.solve(A, b)  # shape (1 + dfe_len,)

    return w  # w[0] = c0, w[1:] = feedback taps


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


def run_pam4_with_ffe_dfe(h: np.ndarray,
                           w_ffe: np.ndarray,
                           snr_db: float,
                           n_sym: int,
                           dfe_len: int,
                           dfe_ridge: float,
                           train_frac: float,
                           rng: np.random.Generator):
    # 전체 심볼/채널 + FFE
    gt_idx, x = pam4_generate_symbols(n_sym, rng)
    y_eq_no_noise = apply_channel_and_ffe(x, h, w_ffe)
    y_eq = add_awgn(y_eq_no_noise, snr_db, rng)

    # DFE 학습 (ground-truth x 사용)
    w_dfe = design_pam4_dfe(
        z=y_eq,
        x_train=x,
        dfe_len=dfe_len,
        ridge=dfe_ridge,
        train_frac=train_frac,
        levels=PAM4_LEVELS,
        rng=rng,
    )

    # DFE 적용 (decision-directed)
    c0 = w_dfe[0]
    fb = w_dfe[1:]  # 길이 dfe_len
    dfe_len = len(fb)

    # 출력/디텍션
    N = len(x)
    dec_idx = np.zeros(N, dtype=int)
    # 초기 구간은 순수 FFE 출력으로만 결정 (feedback 없음)
    for n in range(N):
        if n < dfe_len:
            y_hat = c0 * y_eq[n]
        else:
            fb_term = 0.0
            for k in range(1, dfe_len + 1):
                fb_term += fb[k - 1] * PAM4_LEVELS[dec_idx[n - k]]
            y_hat = c0 * y_eq[n] + fb_term
        # PAM4 slicing
        dec_idx[n] = np.argmin(np.abs(y_hat - PAM4_LEVELS))

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

    print("Q6: Channel b – PAM4 vs ILC3_0c_gp with FFE, and PAM4+DFE (SNR sweep)")
    print(f"Channel b h = {H_B}")
    print(f"N_sym   = {N_SYM}")
    print(f"SNR_dB  = {SNR_LIST}")
    print(f"FFE_LEN = {FFE_LEN}, FFE_RIDGE = {FFE_RIDGE}")
    print(f"DFE_LEN = {DFE_LEN}, DFE_RIDGE = {DFE_RIDGE}, TRAIN_FRAC = {TRAIN_FRAC}")
    print("")

    # FFE 설계 (채널 b 기준)
    w_ffe = design_ffe_mmse(H_B, length=FFE_LEN, ridge=FFE_RIDGE)
    print("[FFE DESIGN] channel b")
    print(f"h_b = {H_B}")
    print(f"w_ffe (len={len(w_ffe)}): {w_ffe}")
    print("")

    results = []
    for snr_db in SNR_LIST:
        print(f"=== SNR = {snr_db:.2f} dB ===")
        pam4_ffe_acc, pam4_ffe_ber = run_pam4_with_ffe_only(
            h=H_B,
            w_ffe=w_ffe,
            snr_db=snr_db,
            n_sym=N_SYM,
            rng=rng,
        )
        pam4_ffe_dfe_acc, pam4_ffe_dfe_ber = run_pam4_with_ffe_dfe(
            h=H_B,
            w_ffe=w_ffe,
            snr_db=snr_db,
            n_sym=N_SYM,
            dfe_len=DFE_LEN,
            dfe_ridge=DFE_RIDGE,
            train_frac=TRAIN_FRAC,
            rng=rng,
        )
        ilc3_ffe_acc, ilc3_ffe_ber = run_ilc3_with_ffe_only(
            h=H_B,
            w_ffe=w_ffe,
            snr_db=snr_db,
            n_sym=N_SYM,
            rng=rng,
        )

        print(f"PAM4 + FFE       : acc={pam4_ffe_acc:.6f}  ber={pam4_ffe_ber:.6f}")
        print(f"PAM4 + FFE + DFE : acc={pam4_ffe_dfe_acc:.6f}  ber={pam4_ffe_dfe_ber:.6f}")
        print(f"ILC3_0c_gp + FFE : acc={ilc3_ffe_acc:.6f}  ber={ilc3_ffe_ber:.6f}")
        print("")

        results.append(
            (
                snr_db,
                pam4_ffe_acc,
                pam4_ffe_ber,
                pam4_ffe_dfe_acc,
                pam4_ffe_dfe_ber,
                ilc3_ffe_acc,
                ilc3_ffe_ber,
            )
        )

    # CSV 저장
    base_dir = Path(__file__).resolve().parents[1] / "results"
    base_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_path = base_dir / f"q6_chanb_snr_sweep_ffe_dfe_{ts}.csv"

    header = (
        "snr_db,"
        "pam4_ffe_acc,pam4_ffe_ber,"
        "pam4_ffe_dfe_acc,pam4_ffe_dfe_ber,"
        "ilc3_ffe_acc,ilc3_ffe_ber\n"
    )
    with out_path.open("w", encoding="utf-8") as f:
        f.write(header)
        for (snr_db,
             pam4_ffe_acc, pam4_ffe_ber,
             pam4_ffe_dfe_acc, pam4_ffe_dfe_ber,
             ilc3_ffe_acc, ilc3_ffe_ber) in results:
            f.write(
                f"{snr_db:.2f},"
                f"{pam4_ffe_acc:.6f},{pam4_ffe_ber:.6f},"
                f"{pam4_ffe_dfe_acc:.6f},{pam4_ffe_dfe_ber:.6f},"
                f"{ilc3_ffe_acc:.6f},{ilc3_ffe_ber:.6f}\n"
            )

    print(f"[WRITE] {out_path}")


if __name__ == "__main__":
    main()