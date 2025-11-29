#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Q9: Channel b – PAM4 vs ILC3_0c_gp, FFE-only confusion matrices

Channel b:
    h_b = [0.05 0.50  1.00  0.50  0.05]

- PAM4:       4-PAM levels [-3, -1, +1, +3]
- ILC3_0c_gp: 3-PAM levels [-1, 0, +1]  (여기서는 guard phase 없이 진폭 성능만 비교)

조건:
    N_sym   = 200000
    SNR_dB  = [6.0, 8.0, 10.0, 12.0]
    FFE_LEN = 11, FFE_RIDGE = 0.001

각 SNR에 대해:
    - PAM4 + FFE: acc, ber, 4x4 confusion matrix
    - ILC3 + FFE: acc, ber, 3x3 confusion matrix

결과는 콘솔 출력 + JSON 파일로 저장:
    results/q9_chanb_confmat_ffe_only_YYYY-MM-DD_HH-MM-SS.json
"""

import json
from datetime import datetime
from pathlib import Path

import numpy as np

# ---------------------------
# 채널 / 코드북 / 파라미터
# ---------------------------

H_B = np.array([0.05, 0.50, 1.00, 0.50, 0.05], dtype=float)

PAM4_LEVELS = np.array([-3.0, -1.0, +1.0, +3.0], dtype=float)
ILC3_LEVELS = np.array([-1.0, 0.0, +1.0], dtype=float)

N_SYM = 200_000
SNR_LIST = [6.0, 8.0, 10.0, 12.0]

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

    # convolution matrix A
    A = np.zeros((conv_len, L), dtype=float)
    for i in range(conv_len):
        for k in range(L):
            j = i - k
            if 0 <= j < len(h):
                A[i, k] = h[j]

    # desired response: 중앙에서 1, 나머지는 0 (Nyquist-like)
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


def pam4_hard_decision(y: np.ndarray) -> np.ndarray:
    """PAM4: 최인접 레벨 slicing."""
    y = np.asarray(y, dtype=float)
    idx = np.argmin(np.abs(y[:, None] - PAM4_LEVELS[None, :]), axis=1)
    return idx


def ilc3_hard_decision(y: np.ndarray) -> np.ndarray:
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


def compute_confusion_matrix(gt_idx: np.ndarray, dec_idx: np.ndarray, num_classes: int) -> np.ndarray:
    """
    gt_idx, dec_idx (0..num_classes-1)를 받아 confusion matrix를 계산.
    rows = GT, cols = DEC.
    """
    gt_idx = np.asarray(gt_idx, dtype=int)
    dec_idx = np.asarray(dec_idx, dtype=int)
    cm = np.zeros((num_classes, num_classes), dtype=int)
    for g, d in zip(gt_idx, dec_idx):
        if 0 <= g < num_classes and 0 <= d < num_classes:
            cm[g, d] += 1
    return cm


def run_scheme_with_confmat(
    scheme: str,
    h: np.ndarray,
    w_ffe: np.ndarray,
    snr_db: float,
    n_sym: int,
    rng: np.random.Generator,
):
    """
    scheme: "PAM4" or "ILC3"
    """
    if scheme == "PAM4":
        num_classes = 4
        gt_idx, x = pam4_generate_symbols(n_sym, rng)
        y_eq_no_noise = apply_channel_and_ffe(x, h, w_ffe)
        y_eq = add_awgn(y_eq_no_noise, snr_db, rng)
        dec_idx = pam4_hard_decision(y_eq)
    elif scheme == "ILC3":
        num_classes = 3
        gt_idx, x = ilc3_generate_symbols(n_sym, rng)
        y_eq_no_noise = apply_channel_and_ffe(x, h, w_ffe)
        y_eq = add_awgn(y_eq_no_noise, snr_db, rng)
        dec_idx = ilc3_hard_decision(y_eq)
    else:
        raise ValueError(f"Unknown scheme: {scheme}")

    acc = float(np.mean(dec_idx == gt_idx))
    ber = 1.0 - acc
    cm = compute_confusion_matrix(gt_idx, dec_idx, num_classes=num_classes)
    return acc, ber, cm


# ---------------------------
# 메인 루프
# ---------------------------

def main():
    rng = np.random.default_rng(1234)

    print("Q9: Channel b – PAM4 vs ILC3_0c_gp, FFE-only confusion matrices")
    print(f"Channel b h = {H_B}")
    print(f"N_sym   = {N_SYM}")
    print(f"SNR_dB  = {SNR_LIST}")
    print(f"FFE_LEN = {FFE_LEN}, FFE_RIDGE = {FFE_RIDGE}")
    print("")

    # FFE 설계 (b 채널 기준, 한 번만)
    w_ffe = design_ffe_mmse(H_B, length=FFE_LEN, ridge=FFE_RIDGE)
    print("[FFE DESIGN] channel b")
    print(f"w_ffe (len={len(w_ffe)}): {w_ffe}")
    print("")

    results = {
        "channel": "b",
        "h": H_B.tolist(),
        "n_sym": int(N_SYM),
        "ffe_len": int(FFE_LEN),
        "ffe_ridge": float(FFE_RIDGE),
        "snr_list": [float(s) for s in SNR_LIST],
        "schemes": {
            "PAM4": [],
            "ILC3_0c_gp": [],
        },
    }

    for snr_db in SNR_LIST:
        print(f"=== SNR = {snr_db:.2f} dB ===")

        # PAM4
        pam4_acc, pam4_ber, pam4_cm = run_scheme_with_confmat(
            scheme="PAM4",
            h=H_B,
            w_ffe=w_ffe,
            snr_db=snr_db,
            n_sym=N_SYM,
            rng=rng,
        )
        print(f"[PAM4 + FFE] acc={pam4_acc:.6f}  ber={pam4_ber:.6f}")
        print("[PAM4 confmat] rows=GT(0..3) cols=DEC(0..3)")
        for row in pam4_cm:
            print(" ", " ".join(f"{v:d}" for v in row))

        print("")

        # ILC3
        ilc3_acc, ilc3_ber, ilc3_cm = run_scheme_with_confmat(
            scheme="ILC3",
            h=H_B,
            w_ffe=w_ffe,
            snr_db=snr_db,
            n_sym=N_SYM,
            rng=rng,
        )
        print(f"[ILC3_0c_gp + FFE] acc={ilc3_acc:.6f}  ber={ilc3_ber:.6f}")
        print("[ILC3 confmat] rows=GT(0..2) cols=DEC(0..2)")
        for row in ilc3_cm:
            print(" ", " ".join(f"{v:d}" for v in row))

        print("")

        # JSON용으로 저장
        results["schemes"]["PAM4"].append(
            {
                "snr_db": float(snr_db),
                "acc": float(pam4_acc),
                "ber": float(pam4_ber),
                "confmat": pam4_cm.tolist(),
            }
        )
        results["schemes"]["ILC3_0c_gp"].append(
            {
                "snr_db": float(snr_db),
                "acc": float(ilc3_acc),
                "ber": float(ilc3_ber),
                "confmat": ilc3_cm.tolist(),
            }
        )

    # JSON 저장
    base_dir = Path(__file__).resolve().parents[1] / "results"
    base_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_path = base_dir / f"q9_chanb_confmat_ffe_only_{ts}.json"

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"[WRITE] {out_path}")


if __name__ == "__main__":
    main()